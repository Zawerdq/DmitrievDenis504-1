"""ROS 2-узел моста: команды гусеницам -> ESP32, состояние связи -> ROS."""

from __future__ import annotations

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, Float32MultiArray, String

from susanin_esp32_bridge.link import Esp32Link, LinkConfig

LATCHED_QOS = QoSProfile(
    depth=1,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)


class BridgeNode(Node):

    def __init__(self) -> None:
        super().__init__('susanin_esp32_bridge')

        transport = str(self.declare_parameter('transport', 'websocket').value)
        if transport != 'websocket':
            raise ValueError(
                f"transport='{transport}' не поддерживается: текущая прошивка ESP32 "
                "принимает команды только по WebSocket (см. docs/AUDIT.md)")

        defaults = LinkConfig()
        cfg = LinkConfig(**{
            name: self.declare_parameter(name, value).value
            for name, value in vars(defaults).items()
        })
        cfg.validate()

        logger = self.get_logger()
        self._link = Esp32Link(cfg, log=lambda level, text: getattr(logger, level)(text))

        self._connected_pub = self.create_publisher(
            Bool, 'susanin/esp32/connected', LATCHED_QOS)
        self._diag_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.create_subscription(
            Float32MultiArray, 'susanin/track_cmd', self._on_track_cmd, 10)
        self.create_subscription(Bool, 'susanin/e_stop', self._on_estop, 10)
        self.create_subscription(Bool, 'susanin/led', self._on_led, 10)
        # Пока режим никто не объявил, мост активен (как раньше, без узла режимов).
        self.create_subscription(String, 'susanin/mode', self._on_mode, 10)
        self._mode = ''

        self._last_connected = None
        self._ticks = 0
        self.create_timer(0.1, self._publish_state)
        self.create_timer(1.0, self._publish_diagnostics)

        self._link.start()
        logger.info(
            f'Мост запущен: ws://{cfg.host}:{cfg.port}{cfg.path}, '
            f'{cfg.send_rate:.0f} Гц, таймаут команды {cfg.command_timeout} с')

    def _on_track_cmd(self, msg: Float32MultiArray) -> None:
        if len(msg.data) != 2:
            self.get_logger().warning(
                'susanin/track_cmd должен содержать 2 числа [левая, правая]',
                throttle_duration_sec=2.0)
            return
        self._link.set_tracks(msg.data[0], msg.data[1])

    def _on_estop(self, msg: Bool) -> None:
        self._link.set_estop(msg.data)

    def _on_led(self, msg: Bool) -> None:
        self._link.set_led(msg.data)

    def _on_mode(self, msg: String) -> None:
        mode = msg.data.strip().lower()
        if mode == self._mode:
            return
        if mode not in ('manual', 'auto'):
            self.get_logger().warning(
                f'Неизвестный режим «{msg.data}»', throttle_duration_sec=5.0)
            return
        self._mode = mode
        self._link.set_active(mode == 'auto')
        if mode == 'manual':
            self.get_logger().info('Ручной режим: мост молчит, управляет веб-джойстик ESP32')
        else:
            self.get_logger().info('Режим AUTO: мост передаёт команды ROS')

    def _publish_state(self) -> None:
        connected = self._link.connected
        self._ticks += 1
        # Публикуем при изменении и раз в секунду (на случай пропуска сообщения).
        if connected != self._last_connected or self._ticks % 10 == 0:
            self._last_connected = connected
            self._connected_pub.publish(Bool(data=connected))

    def _publish_diagnostics(self) -> None:
        stats = self._link.stats()
        status = DiagnosticStatus(name='susanin_esp32_bridge: связь с ESP32',
                                  hardware_id='esp32')
        if stats.connected:
            status.level = DiagnosticStatus.OK
            status.message = 'связь есть'
        else:
            status.level = DiagnosticStatus.ERROR
            status.message = stats.last_error or 'нет связи'
        rtt = '' if stats.last_rtt_ms is None else f'{stats.last_rtt_ms:.1f}'
        status.values = [
            KeyValue(key='connected', value=str(stats.connected)),
            KeyValue(key='connects', value=str(stats.connects)),
            KeyValue(key='tx_count', value=str(stats.tx_count)),
            KeyValue(key='rtt_ms', value=rtt),
            KeyValue(key='last_x', value=str(stats.last_xy[0])),
            KeyValue(key='last_y', value=str(stats.last_xy[1])),
            KeyValue(key='command_stale', value=str(stats.command_stale)),
            KeyValue(key='estop', value=str(stats.estop)),
            KeyValue(key='active', value=str(stats.active)),
        ]
        msg = DiagnosticArray(status=[status])
        msg.header.stamp = self.get_clock().now().to_msg()
        self._diag_pub.publish(msg)

    def destroy_node(self) -> None:
        self._link.stop()   # последним сообщением уходит останов
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = BridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

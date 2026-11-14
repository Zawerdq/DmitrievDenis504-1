"""ROS 2-узел управления: /cmd_vel -> ограничения, рампа, останов -> команды гусеницам."""

from __future__ import annotations

import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, Float32MultiArray, String

from susanin_control.track_controller import ControlConfig, TrackController

# «Защёлкнутый» QoS: поздно подключившийся узел сразу получает последнее значение.
LATCHED_QOS = QoSProfile(
    depth=1,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)


class ControlNode(Node):

    def __init__(self) -> None:
        super().__init__('susanin_control')

        defaults = ControlConfig()
        cfg = ControlConfig(**{
            name: float(self.declare_parameter(name, getattr(defaults, name)).value)
            for name in vars(defaults)
        })
        cfg.validate()
        self._controller = TrackController(cfg)

        rate = float(self.declare_parameter('control_rate', 20.0).value)
        if rate <= 0.0:
            raise ValueError('control_rate должен быть > 0')
        # Пока мост не сообщил о связи с ESP32, считаем, что связи нет.
        self._require_link = bool(self.declare_parameter('require_link', True).value)
        self._controller.set_link_ok(not self._require_link)

        self._pub = self.create_publisher(Float32MultiArray, 'susanin/track_cmd', 10)
        self.create_subscription(Twist, 'cmd_vel', self._on_cmd_vel, 10)
        self.create_subscription(Bool, 'susanin/e_stop', self._on_estop, 10)
        self.create_subscription(
            Bool, 'susanin/esp32/connected', self._on_link, LATCHED_QOS)
        self.create_subscription(String, 'susanin/mode', self._on_mode, 10)
        self.create_timer(1.0 / rate, self._tick)

        self._was_timed_out = True
        self.get_logger().info(
            f'Управление запущено: колея {cfg.track_width} м, '
            f'max_duty {cfg.max_duty}, таймаут /cmd_vel {cfg.cmd_vel_timeout} с')

    def _on_cmd_vel(self, msg: Twist) -> None:
        if not self._controller.set_twist(msg.linear.x, msg.angular.z, time.monotonic()):
            self.get_logger().warning(
                'Отброшена команда /cmd_vel с NaN/inf', throttle_duration_sec=2.0)

    def _on_estop(self, msg: Bool) -> None:
        if msg.data != self._controller.estop_active:
            if msg.data:
                self.get_logger().error('АВАРИЙНЫЙ ОСТАНОВ активирован')
            else:
                self.get_logger().warning('Аварийный останов снят')
        self._controller.set_estop(msg.data)

    def _on_link(self, msg: Bool) -> None:
        if not self._require_link:
            return
        if msg.data != self._controller.link_ok:
            if msg.data:
                self.get_logger().info('Связь с ESP32 есть — движение разрешено')
            else:
                self.get_logger().error('Связь с ESP32 потеряна — команды обнулены')
        self._controller.set_link_ok(msg.data)

    def _on_mode(self, msg: String) -> None:
        mode = msg.data.strip().lower()
        if mode in ('manual', 'auto'):
            self._controller.set_enabled(mode == 'auto')

    def _tick(self) -> None:
        left, right = self._controller.step(time.monotonic())
        timed_out = self._controller.timed_out
        if timed_out and not self._was_timed_out:
            self.get_logger().warning('Нет свежих команд /cmd_vel — останов')
        self._was_timed_out = timed_out
        self._pub.publish(Float32MultiArray(data=[left, right]))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ControlNode()
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

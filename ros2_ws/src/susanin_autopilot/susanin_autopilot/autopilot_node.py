"""ROS 2-узел автопилота: камера -> зрение -> шаги трассы -> /cmd_vel.

Команды публикуются только в режиме ``auto`` (топик susanin/mode). При любом
другом режиме узел молчит, и робот останавливается по таймауту узла управления.
"""

from __future__ import annotations

import os
import time

import cv2
from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String

from susanin_autopilot import autopilot as ap
from susanin_autopilot.frame_source import FrameSource, LatestFrame
from susanin_autopilot.params import declare_dataclass
from susanin_autopilot.vision import analyze, draw_debug, VisionConfig

MODE_AUTO = 'auto'
STALE_FRAME_AFTER = 1.0   # с: кадр старше этого показывается оператору как устаревший


class AutopilotNode(Node):

    def __init__(self) -> None:
        super().__init__('susanin_autopilot')
        self._vision = declare_dataclass(self, 'vision', VisionConfig())
        self._vision.validate()
        pilot_cfg = declare_dataclass(self, 'pilot', ap.AutopilotConfig())
        pilot_cfg.route = [event for event in pilot_cfg.route if event]   # [''] = пустой маршрут
        self._pilot = ap.Autopilot(pilot_cfg)

        self._source_spec = str(self.declare_parameter('source', '/dev/video0').value)
        self._capture_size = (
            int(self.declare_parameter('capture_width', 640).value),
            int(self.declare_parameter('capture_height', 480).value),
            float(self.declare_parameter('capture_fps', 30.0).value),
        )
        self._loop_source = bool(self.declare_parameter('loop_source', False).value)
        rate = float(self.declare_parameter('rate', 20.0).value)
        self._debug_period = float(self.declare_parameter('debug_image_period', 0.5).value)
        self._record_dir = str(self.declare_parameter('record_dir', '').value)

        self._cmd_pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self._state_pub = self.create_publisher(String, 'susanin/autopilot/state', 10)
        self._debug_pub = self.create_publisher(
            CompressedImage, 'susanin/autopilot/debug/compressed', 2)
        self.create_subscription(String, 'susanin/mode', self._on_mode, 10)

        self._frames = None
        self._live = True
        self._next_open = 0.0
        self._mode = ''
        self._last_state = ''
        self._last_state_pub = 0.0
        self._last_debug = 0.0
        self._last_obs = None
        self._last_frame = None
        self._last_frame_time = 0.0
        self._run_dir = ''
        self._frame_count = 0

        self.create_timer(1.0 / rate, self._tick)
        self.get_logger().info(
            f'Автопилот запущен: источник {self._source_spec}, {rate:.0f} Гц, '
            f'маска «{self._vision.track_mode}», маршрут {self._pilot.cfg.route}')

    # ---- камера ------------------------------------------------------------

    def _ensure_source(self, now: float) -> None:
        if self._frames is not None and (not self._frames.ended or not self._live):
            return                               # работает, либо файл записи закончился
        if now < self._next_open:
            return
        self._next_open = now + 2.0
        if self._frames is not None:
            self._frames.stop()
            self._frames = None
            self.get_logger().error('Источник кадров пропал, пробую открыть снова')
        try:
            width, height, fps = self._capture_size
            source = FrameSource(self._source_spec, width, height, fps, self._loop_source)
        except OSError as exc:
            self.get_logger().error(f'Камера недоступна: {exc}', throttle_duration_sec=10.0)
            return
        self._live = source.live
        self._frames = LatestFrame(source).start()
        self.get_logger().info(f'Источник кадров открыт: {self._source_spec}')

    # ---- режим -------------------------------------------------------------

    def _on_mode(self, msg: String) -> None:
        mode = msg.data.strip().lower()
        if mode == self._mode:
            return
        self._mode = mode
        if mode == MODE_AUTO:
            self._pilot.start(time.monotonic())
            self._start_recording()
            self.get_logger().warning('Режим AUTO: автопилот начал заезд')
        else:
            self._pilot.stop(f'mode_{mode}')
            self._cmd_pub.publish(Twist())      # явный ноль при выходе из автономного режима
            self.get_logger().info(f'Режим «{mode}»: автопилот выключен')

    def _start_recording(self) -> None:
        self._run_dir = ''
        if not self._record_dir:
            return
        run_dir = os.path.join(self._record_dir, time.strftime('run_%Y%m%d_%H%M%S'))
        try:
            os.makedirs(run_dir, exist_ok=True)
        except OSError as exc:
            self.get_logger().error(f'Запись заезда отключена: {exc}')
            return
        self._run_dir = run_dir
        self._frame_count = 0

    # ---- основной такт -----------------------------------------------------

    def _tick(self) -> None:
        now = time.monotonic()
        self._ensure_source(now)

        obs = None
        if self._frames is not None:
            frame, _stamp, fresh = self._frames.get()
            if fresh and frame is not None:
                obs = analyze(frame, self._vision)
                self._last_obs, self._last_frame = obs, frame
                self._last_frame_time = now
                if self._run_dir and self._pilot.state != ap.IDLE:
                    self._frame_count += 1
                    cv2.imwrite(os.path.join(
                        self._run_dir, f'{self._frame_count:06d}_{time.time():.3f}.jpg'), frame)

        command = self._pilot.update(obs, now)
        if command.active:
            twist = Twist()
            twist.linear.x = float(command.linear)
            twist.angular.z = float(command.angular)
            self._cmd_pub.publish(twist)

        text = command.state if not command.reason else f'{command.state}:{command.reason}'
        if text != self._last_state:
            self.get_logger().info(f'Автопилот: {text}')
        if text != self._last_state or (now - self._last_state_pub) >= 0.5:
            self._last_state, self._last_state_pub = text, now
            self._state_pub.publish(String(data=text))

        if (self._debug_period > 0.0 and self._last_frame is not None
                and (now - self._last_debug) >= self._debug_period):
            self._last_debug = now
            age = now - self._last_frame_time
            image = draw_debug(self._last_frame, self._last_obs, self._vision, text,
                               stale_seconds=age if age > STALE_FRAME_AFTER else 0.0)
            ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                msg = CompressedImage(format='jpeg', data=encoded.tobytes())
                msg.header.stamp = self.get_clock().now().to_msg()
                self._debug_pub.publish(msg)

    def destroy_node(self) -> None:
        if self._frames is not None:
            self._frames.stop()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = AutopilotNode()
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

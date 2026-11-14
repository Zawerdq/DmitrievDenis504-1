"""Логика управления гусеничной платформой «Сусанин ИИ» (без зависимостей от ROS).

Цепочка преобразований на каждом такте:

    Twist (v, w) -> ограничение скоростей -> скорости гусениц (м/с)
      -> скважность [-1..1] -> плавный разгон/торможение (рампа)
      -> мёртвая зона / минимальная скважность -> команда гусеницам

Платформа управляется в разомкнутом контуре: энкодеров нет, поэтому
«скорость» — это скважность ШИМ, пересчитанная через калибровочный
коэффициент ``max_track_speed`` (скорость гусеницы при скважности 1.0).

Модуль намеренно не импортирует rclpy, чтобы его можно было тестировать
на любом компьютере обычным pytest.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Tuple


@dataclass
class ControlConfig:
    """Параметры управления. Значения по умолчанию — консервативные заглушки."""

    # Геометрия и калибровка (НЕ ИЗМЕРЕНО на реальном роботе — см. docs/SETUP.md)
    track_width: float = 0.15        # м, эффективная колея (расстояние между гусеницами)
    max_track_speed: float = 0.30    # м/с, скорость гусеницы при скважности 1.0

    # Ограничения входной команды
    max_linear_speed: float = 0.20   # м/с
    max_angular_speed: float = 1.50  # рад/с

    # Ограничения выходной скважности
    max_duty: float = 0.60           # доля от полного ШИМ (ограничение тока и скорости)
    min_duty: float = 0.25           # ниже этого мотор стоит под током -> не используем
    duty_deadband: float = 0.03      # всё, что меньше, считается нулём

    # Рампа, 1/с: 2.0 означает разгон 0 -> 1.0 за 0.5 с
    max_accel_rate: float = 2.0
    max_decel_rate: float = 4.0

    # Безопасность
    cmd_vel_timeout: float = 0.5     # с без /cmd_vel до остановки

    def validate(self) -> None:
        """Проверить параметры; при ошибке бросить ValueError с понятным текстом."""
        positive = {
            'track_width': self.track_width,
            'max_track_speed': self.max_track_speed,
            'max_linear_speed': self.max_linear_speed,
            'max_angular_speed': self.max_angular_speed,
            'max_accel_rate': self.max_accel_rate,
            'max_decel_rate': self.max_decel_rate,
            'cmd_vel_timeout': self.cmd_vel_timeout,
        }
        for name, value in positive.items():
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f'{name} должен быть > 0, получено {value!r}')
        if not 0.0 < self.max_duty <= 1.0:
            raise ValueError(f'max_duty должен быть в (0, 1], получено {self.max_duty!r}')
        if not 0.0 <= self.min_duty < self.max_duty:
            raise ValueError(
                f'min_duty должен быть в [0, max_duty), получено {self.min_duty!r}')
        if not 0.0 <= self.duty_deadband <= max(self.min_duty, 0.5):
            raise ValueError(
                f'duty_deadband вне допустимого диапазона: {self.duty_deadband!r}')


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def twist_to_duty(linear: float, angular: float, cfg: ControlConfig) -> Tuple[float, float]:
    """Преобразовать (v, w) в целевые скважности (левая, правая) в [-max_duty, max_duty].

    Соглашение ROS (REP-103): linear > 0 — вперёд, angular > 0 — поворот влево
    (против часовой стрелки), значит правая гусеница должна идти быстрее левой.
    Если требуемая скважность превышает ``max_duty``, обе гусеницы
    масштабируются пропорционально, чтобы сохранить кривизну траектории.
    """
    v = clamp(linear, -cfg.max_linear_speed, cfg.max_linear_speed)
    w = clamp(angular, -cfg.max_angular_speed, cfg.max_angular_speed)

    half = cfg.track_width / 2.0
    left = (v - w * half) / cfg.max_track_speed
    right = (v + w * half) / cfg.max_track_speed

    peak = max(abs(left), abs(right))
    if peak > cfg.max_duty:
        scale = cfg.max_duty / peak
        left *= scale
        right *= scale
    return left, right


def slew(current: float, target: float, dt: float, cfg: ControlConfig) -> float:
    """Ограничить скорость изменения скважности.

    Рост модуля ограничен ``max_accel_rate``, уменьшение — ``max_decel_rate``.
    При смене знака сначала тормозим до нуля, затем разгоняемся: это убирает
    бросок тока при мгновенном реверсе мотора.
    """
    if dt <= 0.0 or current == target:
        return current if dt <= 0.0 else target

    if current != 0.0 and (target == 0.0 or (current > 0.0) != (target > 0.0)):
        # Торможение к нулю (в т.ч. перед реверсом).
        step = cfg.max_decel_rate * dt
        if abs(current) <= step:
            return 0.0
        return current - math.copysign(step, current)

    if abs(target) > abs(current):
        step = cfg.max_accel_rate * dt
        return current + clamp(target - current, -step, step)

    step = cfg.max_decel_rate * dt
    return current + clamp(target - current, -step, step)


def shape_duty(duty: float, cfg: ControlConfig) -> float:
    """Убрать зону, в которой мотор не страгивается, но потребляет ток.

    |duty| < duty_deadband  -> 0
    |duty| < min_duty       -> ±min_duty
    """
    magnitude = abs(duty)
    if magnitude < cfg.duty_deadband:
        return 0.0
    if magnitude < cfg.min_duty:
        return math.copysign(cfg.min_duty, duty)
    return clamp(duty, -cfg.max_duty, cfg.max_duty)


class TrackController:
    """Состояние управления: последняя команда, аварийный останов, рампа."""

    def __init__(self, cfg: Optional[ControlConfig] = None):
        self.cfg = cfg or ControlConfig()
        self.cfg.validate()
        self._target = (0.0, 0.0)
        self._ramped = (0.0, 0.0)
        self._last_cmd_time: Optional[float] = None
        self._last_step_time: Optional[float] = None
        self._estop = False
        self._link_ok = True
        self._timed_out = True

    # ---- входы -------------------------------------------------------------

    def set_twist(self, linear: float, angular: float, now: float) -> bool:
        """Принять команду скорости. Возвращает False, если команда отброшена."""
        if not (math.isfinite(linear) and math.isfinite(angular)):
            # NaN/inf нельзя превращать в ШИМ; считаем это отсутствием команды.
            return False
        self._target = twist_to_duty(linear, angular, self.cfg)
        self._last_cmd_time = now
        return True

    def set_estop(self, active: bool) -> None:
        self._estop = bool(active)
        if self._estop:
            self._hard_stop()

    def set_link_ok(self, ok: bool) -> None:
        """Сообщить о состоянии связи с ESP32.

        При потере связи рампа сбрасывается: после восстановления связи робот
        не должен рывком продолжить движение с прежней скважностью.
        """
        self._link_ok = bool(ok)
        if not self._link_ok:
            self._hard_stop()

    # ---- состояние ---------------------------------------------------------

    @property
    def estop_active(self) -> bool:
        return self._estop

    @property
    def link_ok(self) -> bool:
        return self._link_ok

    @property
    def timed_out(self) -> bool:
        """True, если свежей команды /cmd_vel нет."""
        return self._timed_out

    # ---- такт управления ---------------------------------------------------

    def step(self, now: float) -> Tuple[float, float]:
        """Вычислить команду гусеницам (левая, правая) в [-1, 1] на момент ``now``."""
        dt = 0.0 if self._last_step_time is None else max(0.0, now - self._last_step_time)
        self._last_step_time = now

        self._timed_out = (
            self._last_cmd_time is None
            or (now - self._last_cmd_time) > self.cfg.cmd_vel_timeout
        )

        if self._estop or not self._link_ok:
            self._hard_stop()
            return 0.0, 0.0

        target = (0.0, 0.0) if self._timed_out else self._target
        if self._timed_out:
            self._target = (0.0, 0.0)

        self._ramped = (
            slew(self._ramped[0], target[0], dt, self.cfg),
            slew(self._ramped[1], target[1], dt, self.cfg),
        )
        return shape_duty(self._ramped[0], self.cfg), shape_duty(self._ramped[1], self.cfg)

    def _hard_stop(self) -> None:
        self._target = (0.0, 0.0)
        self._ramped = (0.0, 0.0)

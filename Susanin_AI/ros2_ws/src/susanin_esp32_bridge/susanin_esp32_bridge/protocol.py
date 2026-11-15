"""Протокол существующей прошивки ESP32 (DiffrentialControl_invert.ino).

Прошивка НЕ менялась. Она принимает по WebSocket (ws://<ip>/ws, порт 80)
текстовые JSON-сообщения:

    {"x": X, "y": Y}     джойстик, X и Y в диапазоне -255..255
    {"led": 0|1}         светодиод на GPIO2
    {"fire": 0|1}        силовой ключ (MOSFET) на GPIO15 — мостом не используется
    {"invert1": 0|1}     инверсия мотора 1 (состояние хранится в ОЗУ ESP32)
    {"invert2": 0|1}     инверсия мотора 2
    {"lock": 0|1}        блокировка моторов (только прошивка firmware/susanin_esp32;
                         исходная прошивка это сообщение игнорирует)

Микшер прошивки (функция driveMix):

    left  = constrain((y + x) * invert1, -255, 255)   -> motor1 (канал A)
    right = constrain((y - x) * invert2, -255, 255)   -> motor2 (канал B)
    left == 0 и right == 0  -> brake() обоих моторов

Чтобы задать гусеницам нужные ШИМ L и R, решаем систему обратно:

    x = (L - R) / 2,   y = (L + R) / 2
"""

from __future__ import annotations

import json
import math
from typing import Tuple

PWM_MAX = 255


def _unit(value: float) -> float:
    """Привести значение к [-1, 1]; NaN/inf превращаются в 0 (останов)."""
    if not math.isfinite(value):
        return 0.0
    return max(-1.0, min(1.0, value))


def tracks_to_joystick(
    left: float,
    right: float,
    *,
    pwm_max: int = PWM_MAX,
    invert_left: bool = False,
    invert_right: bool = False,
    swap_sides: bool = False,
) -> Tuple[int, int]:
    """Перевести команды гусениц [-1..1] в координаты джойстика прошивки (x, y).

    ``swap_sides`` и ``invert_*`` описывают фактическое подключение моторов и
    задаются в YAML, чтобы не трогать прошивку и провода.
    """
    left = _unit(left)
    right = _unit(right)
    if swap_sides:
        left, right = right, left
    if invert_left:
        left = -left
    if invert_right:
        right = -right

    pwm_max = max(0, min(PWM_MAX, int(pwm_max)))
    left_pwm = int(round(left * pwm_max))
    right_pwm = int(round(right * pwm_max))

    # x и y — целые, поэтому L и R должны быть одной чётности.
    # Уменьшаем по модулю больший из них на 1 (ошибка не более 1/255).
    if (left_pwm + right_pwm) % 2:
        if abs(left_pwm) >= abs(right_pwm):
            left_pwm -= 1 if left_pwm > 0 else -1
        else:
            right_pwm -= 1 if right_pwm > 0 else -1

    return (left_pwm - right_pwm) // 2, (left_pwm + right_pwm) // 2


def firmware_mix(x: int, y: int, invert1: int = 1, invert2: int = 1) -> Tuple[int, int]:
    """Точная копия driveMix() прошивки: (x, y) -> ШИМ (motor1, motor2)."""
    left = max(-PWM_MAX, min(PWM_MAX, (y + x) * invert1))
    right = max(-PWM_MAX, min(PWM_MAX, (y - x) * invert2))
    return left, right


def drive_message(x: int, y: int) -> str:
    return json.dumps({'x': int(x), 'y': int(y)}, separators=(',', ':'))


def led_message(on: bool) -> str:
    return json.dumps({'led': 1 if on else 0}, separators=(',', ':'))


def lock_message(locked: bool) -> str:
    return json.dumps({'lock': 1 if locked else 0}, separators=(',', ':'))


STOP_MESSAGE = drive_message(0, 0)

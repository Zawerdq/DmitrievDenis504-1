"""Тесты преобразования команд гусениц в протокол прошивки."""

import json
import math

import pytest

from susanin_esp32_bridge.protocol import (
    drive_message,
    firmware_mix,
    led_message,
    STOP_MESSAGE,
    tracks_to_joystick,
)


def through_firmware(left, right, **kwargs):
    """Что получат моторы после микшера прошивки."""
    return firmware_mix(*tracks_to_joystick(left, right, **kwargs))


def test_forward():
    assert through_firmware(1.0, 1.0) == (255, 255)


def test_backward():
    assert through_firmware(-1.0, -1.0) == (-255, -255)


def test_spin_left_and_right():
    assert through_firmware(-1.0, 1.0) == (-255, 255)
    assert through_firmware(1.0, -1.0) == (255, -255)


def test_stop_is_exact_zero():
    assert tracks_to_joystick(0.0, 0.0) == (0, 0)
    assert json.loads(STOP_MESSAGE) == {'x': 0, 'y': 0}


@pytest.mark.parametrize('left', [i / 20.0 for i in range(-20, 21)])
@pytest.mark.parametrize('right', [i / 20.0 for i in range(-20, 21)])
def test_roundtrip_error_is_at_most_one_lsb(left, right):
    got_left, got_right = through_firmware(left, right)
    assert abs(got_left - left * 255) <= 1.5
    assert abs(got_right - right * 255) <= 1.5
    x, y = tracks_to_joystick(left, right)
    assert -255 <= x <= 255 and -255 <= y <= 255


def test_out_of_range_is_clamped():
    assert through_firmware(5.0, -7.0) == (255, -255)


def test_nan_becomes_stop():
    assert tracks_to_joystick(math.nan, math.inf) == (0, 0)


def test_pwm_max_scales_output():
    assert through_firmware(1.0, 1.0, pwm_max=100) == (100, 100)


def test_wiring_options():
    assert through_firmware(1.0, 0.0, swap_sides=True) == (0, 254)
    assert through_firmware(1.0, 1.0, invert_left=True) == (-255, 255)
    assert through_firmware(1.0, 1.0, invert_right=True) == (255, -255)


def test_messages_match_firmware_format():
    assert json.loads(drive_message(10, -20)) == {'x': 10, 'y': -20}
    assert json.loads(led_message(True)) == {'led': 1}
    assert json.loads(led_message(False)) == {'led': 0}

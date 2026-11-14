"""Тесты логики управления гусеницами (без ROS и без робота)."""

import math

import pytest

from susanin_control.track_controller import (
    ControlConfig,
    shape_duty,
    slew,
    TrackController,
    twist_to_duty,
)


def make_cfg(**overrides) -> ControlConfig:
    base = dict(
        track_width=0.2,
        max_track_speed=0.5,
        max_linear_speed=0.4,
        max_angular_speed=2.0,
        max_duty=0.8,
        min_duty=0.2,
        duty_deadband=0.02,
        max_accel_rate=2.0,
        max_decel_rate=4.0,
        cmd_vel_timeout=0.5,
    )
    base.update(overrides)
    return ControlConfig(**base)


def run(controller: TrackController, start: float, seconds: float, dt: float = 0.05):
    """Прокрутить контроллер и вернуть последнюю команду."""
    out = (0.0, 0.0)
    steps = int(round(seconds / dt))
    for i in range(steps + 1):
        out = controller.step(start + i * dt)
    return out


# ---- кинематика --------------------------------------------------------------

def test_forward_gives_equal_positive_duty():
    left, right = twist_to_duty(0.25, 0.0, make_cfg())
    assert left == pytest.approx(0.5)
    assert right == pytest.approx(0.5)


def test_backward_gives_equal_negative_duty():
    left, right = twist_to_duty(-0.25, 0.0, make_cfg())
    assert left == pytest.approx(-0.5)
    assert right == pytest.approx(-0.5)


def test_positive_angular_turns_left():
    # REP-103: angular.z > 0 — против часовой, правая гусеница быстрее.
    left, right = twist_to_duty(0.0, 1.0, make_cfg())
    assert left < 0 < right
    assert left == pytest.approx(-right)


def test_negative_angular_turns_right():
    left, right = twist_to_duty(0.0, -1.0, make_cfg())
    assert right < 0 < left


def test_input_limits_are_applied():
    cfg = make_cfg()
    assert twist_to_duty(10.0, 0.0, cfg) == twist_to_duty(cfg.max_linear_speed, 0.0, cfg)
    assert twist_to_duty(0.0, 99.0, cfg) == twist_to_duty(0.0, cfg.max_angular_speed, cfg)


def test_saturation_preserves_turn_ratio():
    cfg = make_cfg(max_duty=0.5)
    raw_left = (0.4 - 2.0 * 0.1) / 0.5   # 0.4
    raw_right = (0.4 + 2.0 * 0.1) / 0.5  # 1.2
    left, right = twist_to_duty(0.4, 2.0, cfg)
    assert max(abs(left), abs(right)) == pytest.approx(cfg.max_duty)
    assert left / right == pytest.approx(raw_left / raw_right)


# ---- рампа и мёртвая зона ----------------------------------------------------

def test_slew_limits_acceleration():
    cfg = make_cfg()
    assert slew(0.0, 1.0, 0.1, cfg) == pytest.approx(0.2)


def test_slew_decelerates_faster_than_accelerates():
    cfg = make_cfg()
    assert slew(0.8, 0.0, 0.1, cfg) == pytest.approx(0.4)


def test_slew_passes_through_zero_on_reversal():
    cfg = make_cfg()
    value = 0.6
    seen_zero = False
    for _ in range(40):
        previous = value
        value = slew(value, -0.6, 0.05, cfg)
        if value == 0.0:
            seen_zero = True
        # знак не может смениться, минуя ноль
        assert not (previous > 0.0 and value < 0.0)
    assert seen_zero
    assert value == pytest.approx(-0.6)


def test_shape_duty_deadband_and_minimum():
    cfg = make_cfg()
    assert shape_duty(0.01, cfg) == 0.0
    assert shape_duty(0.05, cfg) == 0.0                      # ближе к нулю, чем к min_duty
    assert shape_duty(0.15, cfg) == pytest.approx(cfg.min_duty)
    assert shape_duty(-0.15, cfg) == pytest.approx(-cfg.min_duty)
    assert shape_duty(0.5, cfg) == pytest.approx(0.5)
    assert shape_duty(5.0, cfg) == pytest.approx(cfg.max_duty)


# ---- контроллер --------------------------------------------------------------

def test_no_command_means_stop():
    controller = TrackController(make_cfg())
    assert run(controller, 0.0, 1.0) == (0.0, 0.0)
    assert controller.timed_out


def test_command_ramps_up_to_target():
    controller = TrackController(make_cfg())
    controller.step(0.0)
    controller.set_twist(0.25, 0.0, 0.0)
    first = controller.step(0.05)
    assert 0.0 < first[0] < 0.5          # разгон начался, но цель ещё не достигнута
    controller.set_twist(0.25, 0.0, 0.4)
    final = run(controller, 0.4, 0.4)
    assert final == pytest.approx((0.5, 0.5))


def test_stale_command_stops_robot():
    cfg = make_cfg()
    controller = TrackController(cfg)
    controller.step(0.0)
    controller.set_twist(0.25, 0.0, 0.0)
    run(controller, 0.0, 0.4)
    # Команды перестали приходить: через таймаут + время торможения — ноль.
    final = run(controller, 0.45, cfg.cmd_vel_timeout + 0.5)
    assert final == (0.0, 0.0)
    assert controller.timed_out


def test_estop_is_immediate_and_latched():
    controller = TrackController(make_cfg())
    controller.step(0.0)
    controller.set_twist(0.25, 0.0, 0.0)
    assert run(controller, 0.0, 0.4)[0] > 0.0

    controller.set_estop(True)
    assert controller.step(0.45) == (0.0, 0.0)

    # Новые команды при активном останове игнорируются.
    controller.set_twist(0.25, 0.0, 0.5)
    assert controller.step(0.55) == (0.0, 0.0)

    # После снятия останова движение начинается с нуля, а не рывком.
    controller.set_estop(False)
    controller.set_twist(0.25, 0.0, 0.6)
    resumed = controller.step(0.65)
    assert 0.0 < resumed[0] < 0.5


def test_link_loss_resets_ramp():
    controller = TrackController(make_cfg())
    controller.step(0.0)
    controller.set_twist(0.25, 0.0, 0.0)
    run(controller, 0.0, 0.4)

    controller.set_link_ok(False)
    controller.set_twist(0.25, 0.0, 0.45)
    assert controller.step(0.45) == (0.0, 0.0)

    controller.set_link_ok(True)
    controller.set_twist(0.25, 0.0, 0.5)
    resumed = controller.step(0.5)
    assert resumed[0] < 0.5              # разгон заново


def test_nan_command_is_rejected():
    controller = TrackController(make_cfg())
    controller.step(0.0)
    assert not controller.set_twist(math.nan, 0.0, 0.0)
    assert not controller.set_twist(0.1, math.inf, 0.0)
    assert run(controller, 0.0, 0.3) == (0.0, 0.0)


def test_output_never_exceeds_max_duty():
    cfg = make_cfg(max_duty=0.6)
    controller = TrackController(cfg)
    controller.step(0.0)
    for i in range(1, 100):
        now = i * 0.05
        controller.set_twist(10.0, 10.0 if i % 2 else -10.0, now)
        left, right = controller.step(now)
        assert abs(left) <= cfg.max_duty + 1e-9
        assert abs(right) <= cfg.max_duty + 1e-9


@pytest.mark.parametrize('bad', [
    dict(track_width=0.0),
    dict(max_track_speed=-1.0),
    dict(max_duty=1.5),
    dict(min_duty=0.9, max_duty=0.5),
    dict(cmd_vel_timeout=0.0),
])
def test_invalid_config_is_rejected(bad):
    with pytest.raises(ValueError):
        TrackController(make_cfg(**bad))


def test_manual_mode_blocks_commands_and_resets_ramp():
    controller = TrackController(make_cfg())
    controller.step(0.0)
    controller.set_twist(0.25, 0.0, 0.0)
    assert run(controller, 0.0, 0.4)[0] > 0.0

    controller.set_enabled(False)                 # оператор взял управление
    controller.set_twist(0.25, 0.0, 0.45)
    assert controller.step(0.45) == (0.0, 0.0)

    controller.set_enabled(True)
    controller.set_twist(0.25, 0.0, 0.5)
    assert 0.0 < controller.step(0.55)[0] < 0.5   # разгон заново, без рывка

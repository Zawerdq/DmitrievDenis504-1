"""Модульные тесты зрения и автомата шагов на нарисованных кадрах."""

import cv2
import numpy as np
import pytest

from susanin_autopilot import autopilot as ap
from susanin_autopilot.sim import BALLOON, DARK, FINISH, FLOOR, WOOD
from susanin_autopilot.vision import analyze, draw_debug, Observation, VisionConfig

W, H = 320, 240


def frame_with_track(left: int, right: int, color=WOOD) -> np.ndarray:
    """Кадр: синий пол и вертикальная полоса между столбцами left и right."""
    image = np.full((H, W, 3), FLOOR, np.uint8)
    image[:, left:right] = color
    return image


# ---- зрение ------------------------------------------------------------------

def test_centered_track_gives_zero_offset():
    obs = analyze(frame_with_track(100, 220), VisionConfig())
    assert obs.track_found
    assert abs(obs.offset) < 0.03


def test_track_on_the_right_gives_positive_offset():
    obs = analyze(frame_with_track(200, 300), VisionConfig())
    assert obs.track_found and obs.offset > 0.4


def test_track_on_the_left_gives_negative_offset():
    obs = analyze(frame_with_track(20, 120), VisionConfig())
    assert obs.track_found and obs.offset < -0.4


def test_only_floor_means_no_track():
    obs = analyze(np.full((H, W, 3), FLOOR, np.uint8), VisionConfig())
    assert not obs.track_found


def test_far_offset_shows_where_track_bends():
    image = np.full((H, W, 3), FLOOR, np.uint8)
    # Полоса внизу по центру, вверху уходит вправо.
    points = np.array([[110, H - 1], [210, H - 1], [300, 100], [200, 100]], np.int32)
    cv2.fillPoly(image, [points], WOOD)
    obs = analyze(image, VisionConfig())
    assert obs.track_found and obs.far_offset > 0.2


def test_small_blobs_are_ignored():
    image = np.full((H, W, 3), FLOOR, np.uint8)
    image[150:160, 20:30] = WOOD                 # мусор на полу
    obs = analyze(image, VisionConfig())
    assert not obs.track_found


def test_color_and_line_modes():
    wood = analyze(frame_with_track(100, 220), VisionConfig(track_mode='color'))
    assert wood.track_found and abs(wood.offset) < 0.03
    image = frame_with_track(40, 280)
    image[:, 200:212] = (10, 10, 10)             # чёрная лента правее центра
    line = analyze(image, VisionConfig(track_mode='line', min_band_width=0.02,
                                       min_track_fraction=0.005))
    assert line.track_found and line.offset > 0.2


def test_tunnel_balloon_and_finish_are_measured():
    cfg = VisionConfig()
    dark = frame_with_track(100, 220)
    dark[60:, 180:] = DARK
    obs = analyze(dark, cfg)
    assert obs.dark_fraction > 0.3 and obs.dark_offset > 0.3

    balloon = frame_with_track(100, 220)
    cv2.circle(balloon, (160, 140), 70, BALLOON, -1)
    assert analyze(balloon, cfg).balloon_fraction > 0.15

    finish = frame_with_track(100, 220)
    finish[200:, 100:220] = FINISH
    assert analyze(finish, cfg).finish_fraction > 0.1

    clean = analyze(frame_with_track(100, 220), cfg)
    assert clean.dark_fraction < 0.02 and clean.balloon_fraction < 0.01
    assert clean.finish_fraction < 0.01


def test_any_frame_size_is_accepted_and_debug_image_is_drawn():
    big = cv2.resize(frame_with_track(100, 220), (1280, 720))
    cfg = VisionConfig()
    obs = analyze(big, cfg)
    assert obs.track_found
    debug = draw_debug(big, obs, cfg, 'follow')
    assert debug.shape == (cfg.height, cfg.width, 3)


@pytest.mark.parametrize('bad', [dict(track_mode='magic'), dict(bands=1),
                                 dict(floor_hsv_low=[1, 2]), dict(roi_top=1.0)])
def test_invalid_vision_config(bad):
    with pytest.raises(ValueError):
        VisionConfig(**bad).validate()


# ---- автомат шагов -----------------------------------------------------------

def seen(offset=0.0, **fields) -> Observation:
    return Observation(track_found=True, offset=offset, **fields)


def test_idle_until_started():
    pilot = ap.Autopilot()
    command = pilot.update(seen(), 0.0)
    assert command.state == ap.IDLE and not command.active
    assert command.linear == 0.0 and command.angular == 0.0


def test_steering_sign_follows_ros_convention():
    pilot = ap.Autopilot(ap.AutopilotConfig(route=[]))
    pilot.start(0.0)
    right = pilot.update(seen(offset=0.5), 0.05)     # полоса справа -> поворот вправо
    assert right.angular < 0 and right.linear > 0
    left = pilot.update(seen(offset=-0.5), 0.10)     # полоса слева -> поворот влево
    assert left.angular > 0


def test_slows_down_in_turns_and_respects_limits():
    cfg = ap.AutopilotConfig(route=[])
    pilot = ap.Autopilot(cfg)
    pilot.start(0.0)
    straight = pilot.update(seen(0.0), 0.05)
    turning = pilot.update(seen(1.0, far_offset=1.0), 0.10)
    assert straight.linear == pytest.approx(cfg.cruise_speed)
    assert cfg.min_speed <= turning.linear < straight.linear
    assert abs(turning.angular) <= cfg.max_angular + 1e-9


def test_brief_loss_stops_without_giving_up_then_gives_up():
    cfg = ap.AutopilotConfig(route=[], lost_timeout=0.5)
    pilot = ap.Autopilot(cfg)
    pilot.start(0.0)
    pilot.update(seen(), 0.1)
    blind = pilot.update(Observation(), 0.3)
    assert blind.state == ap.FOLLOW and blind.linear == 0.0     # стоим, но ещё ждём
    assert pilot.update(seen(), 0.4).linear > 0                 # полоса вернулась
    pilot.update(Observation(), 0.5)
    lost = pilot.update(Observation(), 1.2)
    assert lost.state == ap.LOST and lost.reason == 'track_lost'
    assert pilot.update(seen(), 1.3).state == ap.LOST           # сам не возобновляет


def test_restart_after_lost_requires_operator():
    pilot = ap.Autopilot(ap.AutopilotConfig(route=[], lost_timeout=0.1))
    pilot.start(0.0)
    pilot.update(Observation(), 0.5)
    assert pilot.state == ap.LOST
    pilot.start(1.0)
    assert pilot.update(seen(), 1.05).state == ap.FOLLOW


def test_max_run_time():
    pilot = ap.Autopilot(ap.AutopilotConfig(route=[], max_run_time=2.0))
    pilot.start(0.0)
    assert pilot.update(seen(), 1.0).state == ap.FOLLOW
    command = pilot.update(seen(), 2.5)
    assert command.state == ap.LOST and command.reason == 'max_run_time'


def test_tunnel_is_driven_straight_and_approach_aims_at_the_mouth():
    cfg = ap.AutopilotConfig(route=['tunnel'], straight_trim=0.05)
    pilot = ap.Autopilot(cfg)
    pilot.start(0.0)
    # Проём виден справа: рулим к нему, хотя полоса по центру.
    approach = pilot.update(seen(0.0, dark_fraction=0.2, dark_offset=0.6), 0.1)
    assert approach.state == ap.FOLLOW and approach.angular < 0
    inside = pilot.update(Observation(dark_fraction=0.9), 0.2)
    assert inside.state == ap.TUNNEL
    assert inside.linear == cfg.tunnel_speed and inside.angular == cfg.straight_trim
    # Слишком рано «увидели выход» — не верим.
    assert pilot.update(seen(dark_fraction=0.0), 0.5).state == ap.TUNNEL
    assert pilot.update(seen(dark_fraction=0.0), 1.5).state == ap.FOLLOW


def test_balloon_is_rammed_for_fixed_time():
    cfg = ap.AutopilotConfig(route=['balloon'], balloon_time=1.0)
    pilot = ap.Autopilot(cfg)
    pilot.start(0.0)
    hit = pilot.update(Observation(balloon_fraction=0.5), 0.1)   # шар закрыл полосу
    assert hit.state == ap.BALLOON and hit.linear == cfg.balloon_speed
    assert pilot.update(Observation(), 0.6).state == ap.BALLOON
    assert pilot.update(seen(), 1.2).state == ap.FOLLOW


def test_finish_marker_and_track_end():
    marker = ap.Autopilot(ap.AutopilotConfig(route=['finish'], finish_delay=0.3))
    marker.start(0.0)
    assert marker.update(seen(finish_fraction=0.5), 0.1).state == ap.FINISHING
    assert marker.update(seen(), 0.5).state == ap.FINISHED

    no_marker = ap.Autopilot(ap.AutopilotConfig(route=['finish'], lost_timeout=0.2))
    no_marker.start(0.0)
    no_marker.update(seen(), 0.1)
    end = no_marker.update(Observation(), 0.5)
    assert end.state == ap.FINISHED and end.reason == 'track_end'

    strict = ap.Autopilot(ap.AutopilotConfig(route=['finish'], lost_timeout=0.2,
                                             finish_on_track_end=False))
    strict.start(0.0)
    assert strict.update(Observation(), 0.5).state == ap.LOST


@pytest.mark.parametrize('bad', [dict(route=['jump']), dict(cruise_speed=0.0),
                                 dict(min_speed=1.0), dict(tunnel_min_time=9.0),
                                 dict(slow_on_turn=2.0)])
def test_invalid_autopilot_config(bad):
    with pytest.raises(ValueError):
        ap.Autopilot(ap.AutopilotConfig(**bad))


def test_never_seeing_the_track_is_not_a_finish():
    """Старт без полосы в кадре: не «финиш», а «полоса не найдена» (маршрут как в YAML)."""
    pilot = ap.Autopilot(ap.AutopilotConfig(route=['finish'], lost_timeout=0.3))
    pilot.start(0.0)
    command = None
    for step in range(1, 30):
        command = pilot.update(Observation(), step * 0.05)
    assert command.state == ap.LOST and command.reason == 'track_not_found'
    assert command.linear == 0.0 and command.angular == 0.0


def test_finish_marker_alone_without_track_is_not_a_finish():
    pilot = ap.Autopilot(ap.AutopilotConfig(route=['finish'], lost_timeout=0.3))
    pilot.start(0.0)
    pilot.update(Observation(finish_fraction=0.5), 0.05)      # метка есть, полосы не было
    final = pilot.update(Observation(), 1.0)
    assert final.state == ap.LOST and final.reason == 'track_not_found'


def test_stale_frame_is_marked_on_debug_image():
    frame = frame_with_track(100, 220)
    cfg = VisionConfig()
    obs = analyze(frame, cfg)
    fresh = draw_debug(frame, obs, cfg, 'follow')
    stale = draw_debug(frame, obs, cfg, 'follow', stale_seconds=7.0)
    assert stale.shape == fresh.shape
    assert stale.mean() < fresh.mean() * 0.7          # кадр заметно затемнён
    assert (stale[..., 2] > 200).sum() > 50           # и на нём есть красная надпись

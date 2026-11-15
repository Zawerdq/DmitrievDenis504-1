"""Замкнутый контур в симуляторе: камера -> зрение -> автопилот -> робот -> камера.

Синтетическая трасса, НЕ трасса Физтех.Фабрики (см. susanin_autopilot/sim.py).
Тесты проверяют знаки, логику шагов и устойчивость, а не реальные пороги цветов.
"""

import pytest

from susanin_autopilot import autopilot as ap
from susanin_autopilot import sim
from susanin_autopilot.vision import analyze, VisionConfig

DT = 0.05   # 20 Гц


def run(world, robot, camera=None, vision=None, pilot_cfg=None, seconds=90.0,
        frame_gap=None):
    """Прогнать заезд. Возвращает (автопилот, макс. отклонение от оси, список состояний)."""
    camera = camera or sim.Camera()
    vision = vision or VisionConfig()
    pilot = ap.Autopilot(pilot_cfg or ap.AutopilotConfig())
    pilot.start(0.0)
    worst = 0.0
    states = [pilot.state]
    now = 0.0
    while now < seconds:
        frame = sim.render(world, robot, camera)
        obs = analyze(frame, vision)
        if frame_gap and frame_gap[0] <= now < frame_gap[1]:
            obs = None                      # камера «отвалилась»
        command = pilot.update(obs, now)
        if command.state != states[-1]:
            states.append(command.state)
        if command.state in (ap.FINISHED, ap.LOST):
            break
        robot.step(command.linear, command.angular, DT)
        if command.state == ap.FOLLOW:
            worst = max(worst, world.distance_to_centerline(robot.x, robot.y))
        now += DT
    return pilot, worst, states


def long_world(**events):
    """Длинная трасса: прямая (на ней туннель), S-образный поворот, прямая."""
    return sim.make_world(centerline=sim.s_curve(straight=2.0), size_m=(3.0, 5.6), **events)


def follow_only(**overrides):
    return ap.AutopilotConfig(route=[], **overrides)


def test_follows_s_curve_to_the_end():
    world = sim.make_world()
    robot = sim.start_pose(world)
    pilot, worst, states = run(world, robot, pilot_cfg=ap.AutopilotConfig(route=['finish']))
    assert pilot.state == ap.FINISHED and pilot.reason == 'track_end'
    assert worst < world.track_width / 2 - 0.08      # корпус остаётся на полосе
    end_x, end_y = world.centerline[-1]
    assert abs(robot.x - end_x) < 0.35 and abs(robot.y - end_y) < 0.45


@pytest.mark.parametrize('lateral,heading', [(0.12, 0.0), (-0.12, 0.0), (0.0, 15.0),
                                             (0.0, -15.0), (0.10, -12.0)])
def test_recovers_from_bad_start(lateral, heading):
    world = sim.make_world()
    robot = sim.start_pose(world, lateral=lateral, heading_error_deg=heading)
    pilot, worst, _ = run(world, robot, pilot_cfg=ap.AutopilotConfig(route=['finish']))
    assert pilot.state == ap.FINISHED
    assert worst < world.track_width / 2 - 0.04


def test_survives_motor_asymmetry_and_lag():
    world = sim.make_world()
    robot = sim.start_pose(world)
    robot.turn_bias = 0.15        # робота постоянно уводит влево
    robot.response = 0.3
    pilot, worst, _ = run(world, robot, pilot_cfg=ap.AutopilotConfig(route=['finish']))
    assert pilot.state == ap.FINISHED
    assert worst < world.track_width / 2 - 0.04


def test_stops_when_placed_off_track():
    world = sim.make_world()
    robot = sim.start_pose(world, lateral=1.2)      # стоим на голом полу
    pilot, _, _ = run(world, robot, pilot_cfg=follow_only(), seconds=5.0)
    assert pilot.state == ap.LOST and pilot.reason == 'track_not_found'
    start = sim.start_pose(world, lateral=1.2)
    assert abs(robot.x - start.x) < 0.02 and abs(robot.y - start.y) < 0.02   # не поехал


def test_stops_when_camera_stops_delivering_frames():
    world = sim.make_world()
    robot = sim.start_pose(world)
    pilot, _, _ = run(world, robot, pilot_cfg=follow_only(), frame_gap=(2.0, 60.0))
    assert pilot.state == ap.LOST and pilot.reason == 'no_frames'


def test_full_route_tunnel_balloon_finish():
    world = long_world(tunnel_at=(0.8, 1.3), balloon_at=3.6, finish_at=4.1)
    robot = sim.start_pose(world)
    pilot, worst, states = run(world, robot)
    assert states == [ap.FOLLOW, ap.TUNNEL, ap.FOLLOW, ap.BALLOON, ap.FOLLOW,
                      ap.FINISHING, ap.FINISHED]
    assert worst < world.track_width / 2 - 0.04
    assert pilot.reason == 'finish_marker'


def test_tunnel_timeout_stops_robot():
    # «Туннель» не кончается: тень до самого конца трассы.
    world = long_world(tunnel_at=(0.8, 4.4))
    robot = sim.start_pose(world)
    cfg = ap.AutopilotConfig(route=['tunnel'], tunnel_max_time=3.0)
    pilot, _, states = run(world, robot, pilot_cfg=cfg)
    assert ap.TUNNEL in states
    assert pilot.state == ap.LOST and pilot.reason == 'tunnel_timeout'


def test_events_out_of_order_are_ignored():
    # Шар стоит раньше туннеля, а маршрут ждёт сначала туннель: шар не должен
    # переключить режим, и автопилот остановится, упёршись в «потерю полосы» или дойдя дальше.
    world = sim.make_world(balloon_at=1.0)
    robot = sim.start_pose(world)
    _, _, states = run(world, robot, pilot_cfg=ap.AutopilotConfig(route=['tunnel']),
                       seconds=20.0)
    assert ap.BALLOON not in states


def test_line_mode_follows_marking():
    world = sim.make_world()
    # Чёрная линия разметки по оси полосы.
    import cv2
    import numpy as np
    pixels = np.array([world.to_pixel(*p) for p in world.centerline], np.int32).reshape(-1, 1, 2)
    cv2.polylines(world.image, [pixels], False, (10, 10, 10), int(0.03 * world.ppm))
    robot = sim.start_pose(world, lateral=0.08)
    vision = VisionConfig(track_mode='line', min_band_width=0.02, min_track_fraction=0.005)
    pilot, worst, _ = run(world, robot, vision=vision,
                          pilot_cfg=ap.AutopilotConfig(route=['finish']))
    assert pilot.state == ap.FINISHED
    assert worst < 0.10

"""Вся цепочка с параметрами из susanin.yaml в симуляторе.

камера -> зрение -> автопилот -> узел управления (ограничения, рампа, min_duty)
-> протокол прошивки -> микшер прошивки -> гусеницы -> новая картинка

Проверяет, что поставляемые по умолчанию параметры дают устойчивое движение по
синтетической полосе с учётом «грубости» привода (робот не может ехать медленнее
min_duty). Модель трассы и привода условная; на реальном роботе это не проверка.
"""

import math
import os
import sys

import pytest
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, '..', 'config', 'susanin.yaml')
SRC = os.path.join(HERE, '..', '..')
for package in ('susanin_control', 'susanin_esp32_bridge', 'susanin_autopilot'):
    path = os.path.join(SRC, package)
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)

pytest.importorskip('cv2')
from susanin_autopilot import autopilot as ap                    # noqa: E402
from susanin_autopilot import sim                                # noqa: E402
from susanin_autopilot.vision import analyze, VisionConfig       # noqa: E402
from susanin_control.track_controller import ControlConfig, TrackController   # noqa: E402
from susanin_esp32_bridge.protocol import firmware_mix, tracks_to_joystick    # noqa: E402

DT = 0.05
STICTION_PWM = 50      # ниже этого ШИМ гусеница в модели не страгивается


def load():
    with open(CONFIG, encoding='utf-8') as handle:
        config = yaml.safe_load(handle)
    control = dict(config['susanin_control']['ros__parameters'])
    control.pop('control_rate')
    control.pop('require_link')
    auto = config['susanin_autopilot']['ros__parameters']
    return ControlConfig(**control), VisionConfig(**auto['vision']), auto['pilot']


def drive(world, route, seconds=150.0, lateral=0.0, heading=0.0):
    control_cfg, vision_cfg, pilot_params = load()
    pilot = ap.Autopilot(ap.AutopilotConfig(**dict(pilot_params, route=route)))
    controller = TrackController(control_cfg)
    robot = sim.start_pose(world, lateral=lateral, heading_error_deg=heading)
    robot.response = 0.1
    camera = sim.Camera()
    pilot.start(0.0)
    controller.step(0.0)
    worst = now = 0.0
    while now < seconds:
        command = pilot.update(analyze(sim.render(world, robot, camera), vision_cfg), now)
        if command.state in (ap.FINISHED, ap.LOST):
            break
        controller.set_twist(command.linear, command.angular, now)
        left, right = controller.step(now)
        # Мост и прошивка: доли ШИМ -> джойстик -> ШИМ моторов.
        left_pwm, right_pwm = firmware_mix(*tracks_to_joystick(left, right))
        speeds = [0.0 if abs(pwm) < STICTION_PWM else pwm / 255.0 * control_cfg.max_track_speed
                  for pwm in (left_pwm, right_pwm)]
        linear = (speeds[0] + speeds[1]) / 2.0
        angular = (speeds[1] - speeds[0]) / control_cfg.track_width
        robot.step(linear, angular, DT)
        if command.state == ap.FOLLOW:
            worst = max(worst, world.distance_to_centerline(robot.x, robot.y))
        now += DT
    return pilot, worst, robot


@pytest.mark.parametrize('lateral,heading', [(0.0, 0.0), (0.10, 0.0), (-0.10, 10.0)])
def test_default_parameters_follow_the_track(lateral, heading):
    world = sim.make_world()
    pilot, worst, robot = drive(world, ['finish'], lateral=lateral, heading=heading)
    assert pilot.state == ap.FINISHED, pilot.reason
    assert worst < world.track_width / 2 - 0.04
    end_x, end_y = world.centerline[-1]
    assert math.hypot(robot.x - end_x, robot.y - end_y) < 0.6


def test_default_parameters_full_route():
    world = sim.make_world(centerline=sim.s_curve(straight=2.0), size_m=(3.0, 5.6),
                           tunnel_at=(0.8, 1.3), balloon_at=3.6, finish_at=4.1)
    pilot, worst, _ = drive(world, ['tunnel', 'balloon', 'finish'])
    assert pilot.state == ap.FINISHED and pilot.reason == 'finish_marker'
    assert worst < world.track_width / 2 - 0.04

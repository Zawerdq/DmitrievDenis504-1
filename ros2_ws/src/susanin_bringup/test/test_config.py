"""Проверка, что YAML согласован с параметрами, которые объявляют узлы."""

from dataclasses import fields
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

track_controller = pytest.importorskip('susanin_control.track_controller')
link = pytest.importorskip('susanin_esp32_bridge.link')


@pytest.fixture(scope='module')
def config():
    with open(CONFIG, encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def check_types(params: dict, defaults) -> None:
    """Типы в YAML должны совпадать с типами полей: ROS 2 не приводит int к float."""
    names = {item.name for item in fields(defaults)}
    assert set(params) == names
    for name, value in params.items():
        expected = type(getattr(defaults, name))
        assert type(value) is expected, (
            f'{name}: ожидается {expected.__name__}, получено {value!r}')


def test_control_parameters_match_code(config):
    params = dict(config['susanin_control']['ros__parameters'])
    extra = {'control_rate', 'require_link'}
    expected = set(vars(track_controller.ControlConfig())) | extra
    assert set(params) == expected
    for name in extra:
        params.pop(name)
    for name, value in params.items():
        assert isinstance(value, float), f'{name}: нужно число с точкой, получено {value!r}'
    track_controller.ControlConfig(**params).validate()


def test_bridge_parameters_match_code(config):
    params = dict(config['susanin_esp32_bridge']['ros__parameters'])
    assert params.pop('transport') == 'websocket'
    check_types(params, link.LinkConfig())
    link.LinkConfig(**params).validate()


def test_bridge_stops_before_firmware_timeout(config):
    """Сторожевые таймеры ROS должны срабатывать раньше 3-секундного таймаута прошивки."""
    control = config['susanin_control']['ros__parameters']
    bridge = config['susanin_esp32_bridge']['ros__parameters']
    assert control['cmd_vel_timeout'] <= 1.0
    assert bridge['command_timeout'] <= 1.0
    assert bridge['pong_timeout'] < 3.0
    assert bridge['send_rate'] >= 5.0


def test_autopilot_parameters_match_code(config):
    vision = pytest.importorskip('susanin_autopilot.vision')
    autopilot = pytest.importorskip('susanin_autopilot.autopilot')
    params = dict(config['susanin_autopilot']['ros__parameters'])
    vision_params = params.pop('vision')
    pilot_params = params.pop('pilot')
    assert set(params) == {'source', 'capture_width', 'capture_height', 'capture_fps',
                           'loop_source', 'rate', 'debug_image_period', 'record_dir'}
    check_types(vision_params, vision.VisionConfig())
    check_types(pilot_params, autopilot.AutopilotConfig())
    vision.VisionConfig(**vision_params).validate()
    autopilot.AutopilotConfig(**pilot_params).validate()


def test_autopilot_respects_control_limits(config):
    control = config['susanin_control']['ros__parameters']
    pilot = config['susanin_autopilot']['ros__parameters']['pilot']
    assert pilot['cruise_speed'] <= control['max_linear_speed']
    assert pilot['max_angular'] <= control['max_angular_speed']
    # Узел управления должен успевать получать команды автопилота до своего таймаута.
    assert 1.0 / config['susanin_autopilot']['ros__parameters']['rate'] < control['cmd_vel_timeout']


def test_mode_parameters(config):
    params = config['susanin_mode']['ros__parameters']
    assert set(params) == {'initial_mode', 'http_port'}
    assert params['initial_mode'] in ('manual', 'auto')

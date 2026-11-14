"""Проверка, что YAML согласован с параметрами, которые объявляют узлы."""

import os
import sys

import pytest
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, '..', 'config', 'susanin.yaml')
SRC = os.path.join(HERE, '..', '..')
for package in ('susanin_control', 'susanin_esp32_bridge'):
    path = os.path.join(SRC, package)
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)

track_controller = pytest.importorskip('susanin_control.track_controller')
link = pytest.importorskip('susanin_esp32_bridge.link')


@pytest.fixture(scope='module')
def config():
    with open(CONFIG, encoding='utf-8') as handle:
        return yaml.safe_load(handle)


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
    defaults = vars(link.LinkConfig())
    assert set(params) == set(defaults)
    for name, value in params.items():
        assert type(value) is type(defaults[name]), (
            f'{name}: ожидается {type(defaults[name]).__name__}, получено {value!r}')
    link.LinkConfig(**params).validate()


def test_bridge_stops_before_firmware_timeout(config):
    """Сторожевые таймеры ROS должны срабатывать раньше 3-секундного таймаута прошивки."""
    control = config['susanin_control']['ros__parameters']
    bridge = config['susanin_esp32_bridge']['ros__parameters']
    assert control['cmd_vel_timeout'] <= 1.0
    assert bridge['command_timeout'] <= 1.0
    assert bridge['pong_timeout'] < 3.0
    assert bridge['send_rate'] >= 5.0

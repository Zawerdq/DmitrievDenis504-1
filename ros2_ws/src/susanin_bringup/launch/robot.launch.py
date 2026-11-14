"""Запуск робота «Сусанин ИИ».

Примеры:
    ros2 launch susanin_bringup robot.launch.py                       # управление через ROS
    ros2 launch susanin_bringup robot.launch.py autopilot:=true       # + автопилот по камере
    ros2 launch susanin_bringup robot.launch.py fake_esp32:=true      # без робота (эмулятор)
    ros2 launch susanin_bringup robot.launch.py autopilot:=true source:=/data/recordings/run1

Аргументы:
    params_file  — YAML с параметрами (по умолчанию config/susanin.yaml);
    fake_esp32   — true: эмулятор прошивки вместо реальной ESP32;
    autopilot    — true: запустить автопилот. Робот при этом стартует в режиме MANUAL
                   и поедет сам только после нажатия AUTO на страничке оператора;
    source       — источник кадров автопилота (камера, папка с кадрами или видеофайл);
                   пусто — значение из YAML.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

FAKE_PORT = 8765


def _is_true(context, name: str) -> bool:
    return LaunchConfiguration(name).perform(context).strip().lower() in ('true', '1', 'yes')


def _nodes(context):
    params_file = LaunchConfiguration('params_file').perform(context)
    fake = _is_true(context, 'fake_esp32')
    autopilot = _is_true(context, 'autopilot')
    source = LaunchConfiguration('source').perform(context).strip()
    common = dict(output='screen', respawn=True, respawn_delay=2.0)

    bridge_overrides = {'host': '127.0.0.1', 'port': FAKE_PORT} if fake else {}
    # С автопилотом робот включается в ручном режиме: сам он не поедет.
    mode_overrides = {'initial_mode': 'manual'} if autopilot else {}

    nodes = []
    if fake:
        nodes.append(Node(package='susanin_esp32_bridge', executable='fake_esp32',
                          name='fake_esp32', arguments=['--port', str(FAKE_PORT)],
                          output='screen'))
    nodes += [
        Node(package='susanin_esp32_bridge', executable='bridge_node',
             name='susanin_esp32_bridge', parameters=[params_file, bridge_overrides], **common),
        Node(package='susanin_control', executable='control_node',
             name='susanin_control', parameters=[params_file], **common),
        Node(package='susanin_autopilot', executable='mode_node',
             name='susanin_mode', parameters=[params_file, mode_overrides], **common),
    ]
    if autopilot:
        nodes.append(Node(package='susanin_autopilot', executable='autopilot_node',
                          name='susanin_autopilot',
                          parameters=[params_file, {'source': source} if source else {}],
                          **common))
    return nodes


def generate_launch_description():
    default_params = os.path.join(
        get_package_share_directory('susanin_bringup'), 'config', 'susanin.yaml')
    return LaunchDescription([
        DeclareLaunchArgument('params_file', default_value=default_params,
                              description='YAML с параметрами узлов'),
        DeclareLaunchArgument('fake_esp32', default_value='false',
                              description='true — эмулятор прошивки вместо реальной ESP32'),
        DeclareLaunchArgument('autopilot', default_value='false',
                              description='true — запустить автопилот по камере'),
        DeclareLaunchArgument('source', default_value='',
                              description='источник кадров автопилота (пусто — из YAML)'),
        OpaqueFunction(function=_nodes),
    ])

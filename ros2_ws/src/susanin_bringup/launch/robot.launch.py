"""Запуск управления роботом «Сусанин ИИ»: мост к ESP32 + узел управления.

Примеры:
    ros2 launch susanin_bringup robot.launch.py
    ros2 launch susanin_bringup robot.launch.py fake_esp32:=true      # без робота
    ros2 launch susanin_bringup robot.launch.py params_file:=/path/to/my.yaml
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node

FAKE_PORT = '8765'


def generate_launch_description():
    default_params = os.path.join(
        get_package_share_directory('susanin_bringup'), 'config', 'susanin.yaml')

    params_file = LaunchConfiguration('params_file')
    fake = LaunchConfiguration('fake_esp32')
    is_fake = PythonExpression(["'", fake, "'.lower() == 'true'"])

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file', default_value=default_params,
            description='YAML с параметрами узлов'),
        DeclareLaunchArgument(
            'fake_esp32', default_value='false',
            description='true — запустить эмулятор прошивки вместо реальной ESP32'),

        Node(
            package='susanin_esp32_bridge',
            executable='fake_esp32',
            name='fake_esp32',
            arguments=['--port', FAKE_PORT],
            output='screen',
            condition=IfCondition(is_fake),
        ),

        # Реальный робот: параметры только из YAML.
        Node(
            package='susanin_esp32_bridge',
            executable='bridge_node',
            name='susanin_esp32_bridge',
            parameters=[params_file],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
            condition=IfCondition(PythonExpression(['not ', is_fake])),
        ),
        # Эмулятор: тот же YAML, но адрес подменён.
        Node(
            package='susanin_esp32_bridge',
            executable='bridge_node',
            name='susanin_esp32_bridge',
            parameters=[params_file, {'host': '127.0.0.1', 'port': int(FAKE_PORT)}],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
            condition=IfCondition(is_fake),
        ),

        Node(
            package='susanin_control',
            executable='control_node',
            name='susanin_control',
            parameters=[params_file],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),
    ])

#!/bin/bash
# Подключает ROS 2 и собранный workspace, затем выполняет команду контейнера.
set -e
source /opt/ros/jazzy/setup.bash
source /susanin/ros2_ws/install/setup.bash
exec "$@"

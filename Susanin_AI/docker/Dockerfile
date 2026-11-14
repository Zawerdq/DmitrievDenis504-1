# Образ бортового ПО «Сусанин ИИ» для Raspberry Pi 4 (arm64) и для ПК (x86_64).
# Сборка из корня репозитория:  docker compose -f docker/compose.yaml build
FROM ros:jazzy-ros-base

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-websocket python3-websockets \
        python3-opencv python3-numpy python3-yaml python3-pytest \
        ros-jazzy-teleop-twist-keyboard \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /susanin
COPY ros2_ws/src ros2_ws/src
COPY scripts scripts
RUN . /opt/ros/jazzy/setup.sh && cd ros2_ws && colcon build

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["ros2", "launch", "susanin_bringup", "robot.launch.py"]

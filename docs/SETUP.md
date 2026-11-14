# Установка и запуск

## 0. Сначала диагностика Raspberry Pi

```bash
bash scripts/pi_diagnostics.sh | tee pi_report.txt
```

ROS 2 не ставится «вслепую»: версия зависит от ОС.

| ОС на Raspberry Pi 4 | Что делать |
|---|---|
| Ubuntu Server 24.04, arm64 | ROS 2 **Jazzy** из apt (рекомендуемый вариант, поддержка до 2029 г.) |
| Ubuntu Server 22.04, arm64 | ROS 2 **Humble** из apt (поддержка до мая 2027 г.) |
| Raspberry Pi OS 64-бит (Debian) | готовых пакетов ROS 2 нет: либо Docker-образ `ros:jazzy-ros-base`, либо переустановка Ubuntu Server 24.04 |
| любая 32-битная ОС | переустановка на 64-битную обязательна |

Код узлов — чистый Python (`rclpy`), от версии ROS 2 не зависит. Сборка и сквозная проверка
выполнены в контейнере ROS 2 Jazzy (см. [KNOWN_ISSUES.md](KNOWN_ISSUES.md), раздел «Что проверено»).
Актуальный список дистрибутивов сверяйте на docs.ros.org.

## 1. Зависимости (Ubuntu + ROS 2, пока у Pi есть интернет)

```bash
sudo apt update
sudo apt install -y python3-websocket python3-websockets python3-pytest python3-yaml \
                    python3-colcon-common-extensions
```

`python3-websocket` — клиент для связи с ESP32. `python3-websockets` нужен только
эмулятору прошивки и тестам.

## 2. Сборка

```bash
cd ~/Robot/ros2_ws
source /opt/ros/$ROS_DISTRO/setup.bash
colcon build --symlink-install
source install/setup.bash
```

Проверка без робота (сборка + тесты + сквозной прогон с эмулятором ESP32):

```bash
bash scripts/ros_smoke_test.sh
```

## 3. Сеть: Raspberry Pi ↔ ESP32

ESP32 — точка доступа `bot5` (пароль из методички BOTS, адрес 192.168.4.1), без интернета.
Встроенный Wi-Fi Raspberry Pi подключается к ней; для SSH и интернета нужен второй канал —
Ethernet или USB-Wi-Fi адаптер.

```bash
sudo nmcli device wifi connect bot5 password '<пароль>' ifname wlan0
# не отправлять интернет-трафик через ESP32:
sudo nmcli connection modify bot5 ipv4.never-default yes ipv6.method disabled
sudo nmcli connection up bot5
ping -c 3 192.168.4.1
```

Если второго канала нет: ноутбук тоже подключается к `bot5` и заходит на Pi по её адресу
192.168.4.x (точка доступа ESP32 держит до 4 клиентов; интернета при этом нет ни у кого).

## 4. Проверка связи без ROS 2 и без моторов

```bash
python3 scripts/esp32_probe.py --led-blink --seconds 10
```

## 5. Запуск управления

Перед первым запуском с моторами — [FIELD_TESTS.md](FIELD_TESTS.md).

```bash
ros2 launch susanin_bringup robot.launch.py
```

Ручное управление с клавиатуры (в другом терминале):

```bash
sudo apt install -y ros-$ROS_DISTRO-teleop-twist-keyboard
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Аварийный останов и его снятие:

```bash
ros2 topic pub --once /susanin/e_stop std_msgs/msg/Bool '{data: true}'
ros2 topic pub --once /susanin/e_stop std_msgs/msg/Bool '{data: false}'
```

Состояние связи:

```bash
ros2 topic echo /susanin/esp32/connected
ros2 topic echo /diagnostics
```

Режим без робота (эмулятор прошивки):

```bash
ros2 launch susanin_bringup robot.launch.py fake_esp32:=true
```

## 6. Калибровка (значения «НЕ ИЗМЕРЕНО» в susanin.yaml)

Энкодеров нет, поэтому скорости задаются через калибровку. Всё измеряется на полу, на той
поверхности, где робот будет работать.

| Параметр | Как измерить |
|---|---|
| `track_width` | рулеткой: расстояние между серединами гусениц, м |
| `invert_left`, `invert_right`, `swap_sides` | на подставке: команда «вперёд» должна крутить обе гусеницы вперёд, «влево» — правую вперёд, левую назад |
| `min_duty` | на полу: наименьший ШИМ, при котором робот уверенно трогается (подбирать через `esp32_probe.py --drive forward --duty ...`) |
| `max_track_speed` | проехать прямо 3 с при известном ШИМ, измерить путь: `max_track_speed = путь / 3 / duty` |
| `max_duty` | не выше `1.2 А / стопорный ток мотора` (см. AUDIT.md, раздел 9.3); пока ток не измерен — 0.6 |

Гусеницы при повороте проскальзывают, поэтому реальная угловая скорость меньше расчётной.
Если это мешает, увеличьте `track_width` до «эффективного» значения: разверните робота
на месте на 10 оборотов по команде и подберите ширину так, чтобы расчётный угол совпал.

## 7. Разработка на Windows (без ROS 2)

Логика узлов тестируется обычным pytest:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install pytest websocket-client websockets pyyaml
.venv\Scripts\python -m pytest ros2_ws/src/susanin_control/test ros2_ws/src/susanin_esp32_bridge/test ros2_ws/src/susanin_bringup/test
```

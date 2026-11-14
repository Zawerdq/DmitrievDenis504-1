# Сусанин ИИ — управление гусеничным роботом через ROS 2

Проект команды курса BOTS 2026 (МФТИ). Аппаратная основа — набор BOTS
([m112521/bots](https://github.com/m112521/bots/tree/esp32-tb6612), ветка `esp32-tb6612`):
ESP32 + TB6612FNG + два мотора 12 В. Этот репозиторий добавляет бортовое управление
на Raspberry Pi 4 под ROS 2. Прошивка ESP32 используется **без изменений**.

Computer Vision разрабатывается отдельно и сюда не входит; как его подключить —
[docs/INTERFACES.md](docs/INTERFACES.md).

## Состояние

Узлы ROS 2 написаны и проверены **на эмуляторе прошивки** (pytest и сквозной сценарий в
контейнере ROS 2 Jazzy). На реальном роботе и на Raspberry Pi пока не проверялось ничего — см. [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) и
[docs/FIELD_TESTS.md](docs/FIELD_TESTS.md).

## Как это устроено

```
/cmd_vel ─▶ susanin_control ─▶ susanin_esp32_bridge ─▶ Wi-Fi (WebSocket) ─▶ ESP32 ─▶ TB6612 ─▶ моторы
            ограничения,        протокол прошивки,
            рампа, останов      контроль связи
```

| Путь | Что там |
|---|---|
| [docs/AUDIT.md](docs/AUDIT.md) | отчёт аудита: прошивка, схема, проблемы, архитектура, план |
| [docs/SETUP.md](docs/SETUP.md) | установка, сеть, запуск, калибровка |
| [docs/INTERFACES.md](docs/INTERFACES.md) | топики и подключение внешних узлов |
| [docs/FIELD_TESTS.md](docs/FIELD_TESTS.md) | порядок испытаний на роботе |
| [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | известные проблемы и что чем проверено |
| [ros2_ws/src/susanin_control](ros2_ws/src/susanin_control) | узел управления |
| [ros2_ws/src/susanin_esp32_bridge](ros2_ws/src/susanin_esp32_bridge) | мост к ESP32 и эмулятор прошивки |
| [ros2_ws/src/susanin_bringup](ros2_ws/src/susanin_bringup) | launch и единственный YAML с параметрами |
| [scripts/](scripts) | диагностика Raspberry Pi, проверка связи с ESP32, сквозная проверка ROS 2 |
| [firmware/upstream](firmware/upstream) | исходник прошивки из набора BOTS (справочная копия, MIT) |

## Быстрый старт

```bash
bash scripts/pi_diagnostics.sh | tee pi_report.txt     # 1. что стоит на Raspberry Pi
python3 scripts/esp32_probe.py --led-blink             # 2. связь с ESP32, моторы не включаются
bash scripts/ros_smoke_test.sh                         # 3. сборка и проверка с эмулятором
ros2 launch susanin_bringup robot.launch.py            # 4. управление роботом
```

Перед шагом 4 обязательно прочитайте [docs/FIELD_TESTS.md](docs/FIELD_TESTS.md): первые
включения моторов — только на подставке.

## Команда

Дмитриев Денис (электроника, ESP32, интеграция), Кайтуров Никита (Raspberry Pi, ПО),
Шеломанов Данила (механика). Telegram: https://t.me/susanin67ai

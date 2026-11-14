# Сусанин ИИ — автопилот гусеничного робота на ROS 2

Проект команды курса BOTS 2026 (МФТИ). Аппаратная основа — набор BOTS
([m112521/bots](https://github.com/m112521/bots/tree/esp32-tb6612), ветка `esp32-tb6612`):
ESP32 + TB6612FNG + два мотора 12 В. Этот репозиторий — бортовое ПО на Raspberry Pi 4:
управление через ROS 2 и автопилот по USB-камере.

Цель демонстрации: оператор проводит робота через горку вручную, включает автопилот, и
робот сам доезжает до финиша — по деревянной полосе, сквозь туннель и сквозь шар.

## Состояние

* Управление через ROS 2 по Wi-Fi **проверено на стенде** (робот без гусеничных ремней):
  связь, вперёд, поворот, блокировка при останове.
* Автопилот, режимы и страничка оператора написаны и проверены **в симуляторе и на
  эмуляторе прошивки**. На реальной камере, трассе и роботе не проверялись.
* Узлы работают с прошивкой ESP32, которая стоит на роботе, без её изменения. Вариант
  прошивки с быстрым остановом при потере связи подготовлен, но не скомпилирован под ESP32
  и не прошит.

Подробно: [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md), [docs/FIELD_TESTS.md](docs/FIELD_TESTS.md).

## Как это устроено

```
камера ─▶ susanin_autopilot ─▶ /cmd_vel ─▶ susanin_control ─▶ susanin_esp32_bridge ─▶ Wi-Fi ─▶ ESP32 ─▶ моторы
          зрение, шаги трассы              ограничения,        протокол прошивки,
                                           рампа, останов      контроль связи
телефон ─▶ страничка оператора (режим MANUAL/AUTO, СТОП)   телефон ─▶ веб-джойстик ESP32 (в режиме MANUAL)
```

| Путь | Что там |
|---|---|
| [docs/AUTOPILOT.md](docs/AUTOPILOT.md) | автопилот: как работает, порядок заезда, настройка по записи |
| [docs/DEPLOY_PI.md](docs/DEPLOY_PI.md) | развёртывание на Raspberry Pi (Docker, автозапуск) |
| [docs/SETUP.md](docs/SETUP.md) | установка без Docker, сеть, калибровка движения |
| [docs/INTERFACES.md](docs/INTERFACES.md) | узлы, топики, страничка оператора |
| [docs/FIELD_TESTS.md](docs/FIELD_TESTS.md) | испытания: что проверено на эмуляторе, стенде, трассе |
| [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) | известные проблемы и что блокирует демонстрацию |
| [docs/AUDIT.md](docs/AUDIT.md) | исходный аудит: прошивка, схема, электрика |
| [ros2_ws/src/susanin_autopilot](ros2_ws/src/susanin_autopilot) | зрение, автопилот, режимы, симулятор |
| [ros2_ws/src/susanin_control](ros2_ws/src/susanin_control) | узел управления |
| [ros2_ws/src/susanin_esp32_bridge](ros2_ws/src/susanin_esp32_bridge) | мост к ESP32 и эмулятор прошивки |
| [ros2_ws/src/susanin_bringup](ros2_ws/src/susanin_bringup) | launch и единственный YAML с параметрами |
| [scripts/](scripts) | запись с камеры, прогон записей, диагностика, сквозная проверка |
| [firmware/](firmware/README.md) | прошивка BOTS (на роботе) и вариант с правками (не прошит) |
| [docker/](docker) | образ и compose для Pi |

## Быстрый старт

На Raspberry Pi (подробно — [docs/DEPLOY_PI.md](docs/DEPLOY_PI.md)):

```bash
docker compose -f docker/compose.yaml up -d --build
```

Страничка оператора: `http://192.168.4.10:8080`, веб-джойстик: `http://192.168.4.1`.

Запись с камеры и проверка алгоритма по ней (ноутбук или Pi, без ROS):

```bash
python scripts/record_camera.py --seconds 60 --name after_hill
python scripts/vision_replay.py recordings/after_hill
```

Проверка всего ПО без робота:

```bash
bash scripts/ros_smoke_test.sh              # в окружении ROS 2
python scripts/vision_replay.py --demo      # автопилот на условной трассе
```

Первые включения моторов — только на подставке: [docs/FIELD_TESTS.md](docs/FIELD_TESTS.md).

## Команда

Дмитриев Денис, Кайтуров Никита, Шеломанов Данила. Telegram: https://t.me/susanin67ai

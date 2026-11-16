# Интерфейсы ROS 2 робота «Сусанин ИИ»

Все имена относительные (без ведущего `/`), кроме `/diagnostics`; при запуске без
пространства имён они совпадают с указанными ниже.

## Узлы

| Узел | Пакет | Назначение |
|---|---|---|
| `susanin_esp32_bridge` | `susanin_esp32_bridge` | связь с ESP32 по WebSocket |
| `susanin_control` | `susanin_control` | `/cmd_vel` → команды гусеницам, ограничения, остановы |
| `susanin_mode` | `susanin_autopilot` | режим MANUAL/AUTO, страничка оператора (порт 8080) |
| `susanin_autopilot` | `susanin_autopilot` | камера → `/cmd_vel` (запускается при `autopilot:=true`) |

## Топики

| Топик | Тип | Кто публикует | Кто читает | Смысл |
|---|---|---|---|---|
| `/cmd_vel` | `geometry_msgs/msg/Twist` | автопилот или teleop | `susanin_control` | `linear.x` — м/с (вперёд +), `angular.z` — рад/с (влево +) |
| `/susanin/mode` | `std_msgs/msg/String` | `susanin_mode` | мост, управление, автопилот | `manual` или `auto`; повторяется 2 раза в секунду |
| `/susanin/e_stop` | `std_msgs/msg/Bool` | `susanin_mode`, любой узел | мост, управление, `susanin_mode` | `true` — немедленный останов, держится до `false` |
| `/susanin/track_cmd` | `std_msgs/msg/Float32MultiArray` | `susanin_control` | мост | `[левая, правая]`, доля ШИМ −1…1. Внутренний интерфейс |
| `/susanin/esp32/connected` | `std_msgs/msg/Bool` | мост | управление, `susanin_mode` | есть ли связь с ESP32 |
| `/susanin/autopilot/state` | `std_msgs/msg/String` | автопилот | `susanin_mode` | `состояние:причина`, например `follow:start`, `lost:track_lost` |
| `/susanin/autopilot/debug/compressed` | `sensor_msgs/msg/CompressedImage` | автопилот | `susanin_mode` | кадр с разметкой алгоритма (JPEG, раз в 0.5 с) |
| `/susanin/led` | `std_msgs/msg/Bool` | любой узел | мост | светодиод на ESP32 (GPIO2) |
| `/diagnostics` | `diagnostic_msgs/msg/DiagnosticArray` | мост | любой | связь, задержка, переподключения, последняя команда |

Правила:

* `/cmd_vel` должен приходить не реже 2 раз в секунду, иначе робот останавливается
  (`cmd_vel_timeout`).
* В режиме `manual` узел управления выдаёт нули, а мост молчит: роботом управляет
  веб-джойстик ESP32. Если узел режимов не запущен, мост и управление работают как в `auto`.
* Источник `/cmd_vel` в каждый момент один: автопилот публикует только в режиме `auto`.
  Запускать teleop одновременно с работающим автопилотом в режиме `auto` нельзя.
* `/susanin/e_stop` принимается с обычным QoS, подать его может любой узел и команда
  `ros2 topic pub`. Любой останов переводит робота в режим `manual`: после снятия останова
  движение через ROS возобновляется только по явному переходу в `auto`.
* Останов сильнее режима: пока он активен, мост шлёт ESP32 ноль 20 раз в секунду и
  команду блокировки даже в `manual`. Полностью заблокировать веб-джойстик может только
  прошивка `firmware/susanin_esp32` (правка Ф5); со старой прошивкой джойстик способен
  перебивать нули.
* Останов, нажатый на страничке оператора, `susanin_mode` повторяет дважды в секунду,
  поэтому перезапущенный узел получит его снова. Останов, поданный другим узлом, хранится
  только в узлах-получателях — его источник должен повторять сообщение сам.

## Страничка оператора (HTTP, порт 8080)

| Запрос | Действие |
|---|---|
| `GET /` | страничка с кнопками |
| `GET /status` | JSON: `mode`, `estop`, `esp32`, `autopilot`, `debug_image_age` (сколько секунд назад узел автопилота прислал картинку; это не возраст кадра камеры) |
| `GET /frame.jpg` | последний кадр с разметкой алгоритма |
| `POST /mode/auto`, `POST /mode/manual` | переключить режим |
| `POST /estop`, `POST /estop/clear` | останов (с переходом в MANUAL) и его снятие |

## Параметры

Единственный источник — [susanin.yaml](../ros2_ws/src/susanin_bringup/config/susanin.yaml);
там же комментарии к каждому параметру.

## Протокол ESP32 (для справки)

Описан в [protocol.py](../ros2_ws/src/susanin_esp32_bridge/susanin_esp32_bridge/protocol.py)
и в [AUDIT.md](AUDIT.md), раздел 1.1. Мост — единственное место в ROS-части, которое знает
про JSON, WebSocket и диапазон ±255.

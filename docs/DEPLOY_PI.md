# Развёртывание на Raspberry Pi 4 (Debian 13 arm64 + Docker)

ROS 2 Jazzy на Debian ставится только в контейнер. Ниже — воспроизводимый запуск:
после включения питания Pi сама поднимает все узлы.

Состояние: образ собран и проверен на ПК (x86_64) сквозным сценарием. **На Pi (arm64)
эта инструкция целиком ещё не выполнялась** — отметьте результат в
[FIELD_TESTS.md](FIELD_TESTS.md), этап 2.

## 1. Один раз

```bash
# Docker и автозапуск службы
sudo apt install -y docker.io docker-compose-v2      # если Docker ещё не установлен
sudo systemctl enable --now docker
sudo usermod -aG docker $USER                        # затем выйти и войти заново

# Сеть: Pi сама подключается к точке доступа ESP32 и имеет постоянный адрес
sudo nmcli device wifi connect bot5 password '<пароль>' ifname wlan0
sudo nmcli connection modify bot5 connection.autoconnect yes \
     ipv4.method manual ipv4.addresses 192.168.4.10/24 ipv4.never-default yes ipv6.method disabled
sudo nmcli connection up bot5
```

После этого Pi в сети `bot5` всегда доступна по адресу **192.168.4.10**.

Если раньше контейнер запускали вручную (`susanin-ros`), остановите его, чтобы два
комплекта узлов не управляли роботом одновременно: `docker stop susanin-ros`.

## 2. Сборка и запуск

Скопируйте репозиторий на Pi (например, в `~/Robot`) и из его корня:

```bash
docker compose -f docker/compose.yaml up -d --build      # первая сборка 10–20 минут
docker logs -f susanin                                   # журнал узлов, Ctrl+C — выйти
```

Автопилот по камере включается отдельно (без него всё работает как раньше):

```bash
echo SUSANIN_AUTOPILOT=true > docker/.env
docker compose -f docker/compose.yaml up -d
```

## 3. Проверка после перезагрузки (приёмка)

```bash
sudo reboot
# через 1–2 минуты, с ноутбука или телефона в сети bot5:
```

| № | Проверка | Ожидание |
|---|---|---|
| 1 | открыть `http://192.168.4.10:8080` | страничка оператора; «ESP32: есть связь» |
| 2 | `docker ps` на Pi | контейнер `susanin` в состоянии Up |
| 3 | `docker exec susanin ros2 node list` | `/susanin_esp32_bridge`, `/susanin_control`, `/susanin_mode` (и `/susanin_autopilot`) |
| 4 | ничего не нажимать 1 минуту | моторы стоят |

## 4. Повседневные команды

```bash
docker logs --tail 50 susanin                    # что происходит
docker compose -f docker/compose.yaml restart    # перезапуск после правки susanin.yaml
docker compose -f docker/compose.yaml up -d --build   # после обновления кода
docker exec -it susanin bash                     # терминал внутри (ros2 topic echo ... и т.п.)
docker exec -it susanin ros2 run teleop_twist_keyboard teleop_twist_keyboard   # ручное управление через ROS
docker compose -f docker/compose.yaml down       # остановить и не запускать при включении
```

Параметры робота — файл `ros2_ws/src/susanin_bringup/config/susanin.yaml` на Pi: он
подключён в контейнер, пересобирать образ после правки не нужно, достаточно `restart`.

Записи заездов и камеры лежат в `recordings/` в корне репозитория (в контейнере —
`/data/recordings`). Чтобы автопилот сохранял кадры каждого заезда, задайте в YAML
`record_dir: "/data/recordings"`.

## 5. Камера

Камера A4Tech PK-910H подключается в любой USB-порт Pi. Проверка без ROS:

```bash
ls /dev/video*                                              # должно быть /dev/video0
docker exec susanin python3 /susanin/scripts/record_camera.py --camera /dev/video0 --one --out /data/recordings
```

Если номер устройства другой — поправьте `source` в `susanin.yaml`.

## 6. Откат

```bash
docker compose -f docker/compose.yaml down
docker start susanin-ros        # прежний контейнер, если он использовался
```

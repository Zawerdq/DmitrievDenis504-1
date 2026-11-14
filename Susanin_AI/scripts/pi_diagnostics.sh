#!/usr/bin/env bash
# Диагностика Raspberry Pi перед установкой ROS 2. Ничего не меняет в системе.
#
# Запуск на Raspberry Pi:
#     bash pi_diagnostics.sh | tee pi_report.txt
# Файл pi_report.txt передайте разработчику.

section() { printf '\n===== %s =====\n' "$1"; }
run() { printf '$ %s\n' "$*"; "$@" 2>&1 || echo "(команда недоступна или завершилась с ошибкой)"; }

section "Система"
run cat /etc/os-release
run uname -a
run dpkg --print-architecture
run getconf LONG_BIT

section "Плата"
run cat /proc/device-tree/model; echo
run free -h
run df -h /

section "Питание и температура (признаки просадки напряжения)"
run vcgencmd get_throttled
run vcgencmd measure_temp
run vcgencmd measure_volts
echo "Расшифровка get_throttled: 0x0 — всё в порядке; 0x50000/0x50005 — была/есть просадка питания."

section "Python"
run python3 --version
for module in websocket websockets serial yaml pytest; do
  python3 -c "import $module, sys; print('$module', getattr($module, '__version__', 'ok'))" 2>/dev/null \
    || echo "$module: не установлен"
done

section "ROS 2"
run ls /opt/ros
echo "ROS_DISTRO=${ROS_DISTRO:-не задан}"
command -v ros2 >/dev/null && run ros2 --version || echo "ros2: не найден в PATH"
command -v colcon >/dev/null && echo "colcon: есть" || echo "colcon: не найден"
command -v docker >/dev/null && run docker --version || echo "docker: не найден"

section "Сеть"
run hostname
run ip -brief addr
command -v nmcli >/dev/null && run nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device
command -v iw >/dev/null && run iw dev
echo "--- видимые сети Wi-Fi (ищем точку доступа ESP32 bot5) ---"
if command -v nmcli >/dev/null; then
  nmcli -t -f SSID,SIGNAL,CHAN device wifi list 2>&1 | sort -u | head -30
else
  echo "nmcli не найден; выполните: sudo iw dev wlan0 scan | grep SSID"
fi

section "Связь с ESP32 (работает, только если Pi подключена к Wi-Fi bot5)"
run ping -c 3 -W 2 192.168.4.1
if command -v curl >/dev/null; then
  printf '$ curl http://192.168.4.1/ (первые 3 строки)\n'
  curl -s -m 5 http://192.168.4.1/ | head -3 || echo "(нет ответа)"
fi

section "USB-устройства (ESP32 по USB видна как CP210x или CH340)"
run lsusb
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "последовательных портов USB нет"
run groups

section "Готово"
echo "Отправьте этот вывод целиком."

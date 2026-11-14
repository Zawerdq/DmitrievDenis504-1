#!/usr/bin/env bash
# Сборка, модульные тесты и сквозная проверка узлов ROS 2 с ЭМУЛЯТОРОМ ESP32.
# Реальный робот не нужен и не проверяется.
#
# Запуск (Raspberry Pi или любой компьютер с ROS 2 Humble/Jazzy):
#     bash scripts/ros_smoke_test.sh
#
# Что проверяется:
#   1. colcon build всех пакетов;
#   2. colcon test (pytest);
#   3. launch с fake_esp32:=true — связь, движение вперёд, останов по таймауту
#      /cmd_vel, поворот, аварийный останов.

set -o pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS="$REPO/ros2_ws"
LOG="$(mktemp /tmp/susanin_launch.XXXXXX.log)"
FAILED=0

# Подключить ROS 2, если он ещё не подключён в этой оболочке.
if ! command -v ros2 >/dev/null 2>&1; then
  for setup in "/opt/ros/${ROS_DISTRO:-none}/setup.bash" /opt/ros/*/setup.bash; do
    if [ -f "$setup" ]; then
      # shellcheck disable=SC1090
      source "$setup"
      break
    fi
  done
fi
if ! command -v ros2 >/dev/null 2>&1; then
  echo "ROS 2 не найден (нет /opt/ros/*/setup.bash)"; exit 2
fi
echo "=== ROS 2 $ROS_DISTRO, $(python3 --version) ==="

pass() { echo "  [OK]   $1"; }
fail() { echo "  [FAIL] $1"; FAILED=1; }
check() { if eval "$2"; then pass "$1"; else fail "$1"; fi; }

cd "$WS" || exit 2

echo "=== 1. colcon build ==="
colcon build 2>&1 | tail -4 || { echo "сборка не удалась"; exit 1; }

echo "=== 2. colcon test ==="
colcon test --event-handlers console_direct- 2>&1 | tail -4
if colcon test-result 2>&1 | tail -3; then pass "модульные тесты"; else fail "модульные тесты"; fi

# shellcheck disable=SC1091
source install/setup.bash

echo "=== 3. сквозная проверка с эмулятором ESP32 ==="
ros2 launch susanin_bringup robot.launch.py fake_esp32:=true >"$LOG" 2>&1 &
LAUNCH_PID=$!
PUB_PID=""
cleanup() {
  [ -n "$PUB_PID" ] && kill "$PUB_PID" 2>/dev/null
  # Фоновый процесс неинтерактивной оболочки игнорирует SIGINT, поэтому SIGTERM.
  kill -TERM "$LAUNCH_PID" 2>/dev/null
  for _ in $(seq 1 30); do
    kill -0 "$LAUNCH_PID" 2>/dev/null || break
    sleep 0.3
  done
  kill -KILL "$LAUNCH_PID" 2>/dev/null
  pkill -KILL -f 'susanin_(esp32_bridge|control)/lib/' 2>/dev/null
  return 0
}
trap cleanup EXIT

# Последняя строка эмулятора вида "[fake-esp32] motor1= +76 motor2= +76"
last_motors() { grep -a 'motor1=' "$LOG" | tail -1 | sed -E 's/.*motor1= *([+-][0-9]+) motor2= *([+-][0-9]+).*/\1 \2/'; }
motor() { last_motors | cut -d' ' -f"$1"; }
publish() {   # publish "<yaml Twist>"
  [ -n "$PUB_PID" ] && kill "$PUB_PID" 2>/dev/null
  ros2 topic pub -r 20 /cmd_vel geometry_msgs/msg/Twist "$1" >/dev/null 2>&1 &
  PUB_PID=$!
}
stop_publishing() { [ -n "$PUB_PID" ] && kill "$PUB_PID" 2>/dev/null; PUB_PID=""; }

# Ждать выполнения условия не дольше N секунд (узлы и CLI ROS 2 стартуют не мгновенно).
wait_until() {   # wait_until "<условие>" <секунды>
  local deadline=$((SECONDS + $2))
  while [ "$SECONDS" -lt "$deadline" ]; do
    eval "$1" 2>/dev/null && return 0
    sleep 0.3
  done
  return 1
}
expect() {       # expect "<название>" "<условие>" <секунды>
  if wait_until "$2" "$3"; then pass "$1 ($(last_motors))"; else fail "$1 ($(last_motors))"; fi
}
FORWARD='[ "$(motor 1)" -gt 0 ] && [ "$(motor 2)" -gt 0 ]'
BACKWARD='[ "$(motor 1)" -lt 0 ] && [ "$(motor 2)" -lt 0 ]'
STOPPED='[ "$(motor 1)" -eq 0 ] && [ "$(motor 2)" -eq 0 ]'
TURN_LEFT='[ "$(motor 1)" -lt 0 ] && [ "$(motor 2)" -gt 0 ]'
TURN_RIGHT='[ "$(motor 1)" -gt 0 ] && [ "$(motor 2)" -lt 0 ]'
estop() { timeout 30 ros2 topic pub --once /susanin/e_stop std_msgs/msg/Bool "{data: $1}" >/dev/null 2>&1; }

if wait_until "grep -aq 'Связь с ESP32 установлена' '$LOG'" 20; then
  pass "мост подключился к эмулятору"
else
  fail "мост подключился к эмулятору"
fi
if wait_until "timeout 10 ros2 topic echo --once /susanin/esp32/connected | grep -q 'data: true'" 40; then
  pass "топик susanin/esp32/connected = true"
else
  fail "топик susanin/esp32/connected = true"
fi

publish '{linear: {x: 0.2}}'
expect "вперёд: оба мотора > 0" "$FORWARD" 15

stop_publishing
expect "нет /cmd_vel -> останов" "$STOPPED" 5

publish '{linear: {x: -0.2}}'
expect "назад: оба мотора < 0" "$BACKWARD" 15

publish '{angular: {z: 1.0}}'
expect "поворот влево: левый < 0 < правый" "$TURN_LEFT" 15

publish '{angular: {z: -1.0}}'
expect "поворот вправо: левый > 0 > правый" "$TURN_RIGHT" 15

publish '{linear: {x: 0.2}}'
expect "снова вперёд" "$FORWARD" 15
estop true
expect "аварийный останов при идущих командах" "$STOPPED" 5
sleep 2
check "останов держится, пока его не сняли ($(last_motors))" "$STOPPED"
estop false
expect "после снятия останова движение возобновилось" "$FORWARD" 15

stop_publishing
check "нет сообщений об ошибках узлов" "! grep -aqE 'Traceback|process has died' '$LOG'"

echo
if [ "$FAILED" -eq 0 ]; then
  echo "ИТОГ: все проверки пройдены (эмулятор ESP32, не реальный робот)."
else
  echo "ИТОГ: есть ошибки. Журнал запуска: $LOG"
  tail -40 "$LOG"
fi
exit "$FAILED"

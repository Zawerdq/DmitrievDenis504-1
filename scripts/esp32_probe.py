#!/usr/bin/env python3
"""Проверка связи с ESP32 без ROS 2 (с ноутбука или Raspberry Pi, подключённых к Wi-Fi bot5).

Использует тот же код канала связи, что и узел моста.
Нужен пакет websocket-client:  sudo apt install python3-websocket   (или pip install websocket-client)

По умолчанию моторы НЕ включаются: отправляются только нулевые команды и ping.

Примеры:
    python3 scripts/esp32_probe.py                      # связь и задержка, 5 секунд
    python3 scripts/esp32_probe.py --led-blink          # мигнуть светодиодом на ESP32
    python3 scripts/esp32_probe.py --drive forward --duty 0.3 --seconds 1 --robot-is-on-stand
"""

from __future__ import annotations

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'ros2_ws', 'src', 'susanin_esp32_bridge'))

from susanin_esp32_bridge.link import Esp32Link, LinkConfig  # noqa: E402

DIRECTIONS = {
    'forward': (1.0, 1.0),
    'back': (-1.0, -1.0),
    'left': (-1.0, 1.0),
    'right': (1.0, -1.0),
}
MAX_PROBE_DUTY = 0.6
MAX_PROBE_SECONDS = 3.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', default='192.168.4.1')
    parser.add_argument('--port', type=int, default=80)
    parser.add_argument('--seconds', type=float, default=5.0,
                        help='длительность проверки (для --drive не более 3 с)')
    parser.add_argument('--led-blink', action='store_true',
                        help='помигать светодиодом ESP32 (GPIO2) — безопасная проверка команд')
    parser.add_argument('--drive', choices=sorted(DIRECTIONS),
                        help='включить моторы в указанном направлении')
    parser.add_argument('--duty', type=float, default=0.3,
                        help=f'доля ШИМ для --drive, не более {MAX_PROBE_DUTY}')
    parser.add_argument('--robot-is-on-stand', action='store_true',
                        help='подтверждение: гусеницы вывешены, питание проверено')
    args = parser.parse_args()

    if args.drive:
        if not args.robot_is_on_stand:
            print('ОТКАЗ: для включения моторов поднимите робота на подставку (гусеницы '
                  'в воздухе), проверьте питание и добавьте флаг --robot-is-on-stand.')
            return 2
        if not 0.0 < args.duty <= MAX_PROBE_DUTY:
            print(f'ОТКАЗ: --duty должен быть в диапазоне (0, {MAX_PROBE_DUTY}].')
            return 2
        args.seconds = min(args.seconds, MAX_PROBE_SECONDS)

    def log(level: str, text: str) -> None:
        print(f'[{level}] {text}', flush=True)

    link = Esp32Link(LinkConfig(host=args.host, port=args.port), log=log)
    link.start()
    try:
        deadline = time.monotonic() + 6.0
        while not link.connected and time.monotonic() < deadline:
            time.sleep(0.05)
        if not link.connected:
            print(f'НЕТ СВЯЗИ с ws://{args.host}:{args.port}/ws. Проверьте: компьютер '
                  'подключён к Wi-Fi ESP32 (bot5), ESP32 включена.')
            return 1

        left, right = DIRECTIONS.get(args.drive, (0.0, 0.0))
        left *= args.duty
        right *= args.duty
        if args.drive:
            print(f'МОТОРЫ: {args.drive}, ШИМ {args.duty:.0%}, {args.seconds:.1f} с. '
                  'Ctrl+C — немедленный останов.')

        rtts = []
        started = time.monotonic()
        next_report = started
        led = False
        while time.monotonic() - started < args.seconds:
            if args.drive:
                link.set_tracks(left, right)
            now = time.monotonic()
            if now >= next_report:
                next_report = now + 0.5
                stats = link.stats()
                if stats.last_rtt_ms is not None:
                    rtts.append(stats.last_rtt_ms)
                if args.led_blink:
                    led = not led
                    link.set_led(led)
                rtt = '—' if stats.last_rtt_ms is None else f'{stats.last_rtt_ms:.0f} мс'
                print(f'  связь={stats.connected} задержка={rtt} отправлено={stats.tx_count} '
                      f'x={stats.last_xy[0]} y={stats.last_xy[1]} '
                      f'переподключений={max(0, stats.connects - 1)}', flush=True)
            time.sleep(0.02)

        stats = link.stats()
        if args.led_blink:
            link.set_led(False)
            time.sleep(0.2)
        print('\nИТОГ:')
        print(f'  связь на конец проверки: {stats.connected}')
        print(f'  переподключений: {max(0, stats.connects - 1)}')
        if rtts:
            print(f'  задержка ping/pong: мин {min(rtts):.0f} / макс {max(rtts):.0f} мс')
        else:
            print('  ответов pong не получено — двусторонняя связь НЕ подтверждена')
        return 0 if stats.connected and rtts else 1
    except KeyboardInterrupt:
        print('\nПрервано пользователем — останов.')
        return 130
    finally:
        link.stop()   # последним сообщением уходит {"x":0,"y":0}


if __name__ == '__main__':
    sys.exit(main())

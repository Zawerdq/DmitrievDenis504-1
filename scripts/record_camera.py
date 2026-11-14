#!/usr/bin/env python3
"""Запись с камеры для настройки автопилота. Работает на ноутбуке и на Raspberry Pi, без ROS.

Нужен OpenCV:  pip install opencv-python   (на Pi: sudo apt install python3-opencv)

Сохраняет папку с кадрами JPEG; в имени каждого файла — номер и время съёмки.
Такую папку понимают scripts/vision_replay.py и узел автопилота (параметр source).

Примеры:
    python scripts/record_camera.py                       # камера 0, 20 секунд
    python scripts/record_camera.py --camera 1 --seconds 60 --name after_hill_center
    python scripts/record_camera.py --one                 # один кадр: проверить, что камера видна
    python3 scripts/record_camera.py --camera /dev/video0 # Raspberry Pi
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import cv2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--camera', default='0', help='номер камеры или путь /dev/videoN')
    parser.add_argument('--width', type=int, default=640)
    parser.add_argument('--height', type=int, default=480)
    parser.add_argument('--fps', type=float, default=30.0)
    parser.add_argument('--seconds', type=float, default=20.0)
    parser.add_argument('--every', type=int, default=1, help='сохранять каждый N-й кадр')
    parser.add_argument('--out', default='recordings', help='папка для записей')
    parser.add_argument('--name', default='', help='имя записи (иначе — дата и время)')
    parser.add_argument('--note', default='', help='заметка: высота и наклон камеры, участок')
    parser.add_argument('--one', action='store_true', help='снять один кадр и выйти')
    parser.add_argument('--show', action='store_true', help='показывать окно предпросмотра')
    args = parser.parse_args()

    target = int(args.camera) if args.camera.isdigit() else args.camera
    capture = cv2.VideoCapture(target)
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    capture.set(cv2.CAP_PROP_FPS, args.fps)
    if not capture.isOpened():
        print(f'Камера {args.camera} не открылась. Проверьте подключение; на Linux — '
              'ls /dev/video* и права группы video.')
        return 1

    for _ in range(5):                 # первые кадры: камера подстраивает экспозицию
        capture.read()
    ok, frame = capture.read()
    if not ok:
        print('Камера открылась, но кадр не получен.')
        return 1
    real = (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    print(f'Камера {args.camera}: кадр {real[0]}x{real[1]}')

    name = args.name or time.strftime('rec_%Y%m%d_%H%M%S')
    folder = os.path.join(args.out, name)
    os.makedirs(folder, exist_ok=True)

    if args.one:
        path = os.path.join(folder, 'frame.jpg')
        cv2.imwrite(path, frame)
        print(f'Кадр сохранён: {path}')
        return 0

    print(f'Запись {args.seconds:.0f} с в {folder} (Ctrl+C — закончить раньше)')
    started = time.time()
    seen = saved = 0
    try:
        while time.time() - started < args.seconds:
            ok, frame = capture.read()
            if not ok:
                print('Кадр потерян'); continue
            seen += 1
            if seen % args.every == 0:
                saved += 1
                cv2.imwrite(os.path.join(folder, f'{saved:06d}_{time.time():.3f}.jpg'), frame,
                            [cv2.IMWRITE_JPEG_QUALITY, 90])
            if args.show:
                cv2.imshow('record_camera (q - выход)', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        capture.release()
        if args.show:
            cv2.destroyAllWindows()

    elapsed = max(1e-6, time.time() - started)
    meta = {'camera': args.camera, 'width': real[0], 'height': real[1],
            'requested_fps': args.fps, 'measured_fps': round(seen / elapsed, 2),
            'frames': saved, 'seconds': round(elapsed, 2), 'note': args.note,
            'started': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(started))}
    with open(os.path.join(folder, 'meta.json'), 'w', encoding='utf-8') as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)
    print(f'Готово: {saved} кадров, {meta["measured_fps"]} кадр/с. Папка: {folder}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

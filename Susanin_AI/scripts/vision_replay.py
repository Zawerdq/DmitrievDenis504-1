#!/usr/bin/env python3
"""Прогон зрения и автопилота по записи, без робота и без ROS.

Нужны OpenCV, numpy, PyYAML:  pip install opencv-python numpy pyyaml

На выходе — видео, на котором нарисовано, что «понял» алгоритм (найденная полоса,
направление руля, состояние автопилота), и таблица decisions.csv по кадрам.
Параметры берутся из того же susanin.yaml, что использует робот.

Примеры:
    python scripts/vision_replay.py recordings/after_hill_center
    python scripts/vision_replay.py video.mp4 --out out_dir
    python scripts/vision_replay.py recordings/x --sample 140,400,60,60    # цвет пола/полосы
    python scripts/vision_replay.py --demo                                 # синтетическая трасса

--sample x,y,w,h печатает диапазон HSV в прямоугольнике первого кадра: так подбираются
пороги floor_hsv_* / track_hsv_* для susanin.yaml (координаты — в пикселях исходного кадра).
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys

import cv2
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'ros2_ws', 'src', 'susanin_autopilot'))

from susanin_autopilot import autopilot as ap                      # noqa: E402
from susanin_autopilot.frame_source import FrameSource             # noqa: E402
from susanin_autopilot.vision import analyze, draw_debug, VisionConfig   # noqa: E402

DEFAULT_CONFIG = os.path.join(REPO, 'ros2_ws', 'src', 'susanin_bringup', 'config', 'susanin.yaml')


def load_configs(path: str):
    """Прочитать секции vision/pilot узла автопилота из YAML робота."""
    import yaml
    with open(path, encoding='utf-8') as handle:
        params = yaml.safe_load(handle)['susanin_autopilot']['ros__parameters']
    vision = VisionConfig(**params.get('vision', {}))
    pilot = ap.AutopilotConfig(**params.get('pilot', {}))
    pilot.route = [event for event in pilot.route if event]
    vision.validate()
    pilot.validate()
    return vision, pilot


def sample_hsv(frame: np.ndarray, spec: str) -> None:
    x, y, w, h = (int(v) for v in spec.split(','))
    patch = cv2.cvtColor(frame[y:y + h, x:x + w], cv2.COLOR_BGR2HSV).reshape(-1, 3)
    if patch.size == 0:
        print('Прямоугольник вне кадра'); return
    low = np.percentile(patch, 2, axis=0).astype(int)
    high = np.percentile(patch, 98, axis=0).astype(int)
    print(f'HSV в прямоугольнике {spec}: медиана {np.median(patch, axis=0).astype(int).tolist()}')
    print(f'  диапазон 2–98 %:  low {low.tolist()}  high {high.tolist()}')
    margin_low = [max(0, low[0] - 8), max(0, low[1] - 40), max(0, low[2] - 40)]
    margin_high = [min(179, high[0] + 8), min(255, high[1] + 40), min(255, high[2] + 40)]
    print(f'  с запасом для YAML: low {margin_low}  high {margin_high}')


def demo_frames():
    """Кадры синтетической трассы: робот едет под управлением самого автопилота."""
    from susanin_autopilot import sim
    world = sim.make_world(centerline=sim.s_curve(straight=2.0), size_m=(3.0, 5.6),
                           tunnel_at=(0.8, 1.3), balloon_at=3.6, finish_at=4.1)
    return world, sim.start_pose(world, lateral=0.08, heading_error_deg=8), sim.Camera()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', nargs='?', help='папка с кадрами или видеофайл')
    parser.add_argument('--config', default=DEFAULT_CONFIG)
    parser.add_argument('--out', default='', help='папка результата (по умолчанию рядом с записью)')
    parser.add_argument('--fps', type=float, default=0.0, help='частота кадров записи, если неизвестна')
    parser.add_argument('--sample', default='', help='x,y,w,h — напечатать HSV области и выйти')
    parser.add_argument('--demo', action='store_true', help='синтетическая трасса вместо записи')
    args = parser.parse_args()
    if not args.source and not args.demo:
        parser.error('укажите запись или --demo')

    vision, pilot_cfg = load_configs(args.config)
    if args.demo:
        pilot_cfg.route = ['tunnel', 'balloon', 'finish']   # на демо-трассе есть все события
    pilot = ap.Autopilot(pilot_cfg)
    out_dir = args.out or (os.path.join('recordings', 'demo_out') if args.demo
                           else args.source.rstrip('/\\') + '_out')
    os.makedirs(out_dir, exist_ok=True)

    if args.demo:
        from susanin_autopilot import sim
        world, robot, camera = demo_frames()
        source, fps = None, 20.0
    else:
        source = FrameSource(args.source)
        fps = args.fps or source.fps or 30.0

    writer = None
    rows = []
    counts = {}
    transitions = []
    found = total = 0
    now = 0.0
    pilot.start(0.0)
    stamp_pattern = re.compile(r'_(\d+\.\d+)\.[a-z]+$', re.IGNORECASE)
    first_stamp = None

    while True:
        if args.demo:
            if pilot.state in (ap.FINISHED, ap.LOST) or now > 120.0:
                break
            frame = sim.render(world, robot, camera)
        else:
            index = source._index if source._files is not None else None
            frame = source.read()
            if frame is None:
                break
            if index is not None:            # время кадра из имени файла, если оно там есть
                match = stamp_pattern.search(source._files[index])
                if match:
                    stamp = float(match.group(1))
                    first_stamp = first_stamp if first_stamp is not None else stamp
                    now = stamp - first_stamp
        if args.sample and total == 0:
            sample_hsv(frame, args.sample)
            return 0

        obs = analyze(frame, vision)
        command = pilot.update(obs, now)
        if args.demo:
            robot.step(command.linear, command.angular, 1.0 / fps)

        label = command.state + (f':{command.reason}' if command.reason else '')
        if not transitions or transitions[-1][1] != label:
            transitions.append((now, label))
        counts[command.state] = counts.get(command.state, 0) + 1
        total += 1
        found += int(obs.track_found)
        rows.append([total, f'{now:.3f}', int(obs.track_found), f'{obs.offset:.3f}',
                     f'{obs.far_offset:.3f}', f'{obs.track_fraction:.3f}',
                     f'{obs.dark_fraction:.3f}', f'{obs.balloon_fraction:.3f}',
                     f'{obs.finish_fraction:.3f}', command.state, command.reason,
                     f'{command.linear:.3f}', f'{command.angular:.3f}'])

        image = draw_debug(frame, obs, vision,
                           f'{label} v={command.linear:.2f} w={command.angular:+.2f}')
        image = cv2.resize(image, (640, 480), interpolation=cv2.INTER_NEAREST)
        if writer is None:
            writer = cv2.VideoWriter(os.path.join(out_dir, 'debug.avi'),
                                     cv2.VideoWriter_fourcc(*'MJPG'), fps, (640, 480))
        writer.write(image)
        if total == 1 or total % 100 == 0:
            cv2.imwrite(os.path.join(out_dir, f'debug_{total:06d}.jpg'), image)
        if args.demo or first_stamp is None:
            now += 1.0 / fps

    if writer is not None:
        writer.release()
    if total == 0:
        print('В записи нет кадров'); return 1

    with open(os.path.join(out_dir, 'decisions.csv'), 'w', newline='', encoding='utf-8') as handle:
        table = csv.writer(handle)
        table.writerow(['frame', 't', 'track_found', 'offset', 'far_offset', 'track_fraction',
                        'dark_fraction', 'balloon_fraction', 'finish_fraction', 'state',
                        'reason', 'linear', 'angular'])
        table.writerows(rows)

    print(f'Кадров: {total}, длительность {now:.1f} с')
    print(f'Полоса найдена на {100.0 * found / total:.0f} % кадров (маска «{vision.track_mode}»)')
    print('Состояния автопилота (кадров): ' + ', '.join(f'{k} {v}' for k, v in counts.items()))
    print('Переходы:')
    for when, label in transitions:
        print(f'  {when:6.1f} с  {label}')
    print(f'Результат: {os.path.join(out_dir, "debug.avi")}, decisions.csv, debug_*.jpg')
    if not args.demo:
        print('Замечание: по записи нельзя судить, удержался бы робот на полосе — камера '
              'ехала так, как её вели, а не как командовал автопилот.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

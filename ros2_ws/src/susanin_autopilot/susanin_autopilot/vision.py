"""Зрение автопилота: где полоса, не начался ли туннель, не видно ли шар или финиш.

Чистые функции над кадром (numpy + OpenCV), без ROS: одинаково работают на
роботе, на записи с ноутбука и в симуляторе.

Идея: получить маску «проходимой полосы», разрезать нижнюю часть кадра на
горизонтальные ленты и в каждой найти самый широкий сплошной участок маски.
Середины этих участков дают смещение полосы относительно центра кадра.

Пороги цветов по умолчанию — ЗАГЛУШКИ. Их нужно подобрать по записи с реальной
трассы: scripts/vision_replay.py --sample.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

TRACK_MODES = ('not_floor', 'color', 'line')


@dataclass
class VisionConfig:
    # Размер, в котором обрабатывается кадр
    width: int = 320
    height: int = 240

    # Полоса ищется ниже этой доли высоты кадра (выше — стены, люди, потолок)
    roi_top: float = 0.40
    bands: int = 6                    # число горизонтальных лент
    min_band_width: float = 0.10      # мин. ширина участка полосы в ленте, доля ширины кадра
    min_valid_bands: int = 2
    min_track_fraction: float = 0.05  # мин. доля маски в области поиска

    # Как получать маску полосы:
    #   not_floor — всё, что не пол и не тень (нужен только цвет пола);
    #   color     — цвет самой полосы (дерево);
    #   line      — цвет нанесённой разметки.
    track_mode: str = 'not_floor'
    floor_hsv_low: List[int] = field(default_factory=lambda: [90, 60, 40])     # синий пол
    floor_hsv_high: List[int] = field(default_factory=lambda: [130, 255, 255])
    track_hsv_low: List[int] = field(default_factory=lambda: [5, 30, 70])      # дерево
    track_hsv_high: List[int] = field(default_factory=lambda: [35, 200, 255])
    line_hsv_low: List[int] = field(default_factory=lambda: [0, 0, 0])         # чёрная лента
    line_hsv_high: List[int] = field(default_factory=lambda: [179, 255, 60])

    # Туннель: доля тёмных пикселей ниже dark_top
    dark_value: int = 50
    dark_top: float = 0.15

    # Шар и финишная метка (диапазоны HSV; доля считается ниже *_top)
    balloon_hsv_low: List[int] = field(default_factory=lambda: [140, 80, 80])
    balloon_hsv_high: List[int] = field(default_factory=lambda: [175, 255, 255])
    balloon_top: float = 0.10
    finish_hsv_low: List[int] = field(default_factory=lambda: [45, 80, 80])
    finish_hsv_high: List[int] = field(default_factory=lambda: [80, 255, 255])
    finish_top: float = 0.60

    def validate(self) -> None:
        if self.track_mode not in TRACK_MODES:
            raise ValueError(f'track_mode должен быть одним из {TRACK_MODES}')
        if self.width < 32 or self.height < 24:
            raise ValueError('слишком маленький размер кадра')
        if not 0.0 <= self.roi_top < 0.95:
            raise ValueError('roi_top должен быть в [0, 0.95)')
        if self.bands < 2:
            raise ValueError('bands должен быть >= 2')
        for name in ('floor', 'track', 'line', 'balloon', 'finish'):
            for suffix in ('low', 'high'):
                value = getattr(self, f'{name}_hsv_{suffix}')
                if len(value) != 3:
                    raise ValueError(f'{name}_hsv_{suffix} должен содержать 3 числа (H, S, V)')


@dataclass
class Band:
    y: int            # строка середины ленты (в обработанном кадре)
    left: int         # границы найденного участка полосы, пиксели
    right: int
    valid: bool
    clipped: bool     # участок упирается в оба края кадра — краёв полосы не видно


@dataclass
class Observation:
    track_found: bool = False
    offset: float = 0.0          # смещение полосы: -1 (слева) … +1 (справа), 0 — по центру
    far_offset: float = 0.0      # куда полоса уходит вдали относительно ближней части
    track_fraction: float = 0.0
    dark_fraction: float = 0.0   # доля тёмного (туннель)
    dark_offset: float = 0.0     # где центр тёмной области, -1 … +1
    balloon_fraction: float = 0.0
    finish_fraction: float = 0.0
    bands: List[Band] = field(default_factory=list)


def _in_range(hsv: np.ndarray, low: List[int], high: List[int]) -> np.ndarray:
    """inRange с поддержкой «заворота» оттенка (красный: H от 170 до 10)."""
    if low[0] <= high[0]:
        return cv2.inRange(hsv, np.array(low, np.uint8), np.array(high, np.uint8)) > 0
    first = cv2.inRange(hsv, np.array([low[0], low[1], low[2]], np.uint8),
                        np.array([179, high[1], high[2]], np.uint8))
    second = cv2.inRange(hsv, np.array([0, low[1], low[2]], np.uint8),
                         np.array([high[0], high[1], high[2]], np.uint8))
    return (first | second) > 0


def _longest_run(flags: np.ndarray, max_gap: int) -> Optional[Tuple[int, int]]:
    """Самый длинный участок True; разрывы не длиннее max_gap считаются частью участка."""
    best = None
    start = None
    last_true = None
    for i, flag in enumerate(flags):
        if flag:
            if start is None or (i - last_true - 1) > max_gap:
                if start is not None and (best is None or last_true - start > best[1] - best[0]):
                    best = (start, last_true)
                start = i
            last_true = i
    if start is not None and (best is None or last_true - start > best[1] - best[0]):
        best = (start, last_true)
    return best


def track_mask(hsv_roi: np.ndarray, cfg: VisionConfig) -> np.ndarray:
    """Маска полосы (bool) для области поиска."""
    if cfg.track_mode == 'color':
        mask = _in_range(hsv_roi, cfg.track_hsv_low, cfg.track_hsv_high)
    elif cfg.track_mode == 'line':
        mask = _in_range(hsv_roi, cfg.line_hsv_low, cfg.line_hsv_high)
    else:
        floor = _in_range(hsv_roi, cfg.floor_hsv_low, cfg.floor_hsv_high)
        dark = hsv_roi[..., 2] < cfg.dark_value
        mask = ~floor & ~dark
    as_u8 = mask.astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    as_u8 = cv2.morphologyEx(as_u8, cv2.MORPH_OPEN, kernel)
    as_u8 = cv2.morphologyEx(as_u8, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return as_u8 > 0


def analyze(frame_bgr: np.ndarray, cfg: VisionConfig) -> Observation:
    """Разобрать один кадр (BGR, любой размер)."""
    small = cv2.resize(frame_bgr, (cfg.width, cfg.height), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    height, width = hsv.shape[:2]
    half = width / 2.0
    obs = Observation()

    # --- туннель, шар, финиш ------------------------------------------------
    dark = hsv[int(height * cfg.dark_top):, :, 2] < cfg.dark_value
    obs.dark_fraction = float(dark.mean())
    if obs.dark_fraction > 0.02:
        columns = dark.sum(axis=0).astype(np.float64)
        obs.dark_offset = float((np.arange(width) * columns).sum() / columns.sum() - half) / half
    balloon = _in_range(hsv[int(height * cfg.balloon_top):], cfg.balloon_hsv_low,
                        cfg.balloon_hsv_high)
    obs.balloon_fraction = float(balloon.mean())
    finish = _in_range(hsv[int(height * cfg.finish_top):], cfg.finish_hsv_low,
                       cfg.finish_hsv_high)
    obs.finish_fraction = float(finish.mean())

    # --- полоса -------------------------------------------------------------
    top = int(height * cfg.roi_top)
    mask = track_mask(hsv[top:], cfg)
    obs.track_fraction = float(mask.mean())

    band_height = max(1, mask.shape[0] // cfg.bands)
    min_width = cfg.min_band_width * width
    max_gap = max(2, width // 40)
    for index in range(cfg.bands):
        rows = mask[index * band_height:(index + 1) * band_height]
        if rows.size == 0:
            continue
        run = _longest_run(rows.mean(axis=0) > 0.5, max_gap)
        y = top + index * band_height + band_height // 2
        if run is None or (run[1] - run[0] + 1) < min_width:
            obs.bands.append(Band(y, 0, 0, False, False))
            continue
        clipped = run[0] <= 1 and run[1] >= width - 2
        obs.bands.append(Band(y, run[0], run[1], True, clipped))

    valid = [band for band in obs.bands if band.valid]
    if len(valid) < cfg.min_valid_bands or obs.track_fraction < cfg.min_track_fraction:
        return obs

    # Лента, в которой не видно краёв полосы, почти ничего не говорит о смещении.
    centers = np.array([(band.left + band.right) / 2.0 for band in valid])
    weights = np.array([0.2 if band.clipped else 1.0 for band in valid])
    obs.offset = float(((centers * weights).sum() / weights.sum() - half) / half)
    # valid идёт сверху вниз: первый элемент — самая дальняя лента.
    obs.far_offset = float((centers[0] - centers[-1]) / half)
    obs.track_found = True
    return obs


def draw_debug(frame_bgr: np.ndarray, obs: Observation, cfg: VisionConfig,
               text: str = '', stale_seconds: float = 0.0) -> np.ndarray:
    """Кадр с нарисованным результатом — чтобы глазами видеть, что «понял» алгоритм.

    ``stale_seconds`` > 0 — кадр старый (камера молчит): картинка затемняется и
    подписывается, чтобы оператор не принял её за текущую.
    """
    image = cv2.resize(frame_bgr, (cfg.width, cfg.height), interpolation=cv2.INTER_AREA).copy()
    height, width = image.shape[:2]
    if stale_seconds > 0.0:
        image = (image * 0.35).astype(np.uint8)
        cv2.rectangle(image, (0, height // 2 - 22), (width - 1, height // 2 + 22), (0, 0, 0), -1)
        cv2.putText(image, 'NO FRESH FRAMES', (10, height // 2 - 2), cv2.FONT_HERSHEY_SIMPLEX,
                    0.8, (0, 0, 255), 2, cv2.LINE_AA)
        cv2.putText(image, f'last frame {stale_seconds:.0f} s ago', (10, height // 2 + 17),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)
        return image
    top = int(height * cfg.roi_top)
    cv2.line(image, (0, top), (width - 1, top), (128, 128, 128), 1)
    cv2.line(image, (width // 2, top), (width // 2, height - 1), (128, 128, 128), 1)
    for band in obs.bands:
        if not band.valid:
            continue
        color = (0, 200, 255) if band.clipped else (0, 255, 0)
        cv2.line(image, (band.left, band.y), (band.right, band.y), color, 1)
        cv2.circle(image, ((band.left + band.right) // 2, band.y), 3, color, -1)
    if obs.track_found:
        target = int(width / 2 + obs.offset * width / 2)
        cv2.arrowedLine(image, (width // 2, height - 5), (target, top + 10), (0, 0, 255), 2)
    lines = [text] if text else []
    lines.append(f'off {obs.offset:+.2f} far {obs.far_offset:+.2f} trk {obs.track_fraction:.2f}')
    lines.append(f'dark {obs.dark_fraction:.2f} bal {obs.balloon_fraction:.2f} '
                 f'fin {obs.finish_fraction:.2f}')
    for i, line in enumerate(lines):
        cv2.putText(image, line, (4, 12 + 12 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                    (255, 255, 255), 1, cv2.LINE_AA)
    return image

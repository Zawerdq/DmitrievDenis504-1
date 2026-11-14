"""Простой симулятор для проверки автопилота в замкнутом контуре без робота.

Мир — плоская картинка «вид сверху» (синий пол, деревянная полоса, тёмное пятно
туннеля, шар, финишная метка). Камера — точечная модель с заданными высотой,
наклоном и углом обзора; кадр получается перспективным преобразованием карты.
Робот — кинематическая модель гусеничной платформы.

ЭТО НЕ ТРАССА ФИЗТЕХ.ФАБРИКИ. Цвета, размеры и освещение условные. Симулятор
проверяет знаки, логику шагов и устойчивость регулятора, но не пороги цветов и
не поведение на реальном покрытии.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

# Цвета BGR
FLOOR = (160, 90, 30)       # синий пол
WOOD = (120, 170, 205)      # светлое дерево
DARK = (12, 12, 12)         # тень туннеля
BALLOON = (160, 40, 200)    # пурпурный шар
FINISH = (60, 200, 60)      # зелёная метка
WALL = (150, 150, 150)      # всё, что выше горизонта

Point = Tuple[float, float]


@dataclass
class Camera:
    height: float = 0.12        # м над полосой
    tilt_deg: float = 30.0      # наклон вниз
    hfov_deg: float = 70.0
    forward: float = 0.10       # м, вынос камеры вперёд от центра робота
    width: int = 320
    height_px: int = 240

    @property
    def focal(self) -> float:
        return (self.width / 2.0) / math.tan(math.radians(self.hfov_deg) / 2.0)

    def project(self, x: float, y: float) -> Optional[Tuple[float, float]]:
        """Точка пола в системе робота (x вперёд, y влево) -> пиксель кадра."""
        tilt = math.radians(self.tilt_deg)
        px, py, pz = x - self.forward, y, -self.height
        depth = px * math.cos(tilt) - pz * math.sin(tilt)
        if depth <= 1e-6:
            return None
        right = -py
        down = -px * math.sin(tilt) - pz * math.cos(tilt)
        return (self.focal * right / depth + self.width / 2.0,
                self.focal * down / depth + self.height_px / 2.0)


@dataclass
class World:
    image: np.ndarray           # карта, BGR
    ppm: float                  # пикселей на метр
    centerline: List[Point]     # осевая линия полосы, м
    track_width: float

    def to_pixel(self, x: float, y: float) -> Tuple[float, float]:
        """Мировые метры (x вправо, y вверх) -> пиксели карты."""
        return x * self.ppm, self.image.shape[0] - y * self.ppm

    def distance_to_centerline(self, x: float, y: float) -> float:
        best = float('inf')
        for (ax, ay), (bx, by) in zip(self.centerline, self.centerline[1:]):
            dx, dy = bx - ax, by - ay
            length2 = dx * dx + dy * dy
            t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length2))
            best = min(best, math.hypot(x - (ax + t * dx), y - (ay + t * dy)))
        return best


def s_curve(straight: float = 0.8, radius: float = 0.7, sweep_deg: float = 50.0,
            tail: float = 1.2, start: Point = (0.6, 0.4), step: float = 0.02) -> List[Point]:
    """Осевая линия: прямая, поворот влево, поворот вправо, прямая (едем «вверх» по карте)."""
    points: List[Point] = []
    x, y, heading = start[0], start[1], math.pi / 2

    def advance(length: float, curvature: float) -> None:
        nonlocal x, y, heading
        for _ in range(max(1, int(round(length / step)))):
            points.append((x, y))
            heading += curvature * step
            x += math.cos(heading) * step
            y += math.sin(heading) * step

    arc = radius * math.radians(sweep_deg)
    advance(straight, 0.0)
    advance(arc, 1.0 / radius)
    advance(arc, -1.0 / radius)
    advance(tail, 0.0)
    points.append((x, y))
    return points


def _point_at(centerline: Sequence[Point], distance: float) -> Tuple[Point, float]:
    """Точка и направление на осевой линии на заданном расстоянии от начала."""
    travelled = 0.0
    for (ax, ay), (bx, by) in zip(centerline, centerline[1:]):
        segment = math.hypot(bx - ax, by - ay)
        if travelled + segment >= distance:
            t = (distance - travelled) / segment if segment else 0.0
            return (ax + t * (bx - ax), ay + t * (by - ay)), math.atan2(by - ay, bx - ax)
        travelled += segment
    (ax, ay), (bx, by) = centerline[-2], centerline[-1]
    return (bx, by), math.atan2(by - ay, bx - ax)


def make_world(centerline: Optional[List[Point]] = None, track_width: float = 0.5,
               size_m: Tuple[float, float] = (3.0, 4.5), ppm: float = 200.0,
               tunnel_at: Optional[Tuple[float, float]] = None,
               balloon_at: Optional[float] = None,
               finish_at: Optional[float] = None) -> World:
    """Нарисовать карту. Расстояния событий — в метрах вдоль осевой линии от старта."""
    centerline = centerline or s_curve()
    image = np.full((int(size_m[1] * ppm), int(size_m[0] * ppm), 3), FLOOR, np.uint8)
    world = World(image, ppm, centerline, track_width)

    def draw(points: Sequence[Point], color, width_m: float) -> None:
        pixels = np.array([world.to_pixel(*p) for p in points], np.int32).reshape(-1, 1, 2)
        cv2.polylines(image, [pixels], False, color, max(1, int(width_m * ppm)), cv2.LINE_8)

    draw(centerline, WOOD, track_width)

    def fill_section(begin: float, end: float, width_m: float, color) -> None:
        """Закрасить участок поперёк полосы с ровными торцами (без скруглений)."""
        count = max(2, int((end - begin) / 0.02))
        left, right = [], []
        for i in range(count):
            (px, py), heading = _point_at(centerline, begin + (end - begin) * i / (count - 1))
            nx, ny = -math.sin(heading) * width_m / 2, math.cos(heading) * width_m / 2
            left.append(world.to_pixel(px + nx, py + ny))
            right.append(world.to_pixel(px - nx, py - ny))
        polygon = np.array(left + right[::-1], np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(image, [polygon], color)

    if tunnel_at is not None:
        # Тень туннеля шире полосы: внутри не видно ни дерева, ни пола.
        fill_section(tunnel_at[0], tunnel_at[1], track_width * 3.0, DARK)
    if finish_at is not None:
        fill_section(finish_at, finish_at + 0.08, track_width, FINISH)
    if balloon_at is not None:
        (bx, by), _ = _point_at(centerline, balloon_at)
        cv2.circle(image, tuple(int(v) for v in world.to_pixel(bx, by)),
                   int(0.14 * ppm), BALLOON, -1)
    return world


@dataclass
class Robot:
    x: float
    y: float
    heading: float              # рад, 0 — вдоль оси x карты
    linear: float = 0.0
    angular: float = 0.0
    response: float = 0.15      # с, инерция привода
    turn_bias: float = 0.0      # рад/с, постоянный увод (неодинаковые моторы)

    def step(self, linear_cmd: float, angular_cmd: float, dt: float) -> None:
        alpha = min(1.0, dt / self.response) if self.response > 0 else 1.0
        self.linear += (linear_cmd - self.linear) * alpha
        self.angular += (angular_cmd - self.angular) * alpha
        moving = abs(self.linear) > 1e-3
        self.heading += (self.angular + (self.turn_bias if moving else 0.0)) * dt
        self.x += self.linear * math.cos(self.heading) * dt
        self.y += self.linear * math.sin(self.heading) * dt


def render(world: World, robot: Robot, camera: Camera) -> np.ndarray:
    """Кадр с камеры робота."""
    cos_h, sin_h = math.cos(robot.heading), math.sin(robot.heading)
    near, far, side = camera.forward + 0.08, camera.forward + 1.5, 1.0
    ground = [(near, side), (near, -side), (far, side), (far, -side)]
    source, target = [], []
    for gx, gy in ground:
        pixel = camera.project(gx, gy)
        if pixel is None:
            raise ValueError('точка пола вне поля зрения: проверьте наклон камеры')
        wx = robot.x + gx * cos_h - gy * sin_h
        wy = robot.y + gx * sin_h + gy * cos_h
        source.append(world.to_pixel(wx, wy))
        target.append(pixel)
    matrix = cv2.getPerspectiveTransform(np.array(source, np.float32),
                                         np.array(target, np.float32))
    frame = cv2.warpPerspective(world.image, matrix, (camera.width, camera.height_px),
                                flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                borderValue=FLOOR)
    # Выше линии горизонта пола нет — там «стена».
    horizon = camera.height_px / 2.0 - camera.focal * math.tan(math.radians(camera.tilt_deg))
    cutoff = int(min(camera.height_px, max(0, horizon + 6)))
    frame[:cutoff] = WALL
    return frame


def start_pose(world: World, lateral: float = 0.0, heading_error_deg: float = 0.0) -> Robot:
    (x, y), heading = _point_at(world.centerline, 0.05)
    return Robot(x - math.sin(heading) * lateral, y + math.cos(heading) * lateral,
                 heading + math.radians(heading_error_deg))

"""Источник кадров: USB-камера, видеофайл или папка с кадрами. Без ROS.

Чтение идёт в отдельном потоке и хранит только ПОСЛЕДНИЙ кадр: автопилот
никогда не обрабатывает устаревшую картинку из очереди драйвера.
"""

from __future__ import annotations

import glob
import os
import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp')


def is_camera(spec: str) -> bool:
    return spec.isdigit() or spec.startswith('/dev/')


class FrameSource:
    """Открыть источник по строке: '0', '/dev/video0', 'run.mp4', 'frames_dir/'."""

    def __init__(self, spec: str, width: int = 640, height: int = 480, fps: float = 30.0,
                 loop: bool = False):
        self.spec = str(spec)
        self.loop = loop
        self.fps = fps
        self._files = None
        self._index = 0
        self._capture = None
        self.live = is_camera(self.spec)

        if os.path.isdir(self.spec):
            self._files = sorted(
                path for path in glob.glob(os.path.join(self.spec, '*'))
                if path.lower().endswith(IMAGE_EXTENSIONS))
            if not self._files:
                raise OSError(f'в папке {self.spec} нет кадров')
            return

        if self.live:
            target = int(self.spec) if self.spec.isdigit() else self.spec
            self._capture = cv2.VideoCapture(target)
            # MJPG: вебкамера отдаёт 30 кадр/с без перегрузки USB.
            self._capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            self._capture.set(cv2.CAP_PROP_FPS, fps)
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        else:
            self._capture = cv2.VideoCapture(self.spec)
            file_fps = self._capture.get(cv2.CAP_PROP_FPS)
            if file_fps and file_fps > 1.0:
                self.fps = float(file_fps)
        if not self._capture.isOpened():
            raise OSError(f'не удалось открыть источник кадров: {self.spec}')

    def read(self) -> Optional[np.ndarray]:
        """Следующий кадр или None, если источник закончился/камера не ответила."""
        if self._files is not None:
            if self._index >= len(self._files):
                if not self.loop:
                    return None
                self._index = 0
            frame = cv2.imread(self._files[self._index])
            self._index += 1
            return frame
        ok, frame = self._capture.read()
        if not ok and self.loop and not self.live:
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._capture.read()
        return frame if ok else None

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


class LatestFrame:
    """Фоновое чтение источника; get() отдаёт самый свежий кадр и его время."""

    def __init__(self, source: FrameSource, clock=time.monotonic):
        self._source = source
        self._clock = clock
        self._lock = threading.Lock()
        self._frame: Optional[np.ndarray] = None
        self._stamp = 0.0
        self._serial = 0
        self._taken = 0
        self.ended = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name='frame-source', daemon=True)

    def start(self) -> 'LatestFrame':
        self._thread.start()
        return self

    def _run(self) -> None:
        period = 1.0 / self._source.fps if self._source.fps > 0 else 0.033
        failures = 0
        while not self._stop.is_set():
            started = self._clock()
            frame = self._source.read()
            if frame is None:
                if not self._source.live:
                    self.ended = True
                    return
                failures += 1
                if failures > 50:           # камера молчит ~5 с — считаем, что её нет
                    self.ended = True
                    return
                self._stop.wait(0.1)
                continue
            failures = 0
            with self._lock:
                self._frame = frame
                self._stamp = self._clock()
                self._serial += 1
            if not self._source.live:       # файл проигрываем в реальном времени
                self._stop.wait(max(0.0, period - (self._clock() - started)))

    def get(self) -> Tuple[Optional[np.ndarray], float, bool]:
        """(кадр, время получения, новый ли он с прошлого вызова)."""
        with self._lock:
            fresh = self._serial != self._taken
            self._taken = self._serial
            return self._frame, self._stamp, fresh

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(2.0)
        self._source.close()

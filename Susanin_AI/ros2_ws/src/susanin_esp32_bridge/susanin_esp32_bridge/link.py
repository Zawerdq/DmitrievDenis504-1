"""Канал связи с ESP32: поток, который держит соединение и шлёт команды.

Свойства, важные для безопасности:

* команда гусеницам отправляется с постоянной частотой (по умолчанию 20 Гц),
  поэтому таймаут прошивки не срабатывает, пока мост жив;
* если команда от ROS устарела (``command_timeout``), вместо неё уходит ноль;
* аварийный останов обнуляет команду немедленно;
* связь проверяется ping/pong: если ESP32 молчит дольше ``pong_timeout``,
  соединение считается потерянным и переустанавливается;
* при штатном завершении последним сообщением отправляется останов;
* в ручном режиме (``set_active(False)``) мост один раз шлёт останов и замолкает,
  чтобы не перебивать веб-джойстик; связь при этом продолжает проверяться.

Модуль не зависит от ROS и тестируется обычным pytest.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct
import threading
import time
from typing import Callable, Optional, Tuple

from susanin_esp32_bridge.protocol import (
    drive_message,
    led_message,
    STOP_MESSAGE,
    tracks_to_joystick,
)
from susanin_esp32_bridge.transport import TransportError, WebSocketTransport


@dataclass
class LinkConfig:
    # Адрес ESP32. 192.168.4.1 — адрес точки доступа ESP32 по умолчанию.
    host: str = '192.168.4.1'
    port: int = 80
    path: str = '/ws'

    send_rate: float = 20.0           # Гц, частота отправки команды
    command_timeout: float = 0.5      # с, после которых команда от ROS считается устаревшей
    ping_interval: float = 0.5        # с; 0 — не проверять связь ping/pong
    pong_timeout: float = 1.5         # с без ответа ESP32 до разрыва соединения
    connect_timeout: float = 3.0      # с
    reconnect_delay_min: float = 0.5  # с
    reconnect_delay_max: float = 5.0  # с

    # Подключение моторов (описывает железо, чтобы не менять прошивку)
    pwm_max: int = 255
    invert_left: bool = False
    invert_right: bool = False
    swap_sides: bool = False

    def validate(self) -> None:
        if self.send_rate <= 0.0:
            raise ValueError('send_rate должен быть > 0')
        if self.command_timeout <= 0.0:
            raise ValueError('command_timeout должен быть > 0')
        if self.ping_interval < 0.0:
            raise ValueError('ping_interval не может быть отрицательным')
        if self.ping_interval > 0.0 and self.pong_timeout <= self.ping_interval:
            raise ValueError('pong_timeout должен быть больше ping_interval')
        if not 0 < self.pwm_max <= 255:
            raise ValueError('pwm_max должен быть в диапазоне 1..255')
        if not 0.0 < self.reconnect_delay_min <= self.reconnect_delay_max:
            raise ValueError('некорректные reconnect_delay_min/max')


@dataclass
class LinkStats:
    connected: bool = False
    connects: int = 0                 # сколько раз соединение было установлено
    tx_count: int = 0                 # отправлено команд движения
    last_rtt_ms: Optional[float] = None
    last_error: str = ''
    last_xy: Tuple[int, int] = (0, 0)
    command_stale: bool = True
    estop: bool = False
    active: bool = True               # False — ручной режим, команды не отправляются


LogFn = Callable[[str, str], None]


def _silent_log(level: str, message: str) -> None:
    del level, message


class Esp32Link:

    def __init__(
        self,
        cfg: Optional[LinkConfig] = None,
        transport_factory: Optional[Callable[[], object]] = None,
        log: LogFn = _silent_log,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.cfg = cfg or LinkConfig()
        self.cfg.validate()
        self._factory = transport_factory or (lambda: WebSocketTransport(
            self.cfg.host, self.cfg.port, self.cfg.path, self.cfg.connect_timeout))
        self._log = log
        self._clock = clock

        self._lock = threading.Lock()
        self._tracks = (0.0, 0.0)
        self._tracks_time: Optional[float] = None
        self._estop = False
        self._active = True
        self._release_pending = False
        self._led: Optional[bool] = None
        self._led_dirty = False
        self._stats = LinkStats()

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ---- управление из других потоков --------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='esp32-link', daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        """Остановить поток. Перед закрытием соединения отправляется останов."""
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout)

    def set_tracks(self, left: float, right: float) -> None:
        with self._lock:
            self._tracks = (float(left), float(right))
            self._tracks_time = self._clock()

    def set_estop(self, active: bool) -> None:
        with self._lock:
            self._estop = bool(active)
            if self._estop:
                self._tracks = (0.0, 0.0)
                self._tracks_time = None

    def set_active(self, active: bool) -> None:
        """True — передавать команды ROS; False — замолчать (управляет веб-джойстик)."""
        with self._lock:
            active = bool(active)
            if self._active and not active:
                self._release_pending = True      # перед молчанием остановить моторы
            if active and not self._active:
                self._tracks = (0.0, 0.0)         # старая команда не должна «выстрелить»
                self._tracks_time = None
            self._active = active
            self._stats.active = active

    def set_led(self, on: bool) -> None:
        with self._lock:
            self._led = bool(on)
            self._led_dirty = True

    @property
    def connected(self) -> bool:
        with self._lock:
            return self._stats.connected

    def stats(self) -> LinkStats:
        with self._lock:
            return LinkStats(**vars(self._stats))

    # ---- рабочий поток -----------------------------------------------------

    def _current_xy(self, now: float) -> Tuple[int, int]:
        with self._lock:
            stale = (
                self._tracks_time is None
                or (now - self._tracks_time) > self.cfg.command_timeout
            )
            self._stats.command_stale = stale
            self._stats.estop = self._estop
            if stale or self._estop:
                return 0, 0
            left, right = self._tracks
        return tracks_to_joystick(
            left, right,
            pwm_max=self.cfg.pwm_max,
            invert_left=self.cfg.invert_left,
            invert_right=self.cfg.invert_right,
            swap_sides=self.cfg.swap_sides,
        )

    def _run(self) -> None:
        delay = self.cfg.reconnect_delay_min
        while not self._stop.is_set():
            transport = self._factory()
            try:
                transport.connect()
            except TransportError as exc:
                self._note_error(str(exc))
                self._stop.wait(delay)
                delay = min(delay * 2.0, self.cfg.reconnect_delay_max)
                continue

            delay = self.cfg.reconnect_delay_min
            with self._lock:
                self._stats.connected = True
                self._stats.connects += 1
                self._stats.last_error = ''
                self._led_dirty = self._led is not None  # повторить состояние LED
            self._log('info', f'Связь с ESP32 установлена ({self._describe(transport)})')

            try:
                self._session(transport)
            except TransportError as exc:
                self._note_error(str(exc))
            finally:
                try:
                    transport.send_text(STOP_MESSAGE)  # по возможности
                except TransportError:
                    pass
                transport.close()
                with self._lock:
                    self._stats.connected = False
                    self._stats.last_xy = (0, 0)
                    self._stats.last_rtt_ms = None

    def _session(self, transport) -> None:
        cfg = self.cfg
        period = 1.0 / cfg.send_rate
        now = self._clock()
        next_send = now
        last_ping = None
        last_rx = now

        while not self._stop.is_set():
            now = self._clock()

            if now >= next_send:
                with self._lock:
                    active = self._active
                    release = self._release_pending
                    self._release_pending = False
                x, y = 0, 0
                if active:
                    x, y = self._current_xy(now)
                    transport.send_text(drive_message(x, y))
                elif release:
                    transport.send_text(STOP_MESSAGE)
                with self._lock:
                    if active or release:
                        self._stats.tx_count += 1
                        self._stats.last_xy = (x, y)
                    led = self._led if self._led_dirty else None
                    self._led_dirty = False
                if led is not None:
                    transport.send_text(led_message(led))
                next_send += period
                if next_send < now:          # отстали (например, после подвисания)
                    next_send = now + period

            if cfg.ping_interval > 0.0:
                if last_ping is None or (now - last_ping) >= cfg.ping_interval:
                    transport.send_ping(struct.pack('>d', now))
                    last_ping = now
                if (now - last_rx) > cfg.pong_timeout:
                    raise TransportError(
                        f'ESP32 не отвечает дольше {cfg.pong_timeout:.1f} с')

            event = transport.poll(max(0.001, next_send - self._clock()))
            if event is not None:
                last_rx = self._clock()
                kind, data = event
                if kind == 'pong' and len(data) == 8:
                    sent_at = struct.unpack('>d', data)[0]
                    with self._lock:
                        self._stats.last_rtt_ms = max(0.0, (last_rx - sent_at) * 1000.0)

    def _note_error(self, message: str) -> None:
        with self._lock:
            repeated = message == self._stats.last_error
            self._stats.last_error = message
        if not repeated:   # не засорять журнал одинаковыми ошибками при переподключении
            self._log('error', f'Связь с ESP32: {message}')

    @staticmethod
    def _describe(transport) -> str:
        return getattr(transport, 'description', type(transport).__name__)

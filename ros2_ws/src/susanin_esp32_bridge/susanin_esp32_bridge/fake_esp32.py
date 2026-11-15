"""Эмулятор прошивки ESP32 для разработки без робота.

Повторяет поведение прошивки, существенное для моста:

* WebSocket-сервер на пути /ws, текстовые JSON-сообщения;
* микшер driveMix и флаги invert1/invert2;
* таймаут команд: если джойстик «отклонён» и сообщений нет дольше таймаута —
  моторы останавливаются.

Два варианта прошивки (параметр ``firmware``):

* ``upstream`` — исходная DiffrentialControl_invert.ino: таймаут 3000 мс, при
  отключении клиента моторы НЕ останавливаются, таймаут перезапускает любой
  текстовый кадр (даже не JSON);
* ``susanin`` — firmware/susanin_esp32 с правками Ф1–Ф5: таймаут 500 мс, останов
  при отключении клиента, таймаут перезапускает только корректный JSON, блокировка
  моторов по ``{"lock":1}`` (общий СТОП).

ЭТО НЕ ПРОВЕРКА РЕАЛЬНОГО РОБОТА: эмулятор не моделирует моторы, питание,
нагрев драйвера и качество Wi-Fi.

Запуск вручную:  python -m susanin_esp32_bridge.fake_esp32 --port 8765
"""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import time
from typing import List, Optional, Tuple

try:  # websockets >= 13
    from websockets.asyncio.server import serve
except ImportError:  # websockets 10–12 (Ubuntu 22.04/24.04: python3-websockets)
    from websockets import serve
from websockets.exceptions import ConnectionClosed

from susanin_esp32_bridge.protocol import firmware_mix

FIRMWARE_COMMAND_TIMEOUT = 3.0  # COMMAND_TIMEOUT = 3000 мс в исходной прошивке
SUSANIN_COMMAND_TIMEOUT = 0.5   # COMMAND_TIMEOUT = 500 мс после правки Ф1
SUSANIN_MAX_MESSAGE = 128       # размер буфера message[] после правки Ф3
SUSANIN_LOCK_HOLD = 2.0         # LOCK_HOLD = 2000 мс: блокировка без повторов снимается сама
FIRMWARES = ('upstream', 'susanin')


class FakeEsp32:

    def __init__(self, host: str = '127.0.0.1', port: int = 0,
                 command_timeout: Optional[float] = None, verbose: bool = False,
                 firmware: str = 'upstream'):
        if firmware not in FIRMWARES:
            raise ValueError(f'firmware должен быть одним из {FIRMWARES}')
        self._firmware = firmware
        if command_timeout is None:
            command_timeout = (SUSANIN_COMMAND_TIMEOUT if firmware == 'susanin'
                               else FIRMWARE_COMMAND_TIMEOUT)
        self._host = host
        self._requested_port = port
        self._command_timeout = command_timeout
        self._verbose = verbose

        self._lock = threading.Lock()
        self._motors = (0, 0)
        self._joy = (0, 0)
        self._invert = [1, 1]
        self._led = 0
        self._locked = False
        self._lock_time = 0.0
        self.lock_hold = SUSANIN_LOCK_HOLD
        self._last_command: Optional[float] = None
        self._history: List[Tuple[float, int, int]] = []
        self._message_count = 0
        self._timeouts = 0

        self._port: Optional[int] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_future: Optional[asyncio.Future] = None
        self._clients = set()
        self._ready = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ---- состояние для тестов ----------------------------------------------

    @property
    def port(self) -> int:
        assert self._port is not None, 'сервер не запущен'
        return self._port

    @property
    def motors(self) -> Tuple[int, int]:
        """Текущие ШИМ (motor1, motor2) в диапазоне -255..255."""
        with self._lock:
            return self._motors

    @property
    def led(self) -> int:
        with self._lock:
            return self._led

    @property
    def locked(self) -> bool:
        with self._lock:
            return self._locked

    @property
    def message_count(self) -> int:
        with self._lock:
            return self._message_count

    @property
    def timeouts(self) -> int:
        """Сколько раз сработал таймаут команд «прошивки»."""
        with self._lock:
            return self._timeouts

    @property
    def history(self) -> List[Tuple[float, int, int]]:
        with self._lock:
            return list(self._history)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # ---- жизненный цикл ----------------------------------------------------

    def start(self) -> 'FakeEsp32':
        self._thread = threading.Thread(target=self._thread_main, name='fake-esp32', daemon=True)
        self._thread.start()
        if not self._ready.wait(5.0):
            raise RuntimeError('эмулятор ESP32 не запустился')
        return self

    def stop(self) -> None:
        if self._loop is not None and self._stop_future is not None:
            self._loop.call_soon_threadsafe(self._finish)
        if self._thread is not None:
            self._thread.join(5.0)
        self._thread = None

    def _finish(self) -> None:
        if self._stop_future is not None and not self._stop_future.done():
            self._stop_future.set_result(None)

    def drop_clients(self) -> None:
        """Разорвать все соединения (имитация перезагрузки ESP32)."""
        if self._loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(self._close_all(), self._loop)
        future.result(5.0)

    async def _close_all(self) -> None:
        for ws in list(self._clients):
            await ws.close()

    def _thread_main(self) -> None:
        asyncio.run(self._serve())

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop_future = self._loop.create_future()
        async with serve(self._handle, self._host, self._requested_port) as server:
            self._port = server.sockets[0].getsockname()[1]
            watchdog = asyncio.ensure_future(self._watchdog())
            self._ready.set()
            try:
                await self._stop_future
            finally:
                watchdog.cancel()

    # ---- логика «прошивки» -------------------------------------------------

    async def _handle(self, ws, *_legacy_path) -> None:
        request = getattr(ws, 'request', None)
        path = getattr(request, 'path', None) or getattr(ws, 'path', '/ws')
        if path != '/ws':
            await ws.close(code=1008, reason='only /ws')
            return
        self._clients.add(ws)
        try:
            async for message in ws:
                if isinstance(message, str):
                    self._on_text(message)
        except ConnectionClosed:
            pass
        finally:
            self._clients.discard(ws)
            if self._firmware == 'susanin':      # правка Ф2: останов при отключении
                with self._lock:
                    self._joy = (0, 0)
                    self._set_motors(0, 0)

    def _on_text(self, text: str) -> None:
        if self._firmware == 'upstream':
            # Исходная прошивка перезапускает таймаут ДО разбора сообщения.
            with self._lock:
                self._last_command = time.monotonic()
        elif not 0 < len(text.encode('utf-8')) < SUSANIN_MAX_MESSAGE:
            return                               # правка Ф3: слишком длинное сообщение
        try:
            obj = json.loads(text)
        except ValueError:
            return
        if not isinstance(obj, dict):
            return
        with self._lock:
            self._last_command = time.monotonic()
            self._message_count += 1
            if 'lock' in obj and self._firmware == 'susanin':      # правка Ф5
                self._locked = int(obj['lock']) == 1
                self._lock_time = time.monotonic()
                if self._locked:
                    self._joy = (0, 0)
                    self._set_motors(0, 0)
            elif 'x' in obj and 'y' in obj:
                if self._locked:                 # блокировка: команды моторам игнорируются
                    self._joy = (0, 0)
                    self._set_motors(0, 0)
                    return
                self._joy = (int(obj['x']), int(obj['y']))
                self._set_motors(*firmware_mix(*self._joy, *self._invert))
            elif 'led' in obj:
                self._led = int(obj['led'])
            elif 'invert1' in obj:
                self._invert[0] = -1 if int(obj['invert1']) == 1 else 1
            elif 'invert2' in obj:
                self._invert[1] = -1 if int(obj['invert2']) == 1 else 1

    def _set_motors(self, left: int, right: int) -> None:
        if (left, right) != self._motors:
            self._motors = (left, right)
            self._history.append((time.monotonic(), left, right))
            if self._verbose:
                print(f'[fake-esp32] motor1={left:+4d} motor2={right:+4d}', flush=True)

    async def _watchdog(self) -> None:
        while True:
            await asyncio.sleep(0.02)
            with self._lock:
                if self._locked and (time.monotonic() - self._lock_time) > self.lock_hold:
                    self._locked = False         # Pi замолчала — блокировка снимается сама
                if self._joy != (0, 0) and self._last_command is not None and (
                        time.monotonic() - self._last_command > self._command_timeout):
                    self._joy = (0, 0)
                    self._timeouts += 1
                    self._set_motors(0, 0)
                    if self._verbose:
                        print('[fake-esp32] Command timeout! Stopping motors.', flush=True)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description='Эмулятор прошивки ESP32 «Сусанин ИИ»')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--firmware', choices=FIRMWARES, default='upstream',
                        help='upstream — исходная прошивка BOTS; susanin — с правками Ф1–Ф3')
    args, _ = parser.parse_known_args(argv)

    fake = FakeEsp32(args.host, args.port, verbose=True, firmware=args.firmware).start()
    print(f'[fake-esp32] прошивка {args.firmware}, слушаю ws://{args.host}:{fake.port}/ws '
          '(Ctrl+C — выход)', flush=True)
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        fake.stop()


if __name__ == '__main__':
    main()

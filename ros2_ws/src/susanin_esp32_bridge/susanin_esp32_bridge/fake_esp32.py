"""Эмулятор прошивки ESP32 (DiffrentialControl_invert.ino) для разработки без робота.

Повторяет поведение прошивки, существенное для моста:

* WebSocket-сервер на пути /ws, текстовые JSON-сообщения;
* микшер driveMix и флаги invert1/invert2;
* таймаут команд (в прошивке 3000 мс): если джойстик «отклонён» и сообщений
  нет дольше таймаута — моторы останавливаются.

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

FIRMWARE_COMMAND_TIMEOUT = 3.0  # COMMAND_TIMEOUT = 3000 мс в прошивке


class FakeEsp32:

    def __init__(self, host: str = '127.0.0.1', port: int = 0,
                 command_timeout: float = FIRMWARE_COMMAND_TIMEOUT, verbose: bool = False):
        self._host = host
        self._requested_port = port
        self._command_timeout = command_timeout
        self._verbose = verbose

        self._lock = threading.Lock()
        self._motors = (0, 0)
        self._joy = (0, 0)
        self._invert = [1, 1]
        self._led = 0
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

    def _on_text(self, text: str) -> None:
        try:
            obj = json.loads(text)
        except ValueError:
            return
        if not isinstance(obj, dict):
            return
        with self._lock:
            self._last_command = time.monotonic()
            self._message_count += 1
            if 'x' in obj and 'y' in obj:
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
    args, _ = parser.parse_known_args(argv)

    fake = FakeEsp32(args.host, args.port, verbose=True).start()
    print(f'[fake-esp32] слушаю ws://{args.host}:{fake.port}/ws (Ctrl+C — выход)', flush=True)
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        fake.stop()


if __name__ == '__main__':
    main()

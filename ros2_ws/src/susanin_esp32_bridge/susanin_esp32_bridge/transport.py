"""Транспорт до ESP32. Сейчас — WebSocket (работает с прошивкой без изменений).

Интерфейс транспорта намеренно узкий (connect / send_text / send_ping / poll /
close): при появлении в прошивке приёма команд по USB Serial достаточно
добавить второй класс с тем же интерфейсом.
"""

from __future__ import annotations

import socket
from typing import Optional, Tuple

import websocket  # пакет websocket-client (apt: python3-websocket)


class TransportError(Exception):
    """Любая ошибка связи: соединение нужно закрыть и установить заново."""


class WebSocketTransport:

    def __init__(self, host: str, port: int, path: str = '/ws',
                 connect_timeout: float = 3.0, io_timeout: float = 1.0):
        self._url = f'ws://{host}:{int(port)}{path}'
        self._connect_timeout = connect_timeout
        self._io_timeout = io_timeout
        self._ws: Optional[websocket.WebSocket] = None

    @property
    def description(self) -> str:
        return self._url

    def connect(self) -> None:
        try:
            self._ws = websocket.create_connection(
                self._url,
                timeout=self._connect_timeout,
                sockopt=[(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)],
                http_no_proxy=['*'],   # ESP32 всегда в локальной сети, прокси не нужен
                enable_multithread=True,
            )
        except (OSError, websocket.WebSocketException) as exc:
            self._ws = None
            raise TransportError(f'не удалось подключиться к {self._url}: {exc}') from exc

    def send_text(self, text: str) -> None:
        self._send(lambda ws: ws.send(text))

    def send_ping(self, payload: bytes = b'') -> None:
        self._send(lambda ws: ws.ping(payload))

    def _send(self, action) -> None:
        if self._ws is None:
            raise TransportError('соединение не установлено')
        try:
            self._ws.settimeout(self._io_timeout)
            action(self._ws)
        except (OSError, websocket.WebSocketException) as exc:
            raise TransportError(f'ошибка отправки: {exc}') from exc

    def poll(self, timeout: float) -> Optional[Tuple[str, bytes]]:
        """Подождать входящий кадр не дольше ``timeout`` секунд.

        Возвращает ('pong' | 'text' | 'ping' | 'binary', данные) или None по таймауту.
        """
        if self._ws is None:
            raise TransportError('соединение не установлено')
        try:
            self._ws.settimeout(max(0.001, timeout))
            opcode, frame = self._ws.recv_data_frame(control_frame=True)
        except (websocket.WebSocketTimeoutException, socket.timeout):
            return None
        except (OSError, websocket.WebSocketException) as exc:
            raise TransportError(f'ошибка приёма: {exc}') from exc

        if opcode == websocket.ABNF.OPCODE_CLOSE:
            raise TransportError('ESP32 закрыла соединение')
        kind = {
            websocket.ABNF.OPCODE_PONG: 'pong',
            websocket.ABNF.OPCODE_PING: 'ping',
            websocket.ABNF.OPCODE_TEXT: 'text',
        }.get(opcode, 'binary')
        return kind, frame.data

    def close(self) -> None:
        ws, self._ws = self._ws, None
        if ws is None:
            return
        try:
            ws.settimeout(0.3)
            ws.close(timeout=0.3)
        except Exception:  # noqa: BLE001 — закрытие всегда «по возможности»
            pass
        try:
            # ws.close() ничего не делает, если кадр закрытия уже пришёл от ESP32,
            # и TCP-сокет остаётся открытым. Закрываем его явно.
            ws.shutdown()
        except Exception:  # noqa: BLE001
            pass

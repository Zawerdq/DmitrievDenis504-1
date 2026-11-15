"""Поведение двух вариантов прошивки при потере связи (на эмуляторе).

``upstream`` — прошивка, которая сейчас стоит на роботе.
``susanin``  — firmware/susanin_esp32 с правками Ф1–Ф3 (подготовлена, НЕ прошита).

Тесты фиксируют разницу, ради которой правки предложены. Эмулятор повторяет
логику исходников; реальную ESP32 эти тесты не проверяют.
"""

import json
import time

import pytest
import websocket

from susanin_esp32_bridge.fake_esp32 import FakeEsp32
from susanin_esp32_bridge.link import Esp32Link, LinkConfig

FULL_AHEAD = json.dumps({'x': 0, 'y': 255})


def wait_for(condition, timeout=3.0, step=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(step)
    return condition()


def connect(fake):
    return websocket.create_connection(
        f'ws://127.0.0.1:{fake.port}/ws', timeout=2.0, http_no_proxy=['*'])


def crash(ws):
    """Оборвать соединение без кадра закрытия и без команды «стоп» — как при падении моста."""
    ws.sock.close()


@pytest.fixture
def upstream():
    server = FakeEsp32(firmware='upstream').start()
    yield server
    server.stop()


@pytest.fixture
def susanin():
    server = FakeEsp32(firmware='susanin').start()
    yield server
    server.stop()


# ---- обрыв соединения (падение моста) ----------------------------------------

def test_upstream_keeps_driving_after_client_crash(upstream):
    """Проблема П2: исходная прошивка продолжает ехать до своего таймаута 3 с."""
    ws = connect(upstream)
    ws.send(FULL_AHEAD)
    assert wait_for(lambda: upstream.motors == (255, 255))
    crash(ws)
    assert wait_for(lambda: upstream.client_count == 0)
    time.sleep(0.5)
    assert upstream.motors == (255, 255)


def test_susanin_stops_immediately_after_client_crash(susanin):
    """Правка Ф2: останов сразу при отключении клиента."""
    ws = connect(susanin)
    ws.send(FULL_AHEAD)
    assert wait_for(lambda: susanin.motors == (255, 255))
    started = time.monotonic()
    crash(ws)
    assert wait_for(lambda: susanin.motors == (0, 0), timeout=1.0)
    assert time.monotonic() - started < 0.4
    assert susanin.timeouts == 0          # сработал останов по отключению, а не таймаут


# ---- соединение открыто, но команды не идут (пропал Wi-Fi, завис клиент) ------

def test_susanin_stops_after_half_second_of_silence(susanin):
    """Правка Ф1: таймаут 500 мс вместо 3000 мс."""
    ws = connect(susanin)
    try:
        ws.send(FULL_AHEAD)
        assert wait_for(lambda: susanin.motors == (255, 255))
        started = time.monotonic()
        assert wait_for(lambda: susanin.motors == (0, 0), timeout=2.0)
        elapsed = time.monotonic() - started
        assert 0.35 < elapsed < 1.0
        assert susanin.timeouts == 1
    finally:
        ws.close()


def test_upstream_needs_three_seconds_of_silence(upstream):
    ws = connect(upstream)
    try:
        ws.send(FULL_AHEAD)
        assert wait_for(lambda: upstream.motors == (255, 255))
        time.sleep(1.0)
        assert upstream.motors == (255, 255)      # через 1 с всё ещё едет
    finally:
        ws.close()


def test_susanin_keepalive_prevents_timeout(susanin):
    """Веб-джойстик после правки Ф1 повторяет команду каждые 100 мс — робот не встаёт."""
    ws = connect(susanin)
    try:
        for _ in range(15):               # 1.5 с удержания джойстика
            ws.send(FULL_AHEAD)
            time.sleep(0.1)
        assert susanin.motors == (255, 255)
        assert susanin.timeouts == 0
    finally:
        ws.close()


# ---- некорректные сообщения ---------------------------------------------------

def test_susanin_garbage_does_not_keep_robot_moving(susanin):
    """Правка Ф3: мусор не перезапускает таймаут."""
    ws = connect(susanin)
    try:
        ws.send(FULL_AHEAD)
        assert wait_for(lambda: susanin.motors == (255, 255))
        deadline = time.monotonic() + 1.2
        while time.monotonic() < deadline:
            ws.send('not json at all')
            ws.send('x' * 300)
            time.sleep(0.05)
        assert susanin.motors == (0, 0)
        assert susanin.timeouts == 1
    finally:
        ws.close()


def test_upstream_garbage_keeps_robot_moving():
    """Исходная прошивка перезапускает таймаут любым текстовым кадром."""
    server = FakeEsp32(firmware='upstream', command_timeout=0.5).start()
    try:
        ws = connect(server)
        ws.send(FULL_AHEAD)
        assert wait_for(lambda: server.motors == (255, 255))
        deadline = time.monotonic() + 1.2
        while time.monotonic() < deadline:
            ws.send('not json at all')
            time.sleep(0.05)
        assert server.motors == (255, 255)
        ws.close()
    finally:
        server.stop()


# ---- мост ROS 2 с новой прошивкой ---------------------------------------------

def test_bridge_works_with_susanin_firmware(susanin):
    """Мост шлёт команду 20 Гц — таймаут 500 мс при исправной связи не срабатывает."""
    link = Esp32Link(LinkConfig(host='127.0.0.1', port=susanin.port))
    link.start()
    try:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            link.set_tracks(0.5, 0.5)
            time.sleep(0.05)
        assert susanin.motors == (128, 128)
        assert susanin.timeouts == 0
    finally:
        link.stop()
    assert wait_for(lambda: susanin.motors == (0, 0), timeout=1.0)


def test_unknown_firmware_is_rejected():
    with pytest.raises(ValueError):
        FakeEsp32(firmware='nope')


# ---- общий СТОП (правка Ф5): блокировка на ESP32 -------------------------------

def test_susanin_lock_blocks_web_joystick(susanin):
    """СТОП с Pi останавливает робота, даже когда им управляют с телефона."""
    link = Esp32Link(LinkConfig(host='127.0.0.1', port=susanin.port))
    link.start()
    phone = connect(susanin)
    try:
        assert wait_for(lambda: link.connected)
        link.set_active(False)                    # MANUAL: ведёт телефон
        time.sleep(0.2)
        phone.send(FULL_AHEAD)
        assert wait_for(lambda: susanin.motors == (255, 255))

        link.set_estop(True)                      # оператор нажал СТОП на страничке Pi
        assert wait_for(lambda: susanin.motors == (0, 0), timeout=1.0)
        assert wait_for(lambda: susanin.locked)
        for _ in range(10):                       # телефон продолжает давить джойстик
            phone.send(FULL_AHEAD)
            time.sleep(0.05)
            assert susanin.motors == (0, 0)

        link.set_estop(False)                     # СТОП снят
        assert wait_for(lambda: not susanin.locked, timeout=1.0)
        phone.send(FULL_AHEAD)
        assert wait_for(lambda: susanin.motors == (255, 255))
    finally:
        phone.close()
        link.stop()


def test_susanin_lock_expires_if_pi_goes_silent(susanin):
    """Блокировка не «залипает»: без повторов от Pi она снимается сама."""
    susanin.lock_hold = 0.4
    ws = connect(susanin)
    try:
        ws.send(json.dumps({'lock': 1}))
        assert wait_for(lambda: susanin.locked)
        ws.send(FULL_AHEAD)
        time.sleep(0.1)
        assert susanin.motors == (0, 0)
        assert wait_for(lambda: not susanin.locked, timeout=1.5)
        ws.send(FULL_AHEAD)
        assert wait_for(lambda: susanin.motors == (255, 255))
    finally:
        ws.close()


def test_upstream_ignores_lock(upstream):
    """Исходная прошивка блокировку не знает: СТОП с Pi телефон не блокирует."""
    ws = connect(upstream)
    try:
        ws.send(json.dumps({'lock': 1}))
        ws.send(FULL_AHEAD)
        assert wait_for(lambda: upstream.motors == (255, 255))
        assert not upstream.locked
    finally:
        ws.close()

"""Тесты канала связи: сторожевые таймеры, останов, переподключение.

Часть тестов использует подставной транспорт (точный контроль над «обрывом»),
часть — эмулятор прошивки по настоящему WebSocket на localhost.
Это программные тесты; на физическом роботе они ничего не проверяют.
"""

import json
import threading
import time

import pytest

from susanin_esp32_bridge.fake_esp32 import FakeEsp32
from susanin_esp32_bridge.link import Esp32Link, LinkConfig
from susanin_esp32_bridge.transport import TransportError


def wait_for(condition, timeout=3.0, step=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(step)
    return condition()


# ---- подставной транспорт ----------------------------------------------------

class StubTransport:
    """Транспорт в памяти: запоминает отправленное, умеет «замолчать»."""

    def __init__(self, hub):
        self._hub = hub
        self._pongs = []

    def connect(self):
        if self._hub.refuse_connect:
            raise TransportError('подключение отклонено (тест)')
        self._hub.connect_count += 1

    def send_text(self, text):
        if self._hub.broken:
            raise TransportError('обрыв (тест)')
        with self._hub.lock:
            self._hub.sent.append(json.loads(text))

    def send_ping(self, payload=b''):
        if self._hub.answer_pings:
            self._pongs.append(payload)

    def poll(self, timeout):
        if self._pongs:
            return 'pong', self._pongs.pop(0)
        time.sleep(min(timeout, 0.005))
        return None

    def close(self):
        self._hub.close_count += 1


class StubHub:
    def __init__(self):
        self.lock = threading.Lock()
        self.sent = []
        self.connect_count = 0
        self.close_count = 0
        self.refuse_connect = False
        self.answer_pings = True
        self.broken = False

    def drives(self):
        with self.lock:
            return [m for m in self.sent if 'x' in m]

    def last_drive(self):
        drives = self.drives()
        return drives[-1] if drives else None


@pytest.fixture
def stub():
    hub = StubHub()
    cfg = LinkConfig(send_rate=100.0, command_timeout=0.15, ping_interval=0.05,
                     pong_timeout=0.25, reconnect_delay_min=0.02, reconnect_delay_max=0.05)
    link = Esp32Link(cfg, transport_factory=lambda: StubTransport(hub))
    link.start()
    yield hub, link
    link.stop()


def test_sends_zero_when_no_command(stub):
    hub, link = stub
    assert wait_for(lambda: len(hub.drives()) > 5)
    assert all(m == {'x': 0, 'y': 0} for m in hub.drives())
    assert link.stats().command_stale


def test_fresh_command_is_forwarded(stub):
    hub, link = stub
    link.set_tracks(1.0, 1.0)
    assert wait_for(lambda: hub.last_drive() == {'x': 0, 'y': 255})


def test_stale_command_is_replaced_by_stop(stub):
    hub, link = stub
    link.set_tracks(1.0, 1.0)
    assert wait_for(lambda: hub.last_drive() == {'x': 0, 'y': 255})
    # Команды от ROS прекратились — через command_timeout должен пойти ноль.
    assert wait_for(lambda: hub.last_drive() == {'x': 0, 'y': 0}, timeout=1.0)


def test_estop_overrides_command(stub):
    hub, link = stub
    link.set_tracks(1.0, 1.0)
    assert wait_for(lambda: hub.last_drive() == {'x': 0, 'y': 255})
    link.set_estop(True)
    assert wait_for(lambda: hub.last_drive() == {'x': 0, 'y': 0}, timeout=0.5)
    link.set_tracks(1.0, 1.0)          # при активном останове команда не проходит
    time.sleep(0.1)
    assert hub.last_drive() == {'x': 0, 'y': 0}
    link.set_estop(False)
    link.set_tracks(1.0, 1.0)
    assert wait_for(lambda: hub.last_drive() == {'x': 0, 'y': 255})


def test_silent_peer_is_detected_and_reconnected(stub):
    hub, link = stub
    assert wait_for(lambda: link.connected)
    hub.answer_pings = False           # ESP32 «зависла» / вышла из зоны Wi-Fi
    assert wait_for(lambda: hub.close_count >= 1, timeout=2.0)
    hub.answer_pings = True
    assert wait_for(lambda: link.connected and link.stats().connects >= 2, timeout=2.0)


def test_send_failure_triggers_reconnect(stub):
    hub, link = stub
    assert wait_for(lambda: link.connected)
    hub.broken = True
    assert wait_for(lambda: hub.close_count >= 1)
    hub.broken = False
    assert wait_for(lambda: link.connected and hub.connect_count >= 2, timeout=2.0)


def test_connect_failure_is_retried(stub):
    hub, link = stub
    assert wait_for(lambda: link.connected)
    hub.refuse_connect = True
    hub.broken = True
    assert wait_for(lambda: not link.connected)
    assert link.stats().last_error
    hub.broken = False
    hub.refuse_connect = False
    assert wait_for(lambda: link.connected, timeout=2.0)


def test_stop_sends_final_zero():
    hub = StubHub()
    link = Esp32Link(LinkConfig(send_rate=50.0), transport_factory=lambda: StubTransport(hub))
    link.start()
    link.set_tracks(1.0, 1.0)
    assert wait_for(lambda: hub.last_drive() == {'x': 0, 'y': 255})
    link.stop()
    assert hub.last_drive() == {'x': 0, 'y': 0}
    assert hub.close_count == 1


@pytest.mark.parametrize('bad', [
    dict(send_rate=0.0),
    dict(command_timeout=0.0),
    dict(pwm_max=300),
    dict(ping_interval=1.0, pong_timeout=0.5),
])
def test_invalid_config_is_rejected(bad):
    with pytest.raises(ValueError):
        Esp32Link(LinkConfig(**bad))


# ---- настоящий WebSocket против эмулятора прошивки ---------------------------

@pytest.fixture
def fake():
    server = FakeEsp32(command_timeout=3.0).start()
    yield server
    server.stop()


def make_link(fake_server, **overrides):
    params = dict(host='127.0.0.1', port=fake_server.port, send_rate=50.0,
                  command_timeout=0.3, ping_interval=0.1, pong_timeout=0.6,
                  reconnect_delay_min=0.05, reconnect_delay_max=0.2)
    params.update(overrides)
    return Esp32Link(LinkConfig(**params))


def test_websocket_forward_back_turn_stop(fake):
    link = make_link(fake)
    link.start()
    try:
        assert wait_for(lambda: link.connected)

        def drive(left, right, expected):
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and fake.motors != expected:
                link.set_tracks(left, right)       # как узел управления: команда 20+ Гц
                time.sleep(0.02)
            assert fake.motors == expected

        drive(0.5, 0.5, (128, 128))        # вперёд
        drive(-0.5, -0.5, (-128, -128))    # назад
        drive(-0.5, 0.5, (-128, 128))      # разворот влево
        drive(0.5, -0.5, (128, -128))      # разворот вправо
        drive(0.0, 0.0, (0, 0))            # стоп
    finally:
        link.stop()


def test_websocket_ping_pong_measures_rtt(fake):
    link = make_link(fake)
    link.start()
    try:
        assert wait_for(lambda: link.stats().last_rtt_ms is not None)
        assert link.stats().last_rtt_ms < 500.0
    finally:
        link.stop()


def test_websocket_bridge_watchdog_beats_firmware_timeout(fake):
    """Мост обнуляет команду раньше, чем сработает 3-секундный таймаут прошивки."""
    link = make_link(fake)
    link.start()
    try:
        link.set_tracks(1.0, 1.0)
        assert wait_for(lambda: fake.motors == (255, 255))
        started = time.monotonic()
        assert wait_for(lambda: fake.motors == (0, 0), timeout=1.5)
        assert time.monotonic() - started < 1.0
        assert fake.timeouts == 0          # остановил мост, а не прошивка
    finally:
        link.stop()


def test_websocket_reconnects_after_esp32_restart(fake):
    link = make_link(fake)
    link.start()
    try:
        assert wait_for(lambda: link.connected)
        fake.drop_clients()
        assert wait_for(lambda: link.stats().connects >= 2, timeout=3.0)
        link.set_tracks(1.0, 1.0)
        assert wait_for(lambda: fake.motors == (255, 255))
    finally:
        link.stop()


def test_websocket_shutdown_stops_motors(fake):
    link = make_link(fake)
    link.start()
    link.set_tracks(1.0, 1.0)
    assert wait_for(lambda: fake.motors == (255, 255))
    link.stop()
    assert wait_for(lambda: fake.motors == (0, 0), timeout=1.0)
    assert fake.timeouts == 0


def test_websocket_led(fake):
    link = make_link(fake)
    link.start()
    try:
        link.set_led(True)
        assert wait_for(lambda: fake.led == 1)
        link.set_led(False)
        assert wait_for(lambda: fake.led == 0)
    finally:
        link.stop()


def test_websocket_unreachable_host_does_not_crash():
    link = Esp32Link(LinkConfig(host='127.0.0.1', port=9, connect_timeout=0.3,
                                reconnect_delay_min=0.05, reconnect_delay_max=0.1))
    link.start()
    try:
        assert wait_for(lambda: bool(link.stats().last_error), timeout=3.0)
        assert not link.connected
    finally:
        link.stop()


# ---- ручной режим: мост молчит ------------------------------------------------

def test_inactive_link_sends_one_stop_and_goes_silent(stub):
    hub, link = stub
    link.set_tracks(1.0, 1.0)
    assert wait_for(lambda: hub.last_drive() == {'x': 0, 'y': 255})

    link.set_active(False)
    assert wait_for(lambda: hub.last_drive() == {'x': 0, 'y': 0}, timeout=0.5)
    time.sleep(0.05)
    count = len(hub.drives())
    link.set_tracks(1.0, 1.0)              # команды ROS в ручном режиме не уходят
    time.sleep(0.3)
    assert len(hub.drives()) == count
    assert link.connected                  # связь при этом продолжает проверяться
    assert not link.stats().active


def test_reactivated_link_does_not_replay_old_command(stub):
    hub, link = stub
    link.set_tracks(1.0, 1.0)
    assert wait_for(lambda: hub.last_drive() == {'x': 0, 'y': 255})
    link.set_active(False)
    assert wait_for(lambda: hub.last_drive() == {'x': 0, 'y': 0}, timeout=0.5)

    link.set_active(True)
    time.sleep(0.1)
    assert hub.last_drive() == {'x': 0, 'y': 0}     # старая команда забыта
    link.set_tracks(0.5, 0.5)
    assert wait_for(lambda: hub.last_drive() == {'x': 0, 'y': 128})


def test_websocket_manual_mode_leaves_joystick_in_control(fake):
    """В ручном режиме чужие команды (веб-джойстик) мост не перебивает."""
    import websocket
    link = make_link(fake)
    link.start()
    try:
        assert wait_for(lambda: link.connected)
        link.set_active(False)
        time.sleep(0.2)
        phone = websocket.create_connection(
            f'ws://127.0.0.1:{fake.port}/ws', timeout=2.0, http_no_proxy=['*'])
        phone.send('{"x":0,"y":200}')
        assert wait_for(lambda: fake.motors == (200, 200))
        time.sleep(0.5)                     # активный мост давно бы обнулил команду
        assert fake.motors == (200, 200)
        phone.close()
    finally:
        link.stop()

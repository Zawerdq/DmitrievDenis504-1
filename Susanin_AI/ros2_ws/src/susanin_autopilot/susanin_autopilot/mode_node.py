"""Переключатель режимов и страничка оператора (для телефона).

Режимы (топик susanin/mode, std_msgs/String):

* ``manual`` — мост молчит, роботом управляют с веб-джойстика ESP32 (192.168.4.1);
* ``auto``   — мост передаёт команды ROS; автопилот (если запущен) ведёт робота.

Страничка: http://<адрес Pi>:8080 — кнопки AUTO / MANUAL / СТОП, состояние связи и
автопилота, картинка с камеры с разметкой алгоритма. Работает без интернета и
без сторонних библиотек.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Bool, String

MODES = ('manual', 'auto')

LATCHED_QOS = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL)

PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>Сусанин ИИ</title>
<style>
body{background:#121212;color:#fff;font-family:sans-serif;margin:0;padding:12px;text-align:center}
button{width:100%;padding:22px;margin:6px 0;font-size:22px;font-weight:bold;border:0;
border-radius:14px;color:#fff}
#auto{background:#2e7d32}#manual{background:#1565c0}#stop{background:#c62828}
#clear{background:#444;font-size:16px;padding:12px}
.on{outline:4px solid #fff}
#info{font-size:17px;line-height:1.6;margin:8px 0}
img{width:100%;max-width:480px;border-radius:8px;background:#000}
a{color:#bb86fc}
</style></head><body>
<div id="info">загрузка…</div>
<button id="auto" onclick="post('/mode/auto')">AUTO — автопилот</button>
<button id="manual" onclick="post('/mode/manual')">MANUAL — джойстик</button>
<button id="stop" onclick="post('/estop')">СТОП</button>
<button id="clear" onclick="post('/estop/clear')">снять СТОП</button>
<p><a href="http://192.168.4.1/" target="joystick">открыть джойстик ESP32</a></p>
<div id="camwarn" style="color:#ff5252;font-weight:bold;display:none">нет свежего изображения с камеры</div>
<img id="cam" alt="нет картинки с камеры">
<script>
function post(path){fetch(path,{method:'POST'}).then(refresh);}
function refresh(){fetch('/status').then(r=>r.json()).then(s=>{
 document.getElementById('info').innerHTML=
  'Режим: <b>'+s.mode.toUpperCase()+'</b>'+(s.estop?' — <b style="color:#ff5252">СТОП</b>':'')+
  '<br>ESP32: '+(s.esp32?'есть связь':'<b style="color:#ff5252">нет связи</b>')+
  '<br>Автопилот: '+(s.autopilot||'не запущен');
 document.getElementById('auto').className=s.mode=='auto'?'on':'';
 document.getElementById('manual').className=s.mode=='manual'?'on':'';
 var old=(s.frame_age===null||s.frame_age>3);
 document.getElementById('camwarn').style.display=(old&&s.autopilot)?'block':'none';
 document.getElementById('cam').style.opacity=old?0.3:1;
}).catch(()=>{document.getElementById('info').innerHTML='<b style="color:#ff5252">нет связи с Pi</b>';});}
setInterval(refresh,500);refresh();
setInterval(()=>{document.getElementById('cam').src='/frame.jpg?'+Date.now();},700);
</script></body></html>
"""


class ModeNode(Node):

    def __init__(self) -> None:
        super().__init__('susanin_mode')
        mode = str(self.declare_parameter('initial_mode', 'auto').value).lower()
        if mode not in MODES:
            raise ValueError(f'initial_mode должен быть одним из {MODES}')
        port = int(self.declare_parameter('http_port', 8080).value)

        self._lock = threading.Lock()
        self._mode = mode
        self._estop_button = False   # останов, нажатый на страничке: повторяем его сами
        self._estop_seen = False     # последнее значение топика susanin/e_stop (от кого угодно)
        self._esp32 = False
        self._autopilot = ''
        self._autopilot_time = 0.0
        self._frame = b''
        self._frame_time = 0.0

        self._mode_pub = self.create_publisher(String, 'susanin/mode', LATCHED_QOS)
        self._estop_pub = self.create_publisher(Bool, 'susanin/e_stop', 10)
        self.create_subscription(Bool, 'susanin/esp32/connected', self._on_link, LATCHED_QOS)
        self.create_subscription(Bool, 'susanin/e_stop', self._on_estop, 10)
        self.create_subscription(String, 'susanin/autopilot/state', self._on_autopilot, 10)
        self.create_subscription(
            CompressedImage, 'susanin/autopilot/debug/compressed', self._on_frame, 2)
        # Режим и останов повторяются: узел, запущенный позже, не пропустит их.
        self.create_timer(0.5, self._publish)

        self._server = None
        if port > 0:
            self._server = ThreadingHTTPServer(('0.0.0.0', port), self._make_handler())
            threading.Thread(target=self._server.serve_forever, name='mode-http',
                             daemon=True).start()
        self._publish()
        self.get_logger().info(
            f'Режим «{mode}». Страничка оператора: http://<адрес Pi>:{port}/')

    # ---- ROS ---------------------------------------------------------------

    def _publish(self) -> None:
        with self._lock:
            mode, estop = self._mode, self._estop_button
        self._mode_pub.publish(String(data=mode))
        # Повторяется только останов, нажатый здесь. Чужой останов не повторяем:
        # иначе собственное «эхо» могло бы защёлкнуть его уже после снятия.
        if estop:
            self._estop_pub.publish(Bool(data=True))

    def _on_link(self, msg: Bool) -> None:
        with self._lock:
            self._esp32 = bool(msg.data)

    def _on_estop(self, msg: Bool) -> None:
        with self._lock:
            self._estop_seen = bool(msg.data)
            if self._estop_seen and self._mode == 'auto':
                self._mode = 'manual'      # после любого останова автопилот сам не продолжит

    def _on_autopilot(self, msg: String) -> None:
        with self._lock:
            self._autopilot = msg.data
            self._autopilot_time = time.monotonic()

    def _on_frame(self, msg: CompressedImage) -> None:
        with self._lock:
            self._frame = bytes(msg.data)
            self._frame_time = time.monotonic()

    # ---- действия оператора (вызываются из потока HTTP) ----------------------

    def set_mode(self, mode: str) -> None:
        with self._lock:
            changed = mode != self._mode
            self._mode = mode
        if changed:
            self.get_logger().warning(f'Оператор включил режим «{mode}»')
        self._mode_pub.publish(String(data=mode))

    def set_estop(self, active: bool) -> None:
        with self._lock:
            self._estop_button = active
            self._estop_seen = active
            if active:
                self._mode = 'manual'      # после СТОП автопилот сам не продолжит
        self.get_logger().warning('Оператор нажал СТОП' if active else 'Оператор снял СТОП')
        self._estop_pub.publish(Bool(data=active))
        self._publish()

    def status(self) -> dict:
        with self._lock:
            alive = (time.monotonic() - self._autopilot_time) < 2.0
            return {'mode': self._mode, 'estop': self._estop_button or self._estop_seen,
                    'esp32': self._esp32,
                    # возраст последней картинки от автопилота, с (None — картинок не было)
                    'frame_age': (round(time.monotonic() - self._frame_time, 1)
                                  if self._frame_time else None),
                    'autopilot': self._autopilot if alive else ''}

    def frame(self) -> bytes:
        with self._lock:
            return self._frame

    # ---- HTTP --------------------------------------------------------------

    def _make_handler(self):
        node = self

        class Handler(BaseHTTPRequestHandler):

            def _send(self, code: int, content_type: str, body: bytes) -> None:
                self.send_response(code)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                path = self.path.split('?')[0]
                if path == '/':
                    self._send(200, 'text/html; charset=utf-8', PAGE.encode('utf-8'))
                elif path == '/status':
                    self._send(200, 'application/json', json.dumps(node.status()).encode())
                elif path == '/frame.jpg':
                    data = node.frame()
                    self._send(200 if data else 404, 'image/jpeg', data)
                else:
                    self._send(404, 'text/plain', b'not found')

            def do_POST(self) -> None:  # noqa: N802
                path = self.path.split('?')[0]
                if path in ('/mode/auto', '/mode/manual'):
                    node.set_mode(path.rsplit('/', 1)[1])
                elif path == '/estop':
                    node.set_estop(True)
                elif path == '/estop/clear':
                    node.set_estop(False)
                else:
                    self._send(404, 'text/plain', b'not found')
                    return
                self._send(200, 'application/json', json.dumps(node.status()).encode())

            def log_message(self, *args) -> None:   # не засорять журнал запросами
                del args

        return Handler

    def destroy_node(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ModeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

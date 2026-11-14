"""Автопилот: наблюдение зрения -> команда скорости. Без ROS и без OpenCV.

Порядок трассы известен заранее, поэтому автопилот идёт по шагам и на каждом
ждёт только ОДНО следующее событие из списка ``route``:

    по полосе -> [туннель: прямо] -> по полосе -> [шар: прямо] -> по полосе -> [финиш]

Правила безопасности:

* нет полосы дольше ``lost_timeout`` — стоп, состояние LOST (нужен оператор);
* нет свежих кадров дольше ``frame_timeout`` — стоп;
* туннель не кончился за ``tunnel_max_time`` — стоп;
* заезд длится дольше ``max_run_time`` — стоп.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

IDLE = 'idle'            # автопилот выключен
FOLLOW = 'follow'        # едем по полосе
TUNNEL = 'tunnel'        # проезд туннеля прямо
BALLOON = 'balloon'      # проезд сквозь шар прямо
FINISHING = 'finishing'  # увидели финиш, доезжаем
FINISHED = 'finished'    # приехали, стоим
LOST = 'lost'            # остановились, ждём оператора

EVENTS = ('tunnel', 'balloon', 'finish')


@dataclass
class AutopilotConfig:
    # Движение по полосе
    cruise_speed: float = 0.12       # м/с
    min_speed: float = 0.06          # м/с, скорость в крутом повороте
    steer_gain: float = 1.2          # рад/с на единицу смещения полосы
    steer_far_gain: float = 0.4      # рад/с на единицу «ухода» полосы вдали
    max_angular: float = 1.0         # рад/с
    slow_on_turn: float = 0.6        # насколько снижать скорость при |смещении| = 1
    straight_trim: float = 0.0       # рад/с, поправка увода на прямых (калибровка)

    # Безопасность
    lost_timeout: float = 0.6        # с без полосы до остановки
    frame_timeout: float = 0.4       # с без свежего кадра до остановки
    max_run_time: float = 180.0      # с, предельная длительность заезда

    # Ожидаемые события по порядку трассы; пустой список — только езда по полосе
    route: List[str] = field(default_factory=lambda: ['tunnel', 'balloon', 'finish'])

    # Туннель
    tunnel_approach_fraction: float = 0.15  # с этой доли тёмного целимся в проём
    tunnel_enter_fraction: float = 0.45     # с этой — считаем, что въехали
    tunnel_exit_fraction: float = 0.15
    tunnel_speed: float = 0.12
    tunnel_min_time: float = 0.8
    tunnel_max_time: float = 8.0

    # Шар
    balloon_fraction: float = 0.20
    balloon_speed: float = 0.12
    balloon_time: float = 3.0

    # Финиш
    finish_fraction: float = 0.08
    finish_delay: float = 0.5         # с, сколько ещё ехать после обнаружения метки
    finish_on_track_end: bool = True  # нет метки: конец полосы после последнего события = финиш

    def validate(self) -> None:
        for name in ('cruise_speed', 'min_speed', 'steer_gain', 'max_angular', 'lost_timeout',
                     'frame_timeout', 'max_run_time', 'tunnel_speed', 'tunnel_max_time',
                     'balloon_speed', 'balloon_time'):
            if getattr(self, name) <= 0.0:
                raise ValueError(f'{name} должен быть > 0')
        if self.min_speed > self.cruise_speed:
            raise ValueError('min_speed не может быть больше cruise_speed')
        if not 0.0 <= self.slow_on_turn <= 1.0:
            raise ValueError('slow_on_turn должен быть в [0, 1]')
        if self.tunnel_min_time >= self.tunnel_max_time:
            raise ValueError('tunnel_min_time должен быть меньше tunnel_max_time')
        unknown = [event for event in self.route if event not in EVENTS]
        if unknown:
            raise ValueError(f'неизвестные события в route: {unknown}; допустимы {EVENTS}')


@dataclass
class Command:
    linear: float = 0.0
    angular: float = 0.0
    state: str = IDLE
    reason: str = ''

    @property
    def active(self) -> bool:
        """Нужно ли публиковать команду (IDLE — автопилот выключен, молчим)."""
        return self.state != IDLE


def _clamp(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


class Autopilot:

    def __init__(self, cfg: Optional[AutopilotConfig] = None):
        self.cfg = cfg or AutopilotConfig()
        self.cfg.validate()
        self.state = IDLE
        self.reason = ''
        self._route: List[str] = []
        self._run_start = 0.0
        self._state_start = 0.0
        self._last_seen = 0.0
        self._last_frame: Optional[float] = None

    # ---- управление --------------------------------------------------------

    def start(self, now: float) -> None:
        """Начать заезд с первого шага маршрута."""
        self._route = list(self.cfg.route)
        self._run_start = now
        self._last_seen = now
        self._last_frame = None
        self._enter(FOLLOW, now, 'start')

    def stop(self, reason: str = 'stopped') -> None:
        self.state = IDLE
        self.reason = reason

    @property
    def next_event(self) -> Optional[str]:
        return self._route[0] if self._route else None

    def _enter(self, state: str, now: float, reason: str = '') -> None:
        self.state = state
        self.reason = reason
        self._state_start = now

    def _command(self, linear: float = 0.0, angular: float = 0.0) -> Command:
        return Command(linear, angular, self.state, self.reason)

    # ---- шаг ---------------------------------------------------------------

    def update(self, obs, now: float) -> Command:
        """Обработать наблюдение (или None, если свежего кадра нет)."""
        if self.state in (IDLE, FINISHED, LOST):
            return self._command()

        if (now - self._run_start) > self.cfg.max_run_time:
            self._enter(LOST, now, 'max_run_time')
            return self._command()

        if obs is None:
            reference = self._last_frame if self._last_frame is not None else self._run_start
            if (now - reference) > self.cfg.frame_timeout:
                self._enter(LOST, now, 'no_frames')
            return self._command()        # без кадра не едем даже до истечения таймаута
        self._last_frame = now

        if self.state == TUNNEL:
            return self._tunnel(obs, now)
        if self.state == BALLOON:
            return self._balloon(now)
        if self.state == FINISHING:
            if (now - self._state_start) >= self.cfg.finish_delay:
                self._enter(FINISHED, now, 'finish_marker')
                return self._command()
            return self._steer(obs, now)
        return self._follow(obs, now)

    def _follow(self, obs, now: float) -> Command:
        cfg = self.cfg
        event = self.next_event
        if event == 'tunnel' and obs.dark_fraction >= cfg.tunnel_enter_fraction:
            self._route.pop(0)
            self._enter(TUNNEL, now, 'tunnel_entered')
            return self._tunnel(obs, now)
        if event == 'balloon' and obs.balloon_fraction >= cfg.balloon_fraction:
            self._route.pop(0)
            self._enter(BALLOON, now, 'balloon_seen')
            return self._balloon(now)
        if event == 'finish' and obs.finish_fraction >= cfg.finish_fraction:
            self._route.pop(0)
            self._enter(FINISHING, now, 'finish_seen')
        return self._steer(obs, now)

    def _steer(self, obs, now: float) -> Command:
        cfg = self.cfg
        if not obs.track_found:
            if (now - self._last_seen) > cfg.lost_timeout:
                if self.state == FINISHING or (
                        cfg.finish_on_track_end and self.next_event == 'finish'):
                    self._enter(FINISHED, now, 'track_end')
                else:
                    self._enter(LOST, now, 'track_lost')
            return self._command()        # полосы не видно — стоим, не едем вслепую
        self._last_seen = now

        offset = obs.offset
        if (self.next_event == 'tunnel'
                and obs.dark_fraction >= cfg.tunnel_approach_fraction):
            # На подъезде к туннелю целимся в середину проёма: внутри рулить не будем.
            offset = 0.5 * offset + 0.5 * obs.dark_offset
        angular = _clamp(
            -(cfg.steer_gain * offset + cfg.steer_far_gain * obs.far_offset), cfg.max_angular)
        linear = max(cfg.min_speed,
                     cfg.cruise_speed * (1.0 - cfg.slow_on_turn * min(1.0, abs(offset))))
        return self._command(linear, angular + cfg.straight_trim)

    def _tunnel(self, obs, now: float) -> Command:
        cfg = self.cfg
        elapsed = now - self._state_start
        if (elapsed >= cfg.tunnel_min_time and obs.track_found
                and obs.dark_fraction < cfg.tunnel_exit_fraction):
            self._last_seen = now
            self._enter(FOLLOW, now, 'tunnel_passed')
            return self._steer(obs, now)
        if elapsed > cfg.tunnel_max_time:
            self._enter(LOST, now, 'tunnel_timeout')
            return self._command()
        return self._command(cfg.tunnel_speed, cfg.straight_trim)

    def _balloon(self, now: float) -> Command:
        cfg = self.cfg
        if (now - self._state_start) >= cfg.balloon_time:
            self._last_seen = now
            self._enter(FOLLOW, now, 'balloon_passed')
            return self._command(cfg.min_speed, cfg.straight_trim)
        return self._command(cfg.balloon_speed, cfg.straight_trim)

import itertools as it
import logging
import signal
import threading
import time
import typing

import pynput

logging.basicConfig(level=logging.INFO)

class EventProducer:
    def __init__(self,
                 event_cond: threading.Condition,
                 event: threading.Event):
        self._event_cond = event_cond
        self._event = event

    def notify(self):
        with self._event_cond:
            self._event.set()
            self._event_cond.notify_all()


class Timer(EventProducer, threading.Thread):
    def __init__(self,
                 event_cond: threading.Condition,
                 event: threading.Event,
                 duration: int,
                 tick_time: int = 1):
        EventProducer.__init__(self, event_cond, event)
        threading.Thread.__init__(self, daemon=True)
        self.planned_duration = duration
        self.tick_time = tick_time
        self._start_time = None
        self._current_time = None
        self._running = True
        self._logger = logging.getLogger('Timer')

    def run(self) -> None:
        self._logger.info('Start %s. Duration: %s',
                          self.native_id, self.planned_duration)
        self._start_time = time.time()

        while self._running:
            self._current_time = time.time()

            if self._current_time >= self._start_time + self.planned_duration:
                self.notify()

            time.sleep(self.tick_time)
            self._logger.debug('Tick %s', self.native_id)

    def stop(self) -> float:
        self._running = False
        self._logger.info('Stop %s. Fact Duration %s',
                          self.native_id, self.duration)
        return self.duration

    @property
    def duration(self):
        return self._current_time - self._start_time


class MovingListener(EventProducer):
    def __init__(self,
                 event_cond: threading.Condition,
                 event: threading.Event):
        super().__init__(event_cond, event)
        self._event_cond = event_cond
        self._event = event
        self._keyboard_listener = pynput.keyboard.Listener(
            on_press=self._handle_keyboard_event
        )
        self._mouse_listener = pynput.mouse.Listener(
            on_move=self._handle_mouse_event
        )

    def start(self):
        self._keyboard_listener.start()
        self._mouse_listener.start()

    def stop(self):
        self._keyboard_listener.stop()
        self._mouse_listener.stop()

    def _handle_keyboard_event(self, key):
        self.notify()

    def _handle_mouse_event(self, x, y):
        self.notify()


class Stage:
    WORK = 'work'
    RELAX = 'relax'
    STOP = 'stop'

    def __init__(self, name, duration):
        self.name = name
        self.duration = duration

    @classmethod
    def stop(cls):
        return cls(cls.STOP, None)

    @classmethod
    def work(cls, duration):
        return cls(cls.WORK, duration)

    @classmethod
    def relax(cls, duration):
        return cls(cls.RELAX, duration)

    def __repr__(self):
        return f'Stage(name={self.name}, duration={self.duration})'


class Stats:
    def __init__(self):
        self._logger = logging.getLogger('Stats')

    def event(self, stage: Stage, duration: float):
        self._logger.info(f'Event: %s, fact: %s', stage, duration)


class App(threading.Thread):
    schedule = [Stage.work(10), Stage.relax(10)]

    def __init__(self, stats):
        super().__init__()
        self._running = True
        self._stage = Stage.stop()
        self._schedule_iter = it.cycle(self.schedule)
        self._stats = stats
        self._timer = None
        self._event_cond = threading.Condition()
        self._timer_event = threading.Event()
        self._moving_event = threading.Event()
        
        self._logger = logging.getLogger('App')

    def run(self):
        self._start_timer(next(self._schedule_iter))

        def has_event():
            return self._timer_event.is_set() or self._moving_event.is_set()

        while self._running:
            with self._event_cond:
                self._event_cond.wait_for(has_event)
                
                if self._moving_event.is_set():
                    self._handle_movement()
                    self._moving_event.clear()
                    
                if self._timer_event.is_set():
                    self._timer_event.clear()
                    self._handle_alarm()
                
    def _handle_movement(self):
        if self._stage.name == Stage.RELAX:
            self._logger.info('Movement in RELAX stage')
            self.next_stage()
            # TODO: after moving to next stage (WORK) the main thread stopped
        elif self._stage.name == Stage.WORK:
            self._logger.info('Movement in WORK stage')

    def _handle_alarm(self):
        # TODO: if in relax stage wait for movements
        #       if in work stage wait until movements stop
        self.next_stage()
        
    def next_stage(self):
        self._stop_timer()
        self._start_timer(next(self._schedule_iter))

    def _stop_timer(self):
        if self._timer:
            fact_duration = self._timer.stop()
            self._stats.event(self._stage, fact_duration)

    def _start_timer(self, stage: Stage):
        self._logger.info('Starting stage: %s', stage)
        self._stage = stage
        self._timer = Timer(self._event_cond,
                            self._timer_event,
                            self._stage.duration)
        self._timer.start()

    def stop(self) -> float:
        self._stop_timer()
        self._running = False
        self._logger.info('Stop.')


if __name__ == '__main__':
    app = App(Stats())
    moving_listener = MovingListener(app._event_cond, app._moving_event)
    moving_listener.start()

    def _stop(sig, frame):
        app.stop()
        moving_listener.stop()
    signal.signal(signal.SIGINT, _stop)
    
    app.start()

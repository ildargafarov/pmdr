import itertools as it
import logging
import threading
import time
import signal

import pynput

logging.basicConfig(level=logging.DEBUG)


class Alarm(threading.Thread):
    def __init__(self, on_alarm, duration):
        super().__init__()
        self.duration = duration
        self._on_alarm = on_alarm
        self._start_time = None
        self._current_time = None
        self._running = True

    def run(self) -> None:
        logging.info('Starting alarm: %s duration: %s', self.native_id, self.duration)
        self._start_time = time.time()
        while self._running:
            self._current_time = time.time()
            if self._current_time >= self._start_time + self.duration:
                self._on_alarm(self._current_time - self._start_time)
            time.sleep(1)
            logging.debug('Tick %s',  self.native_id)

    def stop(self) -> float:
        self._running = False
        duration = self._current_time - self._start_time
        logging.info('Alarm %s stopped. Duration %s', self.native_id, duration)
        return duration


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
    def event(self, stage: Stage, duration: float):
        logging.info(f'Event: %s, fact: %s', stage, duration)


class App:
    schedule = [Stage.work(10), Stage.relax(10)]

    def __init__(self, stats):
        super().__init__()
        self._stage = Stage.stop()
        self._schedule_iter = it.cycle(self.schedule)
        self._stats = stats
        self._alarm = None

    def handle_movement(self):
        # if self._stage.name == Stage.RELAX:
        #     self.next_stage()
        pass

    def handle_alarm(self, duration):
        # TODO: if in relax stage wait for movements
        #       if in work stage wait until movements stop
        self.next_stage()

    def start(self):
        self._wait_stage(next(self._schedule_iter))

    def stop(self):
        if self._alarm:
            fact_duration = self._alarm.stop()
            self._stats.event(self._stage, fact_duration)

    def next_stage(self):
        self.stop()
        self._wait_stage(next(self._schedule_iter))

    def _wait_stage(self, stage: Stage):
        logging.info('Starting stage: %s', self._stage)
        self._stage = stage
        self._alarm = Alarm(self.handle_alarm, self._stage.duration)
        self._alarm.start()
        self._alarm.join()


def handle_keyboard_event(key):
    print(f'{key} pressed')


def handle_mouse_event(x, y):
    print('Mouse moved')


keyboard_listener = pynput.keyboard.Listener(
    on_press=handle_keyboard_event
)

mouse_listener = pynput.mouse.Listener(
    on_move=handle_mouse_event
)

if __name__ == '__main__':
    # keyboard_listener.start()
    # mouse_listener.start()
    #
    # keyboard_listener.join()
    # mouse_listener.join()

    app = App(Stats())

    def _stop(sig, frame):
        app.stop()

    signal.signal(signal.SIGINT, _stop)

    app.start()

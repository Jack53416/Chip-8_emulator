import threading
import time


def timeit(method):
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if 'log_time' in kw:
            name = kw.get('log_name', method.__name__.upper())
            kw['log_time'][name] = int((te - ts) * 1000)
        else:
            print('%r  %2.2f ms' % \
                  (method.__name__, (te - ts) * 1000))
        return result
    return timed


class HwTimer(threading.Thread):

    def __init__(self, bits: int = 8, freq: int = 60):
        self._bitCount = bits
        self._value = 0
        self._freq = freq
        self._delay = 1 / self._freq
        super().__init__()

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, value: int):
        base = 1 << self._bitCount
        self._value = value % base

    def _tick(self):
        if self._value > 0:
            self._value -= 1

    def abort(self):
        self._value = 0

    def run(self) -> None:

        while self._value > 0:
            time.sleep(self._delay)
            self._tick()


@timeit
def timer_process(hw_timer: HwTimer):
    hw_timer.start()
    hw_timer.join()


if __name__ == "__main__":
    timer = HwTimer(8, 60)
    timer.value = 240
    timer_process(timer)
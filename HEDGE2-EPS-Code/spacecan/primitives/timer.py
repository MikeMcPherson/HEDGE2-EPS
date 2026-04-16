import pyb


class Timer:
    def __init__(self, period, callback, timer_id):
        self._period = period
        self._callback = callback
        self._timer_id = timer_id
        self._running = False
        self._timer = None

    def start(self):
        if self._running:
            self.stop()
        self._running = True
        self._timer = pyb.Timer(self._timer_id)
        self._timer.init(freq=(1 / self._period), callback=self._expired)

    def stop(self):
        self._running = False
        if self._timer:
            self._timer.deinit()

    def _expired(self, timer):
        self._callback()

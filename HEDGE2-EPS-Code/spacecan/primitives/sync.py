"""
The Sync service allows sending sync frames, either manually or
periodically. The Sync service is typically used by the network controller
node to allow responder nodes synchronize their behaviour upon receiving
this event.

"""

from .can_frame import CanFrame, ID_SYNC
from .timer import Timer


TIMER_ID = 2


class SyncProducer:
    def __init__(self, parent):
        self.parent = parent
        self._running = False
        self._timer = None
        self._period = None
        self._can_frame = CanFrame(can_id=ID_SYNC)

    def _send(self):
        self.parent.network.send(self._can_frame)

    def start(self, period):
        self._period = period
        if self._running:
            self.stop()
        self._running = True
        self._send()

        self._timer = Timer(self._period, self._send, TIMER_ID)
        self._timer.start()

    def stop(self):
        self._running = False
        if self._timer:
            self._timer.stop()
            self._timer = None

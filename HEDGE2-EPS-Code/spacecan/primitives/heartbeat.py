"""
The Heartbeat service is needed for the redundancy management, to let the
controller node define the active bus (either nominal or redundant one) for
communication and to let the responder nodes know which is the active bus to
listen to. For this, controller node implements the HeartbeatProducer class
while responder nodes implement the HeartbeatConsumer class.

"""

from .can_frame import CanFrame, ID_HEARTBEAT
from .timer import Timer


TIMER_ID = 1


class HeartbeatProducer:
    def __init__(self, parent):
        self.parent = parent
        self._running = False
        self._timer = None
        self._period = None
        self._can_frame = CanFrame(can_id=ID_HEARTBEAT)

    def _send(self):
        self.parent.network.send(self._can_frame)
        self.parent.sent_heartbeat()

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


class HeartbeatConsumer:
    def __init__(self, parent):
        self.parent = parent
        self._running = False
        self._timer = None

    def start(self, period, max_miss_heartbeat=None, max_bus_switch=None):
        self._period = period
        self._max_miss_heartbeat = max_miss_heartbeat
        self._max_bus_switch = max_bus_switch
        self._heartbeats_missed = 0
        self._bus_switches = 0
        self._running = True

        # schedule the timer expiration
        self._timer = Timer(self._period, self._timer_expired, TIMER_ID)
        self._timer.start()

    def stop(self):
        self._running = False
        if self._timer:
            self._timer.stop()
            self._timer = None

    def _timer_expired(self):
        self._heartbeats_missed += 1

        if (
            self._max_miss_heartbeat is not None
            and self._heartbeats_missed > self._max_miss_heartbeat
        ):
            if (
                self._max_bus_switch is None
                or self._bus_switches < self._max_bus_switch
            ):
                self._heartbeats_missed = 0
                self._bus_switches += 1
                self.parent.switch_bus()

    def received(self):
        if self._running:
            self._heartbeats_missed = 0
            self._bus_switches = 0

            if self._timer:
                # reschedule the next timer expiration
                self._timer.stop()
                self._timer = Timer(self._period, self._timer_expired, TIMER_ID)
                self._timer.start()

            self.parent.received_heartbeat()

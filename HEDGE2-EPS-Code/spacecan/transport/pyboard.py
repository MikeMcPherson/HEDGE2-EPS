import pyb
import micropython
import time

from .base import Bus
from ..primitives.network import Network
from ..primitives.can_frame import CanFrame


class PyboardCanBus(Bus):
    TOTAL_FILTERBANKS = 14
    FRAME_BUFFER_SIZE = 20

    def __init__(self, parent, channel, bitrate=1000):
        super().__init__(parent)
        self._channel = channel
        self._fifo = channel - 1
        self._null_sink = [0, 0, 0, 0, memoryview(bytearray(8))]
        self._bus = pyb.CAN(
            self._channel,
            mode=pyb.CAN.NORMAL,
            auto_restart=True,
            baudrate=1_000_000,
            sample_point=50,
        )
        self._bus.rxcallback(self._fifo, self._callback)
        self.frame_buffer = FrameBuffer(self.FRAME_BUFFER_SIZE)
        self._running = False

    def disconnect(self):
        self._bus.deinit()

    def set_filters(self, filters):
        """
        Set the filters to define which frames to be received from the bus.
        Only frames with a CAN ID that match one of the filter will be
        received.

        - filters (list of tuples): Filters are provided as a list of tuples
        containing a can_id and a mask:

        >>> [(can_id, mask), (can_id, mask), ...]

        A received frame matches the filter when
        (received_can_id & mask) == (can_id & mask).

        """
        if not isinstance(filters, list):
            raise Exception("filters must be a list of tuples")

        if len(filters) > self.TOTAL_FILTERBANKS:
            raise Exception("too many filters provided")

        bank = 0  # start from bank 0
        params = []
        for filter_tuple in filters:
            params.extend(filter_tuple)
            if len(params) == 4:
                self._bus.setfilter(bank, pyb.CAN.MASK16, self._fifo, params)
                params = []
                bank += 1
        if len(params) > 0:  # lists must have 4 entries
            params = params + [0] * (4 - len(params))
            self._bus.setfilter(bank, pyb.CAN.MASK16, self._fifo, params)

    def send(self, can_frame):
        try:
            self._bus.send(data=can_frame.data, id=can_frame.can_id, timeout=0)
            time.sleep(0.005)
        except OSError:
            pass

    def start_receive(self):
        self._running = True

    def stop_receive(self):
        self._running = False

    def flush_fifo(self):
        while self._bus.any(self._fifo):
            self._bus.recv(self._fifo, list=self._null_sink)

    def flush_frame_buffer(self):
        self.frame_buffer.clear()

    def _callback(self, can, reason):
        """Callback for received frames.

        The method is called when a CAN frame is received on the bus
        that matches the filters defined for the bus. If the bus on which the
        frame was received is not the active bus (of the network) then the
        frame is discarded. Otherwise, a processing of the received frame
        is scheduled to be executed once the callback returns.
        The method raises an exception when the hardware fifo overflows.

        """
        if not self._running:
            self.flush_fifo()
            return
        if self.parent.network.selected_bus == self:
            # go through all received frames
            while self._bus.any(self._fifo):
                # read frame into buffer
                self.frame_buffer.buffer_frame(self)

                # schedule process of each pending frame
                try:
                    micropython.schedule(Network.process, self.parent.network)
                except RuntimeError:
                    print("schedule stack overflow")
            if reason == 1:
                # canbus fifo full, no further frames can be buffered
                print("fifo is full")
            elif reason == 2:
                # should never happen
                print("can message lost due to full fifo")
        else:
            # frame received on inactive bus
            self.flush_fifo()


class FrameBuffer:
    def __init__(self, size):
        """
        A FrameBuffer is used to buffer frames received from the Network
        over the active Bus. The FrameBuffer is designed as a FIFO and is
        useful to overcome the limited storing capability of the pyboard CAN
        controller hardware FIFO.

        """
        self._size = size
        self._data = [[0, 0, 0, 0, memoryview(bytearray(8))] for _ in range(size)]
        self._index_write = 0
        self._index_read = 0

    def buffer_frame(self, bus):
        next_index = (self._index_write + 1) % self._size
        if next_index == self._index_read:
            # in case of overflow, discard the received frame(s)
            bus.flush_fifo()
            print("frame buffer overflow")
        else:
            bus._bus.recv(bus._fifo, list=self._data[self._index_write])
            self._index_write = next_index

    def get(self):
        if self._index_read == self._index_write:
            return None  # buffer is empty
        can_id, _, _, _, data = self._data[self._index_read]
        self._index_read = (self._index_read + 1) % self._size
        return CanFrame(can_id, data)

    def any(self):
        if self._index_read == self._index_write:
            return False
        return True

    def clear(self):
        self._index_write = 0
        self._index_read = 0

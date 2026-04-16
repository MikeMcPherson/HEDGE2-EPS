import math


MAX_DATA_LENGTH = 6


class Packet:
    def __init__(self, data=None):
        if data is None:
            self.data = bytearray()
        else:
            self.data = bytearray(data)

    def __repr__(self):
        return f"Packet({list(self.data)})"

    def split(self):
        # calculate number of frames to send
        total_frames = math.ceil(len(self.data) / MAX_DATA_LENGTH)
        # ensure to also send telecommand with zero data
        total_frames = max(1, total_frames)
        for n in range(total_frames):
            data = bytearray(self.data[n * 6 : n * 6 + 6])
            header = bytearray([total_frames - 1, n])
            yield header + data


class PacketAssembler:
    def __init__(self, parent):
        self.parent = parent
        self.buffer = {}

    def process_frame(self, can_frame):
        can_id = can_frame.can_id
        total_frames = can_frame.data[0] + 1
        n = can_frame.data[1]

        if can_id not in self.buffer:
            self.buffer[can_id] = {}

        self.buffer[can_id][n] = can_frame.data[2:]

        if len(self.buffer[can_id]) == total_frames:
            framebuffer = self.buffer[can_id]
            data = []
            for k in sorted(framebuffer):
                data.extend(framebuffer[k])
            del self.buffer[can_id]
            packet = Packet(data)
            return packet

        return None

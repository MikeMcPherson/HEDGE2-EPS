from ..primitives.packet import Packet


class ServicePacket:
    def __init__(self, service, subtype, data=None):
        self.service = service
        self.subtype = subtype
        self.data = data

    def __repr__(self):
        if self.data:
            return f"ServicePacket({self.service}, {self.subtype}, {self.data.hex()})"
        else:
            return f"ServicePacket({self.service}, {self.subtype})"

    def to_packet(self):
        data = bytearray([self.service, self.subtype])
        if self.data:
            data.extend(bytearray(self.data))
        return Packet(data)

    @classmethod
    def from_packet(cls, packet):
        return cls(
            packet.data[0],
            packet.data[1],
            packet.data[2:] if len(packet.data) > 2 else None,
        )

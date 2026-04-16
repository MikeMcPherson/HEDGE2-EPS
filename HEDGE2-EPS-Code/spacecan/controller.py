import json

from .primitives.network import Network
from .primitives.heartbeat import HeartbeatProducer
from .primitives.sync import SyncProducer
from .primitives.packet import PacketAssembler
from .primitives.can_frame import (
    CanFrame,
    FUNCTION_MASK,
    ID_REP,
    ID_REQ,
    ID_SCET,
    ID_UTC,
    ID_SYNC,
)


class Controller:
    def __init__(
        self,
        interface,
        channel_a,
        channel_b,
        heartbeat_period=None,
        sync_period=None,
        use_packets=None,
    ):
        self.node_id = 0  # controller node id is always 0
        self.interface = interface
        self.channel_a = channel_a
        self.channel_b = channel_b
        self.heartbeat_period = heartbeat_period
        self.sync_period = sync_period
        self.use_packets = use_packets

        self.network = None
        self.heartbeat = HeartbeatProducer(self) if heartbeat_period else None
        self.sync = SyncProducer(self) if self.sync_period else None

        if self.use_packets:
            self.packet_assembler = PacketAssembler(self)
        else:
            self.packet_assembler = None

    @classmethod
    def from_file(cls, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            config = json.load(f)

        if config.get("node_id") is not None:
            if config.get("node_id") != 0:
                raise ValueError("Controller node id must be 0")

        return cls(
            interface=config.get("interface"),
            channel_a=config.get("channel_a"),
            channel_b=config.get("channel_b"),
            heartbeat_period=config.get("heartbeat_period"),
            sync_period=config.get("sync_period"),
            use_packets=config.get("use_packets"),
        )

    def connect(self):
        if self.interface == "pyboard":
            from .transport.pyboard import PyboardCanBus

            bus_a = PyboardCanBus(self, channel=self.channel_a)
            bus_b = PyboardCanBus(self, channel=self.channel_b)
            # receive telemetry from all responder nodes
            filters = [(ID_REQ, FUNCTION_MASK)]
            bus_a.set_filters(filters)
            bus_b.set_filters(filters)
            self.network = Network(self, self.node_id, bus_a, bus_b)
        else:
            raise NotImplementedError

    def disconnect(self):
        self.network.bus_a.disconnect()
        self.network.bus_b.disconnect()

    def start(self):
        self.network.start()
        if self.heartbeat:
            self.heartbeat.start(self.heartbeat_period)
        if self.sync:
            self.sync.start(self.sync_period)

    def stop(self):
        if self.sync:
            self.sync.stop()
        if self.heartbeat:
            self.heartbeat.stop()
        self.network.stop()

    def switch_bus(self):
        self.network.stop()
        if self.network.selected_bus == self.network.bus_a:
            self.network.selected_bus = self.network.bus_b
        elif self.network.selected_bus == self.network.bus_b:
            self.network.selected_bus = self.network.bus_a
        self.network.start()

    def send_scet(self, coarse_time, fine_time=0):
        can_id = ID_SCET
        data = bytearray(
            [
                (fine_time >> 16) & 0xFF,
                (fine_time >> 8) & 0xFF,
                fine_time & 0xFF,
                (coarse_time >> 24) & 0xFF,
                (coarse_time >> 16) & 0xFF,
                (coarse_time >> 8) & 0xFF,
                coarse_time & 0xFF,
            ]
        )
        can_frame = CanFrame(can_id, data)
        self.network.send(can_frame)

    def send_utc(self, day, ms_of_day, sub_ms=0):
        can_id = ID_UTC
        data = bytearray(
            [
                sub_ms >> 8,
                sub_ms & 0xFF,
                ms_of_day >> 24,
                (ms_of_day >> 16) & 0xFF,
                (ms_of_day >> 8) & 0xFF,
                ms_of_day & 0xFF,
                day >> 8,
                day & 0xFF,
            ]
        )
        can_frame = CanFrame(can_id, data)
        self.network.send(can_frame)

    def send_sync(self):
        can_id = ID_SYNC
        can_frame = CanFrame(can_id, bytearray())
        self.network.send(can_frame)

    def send_data(self, data, node_id):
        can_id = ID_REQ + node_id
        can_frame = CanFrame(can_id, data)
        self.network.send(can_frame)

    def send_packet(self, packet, node_id):
        can_id = ID_REQ + node_id
        for data in packet.split():
            can_frame = CanFrame(can_id, data)
            self.network.send(can_frame)

    def received_frame(self, can_frame):
        func_id = can_frame.get_func_id()
        node_id = can_frame.get_node_id()

        # controller should only receive telemetry from other nodes
        if func_id == ID_REP:
            if self.use_packets:
                # feed packet into packet assembler
                packet = self.packet_assembler.process_frame(can_frame)
                if packet:
                    self.received_packet(packet, node_id)
            else:
                self.received_data(can_frame.data, node_id)
        else:
            pass

    def received_data(self, data, node_id):
        # to be implemented by higher layer application
        pass

    def received_packet(self, packet, node_id):
        # to be implemented by higher layer application
        pass

    def sent_heartbeat(self):
        # to be implemented by higher layer application
        pass

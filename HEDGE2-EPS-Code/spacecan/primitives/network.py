class Network:
    """
    The Network class represents the redundant CAN system bus. It is
    initialized with a node ID and two bus objects, of which the nominal
    bus will be the selected bus (until the bus is switched).

    """

    def __init__(self, parent, node_id, bus_a, bus_b):
        self.parent = parent
        self.node_id = node_id
        self.bus_a = bus_a
        self.bus_b = bus_b

        self.selected_bus = self.bus_a

    def start(self):
        self.selected_bus.flush_frame_buffer()
        self.selected_bus.start_receive()

    def stop(self):
        self.selected_bus.flush_frame_buffer()
        self.selected_bus.stop_receive()

    # this method is triggered from bus class
    def process(self):
        can_frame = self.selected_bus.frame_buffer.get()
        if can_frame is None:
            return

        self.parent.received_frame(can_frame)

    def send(self, can_frame):
        self.selected_bus.send(can_frame)

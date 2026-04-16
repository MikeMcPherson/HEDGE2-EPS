class Bus:
    def __init__(self, parent):
        self.parent = parent

    def disconnect(self):
        pass

    def flush_frame_buffer(self):
        raise NotImplementedError

    def set_filters(self, filters):
        raise NotImplementedError

    def send(self, can_frame):
        raise NotImplementedError

    def start_receive(self):
        raise NotImplementedError

    def stop_receive(self):
        raise NotImplementedError

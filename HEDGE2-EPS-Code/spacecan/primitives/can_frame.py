# filter masks
FULL_MASK = 0x7FF  # can frame id is 11 bits
FUNCTION_MASK = 0x780  # 111 1000 0000
NODE_MASK = 0x07F  # 000 0111 1111

# mapping of CANopen COB-IDs
ID_SYNC = 0x080
ID_HEARTBEAT = 0x700
ID_SCET = 0x180
ID_UTC = 0x200
ID_REQ = 0x280
ID_REP = 0x300
ID_MESSAGE = 0x380


class CanFrame:
    def __init__(self, can_id, data=None):
        self.can_id = can_id

        if data is None:
            self.data = bytearray()
        else:
            if len(data) > 8:
                raise ValueError("not more than 8 data bytes allowed")
            self.data = bytearray(data)

    def __len__(self):
        return len(self.data)

    def __repr__(self):
        return f"CanFrame({hex(self.can_id)}, {list(self.data)})"

    def get_node_id(self):
        return self.can_id & NODE_MASK

    def get_func_id(self):
        return self.can_id & FUNCTION_MASK

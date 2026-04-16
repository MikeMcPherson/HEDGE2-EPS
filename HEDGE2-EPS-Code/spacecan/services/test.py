from .service_packet import ServicePacket


class TestServiceController:
    def __init__(self, parent):
        self.parent = parent

    def process(arg):
        self, service, subtype, data, node_id = arg
        case = (service, subtype)

        if case == (17, 2):
            self.received_connection_test_report(node_id)

    def received_connection_test_report(self, node_id):
        # to be implemented by higher layer application
        pass


class TestServiceResponder:
    def __init__(self, parent):
        self.parent = parent

    def process(arg):
        self, service, subtype, data, node_id = arg
        case = (service, subtype)

        if case == (17, 1):  # connection test
            # send success acceptance report
            self.parent.send(ServicePacket(1, 1, [service, subtype]))

            # reply
            self.parent.send(ServicePacket(17, 2))

            # send success completion report
            self.parent.send(ServicePacket(1, 7, [service, subtype]))

        else:
            # send fail acceptance report
            self.parent.send(ServicePacket(1, 2, [service, subtype]))

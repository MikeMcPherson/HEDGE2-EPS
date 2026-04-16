class RequestVerificationServiceController:
    def __init__(self, parent):
        self.parent = parent

    def process(arg):
        self, service, subtype, data, node_id = arg
        case = (service, subtype)

        self.received_report(node_id, case, data)

        if case == (1, 1):
            self.received_success_acceptance_report(node_id, data)
        elif case == (1, 2):
            self.received_fail_acceptance_report(node_id, data)
        elif case == (1, 7):
            self.received_success_completion_report(node_id, data)
        elif case == (1, 8):
            self.received_fail_completion_report(node_id, data)

    def received_report(self, node_id, case, data):
        # to be implemented by higher layer application
        pass

    def received_success_acceptance_report(self, node_id, data):
        # to be implemented by higher layer application
        pass

    def received_fail_acceptance_report(self, node_id, data):
        # to be implemented by higher layer application
        pass

    def received_success_completion_report(self, node_id, data):
        # to be implemented by higher layer application
        pass

    def received_fail_completion_report(self, node_id, source_packet):
        # to be implemented
        pass


class RequestVerificationServiceResponder:
    def __init__(self, parent):
        self.parent = parent

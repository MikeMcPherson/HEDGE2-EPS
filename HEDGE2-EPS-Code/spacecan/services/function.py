import struct
import json

from .service_packet import ServicePacket


class Argument:
    def __init__(self, argument_id, argument_name, encoding, **other):
        self.argument_id = argument_id
        self.argument_name = argument_name
        self.encoding = encoding

    def __repr__(self):
        string = (
            f"Argument({self.argument_id}, '{self.argument_name}', '{self.encoding}')"
        )
        return string

    def encode(self, value):
        encoding = (
            self.encoding if self.encoding.startswith("!") else "!" + self.encoding
        )
        return struct.pack(encoding, value)

    def decode(self, data):
        encoding = (
            self.encoding if self.encoding.startswith("!") else "!" + self.encoding
        )
        return struct.unpack(encoding, data)[0]

    def get_encoded_size(self):
        return struct.calcsize(self.encoding)


class Function:
    def __init__(self, function_id, function_name, arguments=None, **other):
        self.function_id = function_id
        self.function_name = function_name
        self.arguments = {}

        if arguments is not None:
            for kwargs in arguments:
                self.add_argument(Argument(**kwargs))

    def __repr__(self):
        string = (
            f"Function({self.function_id}, '{self.function_name}', '{self.arguments}')"
        )
        return string

    def add_argument(self, argument):
        self.arguments[argument.argument_id] = argument

    def get_argument(self, argument_id):
        return self.arguments.get(argument_id)


class FunctionManagementService:
    def __init__(self, parent):
        self.parent = parent
        self.function_pool = {}

    def get_function(self, function_id):
        return self.function_pool.get(function_id)

    def add_function(self, function):
        self.function_pool[function.function_id] = function


class FunctionManagementServiceController(FunctionManagementService):
    def add_functions_from_file(self, filepath, node_id):
        with open(filepath, "r", encoding="utf-8") as f:
            x = json.load(f)
        list_of_dicts = x["functions"]

        # prepend function_id with node_id
        for y in list_of_dicts:
            y["function_id"] = (node_id, y["function_id"])

        for kwargs in list_of_dicts:
            self.add_function(Function(**kwargs))


class FunctionManagementServiceResponder(FunctionManagementService):
    def add_functions_from_file(self, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            x = json.load(f)
        list_of_dicts = x["functions"]

        for kwargs in list_of_dicts:
            self.add_function(Function(**kwargs))

    def process(arg):
        self, service, subtype, data, node_id = arg
        case = (service, subtype)

        if case == (8, 1):  # perform function
            if data is None:  # need to supply at least a function id
                # send fail acceptance report
                self.parent.send(ServicePacket(1, 2, [service, subtype]))
                return
            function_id = data[0]
            data = data[1:]
            function = self.get_function(function_id)

            if function is None:
                # send fail acceptance report
                self.parent.send(ServicePacket(1, 2, [service, subtype]))
                return

            if len(data) > 0:
                n = data[0]
                data = data[1:]
            else:
                n = 0

            argument_values = {}
            for _, argument in sorted(function.arguments.items()):
                size = argument.get_encoded_size()
                try:
                    argument_id = data[0]
                    data = data[1:]
                except IndexError:
                    # send fail acceptance report
                    self.parent.send(ServicePacket(1, 2, [service, subtype]))
                    return
                if argument_id != argument.argument_id:  # an argument is missing
                    # send fail acceptance report
                    self.parent.send(ServicePacket(1, 2, [service, subtype]))
                    return
                encoded_value = data[:size]
                data = data[size:]
                try:
                    value = argument.decode(encoded_value)
                except Exception:
                    # send fail acceptance report
                    self.parent.send(ServicePacket(1, 2, [service, subtype]))
                    return
                argument_values[argument_id] = value

            if len(argument_values) > 0 and n != len(argument_values):
                # send fail acceptance report
                self.parent.send(ServicePacket(1, 2, [service, subtype]))
                return

            # send success acceptance report
            self.parent.send(ServicePacket(1, 1, [service, subtype]))

            if self.perform_function(function_id, argument_values) is False:
                # send fail completion report
                self.parent.send(ServicePacket(1, 8, [service, subtype]))
            else:
                # send success completion report
                self.parent.send(ServicePacket(1, 7, [service, subtype]))
        else:
            # send fail acceptance report
            self.parent.send(ServicePacket(1, 2, [service, subtype]))

    def perform_function(self, function_id, arguments):
        # to be implemented by higher layer application
        return True

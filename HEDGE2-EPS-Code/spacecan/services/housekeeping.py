import micropython
import struct
import time
import json

from ..primitives.timer import Timer
from .core import ServicePacket


TIMER_ID = 3


class HousekeepingReport:
    def __init__(self, parent, report_id, interval, enabled, parameter_ids):
        self.parent = parent
        self.report_id = report_id
        self.interval = interval
        self.enabled = enabled
        self.parameter_ids = parameter_ids
        self.last_sent = 0
        self.encoding = ""

    def __repr__(self):
        return f"HousekeepingStructure({self.report_id}, {self.interval}, {self.enabled}, {self.parameter_ids})"

    def decode(self, data):
        encoding = (
            self.encoding if self.encoding.startswith("!") else "!" + self.encoding
        )
        return struct.unpack(encoding, data)

    def encode(self):
        data = bytearray()
        for parameter_id in self.parameter_ids:
            parameter = self.parent.parent.parameter.get_parameter(parameter_id)
            data += parameter.encode()
        return data


class HousekeepingService:
    def __init__(self, parent):
        self.parent = parent
        self.housekeeping_reports = {}

    def define_housekeeping_report(
        self, report_id, interval, enabled, parameter_ids, **other
    ):
        self.housekeeping_reports[report_id] = HousekeepingReport(
            self, report_id, interval, enabled, parameter_ids
        )
        for parameter_id in parameter_ids:
            parameter = self.parent.parameter.get_parameter(parameter_id)
            self.housekeeping_reports[report_id].encoding += parameter.encoding

    def get_housekeeping_report(self, report_id):
        return self.housekeeping_reports.get(report_id)


class HousekeepingServiceController(HousekeepingService):
    def add_housekeeping_reports_from_file(self, filepath, node_id):
        with open(filepath, "r", encoding="utf-8") as f:
            x = json.load(f)
        list_of_dicts = x["housekeeping_reports"]

        for y in list_of_dicts:
            y["report_id"] = (node_id, y["report_id"])
            new_parameter_ids = []
            for z in y["parameter_ids"]:
                new_parameter_ids.append((node_id, z))
            y["parameter_ids"] = new_parameter_ids

        for kwargs in list_of_dicts:
            self.define_housekeeping_report(**kwargs)

    def process(arg):
        self, service, subtype, data, node_id = arg
        case = (service, subtype)

        if case == (3, 25):  # housekeeping parameter report
            report_id = (node_id, data[0])
            data = data[1:]
            housekeeping_report = self.get_housekeeping_report(report_id)
            decoded_data = housekeeping_report.decode(data)
            report = {}
            for i, value in enumerate(decoded_data):
                parameter_id = housekeeping_report.parameter_ids[i]
                report[parameter_id] = value
            self.received_housekeeping_report(node_id, report, report_id)

    def received_housekeeping_report(self, node_id, report, report_id):
        # to be implemented by higher layer application
        pass


class HousekeepingServiceResponder(HousekeepingService):
    def __init__(self, parent):
        self.parent = parent
        self.housekeeping_reports = {}

        self._timer = None

    def add_housekeeping_reports_from_file(self, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            x = json.load(f)
        list_of_dicts = x["housekeeping_reports"]

        for kwargs in list_of_dicts:
            self.define_housekeeping_report(**kwargs)

        self._update_housekeeping_timer()

    def _update_housekeeping_timer(self):
        enabled = False
        for report in self.housekeeping_reports.values():
            if report.enabled:
                enabled = True
                break

        if enabled is True and self._timer is None:
            self._timer = Timer(1, self._timer_expired, TIMER_ID)
            self._check_and_send_housekeeping_reports()
            self._timer.start()
        elif enabled is False and self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _timer_expired(self):
        micropython.schedule(
            HousekeepingServiceResponder._check_and_send_housekeeping_reports, self
        )

    def _check_and_send_housekeeping_reports(self):
        for report in self.housekeeping_reports.values():
            if report.enabled and report.last_sent + report.interval <= time.time():
                report.last_sent = time.time()
                data = bytearray([report.report_id]) + report.encode()
                self.parent.send(ServicePacket(3, 25, data))

    def process(arg):
        self, service, subtype, data, node_id = arg
        case = (service, subtype)

        if case == (3, 5):  # enable periodic housekeeping report
            report_ids = self._extract_report_ids(data)
            if report_ids is None:
                # send fail acceptance report
                self.parent.send(ServicePacket(1, 2, [service, subtype]))
                return

            # send success acceptance report
            self.parent.send(ServicePacket(1, 1, [service, subtype]))

            for report_id in report_ids:
                report = self.get_housekeeping_report(report_id)
                report.enabled = True

            self._update_housekeeping_timer()

            # send success completion report
            self.parent.send(ServicePacket(1, 7, [service, subtype]))

        elif case == (3, 6):  # disable periodic housekeeping report
            report_ids = self._extract_report_ids(data)
            if report_ids is None:
                # send fail acceptance report
                self.parent.send(ServicePacket(1, 2, [service, subtype]))
                return

            # send success acceptance report
            self.parent.send(ServicePacket(1, 1, [service, subtype]))

            for report_id in report_ids:
                report = self.get_housekeeping_report(report_id)
                report.enabled = False

            self._update_housekeeping_timer()

            # send success completion report
            self.parent.send(ServicePacket(1, 7, [service, subtype]))

        elif case == (3, 27):  # single shot housekeeping report
            report_ids = self._extract_report_ids(data)
            if report_ids is None:
                # send fail acceptance report
                self.parent.send(ServicePacket(1, 2, [service, subtype]))
                return

            # send success acceptance report
            self.parent.send(ServicePacket(1, 1, [service, subtype]))

            for report_id in report_ids:
                report = self.get_housekeeping_report(report_id)
                if report:
                    data = bytearray([report_id]) + report.encode()
                    self.parent.send(ServicePacket(3, 25, data))

            # send success completion report
            self.parent.send(ServicePacket(1, 7, [service, subtype]))
        else:
            # send fail acceptance report
            self.parent.send(ServicePacket(1, 2, [service, subtype]))

    def _extract_report_ids(self, data):
        try:
            n = data[0]
            data = data[1:]
            if n == 0:
                return None
            report_ids = list(x for x in data)
            if n != len(report_ids):
                raise ValueError
            for report_id in report_ids:
                if report_id not in self.housekeeping_reports:
                    raise ValueError
        except (IndexError, ValueError, AttributeError):
            return None
        return report_ids

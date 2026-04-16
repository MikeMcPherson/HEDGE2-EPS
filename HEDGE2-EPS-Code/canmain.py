import time
import struct
from machine import Pin, I2C, SPI
import machine
import spacecan
from mcp2518 import MCP2518FD
from spacecan.primitives.can_frame import CanFrame

# ==========================================
# 1. HARDWARE INITIALIZATION
# ==========================================

# I2C & INA260 Power Monitors
I2C_SDA_PIN = 4
I2C_SCL_PIN = 5
BATT_INA_ADDR = 0x40
i2c = I2C(0, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=400000)

# Load Switch Pins
CHANNELS = {
    "OBC": {"pin": Pin(11, Pin.OUT, value=0), "ina": 0x45},
    "GNSS": {"pin": Pin(12, Pin.OUT, value=0), "ina": 0x41},
    "SCI": {"pin": Pin(13, Pin.OUT, value=0), "ina": 0x42},
    "XBEE": {"pin": Pin(14, Pin.OUT, value=0), "ina": 0x43},
    "DMR": {"pin": Pin(15, Pin.OUT, value=0), "ina": 0x44},
}

# SpaceCAN Target Mapping
TARGET_MAP = {0x01: ["OBC"], 0x02: ["SCI"], 0x03: ["XBEE", "DMR"], 0x04: ["EPS"]}

# Init SPI and CAN Controllers
spi = SPI(
    0, baudrate=10000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19), miso=Pin(16)
)

CAN_A_CS = 21
CAN_A_INT = Pin(22, Pin.IN, Pin.PULL_UP)
can_a = MCP2518FD(spi, cs_pin=CAN_A_CS)

CAN_B_CS = 17
CAN_B_INT = Pin(20, Pin.IN, Pin.PULL_UP)
can_b = MCP2518FD(spi, cs_pin=CAN_B_CS)


class DummyBus:
    def disconnect(self):
        pass


class CustomNetwork:
    # Bypasses the Pyboard hardware routes SpaceCAN to the MCP2518 chips
    def __init__(self, primary, secondary):
        self.primary = primary
        self.secondary = secondary
        # Dummy buses prevent responder.disconnect() from crashing
        self.bus_a = DummyBus()
        self.bus_b = DummyBus()

    def start(self):
        pass

    def stop(self):
        pass

    def send(self, can_frame):
        # The library calls this automatically when it wants to transmit telemetry.
        self.primary.send(can_frame.can_id, can_frame.data)
        self.secondary.send(can_frame.can_id, can_frame.data)


class SABREResponder(spacecan.Responder):
    """
    Child class that cleanly overrides the hardcoded Pyboard connect() method.
    """

    def connect(self):
        print("[EPS] Initializing Dual-Redundant SPI Network...")
        # We assign our custom network safely from INSIDE the class
        self.network = CustomNetwork(can_a, can_b)


# I2C for INA260 Power Monitors
def read_ina260(address):
    try:
        v_bytes = i2c.readfrom_mem(address, 0x02, 2)
        i_bytes = i2c.readfrom_mem(address, 0x01, 2)

        v_raw = struct.unpack(">H", v_bytes)[0]
        i_raw = struct.unpack(">h", i_bytes)[0]

        voltage_v = (v_raw * 1.25) / 1000.0
        current_ma = i_raw * 1.25
        return voltage_v, current_ma
    except OSError:
        return None, None


# ==========================================
# 3. SPACECAN PROTOCOL SETUP
# ==========================================
responder = spacecan.Responder(
    interface="custom",
    channel_a=1,  # Tell library we have Bus A
    channel_b=2,  # Tell library we have Bus B
    node_id=0x04,
    heartbeat_period=0.5,
    use_packets=True,
)

responder.connect()
responder.start()

services = spacecan.Services(responder)
services.from_file("config/eps_services.json")

# Map Telemetry Parameter IDs (Must match eps_services.json)
PARAM_BATT_V = 1
PARAM_BATT_I = 2
PARAM_OBC_I = 3

set_param = services.parameter.set_parameter_value
get_param = services.parameter.get_parameter_value


def enter_safe_mode():
    """
    Executes the Survival/Recovery configuration:
    OBC: ON (Low Power state handled by OBC software)
    GNSS: OFF
    COMM: RECEIVE ONLY (XBEE ON, DMR OFF)
    SCIENCE: OFF
    """
    print("[EPS] Transitioning to SAFE MODE...")

    # 1. Keep OBC powered
    CHANNELS["OBC"]["pin"].value(1)

    # 2. GNSS and Science OFF
    CHANNELS["GNSS"]["pin"].value(0)
    CHANNELS["SCI"]["pin"].value(0)

    # 3. COMM: Receive Only
    # (Powering XBEE for commands, killing high-power DMR)
    CHANNELS["XBEE"]["pin"].value(1)
    CHANNELS["DMR"]["pin"].value(0)


# Execute HEDGE-2 Service 8 Power Commands
def perform_function(function_id, arguments):
    # 0xFF: SAFE SPACECRAFT (Now using the new refined definition)
    if function_id == 0xFF:
        enter_safe_mode()
        return

    # Extract target PCB from SpaceCAN command argument
    target_pcb_id = arguments.get(0)

    if target_pcb_id in TARGET_MAP:
        if target_pcb_id == 0x04 and function_id == 0x01:
            print("SpaceCAN CMD: EPS commanded to self-reset!")
            # Safe the payloads before dying
            for name in ["GNSS", "SCI", "XBEE", "DMR"]:
                CHANNELS[name]["pin"].value(0)
            time.sleep(0.5)
            machine.reset()  # Hard software reboot of the Pico

        else:
            for name in TARGET_MAP[target_pcb_id]:
                # Skip if it's the EPS (we can't power off our own battery)
                if name == "EPS":
                    continue

                if function_id == 0x01:  # Power-Cycle
                    print(f"SpaceCAN CMD: Power Cycling {name}")
                    CHANNELS[name]["pin"].value(0)
                    time.sleep(1)
                    CHANNELS[name]["pin"].value(1)
                elif function_id == 0x02:  # Power-On
                    print(f"SpaceCAN CMD: Powering ON {name}")
                    CHANNELS[name]["pin"].value(1)
                elif function_id == 0x03:  # Power-Off
                    print(f"SpaceCAN CMD: Powering OFF {name}")
                    CHANNELS[name]["pin"].value(0)


# ==========================================
# 4. MAIN FLIGHT LOOP
# ==========================================
responder.connect()
responder.start()

# Start in SAFE MODE
# This powers on OBC and XBEE, but kills Science/DMR/GNSS
enter_safe_mode()
print("SABRE III EPS Dual-Redundant SpaceCAN Node Online.")
print("SABRE III EPS Online. Boot State: SAFE.")

time.sleep(1)

try:
    while True:
        # Check physical interrupt pins
        if CAN_A_INT.value() == 0:
            msg_a = can_a.recv()
            if msg_a:
                frame = CanFrame(msg_a.id, msg_a.payload)
                responder.received_frame(frame)
            else:
                break

        if CAN_B_INT.value() == 0:
            msg_b = can_b.recv()
            if msg_b:
                frame = CanFrame(msg_b.id, msg_b.payload)
                responder.received_frame(frame)
            else:
                break

        # Update Telemetry (Service 3) using sensors
        # If the OBC asks for data, the library handles the 'REP' automatically.
        batt_v, batt_i = read_ina260(BATT_INA_ADDR)
        obc_v, obc_i = read_ina260(CHANNELS["OBC"]["ina"])

        if batt_v is not None:
            set_param(PARAM_BATT_V, batt_v)
            set_param(PARAM_BATT_I, batt_i)
        if obc_i is not None:
            set_param(PARAM_OBC_I, obc_i)

        # Loop Timing (100Hz)
        time.sleep(0.01)

except KeyboardInterrupt:
    print("\n[EPS] Manual Stop Triggered.")
except Exception as e:
    print(f"\n[EPS] CRITICAL ERROR: {e}")
finally:
    # If the software dies, kill all load switches
    print("Safing all load switches...")
    responder.stop()
    responder.disconnect()
    for data in CHANNELS.values():
        data["pin"].value(0)

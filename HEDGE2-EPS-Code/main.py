import time
from machine import Pin, I2C
import struct

# ==========================================
# 1. HARDWARE MAPPING 
# ==========================================
I2C_SDA_PIN = 4
I2C_SCL_PIN = 5
BATT_INA_ADDR = 0x40  # Main Battery Input Monitor

# HEDGE-2 PCB Channel Mapping
# Pins sourced from existing hardware configuration
CHANNELS = {
    "OBC":  {"pin": Pin(11, Pin.OUT, value=0), "ina": 0x45},
    "GNSS": {"pin": Pin(12, Pin.OUT, value=0), "ina": 0x41},
    "XBEE": {"pin": Pin(14, Pin.OUT, value=0), "ina": 0x43},
    "DMR":  {"pin": Pin(15, Pin.OUT, value=0), "ina": 0x44},
    "SCI":  {"pin": Pin(13, Pin.OUT, value=0), "ina": 0x42},
}

i2c = I2C(0, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=400000)

def read_ina260(address):
    """
    Reads Bus Voltage (V) and Current (mA) from INA260.
    """
    try:
        v_bytes = i2c.readfrom_mem(address, 0x02, 2)
        i_bytes = i2c.readfrom_mem(address, 0x01, 2)
        
        v_raw = struct.unpack('>H', v_bytes)[0]
        i_raw = struct.unpack('>h', i_bytes)[0]
        
        voltage_v = (v_raw * 1.25) / 1000.0
        current_ma = (i_raw * 1.25)
        return voltage_v, current_ma
    except OSError:
        return None, None

def report_status(label, address):
    """Prints V/I telemetry for a specific rail."""
    v, i = read_ina260(address)
    if v is not None:
        print(f"   [DATA] {label:.<10} {v:>5.2f} V | {i:>7.1f} mA")
    else:
        print(f"   [ERR ] {label:.<10} MONITOR OFFLINE")

# ==========================================
# 2. SEQUENTIAL BOOT SEQUENCE (MISSION PROFILE)
# ==========================================

def run_mission_boot():
    print("==========================================")
    print(" HEDGE-2 EPS: SEQUENTIAL BOOT INITIATED ")
    print("==========================================")

    # Step 1: OBC Boot (T+0s)
    print("\n[T+00s] Powering OBC...")
    CHANNELS["OBC"]["pin"].value(1)
    time.sleep(0.5)
    report_status("BATT_IN", BATT_INA_ADDR)
    report_status("OBC_OUT", CHANNELS["OBC"]["ina"])
    
    print("--- 10 SECOND OBC INITIALIZATION DELAY ---")
    time.sleep(10)

    # Sequential Loop for remaining subsystems
    # Order: GNSS -> XBEE -> DMR -> SCI
    subsystems = ["GNSS", "XBEE", "DMR", "SCI"]
    elapsed = 10
    
    for sub in subsystems:
        elapsed += 2
        print(f"\n[T+{elapsed}s] Powering {sub}...")
        CHANNELS[sub]["pin"].value(1)
        time.sleep(0.5) 
        report_status("BATT_IN", BATT_INA_ADDR)
        report_status(f"{sub}_OUT", CHANNELS[sub]["ina"])
        time.sleep(1.5) # Wait for remainder of the 2s interval

    print("\n" + "="*42)
    print(" HEDGE-2 SYSTEMS FULLY POWERED ")
    print("="*42 + "\n")

# ==========================================
# 3. STEADY-STATE TELEMETRY
# ==========================================

run_mission_boot()

try:
    while True:
        batt_v, batt_i = read_ina260(BATT_INA_ADDR)
        
        print("\033[H\033[J") # Clear console for cleaner telemetry reading
        print(f"HEDGE-2 MISSION TELEMETRY")
        print(f"------------------------------------------")
        if batt_v:
            print(f"MAIN BUS VOLTAGE : {batt_v:.2f} V")
            print(f"TOTAL SYSTEM DRAW: {batt_i:.1f} mA")
        print(f"------------------------------------------")
        
        for name, data in CHANNELS.items():
            v, i = read_ina260(data["ina"])
            if v is not None:
                # Tracks voltage to ensure switches aren't sagging
                print(f" {name:.<8} : {v:>4.2f} V | {i:>7.1f} mA")
        
        print(f"------------------------------------------")
        time.sleep(2)

except KeyboardInterrupt:
    print("\nManual Safing Triggered.")
finally:
    # Ensure all components are sacrificed/killed if the script stops
    for data in CHANNELS.values():
        data["pin"].value(0)
    print("HEDGE-2 SYSTEM SAFED (ALL CHANNELS OFF).")
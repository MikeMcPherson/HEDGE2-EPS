"""
Sabre III EPS - Phase 3: Interactive Routing & Telemetry Test
Verifies Load Switches, 5V Buck Converter, and INA260 accuracy step-by-step.
"""

from machine import Pin, I2C
import time
import struct
import sys

# ==========================================
# 1. HARDWARE MAPPING
# ==========================================

I2C_SDA_PIN = 4  # GP4
I2C_SCL_PIN = 5  # GP5

BATT_INA_ADDR = 0x40

# Dictionary linking the channel name to its GPIO pin and its specific INA260 address
CHANNELS = {
    "OBC":  {"pin": Pin(11, Pin.OUT, value=0), "ina": 0x45},
    "GNSS": {"pin": Pin(12, Pin.OUT, value=0), "ina": 0x41},
    "SCI":  {"pin": Pin(13, Pin.OUT, value=0), "ina": 0x42},
    "XBEE": {"pin": Pin(14, Pin.OUT, value=0), "ina": 0x43},
    "DMR":  {"pin": Pin(15, Pin.OUT, value=0), "ina": 0x44},
}

# =========================================
# 2. INITIALIZATION
# ==========================================

i2c = I2C(0, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=400000)

def read_ina260(address):
    """Reads Voltage (V) and Current (mA) from INA260."""
    try:
        v_bytes = i2c.readfrom_mem(address, 0x02, 2)
        i_bytes = i2c.readfrom_mem(address, 0x01, 2)
        
        v_raw = struct.unpack('>H', v_bytes)[0]
        i_raw = struct.unpack('>h', i_bytes)[0]
        
        voltage_v = (v_raw * 1.25) / 1000.0
        current_ma = (i_raw * 1.25)  # Already in mA
        return voltage_v, current_ma
    except OSError:
        return None, None

# ==========================================
# 3. INTERACTIVE TEST SEQUENCE
# ==========================================

def main():
    print("==================================================")
    print("  SABRE III EPS - INTERACTIVE HARDWARE VERIFICATION ")
    print("==================================================")
    print("Ensure Bench Supply is set to ~11.1V and 200mA limit.")
    print("All load switches are currently OFF.\n")
    
    for name in ["OBC", "GNSS", "SCI", "XBEE", "DMR"]:
        data = CHANNELS[name]
        print(f"--- TESTING {name} CHANNEL ---")
        print(f"1. Attach multimeter test hooks to the {name} 5V pins.")
        print("   -> Powering ON automatically in 30 seconds...")
        time.sleep(30)
        
        # Turn ON the load switch
        data["pin"].value(1)
        time.sleep(0.5) # Give the buck converter and caps a half-second to stabilize
        
        # Read the sensors
        batt_v, batt_i = read_ina260(BATT_INA_ADDR)
        chan_v, chan_i = read_ina260(data["ina"])
        
        print("\n   [ SYSTEM TELEMETRY ]")
        if batt_v is not None:
            print(f"   -> INPUT (BATT_SENSE) : {batt_v:>5.2f} V | {batt_i:>5.1f} mA")
        else:
            print("   -> INPUT (BATT_SENSE) : OFFLINE")
            
        if chan_v is not None:
            print(f"   -> OUTPUT ({name}_SENSE) : {chan_v:>5.2f} V | {chan_i:>5.1f} mA")
        else:
            print(f"   -> OUTPUT ({name}_SENSE) : OFFLINE")
            
        print("\n2. Read your physical multimeter NOW.")
        print("   -> Holding power for 8 seconds, then turning OFF...")
        time.sleep(8)
        
        # Turn OFF the load switch
        data["pin"].value(0)
        time.sleep(2) # Brief pause before the next channel starts
        print(f"{name} Powered OFF.\n")
        print("="*50 + "\n")

    print("ALL CHANNELS TESTED. SYSTEM SAFED.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest aborted by user. Safing all switches...")
        for data in CHANNELS.values():
            data["pin"].value(0)
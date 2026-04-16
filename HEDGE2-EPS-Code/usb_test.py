"""
Sabre III EPS - Phase 1 Diagnostic (Logic & USB Power Only)
Tests 3.3V rail, I2C comms, and GPIO routing without Main Battery.
"""

from machine import Pin, I2C, SPI
import time
import struct

# ==========================================
# 1. HARDWARE PINS (Mapped strictly to GP numbers)
# ==========================================

# I2C0 Bus (INA260 Power Monitors)
I2C_SDA_PIN = 4  # Physical Pin 6
I2C_SCL_PIN = 5  # Physical Pin 7

# INA260 Addresses
# BATT_SENSE       -> 0x40
# GNSS_SENSE       -> 0x41
# SCI_SENSE        -> 0x42
# COMM_XBEE_SENSE  -> 0x43
# COMM_DMR_SENSE   -> 0x44
# OBC_SENSE        -> 0x45

# SPI0 Bus (MCP2518 CAN Controller)
SPI_MISO_PIN = 16 # Physical Pin 21
SPI_SCK_PIN = 18  # Physical Pin 24
SPI_MOSI_PIN = 19 # Physical Pin 25

# CAN Chip Selects & Interrupts
CAN_B_CS_PIN = 17  # Physical Pin 22
CAN_B_INT_PIN = 20 # Physical Pin 26
CAN_A_CS_PIN = 21  # Physical Pin 27
CAN_A_INT_PIN = 22 # Physical Pin 29

# TPS22997 Load Switch Enable Pins
OBC_C_PIN = 11       # Physical Pin 15
GNSS_C_PIN = 12      # Physical Pin 16
SCI_C_PIN = 13       # Physical Pin 17
COMM_XBEE_C_PIN = 14 # Physical Pin 19
COMM_DMR_C_PIN = 15  # Physical Pin 20

# ==========================================
# 2. INITIALIZATION
# ==========================================

# Setup I2C at 400kHz (Fast Mode) - Block 0 for GP4/GP5
i2c = I2C(0, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=400000)

# Setup SPI (Hardware block 0)
spi = SPI(0, baudrate=1000000, polarity=0, phase=0, 
          sck=Pin(SPI_SCK_PIN), mosi=Pin(SPI_MOSI_PIN), miso=Pin(SPI_MISO_PIN))

# Initialize CS pins high (deselected) so they don't interfere
can_a_cs = Pin(CAN_A_CS_PIN, Pin.OUT, value=1) 
can_b_cs = Pin(CAN_B_CS_PIN, Pin.OUT, value=1) 

# Setup Load Switches (Default OFF)
switches = {
    "OUT_1_OBC": Pin(OBC_C_PIN, Pin.OUT, value=0),
    "OUT_2_GNSS": Pin(GNSS_C_PIN, Pin.OUT, value=0),
    "OUT_3_SCI": Pin(SCI_C_PIN, Pin.OUT, value=0),
    "OUT_4_XBEE": Pin(COMM_XBEE_C_PIN, Pin.OUT, value=0),
    "OUT_5_DMR": Pin(COMM_DMR_C_PIN, Pin.OUT, value=0),
}

# ==========================================
# 3. DIAGNOSTIC TESTS
# ==========================================

def test_ina260_comms():
    print("\n--- TEST 1: I2C BUS & INA260 SCAN ---")
    devices = i2c.scan()
    
    if not devices:
        print("FAIL: No I2C devices found. Check pull-up resistors and 3V3 rail.")
        return
        
    print(f"PASS: Found {len(devices)} device(s) on I2C bus.")
    
    for addr in devices:
        try:
            mfg_id_bytes = i2c.readfrom_mem(addr, 0xFE, 2)
            mfg_id = struct.unpack('>H', mfg_id_bytes)[0]
            
            if mfg_id == 0x5449:
                print(f"  -> Device at {hex(addr)}: Verified INA260 (ID: {hex(mfg_id)})")
            else:
                print(f"  -> Device at {hex(addr)}: Unknown Device (ID: {hex(mfg_id)})")
        except OSError:
            print(f"  -> Device at {hex(addr)}: Unresponsive to ID request.")

# ==========================================
# 4. EXECUTE
# ==========================================

def main():
    print("========================================")
    print("  SABRE III EPS - USB DIAGNOSTIC MODE   ")
    print("========================================")
    
    time.sleep(1) 
    
    test_ina260_comms()
    time.sleep(1)
    
    print("\n========================================")
    print("  DIAGNOSTICS COMPLETE. SYSTEM IDLE.    ")
    print("========================================")

if __name__ == "__main__":
    main()
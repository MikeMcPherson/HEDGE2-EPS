from machine import Pin, SPI
import struct
import time

class CANMessage:
    def __init__(self, can_id, payload):
        self.id = can_id
        self.payload = payload

class MCP2518FD:
    # --- Register Addresses ---
    REG_CiCON      = 0x0000
    REG_CiNBTCFG   = 0x0008 # Nominal Bit Time
    REG_CiFIFOCON1 = 0x0050 # TX FIFO
    REG_CiFIFOSTA1 = 0x0058 
    REG_CiFIFOUA1  = 0x0060 
    REG_CiFIFOCON2 = 0x0054 # RX FIFO
    REG_CiFIFOSTA2 = 0x005C 
    REG_CiFIFOUA2  = 0x0064 
    REG_CiFLTCON0  = 0x01D0 # Filter Control
    REG_CiFLTOBJ0  = 0x01F0 # Filter Object
    REG_CiFLTMASK0 = 0x01F4 # Filter Mask

    def __init__(self, spi, cs_pin):
        self.spi = spi
        self.cs = Pin(cs_pin, Pin.OUT, value=1)
        self.reset_chip()
        self.configure_spacecan()

    def _transfer(self, cmd, address, data_bytes=None, read_len=0):
        header = bytearray(2)
        header[0] = (cmd << 4) | ((address >> 8) & 0x0F)
        header[1] = address & 0xFF
        self.cs.value(0)
        self.spi.write(header)
        res = self.spi.read(read_len) if cmd == 0x03 else None
        if cmd == 0x02 and data_bytes: self.spi.write(data_bytes)
        self.cs.value(1)
        return res

    def read_reg32(self, addr):
        return struct.unpack('<I', self._transfer(0x03, addr, read_len=4))[0]

    def write_reg32(self, addr, val):
        self._transfer(0x02, addr, data_bytes=struct.pack('<I', val))

    def reset_chip(self):
        self._transfer(0x00, 0x0000)
        time.sleep_ms(10)

    def configure_spacecan(self):
        # 1. Enter Configuration Mode
        self.write_reg32(self.REG_CiCON, 0x04000000) 
        
        # 2. Bit Timing: 40MHz Clock -> 1Mbps
        # TSEG1=30, TSEG2=7, SJW=7, BRP=0
        # NBTCFG bits: [BRP:8 | TSEG1:8 | TSEG2:7 | SJW:7]
        self.write_reg32(self.REG_CiNBTCFG, 0x001E0707)

        # 3. FIFO 1: Transmit (8 messages, 8-byte payload)
        # TXEN bit (0x80) + 8 msgs (0x07 << 24)
        self.write_reg32(self.REG_CiFIFOCON1, 0x07000080)

        # 4. FIFO 2: Receive (8 messages, 8-byte payload)
        # RX FIFO (TXEN=0) + 8 msgs (0x07 << 24)
        self.write_reg32(self.REG_CiFIFOCON2, 0x07000000)

        # 5. Global Filter: Accept ALL frames for SpaceCAN processing
        self.write_reg32(self.REG_CiFLTOBJ0, 0x00000000) # Match 0
        self.write_reg32(self.REG_CiFLTMASK0, 0x00000000) # Mask 0 (Don't care)
        self.write_reg32(self.REG_CiFLTCON0, 0x00000080) # Enable Filter 0 -> FIFO 2

        # 6. Switch to Normal Mode
        self.write_reg32(self.REG_CiCON, 0x00000000)
        print("[CAN] MCP2518FD initialized at 1Mbps.")

    def send(self, can_id, payload):
        # Get next available TX address
        tx_addr = self.read_reg32(self.REG_CiFIFOUA1)
        
        # SpaceCAN TMO structure: ID (bits 0-10), DLC=8 (bits 16-19)
        w0 = can_id & 0x7FF
        w1 = 0x00080000 # Standard CAN, DLC=8
        
        # Pack payload into two 32-bit words
        payload_pad = payload + b'\x00' * (8 - len(payload))
        d_low, d_high = struct.unpack('<II', payload_pad)
        
        # Write 16-byte object to RAM
        self._transfer(0x02, tx_addr, data_bytes=struct.pack('<IIII', w0, w1, d_low, d_high))
        
        # Trigger TX: Set UINC (bit 8) and TXREQ (bit 1) in FIFOCON1
        conf = self.read_reg32(self.REG_CiFIFOCON1)
        self.write_reg32(self.REG_CiFIFOCON1, conf | 0x00000102)

    def recv(self):
        # Check FIFO 2 Status (Bit 0: Receive FIFO Not Empty)
        if not (self.read_reg32(self.REG_CiFIFOSTA2) & 0x01):
            return None
            
        # Read from current User Address
        rx_addr = self.read_reg32(self.REG_CiFIFOUA2)
        rx_raw = self._transfer(0x03, rx_addr, read_len=16)
        w0, w1, d_low, d_high = struct.unpack('<IIII', rx_raw)
        
        # Increment FIFO 2: Set UINC (bit 8)
        conf = self.read_reg32(self.REG_CiFIFOCON2)
        self.write_reg32(self.REG_CiFIFOCON2, conf | 0x00000100)
        
        return CANMessage(w0 & 0x7FF, struct.pack('<II', d_low, d_high))
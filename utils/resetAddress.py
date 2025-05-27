import serial
import struct
import time

def modbus_crc16(data):
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            lsb = crc & 0x0001
            crc >>= 1
            if lsb:
                crc ^= 0xA001
    return crc.to_bytes(2, byteorder='little')

def build_modbus_write(addr, reg, value):
    cmd = struct.pack('>B B H H', addr, 0x06, reg, value)
    return cmd + modbus_crc16(cmd)

def reset_addresses(port='COM12', new_addr=0x01):
    try:
        with serial.Serial(port, 9600, timeout=0.5) as ser:
            for old_addr in range(1, 5):
                print(f"--- Attempting to reset sensor at address 0x{old_addr:02X} ---")
                cmd = build_modbus_write(old_addr, 0x0200, new_addr)
                print(f"[TX] {cmd.hex().upper()}")
                ser.reset_input_buffer()
                ser.write(cmd)
                time.sleep(0.1)
                resp = ser.read(8)
                if len(resp) == 8 and resp[:6] == cmd[:6]:
                    print(f"✅ Sensor 0x{old_addr:02X} successfully set to 0x{new_addr:02X}")
                else:
                    print(f"⚠️  No response or failed to write to sensor at 0x{old_addr:02X}")
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    reset_addresses()

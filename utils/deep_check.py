import serial
import struct
import time

def crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            lsb = crc & 0x0001
            crc >>= 1
            if lsb:
                crc ^= 0xA001
    return crc.to_bytes(2, byteorder='little')

def build_write(addr, reg, value):
    cmd = struct.pack('>B B H H', addr, 0x06, reg, value)
    return cmd + crc16(cmd)

def build_read(addr, reg, count):
    cmd = struct.pack('>B B H H', addr, 0x03, reg, count)
    return cmd + crc16(cmd)

def send_cmd(ser, cmd, label, expect=8):
    print(f"[TX] {cmd.hex().upper()} ({label})")
    ser.write(cmd)
    ser.flush()
    time.sleep(0.1)
    resp = ser.read(expect)
    print(f"[RX] {resp.hex().upper() if resp else 'NO RESPONSE'}")
    return resp

if __name__ == "__main__":
    port = "COM10"
    addr = 0x01

    try:
        with serial.Serial(port, 9600, timeout=0.5) as ser:
            # 1. Read address register (baseline)
            send_cmd(ser, build_read(addr, 0x0200, 1), "Read Address Register")

            # 2. Read config mode register
            send_cmd(ser, build_read(addr, 0x0207, 1), "Read Config Mode")

            # 3. Attempt write config enable
            send_cmd(ser, build_write(addr, 0x0207, 0x0001), "Write Config Mode")

            # 4. Re-read config mode
            send_cmd(ser, build_read(addr, 0x0207, 1), "Re-read Config Mode")

            # 5. Write angle & denoise
            send_cmd(ser, build_write(addr, 0x0208, 2), "Write Angle Level")
            send_cmd(ser, build_write(addr, 0x021A, 5), "Write Denoise Level")

            # 6. Re-read angle & denoise
            send_cmd(ser, build_read(addr, 0x0208, 1), "Read Angle Level")
            send_cmd(ser, build_read(addr, 0x021A, 1), "Read Denoise Level")

    except Exception as e:
        print(f"[ERROR] {e}")

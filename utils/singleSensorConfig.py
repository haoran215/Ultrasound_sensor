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

def build_cmd(addr, reg, value):
    cmd = struct.pack('>B B H H', addr, 0x06, reg, value)
    crc = crc16(cmd)
    return cmd + crc

def send_cmd(ser, cmd, label):
    print(f"[TX] {cmd.hex().upper()} ({label})")
    ser.write(cmd)
    ser.flush()
    time.sleep(0.1)
    resp = ser.read(8)
    if len(resp) == 8:
        print(f"[RX] {resp.hex().upper()}")
        if resp[:6] == cmd[:6]:
            print(f"✅ {label} OK")
            return True
    print(f"❌ {label} Failed or No Response")
    return False

if __name__ == "__main__":
    port = "COM13"  # 串口号
    addr = 0x01     # 传感器地址
    try:
        with serial.Serial(port, 9600, timeout=0.5) as ser:
            # Step 1: Enable config mode
            send_cmd(ser, build_cmd(addr, 0x0207, 0x0001), "Enable Config Mode")

            # Step 2: Set angle level (e.g. 2)
            send_cmd(ser, build_cmd(addr, 0x0208, 0x0002), "Write Angle Level")

            # Step 3: Set denoise level (e.g. 5)
            send_cmd(ser, build_cmd(addr, 0x021A, 0x0005), "Write Denoise Level")

    except Exception as e:
        print(f"[ERROR] {e}")

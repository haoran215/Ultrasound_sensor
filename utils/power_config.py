# auto_config_on_powerup.py
# Automatically sends config write commands right after user confirms sensor has just powered up

import serial
import struct
import time

PORT = "COM13"   # <- Change to your actual port
BAUD = 9600
ADDR = 0x01       # Sensor address

# --- CRC16 Modbus ---
def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder='little')

# --- Build Write Command ---
def build_write(addr, reg, val):
    frame = struct.pack('>B B H H', addr, 0x06, reg, val)
    return frame + crc16(frame)

# --- Send command and wait for echo ---
def send_cmd(ser, cmd, label):
    print(f"[TX] {cmd.hex().upper()} ({label})")
    ser.write(cmd)
    ser.flush()
    time.sleep(0.15)
    resp = ser.read(8)
    if resp:
        print(f"[RX] {resp.hex().upper()}")
        if resp[:6] == cmd[:6]:
            print(f"✅ {label} OK")
            return True
        else:
            print(f"❌ {label} Invalid echo")
    else:
        print(f"❌ {label} No response")
    return False

# --- Main auto config sequence ---
def configure_sensor():
    print("⚡ Please power ON the sensor NOW. Starting config in 1.5 seconds...")
    time.sleep(1.5)

    try:
        with serial.Serial(PORT, BAUD, timeout=0.5) as ser:
            ok1 = send_cmd(ser, build_write(ADDR, 0x0207, 0x0001), "Enable Custom Output Mode")
            time.sleep(0.1)
            ok2 = send_cmd(ser, build_write(ADDR, 0x0208, 0x0002), "Set Angle Level to 2")
            time.sleep(0.1)
            ok3 = send_cmd(ser, build_write(ADDR, 0x021A, 0x0005), "Set Denoise Level to 5")

            if ok1 and ok2 and ok3:
                print("\n✅ All settings applied successfully.")
            else:
                print("\n❌ One or more settings failed. Try powering up again and rerun.")

    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    configure_sensor()

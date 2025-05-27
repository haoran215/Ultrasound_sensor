# Minimal GUI Tool for Writing 0x0200 = 0x0001 to DYP Sensor
import tkinter as tk
from tkinter import ttk, messagebox
import serial
import struct
import time

def modbus_crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder='little')

def build_modbus_write(addr, reg, value):
    cmd = struct.pack('>B B H H', addr, 0x06, reg, value)
    return cmd + modbus_crc16(cmd)

class DYPWriteTest:
    def __init__(self, root):
        self.root = root
        root.title("DYP Address Write Test Tool")

        self.port_var = tk.StringVar(value="COM12")
        self.addr_var = tk.StringVar(value="01")

        ttk.Label(root, text="Serial Port:").grid(row=0, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.port_var, width=10).grid(row=0, column=1)

        ttk.Label(root, text="Sensor Address (hex):").grid(row=1, column=0, sticky="e")
        ttk.Entry(root, textvariable=self.addr_var, width=5).grid(row=1, column=1)

        self.log = tk.Text(root, height=10, width=50)
        self.log.grid(row=3, column=0, columnspan=2, padx=10, pady=5)

        ttk.Button(root, text="Write Address (0x0200 = 0x0001)", command=self.send_command).grid(row=2, column=0, columnspan=2, pady=10)

    def send_command(self):
        port = self.port_var.get()
        try:
            addr = int(self.addr_var.get(), 16)
        except ValueError:
            messagebox.showerror("Error", "Invalid address format")
            return

        try:
            with serial.Serial(port, 9600, timeout=0.5) as ser:
                cmd = build_modbus_write(addr, 0x0200, 0x0001)
                self.log.insert(tk.END, f"[TX] {cmd.hex().upper()}\n")
                ser.write(cmd)
                time.sleep(0.1)
                resp = ser.read(8)
                if resp:
                    self.log.insert(tk.END, f"[RX] {resp.hex().upper()}\n")
                    if resp[:6] == cmd[:6]:
                        self.log.insert(tk.END, "✅ Sensor responded correctly.\n\n")
                    else:
                        self.log.insert(tk.END, "⚠️ Response mismatch.\n\n")
                else:
                    self.log.insert(tk.END, "❌ No response received.\n\n")
        except Exception as e:
            self.log.insert(tk.END, f"[ERROR] {e}\n")

if __name__ == '__main__':
    root = tk.Tk()
    app = DYPWriteTest(root)
    root.mainloop()

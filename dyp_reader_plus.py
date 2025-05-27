# DYP Multi-Channel GUI with Angle and Denoise Setting + Config Persistence
import serial
import struct
import time
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import csv
import json
import os
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import statistics

CONFIG_FILE = "sensor_config.json"

# --- CRC16 for Modbus ---
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

# --- Write register ---
def build_modbus_write(addr, reg, value):
    cmd = struct.pack('>B B H H', addr, 0x06, reg, value)
    return cmd + modbus_crc16(cmd)

import serial.tools.list_ports

PORT = None  # dynamic selection
BAUD = 115200
POLL_INTERVAL = 0.2
CHANNEL_LABELS = ["Channel 1", "Channel 2", "Channel 3", "Channel 4"]
DISTANCE_THRESHOLD = 2000

class MultiChannelApp:
    def __init__(self, root):
        self.log_file = open("debug_log.txt", "a")
        self.root = root
        self.root.title("DYP Multi-Channel Sensor Monitor")
        self.serial = None
        self.running = False
        self.smooth_enabled = tk.BooleanVar(value=False)
        self.smooth_window = tk.IntVar(value=5)
        self.angle_level_var = tk.StringVar(value="2")
        self.denoise_level_var = tk.StringVar(value="2")
        self.active_channels = {label: tk.BooleanVar(value=True) for label in CHANNEL_LABELS}
        self.data_vars = {}
        self.std_vars = {}
        self.history = {label: deque(maxlen=50) for label in CHANNEL_LABELS}
        self.csv_file = open(f"sensor_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["Time"] + CHANNEL_LABELS)
        self.build_gui()
        self.setup_plot()
        if self.open_serial():
            self.load_config()

    def build_gui(self):
        # Serial port selector
        self.port_var = tk.StringVar()
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_var.set(ports[0] if ports else "")
        ttk.Label(self.root, text="Serial Port:").grid(column=0, row=99, sticky="e")
        self.port_menu = ttk.Combobox(self.root, textvariable=self.port_var, values=ports, width=10)
        self.port_menu.grid(column=1, row=99, sticky="w")
        frm = ttk.Frame(self.root, padding=20)
        frm.grid()

        ttk.Button(frm, text="Start", command=self.start).grid(column=0, row=0, pady=10)
        ttk.Button(frm, text="Stop", command=self.stop).grid(column=1, row=0, pady=10)
        ttk.Checkbutton(frm, text="Enable Smoothing", variable=self.smooth_enabled).grid(column=2, row=0)
        ttk.Label(frm, text="Window Size:").grid(column=3, row=0)
        ttk.Entry(frm, textvariable=self.smooth_window, width=5).grid(column=4, row=0)

        for i, label in enumerate(CHANNEL_LABELS):
            ttk.Label(frm, text=label).grid(column=0, row=i+1, sticky="e")
            val = tk.StringVar(value="--- mm")
            std = tk.StringVar(value="Std: ---")
            self.data_vars[label] = val
            self.std_vars[label] = std
            ttk.Label(frm, textvariable=val, font=("Arial", 14)).grid(column=1, row=i+1, sticky="w")
            ttk.Label(frm, textvariable=std).grid(column=2, row=i+1, sticky="w")
            ttk.Checkbutton(frm, text="Active", variable=self.active_channels[label]).grid(column=3, row=i+1)

        ttk.Label(frm, text="Angle Level:").grid(column=0, row=6, sticky="e")
        angle_menu = ttk.Combobox(frm, values=["1", "2", "3", "4"], textvariable=self.angle_level_var, width=5)
        angle_menu.grid(column=1, row=6, sticky="w")

        ttk.Label(frm, text="Denoise Level:").grid(column=2, row=6, sticky="e")
        denoise_menu = ttk.Combobox(frm, values=["1", "2", "3", "4", "5"], textvariable=self.denoise_level_var, width=5)
        denoise_menu.grid(column=3, row=6, sticky="w")

        ttk.Button(frm, text="Apply Settings", command=self.apply_sensor_settings).grid(column=4, row=6)
        ttk.Button(frm, text="Save Config", command=self.save_config).grid(column=0, row=7, pady=10)
        ttk.Button(frm, text="Load Config", command=self.load_config).grid(column=1, row=7, pady=10)

    def setup_plot(self):
        self.fig, self.ax = plt.subplots()
        self.lines = {label: self.ax.plot([], [], label=label)[0] for label in CHANNEL_LABELS}
        self.ax.set_xlim(0, 50)
        self.ax.set_ylim(0, 1000)
        self.ax.set_title("Distance over Time (mm)")
        self.ax.set_xlabel("Samples")
        self.ax.set_ylabel("Distance (mm)")
        self.ax.legend()
        self.ani = animation.FuncAnimation(self.fig, self.update_plot, interval=500, cache_frame_data=False)

    def update_plot(self, frame):
        for label, line in self.lines.items():
            if self.active_channels[label].get():
                data = list(self.history[label])
                if self.smooth_enabled.get() and len(data) >= self.smooth_window.get():
                    w = self.smooth_window.get()
                    smoothed = [sum(data[max(0,i-w+1):i+1])//len(data[max(0,i-w+1):i+1]) for i in range(len(data))]
                    line.set_data(range(len(smoothed)), smoothed)
                else:
                    line.set_data(range(len(data)), data)
            else:
                line.set_data([], [])
        return list(self.lines.values())

    def open_serial(self):
        global PORT
        PORT = self.port_var.get()
        try:
            self.serial = serial.Serial(PORT, BAUD, timeout=0.3)
            return True
        except Exception as e:
            messagebox.showerror("Serial Error", str(e))
            return False

    def write_modbus_register(self, addr, reg, value):
        if self.log_file:
            self.log_file.write(f"[WRITE] Addr={addr:#04x} Reg={reg:#06x} Value={value:#06x}")
        if not self.serial:
            messagebox.showerror("Serial Error", "Serial port not opened.")
            return False
        cmd = build_modbus_write(addr, reg, value)
        print(f"[WRITE] {cmd.hex().upper()}")
        if self.log_file:
            self.log_file.write(f"[CMD] {cmd.hex().upper()}")
        try:
            self.serial.write(cmd)
            time.sleep(0.05)
            resp = self.serial.read(8)
            if not resp:
                print("[TIMEOUT] No response received.")
                return False
            print(f"[RECV]  {resp.hex().upper()}")
            if self.log_file:
                self.log_file.write(f"[RECV] {resp.hex().upper()}")
            return resp[:6] == cmd[:6]
        except Exception as e:
            print(f"[ERROR] Serial write error: {e}")
            return False

    def apply_sensor_settings(self):
        self.status_vars = [tk.StringVar(value="Pending") for _ in range(4)]
        for i, status_var in enumerate(self.status_vars):
            ttk.Label(self.root, textvariable=status_var).grid(column=5, row=i+1, sticky="w")

        def task():
            self.running = False
            time.sleep(0.5)  # Ensure read loop has exited
            angle = int(self.angle_level_var.get())
            denoise = int(self.denoise_level_var.get())
            if not self.serial:
                messagebox.showerror("Serial Error", "Serial port not opened.")
                return

            success = True
            addresses = [0x01, 0x02, 0x03, 0x04]

            for i, addr in enumerate(addresses):
                print(f"--- Writing Settings to Sensor {i+1} (Address {addr:#04x}) ---")
                retry = 3
                while retry > 0:
                    ok1 = self.write_modbus_register(addr, 0x0208, angle)
                    time.sleep(0.1)
                    ok2 = self.write_modbus_register(addr, 0x021A, denoise)
                    time.sleep(0.3)
                    if ok1 and ok2:
                        self.status_vars[i].set("✅ Success")
                        break
                    else:
                        retry -= 1
                        print(f"Retrying sensor {i+1}...")
                if retry == 0:
                    self.status_vars[i].set("❌ Failed")
                    success = False

            self.running = True
            threading.Thread(target=self.read_loop, daemon=True).start()

            if success:
                messagebox.showinfo("Finished", "Settings applied to all sensors.")
            else:
                messagebox.showerror("Error", "Some settings may have failed.")

        threading.Thread(target=task, daemon=True).start()

    def save_config(self):
        config = {
            "angle": self.angle_level_var.get(),
            "denoise": self.denoise_level_var.get(),
            "smooth": self.smooth_enabled.get(),
            "window": self.smooth_window.get(),
            "active": {k: v.get() for k, v in self.active_channels.items()}
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        messagebox.showinfo("Config Saved", "Sensor configuration saved successfully.")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                self.angle_level_var.set(config.get("angle", "2"))
                self.denoise_level_var.set(config.get("denoise", "2"))
                self.smooth_enabled.set(config.get("smooth", False))
                self.smooth_window.set(config.get("window", 5))
                for k, v in config.get("active", {}).items():
                    if k in self.active_channels:
                        self.active_channels[k].set(v)

    def read_channels(self):
        cmd = struct.pack('>B B H H', 0x02, 0x03, 0x0106, 0x0004)  # Read from 0x0106 on address 0x02
        cmd += modbus_crc16(cmd)
        self.serial.write(cmd)
        time.sleep(0.02)
        resp = self.serial.read(13)
        
        if len(resp) == 13 and resp[0] == 0x02 and resp[1] == 0x03:
            return [(resp[3+i*2] << 8 | resp[4+i*2]) if (resp[3+i*2] << 8 | resp[4+i*2]) <= DISTANCE_THRESHOLD else 0 for i in range(4)]
        return None

    def read_loop(self):
        while self.running:
            dists = self.read_channels()
            row = [datetime.now().strftime("%H:%M:%S")]
            for i, label in enumerate(CHANNEL_LABELS):
                if self.active_channels[label].get():
                    dist = dists[i] if dists else 0
                    self.data_vars[label].set(f"{dist} mm" if dist > 0 else "--- mm")
                    self.history[label].append(dist)
                    if len(self.history[label]) >= 3:
                        stdv = statistics.stdev(list(self.history[label])[-self.smooth_window.get():])
                        self.std_vars[label].set(f"Std: {stdv:.1f}")
                    else:
                        self.std_vars[label].set("Std: ---")
                    row.append(dist)
                else:
                    self.data_vars[label].set("Inactive")
                    self.std_vars[label].set("Std: ---")
                    row.append("")
            self.csv_writer.writerow(row)
            self.csv_file.flush()
            time.sleep(POLL_INTERVAL)

    def start(self):
        if not self.open_serial(): return
        self.running = True
        threading.Thread(target=self.read_loop, daemon=True).start()
        plt.ion()
        self.fig.show()

    def stop(self):
        self.running = False

    def close(self):
        if self.log_file:
            self.log_file.close()
        self.stop()
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.csv_file.close()
        self.root.quit()

if __name__ == '__main__':
    root = tk.Tk()
    app = MultiChannelApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()

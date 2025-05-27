import serial
import struct
import time
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import csv
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
import statistics

# --- Modbus CRC16 calculation ---
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

# --- Build Modbus RTU command ---
def build_modbus_command(addr=0x01, reg_addr=0x0106, reg_count=0x0004):
    cmd = struct.pack('>B B H H', addr, 0x03, reg_addr, reg_count)
    crc = modbus_crc16(cmd)
    return cmd + crc

# --- Configuration ---
PORT = "COM13"
BAUD = 9600
POLL_INTERVAL = 0.2
CHANNEL_LABELS = ["Channel 1", "Channel 2", "Channel 3", "Channel 4"]
DISTANCE_THRESHOLD = 2000  # mm

# --- GUI App ---
class MultiChannelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DYP Multi-Channel Sensor Monitor")
        self.serial = None
        self.running = False
        self.smooth_enabled = tk.BooleanVar(value=False)
        self.smooth_window = tk.IntVar(value=5)
        self.active_channels = {label: tk.BooleanVar(value=True) for label in CHANNEL_LABELS}
        self.data_vars = {}
        self.std_vars = {}
        self.history = {label: deque(maxlen=50) for label in CHANNEL_LABELS}
        self.csv_file = open(f"sensor_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["Time"] + CHANNEL_LABELS)
        self.build_gui()
        self.setup_plot()

    def build_gui(self):
        frm = ttk.Frame(self.root, padding=20)
        frm.grid()

        ttk.Button(frm, text="Start", command=self.start).grid(column=0, row=0, pady=10)
        ttk.Button(frm, text="Stop", command=self.stop).grid(column=1, row=0, pady=10)
        ttk.Checkbutton(frm, text="Enable Smoothing", variable=self.smooth_enabled).grid(column=2, row=0, padx=10)
        ttk.Label(frm, text="Window Size:").grid(column=3, row=0, sticky="e")
        ttk.Entry(frm, textvariable=self.smooth_window, width=5).grid(column=4, row=0, sticky="w")

        for i, label in enumerate(CHANNEL_LABELS):
            ttk.Label(frm, text=label, font=("Arial", 12)).grid(column=0, row=i+1, sticky="e")
            val = tk.StringVar(value="--- mm")
            std = tk.StringVar(value="Std: ---")
            self.data_vars[label] = val
            self.std_vars[label] = std
            ttk.Label(frm, textvariable=val, font=("Arial", 14)).grid(column=1, row=i+1, sticky="w")
            ttk.Label(frm, textvariable=std).grid(column=2, row=i+1, sticky="w")
            ttk.Checkbutton(frm, text="Active", variable=self.active_channels[label]).grid(column=3, row=i+1, padx=10)

    def setup_plot(self):
        self.fig, self.ax = plt.subplots()
        self.lines = {
            label: self.ax.plot([], [], label=label)[0] for label in CHANNEL_LABELS
        }
        self.ax.set_xlim(0, 50)
        self.ax.set_ylim(0, 1500)
        self.ax.set_title("Distance over Time (mm)")
        self.ax.set_xlabel("Samples")
        self.ax.set_ylabel("Distance (mm)")
        self.ax.legend()
        self.ani = animation.FuncAnimation(self.fig, self.update_plot, interval=500)

    def update_plot(self, frame):
        for label, line in self.lines.items():
            if self.active_channels[label].get():
                data = list(self.history[label])
                if self.smooth_enabled.get() and len(data) >= self.smooth_window.get():
                    window = self.smooth_window.get()
                    smoothed = [sum(data[max(0, i-window+1):i+1])//len(data[max(0, i-window+1):i+1]) for i in range(len(data))]
                    line.set_data(range(len(smoothed)), smoothed)
                else:
                    line.set_data(range(len(data)), data)
            else:
                line.set_data([], [])
        return list(self.lines.values())

    def open_serial(self):
        try:
            self.serial = serial.Serial(PORT, BAUD, timeout=0.3)
            return True
        except Exception as e:
            messagebox.showerror("Serial Error", f"Failed to open {PORT}: {e}")
            return False

    def read_channels(self):
        cmd = build_modbus_command()
        self.serial.write(cmd)
        time.sleep(0.02)
        response = self.serial.read(13)
        if len(response) == 13 and response[0] == 0x01 and response[1] == 0x03:
            values = []
            for i in range(4):
                high = response[3 + i * 2]
                low = response[4 + i * 2]
                dist = (high << 8) + low
                if dist > DISTANCE_THRESHOLD:
                    dist = 0
                values.append(dist)
            return values
        return None

    def read_loop(self):
        while self.running:
            distances = self.read_channels()
            row = [datetime.now().strftime("%H:%M:%S")]
            if distances:
                for i, label in enumerate(CHANNEL_LABELS):
                    if self.active_channels[label].get():
                        dist = distances[i]
                        self.data_vars[label].set(f"{dist} mm" if dist > 0 else "--- mm")
                        self.history[label].append(dist)
                        if len(self.history[label]) >= 5:
                            std_val = statistics.stdev(list(self.history[label])[-self.smooth_window.get():])
                            self.std_vars[label].set(f"Std: {std_val:.1f}")
                        else:
                            self.std_vars[label].set("Std: ---")
                        row.append(dist)
                    else:
                        self.data_vars[label].set("Inactive")
                        self.std_vars[label].set("Std: ---")
                        row.append("")
            else:
                for label in CHANNEL_LABELS:
                    self.data_vars[label].set("--- mm")
                    self.history[label].append(0)
                    self.std_vars[label].set("Std: ---")
                    row.append("")
            self.csv_writer.writerow(row)
            self.csv_file.flush()
            time.sleep(POLL_INTERVAL)

    def start(self):
        if not self.open_serial():
            return
        self.running = True
        self.read_thread = threading.Thread(target=self.read_loop, daemon=True)
        self.read_thread.start()
        plt.ion()
        self.fig.show()

    def stop(self):
        self.running = False

    def close(self):
        self.stop()
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.csv_file.close()
        self.root.quit()

# --- Launch the app ---
def launch_app():
    root = tk.Tk()
    app = MultiChannelApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()

launch_app()

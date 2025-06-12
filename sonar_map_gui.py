import serial
import struct
import tkinter as tk
from tkinter import messagebox
from math import radians
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- CRC and command utils ---

def modbus_crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            lsb = crc & 0x0001
            crc >>= 1
            if lsb:
                crc ^= 0xA001
    return crc.to_bytes(2, byteorder="little")


def build_modbus_command(addr: int = 0x01, reg_addr: int = 0x0106, reg_count: int = 0x0004) -> bytes:
    cmd = struct.pack('>B B H H', addr, 0x03, reg_addr, reg_count)
    return cmd + modbus_crc16(cmd)


class SonarMapApp:
    """Live GUI displaying sonar distances on a polar plot."""

    def __init__(self, root: tk.Tk, port: str = "COM13", baud: int = 9600):
        self.root = root
        self.root.title("Sonar Map")
        self.port = port
        self.baud = baud
        self.serial = None

        self.angles_deg = [0, 90, 180, 270]
        self.angles_rad = [radians(a) for a in self.angles_deg]
        self.dists = [0] * 4

        self.build_gui()
        if self.open_serial():
            self.update_loop()

    # --- GUI setup ---
    def build_gui(self) -> None:
        fig = plt.Figure(figsize=(5, 5))
        self.ax = fig.add_subplot(111, projection="polar")
        self.ax.set_ylim(0, 1500)
        self.ax.set_theta_zero_location("N")
        self.ax.set_theta_direction(-1)
        self.scat = self.ax.scatter(self.angles_rad, self.dists, c="b", s=50)
        self.lines = [self.ax.plot([ang, ang], [0, d], c="b")[0] for ang, d in zip(self.angles_rad, self.dists)]

        canvas = FigureCanvasTkAgg(fig, master=self.root)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas = canvas

    # --- Serial helpers ---
    def open_serial(self) -> bool:
        try:
            self.serial = serial.Serial(self.port, self.baud, timeout=0.3)
            return True
        except Exception as e:
            messagebox.showerror("Serial Error", f"Failed to open {self.port}: {e}")
            return False

    def read_distances(self):
        cmd = build_modbus_command()
        self.serial.write(cmd)
        self.serial.flush()
        self.serial.timeout = 0.3
        resp = self.serial.read(13)
        if len(resp) == 13 and resp[0] == 0x01 and resp[1] == 0x03:
            vals = []
            for i in range(4):
                high = resp[3 + i * 2]
                low = resp[4 + i * 2]
                vals.append((high << 8) + low)
            return vals
        return None

    def update_loop(self) -> None:
        vals = self.read_distances()
        if vals:
            self.dists = vals
            self.scat.set_offsets(list(zip(self.angles_rad, self.dists)))
            for line, angle, dist in zip(self.lines, self.angles_rad, self.dists):
                line.set_data([angle, angle], [0, dist])
            self.ax.set_ylim(0, max(1500, max(self.dists) + 100))
            self.canvas.draw()
        self.root.after(200, self.update_loop)

    def close(self) -> None:
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.root.quit()


if __name__ == "__main__":
    root = tk.Tk()
    app = SonarMapApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()

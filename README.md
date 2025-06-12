# Ultrasound Sensor Utilities

This repository collects Python scripts for interfacing with DYP-E08 ultrasonic sensors over a serial connection.  The tools provide GUIs for reading distance measurements, configuring sensor parameters and visualising data in real time.

## Setup

1. Ensure Python 3.8 or later is available on your Raspberry Pi.
2. For the graphical interfaces install Tkinter:
   ```bash
   sudo apt-get install python3-tk
   ```
3. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

## Applications

- `dyp_uart_reader.py` &ndash; basic multi-channel monitor with live plots.
- `dyp_reader_plus.py` &ndash; extended monitor allowing angle/denoise configuration and saving settings.
- `sonar_map_gui.py` &ndash; displays a polar sonar map of the four channels.
- `utils/` contains helper scripts for low level register writes.

Run a script with `python <script.py>` while the sensors are connected to the configured serial port (default `COM13`).  The notebook `plotter.ipynb` shows how to analyse logged data using pandas and SciPy.

## License

This project is distributed under the MIT License.

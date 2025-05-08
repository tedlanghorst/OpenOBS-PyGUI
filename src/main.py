import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import serial
import serial.tools.list_ports
import time
import datetime
import threading
import subprocess
import sys
from tkcalendar import DateEntry # Only DateEntry is needed from tkcalendar
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import pandas as pd
import matplotlib.colors as mcolors

# Constants (from VB code)
CONTINUOUS_CURRENT = 2.0
ON_CURRENT = 10.8
OFF_CURRENT = 0.05
ON_TIME = 0.96
TEXT_COLUMNS = 60 # Adjusted for typical Python font widths


def wavelength_to_rgb(wavelength):
    """Convert a wavelength in nm to an approximate RGB color."""
    gamma = 0.8
    intensity_max = 255
    factor = 0.0
    R = G = B = 0

    if 380 <= wavelength < 440:
        R = -(wavelength - 440) / (440 - 380)
        G = 0.0
        B = 1.0
    elif 440 <= wavelength < 490:
        R = 0.0
        G = (wavelength - 440) / (490 - 440)
        B = 1.0
    elif 490 <= wavelength < 510:
        R = 0.0
        G = 1.0
        B = -(wavelength - 510) / (510 - 490)
    elif 510 <= wavelength < 580:
        R = (wavelength - 510) / (580 - 510)
        G = 1.0
        B = 0.0
    elif 580 <= wavelength < 645:
        R = 1.0
        G = -(wavelength - 645) / (645 - 580)
        B = 0.0
    elif 645 <= wavelength <= 780:
        R = 1.0
        G = 0.0
        B = 0.0
    
    # Let the intensity fall off near the vision limits
    if 380 <= wavelength < 420:
        factor = 0.3 + 0.7 * (wavelength - 380) / (420 - 380)
    elif 420 <= wavelength < 645:
        factor = 1.0
    elif 645 <= wavelength <= 780:
        factor = 0.3 + 0.7 * (780 - wavelength) / (780 - 645)

    R = round(intensity_max * (R * factor)**gamma)
    G = round(intensity_max * (G * factor)**gamma)
    B = round(intensity_max * (B * factor)**gamma)

    return (R / 255, G / 255, B / 255)


class OpenOBSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OpenOBS Python GUI")
        # Set an icon for the popup window
        self.iconbitmap('sensorIcon.ico')
        # self.geometry("950x600") # Adjust as needed

        # --- Member Variables ---
        self.serial_port = serial.Serial()
        self.connected = False
        self.serial_thread = None
        self.stop_thread = False
        self.sensor_type = None
        # Store interval settings separately
        self.interval_setting_hour = tk.IntVar(value=0)
        self.interval_setting_min = tk.IntVar(value=0)
        self.interval_setting_sec = tk.IntVar(value=5) # Default interval 5s
        self.battery_mah = tk.IntVar(value=2000)
        self.custom_battery_mah = tk.StringVar(value="2000")
        self.column_headers = []
        self.debug_mode = tk.BooleanVar(value=False)  # Add debug mode variable
        
        # File logging attributes
        self.log_file_path = None
        self.is_logging_to_file = False
        self.log_file_object = None

        self.as7265x_bands = [410, 435, 460, 485, 510, 535, 560, 585, 610, 645, 680, 705, 730, 760, 810, 860, 900, 940]
        self.data = {}
        self.time_series_df = pd.DataFrame()
        self.max_time_steps = 30

        # --- Style ---
        style = ttk.Style(self)
        style.configure('TButton', padding=6)
        style.configure('TLabel', padding=2)
        style.configure('TCheckbutton', padding=2)
        style.configure('TCombobox', padding=2)
        style.configure('TEntry', padding=2)

        # --- GUI Construction ---
        # Frame Organisation
        connection_frame = ttk.LabelFrame(self, text="Connection", padding=(10, 5))
        connection_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        file_logging_frame = ttk.LabelFrame(self, text="File Logging", padding=(10, 5))
        file_logging_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        settings_frame = ttk.LabelFrame(self, text="Settings", padding=(10, 5))
        settings_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        self.settings_frame = settings_frame  # Store settings frame for later use

        battery_frame = ttk.LabelFrame(self, text="Battery Estimation", padding=(10, 5))
        battery_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        # Replace the log_frame with a Notebook widget containing tabs for the log and plot
        notebook = ttk.Notebook(self)
        notebook.grid(row=0, column=1, rowspan=3, padx=10, pady=5, sticky="nsew")

        # Create a frame for the serial log tab
        log_tab = ttk.Frame(notebook)
        notebook.add(log_tab, text="Serial Log")

        # Initialize a frame for the plotting tab
        plot_tab = ttk.Frame(notebook)
        notebook.add(plot_tab, text="Plot")
        self.configure_plot_frames(plot_tab)

        # Move the serial log widget into the log_tab
        self.serial_log = scrolledtext.ScrolledText(log_tab, wrap=tk.WORD, height=25, width=TEXT_COLUMNS, state=tk.DISABLED)
        self.serial_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)


        # Configure grid expansions
        self.grid_rowconfigure(0, weight=0)  # connection_frame
        self.grid_rowconfigure(1, weight=0)  # file_logging_frame
        self.grid_rowconfigure(2, weight=1)  # settings_frame (optional)
        self.grid_rowconfigure(3, weight=0)  # battery_frame

        self.grid_columnconfigure(0, weight=0)  # left side (frames)
        self.grid_columnconfigure(1, weight=1)  # right side (notebook)

        # --- Connection Frame ---
        ttk.Label(connection_frame, text="COM Port:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.cb_ports = ttk.Combobox(connection_frame, width=10, state="readonly")
        self.cb_ports.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.cb_ports.bind("<<ComboboxSelected>>", self.on_port_select) # Optional: Handle selection change if needed
        self.cb_ports.bind("<Button-1>", self.update_ports_list) # Update list on dropdown click
        self.update_ports_list() # Initial population

        self.btn_connect = ttk.Button(connection_frame, text="Connect", command=self.toggle_connection)
        self.btn_connect.grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(connection_frame, text="OR").grid(row=0, column=3, padx=5, pady=5)

        self.btn_hex_send = ttk.Button(connection_frame, text="Upload .hex", command=self.send_hex_file)
        self.btn_hex_send.grid(row=0, column=4, padx=5, pady=5)

        ttk.Label(connection_frame, text="Serial No:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.tb_sn = ttk.Entry(connection_frame, width=10, state="readonly")
        self.tb_sn.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # --- Logging Frame ---
        self.btn_toggle_file_log = ttk.Button(file_logging_frame, text="Start Logging to File", command=self.toggle_file_logging)
        self.btn_toggle_file_log.pack(padx=5, pady=5, fill=tk.X)

        # --- Settings Frame ---
        # Reorganize Settings into Data Logger and Measurements
        data_logger_frame = ttk.LabelFrame(settings_frame, text="Data Logger", padding=(10, 5))
        data_logger_frame.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="ew")

        self.sensors_frame = ttk.LabelFrame(settings_frame, text="Sensors", padding=(10, 5))
        self.sensors_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew")

        self.btn_send_settings = ttk.Button(settings_frame, text="Send Settings", command=self.send_settings, state=tk.DISABLED)
        self.btn_send_settings.grid(row=2, column=0, columnspan=3, padx=5, pady=10, sticky='s') # Moved to settings frame

        # Sample Interval (Using Spinboxes)
        interval_group = ttk.Frame(data_logger_frame)
        interval_group.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        ttk.Label(interval_group, text="Sample Interval [HH:mm:ss]:").pack(side=tk.LEFT, padx=(0,2))

        self.spin_interval_h = tk.Spinbox(interval_group, from_=0, to=23, width=3, format="%02.0f", textvariable=self.interval_setting_hour, command=self.update_battery)
        self.spin_interval_h.pack(side=tk.LEFT)
        ttk.Label(interval_group, text=":").pack(side=tk.LEFT)
        self.spin_interval_m = tk.Spinbox(interval_group, from_=0, to=59, width=3, format="%02.0f", textvariable=self.interval_setting_min, command=self.update_battery)
        self.spin_interval_m.pack(side=tk.LEFT)
        ttk.Label(interval_group, text=":").pack(side=tk.LEFT)
        self.spin_interval_s = tk.Spinbox(interval_group, from_=0, to=59, width=3, format="%02.0f", textvariable=self.interval_setting_sec, command=self.update_battery)
        self.spin_interval_s.pack(side=tk.LEFT)

        # Store the Spinboxes in a list for easy enable/disable
        self.interval_spinboxes = [self.spin_interval_h, self.spin_interval_m, self.spin_interval_s]

        self.cb_continuous_var = tk.BooleanVar()
        self.cb_continuous = ttk.Checkbutton(data_logger_frame, text="Continuous (max freq.)", variable=self.cb_continuous_var, command=self.toggle_continuous)
        self.cb_continuous.grid(row=1, column=0, columnspan=3, padx=5, pady=2, sticky="w")

        # Delayed Start
        delay_group = ttk.Frame(data_logger_frame)
        delay_group.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        self.cb_delay_var = tk.BooleanVar()
        self.cb_delay = ttk.Checkbutton(delay_group, text="Delayed start:", variable=self.cb_delay_var, command=self.toggle_delay)
        self.cb_delay.pack(side=tk.LEFT, padx=(0,5))

        # Date Entry (requires tkcalendar)
        if DateEntry:
            self.dtp_start_date = DateEntry(delay_group, width=10, state=tk.DISABLED, date_pattern='MM/dd/yyyy')
            self.dtp_start_date.pack(side=tk.LEFT, padx=(5,0))
            self.dtp_start_date.bind("<<DateEntrySelected>>", lambda e: self.update_battery())
        else:
            self.dtp_start_date_str = tk.StringVar(value=datetime.date.today().strftime("%m/%d/%Y"))
            self.dtp_start_date_entry = ttk.Entry(delay_group, textvariable=self.dtp_start_date_str, width=10, state=tk.DISABLED)
            self.dtp_start_date_entry.pack(side=tk.LEFT, padx=(5,0))
            ttk.Label(delay_group, text="(MM/DD/YYYY)").pack(side=tk.LEFT, padx=(2,5))

        # Start Time Entry (Using Spinboxes)
        self.start_time_hour_var = tk.IntVar(value=datetime.datetime.now().hour)
        self.start_time_min_var = tk.IntVar(value=datetime.datetime.now().minute)

        self.spin_start_h = tk.Spinbox(delay_group, from_=0, to=23, width=3, format="%02.0f", state=tk.DISABLED, textvariable=self.start_time_hour_var, command=self.update_battery)
        self.spin_start_h.pack(side=tk.LEFT)
        ttk.Label(delay_group, text=":").pack(side=tk.LEFT)
        self.spin_start_m = tk.Spinbox(delay_group, from_=0, to=59, width=3, format="%02.0f", state=tk.DISABLED, textvariable=self.start_time_min_var, command=self.update_battery)
        self.spin_start_m.pack(side=tk.LEFT)
        # Store start time spinboxes for easy enable/disable
        self.start_time_spinboxes = [self.spin_start_h, self.spin_start_m]

        # Measurement Flags
        self.cb_ambient_light_var = tk.BooleanVar(value=True)
        self.cb_backscatter_var = tk.BooleanVar(value=True)
        self.cb_pressure_var = tk.BooleanVar(value=True)
        self.cb_temperature_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(self.sensors_frame, text="Ambient Light", variable=self.cb_ambient_light_var).pack(anchor="w")
        ttk.Checkbutton(self.sensors_frame, text="Backscatter", variable=self.cb_backscatter_var).pack(anchor="w")
        ttk.Checkbutton(self.sensors_frame, text="Pressure", variable=self.cb_pressure_var).pack(anchor="w")
        ttk.Checkbutton(self.sensors_frame, text="Temperature", variable=self.cb_temperature_var).pack(anchor="w")

        # LED Current
        # current_group = ttk.LabelFrame(settings_frame, text="LED Current (mA)")
        # current_group.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        # # Use Spinbox for LED current as well (like VB's NumericUpDown)
        # self.led_current_var = tk.IntVar(value=50)
        # self.nud_current = tk.Spinbox(current_group, from_=0, to=255, width=5, textvariable=self.led_current_var, command=self.update_battery) # Added command for immediate update
        # self.nud_current.pack(side=tk.LEFT, padx=5)
        # self.nud_current.delete(0, "end") # Not needed when using textvariable
        # self.nud_current.insert(0, "50") # Default value set by textvariable

        # --- Battery Frame ---
        ttk.Label(battery_frame, text="Battery configuration:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.cb_battery_type = ttk.Combobox(battery_frame, values=["2000 mAh Li-SOCL2", "800 mAh Li-ion", "Custom"], state="readonly", width=20)
        self.cb_battery_type.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.cb_battery_type.current(0)
        self.cb_battery_type.bind("<<ComboboxSelected>>", self.update_battery_config)

        self.lbl_capacity = ttk.Label(battery_frame, text="Capacity (mAh):")
        # self.lbl_capacity.grid(row=1, column=0, padx=5, pady=5, sticky="w") # Grid managed in update_battery_config
        self.tb_capacity_entry = ttk.Entry(battery_frame, textvariable=self.custom_battery_mah, width=8)
        self.tb_capacity_entry.bind("<KeyRelease>", lambda e: self.validate_and_update_battery()) # Update on key release
        # self.tb_capacity_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w") # Grid managed

        ttk.Label(battery_frame, text="Est. Battery Life [days]:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.tb_battery_life = ttk.Entry(battery_frame, width=8, state="readonly")
        self.tb_battery_life.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        self.update_battery_config() # Set initial state based on combobox default

        # Add Debug Mode Checkbox
        debug_frame = ttk.Frame(self)
        debug_frame.grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.cb_debug = ttk.Checkbutton(debug_frame, text="Debug Mode", variable=self.debug_mode)
        self.cb_debug.pack(anchor="w")

       


        # --- Initial State ---
    def update_ports_list(self, event=None):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.cb_ports['values'] = ports
        if ports:
            # Keep current selection if it's still valid, otherwise select first
            current_selection = self.cb_ports.get()
            if current_selection not in ports:
                try:
                    self.cb_ports.current(0)
                except tk.TclError: # Handle case where combobox might be empty initially
                    pass
        else:
            self.cb_ports.set('') # Clear if no ports

    def on_port_select(self, event=None):
        # If needed, handle actions when a port is explicitly selected
        pass

    def toggle_connection(self):
        if not self.connected:
            port = self.cb_ports.get()
            if not port:
                messagebox.showerror("Connection Error", "Please select a COM port.")
                return
            try:
                self.serial_port.port = port
                self.serial_port.baudrate = 250000
                self.serial_port.timeout = 0.1

                # Remove unnecessary DTR toggling and reduce delays
                self.serial_port.open()

                self.stop_thread = False
                self.serial_thread = threading.Thread(target=self.read_serial_data, daemon=True)
                self.serial_thread.start()

                self.btn_connect.config(text="Disconnect")
                self.log_text("Attempting connection...", "center")
                self.connected = True
                self.tb_sn.config(state=tk.NORMAL)
                self.tb_sn.delete(0, tk.END)
                self.tb_sn.config(state=tk.DISABLED)

            except serial.SerialException as e:
                messagebox.showerror("Connection Error", f"Failed to connect to {port}:\n{e}")
                self.log_text(f"Failed to connect to {port}", "center", "error")
                self.connected = False
                if self.serial_port.is_open:
                    self.serial_port.close()
        else:
            self.stop_thread = True
            if self.serial_thread and self.serial_thread.is_alive():
                self.serial_thread.join(timeout=1)
            if self.serial_port.is_open:
                try:
                    self.serial_port.close()
                except serial.SerialException as close_e:
                    self.log_text(f"Error closing port: {close_e}", "center", "error")

            self.btn_connect.config(text="Connect")
            self.connected = False
            self.log_text("Disconnected", "center")

    def toggle_continuous(self):
        is_continuous = self.cb_continuous_var.get()
        new_state = tk.DISABLED if is_continuous else tk.NORMAL

        # Enable/disable interval spinboxes
        for spinbox in self.interval_spinboxes:
            spinbox.config(state=new_state)

        if is_continuous:
            # Set spinboxes to 00:00:00
            self.interval_setting_hour.set(0)
            self.interval_setting_min.set(0)
            self.interval_setting_sec.set(0)
        else:
            # Restore previous non-zero setting if it was zeroed
            # Or just leave the vars as they were (user might have manually set to 0)
             if self.interval_setting_hour.get() == 0 and self.interval_setting_min.get() == 0 and self.interval_setting_sec.get() == 0:
                 # If currently 0, restore a default like 5s if user enables interval mode
                 self.interval_setting_sec.set(5)

        self.update_battery()

    def toggle_delay(self):
        is_delayed = self.cb_delay_var.get()
        new_state = tk.NORMAL if is_delayed else tk.DISABLED

        # Enable/disable Date Entry
        if DateEntry:
            self.dtp_start_date.configure(state=new_state)
        else:
            self.dtp_start_date_entry.config(state=new_state)

        # Enable/disable Time Spinboxes
        for spinbox in self.start_time_spinboxes:
            spinbox.config(state=new_state)

        if not is_delayed: # Reset to now if disabling delay
            now = datetime.datetime.now()
            if DateEntry:
                self.dtp_start_date.set_date(now.date())
            else:
                self.dtp_start_date_str.set(now.strftime("%m/%d/%Y"))
            self.start_time_hour_var.set(now.hour)
            self.start_time_min_var.set(now.minute)


        self.update_battery()

    def update_battery_config(self, event=None):
        selection = self.cb_battery_type.current() # Get index
        show_custom = (selection == 2)

        if show_custom:
            self.lbl_capacity.grid(row=1, column=0, padx=5, pady=5, sticky="w")
            self.tb_capacity_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        else:
            self.lbl_capacity.grid_remove()
            self.tb_capacity_entry.grid_remove()
            if selection == 0: # 2000 mAh
                self.battery_mah.set(2000)
            elif selection == 1: # 800 mAh
                self.battery_mah.set(800)

        self.update_battery()


    def validate_and_update_battery(self):
        """Validate custom capacity input and update battery life."""
        if self.cb_battery_type.current() == 2: # Only validate if custom is selected
            try:
                val = int(self.custom_battery_mah.get())
                if val > 0:
                    self.battery_mah.set(val)
                    self.tb_capacity_entry.config(foreground='black') # Valid input style
                else:
                    # Indicate error subtly, prevent calculation with invalid value
                    self.tb_capacity_entry.config(foreground='red')
                    return # Don't update battery with invalid value
            except ValueError:
                 # Indicate error subtly, prevent calculation with invalid value
                 self.tb_capacity_entry.config(foreground='red')
                 return # Don't update battery with invalid value

        self.update_battery() # Update if validation passed or not custom

    def send_settings(self):
        if not self.connected:
             messagebox.showwarning("Not Connected", "Connect to the device before sending settings.")
             return

        # Get current timestamp (Unix epoch seconds)
        current_time = int(time.time())

        # Get interval in seconds from Spinboxes
        measure_interval = 0
        if not self.cb_continuous_var.get():
            try:
                h = self.interval_setting_hour.get()
                m = self.interval_setting_min.get()
                s = self.interval_setting_sec.get()
                measure_interval = h * 3600 + m * 60 + s
            except tk.TclError: # Handle potential error if spinbox value is invalid somehow
                 messagebox.showerror("Input Error", "Invalid Sample Interval values.")
                 return

        # Get delay in seconds
        delay_start = self.get_delay_seconds()
        if delay_start is None: return # Error handled in get_delay_seconds

        # Build flags byte
        meas_bit_flags = 0
        if self.cb_ambient_light_var.get(): meas_bit_flags |= 1  # Bit 0
        if self.cb_backscatter_var.get():   meas_bit_flags |= 2  # Bit 1
        if self.cb_pressure_var.get():      meas_bit_flags |= 4  # Bit 2
        if self.cb_temperature_var.get():   meas_bit_flags |= 8  # Bit 3

        settings_str = f"SET,{current_time},{measure_interval},{int(delay_start)},{meas_bit_flags}"

        if self.sensor_type == "VCNL4010":
            # settings_str += f",{current}"
            pass

        if self.sensor_type == "AS7265X":
            current = self.led_current_var.get() 
            gain = self.gain_var.get()
            int_cycles = self.integration_cycles_var.get()

            settings_str += F",{current},{gain},{int_cycles}"
        
        self.send_serial_message(settings_str)
        self.log_text("Settings sent, awaiting confirmation...", "center")


    # --- Core Logic ---

    def get_delay_seconds(self):
        """Calculates the delay in seconds from now until the specified start time."""
        if not self.cb_delay_var.get():
            return 0

        try:
            # Get Date
            if DateEntry:
                start_date = self.dtp_start_date.get_date()
            else: # Fallback parser
                start_date = datetime.datetime.strptime(self.dtp_start_date_str.get(), "%m/%d/%Y").date()

            # Get Time from Spinboxes
            start_hour = self.start_time_hour_var.get()
            start_minute = self.start_time_min_var.get()
            start_time = datetime.time(start_hour, start_minute)

            # Combine Date and Time
            start_dt = datetime.datetime.combine(start_date, start_time)

            now_dt = datetime.datetime.now()
            delay_seconds = (start_dt - now_dt).total_seconds()

            if delay_seconds < 0:
                self.log_text("Warning: Delay start time is in the past. Delay set to 0.", "center", "error")
                return 0
            else:
                # Return as integer seconds (matching VB UInt32 expectation)
                return int(delay_seconds)

        except ValueError as e: # Catches date parsing errors
             messagebox.showerror("Input Error", f"Invalid date format for delayed start:\n{e}")
             return None # Indicate error
        except tk.TclError as e: # Catches errors getting spinbox values
            messagebox.showerror("Input Error", f"Invalid time value for delayed start:\n{e}")
            return None # Indicate error


    def calculate_checksum(self, sentence: str) -> str:
        """Calculates the NMEA-style checksum for a sentence."""
        checksum = 0
        for char in sentence:
            checksum ^= ord(char)
        return f"{checksum:02X}" # Format as two uppercase hex characters

    def validate_checksum(self, message: str) -> bool:
        """Validates the checksum of a received NMEA-style message."""
        if not message or '$' not in message or '*' not in message:
            return False

        try:
            start_idx = message.index('$')
            # Find last asterisk for checksum
            end_idx = message.rindex('*')

            if start_idx >= end_idx or end_idx + 3 > len(message):
                return False # Invalid structure or not enough chars for checksum

            sentence = message[start_idx + 1 : end_idx]
            expected_checksum = self.calculate_checksum(sentence)
            provided_checksum = message[end_idx + 1 : end_idx + 3]

            return expected_checksum.upper() == provided_checksum.upper()
        except ValueError:
            return False # index() or rindex() throws ValueError if char not found

    def send_serial_message(self, sentence: str):
        """Formats and sends a message over the serial port."""
        if not self.connected or not self.serial_port.is_open:
            self.log_text("Error: Cannot send, not connected.", "center", "error")
            return

        message = f"${sentence}*{self.calculate_checksum(sentence)}\r\n" # Add CR/LF termination
        try:
            self.serial_port.write(message.encode('ascii'))
            if self.debug_mode:
                # Log serial messages if debug mode is enabled
                self.log_text(f"Debug: Sent: {message.strip()}", "right", "debug")   # Log without CR/LF
        except serial.SerialException as e:
            self.log_text(f"Serial Write Error: {e}", "center", "error")
            # Consider attempting to disconnect/reconnect or notify user more strongly
            self.after(0, self.toggle_connection) # Attempt to reset connection state in main thread
        except Exception as e:
             self.log_text(f"Unexpected Send Error: {e}", "center", "error")


    def read_serial_data(self):
        """Runs in a separate thread to read data from serial port."""
        buffer = ""
        while not self.stop_thread:
            try:
                # Check connection status before reading
                if not self.serial_port.is_open:
                     if not self.stop_thread: # Avoid logging error if we are intentionally stopping
                         self.after(0, self.log_text, "Serial port closed unexpectedly.", "center", "error")
                         self.after(0, self.toggle_connection) # Attempt disconnect state change
                     break # Exit thread if port closed

                if self.serial_port.in_waiting > 0:
                    # Read available bytes, decode assuming ASCII (adjust if needed)
                    try:
                        data = self.serial_port.read(self.serial_port.in_waiting).decode('ascii', errors='ignore')
                        buffer += data
                    except serial.SerialException as read_err:
                        # Handle specific read errors (like device disconnect during read)
                         self.after(0, self.log_text, f"Serial Read Error: {read_err}", "center", "error")
                         self.after(0, self.toggle_connection) # Trigger disconnect logic
                         break # Exit thread on read error

                    # Process complete messages (terminated by newline)
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip() # Remove leading/trailing whitespace and CR
                        if line:
                            # Schedule GUI update from the main thread
                            self.after(0, self.process_received_message, line)

                # Small sleep to prevent busy-waiting and allow GUI thread processing
                time.sleep(0.05)

            except serial.SerialException as e:
                # Handle errors gracefully (e.g., device unplugged)
                 if not self.stop_thread: # Avoid logging error if we are intentionally stopping
                    self.after(0, self.log_text, f"Serial Exception: {e}", "center", "error")
                    self.after(0, self.toggle_connection) # Trigger disconnect logic in main thread
                 break # Exit thread on error
            except Exception as e:
                # Catch other potential errors
                if not self.stop_thread:
                    self.after(0, self.log_text, f"Unexpected Read Error: {e}", "center", "error")
                break # Exit thread

        # Final check on closing (ensure port closed if thread exits)
        if self.serial_port.is_open:
             try: self.serial_port.close()
             except: pass # Ignore errors on close


    def process_received_message(self, message: str):
        """Processes a complete message received from the serial port."""
        if self.debug_mode.get():
            self.log_text(f"Debug: {message}", "left", "debug")

        # Skip checksum validation for HEADERS and DATA messages
        if message.startswith("HEADERS") or message.startswith("DATA"):
            try:
                parts = message.split(',')
                if self.is_logging_to_file and self.log_file_object:
                    try:
                        self.log_file_object.write(','.join(parts[1:]) + "\n")
                        self.log_file_object.flush()
                    except IOError as e:
                        self.log_text(f"File logging error: {e}", "left", "error")
                        # Optionally stop logging or notify user more prominently
            except Exception as e:
                 self.log_text(f"Error parsing message '{message}': {e}", "left", "error")
        elif self.validate_checksum(message):
            try:
                start_idx = message.index('$')
                end_idx = message.rindex('*') # Use last '*' for robustness
                sentence = message[start_idx + 1 : end_idx]
                parts = sentence.split(',')
            except Exception as e:
                 self.log_text(f"Error parsing message '{message}': {e}", "left", "error")
        else:
            self.log_text(f"Invalid Checksum: {message}", "left", "error")


        if not parts: return # Ignore empty sentence

        command = parts[0].upper() # Make comparison case-insensitive
        if command == "OPENOBS":
            # Device sends serial number as handshake (Ex. $OPENOBS,446*50)
            self.connected = True # Confirm connection on valid OPENOBS
            self.log_text("Device handshake received.", "center")
            # Send acknowledgment back to the datalogger
            self.send_serial_message("OPENOBS")

            self.tb_sn.config(state=tk.NORMAL)
            self.tb_sn.delete(0, tk.END)
            self.tb_sn.insert(0, parts[1])
            self.tb_sn.config(state=tk.DISABLED)

        elif command == "SENSOR" or command == "READY":
            # Device sends sensor configuration type after handshake.
            if command == "READY":
                #For backwards compatibility
                self.sensor_type = "VCNL4010" 
            else:
                self.sensor_type = parts[1].strip()

            self.configure_sensor_settings()
            self.btn_send_settings.config(state=tk.NORMAL)
            self.log_text(f"Sensor configured: {self.sensor_type}", "center")
            self.log_text("Send settings when ready", "center")
            
        elif command == "SET" and len(parts) > 1 and parts[1].upper() == "SUCCESS":
            # Device sends $SET,SUCCESS*2D after receiving valid settings
            self.btn_send_settings.config(state=tk.DISABLED) # Disable after success
            self.log_text("Settings Received Successfully", "center")

        elif command == "FILE" and len(parts) > 1 and parts[1].upper() == "OPEN":
            # Device sends $FILE,OPEN,FILENAME.TXT*XX
            filename = parts[2] if len(parts) > 2 else "UNKNOWN"
            self.log_text(f"Logging to ({filename}) ", "center")
            self.log_text(f"--- Sample Readings ---", "center")

        elif command =="HEADERS":
            self.column_headers = parts[1:] # Store headers for later use
            self.log_text(f"Headers: {', '.join(self.column_headers)}", "center")

        elif command =="DATA":
            self.data = {k: float(p) for k, p in zip(self.column_headers, parts[1:])}

            new_df = pd.DataFrame(self.data, index=[0])
            if len(self.time_series_df) == 0:
                self.time_series_df = new_df
            else:
                self.time_series_df = pd.concat([self.time_series_df, new_df], ignore_index=True)
                if len(self.time_series_df) > self.max_time_steps:
                    self.time_series_df = self.time_series_df.iloc[1:]

            self.update_plot()  # Update the plot with the new data
            self.log_text(message)

        # Handle potential error messages
        elif command == "SDINIT" and len(parts) > 1 and parts[1] == "0":
            self.log_text("SD Card Error: Initialization failed!", "center", "error")
            self.log_text("Check for missing or corrupted SD card.", "center", "error")
        elif command == "CLKINIT" and len(parts) > 1 and parts[1] == "0":
            self.log_text("RTC Error: Clock initialization failed!", "center", "error")


    def update_battery(self):
        """Calculates and displays the estimated battery life."""
        try:
            current_batt_mah = self.battery_mah.get()
            if current_batt_mah <= 0:
                self.tb_battery_life.config(state=tk.NORMAL)
                self.tb_battery_life.delete(0, tk.END)
                self.tb_battery_life.insert(0, "N/A")
                self.tb_battery_life.config(state=tk.DISABLED)
                return

            # Calculate delay impact
            delay_seconds = self.get_delay_seconds()
            if delay_seconds is None: delay_seconds = 0 # Use 0 if there was an error getting delay

            # mAh consumed during delay (standby)
            delay_consumption_mah = OFF_CURRENT * (delay_seconds / 3600.0)
            remaining_mah_after_delay = current_batt_mah - delay_consumption_mah

            if remaining_mah_after_delay <= 0:
                 battery_days = 0.0 # Already depleted during delay
            else:
                # Calculate active cycle consumption
                if self.cb_continuous_var.get():
                    # Continuous mode - use the specific constant
                    average_consumption_ma = CONTINUOUS_CURRENT
                else:
                    # Interval mode - get interval from spinboxes
                    try:
                        h = self.interval_setting_hour.get()
                        m = self.interval_setting_min.get()
                        s = self.interval_setting_sec.get()
                        interval_seconds = h * 3600 + m * 60 + s
                    except tk.TclError:
                        interval_seconds = 0 # Cannot calculate if interval is invalid

                    if interval_seconds <= 0:
                         # Avoid division by zero, assume continuous if interval is zero/invalid
                         average_consumption_ma = CONTINUOUS_CURRENT
                    elif interval_seconds < ON_TIME: # Handle case where interval is shorter than on-time
                        average_consumption_ma = ON_CURRENT # Effectively always on
                    else:
                        off_time = interval_seconds - ON_TIME
                        # VB logic: Use continuous if offTime < 5s, otherwise weighted average
                        if off_time < 5: # Use continuous rate for very short off periods
                            average_consumption_ma = CONTINUOUS_CURRENT
                        else: # Weighted average for normal intervals
                            average_consumption_ma = ((ON_CURRENT * ON_TIME) + (OFF_CURRENT * off_time)) / interval_seconds

                # Calculate remaining life in hours, then days
                if average_consumption_ma > 0:
                    remaining_hours = remaining_mah_after_delay / average_consumption_ma
                    remaining_days = remaining_hours / 24.0
                else:
                    # If avg consumption is zero, life is infinite? Or N/A?
                    remaining_days = float('inf')

                # Add the delay period back in days
                total_days = remaining_days + (delay_seconds / 3600.0 / 24.0)
                battery_days = total_days


            # Display result
            self.tb_battery_life.config(state=tk.NORMAL)
            self.tb_battery_life.delete(0, tk.END)
            if battery_days == float('inf'):
                 self.tb_battery_life.insert(0, "Inf")
            else:
                 self.tb_battery_life.insert(0, f"{battery_days:.1f}")
            self.tb_battery_life.config(state=tk.DISABLED)

        except Exception as e:
            # Catch any calculation errors (e.g., parsing Spinbox value)
            self.tb_battery_life.config(state=tk.NORMAL)
            self.tb_battery_life.delete(0, tk.END)
            self.tb_battery_life.insert(0, "Error")
            self.tb_battery_life.config(state=tk.DISABLED)
            print(f"Error updating battery life: {e}") # Log error for debugging

    def send_hex_file(self):
        """Handles the .hex file upload process."""
        port = self.cb_ports.get()
        if not port:
            messagebox.showerror("Upload Error", "Please select a COM port.")
            return

        file_path = filedialog.askopenfilename(
            title="Select .hex file",
            filetypes=[("HEX files", "*.hex"), ("All files", "*.*")]
        )

        if not file_path:
            return  # User cancelled

        try:
            # Construct the avrdude command
            avrdude_command = [
                "avrdude",
                "-v",  # Verbose output
                "-patmega328p",  # Microcontroller type (adjust if needed)
                "-carduino",  # Programmer type
                f"-P{port}",  # Serial port
                "-b115200",  # Baud rate (adjust if needed)
                f"-Uflash:w:{file_path}:i"  # Write the .hex file to flash memory
            ]

            self.log_text(f"Uploading {file_path} to {port} using avrdude...", "center")

            # Run the avrdude command as a subprocess
            result = subprocess.run(avrdude_command, capture_output=True, text=True)

            if result.returncode == 0:
                self.log_text("Upload Complete!", "center")
                messagebox.showinfo("Upload Success", f"Successfully uploaded {file_path} to {port}.")
            else:
                self.log_text(f"Upload Failed: {result.stderr}", "center", "error")
                messagebox.showerror("Upload Failed", f"An error occurred during upload:\n{result.stderr}")

        except FileNotFoundError:
            messagebox.showerror("Upload Error", "avrdude not found. Please install it and try again.")
            self.log_text("Error: avrdude not found.", "center", "error")

        except Exception as e:
            messagebox.showerror("Upload Failed", f"An unexpected error occurred:\n{e}")
            self.log_text(f"Upload Failed: {e}", "center", "error")


    def log_text(self, message: str, justification: str = "left", tag: str = None):
        """Appends text to the serial log Text widget."""
        if not self.debug_mode.get() and tag == "debug":
            # Skip raw serial messages if debug mode is off
            return
        try:
            # Ensure widget exists and is valid before trying to modify
            if not self.serial_log.winfo_exists(): return

            self.serial_log.config(state=tk.NORMAL) # Enable writing
            line_break = '\n' # Always add a newline

            # Insert text with appropriate justification/tag
            if justification == "center":
                self.serial_log.insert(tk.END, message + line_break, ("center", tag) if tag else "center")
            elif justification == "right":
                self.serial_log.insert(tk.END, message + line_break, ("right", tag) if tag else "right")
            else: # Left (default)
                if tag:
                    self.serial_log.insert(tk.END, message + line_break, tag)
                else:
                    self.serial_log.insert(tk.END, message + line_break)

            # Apply red color for debug messages
            if tag == "debug":
                self.serial_log.tag_configure("debug", foreground="red")

            self.serial_log.see(tk.END) # Scroll to the bottom
            self.serial_log.config(state=tk.DISABLED) # Disable writing
            self.update_idletasks() # Ensure log updates immediately
        except tk.TclError as e:
            # Handle cases where the widget might be destroyed during shutdown
            print(f"Error updating log widget: {e}")
        except Exception as e:
            print(f"Unexpected error logging: {e}")

    def update_plot(self, event=None):
        """Updates the plot based on the selected type."""
        self.ax.clear()

        selected_plot = self.plot_type_var.get()
        if selected_plot == "Real-time spectrum":
            if self.spectrum_type_var.get() == "Ambient":
                self.update_ambient_light_plot()
            elif self.spectrum_type_var.get() == "Reflected":
                self.update_reflected_light_plot()

        elif selected_plot == "Time series":
            self.update_time_series_plot()

        self.fig.tight_layout()
        self.plot_canvas.draw()

    def configure_plot_frames(self, plot_tab):
        # """Configures dropdowns for plot type."""
        self.plot_controls_frame = ttk.Frame(plot_tab)
        self.plot_controls_frame.pack(fill=tk.X, padx=5, pady=5)

        self.plot_type_var = tk.StringVar(value="Real-time spectrum")
        self.plot_type_frame = ttk.Frame(self.plot_controls_frame)
        self.plot_type_frame.pack(side=tk.LEFT, fill=tk.X, expand=False, padx=(0, 10))

        ttk.Label(self.plot_type_frame, text="Select plot:").pack(side=tk.LEFT, padx=(0, 5))
        self.plot_type_menu = ttk.Combobox(
            self.plot_type_frame, textvariable=self.plot_type_var, state="readonly",
            values=["Real-time spectrum", "Time series"]
        )
        self.plot_type_menu.pack(side=tk.LEFT, expand=True)
        self.plot_type_menu.bind("<<ComboboxSelected>>", self.update_plot_selectors)

        self.plot_selectors_frame = ttk.Frame(self.plot_controls_frame)
        self.plot_selectors_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.update_plot_selectors()  # Initialize plot selectors
       
        # Create a matplotlib figure and axis and add it to the plot tab
        self.fig, self.ax = plt.subplots()#figsize=(8, 4))
        self.plot_canvas = FigureCanvasTkAgg(self.fig, master=plot_tab)
        self.plot_canvas_widget = self.plot_canvas.get_tk_widget()
        self.plot_canvas_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    
    def update_plot_selectors(self, event=None):
        for widget in self.plot_selectors_frame.winfo_children():
            widget.destroy()

        if self.plot_type_var.get() == "Real-time spectrum":
            self.spectrum_type_var = tk.StringVar(value="Ambient")
            self.spectrum_type_menu = ttk.Combobox(
                self.plot_selectors_frame, textvariable=self.spectrum_type_var, state="readonly",
                values=["Ambient", "Reflected"]
            )
            self.spectrum_type_menu.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.spectrum_type_menu.bind("<<ComboboxSelected>>", self.update_plot)

        elif self.plot_type_var.get() == "Time series":
            self.time_series_listbox = tk.Listbox(
                self.plot_selectors_frame,
                selectmode='multiple',  # or 'extended' for shift-click selection
                height=min(10, len(self.time_series_df.columns))  # Adjust height as needed
            )
            for col in self.time_series_df.columns:
                self.time_series_listbox.insert(tk.END, col)
            self.time_series_listbox.pack(side=tk.LEFT, fill=tk.NONE, expand=True)

            # Clear selections button
            ttk.Button(
                self.plot_selectors_frame,
                text="Clear Selections",
                command=lambda: self.time_series_listbox.selection_clear(0, tk.END)
            ).pack(fill=tk.X)


    def update_time_series_plot(self):
        """Updates the time series plot."""
        selected_indices = self.time_series_listbox.curselection()
        selected_vars = [self.time_series_df.columns[i] for i in selected_indices]

        self.ax.clear()
        self.ax.set_title("Time Series")
        self.ax.set_xlabel("Sample #")
        # self.ax.set_ylabel(var1)
        self.ax.grid(True, linestyle=":", alpha=0.6)

        x = self.time_series_df.index.to_numpy()

        for v in selected_vars:
            y = self.time_series_df[v].to_numpy()
            if len(x) > 0:
                self.ax.plot(x, y, linewidth=2, label=v)
                self.ax.set_xlim(max(0, x[-1] - 30), x[-1])
        plt.legend()
        self.plot_canvas.draw()

    def spectrum_plot(self, band_prefix):
        self.ax.clear()
        values = []
        for b in self.as7265x_bands:
            values.append(self.data[f'{band_prefix}{b}']/100) # Convert from uW/cm2 to W/m2

        fwhm = 30.0
        sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
        lambda_plot = np.linspace(350, 1000, 1000)
        full_spectrum = np.zeros_like(lambda_plot)

        for i, (mu_i, amplitude_i) in enumerate(zip(self.as7265x_bands, values)):
            channel_color = wavelength_to_rgb(mu_i)
            channel_contribution = amplitude_i * np.exp(-((lambda_plot - mu_i)**2) / (2 * sigma**2))
            full_spectrum += channel_contribution
            self.ax.plot(lambda_plot, channel_contribution, color=channel_color, linewidth=2, alpha=0.7)

        self.ax.plot(lambda_plot, full_spectrum, color='black', linewidth=2)
        
        
        self.ax.set_xlabel("Wavelength (nm)")
        self.ax.set_ylabel("Irradiance W/m²")
        self.ax.grid(True, linestyle=":", alpha=0.6)
        self.plot_canvas.draw()

    def update_ambient_light_plot(self):
        """Updates the ambient light spectrum plot."""
        self.spectrum_plot(band_prefix='A')
        self.ax.set_title("Ambient Light Spectrum")
        # self.ax.set_ylim(0, 1.8)


    def update_reflected_light_plot(self):
        """Updates the reflected light spectrum plot."""
        self.spectrum_plot(band_prefix='B') # B for backscatter
        self.ax.set_title("Reflected Light Spectrum")
        # self.ax.set_ylim(0, 1.8)

    def configure_sensor_settings(self):
        for widget in self.sensors_frame.winfo_children():
                widget.destroy()

        if self.sensor_type is None:
            return
        
        ttk.Checkbutton(self.sensors_frame, text="Ambient Light", variable=self.cb_ambient_light_var).grid(row=0, column=0, sticky='w')
        ttk.Checkbutton(self.sensors_frame, text="Backscatter", variable=self.cb_backscatter_var).grid(row=1, column=0, sticky='w')
        ttk.Checkbutton(self.sensors_frame, text="Pressure", variable=self.cb_pressure_var).grid(row=0, column=1, sticky='w')
        ttk.Checkbutton(self.sensors_frame, text="Temperature", variable=self.cb_temperature_var).grid(row=1, column=1, sticky='w')

        if self.sensor_type == "VCNL4010":
            """Configures the GUI for VCNL4010 sensor."""
            # Update measurement settings for VCNL4010

            # Show LED Current Entry for VCNL4010
            self.led_current_frame = ttk.LabelFrame(self, text="LED Current (mA)", padding=(10, 5))
            self.led_current_var = tk.IntVar(value=50)
            self.nud_current = tk.Spinbox(self.led_current_frame, from_=0, to=255, width=5, textvariable=self.led_current_var)
            self.nud_current.pack(anchor="w")


        elif self.sensor_type == "AS7265X":
            """Configures the GUI for AS7265X sensor."""
            # LED Current Dropdown
            self.led_current_var = tk.StringVar(value="25")
            ttk.Label(self.sensors_frame, text="LED Current (mA):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
            led_current_dropdown = ttk.Combobox(
                self.sensors_frame, 
                values=[12.5, 25, 50, 100], 
                textvariable=self.led_current_var, 
                state="readonly")
            led_current_dropdown.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

            # Gain Dropdown
            self.gain_var = tk.StringVar(value="1")
            ttk.Label(self.sensors_frame, text="Gain:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
            gain_dropdown = ttk.Combobox(
                self.sensors_frame, 
                values=[1, 3.7, 16, 64], 
                textvariable=self.gain_var, 
                state="readonly")
            gain_dropdown.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

            # Integration Cycles
            self.integration_cycles_var = tk.StringVar(value="16")
            ttk.Label(self.sensors_frame, text="Integration Cycles [0-255]:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
            integration_cycles_entry = ttk.Entry(self.sensors_frame, textvariable=self.integration_cycles_var)
            integration_cycles_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")

        else:
            # Handle unknown sensor type
            self.log_text(f"Unknown sensor type: {self.sensor_type}", "left", "error")
            self.btn_send_settings.config(state=tk.DISABLED)

    def toggle_file_logging(self):
        if not self.is_logging_to_file:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Log As"
            )
            if file_path:
                try:
                    self.log_file_object = open(file_path, "w")
                    self.log_file_path = file_path
                    self.is_logging_to_file = True
                    self.btn_toggle_file_log.config(text="Stop Logging to File")
                    self.log_text(f"Logging to file: {self.log_file_path}", "center", "info")
                except IOError as e:
                    messagebox.showerror("File Error", f"Could not open file for logging:\n{e}")
                    self.log_file_path = None
                    self.log_file_object = None
            else: # User cancelled
                return
        else:
            if self.log_file_object:
                try:
                    self.log_file_object.close()
                except IOError as e:
                    messagebox.showerror("File Error", f"Error closing log file:\n{e}")
            self.log_text(f"Stopped logging to file: {self.log_file_path}", "center", "info")
            self.is_logging_to_file = False
            self.log_file_object = None
            self.log_file_path = None
            self.btn_toggle_file_log.config(text="Start Logging to File")

    def on_closing(self):
        """Handles window close event."""
        self.stop_thread = True # Signal thread to stop
        if self.serial_thread and self.serial_thread.is_alive():
            self.serial_thread.join(timeout=0.5) # Wait briefly for thread
        if self.serial_port.is_open:
             try:
                 self.serial_port.close()
             except Exception as e:
                 print(f"Error closing serial port on exit: {e}")

        if self.is_logging_to_file and self.log_file_object:
            try:
                self.log_file_object.close()
                print(f"Closed log file: {self.log_file_path}")
            except IOError as e:
                print(f"Error closing log file on exit: {e}")

        self.destroy() # Close the Tkinter window

# --- Main Execution ---
if __name__ == "__main__":
    # Run the application
    app = OpenOBSApp()
    app.mainloop()
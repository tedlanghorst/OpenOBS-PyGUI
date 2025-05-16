import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import serial
import serial.tools.list_ports
import time
import datetime
from tkcalendar import DateEntry
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import subprocess

from util.serial_comm import SerialCommunicator
from util.test_comm import TestCommunicator
from sensors import make_sensor_obj
from plots import get_valid_plots
from calibrators import get_valid_calibrations

# Constants (from VB code)
CONTINUOUS_CURRENT = 2.0
ON_CURRENT = 10.8
OFF_CURRENT = 0.05
ON_TIME = 0.96
TEXT_COLUMNS = 60  # Adjusted for typical Python font widths
UPDATE_INTERVAL_MS = 100  # Adjust the interval as needed


class OpenOBSApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # Set a reasonable default size for the window and center it before drawing
        window_width = 1200
        window_height = 900
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.title("OpenOBS Python GUI")
        # Set an icon for the popup window
        self.iconbitmap("sensorIcon.ico")
        self.geometry(f"{window_width}x{window_height}")

        # --- Member Variables ---
        self.ser_com = SerialCommunicator(self.log_text, self.process_received_sentence)
        self.sensor_type = None
        self.sensor = None
        self.plot = None
        # Store interval settings separately
        self.interval_setting_hour = tk.IntVar(value=0)
        self.interval_setting_min = tk.IntVar(value=0)
        self.interval_setting_sec = tk.IntVar(value=5)  # Default interval 5s
        self.cb_continuous_var = tk.BooleanVar()
        self.cb_delay_var = tk.BooleanVar()
        self.battery_mah = tk.IntVar(value=2000)
        self.custom_battery_mah = tk.StringVar(value="2000")
        self.data_headers = []
        self.debug_mode = tk.BooleanVar(value=True)  # Add debug mode variable
        self.use_test_comm = tk.BooleanVar(
            value=False
        )  # Add TestCommunicator toggle variable

        # File logging attributes
        self.log_file_path = None
        self.is_logging_to_file = False
        self.log_file_object = None

        # --- Style ---
        style = ttk.Style(self)
        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=2)
        style.configure("TCheckbutton", padding=2)
        style.configure("TCombobox", padding=2)
        style.configure("TEntry", padding=2)

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
        # Make the serial log widget in the log_tab
        self.serial_log = scrolledtext.ScrolledText(
            log_tab, wrap=tk.WORD, height=25, width=TEXT_COLUMNS, state=tk.DISABLED
        )
        self.serial_log.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.serial_log.tag_configure("center", justify="center")
        self.serial_log.tag_configure("right", justify="right")
        self.serial_log.tag_configure("left", justify="left")
        self.serial_log.tag_configure("debug", foreground="orange")
        self.serial_log.tag_configure("error", foreground="red")

        # Initialize a frame for the plotting tab
        plot_tab = ttk.Frame(notebook)
        notebook.add(plot_tab, text="Plot")
        self.configure_plot_types(plot_tab)

        # Initialize a frame for the plotting tab
        calibrate_tab = ttk.Frame(notebook)
        notebook.add(calibrate_tab, text="Calibrate")
        self.configure_calibration_types(calibrate_tab)

        # Configure grid expansions
        self.grid_rowconfigure(0, weight=0)  # connection_frame
        self.grid_rowconfigure(1, weight=0)  # file_logging_frame
        self.grid_rowconfigure(2, weight=1)  # settings_frame (optional)
        self.grid_rowconfigure(3, weight=0)  # battery_frame

        self.grid_columnconfigure(0, weight=0)  # left side (frames)
        self.grid_columnconfigure(1, weight=1)  # right side (notebook)

        # --- Connection Frame ---
        ttk.Label(connection_frame, text="COM Port:").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.cb_ports = ttk.Combobox(connection_frame, width=10, state="readonly")
        self.cb_ports.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.cb_ports.bind(
            "<Button-1>", self.update_ports_list
        )  # Update list on dropdown click
        self.update_ports_list()  # Initial population

        self.btn_connect = ttk.Button(
            connection_frame, text="Connect", command=self.toggle_connection
        )
        self.btn_connect.grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(connection_frame, text="OR").grid(row=0, column=3, padx=5, pady=5)

        self.btn_hex_send = ttk.Button(
            connection_frame, text="Upload .hex", command=self.send_hex_file
        )
        self.btn_hex_send.grid(row=0, column=4, padx=5, pady=5)

        ttk.Label(connection_frame, text="Serial No:").grid(
            row=1, column=0, padx=5, pady=5, sticky="w"
        )
        self.tb_sn = ttk.Entry(connection_frame, width=10, state="readonly")
        self.tb_sn.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # --- Logging Frame ---
        self.btn_toggle_file_log = ttk.Button(
            file_logging_frame,
            text="Start Logging to File",
            command=self.toggle_file_logging,
        )
        self.btn_toggle_file_log.pack(padx=5, pady=5, fill=tk.X)

        # --- Settings Frame ---
        # Reorganize Settings into Data Logger and Measurements
        data_logger_frame = ttk.LabelFrame(
            settings_frame, text="Data Logger", padding=(10, 5)
        )
        data_logger_frame.grid(
            row=0, column=0, columnspan=3, padx=5, pady=5, sticky="ew"
        )

        self.sensors_frame = ttk.LabelFrame(
            settings_frame, text="Sensor", padding=(10, 5)
        )
        self.sensors_frame.grid(
            row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew"
        )

        self.btn_send_settings = ttk.Button(
            settings_frame,
            text="Send Settings",
            command=self.send_settings,
            state=tk.DISABLED,
        )
        self.btn_send_settings.grid(
            row=2, column=0, columnspan=3, padx=5, pady=10, sticky="s"
        )  # Moved to settings frame

        # Sample Interval (Using Spinboxes)
        interval_group = ttk.Frame(data_logger_frame)
        interval_group.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        ttk.Label(interval_group, text="Sample Interval [HH:mm:ss]:").pack(
            side=tk.LEFT, padx=(0, 2)
        )

        self.spin_interval_h = tk.Spinbox(
            interval_group,
            from_=0,
            to=23,
            width=3,
            format="%02.0f",
            textvariable=self.interval_setting_hour,
            command=self.update_battery,
        )
        self.spin_interval_h.pack(side=tk.LEFT)
        ttk.Label(interval_group, text=":").pack(side=tk.LEFT)
        self.spin_interval_m = tk.Spinbox(
            interval_group,
            from_=0,
            to=59,
            width=3,
            format="%02.0f",
            textvariable=self.interval_setting_min,
            command=self.update_battery,
        )
        self.spin_interval_m.pack(side=tk.LEFT)
        ttk.Label(interval_group, text=":").pack(side=tk.LEFT)
        self.spin_interval_s = tk.Spinbox(
            interval_group,
            from_=0,
            to=59,
            width=3,
            format="%02.0f",
            textvariable=self.interval_setting_sec,
            command=self.update_battery,
        )
        self.spin_interval_s.pack(side=tk.LEFT)

        # Store the Spinboxes in a list for easy enable/disable
        self.interval_spinboxes = [
            self.spin_interval_h,
            self.spin_interval_m,
            self.spin_interval_s,
        ]

        self.cb_continuous = ttk.Checkbutton(
            data_logger_frame,
            text="Continuous (max freq.)",
            variable=self.cb_continuous_var,
            command=self.toggle_continuous,
        )
        self.cb_continuous.grid(
            row=1, column=0, columnspan=3, padx=5, pady=2, sticky="w"
        )

        # Delayed Start
        delay_group = ttk.Frame(data_logger_frame)
        delay_group.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        self.cb_delay = ttk.Checkbutton(
            delay_group,
            text="Delayed start:",
            variable=self.cb_delay_var,
            command=self.toggle_delay,
        )
        self.cb_delay.pack(side=tk.LEFT, padx=(0, 5))

        # Date Entry (requires tkcalendar)
        self.dtp_start_date = DateEntry(
            delay_group, width=10, state=tk.DISABLED, date_pattern="MM/dd/yyyy"
        )
        self.dtp_start_date.pack(side=tk.LEFT, padx=(5, 0))
        self.dtp_start_date.bind(
            "<<DateEntrySelected>>", lambda e: self.update_battery()
        )

        # Start Time Entry (Using Spinboxes)
        self.start_time_hour_var = tk.IntVar(value=datetime.datetime.now().hour)
        self.start_time_min_var = tk.IntVar(value=datetime.datetime.now().minute)

        self.spin_start_h = tk.Spinbox(
            delay_group,
            from_=0,
            to=23,
            width=3,
            format="%02.0f",
            state=tk.DISABLED,
            textvariable=self.start_time_hour_var,
            command=self.update_battery,
        )
        self.spin_start_h.pack(side=tk.LEFT)
        ttk.Label(delay_group, text=":").pack(side=tk.LEFT)
        self.spin_start_m = tk.Spinbox(
            delay_group,
            from_=0,
            to=59,
            width=3,
            format="%02.0f",
            state=tk.DISABLED,
            textvariable=self.start_time_min_var,
            command=self.update_battery,
        )
        self.spin_start_m.pack(side=tk.LEFT)
        # Store start time spinboxes for easy enable/disable
        self.start_time_spinboxes = [self.spin_start_h, self.spin_start_m]

        # --- Battery Frame ---
        ttk.Label(battery_frame, text="Battery configuration:").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.cb_battery_type = ttk.Combobox(
            battery_frame,
            values=["2000 mAh Li-SOCL2", "800 mAh Li-ion", "Custom"],
            state="readonly",
            width=20,
        )
        self.cb_battery_type.grid(
            row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew"
        )
        self.cb_battery_type.current(0)
        self.cb_battery_type.bind("<<ComboboxSelected>>", self.update_battery_config)

        self.lbl_capacity = ttk.Label(battery_frame, text="Capacity (mAh):")
        self.tb_capacity_entry = ttk.Entry(
            battery_frame, textvariable=self.custom_battery_mah, width=8
        )
        self.tb_capacity_entry.bind(
            "<KeyRelease>", lambda e: self.validate_and_update_battery()
        )  # Update on key release

        ttk.Label(battery_frame, text="Est. Battery Life [days]:").grid(
            row=2, column=0, padx=5, pady=5, sticky="w"
        )
        self.tb_battery_life = ttk.Entry(battery_frame, width=8, state="readonly")
        self.tb_battery_life.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        self.update_battery_config()  # Set initial state based on combobox default

        # Add Debug Mode Checkbox
        debug_frame = ttk.Frame(self)
        debug_frame.grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.cb_debug = ttk.Checkbutton(
            debug_frame, text="Debug Mode", variable=self.debug_mode
        )
        self.cb_debug.pack(anchor="w")

        # Add a new checkbox for using TestCommunicator
        self.cb_use_test_comm = ttk.Checkbutton(
            debug_frame,
            text="Test without sensor",
            variable=self.use_test_comm,
            command=self.toggle_communicator,
        )
        self.cb_use_test_comm.pack(anchor="w")

        # Periodically process the data queue
        self.after(UPDATE_INTERVAL_MS, self.process_data_queue)

    def process_data_queue(self):
        """Process data from the serial communicator's queue."""
        queue_size = self.ser_com.data_queue.qsize()
        if queue_size > 50:  # Example threshold for a warning
            self.log_error(f"Warning: Serial queue size is high ({queue_size} items).")

        data_list = []
        while not self.ser_com.data_queue.empty():
            sentence = self.ser_com.data_queue.get()
            parts = sentence.split(",")

            if parts[0] != "DATA":
                self.log_error(f"Non data message passed to data queue: {sentence}")
                return

            data = {k: float(p) for k, p in zip(self.data_headers, parts[1:])}
            data_list.append(data)
            self.log_text(",".join(parts[1:]), "left")

        if data_list:
            self.plot.update(data_list)
            self.cal.update(data_list)

        # Schedule the next queue processing
        self.after(UPDATE_INTERVAL_MS, self.process_data_queue)

    def update_ports_list(self, event=None):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.cb_ports["values"] = ports
        if ports:
            # Keep current selection if it's still valid, otherwise select first
            current_selection = self.cb_ports.get()
            if current_selection not in ports:
                try:
                    self.cb_ports.current(0)
                except (
                    tk.TclError
                ):  # Handle case where combobox might be empty initially
                    pass
        else:
            self.cb_ports.set("")  # Clear if no ports

    def toggle_connection(self):
        if not self.ser_com.is_open:
            port = self.cb_ports.get()
            if not port:
                messagebox.showerror("Connection Error", "Please select a COM port.")
                return

            self.serial_log.config(state=tk.NORMAL)  # Enable writing
            self.serial_log.delete("1.0", tk.END)  # Clear log
            self.ser_com.open_connection(port)

            if self.ser_com.is_open:
                self.btn_connect.config(text="Disconnect")
                self.tb_sn.config(state=tk.NORMAL)
                self.tb_sn.delete(0, tk.END)
                self.tb_sn.config(state=tk.DISABLED)

                # Clear any leftover data in the serial queue
                while not self.ser_com.data_queue.empty():
                    self.ser_com.data_queue.get()

                # Start processing the data queue
                self.after(UPDATE_INTERVAL_MS, self.process_data_queue)

        else:
            self.ser_com.close_connection()
            if not self.ser_com.is_open:
                self.btn_connect.config(text="Connect")

                # Stop processing the data queue
                self.after_cancel(self.process_data_queue)

    def toggle_continuous(self):
        is_continuous = self.cb_continuous_var.get()
        new_state = tk.DISABLED if is_continuous else tk.NORMAL

        # Enable/disable interval spinboxes
        for spinbox in self.interval_spinboxes:
            spinbox.config(state=new_state)

        if is_continuous:
            self.interval_setting_hour.set(0)
            self.interval_setting_min.set(0)
            self.interval_setting_sec.set(0)
        else:
            # Restore previous non-zero setting if it was zeroed
            # Or just leave the vars as they were (user might have manually set to 0)
            if (
                self.interval_setting_hour.get() == 0
                and self.interval_setting_min.get() == 0
                and self.interval_setting_sec.get() == 0
            ):
                # If currently 0, restore a default like 5s if user enables interval mode
                self.interval_setting_sec.set(5)

        self.update_battery()

    def toggle_delay(self):
        is_delayed = self.cb_delay_var.get()
        new_state = tk.NORMAL if is_delayed else tk.DISABLED

        # Enable/disable Date Entry
        self.dtp_start_date.configure(state=new_state)

        # Enable/disable Time Spinboxes
        for spinbox in self.start_time_spinboxes:
            spinbox.config(state=new_state)

        if not is_delayed:  # Reset to now if disabling delay
            now = datetime.datetime.now()
            self.dtp_start_date.set_date(now.date())
            self.start_time_hour_var.set(now.hour)
            self.start_time_min_var.set(now.minute)

        self.update_battery()

    def update_battery_config(self, event=None):
        selection = self.cb_battery_type.current()  # Get index
        show_custom = selection == 2

        if show_custom:
            self.lbl_capacity.grid(row=1, column=0, padx=5, pady=5, sticky="w")
            self.tb_capacity_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        else:
            self.lbl_capacity.grid_remove()
            self.tb_capacity_entry.grid_remove()
            if selection == 0:  # 2000 mAh
                self.battery_mah.set(2000)
            elif selection == 1:  # 800 mAh
                self.battery_mah.set(800)

        self.update_battery()

    def validate_and_update_battery(self):
        """Validate custom capacity input and update battery life."""
        if self.cb_battery_type.current() == 2:  # Only validate if custom is selected
            try:
                val = int(self.custom_battery_mah.get())
                if val > 0:
                    self.battery_mah.set(val)
                    self.tb_capacity_entry.config(
                        foreground="black"
                    )  # Valid input style
                else:
                    # Indicate error subtly, prevent calculation with invalid value
                    self.tb_capacity_entry.config(foreground="red")
                    return  # Don't update battery with invalid value
            except ValueError:
                # Indicate error subtly, prevent calculation with invalid value
                self.tb_capacity_entry.config(foreground="red")
                return  # Don't update battery with invalid value

        self.update_battery()  # Update if validation passed or not custom

    def send_settings(self):
        if not self.connected:
            messagebox.showwarning(
                "Not Connected", "Connect to the device before sending settings."
            )
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
            except (
                tk.TclError
            ):  # Handle potential error if spinbox value is invalid somehow
                messagebox.showerror("Input Error", "Invalid Sample Interval values.")
                return

        # Get delay in seconds
        delay_start = self.get_delay_seconds()
        if delay_start is None:
            return  # Error handled in get_delay_seconds

        settings_sentence = f"SET,{current_time},{measure_interval},{int(delay_start)},"
        sensor_words = self.sensor.get_settings_words()
        settings_sentence += ",".join(sensor_words)

        self.ser_com.send_serial_message(settings_sentence)
        self.log_text("Settings sent, awaiting confirmation...", "center")

    # --- Core Logic ---
    def get_delay_seconds(self):
        """Calculates the delay in seconds from now until the specified start time."""
        if not self.cb_delay_var.get():
            return 0

        try:
            # Get Date and Time
            start_date = self.dtp_start_date.get_date()
            start_hour = self.start_time_hour_var.get()
            start_minute = self.start_time_min_var.get()
            start_time = datetime.time(start_hour, start_minute)

            # Combine Date and Time
            start_dt = datetime.datetime.combine(start_date, start_time)
            now_dt = datetime.datetime.now()
            delay_seconds = (start_dt - now_dt).total_seconds()

            if delay_seconds < 0:
                self.log_error(
                    "Warning: Delay start time is in the past. Delay set to 0."
                )
                return 0
            else:
                # Return as integer seconds
                return int(delay_seconds)

        except ValueError as e:  # Catches date parsing errors
            messagebox.showerror(
                "Input Error", f"Invalid date format for delayed start:\n{e}"
            )
            return None  # Indicate error
        except tk.TclError as e:  # Catches errors getting spinbox values
            messagebox.showerror(
                "Input Error", f"Invalid time value for delayed start:\n{e}"
            )
            return None  # Indicate error

    def process_received_sentence(self, sentence: str):
        """Processes a complete message received from the serial port."""
        parts = sentence.split(",")

        command = parts[0].upper()  # Make comparison case-insensitive
        if command == "OPENOBS":
            # Send acknowledgment back to the datalogger immediately
            self.ser_com.send_serial_message("OPENOBS")

            # Device sends serial number as handshake (Ex. $OPENOBS,446*50)
            self.connected = True  # Confirm connection on valid OPENOBS
            self.log_text("Device handshake received.", "center")

            self.tb_sn.config(state=tk.NORMAL)
            self.tb_sn.delete(0, tk.END)
            self.tb_sn.insert(0, parts[1])
            self.tb_sn.config(state=tk.DISABLED)

        elif command == "SENSOR" or command == "READY":
            # Device sends sensor configuration type after handshake.
            if command == "READY":
                # For backwards compatibility
                self.sensor_type = "VCNL4010"
            else:
                self.sensor_type = parts[1].strip()

            self.configure_sensor_settings()
            self.btn_send_settings.config(state=tk.NORMAL)
            self.log_text(f"Sensor configured: {self.sensor_type}", "center")
            self.log_text("Send settings when ready", "center")

        elif command == "SET" and len(parts) > 1 and parts[1].upper() == "SUCCESS":
            # Device sends $SET,SUCCESS*2D after receiving valid settings
            self.btn_send_settings.config(state=tk.DISABLED)  # Disable after success
            self.log_text("Settings Received Successfully", "center")

        elif command == "FILE" and len(parts) > 1 and parts[1].upper() == "OPEN":
            # Device sends $FILE,OPEN,FILENAME.TXT*XX
            filename = parts[2] if len(parts) > 2 else "UNKNOWN"
            self.log_text(f"Logging to ({filename}) ", "center")
            self.log_text("--- Sample Readings ---", "center")

        elif command == "HEADERS":
            self.data_headers = parts[1:]  # Store headers for later use
            self.log_text(f"Headers: {', '.join(self.data_headers)}", "center")
            if self.is_logging_to_file and self.log_file_object:
                try:
                    self.log_file_object.write(",".join(parts[1:]) + "\n")
                    self.log_file_object.flush()
                except IOError as e:
                    self.log_error(f"File logging error: {e}")

        # Handle potential error messages
        elif command == "SDINIT" and len(parts) > 1 and parts[1] == "0":
            self.log_error("SD Card Error: Initialization failed!")
            self.log_error("Check for missing or corrupted SD card.")

        elif command == "CLKINIT" and len(parts) > 1 and parts[1] == "0":
            self.log_error("RTC Error: Clock initialization failed!")

        else:
            self.log_error(f"Unknown serial message {sentence}")

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
            if delay_seconds is None:
                delay_seconds = 0  # Use 0 if there was an error getting delay

            # mAh consumed during delay (standby)
            delay_consumption_mah = OFF_CURRENT * (delay_seconds / 3600.0)
            remaining_mah_after_delay = current_batt_mah - delay_consumption_mah

            if remaining_mah_after_delay <= 0:
                battery_days = 0.0  # Already depleted during delay
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
                        interval_seconds = 0  # Cannot calculate if interval is invalid

                    if interval_seconds <= 0:
                        # Avoid division by zero, assume continuous if interval is zero/invalid
                        average_consumption_ma = CONTINUOUS_CURRENT
                    elif (
                        interval_seconds < ON_TIME
                    ):  # Handle case where interval is shorter than on-time
                        average_consumption_ma = ON_CURRENT  # Effectively always on
                    else:
                        off_time = interval_seconds - ON_TIME
                        # VB logic: Use continuous if offTime < 5s, otherwise weighted average
                        if (
                            off_time < 5
                        ):  # Use continuous rate for very short off periods
                            average_consumption_ma = CONTINUOUS_CURRENT
                        else:  # Weighted average for normal intervals
                            average_consumption_ma = (
                                (ON_CURRENT * ON_TIME) + (OFF_CURRENT * off_time)
                            ) / interval_seconds

                # Calculate remaining life in hours, then days
                if average_consumption_ma > 0:
                    remaining_hours = remaining_mah_after_delay / average_consumption_ma
                    remaining_days = remaining_hours / 24.0
                else:
                    # If avg consumption is zero, life is infinite? Or N/A?
                    remaining_days = float("inf")

                # Add the delay period back in days
                total_days = remaining_days + (delay_seconds / 3600.0 / 24.0)
                battery_days = total_days

            # Display result
            self.tb_battery_life.config(state=tk.NORMAL)
            self.tb_battery_life.delete(0, tk.END)
            if battery_days == float("inf"):
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
            print(f"Error updating battery life: {e}")  # Log error for debugging

    def send_hex_file(self):
        """Handles the .hex file upload process."""
        port = self.cb_ports.get()
        if not port:
            messagebox.showerror("Upload Error", "Please select a COM port.")
            return

        file_path = filedialog.askopenfilename(
            title="Select .hex file",
            filetypes=[("HEX files", "*.hex"), ("All files", "*.*")],
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
                f"-Uflash:w:{file_path}:i",  # Write the .hex file to flash memory
            ]

            self.log_text(f"Uploading {file_path} to {port} using avrdude...", "center")

            # Run the avrdude command as a subprocess
            result = subprocess.run(avrdude_command, capture_output=True, text=True)

            if result.returncode == 0:
                self.log_text("Upload Complete!", "center")
                messagebox.showinfo(
                    "Upload Success", f"Successfully uploaded {file_path} to {port}."
                )
            else:
                self.log_error(f"Upload Failed: {result.stderr}")
                messagebox.showerror(
                    "Upload Failed",
                    f"An error occurred during upload:\n{result.stderr}",
                )

        except FileNotFoundError:
            messagebox.showerror(
                "Upload Error", "avrdude not found. Please install it and try again."
            )
            self.log_error("Error: avrdude not found.")

        except Exception as e:
            messagebox.showerror("Upload Failed", f"An unexpected error occurred:\n{e}")
            self.log_error(f"Upload Failed: {e}")

    def log_text(self, message: str, justification: str = "left", tag: str = None):
        """Appends text to the serial log Text widget."""
        if not self.debug_mode.get() and tag == "debug":
            return  # Skip printing raw serial messages if debug mode is off
        try:
            # Ensure widget exists and is valid before trying to modify
            if not self.serial_log.winfo_exists():
                return

            self.serial_log.config(state=tk.NORMAL)  # Enable writing

            # Insert the message with the appropriate tag and justification
            jtag = self._get_tag(justification, tag)
            self.serial_log.insert(tk.END, message + "\n", jtag)

            self.serial_log.see(tk.END)  # Scroll to the bottom
            self.serial_log.config(state=tk.DISABLED)  # Disable writing
            self.update_idletasks()  # Ensure log updates immediately
        except tk.TclError as e:
            # Handle cases where the widget might be destroyed during shutdown
            print(f"Error updating log widget: {e}")
        except Exception as e:
            print(f"Unexpected error logging: {e}")

    def log_error(self, message):
        self.log_text(message, "center", "error")

    def _get_tag(self, justification: str, tag: str) -> str:
        """Determines the appropriate tag based on justification and additional tags."""
        base_tag = (
            justification if justification in ["center", "right", "left"] else "left"
        )
        if tag:
            return (base_tag, tag)
        return base_tag

    def configure_plot_types(self, plot_tab):
        # Layout the controls in the plotting tab
        plot_controls_frame = ttk.Frame(plot_tab)
        plot_controls_frame.pack(fill=tk.X, padx=5, pady=5)

        # Area for selecting plot type
        plot_type_frame = ttk.Frame(plot_controls_frame)
        plot_type_frame.pack(side=tk.LEFT, fill=tk.X, expand=False, padx=(0, 10))

        ttk.Label(plot_type_frame, text="Select plot:").pack(side=tk.LEFT, padx=(0, 5))
        self.plot_type_var = tk.StringVar(value="")
        self.plot_type_menu = ttk.Combobox(
            plot_type_frame,
            textvariable=self.plot_type_var,
            state="readonly",
            values=[],
        )
        self.plot_type_menu.pack(side=tk.LEFT, expand=True)
        self.plot_type_menu.bind("<<ComboboxSelected>>", self.update_plot_settings)

        # Area for specific plot type settings
        self.plot_settings_frame = ttk.Frame(plot_controls_frame)
        self.plot_settings_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Create a matplotlib figure and axis and add it to the plot tab
        self.plot_fig, self.plot_ax = plt.subplots()  # figsize=(8, 4))
        self.plot_canvas = FigureCanvasTkAgg(self.plot_fig, master=plot_tab)
        self.plot_canvas_widget = self.plot_canvas.get_tk_widget()
        self.plot_canvas_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def update_plot_types(self):
        self.plot_types = get_valid_plots(self.sensor.name)
        plots_list = list(self.plot_types.keys())

        self.plot_type_menu["values"] = plots_list
        if self.plot_type_var.get() == "":
            self.plot_type_var.set(plots_list[0])

        self.update_plot_settings()

    def update_plot_settings(self, event=None):
        for widget in self.plot_settings_frame.winfo_children():
            widget.destroy()

        plot_name = self.plot_type_var.get()
        plot_class = self.plot_types[plot_name]
        self.plot = plot_class(
            self.plot_canvas, self.plot_fig, self.plot_ax, self.plot_settings_frame
        )

    def configure_calibration_types(self, calibrate_tab):
        # Layout the controls in the plotting tab
        cal_controls_frame = ttk.Frame(calibrate_tab)
        cal_controls_frame.pack(fill=tk.X)

        # Area for selecting plot type
        cal_type_frame = ttk.LabelFrame(
            cal_controls_frame, text="Type", padding=(10, 5)
        )
        cal_type_frame.pack(side=tk.LEFT, fill=tk.X)

        self.cal_type_var = tk.StringVar(value="")
        self.cal_type_menu = ttk.Combobox(
            cal_type_frame, textvariable=self.cal_type_var, state="readonly", values=[]
        )
        self.cal_type_menu.pack()
        self.cal_type_menu.bind(
            "<<ComboboxSelected>>", self.update_calibration_settings
        )

        btn_cal_reset = ttk.Button(
            cal_type_frame, text="Reset", command=self.update_calibration_settings
        )
        btn_cal_reset.pack()

        # Area for specific plot type settings
        self.cal_settings_frame = ttk.Frame(cal_controls_frame)
        self.cal_settings_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Create a matplotlib figure and axis and add it to the cal tab
        self.cal_fig, self.cal_ax = plt.subplots()  # figsize=(8, 4))
        self.cal_canvas = FigureCanvasTkAgg(self.cal_fig, master=calibrate_tab)
        self.cal_canvas_widget = self.cal_canvas.get_tk_widget()
        self.cal_canvas_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def update_calibration_types(self):
        self.cal_types = get_valid_calibrations(self.sensor.name)
        cal_list = list(self.cal_types.keys())

        self.cal_type_menu["values"] = cal_list
        if self.cal_type_var.get() == "":
            self.cal_type_var.set(cal_list[0])

        self.update_calibration_settings()

    def update_calibration_settings(self, event=None):
        for widget in self.cal_settings_frame.winfo_children():
            widget.destroy()

        cal_name = self.cal_type_var.get()
        cal_class = self.cal_types[cal_name]
        self.cal = cal_class(
            self.cal_canvas, self.cal_fig, self.cal_ax, self.cal_settings_frame
        )

    def configure_sensor_settings(self):
        for widget in self.sensors_frame.winfo_children():
            widget.destroy()

        self.sensor = make_sensor_obj(self.sensor_type, self.sensors_frame)
        self.update_plot_types()
        self.update_calibration_types()

    def toggle_file_logging(self):
        if not self.is_logging_to_file:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Save Log As",
            )
            if file_path:
                try:
                    self.log_file_object = open(file_path, "w")
                    self.log_file_path = file_path
                    self.is_logging_to_file = True
                    self.btn_toggle_file_log.config(text="Stop Logging to File")
                    self.log_text(
                        f"Logging to file: {self.log_file_path}", "center", "info"
                    )
                except IOError as e:
                    messagebox.showerror(
                        "File Error", f"Could not open file for logging:\n{e}"
                    )
                    self.log_file_path = None
                    self.log_file_object = None
            else:  # User cancelled
                return
        else:
            if self.log_file_object:
                try:
                    self.log_file_object.close()
                except IOError as e:
                    messagebox.showerror("File Error", f"Error closing log file:\n{e}")
            self.log_text(
                f"Stopped logging to file: {self.log_file_path}", "center", "info"
            )
            self.is_logging_to_file = False
            self.log_file_object = None
            self.log_file_path = None
            self.btn_toggle_file_log.config(text="Start Logging to File")

    def toggle_communicator(self):
        """Switches between TestCommunicator and SerialCommunicator based on the checkbox state."""
        if self.use_test_comm.get():
            self.ser_com = TestCommunicator(
                self.log_text, self.process_received_sentence
            )
            self.log_text("Switched to TestCommunicator.", "center", "info")
        else:
            self.ser_com = SerialCommunicator(
                self.log_text, self.process_received_sentence
            )
            self.log_text("Switched to SerialCommunicator.", "center", "info")

    def on_closing(self):
        """Handles window close event."""
        self.ser_com.close_connection()

        if self.is_logging_to_file and self.log_file_object:
            try:
                self.log_file_object.close()
                print(f"Closed log file: {self.log_file_path}")
            except IOError as e:
                print(f"Error closing log file on exit: {e}")

        self.destroy()  # Close the Tkinter window


# --- Main Execution ---
if __name__ == "__main__":
    # Run the application
    app = OpenOBSApp()
    app.mainloop()

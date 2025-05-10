from ._base_sensor import BaseSensor
import tkinter as tk
from tkinter import ttk


class AS7265XSensor(BaseSensor):

    def __init__(self):
        super().__init__("AS7265X")

    def configure_gui(self, parent_frame):
        """Add GUI elements specific to AS7265X."""
        self.cb_ambient_light_var = tk.BooleanVar(value=True)
        self.cb_backscatter_var = tk.BooleanVar(value=True)
        self.cb_pressure_var = tk.BooleanVar(value=True)
        self.cb_temperature_var = tk.BooleanVar(value=True)
        self.led_current_var = tk.StringVar(value="25")
        self.gain_var = tk.StringVar(value="1")
        self.integration_cycles_var = tk.StringVar(value="16")

        meas_frame = ttk.LabelFrame(parent_frame, text="Measurements", padding=(10, 5))
        meas_frame.pack(fill="x", padx=5, pady=5)
        ttk.Checkbutton(meas_frame, text="Ambient Light", variable=self.cb_ambient_light_var).pack(anchor="w")
        ttk.Checkbutton(meas_frame, text="Backscatter", variable=self.cb_backscatter_var).pack(anchor="w")
        ttk.Checkbutton(meas_frame, text="Pressure", variable=self.cb_pressure_var).pack(anchor="w")
        ttk.Checkbutton(meas_frame, text="Temperature", variable=self.cb_temperature_var).pack(anchor="w")

        setting_frame = ttk.LabelFrame(parent_frame, text="Settings", padding=(10, 5))
        setting_frame.pack(fill="x", padx=5, pady=5)
        ttk.Label(setting_frame, text="LED Current (mA):").grid(row=0, column=0, sticky="w")
        ttk.Combobox(setting_frame, values=[12.5, 25, 50, 100], textvariable=self.led_current_var).grid(row=0,
                                                                                                        column=1,
                                                                                                        sticky="ew")

        ttk.Label(setting_frame, text="Gain:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(setting_frame, values=[1, 3.7, 16, 64], textvariable=self.gain_var).grid(row=1,
                                                                                              column=1,
                                                                                              sticky="ew")

        ttk.Label(setting_frame, text="Integration Cycles:").grid(row=2, column=0, sticky="w")
        ttk.Entry(setting_frame, textvariable=self.integration_cycles_var).grid(row=2, column=1, sticky="ew")

    def get_settings_words(self):
        """Build the settings string for AS7265X."""
        meas_bit_flags = 0
        if self.cb_ambient_light_var.get():
            meas_bit_flags |= 1  # Bit 0
        if self.cb_backscatter_var.get():
            meas_bit_flags |= 2  # Bit 1
        if self.cb_pressure_var.get():
            meas_bit_flags |= 4  # Bit 2
        if self.cb_temperature_var.get():
            meas_bit_flags |= 8  # Bit 3

        words = [
            str(meas_bit_flags),
            self.led_current_var.get(),
            self.gain_var.get(),
            self.integration_cycles_var.get()
        ]
        return words

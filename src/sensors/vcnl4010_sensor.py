from ._base_sensor import BaseSensor
import tkinter as tk
from tkinter import ttk


class VCNL4010Sensor(BaseSensor):

    def __init__(self):
        super().__init__("VCNL4010")

    def configure_gui(self, parent_frame):
        """Add GUI elements specific to VCNL4010."""
        self.cb_ambient_light_var = tk.BooleanVar(value=True)
        self.cb_backscatter_var = tk.BooleanVar(value=True)
        self.cb_pressure_var = tk.BooleanVar(value=True)
        self.cb_temperature_var = tk.BooleanVar(value=True)

        self.led_current_var = tk.IntVar(value=50)

        meas_frame = ttk.LabelFrame(parent_frame, text="Measurements", padding=(10, 5))
        meas_frame.pack(fill="x", padx=5, pady=5)
        ttk.Checkbutton(meas_frame, text="Ambient Light", variable=self.cb_ambient_light_var).pack(anchor="w")
        ttk.Checkbutton(meas_frame, text="Backscatter", variable=self.cb_backscatter_var).pack(anchor="w")
        ttk.Checkbutton(meas_frame, text="Pressure", variable=self.cb_pressure_var).pack(anchor="w")
        ttk.Checkbutton(meas_frame, text="Temperature", variable=self.cb_temperature_var).pack(anchor="w")

        setting_frame = ttk.LabelFrame(parent_frame, text="Settings", padding=(10, 5))
        setting_frame.pack(fill="x", padx=5, pady=5)
        ttk.Label(setting_frame, text="LED Current (mA):").grid(row=0, column=0, sticky="w")
        tk.Spinbox(setting_frame, from_=0, to=255, textvariable=self.led_current_var).grid(row=0, column=1, sticky="ew")

    def get_settings_words(self):
        """Build the settings string for VCNL4010."""
        return [str(self.led_current_var.get())]

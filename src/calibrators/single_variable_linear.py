from ._base_calibrator import BaseCalibrator
import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np


class SingleVariableLinear(BaseCalibrator):
    def __init__(self, *args):
        self.var_choices = []
        self.calibration_target = tk.StringVar()
        self.recording_key = None
        self.records = {}
        self.var_name = tk.StringVar()
        self.unit_name = tk.StringVar()
        super().__init__(*args)

    @classmethod
    def valid_sensors(cls) -> list[str]:
        return "any"

    @classmethod
    def get_pretty_name(cls) -> str:
        return "Single Value Linear"

    def _setup_axes(self):
        pass

    def _update_variable_choices(self):
        # Update the options for the X and Y variable dropdowns
        self.var_name.set(self.var_choices[0] if self.var_choices else "")

        self.var_dropdown["menu"].delete(0, "end")
        for choice in self.var_choices:
            self.var_dropdown["menu"].add_command(
                label=choice, command=lambda value=choice: self.var_name.set(value)
            )

    def _setup_controls(self):
        # Dropdowns for selecting calibration variable
        selection_frame = ttk.Frame(self.controls_frame)
        selection_frame.grid(row=0, column=0, sticky="ew")
        tk.Label(selection_frame, text="Variable:").grid(row=0, column=0, sticky="w")
        self.var_dropdown = tk.OptionMenu(selection_frame, self.var_name, "")
        self.var_dropdown.grid(row=0, column=1, sticky="ew")

        # Buttons for starting and stopping the calibration recordings
        recording_frame = ttk.Frame(self.controls_frame)
        recording_frame.grid(row=1, column=0)
        tk.Label(recording_frame, text="Cal. Value").grid(row=0, column=0, sticky="w")
        cal_value_entry = tk.Entry(
            recording_frame, textvariable=self.calibration_target
        )
        cal_value_entry.grid(row=0, column=1)
        self.btn_record = ttk.Button(
            recording_frame, text="Begin Recording", command=self._toggle_recording
        )
        self.btn_record.grid(row=1, column=0, columnspan=2)
        btn_fit = ttk.Button(recording_frame, text="Fit Model", command=self._fit_lm)
        btn_fit.grid(row=2, column=0, columnspan=2)

        # Ensure the frames expand properly
        self.controls_frame.columnconfigure(0, weight=1)
        selection_frame.columnconfigure(1, weight=1)
        recording_frame.columnconfigure(1, weight=1)

    def _toggle_recording(self):
        if self.recording_key:
            # Stop recording
            self.recording_key = None
            self.btn_record.config(text="Begin Recording")
        else:
            try:
                # Validate calibration_target as a number
                self.recording_key = float(self.calibration_target.get())

                # Remove existing record if it exists
                self.records.pop(self.recording_key, None)

                # Initialize a new record
                self.records[self.recording_key] = []
                self.btn_record.config(text="Stop Recording")

            except ValueError:
                messagebox.showerror(
                    "Invalid Input",
                    "Invalid calibration value. Please enter a numeric value.",
                )

    def _fit_lm(self):
        if not self.records:
            messagebox.showerror(
                "No Data", "No data to fit. Please record some data first."
            )
            return

        # Prepare data for fitting
        x = []
        y = []
        for key, values in self.records.items():
            x.extend([key] * len(values))
            y.extend(values)
        x = np.array(x)
        y = np.array(y)

        # Perform linear regression
        A = np.vstack([x, np.ones(len(x))]).T
        m, c = np.linalg.lstsq(A, y, rcond=None)[0]

        print(f"Fitted line: y = {m}x + {c}")

        y_hat = m * x + c
        self.ax.plot(x, y_hat, c="red")
        self.canvas.draw()

    def update(self, data):
        if len(self.var_choices) == 0:
            self.var_choices = list(data.keys())
            self._update_variable_choices()

        if self.recording_key:
            # Collect data if recording
            if self.var_name.get() in data:
                value = data[self.var_name.get()]
                if self.recording_key not in self.records:
                    self.records[self.recording_key] = []
                self.records[self.recording_key].append(value)

        # Clear all existing scatter plots on axes
        for collection in self.ax.collections:
            collection.remove()

        # Reset the color cycle
        self.ax.set_prop_cycle(None)

        # Prepare data for plotting
        x = []
        y = []
        for key, values in self.records.items():
            x.extend([key] * len(values))
            y.extend(values)

        self.ax.scatter(x, y, alpha=0.7)
        self.canvas.draw()

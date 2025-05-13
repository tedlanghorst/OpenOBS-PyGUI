from ._base_plot import BasePlot
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd


class TimeSeriesPlot(BasePlot):
    @classmethod
    def valid_sensors(cls):
        return "any"  # works with data from any sensor type.

    @classmethod
    def get_pretty_name(cls):
        return "Time Series"

    def __init__(self, *args):
        self.df = pd.DataFrame()
        self.max_time_steps = 30
        self.num_samples_var = tk.StringVar(
            value=str(self.max_time_steps)
        )  # Default value for number of samples
        self.lines = []  # Store line objects for updates

        super().__init__(*args)

    def _update_variable_choices(self):
        self.time_series_listbox["height"] = min(10, len(self.df.columns))
        # Clear existing options and add new ones.
        self.time_series_listbox.delete(0, tk.END)
        for col in self.df.columns:
            self.time_series_listbox.insert(tk.END, col)

    def _get_num_samples(self):
        try:
            num_samples = int(self.num_samples_var.get())
            if num_samples <= 0:
                raise ValueError("Number of samples must be positive.")
            self.max_time_steps = num_samples
            if len(self.df) > self.max_time_steps:
                self.df = self.df.iloc[
                    -self.max_time_steps :
                ]  # Trim to the last `max_time_steps` rows
        except ValueError:
            messagebox.showerror(
                "Input Error", "Invalid input. Please enter a positive integer."
            )

    def _setup_controls(self):
        self.time_series_listbox = tk.Listbox(
            self.controls_frame, selectmode="multiple", height=1
        )
        self.time_series_listbox.grid(row=0, column=0)

        # Bind the selection change event to the update function using a lambda
        self.time_series_listbox.bind(
            "<<ListboxSelect>>", lambda event: self.update(None)
        )

        # Clear selections button
        ttk.Button(
            self.controls_frame,
            text="Clear Selections",
            command=lambda: self.time_series_listbox.selection_clear(0, tk.END),
        ).grid(row=1, column=0)

        n_samples_frame = ttk.Frame(self.controls_frame)
        n_samples_frame.grid(row=0, column=1, padx=5)
        tk.Label(n_samples_frame, text="# of samples:").grid(row=0, column=0)
        num_samples_entry = tk.Entry(n_samples_frame, textvariable=self.num_samples_var)
        num_samples_entry.grid(row=1, column=0)
        tk.Button(n_samples_frame, text="Submit", command=self._get_num_samples).grid(
            row=2, column=0
        )
        self._get_num_samples()

    def _setup_axes(self):
        """Set up the axes with titles, labels, and grid."""
        self.ax.set_title("Time Series")
        self.ax.set_xlabel("Sample #")
        self.ax.grid(True, linestyle=":", alpha=0.6)

    def update(self, data):
        """Update the time series plot."""
        if data:
            new_df = pd.DataFrame(data, index=[0])
            if len(self.df) == 0:
                self.df = new_df
                self._update_variable_choices()
                self.lines = [
                    self.ax.plot([], [], linewidth=2, label=col)[0]
                    for col in self.df.columns
                ]
            else:
                self.df = pd.concat([self.df, new_df], ignore_index=True)
                if len(self.df) > self.max_time_steps:
                    self.df = self.df.iloc[1:]

        # Clear all existing lines on axes
        for line in self.ax.lines:
            line.remove()
        # Clear the existing legend
        if self.ax.get_legend():
            self.ax.get_legend().remove()

        # Reset the color cycle
        self.ax.set_prop_cycle(None)

        # Get selected columns from the Listbox
        selected_indices = self.time_series_listbox.curselection()
        selected_columns = [self.df.columns[i] for i in selected_indices]

        if len(selected_columns) > 0 and len(self.df) > 1:
            tmp_df = self.df[selected_columns]
            tmp_df.plot(ax=self.ax)

            ymin = tmp_df.min(axis=None)
            ymax = tmp_df.max(axis=None)
            ypad = (ymax - ymin) * 0.05 if ymax > ymin else 1

            self.ax.set_ylim(ymin - ypad, ymax + ypad)
            self.ax.set_xlim(tmp_df.index.min(), tmp_df.index.max())
            self.ax.legend(loc="upper left")
            self.canvas.draw()

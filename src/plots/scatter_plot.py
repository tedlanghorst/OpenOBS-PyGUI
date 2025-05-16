from ._base_plot import BasePlot
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd


class ScatterPlot(BasePlot):
    _valid_sensors = "any"
    _name = "Scatter"

    def __init__(self, *args):
        self.df = pd.DataFrame()
        self.max_time_steps = 30
        self.num_samples_var = tk.StringVar(
            value=str(self.max_time_steps)
        )  # Default value for number of samples
        self.lines = []  # Store line objects for updates

        super().__init__(*args)

    def _update_variable_choices(self):
        # Update the options for the X and Y variable dropdowns
        variable_choices = list(self.df.columns)
        self.x_var.set(variable_choices[0] if variable_choices else "")
        self.y_var.set(variable_choices[1] if len(variable_choices) > 1 else "")

        self.x_dropdown["menu"].delete(0, "end")
        self.y_dropdown["menu"].delete(0, "end")

        for choice in variable_choices:
            self.x_dropdown["menu"].add_command(
                label=choice, command=lambda value=choice: self.x_var.set(value)
            )
            self.y_dropdown["menu"].add_command(
                label=choice, command=lambda value=choice: self.y_var.set(value)
            )

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
        # Dropdowns for selecting X and Y variables
        self.x_var = tk.StringVar()
        self.y_var = tk.StringVar()

        tk.Label(self.controls_frame, text="X Variable:").grid(row=0, column=0)
        self.x_dropdown = tk.OptionMenu(self.controls_frame, self.x_var, "")
        self.x_dropdown.grid(row=0, column=1)

        tk.Label(self.controls_frame, text="Y Variable:").grid(row=1, column=0)
        self.y_dropdown = tk.OptionMenu(self.controls_frame, self.y_var, "")
        self.y_dropdown.grid(row=1, column=1)

        # Frame for number of samples input
        n_samples_frame = ttk.Frame(self.controls_frame)
        n_samples_frame.grid(row=0, column=2, padx=5)
        tk.Label(n_samples_frame, text="# of samples:").grid(row=0, column=0)
        num_samples_entry = tk.Entry(n_samples_frame, textvariable=self.num_samples_var)
        num_samples_entry.grid(row=1, column=2)
        tk.Button(n_samples_frame, text="Submit", command=self._get_num_samples).grid(
            row=2, column=2
        )
        self._get_num_samples()

    def _setup_axes(self):
        """Set up the axes with titles, labels, and grid."""
        self.ax.set_title("Time Series")
        self.ax.set_xlabel("Sample #")
        self.ax.grid(True, linestyle=":", alpha=0.6)

    def update(self, data: list[dict]):
        """Update the scatter plot."""
        if data:
            new_df = pd.DataFrame(data, index=range(len(data)))
            if len(self.df) == 0:
                self.df = new_df
                self._update_variable_choices()
            else:
                self.df = pd.concat([self.df, new_df], ignore_index=True)
                if len(self.df) > self.max_time_steps:
                    # Trim to the last `max_time_steps` rows
                    self.df = self.df.iloc[-self.max_time_steps :]

        # Clear all existing scatter plots on axes
        for collection in self.ax.collections:
            collection.remove()

        # Reset the color cycle
        self.ax.set_prop_cycle(None)

        # Get selected X and Y variables
        x_var = self.x_var.get()
        y_var = self.y_var.get()

        if x_var in self.df.columns and y_var in self.df.columns:
            # Plot the scatter plot
            x = self.df[x_var]
            y = self.df[y_var]
            self.ax.scatter(x, y, alpha=0.7)

            self.ax.set_xlim(get_lims(x))
            self.ax.set_ylim(get_lims(y))
            self.ax.set_xlabel(x_var)
            self.ax.set_ylabel(y_var)
            self.ax.set_title(f"Scatter Plot: {x_var} vs {y_var}")
            self.canvas.draw()


def get_lims(x: pd.Series):
    xmin = x.min(axis=None)
    xmax = x.max(axis=None)
    pad = (xmax - xmin) * 0.05 if xmax > xmin else 1

    return (xmin - pad), (xmax + pad)

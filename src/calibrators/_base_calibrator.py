from abc import ABC, abstractmethod
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class BaseCalibrator(ABC):
    _valid_sensors = "any"  # Can specify a list, e.g. ['VCNL4010','ExampleSensor2']
    _name = "base"

    def __init__(
        self,
        canvas: FigureCanvasTkAgg,
        fig: Figure,
        ax: Axes,
        controls_frame: ttk.Frame,
    ):
        self.canvas = canvas
        self.fig = fig
        self.ax = ax
        self.controls_frame = controls_frame

        self.ax.clear()
        self._setup_controls()
        self._setup_axes()

    @abstractmethod
    def _setup_controls(self):
        pass

    @abstractmethod
    def _setup_axes(self):
        """Sets up the axes with titles, labels, grids, etc."""
        pass

    @abstractmethod
    def update(self, data: list[dict]):
        """Adds data into memory, plots it, etc."""
        pass

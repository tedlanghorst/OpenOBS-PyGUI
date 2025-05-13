from abc import ABC, abstractmethod
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class BaseCalibrator(ABC):
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

    @classmethod
    @abstractmethod
    def valid_sensors(cls) -> list[str]:
        """Returns a list of valid sensors for the plot."""
        pass

    @classmethod
    @abstractmethod
    def get_pretty_name(cls) -> str:
        """Returns a human-readable name for the plot."""
        pass

    @abstractmethod
    def _setup_controls(self):
        pass

    @abstractmethod
    def _setup_axes(self):
        """Sets up the axes with titles, labels, grids, etc."""
        pass

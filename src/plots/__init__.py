from ._base_plot import BasePlot
from .time_series_plot import TimeSeriesPlot
from .scatter_plot import ScatterPlot
from .real_time_spectrum_plot import RealTimeSpectrumPlot


def get_valid_plots(sensor_type: str) -> dict[str, BasePlot]:
    """
    Returns a list of plot classes that are valid for the given sensor type.
    """
    plot_classes = [TimeSeriesPlot, ScatterPlot, RealTimeSpectrumPlot]
    valid_plots = {}

    for plot_class in plot_classes:
        valid_sensors = plot_class.valid_sensors()
        if sensor_type in valid_sensors or valid_sensors == "any":
            valid_plots[plot_class.get_pretty_name()] = plot_class

    return valid_plots

from ._base_plot import BasePlot
import numpy as np
import tkinter as tk
from tkinter import ttk


class RealTimeSpectrumPlot(BasePlot):

    @classmethod
    def valid_sensors(cls):
        return ["AS7265X"]

    @classmethod
    def get_pretty_name(cls):
        return "Real-Time Spectrum"

    def __init__(self, *args):
        self.bands = [410, 435, 460, 485, 510, 535, 560, 585, 610, 645, 680, 705, 730, 760, 810, 860, 900, 940]
        self.colors = [wavelength_to_rgb(b) for b in self.bands]
        self.data_memory = {}
        self.spec_type = ""
        self.band_prefix = ""

        super().__init__(*args)

    def _setup_controls(self):
        self.spectrum_type_var = tk.StringVar(value="Ambient")
        self.spectrum_type_menu = ttk.Combobox(self.controls_frame,
                                               textvariable=self.spectrum_type_var,
                                               state="readonly",
                                               values=["Ambient", "Backscatter"])
        self.spectrum_type_menu.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.spectrum_type_menu.bind("<<ComboboxSelected>>", self.stale_type_update)
        self.stale_type_update()

    def _setup_axes(self):
        """Set up the axes with labels and grid."""
        self.ax.set_xlabel("Wavelength (nm)")
        self.ax.set_ylabel("Irradiance W/m²")
        self.ax.grid(True, linestyle=":", alpha=0.6)

    def stale_type_update(self, event=None):
        self.spec_type = self.spectrum_type_var.get()
        if self.spec_type == 'Ambient':
            self.band_prefix = 'A'
        elif self.spec_type == 'Backscatter':
            self.band_prefix = 'B'

        if self.data_memory:
            self.update(self.data_memory)

    def update(self, data: dict):
        self.data_memory = data
        # Clear all existing lines on axes
        for line in self.ax.lines:
            line.remove()

        self.plot_spectrum(data, self.band_prefix)
        self.ax.set_title(F"{self.spec_type} Light Spectrum")
        self.canvas.draw()

    def plot_spectrum(self, data, band_prefix):
        values = []
        for b in self.bands:
            values.append(data[f'{band_prefix}{b}'] / 100)  # Convert from uW/cm2 to W/m2

        fwhm = 30.0
        sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
        lambda_plot = np.arange(350, 1000, step=1)
        full_spectrum = np.zeros_like(lambda_plot, dtype=float)

        for band, color, amplitude in zip(self.bands, self.colors, values):
            channel_contribution = amplitude * np.exp(-((lambda_plot - band)**2) / (2 * sigma**2))
            full_spectrum += channel_contribution
            self.ax.plot(lambda_plot, channel_contribution, color=color, linewidth=2, alpha=0.7)

        self.ax.plot(lambda_plot, full_spectrum, color='black', linewidth=2)


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

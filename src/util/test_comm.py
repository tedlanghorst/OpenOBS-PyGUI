import threading
import queue
import time
import numpy as np
from tkinter import messagebox


class TestCommunicator:
    """This class is used for serial comms using NMEA-style messages.
    Throughout this class, the following definitions are used:
        - message: Complete string sent through serial
        - sentence: The message without the leading $ and trailing checksum
        - words: List of commands and values that comprise the sentence.
    
    """

    def __init__(self, log_callback, sentence_callback):
        self.is_open = False
        self.log_callback = log_callback  # Function to log messages
        self.sentence_callback = sentence_callback  # Function to process received messages
        self.data_queue = queue.Queue()  # Thread-safe queue for incoming data
        self._stop_thread = threading.Event()  # Event to stop the background thread
        self._background_thread = None  # Thread for sending periodic messages

    def open_connection(self, *args):
        if self.is_open:
            messagebox.showerror("Connection Error", "Already connected to a port.")
            return

        self.is_open = True
        self.sentence_callback("OPENOBS,000")  # Initial handshake from sensor
        self.log_callback("OPENOBS,000", 'left', 'debug')
        self.log_callback("Attempting connection...", "center")

    def close_connection(self):
        """Closes the serial connection and stops the reading thread."""
        if not self.is_open:
            messagebox.showerror("Connection Error", "Not connected to any port.")
            return

        self.is_open = False
        self.stop_sending_data()  # Ensure the background thread is stopped when closing the connection
        self.log_callback("Disconnected", "center")

    def send_serial_message(self, sentence: str):
        """Formats and sends a message over the serial port."""
        if not self.is_open:
            self.log_callback("Error: Cannot send, not connected.", "center", "error")

        self.log_callback(f"Sent: {sentence.strip()}", "right", "debug")

        # GUI acknowledgement in response to "OPENOBS,000" handshake
        if sentence.startswith("OPENOBS"):
            self.sentence_callback("SENSOR,VCNL4010")
            self.log_callback("SENSOR,VCNL4010", "left", "debug")

        elif sentence.startswith("SET"):
            self.sentence_callback("SET,SUCCESS")
            self.log_callback("SET,SUCCESS", "left", "debug")
            time.sleep(0.1)
            self.start_sending_data()

    def start_sending_data(self):
        """Starts a background thread to send data headers and data strings periodically."""
        if self._background_thread and self._background_thread.is_alive():
            self.log_callback("Background thread already running.", "center", "info")
            return

        start_time = time.time()  # Record the start time

        def noisy_sinusoid(mu, amp, freq, t):
            sinusoid = amp * np.sin(2 * np.pi * freq * t)
            noise = np.random.normal(0, amp / 2)
            return int(mu + sinusoid + noise)

        def send_data():
            # Send data headers first
            self.sentence_callback("HEADERS,time,millis,ambient_light,backscatter,pressure,water_temp,battery")
            while not self._stop_thread.is_set():
                current_time = time.time()
                elapsed_time = current_time - start_time
                millis = int(elapsed_time * 1000)

                # Generate noisy sinusoidal data for ambient_light, backscatter, pressure, and water_temp
                ambient_light = noisy_sinusoid(1000, 100, 0.1, elapsed_time)
                backscatter = noisy_sinusoid(1000, 100, 0.1, elapsed_time)
                pressure = noisy_sinusoid(1000, 100, 0.1, elapsed_time)
                water_temp = noisy_sinusoid(1000, 100, 0.1, elapsed_time)

                # Generate noisy data for battery
                battery = 100 + np.random.normal(5)

                # Format the data string
                data_string = f"DATA,{elapsed_time},{millis},{ambient_light},{backscatter},{pressure},{water_temp},{battery}"

                # Send the data string
                self.data_queue.put(data_string)
                time.sleep(0.1)  # Wait for 0.1 seconds

        self._stop_thread.clear()
        self._background_thread = threading.Thread(target=send_data, daemon=True)
        self._background_thread.start()
        self.log_callback("Started sending data.", "center", "info")

    def stop_sending_data(self):
        """Stops the background thread that sends periodic messages."""
        if not self._background_thread or not self._background_thread.is_alive():
            self.log_callback("No background thread to stop.", "center", "info")
            return

        self._stop_thread.set()
        self._background_thread.join()
        self.log_callback("Stopped sending data.", "center", "info")

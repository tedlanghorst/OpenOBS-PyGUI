import serial
import threading
import queue
from tkinter import messagebox

from .xor_checksum import calculate_checksum, validate_checksum


class SerialCommunicator:
    """This class is used for serial comms using NMEA-style messages.
    Throughout this class, the following definitions are used:
        - message: Complete string sent through serial
        - sentence: The message after removing the leading $ and trailing checksum
        - words: List of commands and values that comprise the sentence.
    
    """

    def __init__(self, log_callback, sentence_callback):
        self.serial_port = serial.Serial()
        self.serial_thread = None
        self.stop_thread = False
        self.log_callback = log_callback  # Function to log messages
        self.sentence_callback = sentence_callback  # Function to process received messages
        self.data_queue = queue.Queue()  # Thread-safe queue for incoming data

    def open_connection(self, port, baudrate=250000, timeout=0.1):
        if self.is_open:
            messagebox.showerror("Connection Error", "Already connected to a port.")
            return

        try:
            self.serial_port.port = port
            self.serial_port.baudrate = baudrate
            self.serial_port.timeout = timeout
            self.serial_port.open()

            self.stop_thread = False
            self.serial_thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.serial_thread.start()
            self.log_callback("Attempting connection...", "center")

        except serial.SerialException as e:
            messagebox.showerror("Connection Error", f"Failed to connect to {port}:{e}")
            self.log_callback(f"Failed to connect to {port}", "center", "error")
            if self.is_open:
                self.serial_port.close()

    def close_connection(self):
        """Closes the serial connection and stops the reading thread."""
        if not self.is_open:
            messagebox.showerror("Connection Error", "Not connected to any port.")
            return

        self.stop_thread = True
        if self.serial_thread and self.serial_thread.is_alive():
            self.serial_thread.join(timeout=1)
        if self.is_open:
            try:
                self.serial_port.close()
            except serial.SerialException as close_e:
                self.log_callback(f"Error closing port: {close_e}", "center", "error")
                return

        self.log_callback("Disconnected", "center")

    def send_serial_message(self, sentence: str):
        """Formats and sends a message over the serial port."""
        if not self.is_open or not self.serial_port.is_open:
            self.log_callback("Error: Cannot send, not connected.", "center", "error")

        message = f"${sentence}*{calculate_checksum(sentence)}\r\n"
        try:
            self.serial_port.write(message.encode('ascii'))
            self.log_callback(f"Sent: {message.strip()}", "right", "debug")
        except serial.SerialException as e:
            self.log_callback(f"Serial Write Error: {e}", "center", "error")
        except Exception as e:
            self.log_callback(f"Unexpected Send Error: {e}", "center", "error")

    def read_serial_data(self):
        """Runs in a separate thread to read data from serial port."""
        buffer = ""
        while not self.stop_thread:
            try:
                if not self.serial_port.is_open:
                    break

                if self.serial_port.in_waiting > 0:
                    try:
                        data = self.serial_port.read(self.serial_port.in_waiting).decode('ascii', errors='ignore')
                        buffer += data
                    except serial.SerialException as read_err:
                        # Handle specific read errors (like device disconnect during read)
                        self.log_callback(f"Serial Read Error: {read_err}", "center", "error")
                        self.close_connection()  # Trigger disconnect logic
                        break  # Exit thread on read error

                    # Process complete messages (terminated by newline)
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        message = line.strip()
                        if message:
                            self.log_callback(f"{message}", "left", "debug")

                            sentence = self.get_sentence(message)
                            if sentence:
                                if sentence.startswith("DATA"):
                                    self.data_queue.put(sentence)  # Push to queue for other messages
                                else:
                                    # Bypass queue for critical messages like OPENOBS
                                    self.sentence_callback(sentence)

            except serial.SerialException as e:
                self.log_callback(f"Serial Exception: {e}", "center", "error")
                break
            except Exception as e:
                self.log_callback(f"Unexpected Read Error: {e}", "center", "error")
                break

    def get_sentence(self, message: str) -> list[str]:
        sentence = []
        try:
            # Skip checksum validation for HEADERS and DATA messages
            if message.startswith("HEADERS") or message.startswith("DATA"):
                sentence = message
            elif validate_checksum(message):
                start_idx = message.index('$')
                end_idx = message.rindex('*')  # Use last '*' for robustness
                sentence = message[start_idx + 1:end_idx]
            else:
                self.log_callback(f"Invalid Checksum: {message}", "left", "error")

        except Exception as e:
            self.log_callback(f"Error parsing message '{message}': {e}", "left", "error")

        return sentence

    @property
    def is_open(self):
        """Returns whether the serial port is open."""
        return self.serial_port.is_open

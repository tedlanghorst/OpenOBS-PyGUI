from .vcnl4010_sensor import VCNL4010Sensor
from .as7265x_sensor import AS7265XSensor


def make_sensor_obj(sensor_name: str):
    """
    Factory function to get the appropriate sensor class based on the sensor name.
    """
    if sensor_name == "VCNL4010":
        return VCNL4010Sensor()
    elif sensor_name == "AS7265X":
        return AS7265XSensor()
    else:
        raise ValueError(f"Unknown sensor name: {sensor_name}")

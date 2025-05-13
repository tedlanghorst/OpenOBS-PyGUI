from ._base_calibrator import BaseCalibrator
from .single_variable_linear import SingleVariableLinear


def get_valid_calibrations(sensor_type: str) -> dict[str, BaseCalibrator]:
    """
    Returns a list of plot classes that are valid for the given sensor type.
    """
    cal_classes = [SingleVariableLinear]
    valid_cals = {}

    for cal_class in cal_classes:
        valid_sensors = cal_class.valid_sensors()
        if sensor_type in valid_sensors or valid_sensors == "any":
            valid_cals[cal_class.get_pretty_name()] = cal_class

    return valid_cals

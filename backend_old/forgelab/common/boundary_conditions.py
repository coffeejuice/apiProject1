import logging


LOGGER = logging.getLogger(__name__)


def environment_temperature(_):
    """Returns max_temperature if operation_type is Heat. In other cases returns 20 C"""
    return 20.0


def convection_coefficient(row, _param: dict) -> float:
    if all((
            row['operation_type'] == 'Heat',
            isinstance(_param, dict),
            'operation' in _param,
            'sub_operation_type' in _param['operation'],
            _param['operation']['sub_operation_type'].lower() == 'heating'
    )):
        return 0.1
    else:
        return 0.02


def emissivity(_):
    return 0.7


def friction(_):
    return 1.0


def contact_heat_transfer(_):
    return 1.0

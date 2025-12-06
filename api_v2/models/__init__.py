"""
Archivo __init__ para el paquete models
"""

from .device_models import (
    BatteryInfo,
    ColorInfo,
    ColorsInfo,
    PollingInfo,
    DeviceInfo,
    VibrateRequest,
    ErrorResponse
)

__all__ = [
    'BatteryInfo',
    'ColorInfo',
    'ColorsInfo',
    'PollingInfo',
    'DeviceInfo',
    'VibrateRequest',
    'ErrorResponse'
]

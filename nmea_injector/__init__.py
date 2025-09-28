"""
NMEA Simulator

This package provides a comprehensive NMEA GPS simulation & testing library
"""

__version__ = "1.0.0"
__author__ = "Enhanced NMEA Sim"

from .simulator import Simulator
from .models import GpsReceiver, GlonassReceiver
from . import targeting

__all__ = [
    'Simulator',
    'GpsReceiver', 
    'GlonassReceiver',
    'targeting',
]
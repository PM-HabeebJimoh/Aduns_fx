"""Aduns FX / HYDRA-PRIME pre-movement decision engine.

This package implements a pure-Python, dependency-light version of the
multi-temporal market pre-movement detector described in the project brief.
It is a research/decision-support engine; it does not guarantee trading
profits and it does not place trades by itself.
"""

from .engine import HydraPrimeEngine, FusionConfig
from .models import (
    Direction,
    PriceTick,
    TradeTick,
    OHLCVBar,
    OptionSnapshot,
    DarkPoolSnapshot,
    CotSnapshot,
    PhysicalSnapshot,
    SignalResult,
    Decision,
    PositionPlan,
)
from .risk import RiskLimits, RiskManager

__all__ = [
    "HydraPrimeEngine",
    "FusionConfig",
    "Direction",
    "PriceTick",
    "TradeTick",
    "OHLCVBar",
    "OptionSnapshot",
    "DarkPoolSnapshot",
    "CotSnapshot",
    "PhysicalSnapshot",
    "SignalResult",
    "Decision",
    "PositionPlan",
    "RiskLimits",
    "RiskManager",
]

__version__ = "0.1.0"

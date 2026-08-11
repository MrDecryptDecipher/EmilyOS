"""Emily OS configuration package."""

from emily.config.loader import load_settings
from emily.config.settings import EmilySettings

__all__ = ["EmilySettings", "load_settings"]

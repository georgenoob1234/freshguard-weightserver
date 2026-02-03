"""Dependency injection for FastAPI endpoints."""

from typing import Optional

from app.config import Settings, get_settings
from app.scale_driver import ScaleDriver

# Global scale driver instance (initialized at startup)
_scale_driver: Optional[ScaleDriver] = None


def set_scale_driver(driver: ScaleDriver) -> None:
    """Set the global scale driver instance (called at app startup)."""
    global _scale_driver
    _scale_driver = driver


def get_scale_driver() -> ScaleDriver:
    """Get the global scale driver instance for dependency injection.
    
    Returns:
        The ScaleDriver instance
        
    Raises:
        RuntimeError: If the driver hasn't been initialized yet
    """
    if _scale_driver is None:
        raise RuntimeError("ScaleDriver not initialized. App startup may have failed.")
    return _scale_driver



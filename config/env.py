"""Re-export from shared.config for backward compatibility.

DEPRECATED: Import from shared.config.env instead.
"""

from shared.config.env import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]

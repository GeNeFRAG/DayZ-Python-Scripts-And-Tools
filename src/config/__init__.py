# Configuration package initialization
"""
DayZ Admin Tools - Configuration System

This package provides a lightweight configuration system for the DayZ Admin Tools.

Quick Usage:
    # Import the pre-configured instance
    from config import config
    
    value = config.get('some.nested.key')
    
    # Or create a custom instance
    from config import Config
    custom_config = Config(profile='my_server')

For detailed usage instructions, see the README.md in this directory.
"""

from config.config import Config, config

# Export the Config class and default instance
__all__ = ['Config', 'config']

"""
Minimal Configuration Reader for DayZ Python Tools

A super lightweight configuration system for DayZ admin tools.
Uses             "map_tools": {
                "export_format": "xml",
                "coordinate_precision": 4,
                "default_radius": 100
            }
        }
        
        try:
            with open(profile_path, 'w') as f:
                json.dump(default_config, f, indent=2)
                logger.info(f"Created default profile at '{profile_path}'")
            self.data = default_config
        except Exception as e:
            logger.error(f"Error creating default configuration: {e}")
            self.data = {}guration storage with read-only access.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Config")

class Config:
    """
    A minimal JSON-based configuration reader for DayZ admin tools.
    """
    
    DEFAULT_CONFIG_DIR = os.path.abspath(os.path.join(
        os.path.dirname(__file__), 'profiles')
    )
    DEFAULT_SECRETS_DIR = os.path.abspath(os.path.join(
        os.path.dirname(__file__), 'secrets')
    )
    DEFAULT_PROFILE = "default"
    
    def __init__(self, config_dir: str = None, secrets_dir: str = None, profile: str = None):
        """
        Initialize the Config.
        
        Args:
            config_dir: Directory for config profiles. Defaults to 'profiles' subdirectory.
            secrets_dir: Directory for secrets files. Defaults to 'secrets' subdirectory.
            profile: Profile name to use. Defaults to 'default'.
        """
        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self.secrets_dir = secrets_dir or self.DEFAULT_SECRETS_DIR
        self.profile = profile or self.DEFAULT_PROFILE
        self.data = {}
        
        # Ensure config directories exist
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.secrets_dir, exist_ok=True)
        
        # Load configuration
        self._load()
    
    def _load(self):
        """Load configuration from profile JSON file and merge with secrets."""
        profile_path = os.path.join(self.config_dir, f"{self.profile}.json")
        
        # Create default profile if needed
        if not os.path.exists(profile_path):
            if self.profile == self.DEFAULT_PROFILE:
                self._create_default_profile(profile_path)
            else:
                logger.warning(f"Profile '{self.profile}' not found. Using empty configuration.")
                self.data = {}
                return
        
        # Load configuration
        try:
            with open(profile_path, 'r') as f:
                self.data = json.load(f)
                
            logger.info(f"Loaded configuration from '{self.profile}'")
            
            # Now load and merge secrets if they exist
            self._load_secrets()
                
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.data = {}
            
    # YAML conversion method removed - using JSON only
    
    def _create_default_profile(self, profile_path):
        """Create a default profile configuration."""
        default_config = {}
        try:
            with open(profile_path, 'w') as f:
                json.dump(default_config, f, indent=2)
                logger.info(f"Created default profile at '{profile_path}'")
            self.data = default_config
        except Exception as e:
            logger.error(f"Error creating default configuration: {e}")
            self.data = {}
    
    def _load_secrets(self):
        """Load and merge secrets from the secrets directory."""
        # Look for profile-specific secrets file
        profile_secrets_path = os.path.join(self.secrets_dir, f"{self.profile}_secrets.json")
        if os.path.exists(profile_secrets_path):
            try:
                with open(profile_secrets_path, 'r') as f:
                    profile_secrets = json.load(f)

                # Merge profile-specific secrets
                if isinstance(profile_secrets, dict):
                    self._deep_merge(self.data, profile_secrets)
                    logger.info(f"Loaded and merged secrets from '{profile_secrets_path}'")
            except Exception as e:
                logger.error(f"Error loading profile-specific secrets: {e}")
        else:
            logger.warning(f"No secrets file found for profile '{self.profile}'")
    
    def _deep_merge(self, target, source):
        """Deep merge two dictionaries."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
    
    def get(self, path=None, default=None):
        """
        Get a configuration value by path.
        
        Args:
            path: Dot notation path to the value (e.g., "nitrado.api_token")
                 If None, returns the entire config.
            default: Value to return if path not found.
        
        Returns:
            The configuration value or default if not found.
        """
        if path is None:
            return self.data
        
        # Navigate path
        current = self.data
        if path:
            for key in path.split('.'):
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
        
        return current
    
    def list_profiles(self):
        """List all available profile names."""
        return [f[:-5] for f in os.listdir(self.config_dir) 
                if f.endswith(".json")]
    
    def switch_profile(self, profile):
        """
        Switch to a different profile.
        
        Args:
            profile: Name of profile to switch to.
            
        Returns:
            True if successful, False otherwise.
        """
        profile_path = os.path.join(self.config_dir, f"{profile}.json")
        if os.path.exists(profile_path):
            self.profile = profile
            self._load()
            return True
        else:
            logger.warning(f"Profile '{profile}' not found.")
            return False
    
    def get_full_config(self):
        """Return the full configuration dictionary"""
        return self.data
    
    def get_path(self, path_key, fallback=None):
        """
        Get a resolved filesystem path from configuration.
        
        Args:
            path_key: Path key in dot notation
            fallback: Default path if not found
            
        Returns:
            Resolved absolute path
        """
        path = self.get(path_key, fallback)
        if not path:
            return ""
        
        # If already absolute, return as is
        if os.path.isabs(path):
            return path
        
        # Resolve relative to config directory
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(base_dir, path))


# Simple singleton instance
config = Config()

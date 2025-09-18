"""
Minimal Configuration Reader for DayZ Python Tools

A super lightweight configuration system for DayZ admin tools that provides:
- Profile-based configuration management
- JSON-based configuration storage with read-only access
- Secrets management for sensitive information
- Hierarchical configuration with dot-notation access
- Automatic path resolution for file paths

Usage:
    # Use the default singleton instance
    from config import config
    value = config.get('general.output_path')

    # Create a custom instance with specific profile
    from config import Config
    custom_config = Config(profile='my_server')

The configuration system loads settings in this order (later overrides earlier):
1. Default or specified profile (profiles/<profile>.json)
2. Profile-specific secrets (secrets/<profile>_secrets.json)
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

# Import DayZ base classes
from dayz_admin_tools.base import JSONTool, logger


class Config(JSONTool):
    """
    A minimal JSON-based configuration reader for DayZ admin tools.

    Provides a lightweight configuration system that supports:
    - Multiple profiles for different environments
    - Secrets management for sensitive information
    - Dot-notation access to nested configuration values
    - Automatic file path resolution
    - Deep merging of configuration and secrets

    Attributes:
        config_dir (str): Directory containing profile JSON files
        secrets_dir (str): Directory containing secrets JSON files
        profile (str): Currently active profile name
        data (dict): Loaded configuration data
    """

    # Class constants for default directories and profile name
    DEFAULT_CONFIG_DIR = str(Path(__file__).parent / 'profiles')
    DEFAULT_SECRETS_DIR = str(Path(__file__).parent / 'secrets')
    DEFAULT_PROFILE = "default"

    def __init__(self, config_dir: str = None, secrets_dir: str = None, profile: str = None,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Config instance.

        Args:
            config_dir (str, optional): Directory for config profiles.
                Defaults to 'profiles' subdirectory relative to this file.
            secrets_dir (str, optional): Directory for secrets files.
                Defaults to 'secrets' subdirectory relative to this file.
            profile (str, optional): Profile name to use. Defaults to 'default'.
            config (dict, optional): Base configuration dictionary for JSONTool compatibility.

        Note:
            Automatically creates config directories if they don't exist and
            loads the specified profile and its associated secrets.
        """
        # Initialize base class first
        super().__init__(config)

        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self.secrets_dir = secrets_dir or self.DEFAULT_SECRETS_DIR
        self.profile = profile or self.DEFAULT_PROFILE
        self.data = {}

        # Ensure config directories exist
        Path(self.config_dir).mkdir(parents=True, exist_ok=True)
        Path(self.secrets_dir).mkdir(parents=True, exist_ok=True)

        # Load configuration
        self._load()

    def run(self) -> Dict[str, Any]:
        """
        Run the config tool (implementation of abstract method from DayZTool).

        Returns:
            The full configuration dictionary.
        """
        return self.get_full_config()

    def _load(self):
        """
        Load configuration from profile JSON file and merge with secrets.

        This method:
        1. Loads the profile JSON file (creates default if missing)
        2. Merges profile-specific secrets if available
        3. Handles errors gracefully by setting empty configuration

        The loading process respects the configuration hierarchy where
        secrets override profile settings.
        """
        profile_path = Path(self.config_dir) / f"{self.profile}.json"

        # Create default profile if needed
        if not profile_path.exists():
            if self.profile == self.DEFAULT_PROFILE:
                self._create_default_profile(str(profile_path))
            else:
                logger.warning(f"Profile '{self.profile}' not found. Using empty configuration.")
                self.data = {}
                return

        # Load configuration
        try:
            self.data = self.read_json(str(profile_path))
            logger.info(f"Loaded configuration from '{self.profile}'")

            # Now load and merge secrets if they exist
            self._load_secrets()

        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.data = {}

    # YAML conversion method removed - using JSON only

    def _create_default_profile(self, profile_path: str):
        """
        Create a default profile configuration file.

        Args:
            profile_path (str): Path where the default profile will be created

        Note:
            Creates an empty JSON configuration file. The actual default
            values should be provided in default.json.example.
        """
        default_config = {}
        try:
            self.write_json(default_config, profile_path)
            logger.info(f"Created default profile at '{profile_path}'")
            self.data = default_config
        except Exception as e:
            logger.error(f"Error creating default configuration: {e}")
            self.data = {}

    def _load_secrets(self):
        """
        Load and merge secrets from the secrets directory.

        Looks for profile-specific secrets file named '<profile>_secrets.json'
        and deep-merges it with the existing configuration data. Secrets
        will override any existing configuration values with the same keys.

        Logs warnings if no secrets file is found, which is normal for
        profiles that don't require sensitive information.
        """
        # Look for profile-specific secrets file
        profile_secrets_path = Path(self.secrets_dir) / f"{self.profile}_secrets.json"
        if profile_secrets_path.exists():
            try:
                profile_secrets = self.read_json(str(profile_secrets_path))

                # Merge profile-specific secrets
                if isinstance(profile_secrets, dict):
                    self._deep_merge(self.data, profile_secrets)
                    logger.info(f"Loaded and merged secrets from '{profile_secrets_path}'")
            except Exception as e:
                logger.error(f"Error loading profile-specific secrets: {e}")
        else:
            logger.warning(f"No secrets file found for profile '{self.profile}'")

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]):
        """
        Deep merge two dictionaries.

        Args:
            target (dict): The target dictionary to merge into
            source (dict): The source dictionary to merge from

        Note:
            Recursively merges nested dictionaries. Non-dict values in source
            will completely replace values in target.
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def get(self, path: str = None, default: Any = None) -> Any:
        """
        Get a configuration value by path using dot notation.

        Args:
            path (str, optional): Dot notation path to the value
                (e.g., "general.output_path", "nitrado_server.api_token").
                If None, returns the entire configuration dictionary.
            default (Any, optional): Value to return if path not found.

        Returns:
            Any: The configuration value at the specified path, or default if not found.

        Examples:
            >>> config.get('general.debug', False)
            True
            >>> config.get('paths.types_file')
            '/path/to/types.xml'
            >>> config.get()  # Returns entire config
            {'general': {...}, 'paths': {...}}
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

    def list_profiles(self) -> List[str]:
        """
        List all available profile names.

        Returns:
            List[str]: List of profile names (without .json extension)
                found in the config directory.

        Examples:
            >>> config.list_profiles()
            ['default', 'production', 'testing']
        """
        config_path = Path(self.config_dir)
        return [f.stem for f in config_path.glob("*.json")]

    def switch_profile(self, profile: str) -> bool:
        """
        Switch to a different profile.

        Args:
            profile (str): Name of profile to switch to (without .json extension).

        Returns:
            bool: True if successful, False if profile not found.

        Note:
            This will reload the configuration data from the new profile
            and merge any associated secrets.

        Examples:
            >>> config.switch_profile('production')
            True
            >>> config.switch_profile('nonexistent')
            False
        """
        profile_path = Path(self.config_dir) / f"{profile}.json"
        if profile_path.exists():
            self.profile = profile
            self._load()
            return True
        else:
            logger.warning(f"Profile '{profile}' not found.")
            return False

    def get_full_config(self) -> Dict[str, Any]:
        """
        Return the full configuration dictionary.

        Returns:
            Dict[str, Any]: Complete configuration including merged secrets.

        Note:
            This is equivalent to calling get() with no arguments.
        """
        return self.data

    def get_path(self, path_key: str, fallback: str = None) -> str:
        """
        Get a resolved filesystem path from configuration.

        Args:
            path_key (str): Path key in dot notation (e.g., "paths.types_file")
            fallback (str, optional): Default path if not found

        Returns:
            str: Resolved absolute path. Returns empty string if path is None/empty.
                 Relative paths are resolved relative to the config directory.

        Examples:
            >>> config.get_path('paths.types_file')
            '/absolute/path/to/types.xml'
            >>> config.get_path('paths.nonexistent', 'default.xml')
            '/absolute/path/to/config/default.xml'
        """
        path = self.get(path_key, fallback)
        if not path:
            return ""

        # If already absolute, return as is
        path_obj = Path(path)
        if path_obj.is_absolute():
            return str(path_obj)

        # Resolve relative to config directory
        base_dir = Path(__file__).parent
        return str(base_dir / path)


# Global singleton instance for convenient access throughout the application
# Usage: from config import config; value = config.get('some.key')
config = Config()

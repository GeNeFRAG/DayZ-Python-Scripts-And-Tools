# DayZ Tools Configuration System

This directory contains the configuration system for the DayZ Python Tools. It provides a centralized way to manage settings across different tools and server environments.

## Features

- **Profile-Based Configuration**: Create different profiles for different servers or environments
- **Environment-Specific Settings**: Configure paths, server details, and tool settings per environment
- **Secure Token Storage**: Store API tokens and passwords securely in a dedicated secrets directory
- **Lightweight Design**: Simple, JSON-based configuration with minimal dependencies
- **Hierarchical Settings**: Access nested configuration values using dot notation
- **Default Instance**: Access a pre-configured instance from anywhere in your code

## Directory Structure

- `config.py`: Main configuration manager with the `Config` class
- `__init__.py`: Package initialization with convenience exports
- `profiles/`: Directory containing configuration profiles
  - `default.json`: Default configuration profile
  - `default.json.example`: Example configuration file for reference
- `secrets/`: Directory containing sensitive information (API tokens, server IDs, etc.)
  - `default_secrets.json`: Default secrets file
  - `profile_secrets.json.example`: Example secrets file format

## Using the Configuration System

### In Your Script

The simplest way to use the configuration system:

```python
# Import the pre-configured default instance
from config import config

# Get configuration values using dot notation
api_token = config.get('nitrado_server.api_token')
server_id = config.get('nitrado_server.server_id')
```

For custom configurations:

```python
from config import Config

# Create a config instance with a specific profile
my_config = Config(profile='my_server')

# Get a value with a default fallback if the key doesn't exist
debug_mode = my_config.get('general.debug', False)

# Get a file path (automatically resolves relative paths)
types_file = my_config.get_path('paths.types_file')
```

### JSON Configuration Format

All configuration files use JSON format. Here's an example structure:

```json
{
  "general": {
    "data_directory": "data",
    "debug": false,
    "output_path": "output",
    "log_level": "DEBUG",
    "backup_directory": "backups",
    "log_download_path": "logs"
  },
  "nitrado_server": {
    "mission_directory": "dayzOffline.chernarusplus",
    "remote_base_path": "/gameservers/file_server",
    "ssl_verify": false
  },
  "duping_detector": {
    "proximity_threshold": 10,
    "time_threshold": 60
  }
}
```

### Secrets Management

Sensitive information like API tokens should be stored in the `secrets/` directory. The configuration system will automatically load and merge these with your profile settings.

```json
{
  "api_token": "your-nitrado-api-token",
  "service_id": "your-service-id",
  "server_id": "your-server-id"
}
```

For more details on secrets management, see the [secrets README](/src/config/secrets/README.md).

### Configuration Hierarchy

The configuration system loads settings in this order (later entries override earlier ones):

1. Default profile (`profiles/default.json`)
2. Custom profile (`profiles/<profile>.json`) if specified
3. Default secrets (`secrets/default_secrets.json`) 
4. Profile-specific secrets (`secrets/<profile>_secrets.json`) if available

This allows you to have common settings in the default profile and only override what's needed in custom profiles or secrets files.

### Key Methods

```python
# Get a config value with a default fallback
value = config.get('some.nested.key', default='fallback_value')

# Get a file path (resolves relative paths)
file_path = config.get_path('paths.some_file')

# Get the entire configuration
full_config = config.get_full_config()

# List available profiles
profiles = config.list_profiles()

# Switch to a different profile
config.switch_profile('other_profile')
```

### Creating Your Own Profile

To create a new profile:

1. Copy the default.json file to a new file with your profile name:
   ```bash
   cp src/config/profiles/default.json src/config/profiles/my_server.json
   ```

2. Edit the new JSON file with your preferred settings.

3. If needed, create a corresponding secrets file:
   ```bash
   cp src/config/secrets/profile_secrets.json.example src/config/secrets/my_server_secrets.json
   ```

4. Load your profile in code:
   ```python
   from config import Config
   custom_config = Config(profile="my_server")
   ```

### Integrating with Argparse

For command-line tools, you can add a profile option to your argument parser:

```python
import argparse
from config import Config

# Set up argument parser
parser = argparse.ArgumentParser()
parser.add_argument("--profile", default="default", 
                   help="Configuration profile to use")
args = parser.parse_args()

# Load the specified profile
config = Config(profile=args.profile)

# Use configuration values
output_dir = config.get("general.output_path")
```

## Configuration Structure

The configuration is organized into sections:

- `general`: Common settings used across all tools
  - `output_path`: Directory to store all tool output files
  - `backup_directory`: Directory for backups
  - `data_directory`: Base directory for data files
  - `debug`: Enable debug mode
  - `log_level`: Logging level (DEBUG, INFO, WARNING, ERROR)
  - `log_download_path`: Directory for downloaded logs

- `nitrado_server`: All Nitrado server settings
  - `mission_directory`: Mission directory name (e.g., "dayzOffline.chernarusplus")
  - `remote_base_path`: Base path on remote server
  - `ssl_verify`: Whether to verify SSL connections

- `duping_detector`: Settings for the duping detection tool
  - `proximity_threshold`: Distance threshold in meters
  - `time_threshold`: Time threshold in seconds
  - `login_threshold`: Login time threshold
  - `login_count_threshold`: Maximum login count

- `search_overtime_finder`: Settings for finding search overtime issues
  - `patterns`: Regex patterns for identifying problematic items

- `paths`: File paths for various tools
  - Paths to XML files and other data sources including types, events, and limits

See the default profile (`profiles/default.json`) for a complete list of available settings.

## Best Practices

1. **Keep sensitive information secure**: Store API tokens and passwords in the secrets directory.
2. **Never commit secrets to version control**: The secrets directory should be in your .gitignore.
3. **Create separate profiles for different environments**: Use different profiles for development, testing, and production.
4. **Use relative paths where possible**: This makes configurations portable across different machines.
5. **Provide default values when getting config**: Use `config.get('key.path', default='fallback')` to handle missing values gracefully.

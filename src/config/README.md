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
  - `profile_secrets.json.example`: Example secrets file format

## Using the Configuration System

### In Your Script

The simplest way to use the configuration system:

```python
# Import the pre-configured default instance
from config import config

# Get configuration values using dot notation
api_token = config.get('api_token')
output_path = config.get('general.output_path')
types_file = config.get('paths.types_file')
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

# Get the entire configuration
full_config = my_config.get()
```

### JSON Configuration Format

All configuration files use JSON format. Here's an example structure based on the actual default profile:

```json
{
  "general": {
    "data_directory": "data",
    "debug": false,
    "backup_directory": "backups",
    "log_level": "INFO",
    "output_path": "output",
    "log_download_path": "logs"
  },
  "log_filtering": {
    "default_patterns": ["*.RPT", "*.ADM"],
    "default_limit": 2
  },
  "log": {
    "filter_profiles_dir": "~/.config/dayz_admin_tools/log_profiles"
  },
  "nitrado_server": {
    "mission_directory": "dayzOffline.chernarusplus",
    "remote_base_path": "/gameservers/file_server",
    "ssl_verify": false
  },
  "duping_detector": {
    "proximity_threshold": 10,
    "time_threshold": 60,
    "login_threshold": 300,
    "login_count_threshold": 3
  },
  "search_overtime_finder": {
    "patterns": {
      "overtime": "Item \\[\\d+\\] causing search overtime: \"(.*?)\"",
      "hard_to_place": "LootRespawner\\] \\(PRIDummy\\) :: Item \\[\\d+\\] is hard to place, performance drops: \"(.*?)\""
    }
  },
  "paths": {
    "types_file": "/path/to/your/types.xml",
    "types_file_ref": "/path/to/your/types_ref.xml",
    "mapgroupproto_file": "/path/to/your/mapgroupproto.xml",
    "cfglimitsdefinition_file": "/path/to/your/cfglimitsdefinition.xml",
    "events_file": "/path/to/your/events.xml",
    "event_groups_file": "/path/to/your/cfgeventgroups.xml"
  }
}
```

### Secrets Management

Sensitive information like API tokens should be stored in the `secrets/` directory. The configuration system will automatically load and merge these with your profile settings.

**Profile-specific secrets** (e.g., `my_server_secrets.json` for profile `my_server`):
```json
{
  "api_token": "your-nitrado-api-token",
  "service_id": "your-service-id",
  "server_id": "your-server-id"
}
```

For more details on secrets management, see the [secrets README](secrets/README.md).

### Configuration Hierarchy

The configuration system loads settings in this order (later entries override earlier ones):

1. Default profile (`profiles/default.json`)
2. Custom profile (`profiles/<profile>.json`) if specified
3. Profile-specific secrets (`secrets/<profile>_secrets.json`) if available

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
success = config.switch_profile('other_profile')
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

### Integrating with DayZ Tools

For DayZ admin tools, you can use the base class pattern:

```python
from dayz_admin_tools.base import DayZTool

# Load configuration using the DayZ base class
config = DayZTool.load_config(profile='my_server')

# Access configuration values
output_dir = config.get("general.output_path")
types_file = config.get("paths.types_file")
```

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

The configuration is organized into sections (see the complete structure in `profiles/default.json.example`):

### `general`
Common settings used across all tools:
- `data_directory`: Base directory for data files (default: "data")
- `debug`: Enable/disable debug mode (default: false)
- `backup_directory`: Directory for backups (default: "backups")
- `log_level`: Logging level (default: "INFO", options: "DEBUG", "INFO", "WARNING", "ERROR")
- `output_path`: Directory to store output files (default: "output")
- `log_download_path`: Directory for downloaded log files (default: "logs")

### `log_filtering`
Settings for log file filtering:
- `default_patterns`: Array of file patterns to match (default: ["*.RPT", "*.ADM"])
- `default_limit`: Maximum number of files to download (default: 2)

### `log`
Log-specific settings:
- `filter_profiles_dir`: Directory containing log filter profiles

### `nitrado_server`
Nitrado server connection settings:
- `mission_directory`: Mission directory name (e.g., "dayzOffline.chernarusplus")
- `remote_base_path`: Base path on the remote server (default: "/gameservers/file_server")
- `ssl_verify`: Whether to verify SSL connections (default: false)

### `duping_detector`
Settings for the duping detection tool:
- `proximity_threshold`: Distance threshold for proximity detection (default: 10)
- `time_threshold`: Time threshold in seconds (default: 60)
- `login_threshold`: Login time threshold in seconds (default: 300)
- `login_count_threshold`: Login count threshold (default: 3)

### `search_overtime_finder`
Settings for the search overtime finder tool:
- `patterns`: Regular expression patterns for log parsing

### `paths`
File paths for various tools:
- `types_file`: Path to the main types.xml file
- `types_file_ref`: Path to the reference types.xml file
- `mapgroupproto_file`: Path to the mapgroupproto.xml file
- `cfglimitsdefinition_file`: Path to the cfglimitsdefinition.xml file
- `events_file`: Path to the events.xml file
- `event_groups_file`: Path to the cfgeventgroups.xml file

## Best Practices

1. **Keep sensitive information secure**: Store API tokens and passwords in the secrets directory.
2. **Never commit secrets to version control**: The secrets directory should be in your .gitignore.
3. **Create separate profiles for different environments**: Use different profiles for development, testing, and production.
4. **Use relative paths where possible**: This makes configurations portable across different machines.
5. **Provide default values when getting config**: Use `config.get('key.path', default='fallback')` to handle missing values gracefully.

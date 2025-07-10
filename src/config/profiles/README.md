# Configuration Profiles

This directory contains configuration profiles for the DayZ Python Tools. Each profile is a JSON file that defines settings for a specific environment or server.

## Files in This Directory

- `default.json`: The default configuration profile loaded automatically when no specific profile is requested
- `default.json.example`: Example configuration structure for reference

## Creating a New Profile

To create a new profile:

1. Copy the default.json file to a new file with your profile name:
   ```bash
   cp default.json my_server.json
   ```

2. Edit the new JSON file with your preferred settings.

3. Load your profile in code:
   ```python
   from config import Config
   config = Config(profile="my_server")
   ```

## Profile Structure

Each profile is a nested JSON structure with these main sections:

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
- `filter_profiles_dir`: Directory containing log filter profiles (default: "~/.config/dayz_admin_tools/log_profiles")

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
- `patterns`: Regular expression patterns for log parsing:
  - `overtime`: Pattern for overtime items
  - `hard_to_place`: Pattern for hard-to-place items

### `paths`
File paths for various tools:
- `types_file`: Path to the main types.xml file
- `types_file_ref`: Path to the reference types.xml file
- `mapgroupproto_file`: Path to the mapgroupproto.xml file
- `cfglimitsdefinition_file`: Path to the cfglimitsdefinition.xml file
- `events_file`: Path to the events.xml file
- `event_groups_file`: Path to the cfgeventgroups.xml file

## Example Profile Structure

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

## Secrets Management

Sensitive information like API tokens should be stored in separate secrets files in the `../secrets/` directory:

- `profile_secrets.json`: Contains API tokens and sensitive configuration
- Example structure:
  ```json
  {
    "api_token": "YOUR_NITRADO_API_TOKEN",
    "service_id": "YOUR_NITRADO_SERVICE_ID",
    "server_id": "YOUR_GAME_SERVER_ID"
  }
  ```

## Best Practices

1. **Secrets Management**: Keep sensitive information (API tokens, passwords) in the `../secrets/` directory instead of profiles. Use `profile_secrets.json` for sensitive configuration.

2. **Environment Separation**: Create separate profiles for each environment (development, testing, production servers).

3. **Path Management**: Use absolute paths for server-specific configurations, or relative paths for portable setups.

4. **Documentation**: Document any custom settings in your profiles or maintain separate documentation for custom configurations.

5. **Version Control**: 
   - Version control your `default.json` and `*.example` files
   - Consider excluding custom profiles with sensitive paths from version control
   - Always exclude the `secrets/` directory from version control

6. **Profile Naming**: Use descriptive names for profiles that indicate their purpose (e.g., `production_server1.json`, `testing_chernarus.json`).

7. **Configuration Validation**: Test your profiles with the tools before deploying to ensure all paths and settings are correct.

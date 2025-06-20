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

- `general`: Common settings used across all tools
  - `output_path`: Directory to store output files
  - `data_directory`: Base directory for data files
  - `backup_directory`: Directory for backups
  - `debug`: Enable/disable debug mode
  - `log_level`: Logging level

- `nitrado_server`: Nitrado server settings
  - `mission_directory`: Mission directory (e.g., "dayzOffline.chernarusplus")
  - `remote_base_path`: Base path on the remote server
  - `ssl_verify`: Whether to verify SSL connections

- `paths`: File paths for various tools
  - Paths to XML files and other resources

- `item_tools`: Settings for item-related tools
  - Settings that control item processing behaviors

- `map_tools`: Settings for map-related tools
  - Settings related to map and coordinate processing

## Best Practices

1. Keep sensitive information (API tokens, passwords) in the secrets directory instead of profiles.
2. Create separate profiles for each environment (development, testing, production).
3. Use relative paths where possible for better portability.
4. Document any custom settings in your profiles with comments or documentation.
5. Version control your default profile and examples, but consider excluding custom profiles.

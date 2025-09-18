# DayZ Admin Tools - Log Module

Advanced tools for managing DayZ server logs with robust filtering, organization, and analysis capabilities.

## Overview

The Log module provides a comprehensive solution for downloading, filtering, and managing DayZ server log files. Built specifically for Nitrado-hosted servers, it offers powerful filtering options by dates, patterns, and reusable profiles to simplify log management tasks for server administrators.

The module consists of two main components:
1. **Log Downloader**: Downloads and filters server logs (inherits from `FileBasedTool`)
2. **Log Filter Profiles**: Manages reusable sets of filtering criteria (inherits from `JSONTool`)

Both tools provide consistent file handling, configuration management, and error logging capabilities through their respective base classes.

## Log Downloader

The `NitradoLogDownloader` class provides a flexible system for retrieving log files from Nitrado-hosted DayZ servers.

### Features

- **Flexible Filtering**: Filter logs by date ranges, filename patterns, or combinations
- **Profile Support**: Save and load commonly used filter combinations
- **Smart Defaults**: Automatically download the most relevant logs when no filters specified
- **Incremental Downloads**: Only download new logs since the last download
- **Automatic Organization**: Store logs in date-structured directories
- **Format Support**: Handles all DayZ log types (RPT, ADM, etc.)

### CLI Usage

The command-line interface provides easy access through the `dayz-download-logs` command:

```bash
# Basic usage - downloads latest RPT and ADM logs
dayz-download-logs

# Download logs from a specific date range
dayz-download-logs --start-date 10.06.2025 --end-date 17.06.2025

# Download logs matching specific patterns
dayz-download-logs --pattern "*.RPT" --pattern "*script*.ADM"

# Specify output directory
dayz-download-logs --output-dir ./server_logs

# Download all available logs (use with caution)
dayz-download-logs --all

# Use a server profile with saved credentials
dayz-download-logs --profile my_nitrado_server

# Enable verbose output
dayz-download-logs --verbose
```

**Parameters**:
- `--output-dir`: Directory to save logs to (optional, uses `general.log_download_path` from config if not specified)
- `--start-date`: Start date for log files in D.M.YYYY format (optional, e.g., 01.06.2025)
- `--end-date`: End date for log files in D.M.YYYY format (optional, e.g., 30.06.2025)
- `--pattern`: Filename pattern (e.g., "*.RPT" or "script_*.ADM") (optional, can be specified multiple times)
- `--no-default`: Disable downloading latest .RPT and .ADM files when no other filters match (optional)
- `--all`: Download all .RPT and .ADM files (optional)
- `--verbose, -v`: Enable verbose output (optional)
- `--profile`: Configuration profile to use (optional, uses default if not specified)
- `--console`: Log detailed output summary (optional)

### Filter Profile Management

```bash
# Use a saved filter profile
dayz-download-logs --filter-profile last_week

# Save current filter settings as a profile
dayz-download-logs --start-date 01.06.2025 --end-date 07.06.2025 --pattern "*.RPT" --save-filter weekly_rpt

# List all available filter profiles
dayz-download-logs --list-filters

# List filter profiles in JSON format
dayz-download-logs --list-filters --json

# Create a set of common filter profiles
dayz-download-logs --create-common-filters

# Delete a filter profile
dayz-download-logs --delete-filter old_profile
```

**Filter Profile Parameters**:
- `--filter-profile`: Use a saved filter profile (optional)
- `--save-filter NAME`: Save current filter settings as a named profile (optional)
- `--list-filters`: List all available filter profiles (optional)
- `--json`: Output in JSON format when listing filter profiles (optional)
- `--create-common-filters`: Create a set of common filter profiles (optional)
- `--delete-filter NAME`: Delete a filter profile (optional)

## Log Filter Profiles

The `LogFilterProfile` class allows saving and reusing combinations of filtering criteria, making it easier to consistently retrieve the same types of logs. You can manage profiles either through the main `dayz-download-logs` command or the dedicated `dayz-log-filter-profiles` tool.

### Features

- **Save Filter Settings**: Store combinations of dates and patterns as named profiles
- **Common Presets**: Quickly create standard filter profiles (yesterday, last week, etc.)
- **Portable Formats**: Profiles stored as standard JSON files
- **CLI Integration**: Seamless use with the log downloader

### Managing Profiles with dayz-log-filter-profiles

The dedicated filter profiles tool provides more detailed management capabilities:

```bash
# Create a new filter profile
dayz-log-filter-profiles create weekly_rpt --start-date 01.06.2025 --end-date 07.06.2025 --patterns "*.RPT" --description "Weekly RPT logs"

# Delete a profile
dayz-log-filter-profiles delete old_profile

# Use a specific configuration profile
dayz-log-filter-profiles create error_logs --patterns "*error*.RPT,*crash*.ADM" --profile myserver
```

**Parameters for dayz-log-filter-profiles**:

**Create Command**:
- `name`: Name for the profile (required)
- `--start-date`: Start date in D.M.YYYY format (optional, e.g., 01.06.2025)
- `--end-date`: End date in D.M.YYYY format (optional, e.g., 30.06.2025)
- `--patterns`: Comma-separated list of filename patterns (optional)
- `--description`: Description of the profile (optional)
- `--profile`: Configuration profile to use (optional)
- `--console`: Log detailed output summary (optional)

**Delete Command**:
- `name`: Name of the profile to delete (required)

### Default Profiles

When you run `--create-common-filters`, these standard profiles are created:

| Profile Name | Description | Filter Criteria |
|-------------|-------------|----------------|
| `yesterday` | All logs from yesterday | Date range: yesterday only |
| `last_week` | All logs from the past 7 days | Date range: last 7 days |
| `all_rpt` | All RPT log files | Pattern: `*.RPT` |
| `all_adm` | All ADM log files | Pattern: `*.ADM` |
| `latest_logs` | Most recent RPT and ADM logs | Pattern: `*.RPT`, `*.ADM`, limit: 5 each |

### Profile Storage Location

Filter profiles are stored as JSON files in:

```
~/.config/dayz_admin_tools/log_profiles/
```

## Configuration

### Common Parameters

All log tools support these standard command-line parameters:

- `--profile`: Configuration profile to use (optional, uses default profile if not specified)
- `--console`: Log detailed output summary in addition to regular logging (optional)

### Server Profile Configuration

Log module options can be configured in your server profile (`src/config/profiles/default.json`):

```json
{
  "general": {
    "log_download_path": "logs"
  },
  "log_filtering": {
    "default_patterns": ["*.RPT", "*.ADM"],
    "default_limit": 2
  },
  "log": {
    "filter_profiles_dir": "~/.config/dayz_admin_tools/log_profiles"
  }
}
```

### Filter Profile Format

Each filter profile is stored as a JSON file with this structure:

```json
{
  "name": "weekly_rpt",
  "description": "Weekly RPT logs for monitoring",
  "start_date": "01.06.2025",
  "end_date": "07.06.2025",
  "filename_patterns": ["*.RPT"],
  "created_at": "2025-06-08T15:30:00"
}
```

## Python API Usage

### Basic Log Downloading

```python
from dayz_admin_tools.log.log_downloader import NitradoLogDownloader

# Load configuration
config = NitradoLogDownloader.load_config('my_server')  # or None for default

# Create log downloader
downloader = NitradoLogDownloader(config)

# Download latest logs (2 latest .RPT and 2 latest .ADM files by default)
result = downloader.run(output_dir="./logs")
print(f"Successfully downloaded logs: {result}")
```

### Advanced Filtering

```python
from datetime import datetime, timedelta

# Get logs from the past week with specific patterns
downloader = NitradoLogDownloader(config)
result = downloader.run(
    output_dir="./logs/weekly",
    start_date="01.06.2025",
    end_date="07.06.2025",
    filename_patterns=["*crash*.RPT", "*script*.ADM"],
    latest_default=False,  # Disable default latest files download
    download_all=False
)

# Download all RPT and ADM files (use with caution)
result = downloader.run(
    output_dir="./logs/all",
    download_all=True
)
```

### Working with Filter Profiles

```python
from dayz_admin_tools.log.log_filter_profiles import LogFilterProfile

# Create a filter profile manager
profile_manager = LogFilterProfile(config)

# Create a new filter profile
profile_manager.save_profile(
    name="error_logs",
    description="Logs containing error messages",
    filename_patterns=["*error*.RPT", "*crash*.ADM"],
    start_date="01.06.2025",
    end_date="18.06.2025"
)

# Load an existing profile
profile_data = profile_manager.load_profile("error_logs")

# Use a filter profile with the downloader
downloader = NitradoLogDownloader(config)
result = downloader.run(
    output_dir="./logs",
    filter_profile="error_logs"
)

# List all available profiles
profiles = profile_manager.list_profiles()
for profile in profiles:
    print(f"Profile: {profile['name']} - {profile.get('description', 'No description')}")

# Save current filter settings as a profile
result = downloader.run(
    output_dir="./logs",
    start_date="01.06.2025",
    end_date="07.06.2025",
    filename_patterns=["*.RPT"],
    save_profile="weekly_rpt_logs"
)
```

## Integration with Nitrado API

The Log module uses the Nitrado API client to access server logs. For proper operation:

1. Configure your Nitrado credentials in a secure profile
2. Ensure the API has the necessary permissions
3. Verify the path to your server's log directory

See the Nitrado module documentation for more details on setting up API access.
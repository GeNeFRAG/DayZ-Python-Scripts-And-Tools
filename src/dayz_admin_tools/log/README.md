# DayZ Admin Tools - Log Module

Advanced tools for managing DayZ server logs with robust filtering, organization, and analysis capabilities.

## Overview

The Log module provides a comprehensive solution for downloading, filtering, and managing DayZ server log files. Built specifically for Nitrado-hosted servers, it offers powerful filtering options by dates, patterns, and reusable profiles to simplify log management tasks for server administrators.

The module consists of two main components:
1. **Log Downloader**: Downloads and filters server logs
2. **Log Filter Profiles**: Manages reusable sets of filtering criteria

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

The command-line interface provides easy access through the `dayz-logs` command:

```bash
# Basic usage - downloads latest RPT and ADM logs
dayz-logs

# Download logs from a specific date range
dayz-logs --start-date 2025-06-10 --end-date 2025-06-17

# Download logs matching specific patterns
dayz-logs --pattern "*.RPT" --pattern "*script*.ADM"

# Specify output directory
dayz-logs --output-dir ./server_logs

# Download all available logs (use with caution)
dayz-logs --all

# Use a server profile with saved credentials
dayz-logs --profile my_nitrado_server
```

### Advanced Options

```bash
# Combine multiple filtering options
dayz-logs --start-date 2025-06-01 --pattern "*.RPT" --output-dir ./rpt_logs

# Skip logs that have already been downloaded
dayz-logs --skip-existing

# Show detailed information about available logs without downloading
dayz-logs --list-only
```

## Log Filter Profiles

The `LogFilterProfile` class allows saving and reusing combinations of filtering criteria, making it easier to consistently retrieve the same types of logs.

### Features

- **Save Filter Settings**: Store combinations of dates and patterns as named profiles
- **Common Presets**: Quickly create standard filter profiles (yesterday, last week, etc.)
- **Portable Formats**: Profiles stored as standard JSON files
- **CLI Integration**: Seamless use with the log downloader

### Managing Profiles

```bash
# List all available filter profiles
dayz-logs --list-filters

# Use a saved filter profile
dayz-logs --filter-profile last_week

# Create a set of common filter profiles
dayz-logs --create-common-filters

# Save current filter settings as a profile
dayz-logs --start-date 2025-06-01 --end-date 2025-06-07 --pattern "*.RPT" --save-filter weekly_rpt

# Delete a filter profile
dayz-logs --delete-filter old_profile
```

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
  "start_date": "2025-06-01",
  "end_date": "2025-06-07",
  "filename_patterns": ["*.RPT"],
  "created_at": "2025-06-08T15:30:00"
}
```

## Python API Usage

### Basic Log Downloading

```python
from dayz_admin_tools.log import NitradoLogDownloader
from dayz_admin_tools.config.config import Config

# Load configuration
config = Config(profile='my_server')
config_data = config.get()

# Create log downloader
downloader = NitradoLogDownloader(config_data)

# Download latest logs
results = downloader.run(output_dir="./logs")
print(f"Downloaded {len(results['downloaded'])} log files")
```

### Advanced Filtering

```python
from datetime import datetime, timedelta

# Get logs from the past week with specific patterns
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
today = datetime.now().strftime("%Y-%m-%d")

downloader = NitradoLogDownloader(config_data)
results = downloader.run(
    output_dir="./logs/weekly",
    start_date=yesterday,
    end_date=today,
    filename_patterns=["*crash*.RPT", "*script*.ADM"],
    skip_existing=True
)
```

### Working with Filter Profiles

```python
from dayz_admin_tools.log import LogFilterProfile

# Create a filter profile manager
profile_manager = LogFilterProfile(config_data)

# Create a new filter profile
profile_manager.create_filter(
    name="error_logs",
    description="Logs containing error messages",
    filename_patterns=["*error*.RPT", "*crash*.ADM"],
    start_date="2025-06-01",
    end_date="2025-06-18"
)

# Apply a filter profile with the downloader
filter_data = profile_manager.get_filter("error_logs")
downloader.run(filter_profile=filter_data)
```

## Integration with Nitrado API

The Log module uses the Nitrado API client to access server logs. For proper operation:

1. Configure your Nitrado credentials in a secure profile
2. Ensure the API has the necessary permissions
3. Verify the path to your server's log directory

See the Nitrado module documentation for more details on setting up API access.
# DayZ Admin Tools - Tools Package

A collection of Python tools for DayZ server administration that help analyze server logs, track player activity, and identify server issues.

## Overview

The `dayz_admin_tools.tools` package contains specialized tools developed to assist DayZ server administrators with common administrative tasks. These tools are designed to be used both as standalone command-line applications and as Python modules that can be integrated into other projects.

All tools in this package inherit from the `DayZTool` base class and follow a consistent design pattern for configuration, logging, and execution.

## Available Tools

### Kill Tracker

**Script**: `kill_tracker.py`  
**CLI Command**: `dayz-kill-tracker` or `bin/kill_tracker`

Tracks and ranks player kills from DayZ server logs. The tool analyzes ADM log files to extract kill events, counts kills per player, and provides ranked statistics.

**Features**:
- Extract player kill data from ADM logs
- Filter by date/time ranges
- Generate sorted kill rankings
- Export results to CSV files
- Configurable via configuration profiles

**Usage**:
```bash
# Basic usage with time range
dayz-kill-tracker --log-dir /path/to/logs --start "2025-05-01 00:00:00" --end "2025-05-31 23:59:59"

# Use specific configuration profile
dayz-kill-tracker --profile myserver --start "2025-05-01 00:00:00" --end "2025-05-31 23:59:59"

# Analyze all logs in configured directory
dayz-kill-tracker
```

**Parameters**:
- `--log-dir`: Path to directory containing .ADM log files (optional, uses configured path if not specified)
- `--start`: Start date and time in YYYY-MM-DD HH:MM:SS format (optional)
- `--end`: End date and time in YYYY-MM-DD HH:MM:SS format (optional)
- `--profile`: Configuration profile to use (optional, uses default if not specified)
- `--console`: Log detailed output summary (optional)

### Duping Detector

**Script**: `duping_detector.py`  
**CLI Command**: `dayz-duping-detector` or `bin/duping_detector`

Identifies potential item duplication exploits by analyzing player behavior patterns and item spawns in server logs.

**Features**:
- Detect suspicious login patterns
- Correlate login activity with item spawns
- Identify players with suspicious behavior
- Export findings as CSV reports
- Configurable detection thresholds

**Usage**:
```bash
# Basic duping detection with custom thresholds
dayz-duping-detector --adm-file "/path/to/logs/*.ADM" --rpt-file "/path/to/logs/*.RPT" --proximity-threshold 10

# Use configured log paths with custom parameters
dayz-duping-detector --proximity-threshold 15 --time-threshold 30 --login-threshold 600

# Use specific configuration profile
dayz-duping-detector --profile myserver
```

**Parameters**:
- `--adm-file`: File or pattern for ADM files (e.g., '/path/to/*.ADM') (optional, uses *.ADM in configured logs path if not specified)
- `--rpt-file`: File or pattern for RPT files (e.g., '/path/to/*.RPT') (optional, uses *.RPT in configured logs path if not specified)
- `--proximity-threshold`: Proximity threshold of spawned loot near the player in meters (optional, uses config default)
- `--time-threshold`: Time threshold of spawned loot near the player in seconds (optional, uses config default)
- `--login-threshold`: Login threshold in seconds (optional, uses config default)
- `--login-count-threshold`: Login count threshold (optional, uses config default)
- `--profile`: Configuration profile to use (optional, uses default if not specified)
- `--console`: Log detailed output summary (optional)

### Position Finder

**Script**: `position_finder.py`  
**CLI Command**: `dayz-position-finder` or `bin/position_finder`

Locates player positions in DayZ server logs, allowing administrators to track player movements and activities at specific coordinates.

**Features**:
- Find all players near specified coordinates within a given radius
- Search for all positions and activities of a specific player
- Filter results by date ranges
- Sort results chronologically
- Export position data to timestamped CSV files
- Support for multiple log file patterns

**Usage**:
```bash
# Find positions near coordinates using default *.ADM pattern
dayz-position-finder --target_x 7500 --target_y 8500 --radius 100

# Find positions near coordinates with specific file pattern
dayz-position-finder --file_pattern "*.ADM" --target_x 7500 --target_y 8500 --radius 100

# Find positions for a specific player
dayz-position-finder --player "SurvivorName"

# Filter by date range and use specific output file
dayz-position-finder --player "SurvivorName" --start-date 2023-06-01 --end-date 2023-06-30 --output player_positions.csv

# Use configuration profile
dayz-position-finder --profile myserver --target_x 7500 --target_y 8500
```

**Parameters**:
- `--file_pattern`: File pattern to search (e.g. "*.ADM") (optional, uses default "*.ADM" pattern if not specified)
- `--target_x`: Target X coordinate for location-based search (required unless using --player)
- `--target_y`: Target Y coordinate for location-based search (required unless using --player)
- `--radius`: Search radius in meters (optional, default: 100.0)
- `--output`: Output CSV file name (optional, default: positions.csv)
- `--player`: Player name to filter by (optional, alternative to coordinate search)
- `--start-date`: Start date in YYYY-MM-DD format (optional)
- `--end-date`: End date in YYYY-MM-DD format (optional)
- `--profile`: Configuration profile to use (optional, uses default if not specified)
- `--console`: Log detailed output summary (optional)

### Search Overtime Finder

**Script**: `search_overtime_finder.py`  
**CLI Command**: `dayz-search-overtime` or `bin/search_overtime_finder`

Identifies items in your server configuration that are causing search overtime or performance issues in the loot spawning system.

**Features**:
- Detect items causing search overtime
- Find items that are hard to place
- Process multiple log files
- Count occurrences of problematic items
- Export results to text and CSV formats

**Usage**:
```bash
# Analyze specific log files
dayz-search-overtime /path/to/logs/*.RPT

# Use configured log directory with custom output location
dayz-search-overtime --output /path/to/output --prefix server_issues

# Enable verbose logging
dayz-search-overtime --verbose

# Use specific configuration profile
dayz-search-overtime --profile myserver
```

**Parameters**:
- `log_files`: Path to log file(s), supports wildcards like *.RPT (optional, uses RPT files from configured log path if not specified)
- `--output, -o`: Directory to export results to (optional, uses configured output path if not specified)
- `--prefix`: Prefix for exported files (optional, default: "problematic_items")
- `--verbose, -v`: Enable verbose logging (optional)
- `--profile`: Configuration profile to use (optional, uses default if not specified)
- `--console`: Log detailed output summary (optional)

## Configuration

All tools use the configuration system provided by the `Config` class. Configuration profiles are stored in `src/config/profiles/` and can be specified using the `--profile` argument. 

### Common Parameters

All tools support these standard command-line parameters:

- `--profile`: Configuration profile to use (optional, uses default profile if not specified)
- `--console`: Log detailed output summary in addition to regular logging (optional)

### Default Configuration

```json
{
  "general": {
    "data_directory": "data",
    "debug": false,
    "backup_directory": "backups",
    "log_level": "DEBUG",
    "output_path": "output",
    "log_download_path": "logs"
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
  }
}
```

## Usage as Python Modules

All tools can be imported and used in your Python scripts:

```python
from dayz_admin_tools.tools.kill_tracker import KillTracker
from dayz_admin_tools.tools.position_finder import PositionFinder
from datetime import datetime

# Load configuration
config = KillTracker.load_config("myserver")  # or None for default

# Create tool instances
tracker = KillTracker(config)
finder = PositionFinder(config)

# Run kill tracker analysis
kill_count = tracker.run(
    log_dir="/path/to/logs",
    start_datetime=datetime(2025, 5, 1),
    end_datetime=datetime(2025, 5, 31)
)
print(f"Found {kill_count} total kills")

# Find positions near coordinates
nearby_positions = finder.find_nearby_positions(
    target_x=7500, 
    target_y=8500, 
    radius=100.0
)
print(f"Found {len(nearby_positions)} positions near target")

# Find positions for a specific player
player_positions = finder.find_positions_by_player(
    player_name_filter="SurvivorName"
)
print(f"Found {len(player_positions)} positions for player")
```
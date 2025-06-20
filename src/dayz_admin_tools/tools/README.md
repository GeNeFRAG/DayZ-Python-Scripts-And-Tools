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
dayz-kill-tracker --log-dir /path/to/logs --start "2025-05-01 00:00:00" --end "2025-05-31 23:59:59" --output kills.csv
```

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
dayz-duping-detector --adm-file "/path/to/logs/*.ADM" --rpt-file "/path/to/logs/*.RPT" --proximity-threshold 10
```

### Position Finder

**Script**: `position_finder.py`  
**CLI Command**: `dayz-position-finder` or `bin/position_finder`

Locates player positions in DayZ server logs, allowing administrators to track player movements and activities at specific coordinates.

**Features**:
- Find all players near specified coordinates
- Search for specific player movements
- Track player activities over time
- Visualize player paths
- Export position data to CSV format

**Usage**:
```bash
dayz-position-finder --coords "8000,6000" --radius 100 --log-dir /path/to/logs
```

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
dayz-search-overtime /path/to/logs/*.RPT
```

## Configuration

All tools use the configuration system provided by the `Config` class. Configuration profiles are stored in `src/config/profiles/` and can be specified using the `--profile` argument. 

The default configuration includes:

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
from dayz_admin_tools.config.config import Config

# Load configuration
config = Config()
config_data = config.get()

# Create tool instance
tracker = KillTracker(config_data)

# Run the tool
results = tracker.run("/path/to/logs", output_file="kill_stats.csv")

# Process results
print(f"Found {results['total_kills']} total kills")
```
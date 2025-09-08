# DayZ Admin Tools - Tools Package

A collection of Python tools for DayZ server administration that help analyze server logs, track player activity, and identify server issues.

## Overview

The `dayz_admin_tools.tools` package contains specialized tools developed to assist DayZ server administrators with common administrative tasks. These tools are designed to be used both as standalone command-line applications and as Python modules that can be integrated into other projects.

All tools in this package inherit from the `DayZTool` base class and follow a consistent design pattern for configuration, logging, and execution.

## Available Tools

### Player List Manager

**Script**: `player_list_manager.py`  
**CLI Command**: `dayz-player-list-manager`

Manages player lists (banlist, whitelist, and priority list) via Nitrado API and analyzes banned player connection attempts from RPT log files.

**Features**:
- Retrieve current player lists from the server
- Add/remove players from banlist, whitelist, or priority list
- Export player lists to CSV format
- Import players from text files (one ID per line)
- Batch operations for managing multiple players at once
- **NEW: Monitor banned players attempting to connect to the server**
- **NEW: Analyze RPT log files for security violations**
- **NEW: Export banned connection attempts to CSV for further analysis**
- Full Nitrado API integration

**Usage**:

*Player List Management:*
```bash
# List all banned players
dayz-player-list-manager manage banlist list

# Add players to banlist
dayz-player-list-manager manage banlist add --identifiers player1 player2 player3

# Remove players from whitelist
dayz-player-list-manager manage whitelist remove --identifiers player1 player2

# Export priority list to CSV
dayz-player-list-manager manage priority export --output-file priority.csv

# Import players from text file to banlist
dayz-player-list-manager manage banlist import --input-file banned_players.txt
```

*Banned Connection Attempts Analysis:*
```bash
# Check for banned players trying to connect (display results)
dayz-player-list-manager banned-attempts check --rpt-pattern "logs/*.RPT"

# Export banned connection attempts to CSV
dayz-player-list-manager banned-attempts export --rpt-pattern "logs/*.RPT" --output-file security_violations.csv

# Monitor specific RPT files
dayz-player-list-manager banned-attempts check --rpt-pattern "/path/to/specific/log.RPT"
```

**Banned Connection Detection**:
The tool automatically identifies log entries matching the pattern:
```
14:09:13.649 Player Bogumilwolf (1596804848) kicked from server: 7 (You were banned.)
```

Each detected attempt includes:
- Timestamp of the connection attempt
- Player name and ID
- Source log file and line number
- Full raw log line for reference

**Configuration Requirements**:
- Nitrado API token in secrets configuration (for list management)
- Service ID for the game server (for list management)
- Log path configuration (for banned attempts analysis)
- SSL verification settings (optional)



### ADM Log Analyzer

**Script**: `adm_analyzer.py`  
**CLI Command**: `dayz-adm-analyzer`

Comprehensive analysis of DayZ AdminLog (ADM) files. Extracts player session statistics, PvP combat analytics, building/construction activity, and more. Generates Markdown and CSV summary reports with top players, builders, weapons, killer, and damage. Now supports fully configurable special/custom event extraction and reporting via the configuration file.

**Features**:
- Parse and aggregate multiple ADM log files
- Player session and playtime statistics
- PvP-only combat analytics (kills, K/D, hits, damage, accuracy, top killer)
- Building/construction activity tracking (including all building, placed, folded, packed events)
- Markdown and CSV summary reports with top 10 players/builders, most used weapons, top killer, and top damage
- Configurable, server-specific special/custom event extraction and reporting (e.g., treasure hunts, animal deaths, server-specific events)
- All special/other events are defined in the config JSON (see `special_events` section)
- Robust error handling and defensive parsing for all event types
- CSV export for detailed data
- Configurable via profiles and CLI

**Usage**:
```bash
# Analyze all ADM logs for a profile and generate Markdown and CSV summary reports
dayz-adm-analyzer --profile my_server --output-prefix my_report
```

The Markdown and CSV reports are saved in your configured output directory (see `general.output_path`).

**Parameters**:
- `--profile`: Configuration profile to use
- `--adm-file`: Path to a specific ADM log file (optional)
- `--output-prefix`: Prefix for output files (default: adm_analysis)
- `--no-csv`: Skip CSV export (only generate Markdown report)
- `--console`: Log detailed output summary

**Configurable Special/Other Events**

You can define any number of custom/special events to extract and report on in the ADM analyzer by adding them to the `special_events` section of your config JSON (e.g., `src/config/profiles/default.json`). Example:

```json
"special_events": {
  "enabled": true,
  "events": [
    {
      "name": "treasure_hunt",
      "regexp": "Player \"([^\"]+?)\" \\(id=([A-F0-9]+)\\).*found treasure at pos=<([0-9.-]+), ([0-9.-]+), ([0-9.-]+)>",
      "description": "Treasure Hunt Event"
    },
    {
      "name": "custom_event",
      "regexp": "Player \"([^\"]+?)\" \\(id=([A-F0-9]+)\\).*did something special",
      "description": "Custom server event"
    }
  ]
}
```

All configured special events will be extracted, counted per player, and included as columns in the CSV and Markdown summary reports.

**PvP-Only Statistics**

All K/D, hits, and damage statistics now only count player-vs-player (PvP) events. These columns are clearly labeled with a (PvP) suffix in the CSV and Markdown reports.

**Building Actions**

The "Building Actions" stat now includes all building, placed, folded, and packed events for each player.

**Robust Error Handling**

The analyzer is robust to new or malformed log lines, and will log errors for any lines it cannot parse.

**Example Output**

CSV columns include: Player Name, Sessions, Total Playtime (Hours), Kills (PvP), K/D Ratio (PvP), Hits Dealt (PvP), Damage Dealt (PvP), Building Actions, Deaths by Bear, Deaths by Wolf, and all configured special events.

**See also:** The top-level README for more details on configuration and usage.

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
dayz-kill-tracker --log-dir /path/to/logs --start "01.05.2025 00:00:00" --end "31.05.2025 23:59:59"

# Use specific configuration profile
dayz-kill-tracker --profile myserver --start "01.05.2025 00:00:00" --end "31.05.2025 23:59:59"

# Analyze all logs in configured directory
dayz-kill-tracker
```

**Parameters**:
- `--log-dir`: Path to directory containing .ADM log files (optional, uses configured path if not specified)
- `--start`: Start date and time in D.M.YYYY HH:MM:SS format (e.g., 01.05.2025 00:00:00) (optional)
- `--end`: End date and time in D.M.YYYY HH:MM:SS format (e.g., 31.05.2025 23:59:59) (optional)
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

Comprehensive position and activity analysis tool for DayZ admin logs. Provides advanced filtering capabilities to search player positions, activities, and placements with support for multiple simultaneous filters and output formats.

**Features**:
- **Coordinate-based filtering** with customizable radius
- **Player name filtering** with automatic regex pattern detection
- **Placement action filtering** (e.g., "placed", "Fireplace", "Wooden Crate")
- **Date and time range filtering** with flexible format support (date-only or date+time)
- **Combined filtering** using multiple criteria simultaneously
- **Multiple output formats**: CSV, original ADM log format, or both
- **Auto-detection of regex patterns** in player name and placement filters
- **Distance calculations** for coordinate-based searches
- **Timestamped output files** to prevent overwrites
- Comprehensive error handling and logging

**Usage Examples**:

*Basic Searches:*
```bash
# Find positions near coordinates
dayz-position-finder --target-x 7500 --target-y 8500 --radius 100

# Find positions for a specific player
dayz-position-finder --player "SurvivorName"

# Find all placement actions by any player
dayz-position-finder --placement "placed"

# Find specific item placements
dayz-position-finder --placement "Fireplace"
```

*Combined Filters:*
```bash
# Find player actions within a specific area
dayz-position-finder --player "SurvivorName" --target-x 7500 --target-y 8500 --radius 100

# Find placement actions within a specific area
dayz-position-finder --placement "Fireplace" --target-x 7500 --target-y 8500 --radius 200

# Find specific player's placements within an area
dayz-position-finder --player "LinThoDan" --placement "placed" --target-x 7500 --target-y 8500 --radius 150
```

*Regex Pattern Support (Auto-detected):*
```bash
# Find multiple players with regex pattern
dayz-position-finder --player "(john|jane|bob)"

# Advanced regex patterns
dayz-position-finder --player "^Player[0-9]+$"

# Regex for placement filtering
dayz-position-finder --placement "(Fireplace|Wooden Crate|Tent)"
```

*Date and Time Filtering:*
```bash
# Find actions within date range
dayz-position-finder --player "SurvivorName" --start-date 01.06.2023 --end-date 30.06.2023

# Find actions within specific time range
dayz-position-finder --player "Player15957802" --start-date "07.09.2025 16:00" --end-date "07.09.2025 18:30"

# Combined date + coordinates + player
dayz-position-finder --player "LinThoDan" --target-x 7500 --target-y 8500 --radius 150 --start-date 01.08.2025 --end-date 31.08.2025
```

*Output Format Options:*
```bash
# Save results in original ADM log format
dayz-position-finder --player "LinThoDan" --placement "placed" --output-format adm

# Save results in both CSV and ADM formats
dayz-position-finder --player "Player15957802" --placement "placed" --output-format both --output results
```

**Parameters**:
- `--file_pattern`: File pattern to search (e.g. "*.ADM") (optional, uses default "*.ADM" pattern if not specified)
- `--target-x`: Target X coordinate for location-based search (optional)
- `--target-y`: Target Y coordinate for location-based search (optional)
- `--radius`: Search radius in meters (optional, default: 100.0)
- `--output`: Output file name (optional, default: positions.csv)
- `--output-format`: Output format: csv (default), adm, or both (optional)
- `--player`: Player name to filter by (automatically detects regex patterns) (optional)
- `--placement`: Filter for placement actions (automatically detects regex patterns) (optional)
- `--start-date`: Start date in D.M.YYYY or D.M.YYYY HH:MM format (optional)
- `--end-date`: End date in D.M.YYYY or D.M.YYYY HH:MM format (optional)
- `--profile`: Configuration profile to use (optional, uses default if not specified)
- `--console`: Log detailed output summary (optional)

**Note**: At least one filter (--player, --placement, or coordinates) must be specified.

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
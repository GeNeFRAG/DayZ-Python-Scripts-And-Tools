# DayZ Admin Tools

A Python package for DayZ server administration, providing tools for server management, log analysis, XML file manipulation, and more. This package is particularly focused on simplifying common tasks for DayZ server administrators.


## Features

- **XML Management**: Comprehensive tools for working with DayZ's types.xml, mapgroupproto.xml, and other economy files
- **Log Analysis**: Tools for downloading, analyzing, and extracting useful information from server logs with Nitrado integration
- **Player Management**: Advanced player list management (ban lists, whitelist, priority lists) via Nitrado API
- **JSON Processing**: Utilities for working with DayZ's JSON configuration files like cfgEffectArea.json and object spawner files
- **Player Tracking**: Advanced tools for position tracking, duping detection, and kill analysis
- **Event Visualization**: Plot event spawn positions from cfgeventspawns.xml files onto map images with detailed annotations
- **Nitrado Integration**: Direct API integration for Nitrado-hosted DayZ servers with file and player management
- **Configuration Management**: Robust configuration system supporting multiple server profiles and credentials
- **Configurable Special/Other Event Extraction**: The ADM Log Analyzer now supports fully configurable special/custom event extraction and reporting. Define any number of custom events in your config JSON (see `special_events` section) and they will be extracted, counted per player, and included in all reports.
- **PvP-Only Statistics**: All K/D, hits, and damage statistics in the ADM analyzer now only count player-vs-player (PvP) events, clearly labeled in all reports.
- **Comprehensive Building Actions**: Building/construction activity tracking now includes all building, placed, folded, and packed events.
- **Robust Error Handling**: The ADM analyzer is robust to new or malformed log lines, and will log errors for any lines it cannot parse.

## Installation

```bash
# From the repository root
pip install -e .
```

Note: The event spawn plotter requires `matplotlib` and `Pillow` for image plotting functionality. These are included in the default installation.

## Package Structure

The package is structured as follows:

```
dayz_admin_tools/
├── base.py          # Base classes for all tools
├── log/             # Log analysis and download tools
├── nitrado/         # Nitrado API client for server integration
├── tools/           # Admin tools for player tracking and analysis
├── xml/             # XML file manipulation tools
│   ├── types/       # Tools for types.xml manipulation
│   └── proto/       # Tools for mapgroupproto.xml manipulation
├── json/            # JSON file manipulation tools
└── config/          # Configuration system
```


## Configuration System

This package includes a comprehensive configuration system that allows you to:

- Create different profiles for different servers
- Store API tokens, server IDs, and other settings
- Access configuration values from within your scripts
- Configure common output directories for all tools
- **Define custom/special events for log extraction and reporting** (see `special_events` section below)

All tools use the `general.output_path` setting to store their output files, making it easy to manage generated files across different tools.

Configuration options are defined in `src/config/profiles/default.json`. You can create custom profiles by adding new JSON files to the profiles directory.

### Special/Other Events Configuration

To extract and report on custom/special events in the ADM analyzer, add a `special_events` section to your config JSON. Example:

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

## Available Tools

### XML Types Tools

- **Compare Types**: Compare two types.xml files and identify differences (`dayz-compare-types`)
- **Change Min/Max**: Update quantmin and quantmax values by pattern (`dayz-change-min-max`)
- **Check Usage Tags**: Validate usage tags against cfglimitsdefinition.xml (`dayz-check-usage-tags`)
- **Copy Types Values**: Copy specific values between types.xml files (`dayz-copy-types-values`)
- **Replace Usage/Value Tags**: Update usage and value tags in types.xml (`dayz-replace-usagevalue-tag-types`)
- **Sort Types by Usage**: Organize types.xml by usage categories (`dayz-sort-types-usage`)
- **Static Event Item Counter**: Count items in static events (`dayz-sum-staticbuilder-items`, `dayz-sum-staticmildrop-items`)
- **Sync CSV to Types**: Update types.xml from CSV data with quantity adjustments (`dayz-sync-csv-to-types`)
- **Types to Excel**: Convert between types.xml and Excel formats for easy editing (`dayz-types-to-excel`)

### XML Proto Tools

- **Compare Lootmax**: Compare and merge lootmax values between mapgroupproto files (`dayz-compare-lootmax`)
- **Deathmatch Config**: Configure deathmatch settings with area filtering (`dayz-deathmatch-config`)
- **Compare Missing Groups**: Identify missing groups between mapgroupproto files (`dayz-compare-missing-groups`)


### Admin Tools

- **Player List Manager**: Manage player lists (ban, whitelist, priority) via Nitrado API and analyze banned connection attempts from RPT logs (`dayz-player-list-manager`)
- **ADM Log Analyzer**: Comprehensive analysis of DayZ AdminLog (ADM) files for player and combat statistics, building activity, and more. Generates Markdown summary reports (`dayz-adm-analyzer`)
- **Event Spawn Plotter**: Visualize event spawn positions from cfgeventspawns.xml files and player spawn points from cfgplayerspawnpoints.xml files on map images with coordinate annotations (`dayz-event-spawn-plotter`)
- **Position Finder**: Find player positions and activities in log files (`dayz-position-finder`)
- **Duping Detector**: Detect suspicious duplication activities and login patterns (`dayz-duping-detector`)
- **Kill Tracker**: Track player kills and deaths with rankings (`dayz-kill-tracker`)


### Log Tools

- **Search Overtime**: Find overtime issues in logs (`dayz-search-overtime`)
- **Log Downloader**: Download server logs from Nitrado with filtering (`dayz-download-logs`)
- **Log Filter Profiles**: Manage reusable log filtering profiles (`dayz-log-filter-profiles`)

### JSON Tools

- **Calculate 3D Area**: Calculate 3D areas, dimensions, and volumes from JSON files (`dayz-calculate-3d-area`)
- **Generate Spawner Entries**: Generate spawner entries from item specifications (`dayz-generate-spawner-entries`)
- **Sum Items JSON**: Sum and analyze items in JSON files (`dayz-sum-items-json`)
- **Split Loot Structures**: Split large loot structure files by type classification (`dayz-split-loot-structures`)

## Usage Examples

### XML Types Management

Work with types.xml files for your DayZ server:

```bash
# Compare two types.xml files
dayz-compare-types vanilla_types.xml custom_types.xml

# Change min/max values for specific item types
dayz-change-min-max --pattern "Ammo*" --quantmin 15 --quantmax 45 --xml types.xml

# Convert types.xml to Excel for easy editing
dayz-types-to-excel --to-excel --input types.xml --output types.xlsx

# Sort types.xml by usage categories
dayz-sort-types-usage --xml types.xml

# Check usage tags against cfglimitsdefinition.xml
dayz-check-usage-tags --xml-file types.xml

# Compare mapgroupproto files to find missing groups
dayz-compare-missing-groups vanilla_mapgroupproto.xml custom_mapgroupproto.xml --output group_comparison.csv
```

### Player Management

Manage player access and permissions via Nitrado API:

```bash
# Export current ban list to CSV
dayz-player-list-manager manage banlist export

# Add players to ban list
dayz-player-list-manager manage banlist add --identifiers player1 player2 griefer123

# Remove players from ban list  
dayz-player-list-manager manage banlist remove --identifiers reformed_player

# Import whitelist from CSV file
dayz-player-list-manager manage whitelist import --input-file new_admins.txt

# Export priority/admin list
dayz-player-list-manager manage priority export --output-file priority_list.csv

# Add new admins to priority list
dayz-player-list-manager manage priority add --identifiers admin1 moderator2

# Check for banned players trying to connect (security monitoring)
dayz-player-list-manager banned-attempts check --rpt-pattern "logs/*.RPT"

# Export banned connection attempts to CSV for analysis
dayz-player-list-manager banned-attempts export --rpt-pattern "logs/*.RPT" --output-file banned_attempts.csv
```


### Log Analysis

Analyze server logs for useful information:

```bash
# Analyze ADM logs and generate a Markdown summary report
dayz-adm-analyzer --profile my_server --prefix my_report

# Download logs from Nitrado server
dayz-download-logs --start-date 10.06.2025 --end-date 17.06.2025

# Find player positions in logs
dayz-position-finder --player "SurvivorName" --target-x 7500 --target-y 8500 --radius 100

# Find positions with specific file pattern
dayz-position-finder --file_pattern "*.ADM" --player "SurvivorName" --target-x 7500 --target-y 8500 --radius 100

# Detect possible duping activity
dayz-duping-detector --proximity-threshold 10 --time-threshold 30

# Track player kills
dayz-kill-tracker --start "01.05.2025 00:00:00" --end "31.05.2025 23:59:59"

# Visualize event spawn locations on map
dayz-event-spawn-plotter --event StaticHeliCrash

# List available events in XML file
dayz-event-spawn-plotter --list-events
```
### ADM Log Analyzer Example

Analyze all ADM logs for a server profile and generate a Markdown summary:

```bash
dayz-adm-analyzer --profile my_server --output-prefix my_report
```

The Markdown report includes:
- Top 10 most active players (by playtime)
- Top 10 most active builders
- Most weapon used (excluding melee)
- Top killer
- Top damage

The report is saved in the configured output directory (see `general.output_path` in your config).

### Event Spawn Plotter Example

Visualize event spawn positions from cfgeventspawns.xml files or player spawn points from cfgplayerspawnpoints.xml files on a map image:

```bash
# Plot event spawns
dayz-event-spawn-plotter --event StaticHeliCrash

# Plot event spawns with custom output file
dayz-event-spawn-plotter --event StaticContaminatedArea --output contaminated_zones.jpg

# List all available events in the XML file
dayz-event-spawn-plotter --list-events

# Plot player spawn points (uses default fresh spawns from config)
dayz-event-spawn-plotter --player-spawns

# Plot specific player spawn types
dayz-event-spawn-plotter --player-spawns --spawn-type hop
dayz-event-spawn-plotter --player-spawns --spawn-type hop_Balota

# List all available player spawn types
dayz-event-spawn-plotter --player-spawns --list-spawns
```

The Event Spawn Plotter generates high-quality images showing:
- Event spawn positions or player spawn points as colored markers with coordinate annotations
- Event/spawn type name and spawn count in the legend
- Clear visualization of spawn distribution across the map
- Support for all DayZ maps with configurable dimensions
- Support for both event spawns and player spawns (fresh, hop, travel types)

### JSON Configuration

Work with DayZ's JSON configuration files:

```bash
# Calculate areas from effect area JSON
dayz-calculate-3d-area input.json --max-box-size 50

# Generate spawner entries with items and positions
dayz-generate-spawner-entries generate "Barrel_Green:2:7500:300:7600" "AKM:5:7510:300:7610" --output spawner.json

# Split large loot structure files
dayz-split-loot-structures --types-xml types.xml --input-json large_structures.json
```

### Working with Configuration

```python
from dayz_admin_tools.base import DayZTool

# Load configuration from a profile
config = DayZTool.load_config(profile="my_server")

# Access configuration values
output_path = config.get('general.output_path')
types_file = config.get('paths.types_file')

# Print available configuration profiles
from config.config import Config
config_obj = Config()
print(f"Available profiles: {config_obj.list_profiles()}")
```

### Using the Nitrado API Client

```python
from dayz_admin_tools.nitrado.api_client import NitradoAPIClient
from dayz_admin_tools.base import DayZTool

# Load configuration
config = DayZTool.load_config()

# Create an API client
client = NitradoAPIClient(config)

# File operations (use relative paths from gameserver root)
files = client.list_files("config/")
for file in files:
    print(f"{file['name']} - {file['size']} bytes")

# Download a file (use relative path from gameserver root)
content = client.download_file("config/server.cfg")
with open("local_server.cfg", "wb") as f:
    f.write(content)

# Player list management
ban_list = client.get_banlist()
client.add_to_banlist(['cheater123', 'griefer456'])
client.remove_from_banlist(['reformed_player'])

# Whitelist management
whitelist = client.get_whitelist()
client.add_to_whitelist(['admin1', 'moderator2'])

# Priority/Admin list management
admin_list = client.get_prioritylist()  # or get_adminlist()
client.add_to_prioritylist(['new_admin'])

# Generic list operations (works with 'bans', 'whitelist', 'priority')
ban_list = client.get_list('bans')
client.add_to_list('whitelist', ['player1', 'player2'])
client.remove_from_list('priority', ['old_admin'])
```

### Player List Management with API

```python
from dayz_admin_tools.tools.player_list_manager import PlayerListManagerTool
from dayz_admin_tools.base import DayZTool

# Load configuration
config = DayZTool.load_config()

# Initialize the player list manager
manager = PlayerListManagerTool(config)

# Export current ban list to CSV
result = manager.run('banlist', 'export', output_file='current_bans.csv')

# Add players from CSV to whitelist
result = manager.run('whitelist', 'import', csv_file='new_admins.csv')

# Add individual players to priority list
result = manager.run('priority', 'add', identifiers=['admin1', 'moderator2'])

# Remove players from ban list
result = manager.run('banlist', 'remove', identifiers=['reformed_player'])
```

### XML Types Manipulation

```python
from dayz_admin_tools.xml.types.compare_types import CompareTypesTool
from dayz_admin_tools.base import DayZTool

# Load configuration
config = DayZTool.load_config()

# Initialize a tool
tool = CompareTypesTool(config)

# Compare two types.xml files
result = tool.run("original.xml", "modified.xml")
print(f"Found {result['differences_count']} differences")

# Access the differences data
differences = result['differences']
for diff in differences[:5]:
    print(f"{diff['type_name']}: {diff['attribute']} changed from {diff['old_value']} to {diff['new_value']}")
```

## Installation

```bash
# Install the package in development mode
pip install -e .

# Install with lxml support for better XML handling
pip install -e ".[xml]"
```

## Documentation

Each module includes its own README with detailed documentation:

- [XML Types Module](src/dayz_admin_tools/xml/types/README.md) - Tools for types.xml manipulation
- [XML Proto Module](src/dayz_admin_tools/xml/proto/README.md) - Tools for mapgroupproto.xml manipulation
- [JSON Module](src/dayz_admin_tools/json/README.md) - Tools for JSON file manipulation
- [Log Module](src/dayz_admin_tools/log/README.md) - Tools for log analysis and download
- [Tools Module](src/dayz_admin_tools/tools/README.md) - General admin tools for player tracking
- [Nitrado Module](src/dayz_admin_tools/nitrado/README.md) - Nitrado API integration
- [Configuration System](src/config/README.md) - Configuration management documentation

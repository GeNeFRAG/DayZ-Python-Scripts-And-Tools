# DayZ Admin Tools

A Python package for DayZ server administration, providing tools for server management, log analysis, XML file manipulation, and more. This package is particularly focused on simplifying common tasks for DayZ server administrators.

## Features

- **XML Management**: Comprehensive tools for working with DayZ's types.xml, mapgroupproto.xml, and other economy files
- **Log Analysis**: Tools for downloading, analyzing, and extracting useful information from server logs with Nitrado integration
- **JSON Processing**: Utilities for working with DayZ's JSON configuration files like cfgEffectArea.json and object spawner files
- **Player Tracking**: Advanced tools for position tracking, duping detection, and kill analysis
- **Nitrado Integration**: Direct API integration for Nitrado-hosted DayZ servers
- **Configuration Management**: Robust configuration system supporting multiple server profiles and credentials

## Installation

```bash
# From the repository root
pip install -e .
```

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

All tools use the `general.output_path` setting to store their output files, making it easy to manage generated files across different tools.

Configuration options are defined in `src/config/profiles/default.json`. You can create custom profiles by adding new JSON files to the profiles directory.

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

### Log Tools

- **Position Finder**: Find player positions and activities in log files (`dayz-position-finder`)
- **Duping Detector**: Detect suspicious duplication activities and login patterns (`dayz-duping-detector`)
- **Search Overtime**: Find overtime issues in logs (`dayz-search-overtime`)
- **Kill Tracker**: Track player kills and deaths with rankings (`dayz-kill-tracker`)
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
dayz-check-usage-tags --xml_file types.xml

# Compare mapgroupproto files to find missing groups
dayz-compare-missing-groups vanilla_mapgroupproto.xml custom_mapgroupproto.xml --output group_comparison.csv
```

### Log Analysis

Analyze server logs for useful information:

```bash
# Download logs from Nitrado server
dayz-download-logs --start-date 2025-06-10 --end-date 2025-06-17

# Find player positions in logs
dayz-position-finder --player "SurvivorName" --target_x 7500 --target_y 8500 --radius 100

# Detect possible duping activity
dayz-duping-detector --proximity-threshold 10 --time-threshold 30

# Track player kills
dayz-kill-tracker --start "2025-05-01 00:00:00" --end "2025-05-31 23:59:59"
```

### JSON Configuration

Work with DayZ's JSON configuration files:

```bash
# Calculate areas from effect area JSON
dayz-calculate-3d-area input.json --max-box-size 50

# Generate spawner entries with items and positions
dayz-generate-spawner-entries "Barrel_Green:2:7500:300:7600" "AKM:5:7510:300:7610" --output spawner.json

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

# List files on the server
files = client.list_files("/games/12345/ftproot/dayzxb/config/")
for file in files:
    print(f"{file['name']} - {file['size']} bytes")

# Download a file
content = client.download_file("/games/12345/ftproot/dayzxb/config/server.cfg")
with open("local_server.cfg", "wb") as f:
    f.write(content)
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

## License

This project is open source and available under the MIT License.

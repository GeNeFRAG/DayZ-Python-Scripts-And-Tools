# DayZ Admin Tools

A Python package for DayZ server administration, providing tools for server management, log analysis, XML file manipulation, and more. This package is particularly focused on simplifying common tasks for DayZ server administrators.

## Features

- **XML Management**: Comprehensive tools for working with DayZ's types.xml, mapgroupproto.xml, and other economy files
- **Log Analysis**: Tools for downloading, analyzing, and extracting useful information from server logs
- **JSON Processing**: Utilities for working with DayZ's JSON configuration files like cfgEffectArea.json
- **Nitrado Integration**: Tools specifically designed for interacting with Nitrado-hosted DayZ servers
- **Configuration Management**: Robust configuration system for storing server paths, settings, and credentials

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
├── nitrado/         # Tools for Nitrado servers
├── tools/           # Admin tools for various tasks
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

- **Compare Types**: Compare two types.xml files (`dayz-compare-types`)
- **Change Min/Max**: Update quantmin and quantmax values by pattern (`dayz-change-min-max`)
- **Check Usage Tags**: Validate usage tags (`dayz-check-usage-tags`)
- **Copy Types Values**: Copy values between types.xml files (`dayz-copy-types-values`)
- **Replace Usage/Value Tags**: Update tags in types.xml (`dayz-replace-usagevalue-tag-types`)
- **Sort Types by Usage**: Organize types.xml by usage categories (`dayz-sort-types-usage`)
- **Static Event Item Counter**: Count items in static events (`dayz-sum-staticbuilder-items`, `dayz-sum-staticmildrop-items`)
- **Sync CSV to Types**: Update types.xml from CSV data (`dayz-sync-csv-to-types`)
- **Types to Excel**: Convert between types.xml and Excel formats (`dayz-types-to-excel`)

### XML Proto Tools

- **Compare Lootmax**: Compare and merge lootmax values (`dayz-compare-lootmax`)
- **Deathmatch Config**: Configure deathmatch settings (`dayz-deathmatch-config`)

### Log Tools

- **Position Finder**: Find player positions in log files (`dayz-position-finder`)
- **Duping Detector**: Detect suspicious duplication activities (`dayz-duping-detector`)
- **Search Overtime**: Find overtime issues in logs (`dayz-search-overtime`)
- **Kill Tracker**: Track player kills and deaths (`dayz-kill-tracker`)
- **Log Downloader**: Download server logs from Nitrado (`dayz-download-logs`)
- **Log Filter Profiles**: Filter logs using pre-defined profiles (`dayz-log-filter-profiles`)

### JSON Tools

- **Calculate 3D Area**: Calculate 3D areas from JSON files (`dayz-calculate-3d-area`)
- **Generate Spawner Entries**: Generate spawner entries from data (`dayz-generate-spawner-entries`)
- **Sum Items JSON**: Sum and analyze items in JSON files (`dayz-sum-items-json`)
- **Split Loot Structures**: Split large loot structure files (`dayz-split-loot-structures`)

## Usage Examples

### XML Types Management

Work with types.xml files for your DayZ server:

```bash
# Compare two types.xml files
dayz-compare-types vanilla_types.xml custom_types.xml differences.csv

# Change min/max values for specific item types
dayz-change-min-max "Ammo*" 15 45 --xml types.xml

# Convert types.xml to Excel for easy editing
dayz-types-to-excel --to-excel types.xml types.xlsx

# Sort types.xml by usage categories
dayz-sort-types-usage types.xml sorted_types.xml
```

### Log Analysis

Analyze server logs for useful information:

```bash
# Download logs from Nitrado server
dayz-download-logs --days 3

# Find player positions in logs
dayz-position-finder --player "SurvivorName" --log-dir ./logs

# Detect possible duping activity
dayz-duping-detector --log-dir ./logs --output ./reports/duping_report.csv

# Track player kills
dayz-kill-tracker --output ./reports/kills.csv
```

### JSON Configuration

Work with DayZ's JSON configuration files:

```bash
# Calculate areas from effect area JSON
dayz-calculate-3d-area --json cfgEffectArea.json --output areas.csv

# Split large loot structure files
dayz-split-loot-structures --input large_structures.json --output-dir ./structures
```

### Working with Configuration

```python
from config.config import Config

# Load configuration from a profile
config_obj = Config(profile="my_server")
config = config_obj.get()

# Access configuration values
output_path = config.get('general.output_path')
types_file = config.get('paths.types_file')

# Print available configuration profiles
print(f"Available profiles: {config_obj.list_profiles()}")
```

### Using the Nitrado API Client

```python
from dayz_admin_tools.nitrado import api_client
from config.config import Config

# Load configuration
config = Config().get()

# Create an API client
client = api_client.NitradoAPIClient(config)

# List files on the server
files = client.list_files("/gameservers/file_server/mpmissions")
for file in files:
    print(f"{file['name']} - {file['size']} bytes")

# Download a file
client.download_file("/gameservers/file_server/mpmissions/dayzOffline.chernarusplus/types.xml", 
                     "./downloads/types.xml")
```

### XML Types Manipulation

```python
from dayz_admin_tools.xml.types import compare_types

# Initialize a tool
tool = compare_types.CompareTypesTool()

# Compare two types.xml files
differences = tool.compare_files("original.xml", "modified.xml", "differences.csv")
print(f"Found {len(differences)} differences")

# Print a summary of the changes
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
- [Log Module](src/dayz_admin_tools/log/README.md) - Tools for log analysis
- [Nitrado Module](src/dayz_admin_tools/nitrado/README.md) - Tools for Nitrado integration

## License

This project is open source and available under the MIT License.

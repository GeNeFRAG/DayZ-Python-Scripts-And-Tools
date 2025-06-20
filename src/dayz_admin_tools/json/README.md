# DayZ Admin Tools - JSON Module

A collection of tools for working with DayZ JSON files, enabling efficient server administration and map development.

## Overview

The JSON module provides specialized utilities for processing DayZ's JSON format files, which are commonly used for object placement, item spawning, and other server configuration tasks. These tools help server administrators analyze item distributions, calculate areas, generate spawner configurations, and organize objects for effective server management.

All tools in this module inherit from the `JSONTool` base class, providing consistent file handling, configuration management, and error logging capabilities.

## Available Tools

### Calculate 3D Area

**Module**: `calculate_3d_area.py`  
**CLI Command**: `dayz-calculate-3d-area`

Calculates the dimensions, area, and volume of a 3D space occupied by objects in a JSON file. Useful for planning construction, analyzing player bases, or determining the dimensions of custom areas.

**Features**:
- Calculate precise width, length, and height dimensions
- Determine the center point coordinates
- Compute total area (square units) and volume (cubic units)
- Identify corner coordinates for boundary visualization
- Generate box placements for area representation
- Export results to JSON format

**Usage**:
```bash
# Basic usage with default options
dayz-calculate-3d-area input.json --output results.json

# Advanced usage with box size options
dayz-calculate-3d-area input.json --output results.json --max-box-size 75 --profile my_profile
```

**Python API**:
```python
from dayz_admin_tools.json import Calculate3DArea

calculator = Calculate3DArea(config)
results = calculator.run("input.json", max_box_size=50)
print(f"Area dimensions: {results['width']} x {results['length']} x {results['height']}")
```

### Generate Spawner Entries

**Module**: `generate_spawner_entries.py`  
**CLI Command**: `dayz-generate-spawner-entries`

Creates DayZ object spawner JSON entries from specifications. Takes item names, quantities, and positions to generate properly formatted JSON that can be used directly in DayZ servers.

**Features**:
- Validate items against types.xml (optional)
- Set custom orientation (yaw, pitch, roll)
- Configure item scale and Central Economy persistence flags
- Add custom string attributes (for map/mod compatibility)
- Output to JSON file or standard output for piping

**Usage**:
```bash
# Basic format: item:quantity:x:y:z
dayz-generate-spawner-entries "Barrel_Green:2:7500:300:7600" "AKM:5:7510:300:7610" --output spawner.json

# With types.xml validation and custom orientation
dayz-generate-spawner-entries --types-xml types.xml "Land_Wreck_Ikarus:1:7500:300:7600:90:0:0" --output wrecks.json
```

**Python API**:
```python
from dayz_admin_tools.json import GenerateSpawnerEntries

generator = GenerateSpawnerEntries(config)
entries = generator.run(
    item_specs=["Barrel_Green:2:7500:300:7600", "AKM:5:7510:300:7610"],
    types_xml="types.xml"
)
# Process or save entries
```

### Sum Items JSON

**Module**: `sum_items_json.py`  
**CLI Command**: `dayz-sum-items-json`

Analyzes and aggregates item counts across multiple JSON files. Useful for server administrators who want to inventory items across different areas, analyze loot distribution, or balance spawns.

**Features**:
- Count unique items across multiple JSON files
- Filter objects by name patterns
- Exclude or include static objects (buildings, structures)
- Sort items by frequency or name
- Export results to CSV format for spreadsheet analysis

**Usage**:
```bash
# Basic usage
dayz-sum-items-json output.csv file1.json file2.json file3.json

# With filtering options
dayz-sum-items-json output.csv --include-static --sort-by frequency *.json
```

**Python API**:
```python
from dayz_admin_tools.json import SumItemsJson

counter = SumItemsJson(config)
results = counter.run(
    input_files=["area1.json", "area2.json"], 
    output_file="inventory.csv",
    include_static=True
)
print(f"Found {len(results)} unique items")
```

### Split Loot Structures

**Module**: `split_loot_structures.py`  
**CLI Command**: `dayz-split-loot-structures`

Separates DayZ JSON objects into loot items and structures based on types.xml classifications. Useful for map makers who need to organize objects by type for different processing workflows.

**Features**:
- Intelligently classify objects as loot or structures based on types.xml
- Process complete JSON object files
- Handle normalized name matching for consistent classification
- Generate separate output files for each category
- Support for custom classification rules

**Usage**:
```bash
# Basic usage
dayz-split-loot-structures --types-xml types.xml --input-json objects.json

# With custom options
dayz-split-loot-structures --types-xml types.xml --input-json objects.json --loot-json loot.json --structures-json structures.json --profile my_profile
```

**Python API**:
```python
from dayz_admin_tools.json import SplitLootStructures

splitter = SplitLootStructures(config)
results = splitter.run(
    types_xml="types.xml",
    input_json="my_bigcustom.json",
    loot_json="my_bigcustom_loot.json",
    structures_json="my_bigcustom_structures.json"
)
print(f"Split {results['total']} objects into {results['loot_count']} loot items and {results['structure_count']} structures")
```

## Configuration

All tools use the central configuration system from the `Config` class. You can specify a configuration profile with the `--profile` argument for any command.

**Configuration Structure**:
```json
{
  "general": {
    "data_directory": "data",
    "output_path": "output",
    "backup_directory": "backups",
    "log_level": "INFO",
    "debug": false
  }
}
```

## Common Base Functionality

All JSON tools inherit from the `JSONTool` base class, which provides:

- Standard JSON file reading and writing
- Path resolution and directory management
- Consistent error handling and logging
- Configuration integration

This ensures that all tools maintain a consistent interface and behavior while focusing on their specific functionality.

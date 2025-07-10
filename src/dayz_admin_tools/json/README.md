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
dayz-calculate-3d-area input.json --max-box-size 50

# With custom box size and profile
dayz-calculate-3d-area input.json --max-box-size 75 --profile myserver

# Enable detailed console output
dayz-calculate-3d-area input.json --console
```

**Parameters**:
- `json_file`: Path to the JSON file containing object positions (required)
- `--max-box-size`: Maximum box size to consider for optimization (optional, default: 50)
- `--profile`: Configuration profile to use (optional, uses default if not specified)
- `--console`: Log detailed output summary (optional)

**Python API**:
```python
from dayz_admin_tools.json.calculate_3d_area import Calculate3DArea

# Load configuration
config = Calculate3DArea.load_config("myserver")  # or None for default
calculator = Calculate3DArea(config)

# Calculate area with custom box size
results = calculator.run("input.json", max_box_size=50)

# Access results
print(f"Dimensions: {results['dimensions']['x']} x {results['dimensions']['y']} x {results['dimensions']['z']}")
print(f"Volume: {results['volume']} cubic units")
print(f"Optimal box size: {results['optimal_box']['dimensions']}")
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
dayz-generate-spawner-entries --types_xml types.xml "Land_Wreck_Ikarus:1:7500:300:7600" --ypr "90,0,0" --output wrecks.json

# With custom settings and printing to stdout
dayz-generate-spawner-entries "Barrel_Green:1:7500:300:7600" --scale 1.5 --enableCEPersistence 1 --customString "mymod" --print

# Use configured types.xml path
dayz-generate-spawner-entries --profile myserver "AKM:3:7500:300:7600"
```

**Parameters**:
- `items`: Item(s) in format `<item>:<amount>:<x>:<y>:<z>` (required, can specify multiple)
- `--types_xml`: Path to types.xml (optional, uses `paths.types_file` from config if not specified)
- `--ypr`: YPR (yaw, pitch, roll) as comma-separated values (optional, default: "0.0, -0.0, -0.0")
- `--scale`: Scale factor for objects (optional, default: 1.0)
- `--enableCEPersistence`: Enable Central Economy persistence (optional, default: 0)
- `--customString`: Custom string attribute (optional, default: empty)
- `--output, -o`: Output file (optional, uses default filename in output directory if not specified)
- `--print`: Print the generated JSON to stdout (optional)
- `--profile`: Configuration profile to use (optional, uses default if not specified)
- `--console`: Log detailed output summary (optional)

**Python API**:
```python
from dayz_admin_tools.json.generate_spawner_entries import GenerateSpawnerEntries

# Load configuration
config = GenerateSpawnerEntries.load_config("myserver")
generator = GenerateSpawnerEntries(config)

# Generate entries with custom parameters
entries = generator.run(
    types_xml="types.xml",
    items=["Barrel_Green:2:7500:300:7600", "AKM:5:7510:300:7610"],
    ypr="0.0, -0.0, -0.0",
    scale=1.0,
    enable_ce_persistence=0,
    custom_string="",
    output_file="spawner.json",
    print_output=False
)
print(f"Generated {len(entries)} spawner entries")
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
# Basic usage with output file
dayz-sum-items-json --output inventory.csv file1.json file2.json file3.json

# Use wildcard patterns and custom types.xml
dayz-sum-items-json --types-xml custom_types.xml --output results.csv *.json

# Use configured paths
dayz-sum-items-json --profile myserver area1.json area2.json

# Process files with default output filename
dayz-sum-items-json file1.json file2.json
```

**Parameters**:
- `json_files`: JSON files to process (required, can specify multiple files or use wildcards)
- `--output, -o`: Path to the output CSV file (optional, generates default name in output directory if not specified)
- `--types-xml, -t`: Path to types.xml file for item validation (optional, uses `paths.types_file` from config if not specified)
- `--profile`: Configuration profile to use (optional, uses default if not specified)
- `--console`: Log detailed output summary (optional)

**Python API**:
```python
from dayz_admin_tools.json.sum_items_json import SumItemsJson

# Load configuration
config = SumItemsJson.load_config("myserver")
counter = SumItemsJson(config)

# Process files and generate CSV
results = counter.run(
    json_files=["area1.json", "area2.json"], 
    output_csv="inventory.csv",
    types_xml="types.xml"
)

# Access results - returns dict with item counts and validation info
print(f"Found {len(results)} unique items")
valid_items = sum(1 for info in results.values() if info['valid'])
print(f"Valid items: {valid_items}")
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
# Basic usage with required parameters
dayz-split-loot-structures --types-xml types.xml --input-json objects.json

# With custom output files
dayz-split-loot-structures --types-xml types.xml --input-json objects.json --loot-json loot.json --structures-json structures.json

# Use configured types.xml path
dayz-split-loot-structures --input-json my_bigcustom.json --profile myserver

# With detailed console output
dayz-split-loot-structures --types-xml types.xml --input-json objects.json --console
```

**Parameters**:
- `--input-json`: Input JSON file with objects (required)
- `--types-xml`: Path to types.xml (optional, uses `paths.types_file` from config if not specified)
- `--loot-json`: Output JSON file for loot objects (optional, uses default path in output directory if not specified)
- `--structures-json`: Output JSON file for structure objects (optional, uses default path in output directory if not specified)
- `--profile`: Configuration profile to use (optional, uses default if not specified)
- `--console`: Log detailed output summary (optional)

**Python API**:
```python
from dayz_admin_tools.json.split_loot_structures import SplitLootStructures

# Load configuration
config = SplitLootStructures.load_config("myserver")
splitter = SplitLootStructures(config)

# Split objects into loot and structures
results = splitter.run(
    types_xml="types.xml",
    input_json="my_bigcustom.json",
    loot_json="my_bigcustom_loot.json",
    structures_json="my_bigcustom_structures.json"
)

print(f"Split {results['total_objects']} objects:")
print(f"  - {results['loot_count']} loot items")
print(f"  - {results['structure_count']} structures")
print(f"  - {results['unknown_count']} unknown items")
```

## Configuration

All tools use the central configuration system from the `Config` class. You can specify a configuration profile with the `--profile` argument for any command.

### Common Parameters

All JSON tools support these standard command-line parameters:

- `--profile`: Configuration profile to use (optional, uses default profile if not specified)
- `--console`: Log detailed output summary in addition to regular logging (optional)

### Configuration Structure
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

# DayZ Admin Tools - XML Types Module

Advanced tools for working with DayZ's types.xml and related economy configuration files.

## Overview

The XML Types module provides a comprehensive toolkit for manipulating and analyzing the core economy files in DayZ servers. These tools help server administrators adjust loot distribution, optimize server performance, and maintain consistent gameplay balance.

## Available Tools

### Compare Types Tool

**CLI Command**: `dayz-compare-types`

Compares two types.xml files and identifies differences between them for quick analysis of changes.

**Usage:**
```bash
# Basic comparison between two files
dayz-compare-types vanilla_types.xml custom_types.xml

# Save comparison to specific output directory
dayz-compare-types vanilla_types.xml custom_types.xml --output-dir /path/to/output

# Use specific configuration profile
dayz-compare-types file1.xml file2.xml --profile myserver --output-dir results/
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `types_xml1` | - | Yes | - | Path to the first types.xml file |
| `types_xml2` | - | Yes | - | Path to the second types.xml file |
| `--output-dir` | - | No | general.output_path | Directory to store output files (overrides config) |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |

**Features**:
- Detects differences in nominal, min, lifetime, and other values
- Generates timestamped CSV output for easy comparison in spreadsheets
- Highlights missing or added items between files

### Change Min/Max Tool

**CLI Command**: `dayz-change-min-max`

Updates quantmin and quantmax values for items matching specific patterns - perfect for bulk adjustments to loot quantities.

**Usage:**
```bash
# Increase all ammunition quantities
dayz-change-min-max --pattern "Ammo*" --quantmin 15 --quantmax 45 --xml types.xml

# Update food quantities using profile config path
dayz-change-min-max --pattern "Food*" --quantmin 3 --quantmax 8

# Use specific configuration profile
dayz-change-min-max --pattern "Weapon*" --quantmin 1 --quantmax 3 --profile myserver
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `--pattern` | - | Yes | - | Wildcard pattern to match type names (e.g., "Ammo*") |
| `--quantmin` | - | Yes | - | New quantmin value |
| `--quantmax` | - | Yes | - | New quantmax value |
| `--xml` | - | No | paths.types_file | Path to types.xml file |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |

**Features**:
- Updates quantities using wildcard pattern matching
- Preserves special values (like -1)
- Creates automatic backup before modification

### Check Usage Tags Tool

**CLI Command**: `dayz-check-usage-tags`

Validates usage tags against a cfglimitsdefinition.xml file to ensure proper item categorization.

**Usage:**
```bash
# Check types.xml against cfglimitsdefinition.xml using config paths
dayz-check-usage-tags

# Check specific files
dayz-check-usage-tags --cfglimits cfglimitsdefinition.xml --xml_file types.xml

# Check only mapgroupproto.xml
dayz-check-usage-tags --mapgroupproto_only

# Check only types.xml
dayz-check-usage-tags --types_only

# Custom output paths
dayz-check-usage-tags --csv results.csv --summary-csv summary.csv
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `--cfglimits` | - | No | paths.cfglimitsdefinition_file | Path to the cfglimitsdefinition.xml file |
| `--xml_file` | - | No | - | Path to a specific XML file to check |
| `--mapgroupproto_only` | - | No | - | Check only mapgroupproto.xml instead of both files |
| `--types_only` | - | No | - | Check only types.xml instead of both files |
| `--csv` | - | No | general.output_path | Custom path for CSV output file |
| `--summary-csv` | - | No | general.output_path | Custom path for summary CSV output file |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |

**Features**:
- Identifies invalid usage tags that could cause loot distribution issues
- Works with both types.xml and mapgroupproto.xml files
- Provides detailed reports and summary statistics of problematic tags

### Copy Types Values Tool

**CLI Command**: `dayz-copy-types-values`

Copies specific values (lifetime, nominal, min, etc.) from one types.xml to another.

**Usage:**
```bash
# Copy lifetime values from vanilla to modded types.xml
dayz-copy-types-values --element lifetime --target_file modded.xml --src_file vanilla.xml

# Copy nominal values using profile config source
dayz-copy-types-values --element nominal --target_file target.xml

# Copy values only for weapons
dayz-copy-types-values --element nominal --target_file target.xml --type_name "Weapon*"

# Use specific configuration profile
dayz-copy-types-values --element lifetime --target_file target.xml --profile myserver
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `--element` | - | Yes | - | The XML element to copy (e.g., lifetime, nominal, min) |
| `--target_file` | - | Yes | - | The target XML file path |
| `--src_file` | - | No | paths.types_file | The source XML file path |
| `--type_name` | - | No | - | Wildcard pattern to match type names (e.g., Zmbf*) |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |

**Features**:
- Selectively copy specific element values
- Filter by type name pattern
- Preserves XML structure and comments

### Replace Usage/Value Tags Tool

**CLI Command**: `dayz-replace-usagevalue-tag-types`

Updates usage and value tags in a types.xml file based on a reference file or custom value.

**Usage:**
```bash
# Copy usage and value tags from reference file using config paths
dayz-replace-usagevalue-tag-types --target_file target.xml

# Copy usage and value tags from specific reference file
dayz-replace-usagevalue-tag-types --target_file target.xml --src_file reference.xml

# Apply a single usage tag to all items
dayz-replace-usagevalue-tag-types --target_file target.xml --usage_tag "Military"

# Use specific configuration profile
dayz-replace-usagevalue-tag-types --target_file target.xml --profile myserver
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `--target_file` | - | Yes | - | The target XML file path |
| `--src_file` | - | No | paths.types_file | The source XML file path |
| `--usage_tag` | - | No | - | Usage tag to be added to all types |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |

**Features**:
- Copy usage and value tags from a reference file
- Apply a single usage tag to all items
- Preserve other attributes and XML structure

### Sort Types by Usage Tool

**CLI Command**: `dayz-sort-types-usage`

Organizes types.xml by usage categories for improved readability and analysis.

**Usage:**
```bash
# Sort types.xml using config path
dayz-sort-types-usage

# Sort specific types.xml file
dayz-sort-types-usage --xml types.xml

# Use specific configuration profile
dayz-sort-types-usage --profile myserver --xml custom_types.xml
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `--xml` | - | No | paths.types_file | Path to types.xml file |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |

**Features**:
- Groups items by usage category
- Maintains all attributes and values
- Improves file readability for manual editing
- Creates automatic backup before modification

### Static Event Item Counter Tools

**CLI Commands**: `dayz-sum-staticbuilder-items` and `dayz-sum-staticmildrop-items`

Two specialized tools for counting items in static events.

#### Static Builder Items Counter

**Usage:**
```bash
# Count items in builder events using config paths
dayz-sum-staticbuilder-items

# Count items with specific files
dayz-sum-staticbuilder-items --events cfgeventspawns.xml --groups cfgeventgroups.xml

# Custom output file
dayz-sum-staticbuilder-items --output builder_counts.csv
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `--events` | - | No | paths.events_file | Path to the events.xml file |
| `--groups` | - | No | paths.eventgroups_file | Path to the cfgeventgroups.xml file |
| `--output` | - | No | sb_loot.csv | Path to the output CSV file |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |

#### Static Military Drop Items Counter

**Usage:**
```bash
# Count items in military drop events using config paths
dayz-sum-staticmildrop-items

# Count items with specific files and debug output
dayz-sum-staticmildrop-items --events cfgeventspawns.xml --groups cfgeventgroups.xml --debug

# Custom output file
dayz-sum-staticmildrop-items --output mildrop_counts.csv
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `--events` | - | No | paths.events_file | Path to the events.xml file |
| `--groups` | - | No | paths.eventgroups_file | Path to the cfgeventgroups.xml file |
| `--output` | - | No | md_loot.csv | Path to the output CSV file |
| `--debug` | - | No | - | Enable debug logging |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |

**Features**:
- Analyze event spawner configurations
- Generate CSV reports of item counts
- Identify the most commonly used items

### Sync CSV to Types Tool

**CLI Command**: `dayz-sync-csv-to-types`

Updates nominal and min values in types.xml based on counts from a CSV file.

**Usage:**
```bash
# Update types.xml with data from one CSV file
dayz-sync-csv-to-types item_counts.csv

# Update with data from multiple CSV files
dayz-sync-csv-to-types counts1.csv counts2.csv counts3.csv

# Specify custom reference and output files
dayz-sync-csv-to-types item_counts.csv --reference vanilla.xml --output updated_types.xml

# Organize output by usage categories
dayz-sync-csv-to-types item_counts.csv --organize

# Use specific configuration profile
dayz-sync-csv-to-types item_counts.csv --profile myserver
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `csv_files` | - | Yes | - | One or more paths to input CSV files containing item counts |
| `--reference` | - | No | paths.types_file_ref | Path to the reference types.xml file |
| `--output` | - | No | paths.types_file | Path where the new XML file will be written |
| `--organize` | - | No | - | Organize the output XML file by usage categories with an index |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |

**Features**:
- Import quantity values from external data
- Automatically adjust loot distribution
- Maintain XML structure and comments
- Support for multiple CSV files

### Types to Excel Tool

**CLI Command**: `dayz-types-to-excel`

Converts between types.xml and Excel formats for easy editing in spreadsheets.

**Usage:**
```bash
# Convert types.xml to Excel using config paths
dayz-types-to-excel --to-excel

# Convert types.xml to Excel with specific files
dayz-types-to-excel --to-excel --input types.xml --output types.xlsx

# Convert Excel back to types.xml
dayz-types-to-excel --to-xml --input edited_types.xlsx --output new_types.xml

# Use specific configuration profile
dayz-types-to-excel --to-excel --profile myserver
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `--to-excel` | - | No | true | Convert XML to Excel (default behavior) |
| `--to-xml` | - | No | - | Convert Excel back to XML |
| `--input` | - | No | config paths | Input file path |
| `--output` | - | No | config paths | Output file path |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |

**Requirements**:
- Additional packages: `pip install pandas openpyxl`

**Features**:
- Bi-directional conversion between XML and Excel
- Preserve all attributes and values
- Simplify bulk editing in spreadsheet applications

## Common Parameters

All XML Types tools share these common parameters:

| Parameter | Description |
|-----------|-------------|
| `--profile` | Configuration profile to use (defaults to default profile if not specified) |
| `--console` | Log detailed output summary in addition to regular logging |

## Configuration

These tools can use the following configuration values from `src/config/profiles/default.json`:

```json
{
  "general": {
    "backup_directory": "backups",
    "output_path": "output",
    "log_level": "DEBUG"
  },
  "paths": {
    "types_file": "/path/to/types.xml",
    "types_file_ref": "/path/to/reference/types.xml",
    "events_file": "/path/to/cfgeventspawns.xml",
    "event_groups_file": "/path/to/cfgeventgroups.xml",
    "cfglimitsdefinition_file": "/path/to/cfglimitsdefinition.xml",
    "mapgroupproto_file": "/path/to/mapgroupproto.xml"
  }
}
```

Most tools accept file paths directly as arguments, so configuration is optional. When provided, configuration values serve as defaults when arguments are omitted.

## Common Workflows

### Synchronizing Economy Settings

Combine tools to efficiently update economy configurations:

```bash
# 1. Export types.xml to Excel for easy editing
dayz-types-to-excel --to-excel --input types.xml --output types.xlsx

# 2. After editing in Excel, convert back to XML
dayz-types-to-excel --to-xml --input types.xlsx --output new_types.xml

# 3. Sort by usage categories for better organization
dayz-sort-types-usage --xml new_types.xml

# 4. Validate usage tags
dayz-check-usage-tags --xml_file new_types.xml
```

### Analyzing Event Items

Count and analyze items used in static events:

```bash
# Count items in builder events
dayz-sum-staticbuilder-items --output builder.csv

# Count items in military drop events
dayz-sum-staticmildrop-items --output mildrop.csv

# Update types.xml with counts from analysis
dayz-sync-csv-to-types builder.csv mildrop.csv --organize
```

## Python API Usage

All tools can be used programmatically in Python scripts:

### Compare Types Tool

```python
from dayz_admin_tools.xml.types.compare_types import CompareTypesTool
from dayz_admin_tools.base import DayZTool

# Initialize tool with configuration
config = DayZTool.load_config()
tool = CompareTypesTool(config)

# Compare files
result = tool.run("vanilla.xml", "modded.xml")
print(f"Found {result['differences_count']} differences")
```

### Change Min/Max Tool

```python
from dayz_admin_tools.xml.types.change_min_max import ChangeMinMaxTool

# Initialize tool with configuration
config = DayZTool.load_config()
tool = ChangeMinMaxTool(config)

# Update quantities
result = tool.run("Ammo*", 15, 45, "types.xml")
print(f"Updated {result['changes_count']} items")
```

### Copy Types Values Tool

```python
from dayz_admin_tools.xml.types.copy_types_values import CopyTypesValuesTool

# Initialize tool with configuration
config = DayZTool.load_config()
tool = CopyTypesValuesTool(config)

# Copy values between files
tool.run("nominal", "target.xml", "Ammo*", "source.xml")
```

### Using with Configuration

```python
from dayz_admin_tools.xml.types.sync_csv_to_types import SyncCsvToTypesTool
from dayz_admin_tools.base import DayZTool

# Load configuration
config = DayZTool.load_config("myserver")

# Initialize tool with configuration
tool = SyncCsvToTypesTool(config)

# Sync CSV data to types.xml
result = tool.run(["counts.csv"], "reference.xml", "output.xml", True)
print(f"Updated types.xml with data from {len(result['csv_files'])} CSV files")
```
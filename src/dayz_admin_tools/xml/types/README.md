# DayZ Admin Tools - XML Types Module

Advanced tools for working with DayZ's types.xml and related economy configuration files.

## Overview

The XML Types module provides a comprehensive toolkit for manipulating and analyzing the core economy files in DayZ servers. These tools help server administrators adjust loot distribution, optimize server performance, and maintain consistent gameplay balance.

## Available Tools

### Compare Types Tool

Compares two types.xml files and identifies differences between them for quick analysis of changes.

**Command**: `dayz-compare-types`

**Features**:
- Detects differences in nominal, min, lifetime, and other values
- Generates CSV output for easy comparison in spreadsheets
- Highlights missing or added items between files

**Usage**:
```bash
# Basic comparison between two files
dayz-compare-types vanilla_types.xml custom_types.xml

# Save comparison to CSV file
dayz-compare-types vanilla_types.xml custom_types.xml differences.csv
```

### Change Min/Max Tool

Updates quantmin and quantmax values for items matching specific patterns - perfect for bulk adjustments to loot quantities.

**Command**: `dayz-change-min-max`

**Features**:
- Updates quantities using wildcard pattern matching
- Preserves special values (like -1)
- Offers dry-run mode to preview changes

**Usage**:
```bash
# Increase all ammunition quantities
dayz-change-min-max "Ammo*" 15 45 --xml types.xml

# Preview changes without modifying the file
dayz-change-min-max "Food*" 3 8 --xml types.xml --dry-run
```

### Check Usage Tags Tool

Validates usage tags against a cfglimitsdefinition.xml file to ensure proper item categorization.

**Command**: `dayz-check-usage-tags`

**Features**:
- Identifies invalid usage tags that could cause loot distribution issues
- Works with both types.xml and mapgroupproto.xml files
- Provides detailed reports of problematic tags

**Usage**:
```bash
# Check types.xml against cfglimitsdefinition.xml
dayz-check-usage-tags cfglimitsdefinition.xml types.xml

# Check mapgroupproto.xml for invalid usage tags
dayz-check-usage-tags cfglimitsdefinition.xml mapgroupproto.xml
```

### Copy Types Values Tool

Copies specific values (lifetime, nominal, min, etc.) from one types.xml to another.

**Command**: `dayz-copy-types-values`

**Features**:
- Selectively copy specific element values
- Filter by type name pattern
- Preserves XML structure and comments

**Usage**:
```bash
# Copy lifetime values from vanilla to modded types.xml
dayz-copy-types-values --element lifetime --src_file vanilla.xml --target_file modded.xml

# Copy nominal values only for weapons
dayz-copy-types-values --element nominal --src_file source.xml --target_file target.xml --type_name "Weapon*"
```

### Replace Usage/Value Tags Tool

Updates usage and value tags in a types.xml file based on a reference file or custom value.

**Command**: `dayz-replace-usagevalue-tag-types`

**Features**:
- Copy usage and value tags from a reference file
- Apply a single usage tag to all items
- Preserve other attributes and XML structure

**Usage**:
```bash
# Copy usage and value tags from reference file
dayz-replace-usagevalue-tag-types --src_file reference.xml target.xml output.xml

# Apply a single usage tag to all items
dayz-replace-usagevalue-tag-types --usage_tag "Military" target.xml output.xml
```

### Sort Types by Usage Tool

Organizes types.xml by usage categories for improved readability and analysis.

**Command**: `dayz-sort-types-usage`

**Features**:
- Groups items by usage category
- Maintains all attributes and values
- Improves file readability for manual editing

**Usage**:
```bash
# Sort and organize types.xml by usage categories
dayz-sort-types-usage types.xml sorted_types.xml
```

### Static Event Item Counter Tools

Two specialized tools for counting items in static events:

**Commands**:
- `dayz-sum-staticbuilder-items`: Count items used in builder events
- `dayz-sum-staticmildrop-items`: Count items used in military drop events

**Features**:
- Analyze event spawner configurations
- Generate CSV reports of item counts
- Identify the most commonly used items

**Usage**:
```bash
# Count items in builder events
dayz-sum-staticbuilder-items cfgeventspawns.xml cfgeventgroups.xml builder_counts.csv

# Count items in military drop events
dayz-sum-staticmildrop-items cfgeventspawns.xml cfgeventgroups.xml mildrop_counts.csv
```

### Sync CSV to Types Tool

Updates nominal and min values in types.xml based on counts from a CSV file.

**Command**: `dayz-sync-csv-to-types`

**Features**:
- Import quantity values from external data
- Automatically adjust loot distribution
- Maintain XML structure and comments

**Usage**:
```bash
# Update types.xml nominal/min values from CSV data
dayz-sync-csv-to-types item_counts.csv types.xml updated_types.xml
```

### Types to Excel Tool

Converts between types.xml and Excel formats for easy editing in spreadsheets.

**Command**: `dayz-types-to-excel`

**Features**:
- Bi-directional conversion between XML and Excel
- Preserve all attributes and values
- Simplify bulk editing in spreadsheet applications

**Requirements**:
- Additional packages: `pip install pandas openpyxl`

**Usage**:
```bash
# Convert types.xml to Excel spreadsheet
dayz-types-to-excel --to-excel types.xml types.xlsx

# Convert Excel back to types.xml
dayz-types-to-excel --to-xml edited_types.xlsx new_types.xml
```

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
dayz-types-to-excel --to-excel types.xml types.xlsx

# 2. After editing in Excel, convert back to XML
dayz-types-to-excel --to-xml types.xlsx new_types.xml

# 3. Sort by usage categories for better organization
dayz-sort-types-usage new_types.xml sorted_types.xml

# 4. Validate usage tags
dayz-check-usage-tags cfglimitsdefinition.xml sorted_types.xml
```

### Analyzing Event Items

Count and analyze items used in static events:

```bash
# Count items in builder events
dayz-sum-staticbuilder-items cfgeventspawns.xml cfgeventgroups.xml builder.csv

# Count items in military drop events
dayz-sum-staticmildrop-items cfgeventspawns.xml cfgeventgroups.xml mildrop.csv

# Update types.xml with counts from analysis
dayz-sync-csv-to-types builder.csv types.xml updated_types.xml
```

## Python API Usage

All tools can be used programmatically in Python scripts:

```python
from dayz_admin_tools.xml.types import compare_types
from dayz_admin_tools.base import DayZTool

# Initialize tool with default configuration
tool = compare_types.CompareTypesTool()

# Compare files
differences = tool.compare_files("vanilla.xml", "modded.xml", "differences.csv")
print(f"Found {len(differences)} differences")
```

### Using with Configuration

```python
from dayz_admin_tools.xml.types import copy_types_values
from config.config import Config

# Load configuration
config = Config().get()

# Initialize tool with configuration
tool = copy_types_values.CopyTypesValuesTool(config)

# Copy values between files
tool.copy_values(element="nominal", src_file="vanilla.xml", 
                target_file="modded.xml", type_name="Ammo*")
```
# DayZ Admin Tools - Command Line Utilities

This directory contains wrapper scripts for the command line utilities provided by the DayZ Admin Tools package.

## Naming Convention

All wrapper scripts follow the kebab-case naming pattern (e.g., `tool-name`) without file extensions.

## Usage

These scripts are designed to be executable from the command line:

```bash
./bin/tool-name [options]
```

After installing the package with pip, these tools will also be available in your system PATH with
the prefix `dayz-`:

```bash
dayz-tool-name [options]
```

## Available Tools

Here are the primary tools available:

### Log Management
- `download-logs` - Download server log files from Nitrado with filtering
- `log-filter-profiles` - Manage reusable log filtering profiles

### Player Analysis Tools
- `duping-detector` - Detect potential item duplication exploits and suspicious login patterns
- `kill-tracker` - Track and analyze player kills with rankings
- `position-finder` - Find player positions and activities in logs
- `search-overtime` - Identify items causing search overtime issues

### XML Types Tools
- `compare-types` - Compare two types.xml files and identify differences
- `change-min-max` - Modify quantmin/quantmax values in types.xml by pattern
- `check-usage-tags` - Validate usage tags against cfglimitsdefinition.xml
- `copy-types-values` - Copy specific values between types.xml files
- `replace-usagevalue-tag-types` - Update usage and value tags in types.xml
- `sort-types-usage` - Organize types.xml by usage categories
- `sum-staticbuilder-items` - Count items in static builder events
- `sum-staticmildrop-items` - Count items in static military drop events
- `sync-csv-to-types` - Update types.xml from CSV data with quantity adjustments
- `types-to-excel` - Convert between types.xml and Excel formats

### XML Proto Tools
- `compare-lootmax` - Compare and merge lootmax values between mapgroupproto files
- `compare_missing_groups` - Identify missing groups between mapgroupproto files
- `deathmatch-config` - Configure deathmatch settings with area filtering

### JSON Tools
- `calculate-3d-area` - Calculate 3D areas, dimensions, and volumes from JSON files
- `generate-spawner-entries` - Generate spawner entries from item specifications
- `sum-items-json` - Sum and analyze items in JSON files
- `split-loot-structures` - Split large loot structure files by type classification

For detailed usage instructions for each tool, run:

```bash
./bin/tool-name --help
```

## Development

When adding a new command-line tool:

1. Create a module with a `main()` function in the appropriate package
2. Register the entry point in `setup.py` using the pattern `dayz-tool-name=package.module:main`
3. Create a wrapper script in this directory following the naming convention

# DayZ Proto XML Tools

This package provides tools for working with DayZ proto XML files, specifically:
- `mapgroupproto.xml`: Defines loot spawning configuration for buildings
- `mapgrouppos.xml`: Defines building positions in the world

## Available Tools

### Lootmax Comparer (`compare_merge_lootmax_proto.py`)

**CLI Command**: `dayz-compare-lootmax`

This tool compares and optionally merges lootmax values between two mapgroupproto.xml files.

**Usage:**
```bash
# Basic comparison
dayz-compare-lootmax file1.xml file2.xml --output comparison.csv

# Compare and merge with custom filename
dayz-compare-lootmax file1.xml file2.xml --merge merged.xml

# Compare and merge with default filename
dayz-compare-lootmax file1.xml file2.xml --merge

# Use specific configuration profile
dayz-compare-lootmax file1.xml file2.xml --profile myserver --output comparison.csv
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `file1` | - | Yes | - | First proto XML file |
| `file2` | - | Yes | - | Second proto XML file |
| `--output` | `-o` | No | `lootmax_comparison.csv` | Filename for comparison output (timestamp added automatically) |
| `--merge` | `-m` | No | - | Enable merging and optionally provide a filename (defaults to `merged_mapgroupproto.xml` with timestamp if no filename provided) |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |



### Deathmatch Configuration Tool (`deathmatch_config_tool.py`)

**CLI Command**: `dayz-deathmatch-config`

This simplified tool creates DayZ Deathmatch server configurations in a single operation by:
1. Filtering buildings within a specific coordinate box
2. Removing usage tags from all buildings in the proto file
3. Applying a custom usage tag only to the buildings that were filtered

All output files are stored in the directory specified by `general.output_path` in the configuration.

**Usage:**
```bash
# Basic usage with required coordinates
dayz-deathmatch-config --ur-x 1000 --ur-y 1000 --ll-x 500 --ll-y 500

# Full configuration with custom files and usage tag
dayz-deathmatch-config \
    --mapgrouppos mapgrouppos.xml \
    --mapgroupproto mapgroupproto.xml \
    --ur-x 8600 --ur-y 12780 --ll-x 7820 --ll-y 12000 \
    --usage-tag Deathmatch

# With custom output filenames and verbose logging
dayz-deathmatch-config \
    --mapgrouppos mapgrouppos.xml \
    --mapgroupproto mapgroupproto.xml \
    --pos-output filtered_buildings.xml \
    --proto_output custom_proto.xml \
    --ur-x 1500 --ur-y 1500 --ll-x 1000 --ll-y 1000 \
    --usage-tag Arena --verbose
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `--mapgrouppos` | `-p` | No | `mapgrouppos.xml` | Path to the source mapgrouppos.xml file |
| `--pos-output` | `-f` | No | `deathmatch_<original>` | Filename for the filtered buildings output file (timestamp added automatically) |
| `--mapgroupproto` | `-m` | No | `mapgroupproto.xml` | Path to the source mapgroupproto.xml file |
| `--proto_output` | `-o` | No | `deathmatch_<original>` | Filename for the final output proto file (timestamp added automatically) |
| `--ur-x` | `-ux` | Yes | - | Upper right X coordinate of the deathmatch area |
| `--ur-y` | `-uy` | Yes | - | Upper right Y coordinate of the deathmatch area |
| `--ll-x` | `-lx` | Yes | - | Lower left X coordinate of the deathmatch area |
| `--ll-y` | `-ly` | Yes | - | Lower left Y coordinate of the deathmatch area |
| `--usage-tag` | `-u` | No | `Deathmatch` | Usage tag to apply (determines loot spawning) |
| `--verbose` | `-v` | No | - | Enable verbose logging |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |

### Missing Groups Comparer (`compare_missing_groups.py`)

**CLI Command**: `dayz-compare-missing-groups`

This tool compares two mapgroupproto.xml files and identifies groups that are missing in each file. It generates a comprehensive CSV report showing:

- Common groups that exist in both files
- Groups that are present in one file but missing in the other
- Summary statistics about the comparison

All output files include timestamps automatically and are stored in the directory specified by `general.output_path` in the configuration.

**Usage:**
```bash
# Basic comparison
dayz-compare-missing-groups file1.xml file2.xml --output comparison.csv

# Use default output filename
dayz-compare-missing-groups file1.xml file2.xml

# Use specific configuration profile
dayz-compare-missing-groups file1.xml file2.xml --profile server_2 --output group_comparison.csv
```

**Parameters:**
| Parameter | Short | Required | Default | Description |
|-----------|-------|----------|---------|-------------|
| `file1` | - | Yes | - | First mapgroupproto XML file |
| `file2` | - | Yes | - | Second mapgroupproto XML file |
| `--output` | `-o` | No | `missing_groups_comparison.csv` | Filename for comparison output CSV (timestamp added automatically) |
| `--profile` | - | No | default | Configuration profile to use |
| `--console` | - | No | - | Log detailed output summary |

**Output Format:**
The generated CSV file includes the following information:
- Metadata (comparison date, file paths)
- Summary statistics (total groups, common groups, missing groups)
- List of common groups present in both files
- List of groups missing in the first file
- List of groups missing in the second file

## Common Parameters

All proto XML tools share these common parameters:

| Parameter | Description |
|-----------|-------------|
| `--profile` | Configuration profile to use (defaults to default profile if not specified) |
| `--console` | Log detailed output summary in addition to regular logging |

## Configuration

The tools use the DayZ Admin Tools configuration system. These are the configuration values used from `src/config/profiles/default.json`:

```json
{
  "general": {
    "output_path": "output"
  }
}
```

All output files from the tools will be stored in the directory specified by `general.output_path`. If this isn't specified, it defaults to an "output" directory in the current working directory.

You don't need to configure any additional settings as the tools accept most parameters directly via command-line arguments.

## Python API Usage

You can also use these tools directly in Python code:

### LootmaxComparer

```python
from dayz_admin_tools.xml.proto.compare_merge_lootmax_proto import LootmaxComparer

# Initialize with config
config = {"general": {"output_path": "output"}}
comparer = LootmaxComparer(config)

# Set up files
comparer.file1 = "proto1.xml"
comparer.file2 = "proto2.xml"
comparer.output_file = "comparison.csv"
comparer.merge_output_file = "merged.xml"

# Run comparison and merge
success = comparer.run()
```

### DeathmatchConfigTool

```python
from dayz_admin_tools.xml.proto.deathmatch_config_tool import DeathmatchConfigTool

# Initialize with config
config = {"general": {"output_path": "output"}}
tool = DeathmatchConfigTool(config)

# Set up parameters
tool.mapgrouppos_file = "mapgrouppos.xml"
tool.mapgroupproto_file = "mapgroupproto.xml"
tool.deathmatch_area = (
    (500, 500),    # Lower left coordinates (ll_x, ll_y)
    (1000, 1000)   # Upper right coordinates (ur_x, ur_y)
)
tool.usage_tag = "Deathmatch"

# Run the tool
success = tool.run()
```

### MissingGroupsComparer

```python
from dayz_admin_tools.xml.proto.compare_missing_groups import MissingGroupsComparer

# Initialize with config
config = {"general": {"output_path": "output"}}
comparer = MissingGroupsComparer(config)

# Set up files
comparer.file1 = "proto1.xml"
comparer.file2 = "proto2.xml"
comparer.output_file = "missing_groups.csv"

# Run comparison
success = comparer.run()
```
```

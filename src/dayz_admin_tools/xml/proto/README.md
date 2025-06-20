# DayZ Proto XML Tools

This package provides tools for working with DayZ proto XML files, specifically:
- `mapgroupproto.xml`: Defines loot spawning configuration for buildings
- `mapgrouppos.xml`: Defines building positions in the world

## Available Tools

### Lootmax Comparer (`compare_merge_lootmax_proto.py`)

This tool compares and optionally merges lootmax values between two mapgroupproto.xml files.

**Usage:**
```bash
dayz-compare-lootmax file1.xml file2.xml --output comparison.txt --merge merged.xml
```

**Arguments:**
- `file1`: First proto XML file
- `file2`: Second proto XML file
- `--output, -o`: Filename for comparison output (saved to general.output_path)
- `--merge, -m`: Enable merging and optionally provide a filename (defaults to merged_mapgroupproto.xml)
- `--config, -c`: Configuration profile to use (affects output paths)

**Example Usage:**
```bash
# Compare two proto files and save the comparison
dayz-compare-lootmax vanilla_proto.xml custom_proto.xml --output loot_comparison.txt

# Compare and merge, taking higher lootmax values
dayz-compare-lootmax vanilla_proto.xml custom_proto.xml --merge enhanced_proto.xml
```



### Deathmatch Configuration Tool (`deathmatch_config_tool.py`)

This simplified tool creates DayZ Deathmatch server configurations in a single operation by:
1. Filtering buildings within a specific coordinate box
2. Removing usage tags from all buildings in the proto file
3. Applying a custom usage tag only to the buildings that were filtered

All output files are stored in the directory specified by `general.output_path` in the configuration.

**Usage:**
```bash
dayz-deathmatch-config \
    --mapgrouppos=/path/to/mapgrouppos.xml \
    --mapgroupproto=/path/to/mapgroupproto.xml \
    --ur-x 1000 --ur-y 1000 --ll-x 500 --ll-y 500 \
    --usage-tag Deathmatch
```

**Arguments:**
- `--mapgrouppos, -p`: Path to the source mapgrouppos.xml file (default: mapgrouppos.xml)
- `--filtered-output, -f`: Filename for the filtered buildings output file (defaults to deathmatch_<original pos filename>)
- `--mapgroupproto, -m`: Path to the source mapgroupproto.xml file (default: mapgroupproto.xml)
- `--output, -o`: Filename for the final output proto file (defaults to deathmatch_<original proto filename>)
- `--ur-x, -ux`: Upper right X coordinate of the deathmatch area
- `--ur-y, -uy`: Upper right Y coordinate of the deathmatch area
- `--ll-x, -lx`: Lower left X coordinate of the deathmatch area
- `--ll-y, -ly`: Lower left Y coordinate of the deathmatch area
- `--usage-tag, -u`: Usage tag to apply (default: Deathmatch)
- `--verbose, -v`: Enable verbose logging
- `--config, -c`: Configuration profile to use

**Example Usage:**
```bash
# Create a deathmatch area around Severograd
dayz-deathmatch-config \
    --mapgrouppos=mapgrouppos.xml \
    --mapgroupproto=mapgroupproto.xml \
    --ur-x 8600 --ur-y 12780 --ll-x 7820 --ll-y 12000 \
    --usage-tag Deathmatch

# Configure a small arena with verbose output
dayz-deathmatch-config \
    --mapgrouppos=mapgrouppos.xml \
    --mapgroupproto=mapgroupproto.xml \
    --ur-x 1500 --ur-y 1500 --ll-x 1000 --ll-y 1000 \
    --usage-tag Arena --verbose
```
- `--ll-y, -ly`: Lower left Y coordinate of the deathmatch area
- `--usage-tag, -u`: Usage tag to apply (default: Deathmatch)
- `--config, -c`: Configuration profile to use (affects output paths)
- `--verbose, -v`: Enable verbose logging
- `--config, -c`: Configuration profile to use

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
```

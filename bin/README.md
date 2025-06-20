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
- `download-logs` - Download server log files from Nitrado
- `log-filter-profiles` - Manage log filtering profiles

### Analysis Tools
- `duping-detector` - Detect potential item duplication exploits
- `kill-tracker` - Track and analyze player kills
- `position-finder` - Find player positions in logs
- `search-overtime` - Identify items causing search overtime issues

### XML Tools
- `compare-types` - Compare types.xml files
- `change-min-max` - Modify min/max values in types.xml
- `check-usage-tags` - Check usage tags in XML files
- `copy-types-values` - Copy values between types.xml files
- And many more...

For detailed usage instructions for each tool, run:

```bash
./bin/tool-name --help
```

## Development

When adding a new command-line tool:

1. Create a module with a `main()` function in the appropriate package
2. Register the entry point in `setup.py` using the pattern `dayz-tool-name=package.module:main`
3. Create a wrapper script in this directory following the naming convention

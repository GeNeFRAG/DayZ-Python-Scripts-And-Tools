# Nitrado API Client for DayZ Server Administration

This package provides a generic wrapper for the Nitrado API, allowing interactions with Nitrado-hosted DayZ servers for file operations and other basic functionalities.

**Note**: This module is a pure library component and does not provide any command-line tools. It serves as the foundation API client for other modules (like the Log module) that need to interact with Nitrado servers.

## Components

### API Client (`api_client.py`)

The `NitradoAPIClient` class provides a clean, generic interface for interacting with the Nitrado API:

- Authentication with API tokens
- File operations (list, download, upload)
- Player list management (ban lists, whitelist, priority/admin lists)
- Server settings management

The client is designed to be a minimal wrapper around the Nitrado API, providing core functionality that can be used by higher-level modules.

### Python API Usage

```python
from dayz_admin_tools.nitrado.api_client import NitradoAPIClient

# Load configuration with API credentials
config = NitradoAPIClient.load_config('my_profile')  # or None for default

# Initialize the API client
client = NitradoAPIClient(config)

# List files in a directory
files = client.list_files('/games/12345/ftproot/dayzxb/config/')
for file in files:
    print(f"{file['name']} - {file['size']} bytes")

# Download a file
content = client.download_file('/games/12345/ftproot/dayzxb/config/server.cfg')
with open('local_server.cfg', 'wb') as f:
    f.write(content)
    
# Upload a file
client.upload_file('local_types.xml', '/games/12345/ftproot/dayzxb/mpmissions/dayzOffline.chernarusplus/db/types.xml')

# Player List Management
# Get current ban list
ban_list = client.get_banlist()
for player in ban_list:
    print(f"Banned player: {player['name']}")

# Add players to ban list
client.add_to_banlist(['cheater123', 'griefer456'])

# Remove players from ban list
client.remove_from_banlist(['reformed_player'])

# Whitelist operations
whitelist = client.get_whitelist()
client.add_to_whitelist(['admin1', 'moderator2'])
client.remove_from_whitelist(['former_admin'])

# Priority/Admin list operations
admin_list = client.get_prioritylist()  # or get_adminlist()
client.add_to_prioritylist(['new_admin'])
client.remove_from_prioritylist(['demoted_admin'])

# Generic list operations (more flexible)
# Works with 'bans', 'whitelist', 'priority'
ban_list = client.get_list('bans')
client.add_to_list('whitelist', ['player1', 'player2'])
client.remove_from_list('priority', ['old_admin'])
```

**Available Methods**:

*File Operations:*
- `list_files(directory_path)`: List files in a remote directory
- `download_file(remote_path)`: Download a file and return its content as bytes
- `upload_file(local_path, remote_path)`: Upload a local file to the remote server

*Player List Management:*
- `get_banlist()`, `get_whitelist()`, `get_prioritylist()`: Retrieve player lists
- `add_to_banlist(identifiers)`, `add_to_whitelist(identifiers)`, `add_to_prioritylist(identifiers)`: Add players to lists
- `remove_from_banlist(identifiers)`, `remove_from_whitelist(identifiers)`, `remove_from_prioritylist(identifiers)`: Remove players from lists
- `get_list(list_type)`, `add_to_list(list_type, identifiers)`, `remove_from_list(list_type, identifiers)`: Generic list operations

*Server Settings:*
- `update_server_setting(category, setting_name, value)`: Update individual server settings

## Integration with Other Tools

The API client is used by various tools in the DayZ Admin Tools suite:

### Log Downloader Integration

Used by the `NitradoLogDownloader` class (in the `log` package) for downloading server logs:

```python
from dayz_admin_tools.log.log_downloader import NitradoLogDownloader

# Load configuration with API credentials
config = NitradoLogDownloader.load_config('my_profile')  # or None for default

# Initialize the log downloader (which uses NitradoAPIClient internally)
downloader = NitradoLogDownloader(config)

# Download logs using various filtering options
result = downloader.run(
    output_dir="./logs",
    start_date="2025-05-01",
    end_date="2025-05-31",
    filename_patterns=["*.RPT", "*.ADM"]
)
```

### Player List Manager Integration

Used by the `PlayerListManagerTool` class for managing server player lists:

```python
from dayz_admin_tools.tools.player_list_manager import PlayerListManagerTool

# Load configuration with API credentials
config = PlayerListManagerTool.load_config('my_profile')

# Initialize the player list manager (which uses NitradoAPIClient internally)
manager = PlayerListManagerTool(config)

# Export current ban list to CSV
result = manager.run('banlist', 'export', output_file='current_bans.csv')

# Add players from CSV to whitelist
result = manager.run('whitelist', 'import', csv_file='new_admins.csv')
```

For log-specific functionality, please refer to the documentation in the `log` package.

## Command-Line Interface

**This module does not provide any command-line tools.** The Nitrado API client is designed as a pure library component that other modules can use programmatically. 

For command-line functionality that uses the Nitrado API, see:
- **Log Module**: `dayz-download-logs` command for downloading server logs
- **Player List Manager**: `dayz-player-list-manager` command for managing player lists (ban, whitelist, priority)
- **Other modules**: May use this API client internally for their specific functionality

If you need to interact with the Nitrado API from the command line, consider using the tools in other modules that are built on top of this API client.

## Configuration

The API client uses the configuration system provided by the `dayz_admin_tools` package. The following configuration values from `src/config/profiles/default.json` are used by the Nitrado API client:

```json
// Configuration in src/config/profiles/default.json
{
  "nitrado_server": {
    "mission_directory": "dayzOffline.chernarusplus",
    "remote_base_path": "/gameservers/file_server",
    "ssl_verify": false
  }
}
```

The following sensitive values are typically stored in a secrets file (`src/config/secrets/default_secrets.json`):

```json
// Sensitive configuration in secrets file
{
  "api_token": "your-nitrado-api-token",
  "service_id": "your-nitrado-service-id",
  "server_id": "your-game-server-id"
}
```

## Configuration Details

| Configuration Key | Description | Default Value | Required |
|------------------|-------------|---------------|---------|
| `api_token` | Nitrado API access token from developer settings | (none) | Yes |
| `service_id` | Your Nitrado service ID | (none) | Yes |
| `server_id` | Game Server ID (used for constructing file paths) | (none) | Yes |
| `nitrado_server.remote_base_path` | Base path for file operations | "/gameserver" | No |
| `nitrado_server.ssl_verify` | Whether to verify SSL certificates | true | No |

## Design Philosophy

The `NitradoAPIClient` is designed as a thin wrapper around the Nitrado HTTP API, providing:

- Basic authentication handling
- HTTP request handling with proper error logging
- Core file operations (list, download, upload)
- Player list management (bans, whitelist, priority lists)
- Server settings management

It deliberately avoids adding application-specific functionality, making it a stable base layer for other modules to build upon.

## Recent Improvements

The API client has been significantly refactored and simplified:

- **Removed unused methods**: Eliminated `bulk_update_lists` and obsolete settings sets approach
- **Correct API usage**: All player list operations now use the proven `/gameservers/settings` endpoint
- **Streamlined code**: Reduced codebase by ~20% while maintaining full functionality
- **Improved reliability**: Uses direct settings endpoint for immediate server configuration updates
- **Backward compatibility**: All existing method signatures preserved with convenience aliases
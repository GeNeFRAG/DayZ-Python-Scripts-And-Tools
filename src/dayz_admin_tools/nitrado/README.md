# Nitrado API Client for DayZ Server Administration

This package provides a generic wrapper for the Nitrado API, allowing interactions with Nitrado-hosted DayZ servers for file operations and other basic functionalities.

**Note**: This module is a pure library component and does not provide any command-line tools. It serves as the foundation API client for other modules (like the Log module) that need to interact with Nitrado servers.

## Components

### API Client (`api_client.py`)

The `NitradoAPIClient` class provides a clean, generic interface for interacting with the Nitrado API:

- Authentication with API tokens
- File operations (list, download, upload)

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
```

**Available Methods**:
- `list_files(directory_path)`: List files in a remote directory
- `download_file(remote_path)`: Download a file and return its content as bytes
- `upload_file(local_path, remote_path)`: Upload a local file to the remote server

## Integration with Log Downloader

The API client is used by the `NitradoLogDownloader` class (in the `log` package) for downloading server logs:

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

For log-specific functionality, please refer to the documentation in the `log` package.

## Command-Line Interface

**This module does not provide any command-line tools.** The Nitrado API client is designed as a pure library component that other modules can use programmatically. 

For command-line functionality that uses the Nitrado API, see:
- **Log Module**: `dayz-download-logs` command for downloading server logs
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

It deliberately avoids adding application-specific functionality, making it a stable base layer for other modules to build upon.
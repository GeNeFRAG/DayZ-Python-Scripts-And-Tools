# Nitrado API Client for DayZ Server Administration

This package provides a generic wrapper for the Nitrado API, allowing interactions with Nitrado-hosted DayZ servers for file operations and other basic functionalities.

## Components

### API Client (`api_client.py`)

The `NitradoAPIClient` class provides a clean, generic interface for interacting with the Nitrado API:

- Authentication with API tokens
- File operations (list, download, upload)

The client is designed to be a minimal wrapper around the Nitrado API, providing core functionality that can be used by higher-level modules.

```python
from dayz_admin_tools.nitrado.api_client import NitradoAPIClient
from dayz_admin_tools.config.config import Config

# Load configuration with API credentials
config_obj = Config(profile='my_profile')
config = config_obj.get()

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

## Integration with Log Downloader

The API client is used by the `NitradoLogDownloader` class (in the `log` package) for downloading server logs:

```python
from dayz_admin_tools.log.log_downloader import NitradoLogDownloader
from dayz_admin_tools.config.config import Config

# Load configuration with API credentials
config_obj = Config(profile='my_profile')
config = config_obj.get()

# Initialize the log downloader
downloader = NitradoLogDownloader(config)

# Download logs using various filtering options
downloader.run(
    output_dir="./logs",
    start_date="2025-05-01",
    end_date="2025-05-31",
    filename_patterns=["*.RPT", "*.ADM"]
)
```

For log-specific functionality, please refer to the documentation in the `log` package.

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
# Secrets Management

This directory contains sensitive configuration information like API keys, server IDs, and credentials for Nitrado servers.
**Files in this directory should never be committed to source control.**

## Files in This Directory

- `<profile>_secrets.json`: Profile-specific secrets files (e.g., `default_secrets.json`, `my_server_secrets.json`)
- `profile_secrets.json.example`: Example format for profile-specific secrets

## Nitrado API Credentials

The secrets files typically contain the following Nitrado API credentials:

- `api_token`: Your Nitrado API token for authentication
- `service_id`: The service ID for your Nitrado game server
- `server_id`: The server ID for your DayZ server

## Creating Secrets Files

### Profile-specific Secrets

Create a secrets file named `<profile_name>_secrets.json` for each profile that needs secret credentials:

1. Create a new secrets file for your profile:
   ```bash
   cp profile_secrets.json.example my_server_secrets.json  # for profile "my_server"
   ```

2. Edit with your profile-specific Nitrado credentials:
   ```json
   {
       "api_token": "profile-specific-api-token",
       "service_id": "profile-specific-service-id",
       "server_id": "profile-specific-server-id"
   }
   ```

### Default Profile Secrets

For the default profile, create a `default_secrets.json` file:

```json
{
    "api_token": "YOUR_NITRADO_API_TOKEN",
    "service_id": "YOUR_NITRADO_SERVICE_ID",
    "server_id": "YOUR_GAME_SERVER_ID"
}
```

## How Secrets Are Loaded

The configuration system loads secrets that correspond to the currently active profile only:

1. When a profile is loaded (e.g., `my_server`), the system looks for a corresponding secrets file (e.g., `my_server_secrets.json`).
2. If the secrets file is found, its contents are merged into the configuration, overriding any identical keys from the profile's JSON file.
3. If no secrets file exists for the profile, a warning is logged but loading continues without secrets.

Each profile has its own separate secrets file, maintaining isolation between different server environments.

## Obtaining Nitrado Credentials

To get your Nitrado API credentials:

1. Log in to your [Nitrado account](https://server.nitrado.net/)
2. Go to your account settings
3. Navigate to the "Developer" section
4. Generate an API token with appropriate permissions
5. Copy the service_id and server_id from your DayZ server details page

### Example Structure

```json
{
    "api_token": "your-nitrado-api-token",
    "service_id": "your-nitrado-service-id",
    "server_id": "your-game-server-id"
}
```

## Accessing Secrets in Code

Secrets are accessed through the configuration system like any other configuration value:

```python
# Import from the correct location
from src.config.config import config

# Access secret values the same way as regular config
api_token = config.get('api_token')
service_id = config.get('service_id')
server_id = config.get('server_id')

# Example of using in Nitrado API code
import requests

def get_server_details():
    api_token = config.get('api_token')
    service_id = config.get('service_id')
    
    headers = {'Authorization': f'Bearer {api_token}'}
    url = f'https://api.nitrado.net/services/{service_id}/gameservers'
    response = requests.get(url, headers=headers)
    return response.json()
```

## Security Best Practices

- **Never commit secrets to version control**
- Add all secrets files to `.gitignore`
- Use strong, unique passwords and API keys
- Regularly rotate your API tokens and credentials
- Never share these files through unencrypted channels
- Review and remove unused credentials periodically
- Regenerate credentials immediately if compromised
- Consider environment variables for CI/CD environments
- Limit file access permissions on shared systems

# Secrets Management

This directory contains sensitive configuration information like API keys, server IDs, and credentials for Nitrado servers.
**Files in this directory should never be committed to source control.**

## Files in This Directory

- `default_secrets.json`: Default secrets loaded for all profiles 
- `profile_secrets.json.example`: Example format for profile-specific secrets

## Nitrado API Credentials

The secrets files contain the following Nitrado API credentials:

- `api_token`: Your Nitrado API token for authentication
- `service_id`: The service ID for your Nitrado game server
- `server_id`: The server ID for your DayZ server

## Creating Secrets Files

### Default Secrets

To set up shared secrets that apply to all profiles:

1. If not already present, create a `default_secrets.json` file:
   ```json
   {
       "api_token": "YOUR_NITRADO_API_TOKEN",
       "service_id": "YOUR_NITRADO_SERVICE_ID",
       "server_id": "YOUR_GAME_SERVER_ID"
   }
   ```

2. Replace the placeholder values with your actual credentials

### Profile-specific Secrets

For secrets specific to a profile, create a file named `<profile_name>_secrets.json`:

1. Create a new secrets file for your profile:
   ```bash
   cp profile_secrets.json.example my_server_secrets.json  # for profile "my_server"
   ```

2. Edit with profile-specific Nitrado credentials:
   ```json
   {
       "api_token": "profile-specific-api-token",
       "service_id": "profile-specific-service-id",
       "server_id": "profile-specific-server-id"
   }
   ```

The configuration system prioritizes profile-specific secrets over default secrets, allowing you to maintain different credentials for different server environments.

## How Secrets Are Loaded

1. The configuration system automatically reads these files
2. Secret files are loaded after regular profiles
3. Profile-specific secrets override default secrets
4. All secrets override any identical keys in profile configs

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

### Accessing Secrets in Code

```python
from config import config

# Access secret values the same way as regular config
api_token = config.get('api_token')
service_id = config.get('service_id')
server_id = config.get('server_id')

# Example of using in Nitrado API code
import requests

def get_server_details():
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

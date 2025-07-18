"""
Nitrado API Client

This module provides a generic client for interacting with the Nitrado API for DayZ server management.
"""

import requests
import logging
from typing import Dict, Any, List, Optional
import urllib3
from ..base import DayZTool

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

NITRADO_API_BASE_URL = "https://api.nitrado.net/services/"

# Player list type constants
LIST_TYPE_WHITELIST = 'whitelist'
LIST_TYPE_BANS = 'bans'
LIST_TYPE_PRIORITY = 'priority'
VALID_LIST_TYPES = [LIST_TYPE_WHITELIST, LIST_TYPE_BANS, LIST_TYPE_PRIORITY]

# Line ending constants for player lists
LINE_ENDING_CRLF = '\r\n'  # Windows-style line ending (proper format)
LINE_ENDING_CR = '\r'      # Legacy carriage return only


class NitradoAPIClient(DayZTool):
    """Client for interacting with the Nitrado API."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the Nitrado API client.
        
        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        self._setup_client()
    
    def _setup_client(self) -> None:
        """Set up the API client with configuration values."""
        self.token = self.get_config('api_token', '')
        self.service_id = self.get_config('service_id', '')
        self.server_id = self.get_config('server_id', '')
        self.remote_base_path = self.get_config('nitrado_server.remote_base_path', '/gameserver')
        self.ssl_verify = self.get_config('nitrado_server.ssl_verify', True)
        
        if not self.token:
            logger.warning("No Nitrado API token provided. API calls will fail.")
        
        if not self.service_id:
            logger.warning("No Nitrado service ID provided. API calls will fail.")
            
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Debug logs to validate configuration loading
        logger.debug(f"API Token: {self.token}")
        logger.debug(f"Service ID: {self.service_id}")
        logger.debug(f"Server ID: {self.server_id}")
    
    def make_request(self, endpoint: str, method: str = 'GET', 
                    params: Optional[Dict[str, Any]] = None, 
                    data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a request to the Nitrado API.
        
        Args:
            endpoint: API endpoint path.
            method: HTTP method to use.
            params: Query parameters.
            data: Request body data.
            
        Returns:
            API response as a dictionary.
            
        Raises:
            requests.RequestException: If the request fails.
        """
        url = f"{NITRADO_API_BASE_URL}{self.service_id}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=data,
                verify=self.ssl_verify
            )
            
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def list_files(self, directory: str) -> List[Dict[str, Any]]:
        """
        List files in a directory on the server.
        
        Args:
            directory: Directory path.
            
        Returns:
            List of file information dictionaries.
        """
        params = {'dir': directory}
        response = self.make_request(f"{self.remote_base_path}/list", params=params)
        return response.get('data', {}).get('entries', [])
    
    def _get_download_token(self, remote_path: str) -> Dict[str, Any]:
        """
        Get a download token for a file from Nitrado.
        
        Args:
            remote_path: Path to the file on the server.
            
        Returns:
            Dictionary containing the download token information.
            
        Raises:
            requests.RequestException: If the request fails.
        """
        url = f"{NITRADO_API_BASE_URL}{self.service_id}{self.remote_base_path}/download"
        params = {'file': remote_path}
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                verify=self.ssl_verify
            )
            response.raise_for_status()
            logger.debug(f"Successfully fetched download token for {remote_path}")
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get download token: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise

    def download_file(self, remote_path: str) -> bytes:
        """
        Download a file from the server using Nitrado's two-step download process.
        
        Args:
            remote_path: Path to the file on the server.
            
        Returns:
            Binary content of the file.
            
        Raises:
            requests.RequestException: If the request fails.
            KeyError: If the response format is unexpected.
        """
        try:
            # Step 1: Get download token
            token_response = self._get_download_token(remote_path)
            
            if 'data' not in token_response or 'token' not in token_response['data']:
                raise KeyError(f"Invalid response format from Nitrado API for {remote_path}")
            
            # Extract token information
            token_data = token_response['data']['token']
            download_url = token_data['url']
            download_token = token_data['token']
            
            # Step 2: Download the actual file using the token
            download_response = requests.get(
                download_url,
                params={'token': download_token},
                verify=self.ssl_verify
            )
            
            download_response.raise_for_status()
            logger.info(f"Successfully downloaded {remote_path}")
            return download_response.content
            
        except (requests.RequestException, KeyError) as e:
            logger.error(f"Error downloading file {remote_path}: {e}")
            raise

    # Player Management - Server Settings Based Implementation
    
    def get_server_settings(self) -> Dict[str, Any]:
        """
        Retrieve the current server settings from the most recent settings set.
        
        Since the /gameservers/settings endpoint doesn't have a reliable GET method,
        we use the most recent settings set which contains the actual current configuration.
        
        Returns:
            Dictionary containing server settings.
            
        Raises:
            requests.RequestException: If the request fails.
        """
        try:
            # Get all settings sets
            response = self.make_request("/gameservers/settings/sets", method="GET")
            sets = response.get('data', {}).get('sets', [])
            logger.debug(f"Retrieved {len(sets)} settings sets from Nitrado API")
            
            if not sets:
                logger.warning("No settings sets found, falling back to defaults endpoint")
                # Fallback to defaults if no sets available
                response = self.make_request("/gameservers/settings/defaults", method="GET")
                return response.get('data', {}).get('settings', {})
            
            # Use the most recent set (first in the list)
            latest_set = sets[0]
            settings = latest_set.get('data', {}).get('settings', {})
            
            logger.debug(f"Using settings from latest set (ID: {latest_set.get('id')})")
            return settings
            
        except requests.RequestException as e:
            logger.error(f"Failed to retrieve server settings: {e}")
            raise
    
    def update_server_setting(self, category: str, setting_name: str, value: str) -> Dict[str, Any]:
        """
        Update a single server setting using the direct settings endpoint.
        
        Args:
            category: The settings category (e.g., "general")
            setting_name: The name of the setting to update
            value: The new value for the setting
            
        Returns:
            API response dictionary.
            
        Raises:
            requests.RequestException: If the request fails.
        """
        # Construct settings data for direct settings endpoint
        settings_data = {
            "category": category,
            "key": setting_name,
            "value": value
        }
        
        try:
            response = self.make_request(
                "/gameservers/settings",
                method="POST",
                data=settings_data
            )
            logger.debug(f"Successfully updated setting {category}.{setting_name} = {value}")
            return response
            
        except requests.RequestException as e:
            logger.error(f"Failed to update server setting {category}.{setting_name}: {e}")
            raise

    def _get_list_members(self, list_type: str) -> List[str]:
        """
        Helper method to get list members from active server settings.
        
        Args:
            list_type: Type of list ('whitelist', 'bans', 'priority').
            
        Returns:
            List of player identifiers.
        """
        # Get current active server settings (not settings sets)
        response = self.make_request("/gameservers", method="GET")
        settings = response.get('data', {}).get('gameserver', {}).get('settings', {})
        list_value = settings.get('general', {}).get(list_type, '')
        
        if not list_value:
            return []
        
        # Handle both \r\n and \r line endings for backward compatibility
        if LINE_ENDING_CRLF in list_value:
            members = list_value.split(LINE_ENDING_CRLF)
        else:
            members = list_value.split(LINE_ENDING_CR)
        
        # Filter out empty strings and strip whitespace
        return [member.strip() for member in members if member.strip()]
    
    def _get_current_server_settings(self) -> Dict[str, Any]:
        """
        Get current active server settings.
        
        Returns:
            Dictionary containing current server settings.
            
        Raises:
            requests.RequestException: If the request fails.
            ValueError: If settings cannot be retrieved.
        """
        response = self.make_request("/gameservers", method="GET")
        current_settings = response.get('data', {}).get('gameserver', {}).get('settings', {})
        
        if not current_settings:
            raise ValueError("Failed to retrieve current active server settings")
        
        return current_settings
    
    def _get_current_list_members(self, list_type: str, settings: Dict[str, Any]) -> set:
        """
        Extract current list members from server settings.
        
        Args:
            list_type: Type of list to extract.
            settings: Server settings dictionary.
            
        Returns:
            Set of current list members (cleaned and filtered).
        """
        current_list = settings.get("general", {}).get(list_type, "")
        # Handle both \r\n and \r line endings for backward compatibility
        if LINE_ENDING_CRLF in current_list:
            current_members = set(current_list.split(LINE_ENDING_CRLF))
        else:
            current_members = set(current_list.split(LINE_ENDING_CR)) if current_list else set()
        
        # Remove empty strings from current members
        return {member.strip() for member in current_members if member.strip()}
    
    def _apply_list_changes(self, current_members: set, identifiers: List[str], action: str, list_type: str) -> set:
        """
        Apply add/remove changes to a list and log the operations.
        
        Args:
            current_members: Current set of list members.
            identifiers: List of identifiers to add or remove.
            action: Action to perform ('add' or 'remove').
            list_type: Type of list for logging.
            
        Returns:
            Updated set of list members.
        """
        identifiers_set = set(identifiers)
        
        if action == "add":
            updated_members = current_members.union(identifiers_set)
            added_members = identifiers_set - current_members
            logger.info(f"Adding {len(added_members)} new members to {list_type}: {list(added_members)}")
        else:  # remove
            updated_members = current_members.difference(identifiers_set)
            removed_members = current_members.intersection(identifiers_set)
            logger.info(f"Removing {len(removed_members)} members from {list_type}: {list(removed_members)}")
        
        return updated_members
    
    def _update_list_setting(self, list_type: str, updated_members: set) -> Dict[str, Any]:
        """
        Update the server setting with the new list members.
        
        Args:
            list_type: Type of list to update.
            updated_members: Set of updated list members.
            
        Returns:
            API response dictionary.
            
        Raises:
            requests.RequestException: If the request fails.
        """
        # Format updated list with carriage return + line feed delimiter
        updated_list_value = LINE_ENDING_CRLF.join(sorted(updated_members)) if updated_members else ""
        
        # Construct the proper direct settings update payload
        settings_data = {
            "category": "general",
            "key": list_type,
            "value": updated_list_value
        }
        
        # Use the direct settings endpoint for immediate updates
        response = self.make_request("/gameservers/settings", method="POST", data=settings_data)
        logger.info(f"Successfully updated {list_type} list via direct settings endpoint")
        
        return response
    
    def _manage_list(self, list_type: str, action: str, identifiers: List[str]) -> Dict[str, Any]:
        """
        Manage a player list using the correct direct settings endpoint.
        
        This implementation follows the correct Nitrado API pattern:
        - Uses /gameservers/settings endpoint for immediate updates
        - Formats data as category/key/value for direct settings modification
        - Updates active server configuration immediately
        
        Args:
            list_type: Type of list ('whitelist', 'bans', 'priority').
            action: Action to perform ('add' or 'remove').
            identifiers: List of player identifiers to add or remove.
            
        Returns:
            API response with updated list information.
            
        Raises:
            ValueError: If list_type or action is invalid.
            requests.RequestException: If the request fails.
        """
        # Validate input parameters
        if list_type not in VALID_LIST_TYPES:
            raise ValueError(f"Invalid list type: {list_type}. Use {', '.join(VALID_LIST_TYPES)}.")
        
        if action not in ['add', 'remove']:
            raise ValueError(f"Invalid action: {action}. Use 'add' or 'remove'.")
        
        try:
            # Get current server settings
            current_settings = self._get_current_server_settings()
            
            # Extract current list members
            current_members = self._get_current_list_members(list_type, current_settings)
            
            # Apply the requested changes
            updated_members = self._apply_list_changes(current_members, identifiers, action, list_type)
            
            # Update the server setting
            response = self._update_list_setting(list_type, updated_members)
            
            # Add additional info to response for backwards compatibility
            response['updated_list'] = list(updated_members)
            response['action'] = action
            response['identifiers'] = identifiers
            response['list_type'] = list_type
            
            return response
            
        except (ValueError, requests.RequestException) as e:
            logger.error(f"Failed to update {list_type} list via direct settings: {e}")
            raise

    # Player Management - Simplified Implementation
    
    def _format_list_response(self, members: List[str], list_type: str) -> List[Dict[str, Any]]:
        """
        Format player list as expected API response format.
        
        Args:
            members: List of player identifiers.
            list_type: Type of list for logging.
            
        Returns:
            List of dictionaries with player information.
        """
        formatted_list = [{'name': member, 'id': member, 'id_type': 'identifier'} for member in members]
        logger.info(f"Retrieved {list_type} with {len(formatted_list)} entries")
        return formatted_list
    
    # Generic List Management Methods
    def get_list(self, list_type: str) -> List[Dict[str, Any]]:
        """
        Retrieve any player list for the game server.
        
        Args:
            list_type: Type of list ('bans', 'whitelist', 'priority').
            
        Returns:
            List of players formatted as dictionaries.
        """
        if list_type not in VALID_LIST_TYPES:
            raise ValueError(f"Invalid list type: {list_type}")
            
        try:
            members = self._get_list_members(list_type)
            return self._format_list_response(members, list_type)
        except requests.RequestException as e:
            logger.error(f"Failed to retrieve {list_type}: {e}")
            raise

    def add_to_list(self, list_type: str, identifiers: List[str]) -> Dict[str, Any]:
        """
        Add players to any list.
        
        Args:
            list_type: Type of list ('bans', 'whitelist', 'priority').
            identifiers: List of player identifiers to add.
            
        Returns:
            API response dictionary.
        """
        try:
            response = self._manage_list(list_type, 'add', identifiers)
            logger.info(f"Successfully added {len(identifiers)} players to {list_type}")
            return response
        except (ValueError, requests.RequestException) as e:
            logger.error(f"Failed to add players to {list_type}: {e}")
            raise

    def remove_from_list(self, list_type: str, identifiers: List[str]) -> Dict[str, Any]:
        """
        Remove players from any list.
        
        Args:
            list_type: Type of list ('bans', 'whitelist', 'priority').
            identifiers: List of player identifiers to remove.
            
        Returns:
            API response dictionary.
        """
        try:
            response = self._manage_list(list_type, 'remove', identifiers)
            logger.info(f"Successfully removed {len(identifiers)} players from {list_type}")
            return response
        except (ValueError, requests.RequestException) as e:
            logger.error(f"Failed to remove players from {list_type}: {e}")
            raise

    # Convenience Methods for Backward Compatibility
    def get_banlist(self) -> List[Dict[str, Any]]:
        """Retrieve the current ban list."""
        return self.get_list(LIST_TYPE_BANS)

    def add_to_banlist(self, identifiers: List[str]) -> Dict[str, Any]:
        """Add players to the ban list."""
        return self.add_to_list(LIST_TYPE_BANS, identifiers)

    def remove_from_banlist(self, identifiers: List[str]) -> Dict[str, Any]:
        """Remove players from the ban list."""
        return self.remove_from_list(LIST_TYPE_BANS, identifiers)

    def get_whitelist(self) -> List[Dict[str, Any]]:
        """Retrieve the current whitelist."""
        return self.get_list(LIST_TYPE_WHITELIST)

    def add_to_whitelist(self, identifiers: List[str]) -> Dict[str, Any]:
        """Add players to the whitelist."""
        return self.add_to_list(LIST_TYPE_WHITELIST, identifiers)

    def remove_from_whitelist(self, identifiers: List[str]) -> Dict[str, Any]:
        """Remove players from the whitelist."""
        return self.remove_from_list(LIST_TYPE_WHITELIST, identifiers)

    def get_prioritylist(self) -> List[Dict[str, Any]]:
        """Retrieve the current priority/admin list."""
        return self.get_list(LIST_TYPE_PRIORITY)

    def add_to_prioritylist(self, identifiers: List[str]) -> Dict[str, Any]:
        """Add players to the priority/admin list."""
        return self.add_to_list(LIST_TYPE_PRIORITY, identifiers)
    
    def remove_from_prioritylist(self, identifiers: List[str]) -> Dict[str, Any]:
        """Remove players from the priority/admin list."""
        return self.remove_from_list(LIST_TYPE_PRIORITY, identifiers)
    
    def run(self) -> Dict[str, Any]:
        """
        Minimal implementation of the abstract run method.
        
        This method is implemented to satisfy the DayZTool abstract class requirement but
        performs no operations in this generic API wrapper.
        
        Returns:
            Empty dictionary to indicate successful completion with no data
        """
        logger.warning("The run method is not implemented in the generic API client")
        return {}
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
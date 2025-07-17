#!/usr/bin/env python3
"""
DayZ Admin Tools - Player List Manager

Manages player lists (banlist, whitelist, and future priority list) via Nitrado API.
This tool provides comprehensive functionality for managing player access control lists.
"""

import argparse
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

from ..base import DayZTool, FileBasedTool
from ..nitrado.api_client import NitradoAPIClient

logger = logging.getLogger(__name__)


class PlayerListManagerTool(FileBasedTool):
    """
    Manages player lists via Nitrado API.
    
    This class provides functionality to manage banlist, whitelist, and future
    priority lists through the Nitrado API.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the PlayerListManagerTool with configuration.
        
        Args:
            config: Configuration dictionary from Config class
        """
        super().__init__(config)
        self.initialize_directories()
        
        # Initialize the Nitrado API client
        self.api_client = NitradoAPIClient(config)
        
        # Supported list types
        self.supported_lists = ['banlist', 'whitelist', 'priority']  # Using 'priority' instead of 'adminlist' to match Nitrado API
        
        logger.info("PlayerListManagerTool initialized")

    def get_list(self, list_type: str) -> List[Dict[str, Any]]:
        """
        Retrieve a player list from the server.
        
        Args:
            list_type: Type of list to retrieve ('banlist', 'whitelist', 'adminlist')
            
        Returns:
            List of players with their information
            
        Raises:
            ValueError: If list_type is not supported
        """
        if list_type not in self.supported_lists:
            raise ValueError(f"Unsupported list type: {list_type}. Supported types: {self.supported_lists}")
        
        logger.info(f"Retrieving {list_type}")
        
        if list_type == 'banlist':
            return self.api_client.get_banlist()
        elif list_type == 'whitelist':
            return self.api_client.get_whitelist()
        elif list_type == 'priority':
            return self.api_client.get_adminlist()
        
        return []

    def add_to_list(self, list_type: str, identifiers: List[str]) -> Dict[str, Any]:
        """
        Add players to a list.
        
        Args:
            list_type: Type of list ('banlist', 'whitelist', 'adminlist')
            identifiers: List of player identifiers to add
            
        Returns:
            API response dictionary
            
        Raises:
            ValueError: If list_type is not supported
        """
        if list_type not in self.supported_lists:
            raise ValueError(f"Unsupported list type: {list_type}. Supported types: {self.supported_lists}")
        
        logger.info(f"Adding {len(identifiers)} players to {list_type}: {identifiers}")
        
        if list_type == 'banlist':
            return self.api_client.add_to_banlist(identifiers)
        elif list_type == 'whitelist':
            return self.api_client.add_to_whitelist(identifiers)
        elif list_type == 'priority':
            return self.api_client.add_to_adminlist(identifiers)
        
        return {}

    def remove_from_list(self, list_type: str, identifiers: List[str]) -> Dict[str, Any]:
        """
        Remove players from a list.
        
        Args:
            list_type: Type of list ('banlist', 'whitelist', 'adminlist')
            identifiers: List of player identifiers to remove
            
        Returns:
            API response dictionary
            
        Raises:
            ValueError: If list_type is not supported
        """
        if list_type not in self.supported_lists:
            raise ValueError(f"Unsupported list type: {list_type}. Supported types: {self.supported_lists}")
        
        logger.info(f"Removing {len(identifiers)} players from {list_type}: {identifiers}")
        
        if list_type == 'banlist':
            return self.api_client.remove_from_banlist(identifiers)
        elif list_type == 'whitelist':
            return self.api_client.remove_from_whitelist(identifiers)
        elif list_type == 'priority':
            return self.api_client.remove_from_adminlist(identifiers)
        
        return {}

    def export_list_to_csv(self, list_type: str, output_file: Optional[str] = None) -> str:
        """
        Export a player list to CSV file.
        
        Args:
            list_type: Type of list to export
            output_file: Optional output file path, auto-generated if not provided
            
        Returns:
            Path to the exported CSV file
        """
        players = self.get_list(list_type)
        
        if not output_file:
            output_file = self.generate_timestamped_filename(list_type, "csv")
        
        # Use the base class write_csv method
        return self.write_csv(players, output_file)

    def import_list_from_csv(self, list_type: str, csv_file: str, 
                           identifier_column: str = 'id', add_mode: bool = True) -> Dict[str, Any]:
        """
        Import player identifiers from CSV file to a list.
        
        Args:
            list_type: Type of list to import to
            csv_file: Path to the CSV file
            identifier_column: Name of the column containing player identifiers
            add_mode: If True, add players; if False, remove players
            
        Returns:
            API response dictionary
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            KeyError: If identifier column doesn't exist
        """
        # Use the base class read_csv method
        data_rows = self.read_csv(csv_file, required_columns=[identifier_column])
        
        # Extract identifiers from the specified column
        identifiers = []
        for row in data_rows:
            identifier = row[identifier_column].strip()
            if identifier:  # Skip empty identifiers
                identifiers.append(identifier)
        
        if not identifiers:
            logger.warning(f"No valid identifiers found in {csv_file}")
            return {'status': 'warning', 'message': 'No valid identifiers found'}
        
        logger.info(f"Found {len(identifiers)} identifiers in CSV file")
        
        if add_mode:
            return self.add_to_list(list_type, identifiers)
        else:
            return self.remove_from_list(list_type, identifiers)

    def run(self, list_type: str, action: str, identifiers: Optional[List[str]] = None, 
            csv_file: Optional[str] = None, output_file: Optional[str] = None,
            identifier_column: str = 'id') -> Dict[str, Any]:
        """
        Main execution method for player list management.
        
        Args:
            list_type: Type of list to manage ('banlist', 'whitelist', 'adminlist')
            action: Action to perform ('list', 'add', 'remove', 'export', 'import')
            identifiers: List of player identifiers for add/remove actions
            csv_file: CSV file path for import/export actions
            output_file: Output file path for export action
            identifier_column: Column name for identifiers in CSV
            
        Returns:
            Dictionary containing execution results
        """
        try:
            if action == 'list':
                players = self.get_list(list_type)
                logger.info(f"Found {len(players)} players in {list_type}")
                
                # Print to console
                if players:
                    print(f"\n{list_type.upper()} ({len(players)} players):")
                    print("-" * 50)
                    for player in players:
                        print(f"Name: {player.get('name', 'N/A')}")
                        print(f"ID: {player.get('id', 'N/A')}")
                        print(f"ID Type: {player.get('id_type', 'N/A')}")
                        print("-" * 30)
                else:
                    print(f"\n{list_type.upper()} is empty.")
                
                return {'status': 'success', 'data': players}
            
            elif action == 'add':
                if not identifiers:
                    raise ValueError("Identifiers are required for add action")
                result = self.add_to_list(list_type, identifiers)
                if "error" in result:
                    logger.error(result["error"])
                    return result
                print(f"Successfully added {len(identifiers)} players to {list_type}")
                return result
            
            elif action == 'remove':
                if not identifiers:
                    raise ValueError("Identifiers are required for remove action")
                result = self.remove_from_list(list_type, identifiers)
                if "error" in result:
                    logger.error(result["error"])
                    return result
                print(f"Successfully removed {len(identifiers)} players from {list_type}")
                return result
            
            elif action == 'export':
                output_path = self.export_list_to_csv(list_type, output_file)
                print(f"Exported {list_type} to: {output_path}")
                return {'status': 'success', 'output_file': output_path}
            
            elif action == 'import':
                if not csv_file:
                    raise ValueError("CSV file is required for import action")
                result = self.import_list_from_csv(list_type, csv_file, identifier_column)
                if "error" in result:
                    logger.error(result["error"])
                    return result
                print(f"Imported players from {csv_file} to {list_type}")
                return result
            
            else:
                raise ValueError(f"Unknown action: {action}")
        
        except Exception as e:
            logger.error(f"Error executing {action} on {list_type}: {e}")
            return {'status': 'error', 'error': str(e)}


def main():
    """
    Main entry point for the player list manager CLI.
    """
    parser = argparse.ArgumentParser(
        description="Manage DayZ server player lists (banlist, whitelist, priority) via Nitrado API"
    )
    
    # Add standard arguments
    DayZTool.add_standard_arguments(parser)
    
    # Tool-specific arguments
    parser.add_argument(
        'list_type',
        choices=['banlist', 'whitelist', 'priority'],
        help='Type of player list to manage'
    )
    
    parser.add_argument(
        'action',
        choices=['list', 'add', 'remove', 'export', 'import'],
        help='Action to perform on the player list'
    )
    
    parser.add_argument(
        '--identifiers',
        nargs='+',
        help='Player identifiers (usernames, UUIDs, Steam IDs) for add/remove actions'
    )
    
    parser.add_argument(
        '--csv-file',
        help='CSV file path for import/export actions'
    )
    
    parser.add_argument(
        '--output-file',
        help='Output file path for export action (auto-generated if not specified)'
    )
    
    parser.add_argument(
        '--identifier-column',
        default='id',
        help='Column name for identifiers in CSV file (default: id)'
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = DayZTool.load_config(args.profile)
        
        # Initialize and run the tool
        manager = PlayerListManagerTool(config)
        result = manager.run(
            list_type=args.list_type,
            action=args.action,
            identifiers=args.identifiers,
            csv_file=args.csv_file,
            output_file=args.output_file,
            identifier_column=args.identifier_column
        )
        
        if result.get('status') == 'error':
            logger.error(f"Tool execution failed: {result.get('error')}")
            return 1
        
        logger.info("Tool execution completed successfully")
        return 0
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())

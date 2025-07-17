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

    def import_list_from_file(self, list_type: str, input_file: str, add_mode: bool = True) -> Dict[str, Any]:
        """
        Import player identifiers from a text file to a list.
        
        Args:
            list_type: Type of list to import to
            input_file: Path to the text file (one player ID per line)
            add_mode: If True, add players; if False, remove players
            
        Returns:
            API response dictionary
            
        Raises:
            FileNotFoundError: If input file doesn't exist
        """
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        # Extract identifiers from each line
        identifiers = []
        for line_num, line in enumerate(lines, 1):
            identifier = line.strip()
            if identifier and not identifier.startswith('#'):  # Skip empty lines and comments
                identifiers.append(identifier)
                logger.debug(f"Line {line_num}: Added identifier '{identifier}'")
            elif identifier.startswith('#'):
                logger.debug(f"Line {line_num}: Skipped comment line")
        
        if not identifiers:
            logger.warning(f"No valid identifiers found in {input_file}")
            return {'status': 'warning', 'message': 'No valid identifiers found'}
        
        logger.info(f"Found {len(identifiers)} identifiers in file {input_file}")
        
        if add_mode:
            return self.add_to_list(list_type, identifiers)
        else:
            return self.remove_from_list(list_type, identifiers)

    def run(self, list_type: str, action: str, identifiers: Optional[List[str]] = None, 
            input_file: Optional[str] = None, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Main execution method for player list management.
        
        Args:
            list_type: Type of list to manage ('banlist', 'whitelist', 'priority')
            action: Action to perform ('list', 'add', 'remove', 'export', 'import')
            identifiers: List of player identifiers for add/remove actions
            input_file: Text file path for import actions (one ID per line)
            output_file: Output file path for export action
            
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
                # Check if user provided input_file instead of identifiers
                if input_file and not identifiers:
                    logger.info("Input file provided for 'add' action, treating as 'import' operation")
                    if not input_file:
                        raise ValueError("Input file is required when no identifiers provided")
                    result = self.import_list_from_file(list_type, input_file)
                    if "error" in result:
                        logger.error(result["error"])
                        return result
                    print(f"Imported and added players from {input_file} to {list_type}")
                    return result
                elif not identifiers:
                    raise ValueError("Identifiers are required for add action (use --identifiers player1 player2... or --input-file filename.txt)")
                
                result = self.add_to_list(list_type, identifiers)
                if "error" in result:
                    logger.error(result["error"])
                    return result
                print(f"Successfully added {len(identifiers)} players to {list_type}")
                return result
            
            elif action == 'remove':
                # Check if user provided input_file instead of identifiers
                if input_file and not identifiers:
                    logger.info("Input file provided for 'remove' action, treating as file-based removal")
                    result = self.import_list_from_file(list_type, input_file, add_mode=False)
                    if "error" in result:
                        logger.error(result["error"])
                        return result
                    print(f"Imported and removed players from {input_file} from {list_type}")
                    return result
                elif not identifiers:
                    raise ValueError("Identifiers are required for remove action (use --identifiers player1 player2... or --input-file filename.txt)")
                
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
                if not input_file:
                    raise ValueError("Input file is required for import action")
                result = self.import_list_from_file(list_type, input_file)
                if "error" in result:
                    logger.error(result["error"])
                    return result
                print(f"Imported players from {input_file} to {list_type}")
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
        '--input-file',
        help='Text file path for import actions OR for add/remove actions (one player ID per line, lines starting with # are ignored as comments)'
    )
    
    parser.add_argument(
        '--output-file',
        help='Output file path for export action (auto-generated if not specified)'
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
            input_file=args.input_file,
            output_file=args.output_file
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

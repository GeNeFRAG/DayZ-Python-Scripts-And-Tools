#!/usr/bin/env python3
"""
DayZ Admin Tools - Player List Manager

Manages player lists (banlist, whitelist, and priority list) via Nitrado API and 
analyzes banned player connection attempts from RPT log files.

This tool provides comprehensive functionality for:
1. Managing player access control lists (banlist, whitelist, priority)
2. Analyzing RPT log files to detect banned players attempting to connect
3. Exporting banned connection attempts to CSV for further analysis

Features:
- Add/remove players from server lists
- Import/export player lists from/to files
- Monitor banned player connection attempts in real-time
- Generate detailed reports of security violations
"""

import argparse
import logging
import re
import glob
import os
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

from ..base import DayZTool, FileBasedTool
from ..nitrado.api_client import NitradoAPIClient

logger = logging.getLogger(__name__)


class PlayerListManagerTool(FileBasedTool):
    """
    Manages player lists via Nitrado API and analyzes banned connection attempts.
    
    This class provides functionality to:
    1. Manage banlist, whitelist, and priority lists through the Nitrado API
    2. Parse RPT log files to detect banned players trying to connect
    3. Export banned connection attempts to CSV files for analysis
    
    Banned Connection Detection:
    - Searches for log entries matching the pattern: 
      "Player NAME (ID) kicked from server: 7 (You were banned.)"
    - Extracts player names, IDs, timestamps, and source log files
    - Supports wildcard patterns for processing multiple RPT files
    - Handles multiple date formats and log file structures
    
    Usage Examples:
        # Check for banned connection attempts
        manager = PlayerListManagerTool(config)
        attempts = manager.check_banned_connection_attempts("logs/*.RPT")
        
        # Export to CSV
        csv_file = manager.export_banned_attempts_to_csv("logs/*.RPT")
        
        # Manage player lists
        manager.add_to_list('banlist', ['PlayerName123'])
        players = manager.get_list('banlist')
    """
    
    # Precompiled regex patterns for better performance
    # Pattern to match banned player kick messages
    # Example: "14:09:13.649 Player Bogumilwolf (1596804848) kicked from server: 7 (You were banned.)"
    BANNED_PATTERN = re.compile(
        r'(\d{1,2}:\d{2}:\d{2}\.\d{3})\s+Player\s+(\S+)\s+\((\d+)\)\s+kicked from server:\s*7\s*\(You were banned\.\)',
        re.IGNORECASE
    )
    # Pattern to extract date from RPT file header
    # Example: "Current time:  2025/07/25 12:05:34"
    DATE_PATTERN = re.compile(r'Current time:\s+(\d{4}/\d{2}/\d{2})')

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
            return self.api_client.add_to_prioritylist(identifiers)
        
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
            return self.api_client.remove_from_prioritylist(identifiers)
        
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

    def check_banned_connection_attempts(self, rpt_file_pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Check RPT log files for banned players attempting to connect to the server.
        
        Args:
            rpt_file_pattern: File pattern for RPT log files (e.g., '/path/to/*.RPT')
                            If not provided, uses *.RPT in the configured log directory
        
        Returns:
            List of dictionaries containing banned connection attempt information
        """
        # Set default pattern if not provided
        if not rpt_file_pattern:
            # Use configured log directory from the base class
            rpt_file_pattern = os.path.join(self.log_dir, "*.RPT")
        
        # Resolve the path to ensure it's absolute
        rpt_pattern_resolved = self.resolve_path(rpt_file_pattern)
        rpt_files = glob.glob(rpt_pattern_resolved)
        
        if not rpt_files:
            logger.warning(f"No RPT files found matching pattern: {rpt_file_pattern}")
            return []
        
        logger.info(f"Processing {len(rpt_files)} RPT files for banned connection attempts")
        
        banned_attempts = []
        
        for rpt_file_path in rpt_files:
            current_date = None
            logger.debug(f"Processing RPT file: {rpt_file_path}")
            
            try:
                with open(rpt_file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    for line_num, line in enumerate(file, 1):
                        # Extract the date from the RPT file header
                        if "Current time:" in line:
                            match_date = self.DATE_PATTERN.search(line)
                            if match_date:
                                current_date = datetime.strptime(match_date.group(1), '%Y/%m/%d').date()
                                logger.debug(f"RPT log date: {current_date}")
                        
                        # Look for banned player connection attempts
                        match = self.BANNED_PATTERN.search(line)
                        if match and current_date:
                            time_part = match.group(1).split('.')[0]  # Strip milliseconds for consistency
                            try:
                                timestamp = datetime.combine(current_date, datetime.strptime(time_part, '%H:%M:%S').time())
                                player_name = match.group(2)
                                player_id = match.group(3)
                                
                                banned_attempt = {
                                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                                    'player_name': player_name,
                                    'player_id': player_id,
                                    'log_file': os.path.basename(rpt_file_path),
                                    'line_number': line_num,
                                    'raw_line': line.strip()
                                }
                                
                                banned_attempts.append(banned_attempt)
                                logger.debug(f"Found banned connection attempt: {player_name} ({player_id}) at {timestamp}")
                                
                            except ValueError as e:
                                logger.warning(f"Error parsing timestamp in {rpt_file_path}:{line_num}: {e}")
                                continue
                        
            except IOError as e:
                logger.error(f"Error reading RPT file {rpt_file_path}: {e}")
                continue
        
        logger.info(f"Found {len(banned_attempts)} banned connection attempts")
        return banned_attempts
    
    def export_banned_attempts_to_csv(self, rpt_file_pattern: Optional[str] = None, 
                                     output_file: Optional[str] = None) -> str:
        """
        Export banned connection attempts to CSV file.
        
        Args:
            rpt_file_pattern: File pattern for RPT log files
            output_file: Optional output file path, auto-generated if not provided
            
        Returns:
            Path to the exported CSV file
        """
        banned_attempts = self.check_banned_connection_attempts(rpt_file_pattern)
        
        # Sort by timestamp for chronological order
        banned_attempts.sort(key=lambda x: x['timestamp'])
        
        if not output_file:
            output_file = self.generate_timestamped_filename("banned_connection_attempts", "csv")
        
        # Use the base class write_csv method
        return self.write_csv(banned_attempts, output_file)

    def run(self, list_type: str = None, action: str = None, identifiers: Optional[List[str]] = None, 
            input_file: Optional[str] = None, output_file: Optional[str] = None,
            rpt_file_pattern: Optional[str] = None) -> Dict[str, Any]:
        """
        Main execution method for player list management.
        
        Args:
            list_type: Type of list to manage ('banlist', 'whitelist', 'priority')
            action: Action to perform ('list', 'add', 'remove', 'export', 'import', 'check-banned-attempts')
            identifiers: List of player identifiers for add/remove actions
            input_file: Text file path for import actions (one ID per line)
            output_file: Output file path for export action
            rpt_file_pattern: File pattern for RPT log files (for check-banned-attempts action)
            
        Returns:
            Dictionary containing execution results
        """
        try:
            # Handle banned connection attempts check action (doesn't require list_type)
            if action == 'check-banned-attempts':
                banned_attempts = self.check_banned_connection_attempts(rpt_file_pattern)
                
                if banned_attempts:
                    print(f"\nFound {len(banned_attempts)} banned connection attempts:")
                    print("-" * 80)
                    for attempt in banned_attempts:
                        print(f"Timestamp: {attempt['timestamp']}")
                        print(f"Player: {attempt['player_name']} (ID: {attempt['player_id']})")
                        print(f"Log File: {attempt['log_file']} (Line: {attempt['line_number']})")
                        print(f"Raw Line: {attempt['raw_line']}")
                        print("-" * 80)
                else:
                    print("\nNo banned connection attempts found in the analyzed RPT files.")
                
                return {'status': 'success', 'banned_attempts': banned_attempts}
            
            elif action == 'export-banned-attempts':
                output_path = self.export_banned_attempts_to_csv(rpt_file_pattern, output_file)
                banned_count = len(self.check_banned_connection_attempts(rpt_file_pattern))
                print(f"Exported {banned_count} banned connection attempts to: {output_path}")
                return {'status': 'success', 'output_file': output_path, 'banned_count': banned_count}
            
            # All other actions require list_type
            if not list_type:
                raise ValueError("list_type is required for this action")
            
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
        description="Manage DayZ server player lists (banlist, whitelist, priority) via Nitrado API and analyze banned connection attempts"
    )
    
    # Add standard arguments
    DayZTool.add_standard_arguments(parser)
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Player list management subparser
    list_parser = subparsers.add_parser('manage', help='Manage player lists (banlist, whitelist, priority)')
    list_parser.add_argument(
        'list_type',
        choices=['banlist', 'whitelist', 'priority'],
        help='Type of player list to manage'
    )
    list_parser.add_argument(
        'action',
        choices=['list', 'add', 'remove', 'export', 'import'],
        help='Action to perform on the player list'
    )
    list_parser.add_argument(
        '--identifiers',
        nargs='+',
        help='Player identifiers (usernames, UUIDs, Steam IDs) for add/remove actions'
    )
    list_parser.add_argument(
        '--input-file',
        help='Text file path for import actions OR for add/remove actions (one player ID per line, lines starting with # are ignored as comments)'
    )
    list_parser.add_argument(
        '--output-file',
        help='Output file path for export action (auto-generated if not specified)'
    )
    
    # Banned connection attempts subparser
    banned_parser = subparsers.add_parser('banned-attempts', help='Check for banned player connection attempts in RPT logs')
    banned_parser.add_argument(
        'action',
        choices=['check', 'export'],
        help='Action to perform: "check" to display results, "export" to save to CSV'
    )
    banned_parser.add_argument(
        '--rpt-pattern',
        help='File pattern for RPT log files (e.g., "/path/to/*.RPT"). If not provided, uses *.RPT in the configured log directory'
    )
    banned_parser.add_argument(
        '--output-file',
        help='Output file path for export action (auto-generated if not specified)'
    )
    
    args = parser.parse_args()
    
    # Show help if no command is provided
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        # Load configuration
        config = DayZTool.load_config(args.profile)
        
        # Initialize the tool
        manager = PlayerListManagerTool(config)
        
        # Handle different commands
        if args.command == 'manage':
            result = manager.run(
                list_type=args.list_type,
                action=args.action,
                identifiers=args.identifiers,
                input_file=args.input_file,
                output_file=args.output_file
            )
        elif args.command == 'banned-attempts':
            if args.action == 'check':
                result = manager.run(
                    action='check-banned-attempts',
                    rpt_file_pattern=args.rpt_pattern
                )
            elif args.action == 'export':
                result = manager.run(
                    action='export-banned-attempts',
                    rpt_file_pattern=args.rpt_pattern,
                    output_file=args.output_file
                )
            else:
                raise ValueError(f"Unknown banned-attempts action: {args.action}")
        else:
            raise ValueError(f"Unknown command: {args.command}")
        
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

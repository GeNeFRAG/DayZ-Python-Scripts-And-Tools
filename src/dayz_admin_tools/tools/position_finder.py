"""
Position finder tool for DayZ admin logs.

This module provides functionalities to search player positions
in DayZ admin log files, filter by coordinates or player names,
and save the results to CSV files.
"""

import re
import math
import glob
import os
import logging
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any

from dayz_admin_tools.base import DayZTool, FileBasedTool

logger = logging.getLogger(__name__)

class PositionFinder(FileBasedTool):
    """Tool for finding player positions in DayZ admin log files."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the position finder tool.
        
        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        self.initialize_directories()
        # Get default patterns from config but only use *.ADM pattern
        config_patterns = self.get_config('log_filtering.default_patterns', ["*.RPT", "*.ADM"])
        self.default_pattern = "*.ADM"  # Always use *.ADM pattern regardless of config
    
    def _extract_info(self, line: str, file_date: str) -> Tuple[Optional[str], Optional[str], Optional[tuple], Optional[str]]:
        """
        Extract time, player name, position coordinates, and action from a line of text
        
        Args:
            line: String containing player data
            file_date: Date extracted from filename
            
        Returns:
            Tuple of (time_str, player_name, (x, y, z) coordinates, action)
        """
        try:
            # Split the line by '|' to get the time
            parts = line.split('|', 1)
            time_str = parts[0].strip() if len(parts) > 0 else None

            # Extract player name
            name_match = re.search(r'"([^"]+)"', line)
            player_name = name_match.group(1) if name_match else None

            # Extract position
            pos_match = re.search(r'pos=<([-\d.,\s]+)>', line)
            if not pos_match:
                # Try CSV format
                parts = line.split(',')
                if len(parts) >= 9:  # Assuming CSV format with at least 9 columns
                    try:
                        x = float(parts[5])
                        y = float(parts[6])
                        z = float(parts[7])
                        time_str = parts[3]
                        player_name = parts[4]
                        action = parts[8]
                        return time_str, player_name, (x, y, z), action
                    except (ValueError, IndexError):
                        pass
                return time_str, player_name, None, None
            
            coords = pos_match.group(1).split(',')
            if len(coords) != 3:
                return time_str, player_name, None, None
                
            position = tuple(float(coord.strip()) for coord in coords)
            
            # Extract action (everything after the coordinates)
            action_match = re.search(r'>\s*(.*?)(?:\s*\(|$)', line)
            action = action_match.group(1).strip() if action_match else ""
            
            return time_str, player_name, position, action
        except Exception as e:
            logger.error(f"Error extracting info: {e}")
            return None, None, None, None

    def _extract_date_from_file(self, file_path: str) -> str:
        """
        Extract date from the top entry of the file
        
        Args:
            file_path: Path to the log file
            
        Returns:
            Date string in YYYY-MM-DD format or "Unknown date" if not found
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                for _ in range(3):
                    file.readline()  # Skip the first three lines
                fourth_line = file.readline().strip()
                date_match = re.search(r'AdminLog started on (\d{4}-\d{2}-\d{2})', fourth_line)
                if date_match:
                    return date_match.group(1)
        except Exception as e:
            logger.error(f"Error extracting date from file {file_path}: {e}")
        return "Unknown date"

    def _calculate_distance(self, x1: float, y1: float, x2: float, y2: float) -> float:
        """
        Calculate 2D distance between two points
        
        Args:
            x1: First point x-coordinate
            y1: First point y-coordinate
            x2: Second point x-coordinate
            y2: Second point y-coordinate
            
        Returns:
            Distance between the points
        """
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    def find_nearby_positions(self, file_pattern: Optional[str] = None, target_x: float = 0.0, target_y: float = 0.0, radius: float = 100.0) -> List[tuple]:
        """
        Find positions within specified radius of target coordinates in multiple files
        
        Args:
            file_pattern: File pattern to search (e.g. "*.ADM"). If None, uses default *.ADM pattern.
            target_x: Target X coordinate
            target_y: Target Y coordinate
            radius: Search radius in meters
            
        Returns:
            List of tuples containing position information
        """
        nearby_positions = []
        
        # Use provided pattern or default to *.ADM
        pattern_to_use = file_pattern if file_pattern else self.default_pattern
        logger.info(f"Using file pattern: {pattern_to_use}")
        
        # If pattern doesn't include a path, use the log_dir from config
        pattern = pattern_to_use
        if not os.path.dirname(pattern):
            pattern = os.path.join(self.resolve_path(self.log_dir), pattern)
            
        matching_files = glob.glob(pattern)
        
        if not matching_files:
            logger.warning(f"No files found matching pattern: {pattern}")
            return nearby_positions
                
        logger.info(f"Searching {len(matching_files)} files for positions within {radius}m of ({target_x}, {target_y})")
        
        for file_path in matching_files:
            try:
                file_date = self._extract_date_from_file(file_path)
                
                with open(file_path, 'r', encoding='utf-8') as file:
                    for line_num, line in enumerate(file, 1):
                        time_str, player_name, coords, action = self._extract_info(line, file_date)
                        
                        if coords:
                            x, y, z = coords
                            distance = self._calculate_distance(target_x, target_y, x, y)
                            
                            if distance <= radius:
                                nearby_positions.append((
                                    os.path.basename(file_path),
                                    line_num,
                                    file_date,
                                    time_str,
                                    player_name,
                                    coords,
                                    action,
                                    distance
                                ))
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                    
        return sorted(nearby_positions, key=lambda x: x[7])  # Sort by distance

    def find_positions_by_player(self, file_pattern: Optional[str] = None, player_name_filter: str = "") -> List[tuple]:
        """
        Find positions and actions for a specific player in multiple files
        
        Args:
            file_pattern: File pattern to search (e.g. "*.ADM"). If None, uses default *.ADM pattern.
            player_name_filter: Player name to filter by
        
        Returns:
            List of tuples containing file details and player actions
        """
        player_positions = []
        
        # Use provided pattern or default to *.ADM
        pattern_to_use = file_pattern if file_pattern else self.default_pattern
        logger.info(f"Using file pattern: {pattern_to_use}")
        
        # If pattern doesn't include a path, use the log_dir from config
        pattern = pattern_to_use
        if not os.path.dirname(pattern):
            pattern = os.path.join(self.resolve_path(self.log_dir), pattern)
            
        matching_files = glob.glob(pattern)
        
        if not matching_files:
            logger.warning(f"No files found matching pattern: {pattern}")
            return player_positions
            
        logger.info(f"Searching {len(matching_files)} files for player: {player_name_filter}")
        
        for file_path in matching_files:
            try:
                file_date = self._extract_date_from_file(file_path)
                
                with open(file_path, 'r', encoding='utf-8') as file:
                    for line_num, line in enumerate(file, 1):
                        time_str, player_name, coords, action = self._extract_info(line, file_date)
                        
                        if player_name and player_name_filter.lower() in player_name.lower():
                            player_positions.append((
                                os.path.basename(file_path),
                                line_num,
                                file_date,
                                time_str,
                                player_name,
                                coords,
                                action
                            ))
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                    
        return player_positions

    def _filter_by_date_range(self, results: List[tuple], start_date: Optional[str], end_date: Optional[str]) -> List[tuple]:
        """
        Filter results by date range
        
        Args:
            results: List of result tuples
            start_date: Start date in YYYY-MM-DD format (optional)
            end_date: End date in YYYY-MM-DD format (optional)
        
        Returns:
            Filtered list of result tuples
        """
        if not start_date and not end_date:
            return results
        
        filtered_results = []
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
        
        for result in results:
            file_date_str = result[2]
            if file_date_str == "Unknown date":
                continue
            file_date_obj = datetime.strptime(file_date_str, "%Y-%m-%d")
            
            if (not start_date_obj or file_date_obj >= start_date_obj) and (not end_date_obj or file_date_obj <= end_date_obj):
                filtered_results.append(result)
        
        return filtered_results

    def _sort_by_time(self, results: List[tuple]) -> List[tuple]:
        """
        Sort results by time
        
        Args:
            results: List of result tuples
        
        Returns:
            Sorted list of result tuples
        """
        return sorted(results, key=lambda x: (x[2], x[3]))  # Sort by date and time

    def _save_to_csv(self, results: List[tuple], output_file: str):
        """
        Save results to CSV file
        
        Args:
            results: List of result tuples
            output_file: Name of the CSV file to create
        """
        try:
            # Add generated timestamp to the CSV
            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Convert tuples to list of dictionaries for CSV export
            data = []
            
            # Add timestamp as the first row
            data.append({"Report Generated": current_timestamp})
            
            # Add an empty row for better readability
            data.append({})
            
            # Define headers
            headers = ['File', 'Line', 'Date', 'Time', 'Player', 'X', 'Y', 'Z', 'Action', 'Distance']
            
            # Process each result
            for filename, line_num, file_date, time_str, player_name, coords, action, distance in results:
                data.append({
                    'File': filename,
                    'Line': line_num,
                    'Date': file_date,
                    'Time': time_str,
                    'Player': player_name,
                    'X': f"{coords[0]:.1f}",
                    'Y': f"{coords[1]:.1f}",
                    'Z': f"{coords[2]:.1f}",
                    'Action': action if action else "",
                    'Distance': f"{distance:.2f}"
                })
            
            # Use write_csv from FileBasedTool
            self.write_csv(data, output_file, headers=['Report Generated'] + headers)
            
            logger.info(f"Results saved to: {output_file} (timestamp: {current_timestamp})")
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")

    def _save_player_positions_to_csv(self, results: List[tuple], output_file: str):
        """
        Save player positions to CSV file
        
        Args:
            results: List of result tuples
            output_file: Name of the CSV file to create
        """
        try:
            # Add generated timestamp to the CSV
            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Convert tuples to list of dictionaries for CSV export
            data = []
            
            # Add timestamp as the first row
            data.append({"Report Generated": current_timestamp})
            
            # Add an empty row for better readability
            data.append({})
            
            # Define headers
            headers = ['File', 'Line', 'Date', 'Time', 'Player', 'X', 'Y', 'Z', 'Action']
            
            # Process each result
            for filename, line_num, file_date, time_str, player_name, coords, action in results:
                data.append({
                    'File': filename,
                    'Line': line_num,
                    'Date': file_date,
                    'Time': time_str,
                    'Player': player_name,
                    'X': f"{coords[0]:.1f}" if coords else "",
                    'Y': f"{coords[1]:.1f}" if coords else "",
                    'Z': f"{coords[2]:.1f}" if coords else "",
                    'Action': action if action else ""
                })
            
            # Use write_csv from FileBasedTool
            self.write_csv(data, output_file, headers=['Report Generated'] + headers)
            
            logger.info(f"Results saved to: {output_file} (timestamp: {current_timestamp})")
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")

    def run(self, args) -> None:
        """
        Run the position finder tool.
        
        Args:
            args: Command-line arguments
        """
        # Ensure output directory exists
        os.makedirs(self.resolve_path(self.output_dir), exist_ok=True)

        # Add timestamp to output filename
        filename, extension = os.path.splitext(args.output)
        extension = extension.lstrip('.')  # Remove leading dot
        timestamped_filename = self.generate_timestamped_filename(filename, extension)
        
        # Build output file path
        output_file = os.path.join(self.resolve_path(self.output_dir), timestamped_filename)
        
        if args.player:
            if args.target_x is not None or args.target_y is not None:
                logger.warning("Target coordinates are ignored when searching by player name")
                
            results = self.find_positions_by_player(args.file_pattern, args.player)
            if not results:
                logger.info(f"No positions found for player: {args.player}.")
                return
                
            results = self._filter_by_date_range(results, args.start_date, args.end_date)
            results = self._sort_by_time(results)
            self._save_player_positions_to_csv(results, output_file)
            logger.info(f"Found {len(results)} positions for player: {args.player}.")
        else:
            if args.target_x is None or args.target_y is None:
                logger.error("Target coordinates (--target_x and --target_y) are required when not searching by player name.")
                return
                
            results = self.find_nearby_positions(args.file_pattern, args.target_x, args.target_y, args.radius)
            if not results:
                logger.info(f"No positions found within {args.radius}m radius of ({args.target_x}, {args.target_y}).")
                return
                
            results = self._filter_by_date_range(results, args.start_date, args.end_date)
            results = self._sort_by_time(results)
            self._save_to_csv(results, output_file)
            logger.info(f"Found {len(results)} positions within {args.radius}m radius.")

def main():
    """Command-line entry point for the position finder tool."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Find player positions and actions in DayZ admin log files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Find positions near coordinates using default *.ADM pattern
  dayz-position-finder --target_x 7500 --target_y 8500 --radius 100
  
  # Find positions near coordinates with specific file pattern
  dayz-position-finder --file_pattern "*.ADM" --target_x 7500 --target_y 8500 --radius 100
  
  # Find positions for a specific player
  dayz-position-finder --player "SurvivorName"
  
  # Filter by date range and use specific output file
  dayz-position-finder --player "SurvivorName" --start-date 2023-06-01 --end-date 2023-06-30 --output player_positions.csv
  
  # Use configuration profile
  dayz-position-finder --profile myserver --target_x 7500 --target_y 8500
''')
    
    parser.add_argument('--file_pattern', help='File pattern to search (e.g. "*.ADM"). If not specified, the default "*.ADM" pattern will be used.')
    parser.add_argument('--target_x', type=float, help='Target X coordinate for location-based search')
    parser.add_argument('--target_y', type=float, help='Target Y coordinate for location-based search')
    parser.add_argument('--radius', type=float, default=100.0, help='Search radius in meters (default: 100.0)')
    parser.add_argument('--output', default='positions.csv', help='Output CSV file name (default: positions.csv)')
    parser.add_argument('--player', help='Player name to filter by')
    parser.add_argument('--start-date', help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end-date', help='End date in YYYY-MM-DD format')
    
    # For backward compatibility
    parser.add_argument('file_pattern_pos', nargs='?', help='File pattern (positional argument, deprecated)')
    
    # Add standard arguments from DayZTool
    DayZTool.add_standard_arguments(parser)
    
    args = parser.parse_args()
    
    # Handle backward compatibility for positional argument
    if args.file_pattern_pos and not args.file_pattern:
        args.file_pattern = args.file_pattern_pos
        logger.warning("Using positional file pattern argument is deprecated. Please use --file_pattern instead.")
    
    # Load configuration
    config = PositionFinder.load_config(args.profile)
    
    # Initialize and run the tool
    finder = PositionFinder(config)
    finder.run(args)

if __name__ == "__main__":
    main()

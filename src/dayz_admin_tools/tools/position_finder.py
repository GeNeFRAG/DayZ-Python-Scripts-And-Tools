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
        self._player_regex = None  # Cache for compiled regex pattern
        # Precompiled regex to detect regex metacharacters
        self._regex_detector = re.compile(r'[.*+?^${}()|[\]\\]')
    
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
            Date string in D.M.YYYY format or "Unknown date" if not found
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                for _ in range(3):
                    file.readline()  # Skip the first three lines
                fourth_line = file.readline().strip()
                date_match = re.search(r'AdminLog started on (\d{4}-\d{2}-\d{2})', fourth_line)
                if date_match:
                    # Parse the date and reformat to D.M.YYYY
                    date_str = date_match.group(1)
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                        return date_obj.strftime("%d.%m.%Y")
                    except ValueError:
                        return date_str  # Fallback to original format if parsing fails
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

    def _get_matching_files(self, file_pattern: Optional[str] = None) -> List[str]:
        """
        Get list of files matching the specified pattern
        
        Args:
            file_pattern: File pattern to search (e.g. "*.ADM"). If None, uses default *.ADM pattern.
            
        Returns:
            List of file paths matching the pattern
        """
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
            
        return matching_files

    def _process_files(self, file_pattern: Optional[str], line_processor_func, description: str) -> List[tuple]:
        """
        Process log files with a custom line processor function
        
        Args:
            file_pattern: File pattern to search
            line_processor_func: Function to process each line (returns tuple or None)
            description: Description for logging
            
        Returns:
            List of processed results
        """
        matching_files = self._get_matching_files(file_pattern)
        
        if not matching_files:
            return []
            
        logger.info(f"Searching {len(matching_files)} files for {description}")
        
        results = []
        for file_path in matching_files:
            try:
                file_date = self._extract_date_from_file(file_path)
                
                with open(file_path, 'r', encoding='utf-8') as file:
                    for line_num, line in enumerate(file, 1):
                        time_str, player_name, coords, action = self._extract_info(line, file_date)
                        
                        # Call the custom processor function
                        result = line_processor_func(
                            os.path.basename(file_path),
                            line_num,
                            file_date,
                            time_str,
                            player_name,
                            coords,
                            action
                        )
                        
                        if result is not None:
                            results.append(result)
                            
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                    
        return results

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
        def process_nearby_line(filename, line_num, file_date, time_str, player_name, coords, action):
            """Process line for nearby position search"""
            if coords:
                x, y, z = coords
                distance = self._calculate_distance(target_x, target_y, x, y)
                
                if distance <= radius:
                    return (filename, line_num, file_date, time_str, player_name, coords, action, distance)
            return None
        
        results = self._process_files(
            file_pattern,
            process_nearby_line,
            f"positions within {radius}m of ({target_x}, {target_y})"
        )
        
        return sorted(results, key=lambda x: x[7])  # Sort by distance

    def _is_regex_pattern(self, pattern: str) -> bool:
        """
        Detect if a string contains regex metacharacters
        
        Args:
            pattern: String to check for regex patterns
            
        Returns:
            True if pattern contains regex metacharacters, False otherwise
        """
        return bool(self._regex_detector.search(pattern))

    def find_positions_by_player(self, file_pattern: Optional[str] = None, player_name_filter: str = "", placement_filter: Optional[str] = None) -> List[tuple]:
        """
        Find positions and actions for a specific player in multiple files
        
        Args:
            file_pattern: File pattern to search (e.g. "*.ADM"). If None, uses default *.ADM pattern.
            player_name_filter: Player name to filter by (automatically detects regex patterns)
            placement_filter: Filter for placement actions (e.g., "placed", "Fireplace", "Wooden Crate")
        
        Returns:
            List of tuples containing file details and player actions
        """
        # Auto-detect if the filter contains regex patterns
        use_regex = self._is_regex_pattern(player_name_filter)
        
        # Precompile regex pattern if needed
        if use_regex:
            try:
                self._player_regex = re.compile(player_name_filter, re.IGNORECASE)
                logger.info(f"Auto-detected regex pattern for player search: {player_name_filter}")
            except re.error as e:
                logger.error(f"Invalid regex pattern '{player_name_filter}': {e}")
                return []
        else:
            self._player_regex = None
            logger.info(f"Using substring search for player: {player_name_filter}")

        # Handle placement filter
        placement_regex = None
        use_placement_regex = False
        if placement_filter:
            use_placement_regex = self._is_regex_pattern(placement_filter)
            if use_placement_regex:
                try:
                    placement_regex = re.compile(placement_filter, re.IGNORECASE)
                    logger.info(f"Auto-detected regex pattern for placement search: {placement_filter}")
                except re.error as e:
                    logger.error(f"Invalid regex pattern '{placement_filter}': {e}")
                    return []
            else:
                logger.info(f"Using substring search for placement: {placement_filter}")

        def process_player_line(filename, line_num, file_date, time_str, player_name, coords, action):
            """Process line for player search"""
            # Check player name filter
            player_match = True
            if player_name_filter and player_name:
                if use_regex and self._player_regex:
                    player_match = bool(self._player_regex.search(player_name))
                elif not use_regex:
                    player_match = player_name_filter.lower() in player_name.lower()
                else:
                    player_match = False
            elif player_name_filter:
                player_match = False
            
            # Check placement filter
            placement_match = True
            if placement_filter and action:
                if use_placement_regex and placement_regex:
                    placement_match = bool(placement_regex.search(action))
                elif not use_placement_regex:
                    placement_match = placement_filter.lower() in action.lower()
                else:
                    placement_match = False
            elif placement_filter:
                placement_match = False
            
            if player_match and placement_match:
                return (filename, line_num, file_date, time_str, player_name, coords, action)
            return None
        
        search_description = []
        if player_name_filter:
            search_description.append(f"player: {player_name_filter} {'(auto-detected regex)' if use_regex else '(substring)'}")
        if placement_filter:
            search_description.append(f"placement: {placement_filter} {'(auto-detected regex)' if use_placement_regex else '(substring)'}")
        
        description = " and ".join(search_description) if search_description else "all actions"
        
        return self._process_files(
            file_pattern,
            process_player_line,
            description
        )

    def find_placement_actions(self, file_pattern: Optional[str] = None, player_name_filter: str = "", placement_filter: str = "placed") -> List[tuple]:
        """
        Find placement actions in multiple files
        
        Args:
            file_pattern: File pattern to search (e.g. "*.ADM"). If None, uses default *.ADM pattern.
            player_name_filter: Player name to filter by (automatically detects regex patterns)
            placement_filter: Filter for placement actions (default: "placed")
        
        Returns:
            List of tuples containing file details and placement actions
        """
        return self.find_positions_by_player(file_pattern, player_name_filter, placement_filter)

    def find_combined_filters(self, file_pattern: Optional[str] = None, 
                             target_x: Optional[float] = None, target_y: Optional[float] = None, radius: float = 100.0,
                             player_name_filter: str = "", placement_filter: Optional[str] = None,
                             start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[tuple]:
        """
        Find positions using combined coordinate, player, placement, and date filters
        
        Args:
            file_pattern: File pattern to search (e.g. "*.ADM"). If None, uses default *.ADM pattern.
            target_x: Target X coordinate (optional)
            target_y: Target Y coordinate (optional)
            radius: Search radius in meters (default: 100.0)
            player_name_filter: Player name to filter by (automatically detects regex patterns)
            placement_filter: Filter for placement actions (e.g., "placed", "Fireplace", "Wooden Crate")
            start_date: Start date filter in D.M.YYYY format (optional)
            end_date: End date filter in D.M.YYYY format (optional)
        
        Returns:
            List of tuples containing position information with distance (if coordinates provided)
        """
        # Auto-detect if the player filter contains regex patterns
        use_regex = self._is_regex_pattern(player_name_filter) if player_name_filter else False
        
        # Precompile regex pattern if needed
        if use_regex:
            try:
                self._player_regex = re.compile(player_name_filter, re.IGNORECASE)
                logger.info(f"Auto-detected regex pattern for player search: {player_name_filter}")
            except re.error as e:
                logger.error(f"Invalid regex pattern '{player_name_filter}': {e}")
                return []
        else:
            self._player_regex = None
            if player_name_filter:
                logger.info(f"Using substring search for player: {player_name_filter}")

        # Handle placement filter
        placement_regex = None
        use_placement_regex = False
        if placement_filter:
            use_placement_regex = self._is_regex_pattern(placement_filter)
            if use_placement_regex:
                try:
                    placement_regex = re.compile(placement_filter, re.IGNORECASE)
                    logger.info(f"Auto-detected regex pattern for placement search: {placement_filter}")
                except re.error as e:
                    logger.error(f"Invalid regex pattern '{placement_filter}': {e}")
                    return []
            else:
                logger.info(f"Using substring search for placement: {placement_filter}")

        # Determine if we're doing coordinate filtering
        use_coordinates = target_x is not None and target_y is not None

        def process_combined_line(filename, line_num, file_date, time_str, player_name, coords, action):
            """Process line for combined search"""
            # Check player name filter
            player_match = True
            if player_name_filter and player_name:
                if use_regex and self._player_regex:
                    player_match = bool(self._player_regex.search(player_name))
                elif not use_regex:
                    player_match = player_name_filter.lower() in player_name.lower()
                else:
                    player_match = False
            elif player_name_filter:
                player_match = False
            
            # Check placement filter
            placement_match = True
            if placement_filter and action:
                if use_placement_regex and placement_regex:
                    placement_match = bool(placement_regex.search(action))
                elif not use_placement_regex:
                    placement_match = placement_filter.lower() in action.lower()
                else:
                    placement_match = False
            elif placement_filter:
                placement_match = False
            
            # Check coordinate filter
            coordinate_match = True
            distance = None
            if use_coordinates and coords:
                x, y, z = coords
                distance = self._calculate_distance(target_x, target_y, x, y)
                coordinate_match = distance <= radius
            elif use_coordinates:
                coordinate_match = False  # No coordinates available but coordinates required
            
            if player_match and placement_match and coordinate_match:
                if use_coordinates:
                    return (filename, line_num, file_date, time_str, player_name, coords, action, distance)
                else:
                    return (filename, line_num, file_date, time_str, player_name, coords, action)
            return None
        
        # Build search description
        search_description = []
        if player_name_filter:
            search_description.append(f"player: {player_name_filter} {'(auto-detected regex)' if use_regex else '(substring)'}")
        if placement_filter:
            search_description.append(f"placement: {placement_filter} {'(auto-detected regex)' if use_placement_regex else '(substring)'}")
        if use_coordinates:
            search_description.append(f"within {radius}m of ({target_x}, {target_y})")
        if start_date or end_date:
            date_parts = []
            if start_date:
                date_parts.append(f"from {start_date}")
            if end_date:
                date_parts.append(f"to {end_date}")
            search_description.append(" ".join(date_parts))
        
        description = " and ".join(search_description) if search_description else "all actions"
        
        results = self._process_files(
            file_pattern,
            process_combined_line,
            description
        )
        
        # Apply date filtering if specified
        if start_date or end_date:
            results = self._filter_by_date_range(results, start_date, end_date)
        
        # Sort results appropriately
        if use_coordinates:
            return sorted(results, key=lambda x: x[7])  # Sort by distance
        else:
            return results

    def _filter_by_date_range(self, results: List[tuple], start_date: Optional[str], end_date: Optional[str]) -> List[tuple]:
        """
        Filter results by date range
        
        Args:
            results: List of result tuples
            start_date: Start date in D.M.YYYY format (optional)
            end_date: End date in D.M.YYYY format (optional)
        
        Returns:
            Filtered list of result tuples
        """
        if not start_date and not end_date:
            return results
        
        filtered_results = []
        start_date_obj = datetime.strptime(start_date, "%d.%m.%Y") if start_date else None
        end_date_obj = datetime.strptime(end_date, "%d.%m.%Y") if end_date else None
        
        for result in results:
            file_date_str = result[2]
            if file_date_str == "Unknown date":
                continue
            
            try:
                # Parse the D.M.YYYY format
                file_date_obj = datetime.strptime(file_date_str, "%d.%m.%Y")
            except ValueError:
                continue
            
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
        Save results to CSV file (with distance column for coordinate-based searches)
        
        Args:
            results: List of result tuples (8 elements: filename, line_num, file_date, time_str, player_name, coords, action, distance)
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
            for result in results:
                if len(result) == 8:  # With distance
                    filename, line_num, file_date, time_str, player_name, coords, action, distance = result
                    distance_str = f"{distance:.2f}"
                elif len(result) == 7:  # Without distance
                    filename, line_num, file_date, time_str, player_name, coords, action = result
                    distance_str = "N/A"
                else:
                    logger.warning(f"Unexpected result tuple length: {len(result)}")
                    continue
                    
                data.append({
                    'File': filename,
                    'Line': line_num,
                    'Date': file_date,
                    'Time': time_str,
                    'Player': player_name,
                    'X': f"{coords[0]:.1f}" if coords else "",
                    'Y': f"{coords[1]:.1f}" if coords else "",
                    'Z': f"{coords[2]:.1f}" if coords else "",
                    'Action': action if action else "",
                    'Distance': distance_str
                })
            
            # Use write_csv from FileBasedTool
            self.write_csv(data, output_file, headers=['Report Generated'] + headers)
            
            logger.info(f"Results saved to: {output_file} (timestamp: {current_timestamp})")
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")

    def _save_player_positions_to_csv(self, results: List[tuple], output_file: str):
        """
        Save player positions to CSV file (without distance column for non-coordinate searches)
        
        Args:
            results: List of result tuples (7 or 8 elements)
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
            for result in results:
                if len(result) == 8:  # With distance (ignore distance for this output)
                    filename, line_num, file_date, time_str, player_name, coords, action, distance = result
                elif len(result) == 7:  # Without distance
                    filename, line_num, file_date, time_str, player_name, coords, action = result
                else:
                    logger.warning(f"Unexpected result tuple length: {len(result)}")
                    continue
                    
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
        
        # Determine what filters are being used
        has_player = bool(args.player)
        has_placement = bool(args.placement)
        has_coordinates = args.target_x is not None and args.target_y is not None
        
        # Check for valid combinations
        if not has_player and not has_placement and not has_coordinates:
            logger.error("You must specify at least one filter: --player, --placement, or coordinates (--target-x and --target-y)")
            return
        
        if has_coordinates and (args.target_x is None or args.target_y is None):
            logger.error("Both --target-x and --target-y must be specified for coordinate filtering")
            return
        
        # Use the new combined filter method
        player_filter = args.player if has_player else ""
        placement_filter = args.placement if has_placement else None
        target_x = args.target_x if has_coordinates else None
        target_y = args.target_y if has_coordinates else None
        
        results = self.find_combined_filters(
            args.file_pattern, 
            target_x, target_y, args.radius,
            player_filter, placement_filter,
            args.start_date, args.end_date
        )
        
        if not results:
            # Build search description for logging
            search_parts = []
            if has_player:
                search_parts.append(f"player: {args.player}")
            if has_placement:
                search_parts.append(f"placement: {args.placement}")
            if has_coordinates:
                search_parts.append(f"within {args.radius}m of ({args.target_x}, {args.target_y})")
            search_description = " and ".join(search_parts)
            logger.info(f"No positions found for {search_description}.")
            return
        
        # Apply sorting (date filtering is already done in find_combined_filters)
        results = self._sort_by_time(results)
        
        # Save results using the appropriate method based on whether we have distance data
        if has_coordinates:
            self._save_to_csv(results, output_file)
        else:
            self._save_player_positions_to_csv(results, output_file)
        
        # Build search description for final logging
        search_parts = []
        if has_player:
            search_parts.append(f"player: {args.player}")
        if has_placement:
            search_parts.append(f"placement: {args.placement}")
        if has_coordinates:
            search_parts.append(f"within {args.radius}m of ({args.target_x}, {args.target_y})")
        if args.start_date or args.end_date:
            date_range = []
            if args.start_date:
                date_range.append(f"from {args.start_date}")
            if args.end_date:
                date_range.append(f"to {args.end_date}")
            search_parts.append(" ".join(date_range))
        search_description = " and ".join(search_parts)
        
        logger.info(f"Found {len(results)} positions for {search_description}.")

def main():
    """Command-line entry point for the position finder tool."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Find player positions and actions in DayZ admin log files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Find positions near coordinates using default *.ADM pattern
  dayz-position-finder --target-x 7500 --target-y 8500 --radius 100
  
  # Find positions near coordinates with specific file pattern
  dayz-position-finder --file_pattern "*.ADM" --target-x 7500 --target-y 8500 --radius 100
  
  # Find positions for a specific player (substring search)
  dayz-position-finder --player "SurvivorName"
  
  # Find all placement actions by any player
  dayz-position-finder --placement "placed"
  
  # Find specific item placements (e.g., Fireplace)
  dayz-position-finder --placement "Fireplace"
  
  # Find placement actions by a specific player
  dayz-position-finder --player "LinThoDan" --placement "placed"
  
  # Find specific item placements by a specific player
  dayz-position-finder --player "SpeckSepp" --placement "Wooden Crate"
  
  # COMBINED FILTERS - Find player actions within a specific area
  dayz-position-finder --player "SurvivorName" --target-x 7500 --target-y 8500 --radius 100
  
  # COMBINED FILTERS - Find placement actions within a specific area
  dayz-position-finder --placement "Fireplace" --target-x 7500 --target-y 8500 --radius 200
  
  # COMBINED FILTERS - Find specific player's placements within an area
  dayz-position-finder --player "LinThoDan" --placement "placed" --target-x 7500 --target-y 8500 --radius 150
  
  # COMBINED FILTERS - Find specific item placements by specific player in area
  dayz-position-finder --player "SpeckSepp" --placement "Wooden Crate" --target-x 8440 --target-y 12893 --radius 50
  
  # Find positions using regex pattern (auto-detected)
  dayz-position-finder --player "Survivor.*"
  
  # Find multiple players with regex (auto-detected)
  dayz-position-finder --player "(john|jane|bob)"
  
  # Advanced regex patterns (auto-detected)
  dayz-position-finder --player "^Player[0-9]+$"
  
  # Regex for placement filtering (auto-detected)
  dayz-position-finder --placement "(Fireplace|Wooden Crate|Tent)"
  
  # COMBINED with regex - Find players matching pattern within area
  dayz-position-finder --player "Survivor.*" --target-x 7500 --target-y 8500 --radius 100
  
  # DATE FILTERING - Find player actions within date range
  dayz-position-finder --player "SurvivorName" --start-date 01.06.2023 --end-date 30.06.2023
  
  # DATE + COORDINATES - Find actions in area within date range
  dayz-position-finder --target-x 8440 --target-y 12893 --radius 100 --start-date 15.08.2025 --end-date 30.08.2025
  
  # DATE + PLAYER + COORDINATES - Find player actions in area within date range
  dayz-position-finder --player "LinThoDan" --target-x 7500 --target-y 8500 --radius 150 --start-date 01.08.2025 --end-date 31.08.2025
  
  # FULL COMBINATION - Player + Placement + Area + Date Range
  dayz-position-finder --player "SpeckSepp" --placement "Wooden Crate" --target-x 8440 --target-y 12893 --radius 100 --start-date 20.08.2025 --end-date 30.08.2025
  
  # DATE + PLACEMENT + COORDINATES - Find placements in area within date range
  dayz-position-finder --placement "Fireplace" --target-x 7500 --target-y 8500 --radius 200 --start-date 01.07.2025 --end-date 31.07.2025
  
  # COMBINED with regex + area + date - Find players matching pattern within area and date range
  dayz-position-finder --player "Survivor.*" --target-x 7500 --target-y 8500 --radius 100 --start-date 01.08.2025 --end-date 31.08.2025
  
  # Filter by date range and use specific output file
  dayz-position-finder --player "SurvivorName" --start-date 01.06.2023 --end-date 30.06.2023 --output player_positions.csv
  
  # Use configuration profile
  dayz-position-finder --profile myserver --target-x 7500 --target-y 8500
''')
    
    parser.add_argument('--file_pattern', help='File pattern to search (e.g. "*.ADM"). If not specified, the default "*.ADM" pattern will be used.')
    parser.add_argument('--target-x', type=float, help='Target X coordinate for location-based search')
    parser.add_argument('--target-y', type=float, help='Target Y coordinate for location-based search')
    parser.add_argument('--radius', type=float, default=100.0, help='Search radius in meters (default: 100.0)')
    parser.add_argument('--output', default='positions.csv', help='Output CSV file name (default: positions.csv)')
    parser.add_argument('--player', help='Player name to filter by (regex patterns are auto-detected)')
    parser.add_argument('--placement', help='Filter for placement actions (e.g., "placed", "Fireplace", "Wooden Crate"). Can be used alone or with --player')
    parser.add_argument('--start-date', help='Start date in D.M.YYYY format (e.g., 01.06.2023)')
    parser.add_argument('--end-date', help='End date in D.M.YYYY format (e.g., 30.06.2023)')
    
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

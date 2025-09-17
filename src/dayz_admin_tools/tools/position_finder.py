"""
Position finder tool for DayZ admin logs.

This module provides comprehensive functionalities to search and analyze player positions
and activities in DayZ admin log files. It supports multiple filtering options including:

- Coordinate-based filtering with customizable radius
- Player name filtering with automatic regex pattern detection
- Placement action filtering (e.g., "placed", "Fireplace", "Wooden Crate")
- Date and time range filtering with flexible format support
- Combined filtering using multiple criteria simultaneously

The tool can save results in multiple formats:
- CSV files for data analysis and spreadsheet import
- Original ADM log format for further log analysis
- Both formats simultaneously for maximum flexibility

Key features:
- Auto-detection of regex patterns in player name and placement filters
- Support for date-only or date+time filtering
- Distance calculations for coordinate-based searches
- Timestamped output files to prevent overwrites
- Comprehensive error handling and logging
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
    
    # Default values
    DEFAULT_RADIUS = 100.0
    DEFAULT_PATTERN = "*.ADM"
    
    # File parsing constants
    CSV_MIN_COLUMNS = 9
    HEADER_SKIP_LINES = 3
    COORDINATE_COUNT = 3
    
    # Result tuple indices
    FILENAME_INDEX = 0
    LINE_NUM_INDEX = 1
    FILE_DATE_INDEX = 2
    TIME_STR_INDEX = 3
    PLAYER_NAME_INDEX = 4
    COORDS_INDEX = 5
    ACTION_INDEX = 6
    DISTANCE_INDEX = 7
    
    # Formatting constants
    COORDINATE_PRECISION = 1
    DISTANCE_PRECISION = 2
    
    # Date/time formats
    DATE_FORMAT = "%d.%m.%Y"
    DATETIME_FORMAT = "%d.%m.%Y %H:%M"
    ADMIN_LOG_DATE_FORMAT = "%Y-%m-%d"
    TIME_COMPONENT_COUNT = 2
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the position finder tool.
        
        Args:
            config: Optional configuration dictionary.
            
        Raises:
            ValueError: If configuration is invalid
        """
        if config is not None and not isinstance(config, dict):
            raise ValueError("Config must be a dictionary or None")
            
        super().__init__(config)
        self.initialize_directories()
        
        # Validate log directory exists
        if not hasattr(self, 'log_dir') or not self.log_dir:
            logger.warning("log_dir not configured, will use relative paths")
            
        # Always use *.ADM pattern for position finding
        self.default_pattern = self.DEFAULT_PATTERN
        self._player_regex = None  # Cache for compiled regex pattern
        # Precompiled regex to detect regex metacharacters
        self._regex_detector = re.compile(r'[.*+?^${}()|[\]\\]')
    
    def _extract_info(self, 
                     line: str, 
                     file_date: str) -> Tuple[Optional[str], Optional[str], Optional[tuple], Optional[str]]:
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
                if len(parts) >= self.CSV_MIN_COLUMNS:  # Assuming CSV format with at least 9 columns
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
            if len(coords) != self.COORDINATE_COUNT:
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
                for _ in range(self.HEADER_SKIP_LINES):
                    file.readline()  # Skip the first three lines
                fourth_line = file.readline().strip()
                date_match = re.search(r'AdminLog started on (\d{4}-\d{2}-\d{2})', fourth_line)
                if date_match:
                    # Parse the date and reformat to D.M.YYYY
                    date_str = date_match.group(1)
                    try:
                        date_obj = datetime.strptime(date_str, self.ADMIN_LOG_DATE_FORMAT)
                        return date_obj.strftime(self.DATE_FORMAT)
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
            
        Raises:
            ValueError: If coordinates are invalid
        """
        # Validate coordinates
        coords = [x1, y1, x2, y2]
        coord_names = ['x1', 'y1', 'x2', 'y2']
        
        for coord, name in zip(coords, coord_names):
            if not isinstance(coord, (int, float)):
                raise ValueError(f"Coordinate {name} must be a number, got {type(coord)}")
            if not (-50000 <= coord <= 50000):  # Reasonable bounds for DayZ maps
                logger.warning(f"Coordinate {name}={coord} is outside typical DayZ map bounds (-50000 to 50000)")
        
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

    def _is_regex_pattern(self, pattern: str) -> bool:
        """
        Detect if a string contains regex metacharacters
        
        Args:
            pattern: String to check for regex patterns
            
        Returns:
            True if pattern contains regex metacharacters, False otherwise
        """
        return bool(self._regex_detector.search(pattern))

    def find_combined_filters(self, 
                             file_pattern: Optional[str] = None, 
                             target_x: Optional[float] = None, 
                             target_y: Optional[float] = None, 
                             radius: float = DEFAULT_RADIUS,
                             player_name_filter: str = "", 
                             placement_filter: Optional[str] = None,
                             start_date: Optional[str] = None, 
                             end_date: Optional[str] = None) -> List[tuple]:
        """
        Find positions using combined coordinate, player, placement, and date filters
        
        Args:
            file_pattern: File pattern to search (e.g. "*.ADM"). If None, uses default *.ADM pattern.
            target_x: Target X coordinate (optional)
            target_y: Target Y coordinate (optional)
            radius: Search radius in meters (default: 100.0)
            player_name_filter: Player name to filter by (automatically detects regex patterns)
            placement_filter: Filter for placement actions (e.g., "placed", "Fireplace", "Wooden Crate")
            start_date: Start date filter in D.M.YYYY or D.M.YYYY HH:MM format (optional)
            end_date: End date filter in D.M.YYYY or D.M.YYYY HH:MM format (optional)
        
        Returns:
            List of tuples containing position information with distance (if coordinates provided)
        """
        # Setup regex patterns
        use_regex, use_placement_regex, placement_regex = self._setup_regex_patterns(
            player_name_filter, placement_filter)
        
        # Determine if we're doing coordinate filtering
        use_coordinates = target_x is not None and target_y is not None

        def process_combined_line(filename, line_num, file_date, time_str, player_name, coords, action):
            """Process line for combined search"""
            return self._process_combined_line_filters(
                filename, line_num, file_date, time_str, player_name, coords, action,
                player_name_filter, placement_filter, target_x, target_y, radius,
                use_regex, use_placement_regex, placement_regex, use_coordinates
            )
        
        # Build search description
        description = self._build_search_description(
            player_name_filter, placement_filter, target_x, target_y, radius,
            start_date, end_date, use_regex, use_placement_regex, use_coordinates
        )
        
        results = self._process_files(file_pattern, process_combined_line, description)
        
        # Apply date filtering if specified
        if start_date or end_date:
            results = self._filter_by_date_range(results, start_date, end_date)
        
        # Sort results appropriately
        if use_coordinates:
            return sorted(results, key=lambda x: x[self.DISTANCE_INDEX])  # Sort by distance
        else:
            return results
    
    def _setup_regex_patterns(self, 
                             player_name_filter: str, 
                             placement_filter: Optional[str]) -> Tuple[bool, bool, Optional[re.Pattern]]:
        """Setup regex patterns for player and placement filters."""
        # Auto-detect if the player filter contains regex patterns
        use_regex = self._is_regex_pattern(player_name_filter) if player_name_filter else False
        
        # Precompile regex pattern if needed
        if use_regex:
            try:
                self._player_regex = re.compile(player_name_filter, re.IGNORECASE)
                logger.info(f"Auto-detected regex pattern for player search: {player_name_filter}")
            except re.error as e:
                logger.error(f"Invalid regex pattern '{player_name_filter}': {e}")
                return False, False, None
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
                    return use_regex, False, None
            else:
                logger.info(f"Using substring search for placement: {placement_filter}")
        
        return use_regex, use_placement_regex, placement_regex
    
    def _process_combined_line_filters(self, 
                                     filename, line_num, file_date, time_str, player_name, coords, action,
                                     player_name_filter, placement_filter, target_x, target_y, radius,
                                     use_regex, use_placement_regex, placement_regex, use_coordinates):
        """Process a single line against all filters."""
        # Check player name filter
        player_match = self._check_player_filter(
            player_name, player_name_filter, use_regex)
        
        # Check placement filter
        placement_match = self._check_placement_filter(
            action, placement_filter, use_placement_regex, placement_regex)
        
        # Check coordinate filter
        coordinate_match, distance = self._check_coordinate_filter(
            coords, target_x, target_y, radius, use_coordinates)
        
        if player_match and placement_match and coordinate_match:
            if use_coordinates:
                return (filename, line_num, file_date, time_str, player_name, coords, action, distance)
            else:
                return (filename, line_num, file_date, time_str, player_name, coords, action)
        return None
    
    def _check_player_filter(self, player_name, player_name_filter, use_regex) -> bool:
        """Check if player name matches the filter."""
        if not player_name_filter:
            return True
        if not player_name:
            return False
            
        if use_regex and self._player_regex:
            return bool(self._player_regex.search(player_name))
        elif not use_regex:
            return player_name_filter.lower() in player_name.lower()
        return False
    
    def _check_placement_filter(self, action, placement_filter, use_placement_regex, placement_regex) -> bool:
        """Check if action matches the placement filter."""
        if not placement_filter:
            return True
        if not action:
            return False
            
        if use_placement_regex and placement_regex:
            return bool(placement_regex.search(action))
        elif not use_placement_regex:
            return placement_filter.lower() in action.lower()
        return False
    
    def _check_coordinate_filter(self, coords, target_x, target_y, radius, use_coordinates) -> Tuple[bool, Optional[float]]:
        """Check if coordinates match the location filter."""
        if not use_coordinates:
            return True, None
        if not coords:
            return False, None
            
        x, y, z = coords
        distance = self._calculate_distance(target_x, target_y, x, y)
        return distance <= radius, distance
    
    def _build_search_description(self, 
                                player_name_filter, placement_filter, target_x, target_y, radius,
                                start_date, end_date, use_regex, use_placement_regex, use_coordinates) -> str:
        """Build a description of the search criteria."""
        search_description = []
        if player_name_filter:
            regex_note = "(auto-detected regex)" if use_regex else "(substring)"
            search_description.append(f"player: {player_name_filter} {regex_note}")
        if placement_filter:
            regex_note = "(auto-detected regex)" if use_placement_regex else "(substring)"
            search_description.append(f"placement: {placement_filter} {regex_note}")
        if use_coordinates:
            search_description.append(f"within {radius}m of ({target_x}, {target_y})")
        if start_date or end_date:
            date_parts = []
            if start_date:
                date_parts.append(f"from {start_date}")
            if end_date:
                date_parts.append(f"to {end_date}")
            search_description.append(" ".join(date_parts))
        
        return " and ".join(search_description) if search_description else "all actions"

    def _filter_by_date_range(self, 
                             results: List[tuple], 
                             start_date: Optional[str], 
                             end_date: Optional[str]) -> List[tuple]:
        """
        Filter results by date range with optional time support
        
        Args:
            results: List of result tuples
            start_date: Start date in D.M.YYYY format or D.M.YYYY HH:MM format (optional)
            end_date: End date in D.M.YYYY format or D.M.YYYY HH:MM format (optional)
        
        Returns:
            Filtered list of result tuples
        """
        if not start_date and not end_date:
            return results
        
        # Parse start and end dates with optional time
        start_datetime_obj = self._parse_datetime(start_date) if start_date else None
        end_datetime_obj = self._parse_datetime(end_date) if end_date else None
        
        # Determine if we're filtering by time (not just date)
        start_has_time = start_date and ' ' in start_date if start_date else False
        end_has_time = end_date and ' ' in end_date if end_date else False
        
        filtered_results = []
        
        for result in results:
            file_date_str = result[self.FILE_DATE_INDEX]  # File date from result tuple
            time_str = result[self.TIME_STR_INDEX]        # Time string from result tuple
            
            if file_date_str == "Unknown date":
                continue
            
            try:
                # Parse the file date (D.M.YYYY format)
                file_date_obj = datetime.strptime(file_date_str, self.DATE_FORMAT)
                
                # If we have time filters, also parse the log entry time
                if (start_has_time or end_has_time) and time_str:
                    try:
                        # Parse time from log entry (HH:MM:SS format)
                        time_parts = time_str.split(':')
                        if len(time_parts) >= 2:
                            hour = int(time_parts[0])
                            minute = int(time_parts[1])
                            second = int(time_parts[2]) if len(time_parts) > 2 else 0
                            
                            # Combine file date with log entry time
                            log_datetime_obj = file_date_obj.replace(
                                hour=hour, 
                                minute=minute, 
                                second=second
                            )
                        else:
                            # Fallback to date-only comparison if time parsing fails
                            log_datetime_obj = file_date_obj
                    except (ValueError, IndexError):
                        # Fallback to date-only comparison if time parsing fails
                        log_datetime_obj = file_date_obj
                else:
                    # Use date-only comparison
                    log_datetime_obj = file_date_obj
                
                # Apply filtering based on whether time is specified
                include_result = True
                
                if start_datetime_obj:
                    if start_has_time:
                        include_result = include_result and log_datetime_obj >= start_datetime_obj
                    else:
                        # Date-only comparison for start date
                        include_result = include_result and log_datetime_obj.date() >= start_datetime_obj.date()
                
                if end_datetime_obj and include_result:
                    if end_has_time:
                        include_result = include_result and log_datetime_obj <= end_datetime_obj
                    else:
                        # Date-only comparison for end date
                        include_result = include_result and log_datetime_obj.date() <= end_datetime_obj.date()
                
                if include_result:
                    filtered_results.append(result)
                    
            except ValueError as e:
                logger.debug(f"Date parsing error for result {result}: {e}")
                continue
        
        return filtered_results

    def _parse_datetime(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string with optional time support
        
        Args:
            date_str: Date string in D.M.YYYY or D.M.YYYY HH:MM format
            
        Returns:
            Parsed datetime object or None if parsing fails
            
        Raises:
            ValueError: If date format is invalid
        """
        if not date_str:
            return None
        
        if not isinstance(date_str, str):
            raise ValueError(f"Date must be a string, got {type(date_str)}")
            
        date_str = date_str.strip()
        if not date_str:
            return None
            
        try:
            # Try parsing with time first (D.M.YYYY HH:MM)
            if ' ' in date_str:
                parts = date_str.split(' ')
                if len(parts) != 2:
                    raise ValueError(f"Invalid datetime format '{date_str}': expected 'D.M.YYYY HH:MM'")
                return datetime.strptime(date_str, self.DATETIME_FORMAT)
            else:
                # Parse date-only (D.M.YYYY)
                return datetime.strptime(date_str, self.DATE_FORMAT)
        except ValueError as e:
            logger.error(f"Invalid date format '{date_str}': {e}")
            logger.error("Expected formats: D.M.YYYY (e.g., 01.06.2023) or D.M.YYYY HH:MM (e.g., 01.06.2023 14:30)")
            raise

    def _sort_by_time(self, results: List[tuple]) -> List[tuple]:
        """
        Sort results by time
        
        Args:
            results: List of result tuples
        
        Returns:
            Sorted list of result tuples
        """
        return sorted(results, key=lambda x: (x[self.FILE_DATE_INDEX], x[self.TIME_STR_INDEX]))  # Sort by date and time

    def _save_to_csv(self, results: List[tuple], output_file: str):
        """
        Save results to CSV file (with distance column for coordinate-based searches)
        
        Args:
            results: List of result tuples (8 elements: filename, line_num, file_date, 
                    time_str, player_name, coords, action, distance)
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
                    distance_str = f"{distance:.{self.DISTANCE_PRECISION}f}"
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
                    'X': f"{coords[0]:.{self.COORDINATE_PRECISION}f}" if coords else "",
                    'Y': f"{coords[1]:.{self.COORDINATE_PRECISION}f}" if coords else "",
                    'Z': f"{coords[2]:.{self.COORDINATE_PRECISION}f}" if coords else "",
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
                    'X': f"{coords[0]:.{self.COORDINATE_PRECISION}f}" if coords else "",
                    'Y': f"{coords[1]:.{self.COORDINATE_PRECISION}f}" if coords else "",
                    'Z': f"{coords[2]:.{self.COORDINATE_PRECISION}f}" if coords else "",
                    'Action': action if action else ""
                })
            
            # Use write_csv from FileBasedTool
            self.write_csv(data, output_file, headers=['Report Generated'] + headers)
            
            logger.info(f"Results saved to: {output_file} (timestamp: {current_timestamp})")
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")

    def _save_to_adm(self, results: List[tuple], output_file: str):
        """
        Save filtered results to ADM file format (original log format with only filtered lines)
        
        Args:
            results: List of result tuples
            output_file: Name of the ADM file to create
        """
        try:
            # Extract date and time from the first result for header
            if results:
                first_result = results[0]
                first_file_date = first_result[2]  # File date (D.M.YYYY format)
                first_time_str = first_result[3]   # Time string (HH:MM:SS format)
                
                # Convert file date to YYYY-MM-DD format for header
                try:
                    file_date_obj = datetime.strptime(first_file_date, "%d.%m.%Y")
                    header_date = file_date_obj.strftime("%Y-%m-%d")
                    
                    # Use the time from the first entry, or current time as fallback
                    if first_time_str:
                        header_time = first_time_str
                    else:
                        header_time = datetime.now().strftime("%H:%M:%S")
                        
                except ValueError:
                    # Fallback to current date/time if parsing fails
                    header_date = datetime.now().strftime("%Y-%m-%d")
                    header_time = datetime.now().strftime("%H:%M:%S")
            else:
                # Fallback to current date/time if no results
                header_date = datetime.now().strftime("%Y-%m-%d")
                header_time = datetime.now().strftime("%H:%M:%S")
            
            # Generate metadata timestamp for comment
            current_timestamp = datetime.now().strftime("%Y-%m-%d at %H:%M:%S")
            
            # Build a dictionary to group results by original file
            files_data = {}
            original_lines = {}
            
            # First pass: collect unique source files and read their original lines
            for result in results:
                filename = result[0]
                line_num = result[1]
                
                if filename not in files_data:
                    files_data[filename] = []
                    original_lines[filename] = {}
                
                files_data[filename].append((line_num, result))
            
            # Read original lines from source files
            for filename in files_data.keys():
                # Find the full path to the source file
                source_files = self._get_matching_files()
                source_file_path = None
                
                for source_path in source_files:
                    if os.path.basename(source_path) == filename:
                        source_file_path = source_path
                        break
                
                if source_file_path and os.path.exists(source_file_path):
                    try:
                        with open(source_file_path, 'r', encoding='utf-8') as f:
                            for current_line_num, line in enumerate(f, 1):
                                # Store lines that are in our results
                                for line_num, _ in files_data[filename]:
                                    if current_line_num == line_num:
                                        original_lines[filename][line_num] = line.rstrip('\n\r')
                    except Exception as e:
                        logger.warning(f"Could not read original lines from {source_file_path}: {e}")
            
            # Write to ADM file with format closer to original
            with open(output_file, 'w', encoding='utf-8') as f:
                # Add empty lines at the beginning (like original)
                f.write("\n\n")
                
                # Write header similar to original but with warning
                f.write("******************************************************************************\n")
                f.write("*** FILTERED ADMIN LOG - NOT A COMPLETE LOG - FOR ANALYSIS ONLY ***\n")
                f.write("******************************************************************************\n")
                f.write(f"AdminLog started on {header_date} at {header_time}\n")
                
                # Write filtered log entries without file separators for cleaner look
                for result in results:
                    filename = result[0]
                    line_num = result[1]
                    
                    # Try to write the original line if available
                    if filename in original_lines and line_num in original_lines[filename]:
                        f.write(original_lines[filename][line_num] + "\n")
                    else:
                        # Fallback: reconstruct the line from parsed data
                        time_str = result[3] if result[3] else ""
                        player_name = result[4] if result[4] else ""
                        coords = result[5]
                        action = result[6] if result[6] else ""
                        
                        if coords:
                            pos_str = f"pos=<{coords[0]:.{self.COORDINATE_PRECISION}f}, " \
                                     f"{coords[1]:.{self.COORDINATE_PRECISION}f}, " \
                                     f"{coords[2]:.{self.COORDINATE_PRECISION}f}>"
                            reconstructed_line = f'{time_str} | Player "{player_name}" (id=UNKNOWN {pos_str}) {action}'
                        else:
                            reconstructed_line = f'{time_str} | Player "{player_name}" {action}'
                        
                        f.write(reconstructed_line + "\n")
            
            logger.info(f"Filtered ADM results saved to: {output_file} (entries: {len(results)})")
            
        except Exception as e:
            logger.error(f"Error saving to ADM format: {e}")

    def run(self, args) -> None:
        """
        Run the position finder tool.
        
        Args:
            args: Command-line arguments
        """
        # Ensure output directory exists
        os.makedirs(self.resolve_path(self.output_dir), exist_ok=True)

        # Determine output file extension based on format
        output_format = getattr(args, 'output_format', 'csv')
        
        # For 'both' format, we'll create both files with appropriate extensions
        if output_format == 'both':
            # Parse the original filename
            filename, extension = os.path.splitext(args.output)
            base_filename = filename
            
            # Generate timestamped filenames for both formats
            csv_filename = self.generate_timestamped_filename(base_filename, 'csv')
            adm_filename = self.generate_timestamped_filename(base_filename, 'ADM')
            
            # Build output file paths
            csv_output_file = os.path.join(self.resolve_path(self.output_dir), csv_filename)
            adm_output_file = os.path.join(self.resolve_path(self.output_dir), adm_filename)
            
        elif output_format == 'adm':
            # Change extension to .ADM if user specified csv extension
            filename, extension = os.path.splitext(args.output)
            if extension.lower() in ['.csv']:
                base_filename = filename
                file_extension = 'ADM'
            else:
                base_filename = filename + extension.lstrip('.')
                file_extension = 'ADM'
            
            # Add timestamp to output filename
            timestamped_filename = self.generate_timestamped_filename(base_filename, file_extension)
            
            # Build output file path
            output_file = os.path.join(self.resolve_path(self.output_dir), timestamped_filename)
            
        else:
            # CSV format (default)
            filename, extension = os.path.splitext(args.output)
            extension = extension.lstrip('.')  # Remove leading dot
            if not extension:
                extension = 'csv'
            base_filename = filename
            file_extension = extension

            # Add timestamp to output filename
            timestamped_filename = self.generate_timestamped_filename(base_filename, file_extension)
            
            # Build output file path
            output_file = os.path.join(self.resolve_path(self.output_dir), timestamped_filename)
        
        # Determine what filters are being used
        has_player = bool(args.player)
        has_placement = bool(args.placement)
        has_coordinates = args.target_x is not None and args.target_y is not None
        
        # Check for valid combinations
        if not has_player and not has_placement and not has_coordinates:
            logger.error("You must specify at least one filter: --player, --placement, "
                        "or coordinates (--target-x and --target-y)")
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
        
        # Save results using the appropriate method based on output format
        if output_format == 'both':
            # Save both CSV and ADM formats
            if has_coordinates:
                self._save_to_csv(results, csv_output_file)
            else:
                self._save_player_positions_to_csv(results, csv_output_file)
            self._save_to_adm(results, adm_output_file)
            
        elif output_format == 'adm':
            self._save_to_adm(results, output_file)
        elif has_coordinates:
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
  
  # DATE + TIME FILTERING - Find actions within specific time range
  dayz-position-finder --player "Player15957802" --start-date "07.09.2025 16:00" --end-date "07.09.2025 18:30"
  
  # DATE + COORDINATES - Find actions in area within date range
  dayz-position-finder --target-x 8440 --target-y 12893 --radius 100 --start-date 15.08.2025 --end-date 30.08.2025
  
  # TIME-SPECIFIC COORDINATE SEARCH - Find actions in area at specific time
  dayz-position-finder --target-x 4631 --target-y 10439 --radius 50 --start-date "05.09.2025 16:00" --end-date "05.09.2025 17:00"
  
  # DATE + PLAYER + COORDINATES - Find player actions in area within date range
  dayz-position-finder --player "LinThoDan" --target-x 7500 --target-y 8500 --radius 150 --start-date 01.08.2025 --end-date 31.08.2025
  
  # FULL COMBINATION - Player + Placement + Area + Date Range
  dayz-position-finder --player "SpeckSepp" --placement "Wooden Crate" --target-x 8440 --target-y 12893 --radius 100 --start-date 20.08.2025 --end-date 30.08.2025
  
  # DATE + PLACEMENT + COORDINATES - Find placements in area within date range
  dayz-position-finder --placement "Fireplace" --target-x 7500 --target-y 8500 --radius 200 --start-date 01.07.2025 --end-date 31.07.2025
  
  # COMBINED with regex + area + date - Find players matching pattern within area and date range
  dayz-position-finder --player "Survivor.*" --target-x 7500 --target-y 8500 --radius 100 --start-date 01.08.2025 --end-date 31.08.2025
  
  # TIME-BASED FILTERING - Find actions within specific time window
  dayz-position-finder --placement "placed" --start-date "08.09.2025 14:00" --end-date "08.09.2025 16:00"
  
  # Filter by date range and use specific output file
  dayz-position-finder --player "SurvivorName" --start-date 01.06.2023 --end-date 30.06.2023 --output player_positions.csv
  
  # Save results in original ADM log format instead of CSV
  dayz-position-finder --player "LinThoDan" --placement "placed" --output-format adm --output filtered_results.ADM
  
  # Find player actions and save as ADM file for further analysis
  dayz-position-finder --player "SpeckSepp" --target-x 8440 --target-y 12893 --radius 100 --output-format adm
  
  # Save results in both CSV and ADM formats
  dayz-position-finder --player "Player15957802" --placement "placed" --output-format both --output results
  
  # Generate both formats for coordinate-based search
  dayz-position-finder --target-x 7500 --target-y 8500 --radius 100 --output-format both
  
  # Use configuration profile
  dayz-position-finder --profile myserver --target-x 7500 --target-y 8500
''')
    
    parser.add_argument('--file_pattern', 
                       help='File pattern to search (e.g. "*.ADM"). '
                            'If not specified, the default "*.ADM" pattern will be used.')
    parser.add_argument('--target-x', type=float, 
                       help='Target X coordinate for location-based search')
    parser.add_argument('--target-y', type=float, 
                       help='Target Y coordinate for location-based search')
    parser.add_argument('--radius', type=float, default=PositionFinder.DEFAULT_RADIUS, 
                       help=f'Search radius in meters (default: {PositionFinder.DEFAULT_RADIUS})')
    parser.add_argument('--output', default='positions.csv', 
                       help='Output file name (default: positions.csv)')
    parser.add_argument('--output-format', choices=['csv', 'adm', 'both'], default='csv', 
                       help='Output format: csv for CSV file (default), adm for original ADM log format, '
                            'or both for both formats')
    parser.add_argument('--player', 
                       help='Player name to filter by (regex patterns are auto-detected)')
    parser.add_argument('--placement', 
                       help='Filter for placement actions (e.g., "placed", "Fireplace", "Wooden Crate"). '
                            'Can be used alone or with --player')
    parser.add_argument('--start-date', 
                       help='Start date filter in D.M.YYYY format (e.g., 01.06.2023) '
                            'or D.M.YYYY HH:MM format (e.g., 01.06.2023 14:30)')
    parser.add_argument('--end-date', 
                       help='End date filter in D.M.YYYY format (e.g., 30.06.2023) '
                            'or D.M.YYYY HH:MM format (e.g., 30.06.2023 18:45)')
    
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

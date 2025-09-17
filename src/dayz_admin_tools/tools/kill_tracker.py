#!/usr/bin/env python3
"""
DayZ Admin Tools - Kill Tracker

Analyzes DayZ server logs to rank players by kill count.
This tool parses ADM log files and provides statistics on player kills.
"""

import argparse
import os
import logging
import re
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

from dayz_admin_tools.base import DayZTool, FileBasedTool

logger = logging.getLogger(__name__)


class KillTracker(FileBasedTool):
    """
    Tracks and ranks player kills from DayZ server logs.
    
    This class parses ADM log files to extract kill events,
    and provides ranked statistics on player kills.
    """
    
    # Class constants
    LOG_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    INPUT_DATE_FORMAT = "%d.%m.%Y %H:%M:%S"
    TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
    ADM_FILE_EXTENSION = ".adm"
    
    # Precompiled regex patterns for better performance
    ADMIN_LOG_START_PATTERN = re.compile(r'AdminLog started on (.+?) at (.+)')
    KILL_EVENT_PATTERN = re.compile(r'(.+?) \| Player "(.+?)" .*? killed by Player "(.+?)"')
    
    # CSV headers
    CSV_HEADERS = ["Report Generated", "Rank", "Player", "Kills", "Victims"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the KillTracker with configuration.
        
        Args:
            config: Configuration dictionary from Config class
        """
        super().__init__(config)
        self.initialize_directories()
        
        # Use proper configuration access pattern
        self.log_download_path = self.config.get('paths.log_dir') or self.log_dir
        
        # Ensure directories exist
        self.ensure_dir(self.log_download_path)
        self.ensure_dir(self.output_dir)
        
    def _validate_log_file(self, file_path: str) -> bool:
        """
        Validate that a log file exists and is readable.
        
        Args:
            file_path: Path to the log file
            
        Returns:
            True if file is valid, False otherwise
        """
        try:
            if not os.path.isfile(file_path):
                logger.warning(f"File does not exist: {file_path}")
                return False
            
            if not os.access(file_path, os.R_OK):
                logger.warning(f"File is not readable: {file_path}")
                return False
                
            # Check file size (warn if too large, but don't reject)
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:  # 100MB
                logger.warning(f"Large file detected ({file_size / 1024 / 1024:.1f}MB): {file_path}")
                
            return True
        except Exception as e:
            logger.error(f"Error validating file {file_path}: {e}")
            return False
        
    def parse_log(self, file_path: str, start_datetime: Optional[datetime] = None,
                 end_datetime: Optional[datetime] = None) -> Tuple[List[Tuple[str, int]], Dict[str, List[str]]]:
        """
        Parse a single log file for kill events.
        
        Args:
            file_path: Path to the log file
            start_datetime: Optional start time filter
            end_datetime: Optional end time filter
            
        Returns:
            Tuple of (sorted_kills, killed_tags)
        """
        kills = {}
        killed_tags = {}
        processed_kills = set()  # Track processed kill events to avoid double-counting
        log_date = None

        # Resolve and validate the path
        resolved_path = self.resolve_path(file_path)
        
        if not self._validate_log_file(resolved_path):
            return [], {}
            
        logger.info(f"Parsing log file: {resolved_path}")
        
        try:
            with open(resolved_path, 'r', encoding='utf-8', errors='ignore') as file:
                for line_num, line in enumerate(file, 1):
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Extract the date from the log header using regex
                    if not log_date:
                        admin_log_match = self.ADMIN_LOG_START_PATTERN.search(line)
                        if admin_log_match:
                            try:
                                log_date = admin_log_match.group(1)
                                logger.debug(f"Found log date: {log_date}")
                                continue
                            except Exception as e:
                                logger.warning(f"Failed to parse log date from line {line_num}: {e}")
                                continue

                    # Skip lines until the date is extracted
                    if not log_date:
                        continue

                    # Check if the line contains a kill event using regex
                    kill_match = self.KILL_EVENT_PATTERN.search(line)
                    if kill_match:
                        try:
                            time_part = kill_match.group(1)
                            killed = kill_match.group(2)
                            killer = kill_match.group(3)
                            
                            # Parse datetime
                            try:
                                log_datetime = datetime.strptime(f"{log_date} {time_part}", self.LOG_DATETIME_FORMAT)
                            except ValueError as e:
                                logger.warning(f"Invalid datetime format on line {line_num}: {e}")
                                continue

                            # Apply time filters
                            if start_datetime and log_datetime < start_datetime:
                                continue
                            if end_datetime and log_datetime > end_datetime:
                                continue

                            # Create a unique key for this kill event
                            kill_key = f"{time_part}_{killed}_{killer}"
                            
                            # Only count if we haven't seen this exact kill event before
                            if kill_key not in processed_kills:
                                processed_kills.add(kill_key)
                                
                                # Update kills and killed player lists
                                kills[killer] = kills.get(killer, 0) + 1
                                if killer not in killed_tags:
                                    killed_tags[killer] = []
                                killed_tags[killer].append(killed)
                                
                        except (IndexError, ValueError) as e:
                            logger.warning(f"Failed to parse kill event on line {line_num}: {line} - {e}")
                            continue
                            
        except Exception as e:
            logger.error(f"Error parsing log file {resolved_path}: {e}")
            return [], {}
            
        logger.info(f"Processed {len(processed_kills)} kill events from {resolved_path}")
        
        # Sort kills by count in descending order
        sorted_kills = sorted(kills.items(), key=lambda x: x[1], reverse=True)
        return sorted_kills, killed_tags
        
    def analyze_logs(self, log_dir: Optional[str] = None, start_datetime: Optional[datetime] = None,
                    end_datetime: Optional[datetime] = None) -> Tuple[List[Tuple[str, int]], Dict[str, List[str]]]:
        """
        Analyze all log files in a directory.
        
        Args:
            log_dir: Directory containing .ADM log files
            start_datetime: Optional start time filter
            end_datetime: Optional end time filter
            
        Returns:
            Tuple of (sorted_kills, killed_tags)
        """
        # Use configured log path if none provided
        if log_dir is None:
            log_dir = self.log_download_path
        
        # Resolve the directory path
        resolved_dir = self.resolve_path(log_dir)
            
        if not os.path.isdir(resolved_dir):
            logger.error(f"The specified path is not a directory: {resolved_dir}")
            return [], {}

        # Find all ADM files
        adm_files = []
        try:
            for file in os.listdir(resolved_dir):
                if file.lower().endswith(self.ADM_FILE_EXTENSION):
                    adm_files.append(os.path.join(resolved_dir, file))
        except Exception as e:
            logger.error(f"Error listing directory {resolved_dir}: {e}")
            return [], {}
                
        if not adm_files:
            logger.error(f"No {self.ADM_FILE_EXTENSION} files found in directory: {resolved_dir}")
            return [], {}
            
        logger.info(f"Found {len(adm_files)} log files to analyze")

        # Aggregate kills across all .ADM files
        total_kills = {}
        total_killed_tags = {}
        
        for i, file_path in enumerate(adm_files, 1):
            logger.info(f"Processing file {i}/{len(adm_files)}: {os.path.basename(file_path)}")
            
            kills, killed_tags = self.parse_log(file_path, start_datetime, end_datetime)
            
            # Aggregate results
            for player, count in kills:
                total_kills[player] = total_kills.get(player, 0) + count
                
            for player, tags in killed_tags.items():
                if player not in total_killed_tags:
                    total_killed_tags[player] = []
                total_killed_tags[player].extend(tags)

        # Sort results
        sorted_kills = sorted(total_kills.items(), key=lambda x: x[1], reverse=True)
        logger.info(f"Analysis complete: {len(sorted_kills)} players with kills")
        
        return sorted_kills, total_killed_tags

    def print_results(self, sorted_kills: List[Tuple[str, int]], 
                     killed_tags: Dict[str, List[str]]) -> int:
        """
        Print the kill statistics to the console.
        
        Args:
            sorted_kills: List of (player, kill_count) tuples
            killed_tags: Dictionary mapping killers to their victims
            
        Returns:
            Total number of kills
        """
        if not sorted_kills:
            logger.info("No kill events found.")
            return 0
            
        logger.info("Kills per player (ranked):")
        logger.info("=" * 50)
        
        grand_total = 0
        
        for rank, (player, count) in enumerate(sorted_kills, start=1):
            victims_list = ", ".join(killed_tags.get(player, []))
            logger.info(f"{rank:3d}. {player}: {count} kills (Victims: {victims_list})")
            grand_total += count

        logger.info("=" * 50)
        logger.info(f"Grand Total (GT) of kills: {grand_total}")
        
        return grand_total
    
    def _prepare_csv_data(self, sorted_kills: List[Tuple[str, int]], 
                         killed_tags: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """
        Prepare data for CSV export.
        
        Args:
            sorted_kills: List of (player, kill_count) tuples
            killed_tags: Dictionary mapping killers to their victims
            
        Returns:
            List of dictionaries ready for CSV export
        """
        data = []
        current_timestamp = datetime.now().strftime(self.TIMESTAMP_FORMAT)
        
        # Add metadata
        data.append({"Report Generated": current_timestamp})
        data.append({})  # Empty row
        
        # Add headers
        data.append({
            "Rank": "Rank",
            "Player": "Player", 
            "Kills": "Kills",
            "Victims": "Victims"
        })
        
        # Add kill data
        grand_total = 0
        for rank, (player, count) in enumerate(sorted_kills, start=1):
            victims_list = ", ".join(killed_tags.get(player, []))
            data.append({
                "Rank": rank,
                "Player": player,
                "Kills": count,
                "Victims": victims_list
            })
            grand_total += count
            
        # Add summary
        data.append({})  # Empty row
        data.append({
            "Player": "GRAND TOTAL",
            "Kills": grand_total
        })
        
        return data
    
    def save_to_csv(self, sorted_kills: List[Tuple[str, int]], 
                   killed_tags: Dict[str, List[str]]) -> str:
        """
        Save kill statistics to a CSV file.
        
        Args:
            sorted_kills: List of (player, kill_count) tuples
            killed_tags: Dictionary mapping killers to their victims
            
        Returns:
            Path to the saved CSV file
        """
        # Create CSV filename with timestamp using base class method
        output_file = self.generate_timestamped_filename("kill_tracker", "csv")
        
        # Prepare data for CSV
        data = self._prepare_csv_data(sorted_kills, killed_tags)
        
        # Use write_csv from FileBasedTool
        file_path = self.write_csv(data, output_file, headers=self.CSV_HEADERS)
        
        current_timestamp = datetime.now().strftime(self.TIMESTAMP_FORMAT)
        logger.info(f"Kill statistics saved to: {file_path} (timestamp: {current_timestamp})")
        
        return file_path
        
    def run(self, log_dir: Optional[str] = None, start_datetime: Optional[datetime] = None, 
           end_datetime: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Run the kill tracker analysis.
        
        Args:
            log_dir: Directory containing .ADM log files
            start_datetime: Optional start time filter
            end_datetime: Optional end time filter
            
        Returns:
            Dictionary with analysis results
        """
        logger.info("Starting kill tracker analysis...")
        
        if start_datetime:
            logger.info(f"Start time filter: {start_datetime.strftime(self.LOG_DATETIME_FORMAT)}")
        if end_datetime:
            logger.info(f"End time filter: {end_datetime.strftime(self.LOG_DATETIME_FORMAT)}")
        
        sorted_kills, killed_tags = self.analyze_logs(log_dir, start_datetime, end_datetime)
        
        result = {
            "success": True,
            "kill_count": 0,
            "player_count": len(sorted_kills),
            "output_file": None
        }
        
        if sorted_kills:
            # Print results to console
            kill_count = self.print_results(sorted_kills, killed_tags)
            
            # Save results to CSV
            output_file = self.save_to_csv(sorted_kills, killed_tags)
            
            result.update({
                "kill_count": kill_count,
                "output_file": output_file
            })
            
            logger.info(f"Analysis complete: {kill_count} total kills from {len(sorted_kills)} players")
        else:
            logger.warning("No kill events found in the log files.")
            result["success"] = False
            
        return result
        

def main():
    """
    Main entry point for the kill tracker command line tool.
    """
    parser = argparse.ArgumentParser(
        description="Parse DayZ log files and count kills per player.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --log-dir /path/to/logs
    %(prog)s --start "01.06.2023 14:30:00" --end "30.06.2023 23:59:59"
    %(prog)s --profile my_server

Configuration:
    - paths.log_dir: Directory containing .ADM log files
    - general.output_path: Directory for CSV output files
        """
    )
    parser.add_argument(
        "--log-dir", 
        help="Path to the directory containing .ADM log files. If not specified, uses the configured path."
    )
    parser.add_argument(
        "--start", 
        help="Start date and time in D.M.YYYY HH:MM:SS format (e.g., 01.06.2023 14:30:00).", 
        type=str
    )
    parser.add_argument(
        "--end", 
        help="End date and time in D.M.YYYY HH:MM:SS format (e.g., 30.06.2023 23:59:59).", 
        type=str
    )
    
    # Add standard arguments from DayZTool
    DayZTool.add_standard_arguments(parser)
    args = parser.parse_args()

    try:
        # Load configuration using the base class static method
        config = KillTracker.load_config(args.profile)
        
        # Parse start and end datetimes
        start_datetime = None
        end_datetime = None
        
        if args.start:
            try:
                start_datetime = datetime.strptime(args.start, KillTracker.INPUT_DATE_FORMAT)
            except ValueError:
                raise ValueError(f"Invalid start date format. Use D.M.YYYY HH:MM:SS format (e.g., 01.06.2023 14:30:00)")
        
        if args.end:
            try:
                end_datetime = datetime.strptime(args.end, KillTracker.INPUT_DATE_FORMAT)
            except ValueError:
                raise ValueError(f"Invalid end date format. Use D.M.YYYY HH:MM:SS format (e.g., 30.06.2023 23:59:59)")

        # Validate date range
        if start_datetime and end_datetime and start_datetime >= end_datetime:
            raise ValueError("Start date must be before end date")

        # Initialize and run tracker
        tracker = KillTracker(config)
        result = tracker.run(args.log_dir, start_datetime, end_datetime)
        
        if args.console:
            logger.info(f"Kill tracker analysis completed: {result}")
        
        # Return success code
        return 0 if result["success"] else 1
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())

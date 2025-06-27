#!/usr/bin/env python3
"""
DayZ Admin Tools - Kill Tracker

Analyzes DayZ server logs to rank players by kill count.
This tool parses ADM log files and provides statistics on player kills.
"""

import argparse
import os
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any

from dayz_admin_tools.base import DayZTool, FileBasedTool

logger = logging.getLogger(__name__)


class KillTracker(FileBasedTool):
    """
    Tracks and ranks player kills from DayZ server logs.
    
    This class parses ADM log files to extract kill events,
    and provides ranked statistics on player kills.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the KillTracker with configuration.
        
        Args:
            config: Configuration dictionary from Config class
        """
        super().__init__(config)
        self.initialize_directories()
        
        # Map log_dir to log_download_path for compatibility with existing methods
        self.log_download_path = self.log_dir
        
        # Ensure directories exist
        self.ensure_dir(self.log_download_path)
        self.ensure_dir(self.output_dir)
        
    def parse_log(self, file_path: str, start_datetime: datetime = None, 
                 end_datetime: datetime = None) -> Tuple[List[Tuple[str, int]], Dict[str, List[str]]]:
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
        log_date = None

        # Resolve the path to ensure it's absolute
        resolved_path = self.resolve_path(file_path)
        logger.info(f"Parsing log file: {resolved_path}")
        
        try:
            with open(resolved_path, 'r') as file:
                for line in file:
                    # Extract the date from the log header
                    if "AdminLog started on" in line:
                        log_date = line.split("AdminLog started on ")[1].split(" at ")[0]
                        continue

                    # Skip lines until the date is extracted
                    if not log_date:
                        continue

                    # Check if the line contains a kill event
                    if "killed by Player" in line:
                        # Extract timestamp and combine with log_date
                        time_part = line.split(" | ")[0]
                        log_datetime = datetime.strptime(f"{log_date} {time_part}", "%Y-%m-%d %H:%M:%S")

                        # Ensure the datetime falls within the range
                        if start_datetime and log_datetime < start_datetime:
                            continue
                        if end_datetime and log_datetime > end_datetime:
                            continue

                        # Extract killer's name and killed player's name
                        killer = line.split('killed by Player "')[1].split('"')[0]
                        killed = line.split('Player "')[1].split('"')[0]

                        # Update kills and killed Gamertags
                        kills[killer] = kills.get(killer, 0) + 1
                        if killer not in killed_tags:
                            killed_tags[killer] = []
                        killed_tags[killer].append(killed)
        except Exception as e:
            logger.error(f"Error parsing log file {resolved_path}: {str(e)}")
            
        # Sort kills by count in descending order
        sorted_kills = sorted(kills.items(), key=lambda x: x[1], reverse=True)
        return sorted_kills, killed_tags
        
    def analyze_logs(self, log_dir: str = None, start_datetime: datetime = None, 
                    end_datetime: datetime = None) -> Tuple[List[Tuple[str, int]], Dict[str, List[str]]]:
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
            logger.error(f"Error: The specified path is not a directory: {resolved_dir}")
            return [], {}

        adm_files = []
        for file in os.listdir(resolved_dir):
            if file.lower().endswith(".adm"):
                adm_files.append(os.path.join(resolved_dir, file))
                
        if not adm_files:
            logger.error(f"Error: No .ADM files found in the specified directory: {resolved_dir}")
            return [], {}
            
        logger.info(f"Found {len(adm_files)} log files to analyze")

        # Aggregate kills across all .ADM files
        total_kills = {}
        total_killed_tags = {}
        for file_path in adm_files:
            kills, killed_tags = self.parse_log(file_path, start_datetime, end_datetime)
            for player, count in kills:
                total_kills[player] = total_kills.get(player, 0) + count
            for player, tags in killed_tags.items():
                if player not in total_killed_tags:
                    total_killed_tags[player] = []
                total_killed_tags[player].extend(tags)

        # Sort results
        sorted_kills = sorted(total_kills.items(), key=lambda x: x[1], reverse=True)
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
        logger.info("Kills per player (ranked):")
        grand_total = 0
        
        for rank, (player, count) in enumerate(sorted_kills, start=1):
            killed_list = ", ".join(killed_tags[player])
            logger.info(f"{rank}. {player}: {count} kills (Killed: {killed_list})")
            grand_total += count

        logger.info(f"\nGrand Total (GT) of kills: {grand_total}")
        
        # Return the kill count for internal use, but this won't be used as an exit code anymore
        return grand_total
    
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
        # Generate current timestamp for data and filename
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create CSV filename with timestamp using base class method
        output_file = self.generate_timestamped_filename("kill_tracker", "csv")
        
        # Prepare data for CSV
        data = []
        
        # Add timestamp as the first row
        data.append({"Report Generated": current_timestamp})
        
        # Add an empty row for better readability
        data.append({})
        
        # Add column headers as a record
        data.append({"Rank": "Rank", "Player": "Player", "Kills": "Kills", "Victims": "Victims"})
        
        # Add kill data
        grand_total = 0
        for rank, (player, count) in enumerate(sorted_kills, start=1):
            killed_list = ", ".join(killed_tags[player])
            data.append({
                "Rank": rank,
                "Player": player,
                "Kills": count,
                "Victims": killed_list
            })
            grand_total += count
            
        # Add summary row with grand total
        data.append({})  # Empty row
        data.append({"Player": "GRAND TOTAL", "Kills": grand_total})
        
        # Use write_csv from FileBasedTool
        headers = ["Report Generated", "Rank", "Player", "Kills", "Victims"]
        file_path = self.write_csv(data, output_file, headers=headers)
        
        logger.info(f"Kill statistics saved to: {file_path} (timestamp: {current_timestamp})")
        return file_path
        
    def run(self, log_dir: str = None, start_datetime: datetime = None, 
           end_datetime: datetime = None) -> int:
        """
        Run the kill tracker analysis.
        
        Args:
            log_dir: Directory containing .ADM log files
            start_datetime: Optional start time filter
            end_datetime: Optional end time filter
            
        Returns:
            Total number of kills found
        """
        sorted_kills, killed_tags = self.analyze_logs(log_dir, start_datetime, end_datetime)
        
        if sorted_kills:
            # Print results to console
            kill_count = self.print_results(sorted_kills, killed_tags)
            
            # Save results to CSV
            self.save_to_csv(sorted_kills, killed_tags)
            
            return kill_count
        else:
            logger.warning("No kill events found in the log files.")
            return 0
        

def main():
    """
    Main entry point for the kill tracker command line tool.
    """
    parser = argparse.ArgumentParser(
        description="Parse DayZ log files and count kills per player.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--log-dir", 
        help="Path to the directory containing .ADM log files. If not specified, uses the configured path."
    )
    parser.add_argument(
        "--start", 
        help="Start date and time in YYYY-MM-DD HH:MM:SS format.", 
        type=str
    )
    parser.add_argument(
        "--end", 
        help="End date and time in YYYY-MM-DD HH:MM:SS format.", 
        type=str
    )
    
    # Add standard arguments from DayZTool
    DayZTool.add_standard_arguments(parser)
    args = parser.parse_args()

    try:
        # Load configuration using the base class static method
        config = KillTracker.load_config(args.profile)
        
        # Parse start and end datetimes
        start_datetime = datetime.strptime(args.start, "%Y-%m-%d %H:%M:%S") if args.start else None
        end_datetime = datetime.strptime(args.end, "%Y-%m-%d %H:%M:%S") if args.end else None

        # Initialize and run tracker
        tracker = KillTracker(config)
        kill_count = tracker.run(args.log_dir, start_datetime, end_datetime)
        
        # Always return 0 for success, regardless of the number of kills found
        # The actual kill count is already logged by the run method
        return 0
            
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main())

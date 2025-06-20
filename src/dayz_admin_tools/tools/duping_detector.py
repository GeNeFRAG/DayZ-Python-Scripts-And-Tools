#!/usr/bin/env python3
"""
DayZ Admin Tools - Duping Detector

Analyzes DayZ server logs to detect possible item duplication by players.
This tool parses ADM and RPT log files to identify suspicious activities.
"""

import re
import glob
import argparse
import logging
import os
from datetime import datetime, timedelta
from math import sqrt
from typing import Dict, List, Tuple, Any

from dayz_admin_tools.base import DayZTool, FileBasedTool

logger = logging.getLogger(__name__)


class DupingDetector(FileBasedTool):
    """
    Detects possible duping activities from DayZ server logs.
    
    This class parses ADM and RPT log files to identify suspicious 
    item spawn patterns that might indicate duplication exploits.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the DupingDetector with configuration.
        
        Args:
            config: Configuration dictionary from Config class
        """
        super().__init__(config)
        self.initialize_directories()
        
        # Ensure directories exist
        self.ensure_dir(self.log_dir)
        self.ensure_dir(self.output_dir)
        
        # Map log_dir to log_download_path for compatibility with existing methods
        self.log_download_path = self.log_dir
        
        # Get default thresholds from config or use hardcoded defaults
        self.proximity_threshold = float(self.get_config('duping_detector.proximity_threshold', 10))
        self.time_threshold = timedelta(seconds=int(self.get_config('duping_detector.time_threshold', 60)))
        self.login_threshold = timedelta(seconds=int(self.get_config('duping_detector.login_threshold', 300)))
        self.login_count_threshold = int(self.get_config('duping_detector.login_count_threshold', 3))
        
    def parse_adm_file(self, file_path: str) -> Tuple[List[Tuple[datetime, Tuple[float, float], str]], List[Tuple[datetime, str]]]:
        """
        Parses an ADM log file to extract player positions and login events.

        Args:
            file_path: The path to the ADM log file.

        Returns:
            A tuple containing:
                - player_positions: A list of tuples with player positions in the format (timestamp, position, player_name).
                - login_events: A list of tuples with login events in the format (timestamp, player_name).
        """
        player_positions = []
        login_events = []
        current_date = None
        
        # Resolve the path to ensure it's absolute
        resolved_path = self.resolve_path(file_path)
        logger.debug(f"Parsing ADM file: {resolved_path}")
        
        try:
            with open(resolved_path, 'r') as file:
                for line in file:
                    # Extract the date from the ADM file header
                    if "AdminLog started on" in line:
                        match_date = re.search(r'AdminLog started on (\d{4}-\d{2}-\d{2})', line)
                        if match_date:
                            current_date = datetime.strptime(match_date.group(1), '%Y-%m-%d').date()
                            logger.debug(f"ADM log date: {current_date}")
                    # Extract player positions
                    match = re.search(r'Player "(.*?)" \(id=.*? pos=<(\d+\.\d+), (\d+\.\d+), \d+\.\d+>', line)
                    if match and current_date:
                        time_part = line.split('|')[0].strip()
                        timestamp = datetime.combine(current_date, datetime.strptime(time_part, '%H:%M:%S').time())
                        player_name = match.group(1)  # Extract player name
                        pos = (float(match.group(2)), float(match.group(3)))  # Ignore z-coordinate
                        player_positions.append((timestamp, pos, player_name))
                    # Extract login events
                    login_match = re.search(r'(\d{2}:\d{2}:\d{2}) \| Player "(.*?)"\(id=.*?\) is connected', line)
                    if login_match and current_date:
                        login_time = datetime.combine(current_date, datetime.strptime(login_match.group(1), '%H:%M:%S').time())
                        player_name = login_match.group(2)
                        login_events.append((login_time, player_name))
                        
            logger.info(f"Parsed {len(player_positions)} player positions and {len(login_events)} login events from {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"Error parsing ADM file {resolved_path}: {str(e)}")
            
        return player_positions, login_events

    def parse_rpt_file(self, file_path: str) -> List[Tuple[datetime, Tuple[float, float], str]]:
        """
        Parses an RPT log file to extract loot spawn events.

        Args:
            file_path: The path to the RPT log file.

        Returns:
            A list of tuples with loot spawn events in the format (timestamp, position, loot_item).
        """
        loot_spawns = []
        current_date = None
        
        # Resolve the path to ensure it's absolute  
        resolved_path = self.resolve_path(file_path)
        logger.debug(f"Parsing RPT file: {resolved_path}")
        
        try:
            with open(resolved_path, 'r') as file:
                for line in file:
                    # Extract the date from the RPT file header
                    if "Current time:" in line:
                        match_date = re.search(r'Current time:\s+(\d{4}/\d{2}/\d{2})', line)
                        if match_date:
                            current_date = datetime.strptime(match_date.group(1), '%Y/%m/%d').date()
                            logger.debug(f"RPT log date: {current_date}")
                    # Extract loot spawns
                    match = re.search(r'(\d{1,2}:\d{2}:\d{2}\.\d{3})\s+Adding (.*?) at \[(\d+),(\d+)\]', line)
                    if match and current_date:
                        time_part = match.group(1).split('.')[0]  # Strip milliseconds for consistency
                        timestamp = datetime.combine(current_date, datetime.strptime(time_part, '%H:%M:%S').time())
                        loot_item = match.group(2)  # Extract loot item
                        pos = (float(match.group(3)), float(match.group(4)))
                        loot_spawns.append((timestamp, pos, loot_item))
                        
            logger.info(f"Parsed {len(loot_spawns)} loot spawn events from {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"Error parsing RPT file {resolved_path}: {str(e)}")
            
        return loot_spawns

    def calculate_distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """
        Calculates the 2D Euclidean distance between two positions.

        Args:
            pos1: The first position as a tuple (x, y).
            pos2: The second position as a tuple (x, y).

        Returns:
            The Euclidean distance between the two positions.
        """
        # Simplify to 2D distance calculation
        return sqrt((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2)

    def detect_duplication(self, adm_pattern: str, rpt_pattern: str, 
                          proximity_threshold: float = None,
                          time_threshold: timedelta = None,
                          login_threshold: timedelta = None, 
                          login_count_threshold: int = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Detects suspicious duplication activities based on ADM and RPT logs.
        
        Args:
            adm_pattern: File pattern for ADM log files
            rpt_pattern: File pattern for RPT log files
            proximity_threshold: Distance threshold in meters
            time_threshold: Time window for considering events related
            login_threshold: Time window for suspicious login clusters
            login_count_threshold: Number of logins to consider suspicious
            
        Returns:
            Tuple containing lists of suspicious activities and suspicious logins
        """
        # Use provided values or fall back to instance defaults
        proximity_threshold = proximity_threshold or self.proximity_threshold
        time_threshold = time_threshold or self.time_threshold
        login_threshold = login_threshold or self.login_threshold
        login_count_threshold = login_count_threshold or self.login_count_threshold
        
        suspicious_activities = []
        suspicious_logins_list = []
        time_threshold_seconds = time_threshold.total_seconds()
        login_threshold_seconds = login_threshold.total_seconds()

        # Get all matching ADM and RPT files using resolve_path
        adm_pattern_resolved = self.resolve_path(adm_pattern)
        rpt_pattern_resolved = self.resolve_path(rpt_pattern)
        
        adm_files = glob.glob(adm_pattern_resolved)
        rpt_files = glob.glob(rpt_pattern_resolved)
        
        if not adm_files:
            logger.warning(f"No ADM files found matching pattern: {adm_pattern}")
            return [], []
            
        if not rpt_files:
            logger.warning(f"No RPT files found matching pattern: {rpt_pattern}")
            return [], []
            
        logger.info(f"Processing {len(adm_files)} ADM files and {len(rpt_files)} RPT files")

        # Precompute loot spawns for all RPT files
        all_loot_spawns = []
        for rpt_file_path in rpt_files:
            all_loot_spawns.extend(self.parse_rpt_file(rpt_file_path))

        for adm_file_path in adm_files:
            player_positions, login_events = self.parse_adm_file(adm_file_path)

            # Identify players with suspicious logins
            suspicious_logins = {}
            for player_name in set(name for _, name in login_events):  # Process each player once
                player_logins = [time for time, name in login_events if name == player_name]
                player_logins.sort()  # Ensure logins are sorted by time
                
                if len(player_logins) < login_count_threshold:
                    continue

                clusters = []  # To store clusters of suspicious logins
                current_cluster = [player_logins[0]]  # Start with the first login

                for i in range(1, len(player_logins)):
                    if (player_logins[i] - player_logins[i - 1]).total_seconds() <= login_threshold_seconds:
                        current_cluster.append(player_logins[i])
                    else:
                        if len(current_cluster) >= login_count_threshold:
                            clusters.append(current_cluster)
                        current_cluster = [player_logins[i]]

                # Check the last cluster
                if len(current_cluster) >= login_count_threshold:
                    clusters.append(current_cluster)

                # Add clusters to suspicious logins
                if clusters:
                    suspicious_logins[player_name] = clusters
                    for cluster in clusters:
                        suspicious_logins_list.append({
                            "player_name": player_name,
                            "recent_logins": [time.strftime('%Y-%m-%d %H:%M:%S') for time in cluster]
                        })

            # Check loot spawns for players with suspicious logins
            for player_name, login_clusters in suspicious_logins.items():
                for loot_time, loot_pos, loot_item in all_loot_spawns:
                    # Ensure loot spawn occurs during or shortly after any suspicious login in any cluster
                    if any(abs((loot_time - login_time).total_seconds()) <= time_threshold_seconds 
                           for cluster in login_clusters for login_time in cluster):
                        relevant_positions = [
                            (player_time, player_pos) for player_time, player_pos, name in player_positions
                            if name == player_name and abs((loot_time - player_time).total_seconds()) <= time_threshold_seconds
                        ]
                        for player_time, player_pos in relevant_positions:
                            distance = self.calculate_distance(loot_pos, player_pos)
                            if distance <= proximity_threshold:
                                suspicious_activities.append({
                                    "adm_file": os.path.basename(adm_file_path),
                                    "loot_time": loot_time.strftime('%Y-%m-%d %H:%M:%S'),
                                    "loot_pos": loot_pos,
                                    "loot_item": loot_item,
                                    "player_time": player_time.strftime('%Y-%m-%d %H:%M:%S'),
                                    "player_pos": player_pos,
                                    "player_name": player_name,
                                    "recent_logins": len([login for cluster in login_clusters for login in cluster]),
                                    "distance": round(distance, 2)
                                })

        return suspicious_activities, suspicious_logins_list
        
    def run(self, adm_pattern: str = None, rpt_pattern: str = None,
           proximity_threshold: float = None, time_threshold: int = None,
           login_threshold: int = None, login_count_threshold: int = None) -> int:
        """
        Run the duping detector analysis.
        
        Args:
            adm_pattern: File pattern for ADM log files
            rpt_pattern: File pattern for RPT log files
            proximity_threshold: Distance threshold in meters
            time_threshold: Time window in seconds for considering events related
            login_threshold: Time window in seconds for suspicious login clusters
            login_count_threshold: Number of logins to consider suspicious
            
        Returns:
            Exit code (0 = success)
        """
        # Use provided values or fall back to default patterns from logs directory
        log_dir = self.log_dir
        adm_pattern = adm_pattern or os.path.join(log_dir, "*.ADM")
        rpt_pattern = rpt_pattern or os.path.join(log_dir, "*.RPT")
        
        # Convert time thresholds to timedelta if provided as integers
        time_td = timedelta(seconds=time_threshold) if time_threshold is not None else self.time_threshold
        login_td = timedelta(seconds=login_threshold) if login_threshold is not None else self.login_threshold
        
        logger.info(f"Running duping detection with:")
        logger.info(f"  ADM pattern: {adm_pattern}")
        logger.info(f"  RPT pattern: {rpt_pattern}")
        logger.info(f"  Proximity threshold: {proximity_threshold or self.proximity_threshold} meters")
        logger.info(f"  Time threshold: {time_td.total_seconds()} seconds")
        logger.info(f"  Login threshold: {login_td.total_seconds()} seconds")
        logger.info(f"  Login count threshold: {login_count_threshold or self.login_count_threshold}")
        
        suspicious_activities, suspicious_logins_list = self.detect_duplication(
            adm_pattern, rpt_pattern, 
            proximity_threshold, time_td, login_td, 
            login_count_threshold
        )
        
        # Generate timestamp for filenames and report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Write results to CSV files in the output directory
        activities_file = f"suspicious_activities_{timestamp}.csv"
        logins_file = f"suspicious_logins_{timestamp}.csv"
        
        # Use self.write_csv which handles output directory and headers
        if suspicious_activities:
            # Add timestamp information to the CSV data
            timestamp_header = {"Report Generated": current_timestamp}
            
            self.write_csv(
                [timestamp_header] + suspicious_activities,
                activities_file,
                ["Report Generated", "adm_file", "loot_time", "loot_pos", "loot_item", "player_time", "player_pos", 
                 "player_name", "recent_logins", "distance"]
            )
            logger.info(f"Suspicious duplication activities detected. Results saved to '{activities_file}' (timestamp: {current_timestamp})")
        else:
            logger.info("No suspicious activities detected.")
            # Create empty file anyway with timestamp
            timestamp_header = [{"Report Generated": current_timestamp}]
            self.write_csv(timestamp_header, activities_file, 
                          ["Report Generated", "adm_file", "loot_time", "loot_pos", "loot_item", "player_time", 
                           "player_pos", "player_name", "recent_logins", "distance"])
            logger.info(f"Empty activities file created at '{activities_file}' (timestamp: {current_timestamp})")

        if suspicious_logins_list:
            formatted_logins = []
            for login in suspicious_logins_list:
                formatted_logins.append({
                    "player_name": login["player_name"],
                    "recent_logins": ", ".join(login["recent_logins"])
                })
            
            # Add timestamp information to the CSV data
            timestamp_header = {"Report Generated": current_timestamp}
            
            self.write_csv([timestamp_header] + formatted_logins, logins_file, 
                          ["Report Generated", "player_name", "recent_logins"])
            logger.info(f"Suspicious logins detected. Results saved to '{logins_file}' (timestamp: {current_timestamp})")
        else:
            logger.info("No suspicious logins detected.")
            # Create empty file anyway with timestamp
            timestamp_header = [{"Report Generated": current_timestamp}]
            self.write_csv(timestamp_header, logins_file, ["Report Generated", "player_name", "recent_logins"])
            logger.info(f"Empty logins file created at '{logins_file}' (timestamp: {current_timestamp})")
            
        return 0


def main():
    """
    Main entry point for the duping detector command line tool.
    """
    parser = argparse.ArgumentParser(
        description="Detect suspicious duplication activities in DayZ server logs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--adm-file", 
        help="File or pattern for ADM files (e.g., '/path/to/*.ADM'). If not specified, uses *.ADM in the configured logs path."
    )
    parser.add_argument(
        "--rpt-file", 
        help="File or pattern for RPT files (e.g., '/path/to/*.RPT'). If not specified, uses *.RPT in the configured logs path."
    )
    parser.add_argument(
        "--proximity-threshold", 
        type=float, 
        help="Proximity threshold of spawned loot near the player in meters."
    )
    parser.add_argument(
        "--time-threshold", 
        type=int, 
        help="Time threshold of spawned loot near the Player in seconds."
    )
    parser.add_argument(
        "--login-threshold", 
        type=int, 
        help="Login threshold in seconds."
    )
    parser.add_argument(
        "--login-count-threshold", 
        type=int, 
        help="Login count threshold."
    )
    
    # Add standard arguments from DayZTool
    DayZTool.add_standard_arguments(parser)
    args = parser.parse_args()

    try:
        # Load configuration using the base class static method
        config = DupingDetector.load_config(args.profile)
        
        # Initialize detector
        detector = DupingDetector(config)
        
        # Run the analysis with command line arguments or defaults
        return detector.run(
            adm_pattern=args.adm_file,
            rpt_pattern=args.rpt_file,
            proximity_threshold=args.proximity_threshold,
            time_threshold=args.time_threshold,
            login_threshold=args.login_threshold,
            login_count_threshold=args.login_count_threshold
        )
            
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        import traceback
        logging.debug(traceback.format_exc())
        return 1
if __name__ == "__main__":
    exit(main())
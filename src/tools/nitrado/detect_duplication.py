import re
import glob
import argparse
from datetime import datetime, timedelta
from math import sqrt
import csv

def parse_adm_file(file_path):
    """Parses an ADM log file to extract player positions and login events.

    Args:
        file_path (str): The path to the ADM log file.

    Returns:
        tuple: A tuple containing:
            - player_positions (list): A list of tuples with player positions in the format (timestamp, position, player_name).
            - login_events (list): A list of tuples with login events in the format (timestamp, player_name).
    """
    player_positions = []
    login_events = []
    current_date = None
    with open(file_path, 'r') as file:
        for line in file:
            # Extract the date from the ADM file header
            if "AdminLog started on" in line:
                match_date = re.search(r'AdminLog started on (\d{4}-\d{2}-\d{2})', line)
                if match_date:
                    current_date = datetime.strptime(match_date.group(1), '%Y-%m-%d').date()
                    print(f"ADM log date: {current_date}")
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
        print(f"Number of Player positions: {len(player_positions)} File: {file_path}")
        print(f"Number of Login events: {len(login_events)} File: {file_path}")
    return player_positions, login_events

def parse_rpt_file(file_path):
    """Parses an RPT log file to extract loot spawn events.

    Args:
        file_path (str): The path to the RPT log file.

    Returns:
        list: A list of tuples with loot spawn events in the format (timestamp, position, loot_item).
    """
    loot_spawns = []
    current_date = None
    with open(file_path, 'r') as file:
        for line in file:
            # Extract the date from the RPT file header
            if "Current time:" in line:
                match_date = re.search(r'Current time:\s+(\d{4}/\d{2}/\d{2})', line)
                if match_date:
                    current_date = datetime.strptime(match_date.group(1), '%Y/%m/%d').date()
                    print(f"RPT log date: {current_date}")
            # Extract loot spawns
            match = re.search(r'(\d{1,2}:\d{2}:\d{2}\.\d{3})\s+Adding (.*?) at \[(\d+),(\d+)\]', line)
            if match and current_date:
                time_part = match.group(1).split('.')[0]  # Strip milliseconds for consistency
                timestamp = datetime.combine(current_date, datetime.strptime(time_part, '%H:%M:%S').time())
                loot_item = match.group(2)  # Extract loot item
                pos = (float(match.group(3)), float(match.group(4)))
                loot_spawns.append((timestamp, pos, loot_item))
        print(f"Number of Loot positions: {len(loot_spawns)} File: {file_path}")
    return loot_spawns

def calculate_distance(pos1, pos2):
    """Calculates the 2D Euclidean distance between two positions.

    Args:
        pos1 (tuple): The first position as a tuple (x, y).
        pos2 (tuple): The second position as a tuple (x, y).

    Returns:
        float: The Euclidean distance between the two positions.
    """
    # Simplify to 2D distance calculation
    return sqrt((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2)

# Detect suspicious duplication activity for multiple files
def detect_duplication(adm_pattern, rpt_pattern, proximity_threshold=50, time_threshold=timedelta(seconds=10), login_threshold=timedelta(seconds=15), login_count_threshold=3):
    """Detects suspicious duplication activities based on ADM and RPT logs."""
    suspicious_activities = []
    suspicious_logins_list = []  # To store suspicious logins for CSV output
    time_threshold_seconds = time_threshold.total_seconds()
    login_threshold_seconds = login_threshold.total_seconds()

    # Get all matching ADM and RPT files
    adm_files = glob.glob(adm_pattern)
    rpt_files = glob.glob(rpt_pattern)

    # Precompute loot spawns for all RPT files
    all_loot_spawns = []
    for rpt_file_path in rpt_files:
        all_loot_spawns.extend(parse_rpt_file(rpt_file_path))

    for adm_file_path in adm_files:
        player_positions, login_events = parse_adm_file(adm_file_path)

        # Identify players with suspicious logins
        suspicious_logins = {}
        for player_name in set(name for _, name in login_events):  # Process each player once
            player_logins = [time for time, name in login_events if name == player_name]
            player_logins.sort()  # Ensure logins are sorted by time

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
        for player_name, login_times in suspicious_logins.items():
            for loot_time, loot_pos, loot_item in all_loot_spawns:
                if any(abs((loot_time - login_time).total_seconds()) <= time_threshold_seconds for login_time in login_times):
                    relevant_positions = [
                        (player_time, player_pos) for player_time, player_pos, name in player_positions
                        if name == player_name and abs((loot_time - player_time).total_seconds()) <= time_threshold_seconds
                    ]
                    for player_time, player_pos in relevant_positions:
                        distance = calculate_distance(loot_pos, player_pos)
                        if distance <= proximity_threshold:
                            suspicious_activities.append({
                                "adm_file": adm_file_path,
                                "loot_time": loot_time.strftime('%Y-%m-%d %H:%M:%S'),
                                "loot_pos": loot_pos,
                                "loot_item": loot_item,
                                "player_time": player_time.strftime('%Y-%m-%d %H:%M:%S'),
                                "player_pos": player_pos,
                                "player_name": player_name,
                                "recent_logins": len(login_times)
                            })

    return suspicious_activities, suspicious_logins_list

def write_csv(file_name, fieldnames, data):
    """Writes data to a CSV file.

    Args:
        file_name (str): The name of the CSV file.
        fieldnames (list): The list of field names for the CSV.
        data (list): The list of dictionaries to write to the CSV.
    """
    with open(file_name, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

# Main function
if __name__ == "__main__":
    """Main function to parse arguments, detect suspicious activities, and save results to CSV files."""
    parser = argparse.ArgumentParser(description="Detect suspicious duplication activities in DayZ server logs.")
    parser.add_argument("--adm-file", required=True, help="File or pattern for ADM files (e.g., '/path/to/*.ADM').")
    parser.add_argument("--rpt-file", required=True, help="File or pattern for RPT files (e.g., '/path/to/*.RPT').")
    parser.add_argument("--proximity-threshold", type=float, default=10, help="Proximity threshold of spwaned loot near the player in meters (default: 10).")
    parser.add_argument("--time-threshold", type=int, default=300, help="Time threshold of spawned loot near the Player in seconds (default: 300).")
    parser.add_argument("--login-threshold", type=int, default=300, help="Login threshold in seconds (default: 300).")
    parser.add_argument("--login-count-threshold", type=int, default=3, help="Login count threshold (default: 3).")

    args = parser.parse_args()

    adm_pattern = args.adm_pattern
    rpt_pattern = args.rpt_pattern
    proximity_threshold = args.proximity_threshold
    time_threshold = timedelta(seconds=args.time_threshold)
    login_threshold = timedelta(seconds=args.login_threshold)
    login_count_threshold = args.login_count_threshold

    suspicious_activities, suspicious_logins_list = detect_duplication(  # Ensure correct variable name is used
        adm_pattern, rpt_pattern, proximity_threshold, time_threshold, login_threshold, login_count_threshold
    )

    # Write suspicious activities to a CSV file
    write_csv("suspicious_activities.csv", 
              ["adm_file", "loot_time", "loot_pos", "loot_item", "player_time", "player_pos", "player_name", "recent_logins"], 
              suspicious_activities)

    # Write suspicious logins to a CSV file
    write_csv("suspicious_logins.csv", 
              ["player_name", "recent_logins"], 
              [{"player_name": login["player_name"], "recent_logins": ", ".join(login["recent_logins"])} for login in suspicious_logins_list])

    if suspicious_activities:
        print("Suspicious duplication activities detected. Results saved to 'suspicious_activities.csv'.")
    else:
        print("No suspicious activities detected.")

    if suspicious_logins_list:  # Ensure correct variable name is used
        print("Suspicious logins detected. Results saved to 'suspicious_logins.csv'.")
    else:
        print("No suspicious logins detected.")
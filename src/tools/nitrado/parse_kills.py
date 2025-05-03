import argparse
from datetime import datetime
import os

def parse_log(file_path, start_datetime=None, end_datetime=None):
    kills = {}
    log_date = None

    with open(file_path, 'r') as file:
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

                # Extract killer's name
                killer = line.split('killed by Player "')[1].split('"')[0]
                kills[killer] = kills.get(killer, 0) + 1

    # Sort kills by count in descending order
    sorted_kills = sorted(kills.items(), key=lambda x: x[1], reverse=True)
    return sorted_kills

def main():
    parser = argparse.ArgumentParser(description="Parse DayZ log files in a directory and count kills per player.")
    parser.add_argument("log_dir", help="Path to the directory containing .ADM log files.")
    parser.add_argument("--start", help="Start date and time in YYYY-MM-DD HH:MM:SS format.", type=str)
    parser.add_argument("--end", help="End date and time in YYYY-MM-DD HH:MM:SS format.", type=str)
    args = parser.parse_args()

    # Parse start and end datetimes
    start_datetime = datetime.strptime(args.start, "%Y-%m-%d %H:%M:%S") if args.start else None
    end_datetime = datetime.strptime(args.end, "%Y-%m-%d %H:%M:%S") if args.end else None

    # Collect all .ADM files in the directory
    if not os.path.isdir(args.log_dir):
        print("Error: The specified path is not a directory.")
        return

    adm_files = [os.path.join(args.log_dir, f) for f in os.listdir(args.log_dir) if f.lower().endswith(".adm")]
    if not adm_files:
        print("Error: No .ADM files found in the specified directory.")
        return

    # Aggregate kills across all .ADM files
    total_kills = {}
    for file_path in adm_files:
        kills = parse_log(file_path, start_datetime, end_datetime)
        for player, count in kills:
            total_kills[player] = total_kills.get(player, 0) + count

    # Sort and print results
    sorted_kills = sorted(total_kills.items(), key=lambda x: x[1], reverse=True)
    print("Kills per player (ranked):")
    for rank, (player, count) in enumerate(sorted_kills, start=1):
        print(f"{rank}. {player}: {count} kills")

if __name__ == "__main__":
    main()

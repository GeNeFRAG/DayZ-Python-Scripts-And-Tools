import re
import math
from typing import List, Tuple, Optional
import glob
import os
from datetime import datetime
import csv

def extract_info(line: str, file_date: str) -> Tuple[Optional[str], Optional[str], Optional[tuple], Optional[str]]:
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
        action_match = re.search(r'>\s*(.*?)(?:\s*\(|\[|$)', line)
        action = action_match.group(1).strip() if action_match else ""
        
        # Remove trailing ')' if present
        if action.endswith(')'):
            action = action[:-1].strip()
        
        # Remove leading ')' if present
        if action.startswith(')'):
            action = action[1:].strip()
        
        return time_str, player_name, position, action
    except Exception as e:
        print(f"Error extracting info: {e}")
        return None, None, None, None

def extract_date_from_file(file_path: str) -> str:
    """
    Extract date from the top entry of the file
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
        print(f"Error extracting date from file {file_path}: {e}")
    return "Unknown date"

def calculate_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """
    Calculate 2D distance between two points
    """
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

def find_nearby_positions(file_pattern: str, target_x: float, target_y: float, radius: float = 100.0) -> List[tuple]:
    """
    Find positions within specified radius of target coordinates in multiple files
    """
    nearby_positions = []
    
    matching_files = glob.glob(file_pattern)
    
    for file_path in matching_files:
        try:
            file_date = extract_date_from_file(file_path)
            
            with open(file_path, 'r', encoding='utf-8') as file:
                for line_num, line in enumerate(file, 1):
                    time_str, player_name, coords, action = extract_info(line, file_date)
                    
                    if coords:
                        x, y, z = coords
                        distance = calculate_distance(target_x, target_y, x, y)
                        
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
            print(f"Error processing file {file_path}: {str(e)}")
            
    return sorted(nearby_positions, key=lambda x: x[7])  # Sort by distance

def save_to_csv(results: List[tuple], output_file: str):
    """
    Save results to CSV file
    
    Args:
        results: List of result tuples
        output_file: Name of the CSV file to create
    """
    headers = ['File', 'Line', 'Date', 'Time', 'Player', 'X', 'Y', 'Z', 'Action', 'Distance']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        
        for filename, line_num, file_date, time_str, player_name, coords, action, distance in results:
            writer.writerow([
                filename,
                line_num,
                file_date,
                time_str,
                player_name,
                f"{coords[0]:.1f}",
                f"{coords[1]:.1f}",
                f"{coords[2]:.1f}",
                action if action else "",
                f"{distance:.2f}"
            ])

def find_positions_by_players(file_pattern: str, player_names: List[str]) -> List[tuple]:
    """
    Find positions and actions for specific players in multiple files
    
    Args:
        file_pattern: File pattern to search (e.g. "*.ADM")
        player_names: List of player names to filter by
    
    Returns:
        List of tuples containing file details and player actions
    """
    player_positions = []
    
    matching_files = glob.glob(file_pattern)
    
    for file_path in matching_files:
        try:
            file_date = extract_date_from_file(file_path)
            
            with open(file_path, 'r', encoding='utf-8') as file:
                for line_num, line in enumerate(file, 1):
                    time_str, player_name, coords, action = extract_info(line, file_date)
                    
                    if player_name and any(player_name_filter.lower() in player_name.lower() for player_name_filter in player_names):
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
            print(f"Error processing file {file_path}: {str(e)}")
            
    return player_positions

def save_player_positions_to_csv(results: List[tuple], output_file: str):
    """
    Save player positions to CSV file
    
    Args:
        results: List of result tuples
        output_file: Name of the CSV file to create
    """
    headers = ['File', 'Line', 'Date', 'Time', 'Player', 'X', 'Y', 'Z', 'Action']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        
        for filename, line_num, file_date, time_str, player_name, coords, action in results:
            writer.writerow([
                filename,
                line_num,
                file_date,
                time_str,
                player_name,
                f"{coords[0]:.1f}" if coords else "",
                f"{coords[1]:.1f}" if coords else "",
                f"{coords[2]:.1f}" if coords else "",
                action if action else ""
            ])

def filter_by_date_range(results: List[tuple], start_date: Optional[str], end_date: Optional[str]) -> List[tuple]:
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

def sort_by_time(results: List[tuple]) -> List[tuple]:
    """
    Sort results by time
    
    Args:
        results: List of result tuples
    
    Returns:
        Sorted list of result tuples
    """
    return sorted(results, key=lambda x: (x[2], x[3]))  # Sort by date and time

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Find nearby player positions and actions in files')
    parser.add_argument('file_pattern', help='File pattern to search (e.g. "*.ADM")')
    parser.add_argument('--target_x', type=float, help='Target X coordinate')
    parser.add_argument('--target_y', type=float, help='Target Y coordinate')
    parser.add_argument('--radius', type=float, default=100.0, help='Search radius in meters')
    parser.add_argument('--output', default='results.csv', help='Output CSV file name (default: results.csv)')
    parser.add_argument('--player', nargs='+', help='Player names to filter by (optional)')
    parser.add_argument('--start-date', help='Start date in YYYY-MM-DD format (optional)')
    parser.add_argument('--end-date', help='End date in YYYY-MM-DD format (optional)')
    
    args = parser.parse_args()
    
    if args.player and (args.target_x is None or args.target_y is None):
        results = find_positions_by_players(args.file_pattern, args.player)
        if not results:
            print(f"No positions found for players: {', '.join(args.player)}.")
            return
        results = filter_by_date_range(results, args.start_date, args.end_date)
        results = sort_by_time(results)
        save_player_positions_to_csv(results, args.output)
        print(f"\nFound {len(results)} positions for players: {', '.join(args.player)}.")
    else:
        results = find_nearby_positions(args.file_pattern, args.target_x, args.target_y, args.radius)
        if not results:
            print("No positions found within specified radius.")
            return
        results = filter_by_date_range(results, args.start_date, args.end_date)
        results = sort_by_time(results)
        save_to_csv(results, args.output)
        print(f"\nFound {len(results)} positions within {args.radius}m radius.")
    
    print(f"Results have been saved to: {args.output}")

if __name__ == "__main__":
    main()


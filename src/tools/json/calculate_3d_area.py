import json
import argparse

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Calculate 3D area from JSON file.')
parser.add_argument('json_file', type=str, help='Path to the JSON file containing object positions')
args = parser.parse_args()

# Load positions from the JSON file
with open(args.json_file, 'r') as file:
    data = json.load(file)
    positions = [obj['pos'] for obj in data['Objects']]  # Extract positions from the JSON structure

# Initialize variables for calculations
min_x, max_x = float('inf'), float('-inf')
min_y, max_y = float('inf'), float('-inf')
min_z, max_z = float('inf'), float('-inf')

for x, y, z in positions:
    min_x, max_x = min(min_x, x), max(max_x, x)
    min_y, max_y = min(min_y, y), max(max_y, y)
    min_z, max_z = min(min_z, z), max(max_z, z)

corners = [
    [min_x, min_y, min_z],
    [min_x, min_y, max_z],
    [max_x, min_y, min_z],
    [max_x, min_y, max_z]
]

approximate_height = max_y - min_y
lowest_point = [min_x, min_y, min_z]

# Calculate the lowest point in the middle
middle_x = (min_x + max_x) / 2
middle_z = (min_z + max_z) / 2
lowest_middle_point = [middle_x, min_y, middle_z]

# Calculate dimensions in meters
dimension_x = max_x - min_x
dimension_y = max_y - min_y
dimension_z = max_z - min_z

# Print results
print("\nLowest Middle Point Visualization:")
print("════════════════════════════════════════════════")
print(f"Coordinates: [{middle_x:.2f}, {min_y:.2f}, {middle_z:.2f}]")
print("")
print("          Top View")
print("    ┌───────────────┐")
print("    │               │")
print("    │       ◉       │    ◉ = Middle Point")
print("    │               │")
print("    └───────────────┘")
print("")

# Replace the last few print statements with this enhanced visualization
print("\nEnhanced 3D Visualization:")
print(f"    {min_x:.2f}/{min_z:.2f}      {min_x:.2f}/{max_z:.2f}")
print(f"    +---------------------+ y={dimension_y:.2f}m")
print("   /|                    /|")
print("  / |                   / |")
print(" /  |                  /  |")
print("+   |                 +   |")
print("|   |                 |   |")
print("|   |                 |   |")
print("|   +-----------------|---+ ")
print("|  /                  |  /")
print("| /                   | /")
print("|/                    |/")
print("+---------------------+")
print(f"{max_x:.2f}/{min_z:.2f}      {max_x:.2f}/{max_z:.2f}\n")


# Add dimension labels
print("Box Dimensions:")
print(f"Length (X): {dimension_x:.2f}m")
print(f"Height (Y): {dimension_y:.2f}m")
print(f"Width (Z): {dimension_z:.2f}m")
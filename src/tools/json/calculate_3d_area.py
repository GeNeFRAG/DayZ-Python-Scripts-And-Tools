import json
import argparse
import os
from math import ceil
from itertools import product
from typing import List, Tuple

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

def find_optimal_box_size(dimension_x: float, dimension_y: float, dimension_z: float, max_box_size: int) -> List[int]:
    optimal_box_size = [max_box_size, max_box_size, max_box_size]
    min_boxes = float('inf')

    for box_width, box_height, box_length in product(range(1, max_box_size + 1), repeat=3):
        num_boxes_x = ceil(dimension_x / box_width)
        num_boxes_y = ceil(dimension_y / box_height)
        num_boxes_z = ceil(dimension_z / box_length)
        total_boxes = num_boxes_x * num_boxes_y * num_boxes_z

        if total_boxes < min_boxes:
            min_boxes = total_boxes
            optimal_box_size = [box_width, box_height, box_length]

    return optimal_box_size

# Find the optimal box size
max_box_size = 50  # Maximum box size to consider
optimal_box_size = find_optimal_box_size(dimension_x, dimension_y, dimension_z, max_box_size)
box_width, box_height, box_length = optimal_box_size

# Calculate the number of boxes needed along each dimension with the optimal size
num_boxes_x = ceil(dimension_x / box_width)
num_boxes_y = ceil(dimension_y / box_height)
num_boxes_z = ceil(dimension_z / box_length)

# Generate box positions with the optimal size
boxes = [
    [
        [box_width, box_height, box_length],
        [0, 0, 0],
        [min_x + i * box_width, min_y + j * box_height, min_z + k * box_length]
    ]
    for i in range(num_boxes_x)
    for j in range(num_boxes_y)
    for k in range(num_boxes_z)
]

# Create JSON structure
output_data = {
    "areaName": "Generated_3D_Area",
    "PRABoxes": boxes,
    "safePositions3D": []  # Add safe positions if needed
}

# Output to JSON file
output_file = os.path.join(os.path.dirname(args.json_file), "output_boxes.json")
with open(output_file, 'w') as json_file:
    json.dump(output_data, json_file, indent=2)

print(f"Output written to {output_file}")

# Print box placement summary
print("\nOptimal Box Placement Summary:")
print(f"Optimal Box Dimensions: {box_width}x{box_height}x{box_length}")
print(f"Number of boxes along X: {num_boxes_x}")
print(f"Number of boxes along Y: {num_boxes_y}")
print(f"Number of boxes along Z: {num_boxes_z}")
print(f"Total boxes: {len(boxes)}")

# Optionally, print the positions of the boxes
print("\nBox Positions:")
for box in boxes:
    print(f"Box at ({box[2][0]:.2f}, {box[2][1]:.2f}, {box[2][2]:.2f}) "
          f"with dimensions ({box[0][0]}x{box[0][1]}x{box[0][2]})")
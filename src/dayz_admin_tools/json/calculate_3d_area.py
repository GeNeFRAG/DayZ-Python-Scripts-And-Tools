"""
Calculate 3D Area Tool

Calculate 3D areas from DayZ JSON object files.
Processes a JSON file containing object positions and calculates the area,
volume, and bounding box coordinates.
"""

import json
import argparse
import os
from math import ceil
from itertools import product
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..base import JSONTool, logger


__all__ = ['Calculate3DArea', 'main']


class Calculate3DArea(JSONTool):
    """
    Calculate 3D areas from DayZ JSON object files.
    
    This tool analyzes the positions of objects in a JSON file to calculate
    the volume and dimensions of the area these objects occupy, and generates
    box placements for the area.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the Calculate3DArea tool.
        
        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        # Note: directories are already initialized in the parent class
        # and self.output_dir is already set
    
    def run(self, json_file: str, max_box_size: int = 50) -> Dict[str, Any]:
        """
        Run the area calculation tool.
        
        Args:
            json_file: Path to the JSON file containing object positions
            max_box_size: Maximum box size to consider for optimization
            
        Returns:
            Dictionary with area calculation results
        """
        # Process the file and calculate areas
        result = self.calculate_area(json_file, max_box_size)
        return result
        
    def calculate_area(self, json_file: str, max_box_size: int = 50) -> Dict[str, Any]:
        """
        Calculate 3D area from a JSON file of object positions.
        
        Args:
            json_file: Path to the JSON file containing object positions
            max_box_size: Maximum box size to consider for optimization
            
        Returns:
            Dictionary with area calculation results
        """
        logger.info(f"Processing JSON file: {json_file}")
        
        # Load positions from the JSON file
        try:
            data = self.read_json(json_file)
            
            if 'Objects' not in data:
                logger.error(f"Invalid JSON format: 'Objects' key not found in {json_file}")
                return {'error': 'Invalid JSON format'}
                
            positions = [obj['pos'] for obj in data['Objects'] if 'pos' in obj]
            
            if not positions:
                logger.warning(f"No position data found in {json_file}")
                return {'error': 'No position data found'}
                
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error reading JSON file: {e}")
            return {'error': str(e)}

        # Initialize variables for calculations
        min_x, max_x = float('inf'), float('-inf')
        min_y, max_y = float('inf'), float('-inf')
        min_z, max_z = float('inf'), float('-inf')

        # Find the minimum and maximum coordinates
        for x, y, z in positions:
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
            min_z, max_z = min(min_z, z), max(max_z, z)

        # Calculate dimensions and metrics
        dimension_x = max_x - min_x
        dimension_y = max_y - min_y
        dimension_z = max_z - min_z
        
        area = dimension_x * dimension_z
        volume = area * dimension_y
        
        # Calculate the lowest point in the middle
        middle_x = (min_x + max_x) / 2
        middle_z = (min_z + max_z) / 2

        # Find optimal box size and placements
        optimal_box_size = self.find_optimal_box_size(dimension_x, dimension_y, dimension_z, max_box_size)
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

        # Create output data with timestamp
        output_data = {
            "areaName": "Generated_3D_Area",
            "PRABoxes": boxes,
            "safePositions3D": []  # Add safe positions if needed
        }

        # Save to output file in the configured output directory using generate_timestamped_filename
        output_filename = self.generate_timestamped_filename(
            f"{Path(json_file).stem}", "json", suffix="boxes"
        )
        output_file = os.path.join(self.output_dir, output_filename)
        
        # Ensure the output directory exists
        self.ensure_dir(self.output_dir)
            
        self.write_json(output_data, output_file)
        
        # Log calculation results
        logger.info("\nLowest Middle Point Visualization:")
        logger.info("════════════════════════════════════════════════")
        logger.info(f"Coordinates: [{middle_x:.2f}, {min_y:.2f}, {middle_z:.2f}]")
        logger.info("")
        logger.info("          Top View")
        logger.info("    ┌───────────────┐")
        logger.info("    │               │")
        logger.info("    │       ◉       │    ◉ = Middle Point")
        logger.info("    │               │")
        logger.info("    └───────────────┘")
        logger.info("")

        logger.info("\nEnhanced 3D Visualization:")
        logger.info(f"    {min_x:.2f}/{min_z:.2f}      {min_x:.2f}/{max_z:.2f}")
        logger.info(f"    +---------------------+ y={dimension_y:.2f}m")
        logger.info("   /|                    /|")
        logger.info("  / |                   / |")
        logger.info(" /  |                  /  |")
        logger.info("+   |                 +   |")
        logger.info("|   |                 |   |")
        logger.info("|   |                 |   |")
        logger.info("|   +-----------------|---+ ")
        logger.info("|  /                  |  /")
        logger.info("| /                   | /")
        logger.info("|/                    |/")
        logger.info("+---------------------+")
        logger.info(f"{max_x:.2f}/{min_z:.2f}      {max_x:.2f}/{max_z:.2f}\n")

        logger.info("Box Dimensions:")
        logger.info(f"Length (X): {dimension_x:.2f}m")
        logger.info(f"Height (Y): {dimension_y:.2f}m")
        logger.info(f"Width (Z): {dimension_z:.2f}m")
        
        logger.info("\nOptimal Box Placement Summary:")
        logger.info(f"Optimal Box Dimensions: {box_width}x{box_height}x{box_length}")
        logger.info(f"Number of boxes along X: {num_boxes_x}")
        logger.info(f"Number of boxes along Y: {num_boxes_y}")
        logger.info(f"Number of boxes along Z: {num_boxes_z}")
        logger.info(f"Total boxes: {len(boxes)}")
        logger.info(f"Output written to {output_file}")

        # Return a comprehensive result dictionary
        return {
            'timestamp': self.get_timestamp_str(),
            'dimensions': {
                'x': round(dimension_x, 2),
                'y': round(dimension_y, 2),
                'z': round(dimension_z, 2)
            },
            'area': round(area, 2),
            'volume': round(volume, 2),
            'bounds': {
                'min': [round(min_x, 2), round(min_y, 2), round(min_z, 2)],
                'max': [round(max_x, 2), round(max_y, 2), round(max_z, 2)]
            },
            'lowest_middle_point': [round(middle_x, 2), round(min_y, 2), round(middle_z, 2)],
            'optimal_box': {
                'dimensions': optimal_box_size,
                'count_x': num_boxes_x,
                'count_y': num_boxes_y, 
                'count_z': num_boxes_z,
                'total': len(boxes)
            },
            'output_file': output_file
        }

    def find_optimal_box_size(self, dimension_x: float, dimension_y: float, dimension_z: float, max_box_size: int) -> List[int]:
        """
        Find the optimal box size for filling the given volume.
        
        Args:
            dimension_x: X dimension of the area
            dimension_y: Y dimension of the area
            dimension_z: Z dimension of the area
            max_box_size: Maximum box size to consider
            
        Returns:
            List containing optimal [width, height, length]
        """
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
    
# Standard arguments are now added from the base DayZTool class

def main():
    """
    Main function to run the 3D area calculator as a command-line tool.
    """
    parser = argparse.ArgumentParser(
        description='Calculate 3D area from a JSON file of DayZ object positions and generate optimal box placements.'
    )
    parser.add_argument('json_file', type=str, 
                      help='Path to the JSON file containing object positions')
    parser.add_argument('--max-box-size', type=int, default=50,
                      help='Maximum box size to consider for optimization (default: 50)')
    
    # Add standard arguments from base class
    from ..base import DayZTool
    DayZTool.add_standard_arguments(parser)
    args = parser.parse_args()
    
    # Load configuration
    config = DayZTool.load_config(args.profile)
    
    # Create and run the tool
    calculator = Calculate3DArea(config)
    results = calculator.run(args.json_file, args.max_box_size)
    
    # Log a summary if requested
    if args.console and 'error' not in results:
        logger.info("\nSummary:")
        logger.info(f"Length (X): {results['dimensions']['x']}m")
        logger.info(f"Height (Y): {results['dimensions']['y']}m")
        logger.info(f"Width (Z): {results['dimensions']['z']}m")
        logger.info(f"Volume: {results['volume']} cubic units")
        logger.info(f"Optimal Box Size: {results['optimal_box']['dimensions']}")
        logger.info(f"Total Boxes: {results['optimal_box']['total']}")
        logger.info(f"Output file: {results['output_file']}")
        logger.info(f"Output directory: {calculator.output_dir}")
    elif args.console and 'error' in results:
        logger.error(f"Error: {results['error']}")

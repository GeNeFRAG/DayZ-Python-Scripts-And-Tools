"""
Generate Spawner Entries Tool

Create DayZ object spawner JSON entries from command line inputs.
Takes item names, quantities, and positions to generate formatted JSON entries.
"""

import sys
import xml.etree.ElementTree as ET
import json
import argparse
import os
from typing import Dict, Any, Optional, List, Tuple

# Import base class and logger
from ..base import JSONTool, logger

__all__ = ['GenerateSpawnerEntries', 'main']

# Configuration loading is now handled by DayZTool.load_config()


class GenerateSpawnerEntries(JSONTool):
    """
    Generate DayZ object spawner JSON entries from command line inputs.
    
    This tool creates correctly formatted JSON entries for object spawners
    in DayZ, verifying that the items exist in the types.xml file.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the GenerateSpawnerEntries tool.
        
        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        
        # Item names from types.xml
        self.valid_items = set()
    
    def run(self, types_xml_path: str, items: List[Tuple[str, int, List[float]]],
            ypr: str = "0 0 0", scale: float = 1.0, 
            enable_ce_persistence: int = 0, custom_string: str = "",
            output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the tool to generate object spawner entries.
        
        Args:
            types_xml_path: Path to the types.xml file
            items: List of tuples with (item_name, amount, [x, y, z])
            ypr: Yaw, pitch, roll as a string
            scale: Scale factor
            enable_ce_persistence: CE persistence flag (0 or 1)
            custom_string: Custom string for the objects
            output_file: Optional path for saving the output. If None, a default filename
                        will be used in the standard output directory.
            
        Returns:
            Dictionary with the generated entries
        """
        return self.generate_entries(
            types_xml_path, items, ypr, scale, enable_ce_persistence, 
            custom_string, output_file
        )
    
    def parse_item_amount_pos(self, s: str) -> Tuple[str, int, List[float]]:
        """
        Parse a string in the format <item>:<amount>:<x>:<y>:<z>.
        
        Args:
            s: String containing item, amount, and position data
            
        Returns:
            Tuple of (item_name, amount, [x, y, z])
            
        Raises:
            ValueError: If the format is invalid
        """
        parts = s.split(':')
        if len(parts) != 5:
            raise ValueError(f"Invalid item spec '{s}', must be <item>:<amount>:<x>:<y>:<z>")
        
        name, amount, x, y, z = parts
        
        if not amount.isdigit() or int(amount) < 1:
            raise ValueError(f"Invalid amount '{amount}' for item '{name}'")
        
        try:
            x, y, z = float(x), float(y), float(z)
        except ValueError:
            raise ValueError(f"Invalid coordinates for item '{name}'")
            
        return (name, int(amount), [x, y, z])
    
    def load_types_xml(self, types_xml_path: str) -> None:
        """
        Load and validate valid item names from types.xml.
        
        Args:
            types_xml_path: Path to the types.xml file
        """
        logger.info(f"Loading types.xml from {types_xml_path}")
        
        try:
            tree = ET.parse(types_xml_path)
            root = tree.getroot()
            
            for type_elem in root.findall('type'):
                name = type_elem.get('name')
                if name:
                    self.valid_items.add(name)
            
            logger.info(f"Loaded {len(self.valid_items)} valid items from types.xml")
        
        except (ET.ParseError, FileNotFoundError) as e:
            logger.error(f"Error loading types.xml: {e}")
            raise
    
    def generate_entries(self, types_xml_path: str, items: List[Tuple[str, int, List[float]]],
                        ypr: str = "0 0 0", scale: float = 1.0, 
                        enable_ce_persistence: int = 0, custom_string: str = "",
                        output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate object spawner entries from the provided items.
        
        Args:
            types_xml_path: Path to the types.xml file
            items: List of tuples with (item_name, amount, [x, y, z])
            ypr: Yaw, pitch, roll as a string
            scale: Scale factor
            enable_ce_persistence: CE persistence flag (0 or 1)
            custom_string: Custom string for the objects
            output_file: Optional path for saving the output. If None, a default filename
                        will be used in the standard output directory.
            
        Returns:
            Dictionary with the generated entries
        """
        # Load valid items from types.xml
        self.load_types_xml(types_xml_path)
        
        # Prepare result structure
        result = {"Objects": []}
        
        # Process each item
        for name, amount, pos in items:
            if name not in self.valid_items:
                logger.warning(f"Item '{name}' not found in types.xml - adding anyway")
            
            obj = {
                "name": name,
                "pos": pos,
                "ypr": ypr,
                "scale": scale,
                "enableCEPersistence": enable_ce_persistence,
            }
            
            if custom_string:
                obj["customString"] = custom_string
                
            # Add the item multiple times based on amount
            for _ in range(amount):
                result["Objects"].append(obj.copy())
        
        logger.info(f"Generated {len(result['Objects'])} object entries")
        
        # Save to file
        if output_file:
            # If an absolute path is provided, use it as is
            if os.path.isabs(output_file):
                target_file = output_file
            else:
                # Otherwise, put it in the output directory
                target_file = os.path.join(self.output_dir, output_file)
        else:
            # Generate default filename if none provided
            default_filename = f"spawner_entries_{len(result['Objects'])}_items.json"
            target_file = os.path.join(self.output_dir, default_filename)
        
        # Ensure output directory exists
        self.ensure_dir(os.path.dirname(target_file))
            
        # Write the file
        self.write_json(result, target_file, indent=2)
        logger.info(f"Output written to: {target_file}")
        
        # Add the output file path to the result
        result["output_file"] = target_file
        
        return result


def parse_item_amount_pos(s: str) -> Tuple[str, int, List[float]]:
    """
    Parse a string in the format <item>:<amount>:<x>:<y>:<z>.
    
    Args:
        s: String containing item, amount, and position data
        
    Returns:
        Tuple of (item_name, amount, [x, y, z])
    """
    parts = s.split(':')
    if len(parts) != 5:
        raise argparse.ArgumentTypeError(f"Invalid item spec '{s}', must be <item>:<amount>:<x>:<y>:<z>")
    
    name, amount, x, y, z = parts
    
    if not amount.isdigit() or int(amount) < 1:
        raise argparse.ArgumentTypeError(f"Invalid amount '{amount}' for item '{name}'")
    
    try:
        x, y, z = float(x), float(y), float(z)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid coordinates for item '{name}'")
        
    return (name, int(amount), [x, y, z])

# Standard arguments are now added from the base DayZTool class

def main():
    """
    Main function to run the spawner entries generator as a command-line tool.
    """
    parser = argparse.ArgumentParser(
        description="Generate DayZ object spawner JSON entries from command line."
    )
    parser.add_argument("--types_xml", help="Path to types.xml (defaults to path.types_file from config)")
    parser.add_argument("items", nargs='+', type=parse_item_amount_pos, 
                      help="Item(s) in format <item>:<amount>:<x>:<y>:<z>")
    parser.add_argument("--ypr", default="0 0 0", help="YPR (default: '0 0 0')")
    parser.add_argument("--scale", type=float, default=1.0, help="Scale (default: 1.0)")
    parser.add_argument("--enableCEPersistence", type=int, default=0, 
                      help="enableCEPersistence (default: 0)")
    parser.add_argument("--customString", default="", 
                      help="customString (default: empty)")
    parser.add_argument("--output", "-o", default=None, 
                      help="Output file (if not specified, a default filename will be used in the standard output directory)")
    parser.add_argument("--print", action="store_true",
                      help="Print the generated JSON to stdout")
    
    # Add standard arguments from base class
    from ..base import DayZTool
    DayZTool.add_standard_arguments(parser)
    args = parser.parse_args()
    
    # Load configuration using the static method from DayZTool
    config = DayZTool.load_config(args.profile)
    
    # Create and run the tool
    generator = GenerateSpawnerEntries(config)
    
    # Use types_xml from command line or from config
    types_xml_path = args.types_xml if args.types_xml else generator.get_config('paths.types_file')
    
    if not types_xml_path:
        logger.error("No types.xml path provided in command line or configuration")
        sys.exit(1)
    
    # Use the run method which is required by the base class
    result = generator.run(
        types_xml_path,
        args.items,
        args.ypr,
        args.scale,
        args.enableCEPersistence,
        args.customString,
        args.output
    )
    
    # Output result to console if requested
    if args.print:
        logger.info("Generated result:")
        for line in json.dumps(result, indent=2).split('\n'):
            logger.info(line)
    else:
        logger.info(f"Output saved to: {result['output_file']}")
        logger.info(f"Output directory: {generator.output_dir}")
        
    # Show additional information if --console flag is used
    if args.console:
        logger.info("\nSummary:")
        logger.info(f"Number of items processed: {len(args.items)}")
        for item_name, amount, pos in args.items:
            logger.info(f"  - {item_name}: {amount}x at position {pos}")


if __name__ == '__main__':
    main()

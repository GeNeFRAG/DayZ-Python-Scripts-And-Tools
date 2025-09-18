"""
Generate Spawner Entries Tool

Create DayZ object spawner JSON entries from command line inputs.
Takes item names, quantities, and positions to generate formatted JSON entries.

Supports configuration-based defaults:
- object_spawner.default_coordinates: Default x:y:z coordinates (e.g., "10106.6:8.5:1696.5")
- object_spawner.default_filename: Default output filename (e.g., "16355842-shop.json")

Commands:
- generate: Create spawner entries from item specifications
- empty: Create an empty spawner JSON template with just {"Objects": []}

Items can be specified as:
- item:amount - Uses default coordinates from configuration
- item:amount:x:y:z - Uses specific coordinates
"""

import sys
import json
import argparse
import os
from typing import Dict, Any, Optional, List, Tuple

# Import base class and logger
from ..base import XMLTool, JSONTool, logger


# Create a hybrid base class that provides both XML and JSON functionality
class XMLJSONTool(XMLTool, JSONTool):
    """Base class that provides both XML and JSON functionality."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize with both XML and JSON capabilities."""
        # Call both parent constructors
        XMLTool.__init__(self, config)
        # JSONTool also inherits from FileBasedTool, so we don't need to call it again


__all__ = ['GenerateSpawnerEntries', 'main']

# Configuration loading is now handled by DayZTool.load_config()


class GenerateSpawnerEntries(XMLJSONTool):
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

        # Parse default coordinates from config
        self.default_coordinates = self._parse_default_coordinates()

    def _parse_default_coordinates(self) -> List[float]:
        """
        Parse default coordinates from configuration.

        Returns:
            List of [x, y, z] coordinates from config, or [0.0, 0.0, 0.0] if not set
        """
        coord_str = self.get_config('object_spawner.default_coordinates', '0.0:0.0:0.0')
        try:
            parts = coord_str.split(':')
            if len(parts) != 3:
                logger.warning(f"Invalid default coordinates format '{coord_str}', using [0.0, 0.0, 0.0]")
                return [0.0, 0.0, 0.0]
            return [float(parts[0]), float(parts[1]), float(parts[2])]
        except ValueError:
            logger.warning(f"Could not parse default coordinates '{coord_str}', using [0.0, 0.0, 0.0]")
            return [0.0, 0.0, 0.0]

    def run(self, types_xml_path: str, items: List[Tuple[str, int, List[float]]],
            ypr: str = "0.0, -0.0, -0.0", scale: float = 1.0,
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
        Parse a string in the format <item>:<amount> or <item>:<amount>:<x>:<y>:<z>.
        If coordinates are not provided, use default coordinates from config.

        Args:
            s: String containing item, amount, and optionally position data

        Returns:
            Tuple of (item_name, amount, [x, y, z])

        Raises:
            ValueError: If the format is invalid
        """
        parts = s.split(':')
        if len(parts) == 2:
            # Use default coordinates
            name, amount = parts
            coords = self.default_coordinates.copy()  # Use copy to avoid mutation
        elif len(parts) == 5:
            # Full specification with coordinates
            name, amount, x, y, z = parts
            try:
                coords = [float(x), float(y), float(z)]
            except ValueError as e:
                raise ValueError(f"Invalid coordinates for item '{name}': {e}")
        else:
            raise ValueError(f"Invalid item spec '{s}', must be <item>:<amount> or <item>:<amount>:<x>:<y>:<z>")

        # Validate item name
        if not name or not name.strip():
            raise ValueError("Item name cannot be empty")
        name = name.strip()

        # Validate amount
        try:
            amount_int = int(amount)
            if amount_int < 1:
                raise ValueError(f"Amount must be at least 1 for item '{name}', got {amount_int}")
        except ValueError as e:
            if "invalid literal" in str(e):
                raise ValueError(f"Invalid amount '{amount}' for item '{name}': must be a positive integer")
            raise

        return (name, amount_int, coords)

    def _load_types_xml(self, types_xml_path: str) -> None:
        """
        Load valid item names from types.xml file.

        Args:
            types_xml_path: Path to the types.xml file
        """
        logger.info(f"Loading types.xml from {types_xml_path}")

        if not os.path.exists(types_xml_path):
            raise FileNotFoundError(f"types.xml file not found: {types_xml_path}")

        try:
            # Use base class read_xml method instead of direct ElementTree
            root = self.read_xml(types_xml_path)

            if root.tag != 'types':
                logger.warning(f"Unexpected root element '{root.tag}' in types.xml, expected 'types'")

            type_count = 0
            for type_elem in root.findall('type'):
                name = type_elem.get('name')
                if name and name.strip():
                    self.valid_items.add(name.strip())
                    type_count += 1
                else:
                    logger.warning("Found type element without valid name attribute")

            if type_count == 0:
                logger.warning("No valid type elements found in types.xml")

            logger.info(f"Loaded {len(self.valid_items)} valid items from types.xml")

        except Exception as e:
            # Handle both XML parsing errors and other exceptions
            if "XML" in str(type(e).__name__) or "parse" in str(e).lower():
                logger.error(f"XML parsing error in types.xml: {e}")
                raise ValueError(f"Invalid XML format in types.xml: {e}")
            else:
                logger.error(f"Unexpected error loading types.xml: {e}")
                raise

    def generate_entries(self, types_xml_path: str, items: List[Tuple[str, int, List[float]]],
                         ypr: str = "0.0, -0.0, -0.0", scale: float = 1.0,
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

        # Convert ypr string to array of floats
        try:
            ypr_values = [float(v.strip()) for v in ypr.split(',')]
            if len(ypr_values) < 3:
                # Use default values with negative zeros for missing values
                default_ypr = [0.0, -0.0, -0.0]
                ypr_values = ypr_values + default_ypr[len(ypr_values):]
        except ValueError:
            # Fallback to default values if parsing fails
            logger.warning(f"Could not parse YPR values '{ypr}', using defaults")
            ypr_values = [0.0, -0.0, -0.0]

        # Process each item
        for name, amount, pos in items:
            if name not in self.valid_items:
                logger.warning(f"Item '{name}' not found in types.xml")
                next

            obj = {
                "name": name,
                "pos": pos,
                "ypr": ypr_values,
                "scale": scale,
                "enableCEPersistency": enable_ce_persistence
            }

            if custom_string == "":
                obj["customString"] = custom_string

            # Add the item multiple times based on amount
            for _ in range(amount):
                result["Objects"].append(obj.copy())

        logger.info(f"Generated {len(result['Objects'])} object entries")

        # Save to file
        if output_file:
            # Use the provided filename (base class handles path resolution)
            target_file = self.write_json(result, output_file, indent=2)
        else:
            # Try to use the default filename from config, otherwise generate timestamped filename
            default_filename = self.get_config('object_spawner.default_filename')
            if default_filename:
                target_file = self.write_json(result, default_filename, indent=2)
            else:
                # Generate default filename with timestamp using the base class utility method
                filename = self.generate_timestamped_filename(
                    "spawner_entries", "json", suffix=f"{len(result['Objects'])}_items"
                )
                target_file = self.write_json(result, filename, indent=2)

        # Create a separate result dictionary for the return value with metadata
        return_result = result.copy()
        return_result["output_file"] = target_file
        return_result["timestamp"] = self.get_timestamp_str()  # Keep timestamp for logging only

        return return_result

    def create_empty_json(self, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Create an empty DayZ object spawner JSON file with the basic structure.

        Args:
            output_file: Optional path for saving the output. If None, a default filename
                        will be used from config or generated with timestamp.

        Returns:
            Dictionary with the created empty structure and metadata
        """
        # Create empty structure
        result = {"Objects": []}

        # Determine output file and write
        if output_file:
            # Use the provided filename (base class handles path resolution)
            target_file = self.write_json(result, output_file, indent=2)
        else:
            # Try to use the default filename from config, otherwise generate timestamped filename
            default_filename = self.get_config('object_spawner.default_filename')
            if default_filename:
                target_file = self.write_json(result, default_filename, indent=2)
            else:
                # Generate default filename with timestamp using the base class utility method
                filename = self.generate_timestamped_filename(
                    "empty_spawner", "json", suffix="template"
                )
                target_file = self.write_json(result, filename, indent=2)

        # Create result dictionary with metadata
        return_result = result.copy()
        return_result["output_file"] = target_file
        return_result["timestamp"] = self.get_timestamp_str()

        return return_result


def parse_item_amount_pos(s: str) -> Tuple[str, int, List[float]]:
    """
    Parse a string in the format <item>:<amount> or <item>:<amount>:<x>:<y>:<z>.
    If coordinates are not provided, use [0.0, 0.0, 0.0] as default.

    Args:
        s: String containing item, amount, and optionally position data

    Returns:
        Tuple of (item_name, amount, [x, y, z])
    """
    parts = s.split(':')
    if len(parts) == 2:
        # Use default coordinates [0.0, 0.0, 0.0]
        name, amount = parts
        coords = [0.0, 0.0, 0.0]
    elif len(parts) == 5:
        # Full specification with coordinates
        name, amount, x, y, z = parts
        try:
            coords = [float(x), float(y), float(z)]
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid coordinates for item '{name}'")
    else:
        raise argparse.ArgumentTypeError(
            f"Invalid item spec '{s}', must be <item>:<amount> or <item>:<amount>:<x>:<y>:<z>")

    if not amount.isdigit() or int(amount) < 1:
        raise argparse.ArgumentTypeError(f"Invalid amount '{amount}' for item '{name}'")

    return (name, int(amount), coords)

# Standard arguments are now added from the base DayZTool class


def main():
    """
    Main function to run the spawner entries generator as a command-line tool.

    The tool supports configuration-based defaults for:
    - Default coordinates: 'object_spawner.default_coordinates' (format: 'x:y:z')
    - Default output filename: 'object_spawner.default_filename'

    Items can be specified in two formats:
    - <item>:<amount> - Uses default coordinates from config
    - <item>:<amount>:<x>:<y>:<z> - Uses specified coordinates
    """
    parser = argparse.ArgumentParser(
        description="Generate DayZ object spawner JSON entries from command line."
    )

    # Add subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Generate entries subcommand
    generate_parser = subparsers.add_parser('generate', help='Generate spawner entries from items')
    generate_parser.add_argument("--types_xml", help="Path to types.xml (defaults to path.types_file from config)")
    generate_parser.add_argument("items", nargs='+', type=str,
                                 help="Item(s) in format <item>:<amount> or <item>:<amount>:<x>:<y>:<z>")
    generate_parser.add_argument("--ypr", default="0.0, -0.0, -0.0",
                                 help="YPR as comma-separated values (default: '0.0, -0.0, -0.0')")
    generate_parser.add_argument("--scale", type=float, default=1.0, help="Scale (default: 1.0)")
    generate_parser.add_argument("--enableCEPersistence", type=int, default=0,
                                 help="enableCEPersistence (default: 0)")
    generate_parser.add_argument("--customString", default="",
                                 help="customString (default: empty)")
    generate_parser.add_argument("--output", "-o", default=None,
                                 help="Output file (if not specified, default filename from config will be used)")
    generate_parser.add_argument("--print", action="store_true",
                                 help="Print the generated JSON to stdout")

    # Create empty file subcommand
    empty_parser = subparsers.add_parser('empty', help='Create an empty spawner JSON template')
    empty_parser.add_argument("--output", "-o", default=None,
                              help="Output file (if not specified, default filename from config will be used)")
    empty_parser.add_argument("--print", action="store_true",
                              help="Print the empty JSON structure to stdout")

    # Add standard arguments from base class to main parser
    from ..base import DayZTool
    DayZTool.add_standard_arguments(parser)

    # For backward compatibility, if no subcommand is provided but items are given, assume 'generate'
    args, unknown = parser.parse_known_args()
    if args.command is None and unknown:
        # Rebuild args with 'generate' subcommand for backward compatibility
        sys.argv.insert(1, 'generate')
        args = parser.parse_args()
    elif args.command is None:
        parser.error("Please specify a command: 'generate' or 'empty'")

    # Load configuration using the static method from DayZTool
    config = DayZTool.load_config(args.profile)

    # Create the tool
    generator = GenerateSpawnerEntries(config)

    if args.command == 'generate':
        # Parse items using the tool's method to get default coordinates from config
        try:
            parsed_items = [generator.parse_item_amount_pos(item) for item in args.items]
        except ValueError as e:
            logger.error(f"Error parsing items: {e}")
            sys.exit(1)

        # Use types_xml from command line or from config
        types_xml_path = args.types_xml if args.types_xml else generator.get_config('paths.types_file')

        if not types_xml_path:
            logger.error("No types.xml path provided in command line or configuration")
            sys.exit(1)

        # Use the run method which is required by the base class
        result = generator.run(
            types_xml_path,
            parsed_items,
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
            logger.info(f"Number of items processed: {len(parsed_items)}")
            for item_name, amount, pos in parsed_items:
                logger.info(f"  - {item_name}: {amount}x at position {pos}")
            logger.info(f"Default coordinates from config: {generator.default_coordinates}")

    elif args.command == 'empty':
        # Create empty JSON file
        result = generator.create_empty_json(args.output)

        # Output result to console if requested
        if args.print:
            logger.info("Empty JSON structure:")
            for line in json.dumps({"Objects": []}, indent=2).split('\n'):
                logger.info(line)
        else:
            logger.info(f"Empty spawner template created: {result['output_file']}")
            logger.info(f"Output directory: {generator.output_dir}")

        # Show additional information if --console flag is used
        if args.console:
            default_filename = generator.get_config('object_spawner.default_filename')
            logger.info(f"\nEmpty template created with default filename from config: {default_filename}")
            logger.info(f"Default coordinates available: {generator.default_coordinates}")


if __name__ == '__main__':
    main()

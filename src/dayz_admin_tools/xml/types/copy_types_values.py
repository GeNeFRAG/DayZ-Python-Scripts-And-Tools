"""
Copy Types Values Tool

A tool that copies specified element values from a source XML file to a target XML file.
This is useful for transferring specific values (like lifetime, usage, or nominal values)
from one types.xml file to another.
"""

import xml.etree.ElementTree as ET
import argparse
import logging
from typing import Dict, Optional, Any, Tuple

# Add support for the config system
from ...base import XMLTool, DayZTool

__all__ = ['CopyTypesValuesTool', 'main']

# Configure logging
logger = logging.getLogger(__name__)


def setup_console_logging():
    """Set up console logging for user-visible output."""
    # Create console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)

    # Create a simple formatter without timestamps for cleaner user output
    formatter = logging.Formatter('%(message)s')
    console.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(console)


class CopyTypesValuesTool(XMLTool):
    """Tool for copying element values between different XML files."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the copy types values tool.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)

        # Initialize common directories
        self.initialize_directories()

    def copy_element_values(self, src_file: str, target_file: str, element_to_copy: str,
                            type_name_pattern: Optional[str] = None) -> Tuple[int, int]:
        """
        Copy element values from source XML file to target XML file.

        Args:
            src_file: Path to the source XML file
            target_file: Path to the target XML file
            element_to_copy: The XML element to copy (e.g., 'lifetime')
            type_name_pattern: Wildcard pattern to match type names (e.g., 'Zmbf*')

        Returns:
            Tuple of (matched_items, changed_items)
        """
        # Build a dictionary of types and their values from source file
        source_types = self.build_type_dict(src_file, elements=[element_to_copy])
        matched_items = len(source_types)

        logger.info(f"Found {matched_items} items with '{element_to_copy}' element in source file")
        if matched_items == 0:
            logger.warning(f"No matching items found for element '{element_to_copy}'")
            return (0, 0)

        # Read and filter target types
        # Use read_xml_with_comments to ensure XML comments are preserved when writing back
        target_root = self.read_xml_with_comments(target_file)
        target_types = self.filter_types_by_name(target_root, type_name_pattern)

        # Update element values in target file
        changed_items = 0
        logger.info(f"Updating target file with values for {len(source_types)} types")

        for type_elem in target_types:
            name = type_elem.get('name')
            if name in source_types and element_to_copy in source_types[name]:
                new_value = source_types[name][element_to_copy]
                if new_value is not None:
                    element = type_elem.find(element_to_copy)
                    if element is None:
                        element = ET.SubElement(type_elem, element_to_copy)
                    element.text = new_value
                    changed_items += 1

        logger.info(f"Updated {changed_items} items in target file")

        # Write the updated target file using base class method
        # The improved write_xml method will preserve comments that were read with read_xml_with_comments
        self.write_xml(target_root, target_file, pretty=True, xml_declaration=True)
        logger.info(f"Saved updated file: {target_file}")

        return (matched_items, changed_items)

    def run(self, element_to_copy: str, target_file: str,
            type_name_pattern: Optional[str] = None, src_file: Optional[str] = None) -> None:
        """
        Run the copy types values tool.

        Args:
            element_to_copy: The XML element to copy (e.g., 'lifetime')
            target_file: Path to the target XML file
            type_name_pattern: Wildcard pattern to match type names (e.g., 'Zmbf*')
            src_file: Optional path to the source XML file (uses paths.types_file from config if None)
        """
        # Use the types_file from config if src_file is not provided
        if not src_file:
            src_file = self.get_config('paths.types_file')
            if not src_file:
                logger.error("No source file specified and no 'paths.types_file' configured in profile")
                raise ValueError("Source file path is required, either directly or via configuration")

        logger.info("Starting copy types values tool")
        logger.info(f"Element to copy: {element_to_copy}")
        logger.info(f"Source file: {src_file}")
        logger.info(f"Target file: {target_file}")
        if type_name_pattern:
            logger.info(f"Type name pattern: {type_name_pattern}")

        # Make a backup of the target file in the configured backup directory
        backup_dir = self.get_config('general.backup_directory', None)
        backup_file = self.backup_file(target_file, backup_dir)
        logger.info(f"Created backup of target file: {backup_file}")

        # Copy element values from source to target
        matched_items, changed_items = self.copy_element_values(
            src_file, target_file, element_to_copy, type_name_pattern
        )

        logger.info("Copy types values tool completed successfully")
        logger.info(f"Number of matched items: {matched_items}")
        logger.info(f"Number of changed items: {changed_items}")


def main():
    """Main function for the copy types values tool."""
    parser = argparse.ArgumentParser(
        description='Copy specified element values from a source XML file to a target XML file.'
    )
    parser.add_argument('--element', type=str, required=True,
                        help='The XML element to copy (e.g., lifetime)')
    parser.add_argument('--target_file', type=str, required=True,
                        help='The target XML file path')
    parser.add_argument('--src_file', type=str, required=False,
                        help='The source XML file path (uses paths.types_file from profile if not specified)')
    parser.add_argument('--type_name', type=str, required=False,
                        help='Wildcard pattern to match type names (e.g., Zmbf*)')

    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)

    args = parser.parse_args()

    try:
        # Load configuration
        config = DayZTool.load_config(args.profile)

        # Set up console logging for user output
        setup_console_logging()

        # Create and run the tool
        tool = CopyTypesValuesTool(config)
        tool.run(args.element, args.target_file, args.type_name, args.src_file)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
        exit(1)


if __name__ == "__main__":
    main()

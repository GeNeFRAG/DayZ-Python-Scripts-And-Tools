"""
Replace Usage and Value Tags Tool

A tool for updating usage and value tags in types.xml files.
This tool can be used to:
1. Copy usage and value tags from a source types.xml file to a target file
2. Apply a single usage tag to all items in a types.xml file
"""

import argparse
import logging
from typing import Dict, List, Optional, Any

# Add support for the config system
from ...base import XMLTool, DayZTool, ET

__all__ = ['ReplaceUsageValueTagTypesTool', 'main']

# Configure logging
logger = logging.getLogger(__name__)


class ReplaceUsageValueTagTypesTool(XMLTool):
    """Tool for replacing usage and value tags in types.xml files."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the replace usage value tag types tool.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)

        # Initialize common directories
        self.initialize_directories()

    def extract_usages_and_values(self, src_file: str) -> Dict[str, Dict[str, List[str]]]:
        """
        Extract usage and value tags from a source XML file.

        Args:
            src_file: Path to the source XML file

        Returns:
            Dictionary mapping type names to their usage and value tags
        """
        root = self.read_xml(src_file)
        usages_and_values = {}

        for type_elem in root.findall('type'):
            name = type_elem.get('name')
            usage_tags = [usage.get('name') for usage in type_elem.findall('usage')]
            value_tags = [value.get('name') for value in type_elem.findall('value')]
            usages_and_values[name] = {'usages': usage_tags, 'values': value_tags}

        logger.debug(f"Extracted usage and value tags for {len(usages_and_values)} types")
        return usages_and_values

    def update_target_file(self, target_file: str, usages_and_values: Dict[str, Dict[str, List[str]]],
                           cmd_usage_tag: Optional[str] = None) -> List[str]:
        """
        Update a target XML file with usage and value tags.

        Args:
            target_file: Path to the target XML file
            usages_and_values: Dictionary of type names to their usage and value tags
            cmd_usage_tag: Optional single usage tag to apply to all types

        Returns:
            List of type names not found in the source file
        """
        # Use read_xml_with_comments to preserve comments
        root = self.read_xml_with_comments(target_file)
        not_found = []
        updated_count = 0

        for type_elem in root.findall('type'):
            name = type_elem.get('name')
            if name in usages_and_values:
                # Remove existing category, usage, tag, and value tags
                tags_to_remove = (type_elem.findall('category') + type_elem.findall('usage') +
                                  type_elem.findall('tag') + type_elem.findall('value'))
                for tag in tags_to_remove:
                    type_elem.remove(tag)
                # Add usage tags from source file
                for usage_name in usages_and_values[name]['usages']:
                    usage_elem = ET.Element('usage')
                    usage_elem.set('name', usage_name)
                    type_elem.append(usage_elem)
                # Add value tags from source file
                for value_name in usages_and_values[name]['values']:
                    value_elem = ET.Element('value')
                    value_elem.set('name', value_name)
                    type_elem.append(value_elem)
                updated_count += 1
            else:
                not_found.append(name)

            # Replace all usage and value tags with the usage_tag from cmd line if provided
            has_tags = (type_elem.findall('usage') or type_elem.findall('value') or
                        type_elem.findall('category'))
            if cmd_usage_tag and has_tags:
                tags_to_remove = (type_elem.findall('category') + type_elem.findall('usage') +
                                  type_elem.findall('tag') + type_elem.findall('value'))
                for tag in tags_to_remove:
                    type_elem.remove(tag)
                usage_elem = ET.Element('usage')
                usage_elem.set('name', cmd_usage_tag)
                type_elem.append(usage_elem)
                updated_count += 1

        logger.info(f"Updated {updated_count} types in {target_file}")

        # Use write_xml from the base class to write the XML
        # This handles directory creation, proper formatting, and comment preservation
        # since we read the file with read_xml_with_comments
        self.write_xml(root, target_file, pretty=True, xml_declaration=True)

        logger.info(f"Updated {updated_count} types in {target_file}")
        return not_found

    def run(self, target_file: str, usage_tag: Optional[str] = None, src_file: Optional[str] = None) -> None:
        """
        Run the replace usage and value tags tool.

        Args:
            target_file: Path to the target XML file
            usage_tag: Optional single usage tag to apply to all types
            src_file: Optional path to the source XML file (uses paths.types_file from config if None)
        """
        logger.info("Starting replace usage and value tags tool")

        # Use the types_file from config if src_file is not provided
        if not src_file:
            src_file = self.get_config('paths.types_file')
            if not src_file:
                logger.error("No source file specified and no 'paths.types_file' configured in profile")
                raise ValueError("Source file path is required, either directly or via configuration")

        # Initialize usages_and_values
        usages_and_values = {}

        # Extract usage and value tags from source file
        logger.info(f"Extracting usage and value tags from {src_file}")
        usages_and_values = self.extract_usages_and_values(src_file)

        # Get backup directory from config
        backup_dir = self.get_config('general.backup_directory', None)

        # Backup the target file before modification
        logger.info(f"Creating backup of {target_file} in backup directory")
        self.backup_file(target_file, backup_dir)

        # Update the target file with the extracted tags (write back to same file)
        logger.info(f"Updating {target_file}")
        not_found = self.update_target_file(target_file, usages_and_values, usage_tag)

        # Log any types that weren't found in the source file
        if not_found:
            logger.warning(f"The following {len(not_found)} types were not found in the source file:")
            for name in not_found:
                logger.warning(f"  {name}")

        logger.info("Replace usage and value tags tool completed successfully")


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


def main():
    """Main function for the replace usage and value tags tool."""
    parser = argparse.ArgumentParser(
        description='Update target XML file with usage and value tags from source XML file.'
    )
    parser.add_argument('--target_file', type=str, required=True,
                        help='The target XML file path')
    parser.add_argument('--src_file', type=str, required=False,
                        help='The source XML file path (uses paths.types_file from profile if not specified)')
    parser.add_argument('--usage_tag', type=str, required=False,
                        help='Usage tag to be added to all types')

    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)

    args = parser.parse_args()

    try:
        # Load configuration
        config = DayZTool.load_config(args.profile)

        # Set up console logging for user output
        setup_console_logging()

        # Create and run the tool
        tool = ReplaceUsageValueTagTypesTool(config)
        tool.run(args.target_file, args.usage_tag, args.src_file)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

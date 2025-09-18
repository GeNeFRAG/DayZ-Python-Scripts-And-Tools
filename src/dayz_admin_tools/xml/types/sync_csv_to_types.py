"""
Sync CSV to Types Tool

This tool updates nominal and minimum values in a types.xml file based on counts from CSV files.
It's useful for adjusting DayZ server item spawns based on external data sources or calculations.
"""

import logging
import os
import argparse
from pathlib import Path
from typing import Dict, Optional, Any, List

from ...base import XMLTool, DayZTool

__all__ = ['SyncCsvToTypesTool', 'main']

# Configure logging
logger = logging.getLogger(__name__)


class SyncCsvToTypesTool(XMLTool):
    """Tool for syncing CSV counts with types.xml file."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the sync CSV to types tool.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)

        # Initialize common directories
        self.initialize_directories()

        # Get reference and output types files from config
        self.types_file_ref = self.get_config('paths.types_file_ref')
        self.types_file = self.get_config('paths.types_file')

        # Get backup directory from config
        self.backup_dir = self.get_config('general.backup_directory', 'backups')

    def read_csv_counts(self, csv_file: str) -> Dict[str, int]:
        """
        Reads item counts from a CSV file.

        Args:
            csv_file: Path to the CSV file.

        Returns:
            A dictionary with item names as keys and counts as values.
        """
        # Use the base class read_csv method
        data_rows = self.read_csv(csv_file, required_columns=['item', 'count'])

        counts = {}
        for row in data_rows:
            counts[row['item']] = int(row['count'])

        if not counts:
            logger.warning(f"CSV file '{csv_file}' is empty. No items will be updated.")
        else:
            logger.info(f"Read {len(counts)} items from {csv_file}")

        return counts

    def combine_csv_counts(self, csv_files: List[str]) -> Dict[str, int]:
        """
        Reads and combines item counts from multiple CSV files.

        Args:
            csv_files: List of paths to CSV files.

        Returns:
            A dictionary with item names as keys and combined counts as values.
        """
        combined_counts = {}
        for csv_file in csv_files:
            logger.info(f"Reading counts from {csv_file}")
            counts = self.read_csv_counts(csv_file)
            for item, count in counts.items():
                if item in combined_counts:
                    combined_counts[item] += count
                    logger.debug(f"Updated count for {item}: added {count} (total: {combined_counts[item]})")
                else:
                    combined_counts[item] = count
                    logger.debug(f"New item {item}: count {count}")

        logger.info(f"Combined {len(csv_files)} CSV files with {len(combined_counts)} unique items")
        return combined_counts

    def generate_output_filename(self, reference_file: str) -> str:
        """
        Generate an output filename based on the reference file.

        Args:
            reference_file: Path to the reference types.xml file

        Returns:
            Generated output path in the configured output directory
        """
        ref_path = Path(reference_file)
        output_name = f"{ref_path.stem}_updated{ref_path.suffix}"
        return os.path.join(self.output_dir, output_name)

    def update_types_xml(self, reference_types_file: str, output_types_file: str, counts: Dict[str, int],
                         organize_by_usage: bool = False) -> None:
        """
        Creates a new types.xml file with updated nominal and minimum values based on the counts.

        Args:
            reference_types_file: Path to the reference types.xml file (will not be modified)
            output_types_file: Path where the new XML file will be written
            counts: A dictionary with item names as keys and counts as values
            organize_by_usage: Whether to organize the output by usage categories
        """
        # Read and parse reference XML using base class method with comment preservation
        root = self.read_xml_with_comments(reference_types_file)

        # Use base class method to get all type elements
        items = self.filter_types_by_name(root)

        updated_count = 0
        for item in items:
            name = item.get('name')
            if name in counts:
                nominal = item.find('nominal')
                min_val = item.find('min')

                if nominal is not None and int(nominal.text) != 0:
                    nominal_before = nominal.text
                    min_val_before = min_val.text if min_val is not None else None

                    nominal.text = str(int(nominal.text) + counts[name])
                    if min_val is not None:
                        min_val.text = str(int(min_val.text) + counts[name])

                    if nominal.text != nominal_before or (min_val is not None and min_val.text != min_val_before):
                        min_text = min_val.text if min_val is not None else 'N/A'
                        logger.info(
                            f"Updated {name}: nominal={nominal_before}>{nominal.text}, min={min_val_before}>{min_text}")
                        updated_count += 1

        if organize_by_usage:
            # Use the new base class method to organize by usage
            logger.info("Organizing items by usage categories")
            root = self.create_sorted_by_usage_root(root, add_index=True)

        # Create a backup of the output file before writing changes
        if os.path.exists(output_types_file):
            backup_file = self.backup_file(output_types_file, self.backup_dir)
            logger.info(f"Created backup of types.xml: {backup_file}")

        # Write new XML using base class method (preserves comments that were read with read_xml_with_comments)
        self.write_xml(root, output_types_file, pretty=True)

        logger.info(f"Created new types.xml with {updated_count} updated items at {output_types_file}")

    def run(self, csv_files: List[str], reference_types_file: Optional[str] = None,
            output_types_file: Optional[str] = None, organize_by_usage: bool = False) -> Dict[str, Any]:
        """
        Run the sync CSV to types tool.

        Args:
            csv_files: List of paths to input CSV files
            reference_types_file: Path to the reference types.xml file (if None, uses config paths.types_file_ref)
            output_types_file: Path where the new XML file will be written (if None, uses config paths.types_file)
            organize_by_usage: Whether to organize the output by usage categories

        Returns:
            Dictionary with results information
        """
        logger.info("Starting sync CSV to types tool")

        # Use configured reference file if none provided
        if not reference_types_file:
            reference_types_file = self.types_file_ref
            if not reference_types_file:
                msg = "No reference types file specified and no 'paths.types_file_ref' configured in profile"
                logger.error(msg)
                return {"error": msg}
            logger.info(f"Using configured reference types file: {reference_types_file}")

        # Use configured output file if none provided
        if not output_types_file:
            output_types_file = self.types_file
            if not output_types_file:
                # Fall back to generating name if no config
                output_types_file = self.generate_output_filename(reference_types_file)
            logger.info(f"Using configured output types file: {output_types_file}")

        try:
            # Read and combine item counts from all CSV files
            logger.info(f"Processing {len(csv_files)} CSV files")
            counts = self.combine_csv_counts(csv_files)

            # Create new types.xml with updated counts
            logger.info("Creating new types.xml with combined counts")
            self.update_types_xml(reference_types_file, output_types_file, counts, organize_by_usage)

            return {
                "success": True,
                "reference_file": reference_types_file,
                "output_file": output_types_file,
                "csv_files": csv_files,
                "organize_by_usage": organize_by_usage,
                "items_updated": sum(1 for item in counts if item in counts)
            }

        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return {"error": str(e)}


def main():
    """Main function for the sync CSV to types tool."""
    parser = argparse.ArgumentParser(
        description='Create a new types.xml with updated nominal and min values based on counts from CSV files. ' +
        'If no reference or output files are specified, uses paths from config profile.'
    )
    parser.add_argument('csv_files', nargs='+',
                        help='One or more paths to input CSV files containing item counts'
                        )
    parser.add_argument('--reference', dest='reference_types_file',
                        help='Path to the reference types.xml file (if not specified, '
                             'uses paths.types_file_ref from config)')
    parser.add_argument('--output', dest='output_types_file',
                        help='Path where the new XML file will be written (if not specified, '
                             'uses paths.types_file from config)')
    parser.add_argument('--organize', dest='organize_by_usage', action='store_true',
                        help='Organize the output XML file by usage categories with an index')

    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)

    args = parser.parse_args()

    try:
        # Load configuration
        config = SyncCsvToTypesTool.load_config(args.profile)

        # Create and run the tool
        tool = SyncCsvToTypesTool(config)
        result = tool.run(args.csv_files, args.reference_types_file, args.output_types_file, args.organize_by_usage)

        if "error" in result:
            logger.error(f"Error: {result['error']}")
            return 1

        success_msg = (f"Successfully created {result['output_file']} with updated values "
                       f"from {len(result['csv_files'])} CSV files")
        if result.get('organize_by_usage'):
            success_msg += " (organized by usage categories)"
        logger.info(success_msg)
        return 0

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        import traceback
        logging.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

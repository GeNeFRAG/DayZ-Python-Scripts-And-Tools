"""
Missing Groups Comparison Tool

This module provides functionality to compare mapgroupproto.xml files and identify
which group names are missing in each file, helping server admins to
analyze and adjust map group definitions across different server configurations.
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, Optional, Set

from dayz_admin_tools.base import XMLTool, DayZTool

logger = logging.getLogger(__name__)


class MissingGroupsComparer(XMLTool):
    """Compare mapgroupproto XML files to identify missing groups."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the Missing Groups Comparer tool.

        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        self.initialize_directories()
        self.file1 = None
        self.file2 = None
        self.output_file = None

    def parse_groups(self, file_path: str) -> Set[str]:
        """
        Parse group names from the given XML file.

        Args:
            file_path: Path to the XML file

        Returns:
            Set containing all group names
        """
        # Use the read_xml method from XMLTool base class
        root = self.read_xml(file_path)
        group_names = set()

        for group in root.findall('group'):
            group_name = group.get('name')
            if group_name:
                group_names.add(group_name)

        return group_names

    def compare_missing_groups(self) -> bool:
        """
        Compare group names between two XML files and identify which ones are missing in each file.
        Results are written to a CSV file.

        Returns:
            True if successful, False otherwise
        """
        try:
            groups1 = self.parse_groups(self.file1)
            groups2 = self.parse_groups(self.file2)

            # Find missing groups in each file
            missing_in_file1 = groups2 - groups1
            missing_in_file2 = groups1 - groups2
            common_groups = groups1.intersection(groups2)

            file1_name = os.path.basename(self.file1)
            file2_name = os.path.basename(self.file2)

            # Create data for CSV output
            csv_data = []

            # Define CSV headers
            headers = [
                'Type',
                'Group Name',
                f'Present in {file1_name}',
                f'Present in {file2_name}'
            ]

            # Add comparison metadata as first rows
            from datetime import datetime
            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            csv_data.append({
                'Type': 'Metadata',
                'Group Name': 'Comparison Date',
                f'Present in {file1_name}': current_date,
                f'Present in {file2_name}': current_date
            })

            csv_data.append({
                'Type': 'Metadata',
                'Group Name': 'File 1',
                f'Present in {file1_name}': self.file1,
                f'Present in {file2_name}': ''
            })

            csv_data.append({
                'Type': 'Metadata',
                'Group Name': 'File 2',
                f'Present in {file1_name}': '',
                f'Present in {file2_name}': self.file2
            })

            # Add an empty row for better readability
            csv_data.append({
                'Type': '',
                'Group Name': '',
                f'Present in {file1_name}': '',
                f'Present in {file2_name}': ''
            })

            # Add summary information
            csv_data.append({
                'Type': 'Summary',
                'Group Name': 'Total Groups',
                f'Present in {file1_name}': len(groups1),
                f'Present in {file2_name}': len(groups2)
            })

            csv_data.append({
                'Type': 'Summary',
                'Group Name': 'Common Groups',
                f'Present in {file1_name}': len(common_groups),
                f'Present in {file2_name}': len(common_groups)
            })

            csv_data.append({
                'Type': 'Summary',
                'Group Name': 'Missing Groups',
                f'Present in {file1_name}': len(missing_in_file1),
                f'Present in {file2_name}': len(missing_in_file2)
            })

            # Add an empty row for better readability
            csv_data.append({
                'Type': '',
                'Group Name': '',
                f'Present in {file1_name}': '',
                f'Present in {file2_name}': ''
            })

            # Add common groups section
            if common_groups:
                csv_data.append({
                    'Type': 'Section',
                    'Group Name': 'COMMON GROUPS',
                    f'Present in {file1_name}': '',
                    f'Present in {file2_name}': ''
                })

                for group_name in sorted(common_groups):
                    csv_data.append({
                        'Type': 'Group',
                        'Group Name': group_name,
                        f'Present in {file1_name}': 'Yes',
                        f'Present in {file2_name}': 'Yes'
                    })

                # Add an empty row for better readability
                csv_data.append({
                    'Type': '',
                    'Group Name': '',
                    f'Present in {file1_name}': '',
                    f'Present in {file2_name}': ''
                })

            # Add missing in file1 section
            if missing_in_file1:
                csv_data.append({
                    'Type': 'Section',
                    'Group Name': f'GROUPS MISSING IN {file1_name}',
                    f'Present in {file1_name}': '',
                    f'Present in {file2_name}': ''
                })

                for group_name in sorted(missing_in_file1):
                    csv_data.append({
                        'Type': 'Group',
                        'Group Name': group_name,
                        f'Present in {file1_name}': 'No',
                        f'Present in {file2_name}': 'Yes'
                    })

                # Add an empty row for better readability
                csv_data.append({
                    'Type': '',
                    'Group Name': '',
                    f'Present in {file1_name}': '',
                    f'Present in {file2_name}': ''
                })

            # Add missing in file2 section
            if missing_in_file2:
                csv_data.append({
                    'Type': 'Section',
                    'Group Name': f'GROUPS MISSING IN {file2_name}',
                    f'Present in {file1_name}': '',
                    f'Present in {file2_name}': ''
                })

                for group_name in sorted(missing_in_file2):
                    csv_data.append({
                        'Type': 'Group',
                        'Group Name': group_name,
                        f'Present in {file1_name}': 'Yes',
                        f'Present in {file2_name}': 'No'
                    })

            # Ensure the output file has .csv extension
            csv_output_file = self.output_file
            if not csv_output_file.lower().endswith('.csv'):
                name, ext = os.path.splitext(csv_output_file)
                csv_output_file = f"{name}.csv"

            # Write the CSV file using the base class method
            resolved_path = self.write_csv(csv_data, csv_output_file, headers)

            if resolved_path:
                logger.info(f"Comparison results written to {resolved_path}")
                logger.info(f"Found {len(missing_in_file1)} groups missing in {file1_name} and "
                            f"{len(missing_in_file2)} groups missing in {file2_name}")
                self.output_file = resolved_path  # Update the output file path with the actual path
                return True
            return False

        except Exception as e:
            logger.error(f"Error comparing group names: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    # Removed get_timestamped_filename method in favor of using the base class implementation

    def _get_output_path(self, path: str) -> str:
        """
        Helper to get the correct output path, handling both absolute and relative paths.
        Adds a timestamp to the filename.

        Args:
            path: The file path from arguments

        Returns:
            The resolved output path with timestamp
        """
        if not path:
            return None

        # Add timestamp to filename using the base class method
        name, ext = os.path.splitext(path)
        timestamped_path = name + "_" + self.generate_timestamped_filename("", ext.lstrip("."))

        if os.path.isabs(timestamped_path):
            return self.resolve_path(timestamped_path)
        else:
            # Relative path - put in output directory
            return os.path.join(self.output_dir, timestamped_path)

    def setup_from_args(self, args: argparse.Namespace) -> None:
        """
        Set up the tool from command line arguments.

        Args:
            args: Command line arguments
        """
        # Make sure directories are initialized
        if not hasattr(self, 'output_dir') or not self.output_dir:
            self.initialize_directories()

        # Set input files (source files)
        self.file1 = self.resolve_path(args.file1)
        self.file2 = self.resolve_path(args.file2)

        # Set output file (with proper extension)
        output_filename = args.output
        # Ensure the file has .csv extension
        if not output_filename.lower().endswith('.csv'):
            name, ext = os.path.splitext(output_filename)
            output_filename = f"{name}.csv"

        # Use _get_output_path to add timestamp and handle directory paths
        self.output_file = self._get_output_path(output_filename) or os.path.join(
            self.output_dir, "missing_groups_comparison.csv")

        # Ensure output directory exists using the base class method
        if self.output_file:
            self.ensure_dir(os.path.dirname(self.output_file))

        # Log file paths
        logger.info(f"Input file 1: {self.file1}")
        logger.info(f"Input file 2: {self.file2}")
        logger.info(f"Comparison output file: {self.output_file}")

    def run(self) -> bool:
        """
        Run the Missing Groups Comparer tool.

        Returns:
            True if successful, False otherwise
        """
        return self.compare_missing_groups()


def main():
    """
    Main entry point for the Missing Groups Comparer tool when run as a script.
    """
    parser = argparse.ArgumentParser(
        description='Compare mapgroupproto.xml files to identify missing group names.\n'
        'Features:\n'
        '  - Identifies groups that are present in one file but missing in the other\n'
        '  - Outputs comparison data in CSV format with timestamps in filenames\n'
        '  - All output files include timestamps automatically\n'
        '  - Utilizes standard file I/O operations from the base library\n'
        '  - All output files will be placed in the directory specified by general.output_path config',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('file1',
                        help='First mapgroupproto XML file')

    parser.add_argument('file2',
                        help='Second mapgroupproto XML file')

    parser.add_argument('--output', '-o',
                        default='missing_groups_comparison.csv',
                        help='Filename for comparison output (timestamp will be added automatically)')

    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)

    args = parser.parse_args()

    # Initialize tool with config
    config = DayZTool.load_config(args.profile)
    tool = MissingGroupsComparer(config)
    tool.setup_from_args(args)

    # Run the tool
    success = tool.run()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

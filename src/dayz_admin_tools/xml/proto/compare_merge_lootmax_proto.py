"""
Lootmax Comparison and Merger Tool

This module provides functionality to compare and merge lootmax values
between different mapgroupproto.xml files, helping server admins to
analyze and adjust loot distribution across various buildings.
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, Optional

from dayz_admin_tools.base import XMLTool, DayZTool

logger = logging.getLogger(__name__)


class LootmaxComparer(XMLTool):
    """Compare and merge lootmax values between mapgroupproto XML files."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the Lootmax Comparer tool.

        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        self.initialize_directories()
        self.file1 = None
        self.file2 = None
        self.output_file = None
        self.merge_output_file = None

    def parse_lootmax(self, file_path: str) -> Dict[str, Dict]:
        """
        Parse lootmax values from the given XML file.

        Args:
            file_path: Path to the XML file

        Returns:
            Dictionary containing lootmax data for groups and containers
        """
        # Use the read_xml method from XMLTool base class
        root = self.read_xml(file_path)
        lootmax_data = {}

        for group in root.findall('group'):
            group_name = group.get('name')
            group_lootmax = int(group.get('lootmax', 0))
            containers = []

            for container in group.findall('container'):
                container_name = container.get('name')
                container_lootmax = int(container.get('lootmax', 0))
                containers.append((container_name, container_lootmax))

            lootmax_data[group_name] = {
                'group_lootmax': group_lootmax,
                'containers': containers
            }

        return lootmax_data

    def compare_lootmax(self) -> bool:
        """
        Compare lootmax values between two XML files and write results to a CSV file.
        Uses separate Group Name and Container Name columns to better represent hierarchy.

        Returns:
            True if successful, False otherwise
        """
        try:
            lootmax1 = self.parse_lootmax(self.file1)
            lootmax2 = self.parse_lootmax(self.file2)

            common_groups = set(lootmax1.keys()).intersection(set(lootmax2.keys()))
            unique_to_file1 = set(lootmax1.keys()) - set(lootmax2.keys())
            unique_to_file2 = set(lootmax2.keys()) - set(lootmax1.keys())

            file1_name = os.path.basename(self.file1)
            file2_name = os.path.basename(self.file2)

            # Create data for CSV output
            csv_data = []

            # Define CSV headers with separate Group Name and Container Name columns
            headers = [
                'Type',
                'Group Name',
                'Container Name',
                f'Lootmax in {file1_name}',
                f'Lootmax in {file2_name}',
                'Difference'
            ]

            # Add comparison metadata as first rows
            from datetime import datetime
            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            csv_data.append({
                'Type': 'Metadata',
                'Group Name': 'Comparison Date',
                'Container Name': '',
                f'Lootmax in {file1_name}': current_date,
                f'Lootmax in {file2_name}': '',
                'Difference': ''
            })

            csv_data.append({
                'Type': 'Metadata',
                'Group Name': 'File 1',
                'Container Name': '',
                f'Lootmax in {file1_name}': self.file1,
                f'Lootmax in {file2_name}': '',
                'Difference': ''
            })

            csv_data.append({
                'Type': 'Metadata',
                'Group Name': 'File 2',
                'Container Name': '',
                f'Lootmax in {file1_name}': '',
                f'Lootmax in {file2_name}': self.file2,
                'Difference': ''
            })

            # Add an empty row for better readability
            csv_data.append({
                'Type': '',
                'Group Name': '',
                'Container Name': '',
                f'Lootmax in {file1_name}': '',
                f'Lootmax in {file2_name}': '',
                'Difference': ''
            })

            # Process groups that exist in both files
            if common_groups:
                csv_data.append({
                    'Type': 'Section',
                    'Group Name': 'COMMON GROUPS',
                    'Container Name': '',
                    f'Lootmax in {file1_name}': '',
                    f'Lootmax in {file2_name}': '',
                    'Difference': ''
                })

                for group in sorted(common_groups):
                    lootmax1_data = lootmax1[group]
                    lootmax2_data = lootmax2[group]

                    # Add group entry
                    group_lootmax1 = lootmax1_data['group_lootmax']
                    group_lootmax2 = lootmax2_data['group_lootmax']
                    group_diff = group_lootmax2 - group_lootmax1

                    csv_data.append({
                        'Type': 'Group',
                        'Group Name': group,
                        'Container Name': '',
                        f'Lootmax in {file1_name}': group_lootmax1,
                        f'Lootmax in {file2_name}': group_lootmax2,
                        'Difference': group_diff
                    })

                    # Get all containers for this group
                    containers1 = {name: lootmax for name, lootmax in lootmax1_data['containers']}
                    containers2 = {name: lootmax for name, lootmax in lootmax2_data['containers']}
                    all_containers = set(containers1.keys()).union(set(containers2.keys()))

                    # Add container entries
                    for container in sorted(all_containers):
                        lootmax1_value = containers1.get(container, 0)
                        lootmax2_value = containers2.get(container, 0)
                        container_diff = lootmax2_value - lootmax1_value

                        csv_data.append({
                            'Type': 'Container',
                            'Group Name': group,  # Include the group name for better filtering
                            'Container Name': container,
                            f'Lootmax in {file1_name}': lootmax1_value,
                            f'Lootmax in {file2_name}': lootmax2_value,
                            'Difference': container_diff
                        })

                    # Add subtotal for this group
                    total_lootmax1 = sum(value for value in containers1.values() if isinstance(value, (int, float)))
                    total_lootmax2 = sum(value for value in containers2.values() if isinstance(value, (int, float)))
                    total_diff = total_lootmax2 - total_lootmax1

                    csv_data.append({
                        'Type': 'Subtotal',
                        'Group Name': group,
                        'Container Name': 'Total',
                        f'Lootmax in {file1_name}': total_lootmax1,
                        f'Lootmax in {file2_name}': total_lootmax2,
                        'Difference': total_diff
                    })

                    # Add a blank row after each group for better readability
                    csv_data.append({
                        'Type': '',
                        'Group Name': '',
                        'Container Name': '',
                        f'Lootmax in {file1_name}': '',
                        f'Lootmax in {file2_name}': '',
                        'Difference': ''
                    })

            # Add groups unique to file1
            if unique_to_file1:
                csv_data.append({
                    'Type': 'Section',
                    'Group Name': f'GROUPS ONLY IN {file1_name}',
                    'Container Name': '',
                    f'Lootmax in {file1_name}': '',
                    f'Lootmax in {file2_name}': '',
                    'Difference': ''
                })

                for group in sorted(unique_to_file1):
                    group_data = lootmax1[group]

                    csv_data.append({
                        'Type': 'Group',
                        'Group Name': group,
                        'Container Name': '',
                        f'Lootmax in {file1_name}': group_data['group_lootmax'],
                        f'Lootmax in {file2_name}': 0,
                        'Difference': -group_data['group_lootmax']
                    })

                    # Add container entries
                    for container_name, container_lootmax in sorted(group_data['containers']):
                        csv_data.append({
                            'Type': 'Container',
                            'Group Name': group,
                            'Container Name': container_name,
                            f'Lootmax in {file1_name}': container_lootmax,
                            f'Lootmax in {file2_name}': 0,
                            'Difference': -container_lootmax
                        })

                    # Add subtotal
                    total_lootmax = sum(lootmax for _, lootmax in group_data['containers'])
                    csv_data.append({
                        'Type': 'Subtotal',
                        'Group Name': group,
                        'Container Name': 'Total',
                        f'Lootmax in {file1_name}': total_lootmax,
                        f'Lootmax in {file2_name}': 0,
                        'Difference': -total_lootmax
                    })

                    # Add a blank row after each group for better readability
                    csv_data.append({
                        'Type': '',
                        'Group Name': '',
                        'Container Name': '',
                        f'Lootmax in {file1_name}': '',
                        f'Lootmax in {file2_name}': '',
                        'Difference': ''
                    })

            # Add groups unique to file2
            if unique_to_file2:
                csv_data.append({
                    'Type': 'Section',
                    'Group Name': f'GROUPS ONLY IN {file2_name}',
                    'Container Name': '',
                    f'Lootmax in {file1_name}': '',
                    f'Lootmax in {file2_name}': '',
                    'Difference': ''
                })

                for group in sorted(unique_to_file2):
                    group_data = lootmax2[group]

                    csv_data.append({
                        'Type': 'Group',
                        'Group Name': group,
                        'Container Name': '',
                        f'Lootmax in {file1_name}': 0,
                        f'Lootmax in {file2_name}': group_data['group_lootmax'],
                        'Difference': group_data['group_lootmax']
                    })

                    # Add container entries
                    for container_name, container_lootmax in sorted(group_data['containers']):
                        csv_data.append({
                            'Type': 'Container',
                            'Group Name': group,
                            'Container Name': container_name,
                            f'Lootmax in {file1_name}': 0,
                            f'Lootmax in {file2_name}': container_lootmax,
                            'Difference': container_lootmax
                        })

                    # Add subtotal
                    total_lootmax = sum(lootmax for _, lootmax in group_data['containers'])
                    csv_data.append({
                        'Type': 'Subtotal',
                        'Group Name': group,
                        'Container Name': 'Total',
                        f'Lootmax in {file1_name}': 0,
                        f'Lootmax in {file2_name}': total_lootmax,
                        'Difference': total_lootmax
                    })

                    # Add a blank row after each group for better readability
                    csv_data.append({
                        'Type': '',
                        'Group Name': '',
                        'Container Name': '',
                        f'Lootmax in {file1_name}': '',
                        f'Lootmax in {file2_name}': '',
                        'Difference': ''
                    })

            # Add summary information at the end
            csv_data.append({
                'Type': 'Summary',
                'Group Name': 'Total Groups',
                'Container Name': '',
                f'Lootmax in {file1_name}': len(lootmax1),
                f'Lootmax in {file2_name}': len(lootmax2),
                'Difference': len(lootmax2) - len(lootmax1)
            })

            # Ensure the output file has .csv extension
            csv_output_file = self.output_file
            if not csv_output_file.lower().endswith('.csv'):
                name, ext = os.path.splitext(csv_output_file)
                csv_output_file = f"{name}.csv"

            # Write the CSV file using the base class method - no need to add timestamp here
            # since it was already added in _get_output_path
            resolved_path = self.write_csv(csv_data, csv_output_file, headers)

            if resolved_path:
                logger.info(f"Comparison results written to {resolved_path}")
                logger.info("CSV format uses separate 'Group Name' and 'Container Name' columns to represent hierarchy")
                self.output_file = resolved_path  # Update the output file path with the actual path
                return True
            return False

        except Exception as e:
            logger.error(f"Error comparing lootmax values: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def merge_lootmax(self) -> bool:
        """
        Merge lootmax values from file2 to file1 and save to specified output file.
        Preserves XML comments and maintains attribute ordering.
        Uses write_xml from base class for XML output.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check that merge output file is specified (should be set in setup_from_args)
            if not self.merge_output_file:
                logger.error("Merge output file not specified")
                return False

            # Parse source file (file2) to extract lootmax values
            source_root = self.read_xml_with_comments(self.file2)

            # Build lookup dictionary from source file
            source_values = {}
            self._build_lootmax_lookup(source_root, source_values)

            # Parse target file (file1) with comments preserved
            target_root = self.read_xml_with_comments(self.file1)

            # Update target with source values
            self._update_lootmax_values(target_root, source_values)

            # Write the merged XML using write_xml from base class
            logger.info(f"Writing merged XML to {self.merge_output_file}")
            self.write_xml(
                root=target_root,
                file_path=self.merge_output_file,
                pretty=True,
                xml_declaration=True
            )

            logger.info(
                f"Successfully merged lootmax values from {os.path.basename(self.file2)} "
                f"into {os.path.basename(self.file1)}")
            return True

        except Exception as e:
            logger.error(f"Error merging lootmax values: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def _build_lootmax_lookup(self, root, lookup_dict):
        """
        Build a lookup dictionary of lootmax values from the source XML.

        Args:
            root: XML root element
            lookup_dict: Dictionary to populate with lootmax values
        """
        # Process each group element
        for group in root.findall('group'):
            group_name = group.get('name')
            if group_name:
                # Store group lootmax
                group_lootmax = group.get('lootmax')
                if group_lootmax:
                    lookup_dict[f"group:{group_name}"] = group_lootmax

                # Store container lootmax values
                for container in group.findall('container'):
                    container_name = container.get('name')
                    container_lootmax = container.get('lootmax')
                    if container_name and container_lootmax:
                        lookup_dict[f"container:{group_name}:{container_name}"] = container_lootmax

    def _update_lootmax_values(self, root, source_values):
        """
        Update lootmax values in the target XML using the source values.

        Args:
            root: XML root element to update
            source_values: Dictionary with lootmax values from source
        """
        # Update group elements
        for group in root.findall('group'):
            group_name = group.get('name')
            if group_name:
                # Update group lootmax if available
                group_key = f"group:{group_name}"
                if group_key in source_values:
                    group.set('lootmax', source_values[group_key])
                    logger.debug(f"Updated group lootmax for {group_name}")

                # Update container lootmax values
                for container in group.findall('container'):
                    container_name = container.get('name')
                    if container_name:
                        container_key = f"container:{group_name}:{container_name}"
                        if container_key in source_values:
                            container.set('lootmax', source_values[container_key])
                            logger.debug(f"Updated container lootmax for {group_name}/{container_name}")

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
            self.output_dir, "lootmax_comparison.csv")

        # For merge output, check if merging was requested
        if args.merge is not None:  # The --merge flag was specified
            if args.merge:  # A specific filename was provided
                # Use _get_output_path to add timestamp and handle directory paths
                self.merge_output_file = self._get_output_path(args.merge)
            else:  # Just --merge with no value, use default name
                # Generate a default name with timestamp directly
                default_merge_filename = "merged_mapgroupproto.xml"
                self.merge_output_file = self._get_output_path(default_merge_filename)
                logger.info(f"Using default merge filename: {os.path.basename(self.merge_output_file)}")
        else:
            # No --merge flag was specified, don't create a merged file
            self.merge_output_file = None

        # Ensure output directories exist using the base class method
        if self.output_file:
            self.ensure_dir(os.path.dirname(self.output_file))
        if self.merge_output_file:
            self.ensure_dir(os.path.dirname(self.merge_output_file))

        # Log file paths
        logger.info(f"Input file 1: {self.file1}")
        logger.info(f"Input file 2: {self.file2}")
        logger.info(f"Comparison output file: {self.output_file}")
        if self.merge_output_file:
            logger.info(f"Merge output file: {self.merge_output_file}")

    def run(self) -> bool:
        """
        Run the Lootmax Comparer tool.

        Returns:
            True if successful, False otherwise
        """
        success = self.compare_lootmax()

        if success and self.merge_output_file:
            success = self.merge_lootmax()

        return success


def main():
    """
    Main entry point for the Lootmax Comparer tool when run as a script.
    """
    parser = argparse.ArgumentParser(
        description='Compare and merge lootmax values between mapgroupproto.xml files.\n'
        'Features:\n'
        '  - Outputs comparison data in CSV format with timestamps in filenames\n'
        '  - Preserves XML comments and structure during merges\n'
        '  - All output files include timestamps automatically\n'
        '  - Utilizes standard file I/O operations from the base library\n'
        '  - All output files will be placed in the directory specified by general.output_path config',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('file1',
                        help='First proto XML file')

    parser.add_argument('file2',
                        help='Second proto XML file')

    parser.add_argument('--output', '-o',
                        default='lootmax_comparison.csv',
                        help='Filename for comparison output (timestamp will be added automatically)')

    parser.add_argument('--merge', '-m',
                        nargs='?',  # Makes the argument optional but captures a value if provided
                        const='',   # Value used if --merge is provided without a value
                        help='Enable merging and optionally provide a filename (defaults to '
                             'merged_mapgroupproto.xml with timestamp)')

    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)

    args = parser.parse_args()

    # Initialize tool with config
    config = DayZTool.load_config(args.profile)
    tool = LootmaxComparer(config)
    tool.setup_from_args(args)

    # Run the tool
    success = tool.run()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

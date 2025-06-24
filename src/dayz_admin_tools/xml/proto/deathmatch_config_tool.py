"""
DayZ Deathmatch Configuration Tool

This module provides a simplified tool for creating DayZ Deathmatch server configurations
with three main steps:
1. Filter buildings within a specific coordinate box
2. Update the original mapgroupproto file by removing all usage tags
3. Apply a custom usage tag only to the buildings that were filtered by coordinates

The result is a ready-to-use configuration for DayZ Deathmatch servers with customized
loot spawning only in the desired areas.

All output files are stored in the directory specified by the general.output_path
configuration setting, making it easy to manage generated files.
"""

import argparse
import logging
import os
import sys
from typing import Dict, Any, Optional

from dayz_admin_tools.base import XMLTool, DayZTool

# Set up logger
logger = logging.getLogger(__name__)


class DeathmatchConfigTool(XMLTool):
    """
    Simplified tool for creating DayZ Deathmatch server configurations.
    
    This tool handles three main steps:
    1. Filter buildings within specific map coordinates
    2. Remove all usage tags from the proto file
    3. Apply a custom usage tag only to buildings that were filtered by coordinates
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the Deathmatch Configuration Tool.
        
        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        self.initialize_directories()
        
        # Files
        self.mapgrouppos_file = None
        self.filtered_pos_file = None
        self.mapgroupproto_file = None
        self.output_proto_file = None
        
        # Usage tag
        self.usage_tag = None
    
    def filter_buildings(self) -> bool:
        """
        Step 1: Filter buildings based on coordinates and write to output file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Step 1: Filtering buildings within coordinate box: "
                       f"({self.deathmatch_area[0][0]}, {self.deathmatch_area[0][1]}) to "
                       f"({self.deathmatch_area[1][0]}, {self.deathmatch_area[1][1]})")
            
            # Read source XML with comments preserved
            source_root = self.read_xml_with_comments(self.mapgrouppos_file)
            if source_root is None:
                logger.error("Failed to read source XML file")
                return False
                
            # Import the correct ElementTree module to match what read_xml_with_comments uses
            from dayz_admin_tools.base import ET
            
            # Create new root element using the same ElementTree library
            output_root = ET.Element(source_root.tag)
            # Copy attributes safely
            for key, value in source_root.attrib.items():
                output_root.set(key, value)
            
            # Track statistics
            total_buildings = 0
            filtered_buildings = 0
            filtered_group_names = set()
            
            # Process all elements
            for child in source_root:
                # Copy non-group elements (like header comments) directly
                if child.tag != 'group':
                    output_root.append(child)
                    continue
                
                # For group elements, check coordinates
                total_buildings += 1
                group_name = child.get('name', 'unknown')
                
                # Check if the group has a position
                pos_attr = child.get('pos')
                if pos_attr:
                    try:
                        # Extract and check coordinates
                        coords = pos_attr.split()
                        x, z = float(coords[0]), float(coords[2])  # x and z(y) coordinates
                        
                        # Determine if in box - deathmatch_area is [(ll_x, ll_y), (ur_x, ur_y)]
                        min_x = min(self.deathmatch_area[0][0], self.deathmatch_area[1][0])
                        max_x = max(self.deathmatch_area[0][0], self.deathmatch_area[1][0])
                        min_y = min(self.deathmatch_area[0][1], self.deathmatch_area[1][1])
                        max_y = max(self.deathmatch_area[0][1], self.deathmatch_area[1][1])
                        
                        in_box = (min_x <= x <= max_x) and (min_y <= z <= max_y)
                        
                        if in_box:
                            # Keep this building
                            filtered_buildings += 1
                            filtered_group_names.add(group_name)
                            output_root.append(child)
                            logger.debug(f"Including building '{group_name}' at position: {x}, {z}")
                    except (IndexError, ValueError) as e:
                        logger.warning(f"Skipping building with invalid coordinates: {group_name}, Error: {str(e)}")
            
            # Write filtered XML with pretty formatting
            self.write_xml(output_root, self.filtered_pos_file, pretty=True, xml_declaration=True)
            
            logger.info(f"Filtered {filtered_buildings} out of {total_buildings} buildings within coordinate box")
            logger.info(f"Filtered buildings saved to {self.filtered_pos_file}")
            
            # Store the filtered group names for later use
            self.filtered_group_names = filtered_group_names
            
            return True
            
        except Exception as e:
            logger.error(f"Error filtering buildings: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def configure_proto(self) -> bool:
        """
        Steps 2 & 3: Configure the proto file by removing all usage tags and 
        applying custom usage tag only to filtered buildings.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Step 2 & 3: Configuring proto file with usage tag '{self.usage_tag}'")
            
            # Read proto XML with comments preserved
            proto_root = self.read_xml_with_comments(self.mapgroupproto_file)
            if proto_root is None:
                logger.error("Failed to read proto XML file")
                return False
            
            # Import the correct ElementTree module to match what read_xml_with_comments uses
            from dayz_admin_tools.base import ET
            
            # Always use the dedicated output file path
            output_file = self.proto_output_file
            
            # Process all groups
            total_groups = 0
            updated_groups = 0
            
            for group in proto_root.findall('.//group'):
                total_groups += 1
                group_name = group.get('name', '')
                
                # Remove any existing usage/category tags
                # This needs to be done carefully to avoid issues with modifying during iteration
                for tag_type in ['usage', 'category', 'tag', 'value']:
                    tags_to_remove = list(group.findall(tag_type))
                    for tag in tags_to_remove:
                        group.remove(tag)
                
                # Add usage tag only if this building was in the filtered list
                if group_name in self.filtered_group_names:
                    # Create element using the same ET library
                    usage_elem = ET.Element('usage')
                    usage_elem.set('name', self.usage_tag)
                    group.insert(0, usage_elem)
                    
                    # Ensure there is a newline after the usage tag
                    group.text = '\n' + (group.text or '')
                    updated_groups += 1
                    logger.debug(f"Applied usage tag '{self.usage_tag}' to group '{group_name}'")
            
            # Write the updated proto file with pretty formatting
            self.write_xml(proto_root, output_file, pretty=True, xml_declaration=True)
            
            logger.info(f"Applied custom usage tag '{self.usage_tag}' to {updated_groups} out of {total_groups} groups")
            logger.info(f"Updated proto file saved to {output_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error configuring proto file: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def setup_from_args(self, args: argparse.Namespace) -> None:
        """
        Set up the tool from command line arguments.
        
        Args:
            args: Command line arguments
        """
        # Set input files (source files)
        self.mapgrouppos_file = self.resolve_path(args.mapgrouppos)
        self.mapgroupproto_file = self.resolve_path(args.mapgroupproto)
        
        # Make sure output directory is initialized
        if not hasattr(self, 'output_dir') or not self.output_dir:
            self.initialize_directories()
        
        # Get input file basenames for better naming of output files
        pos_basename = os.path.basename(self.mapgrouppos_file)
        proto_basename = os.path.basename(self.mapgroupproto_file)
        
        # Set filtered buildings output file
        if hasattr(args, 'pos_output') and args.pos_output:
            self.filtered_pos_file = self._get_output_path(args.pos_output)
        else:
            # Default filename in output directory using original filename pattern with timestamp
            default_pos_filename = f"deathmatch_{pos_basename}"
            self.filtered_pos_file = self._get_output_path(default_pos_filename)
        
        # Set proto output file
        if hasattr(args, 'proto_output') and args.proto_output:
            self.proto_output_file = self._get_output_path(args.proto_output)
        else:
            # Default filename in output directory using original filename pattern with timestamp
            default_proto_filename = f"deathmatch_{proto_basename}"
            self.proto_output_file = self._get_output_path(default_proto_filename)
        
        # Deathmatch area coordinates
        self.deathmatch_area = (
            (args.ll_x, args.ll_y),  # Lower left corner
            (args.ur_x, args.ur_y)   # Upper right corner
        )
        
        # Usage tag
        self.usage_tag = args.usage_tag
        
        # Initialize filtered group names
        self.filtered_group_names = set()
        
        # Ensure output directories exist using the base class method
        self.ensure_dir(os.path.dirname(self.filtered_pos_file))
        self.ensure_dir(os.path.dirname(self.proto_output_file))
            
        # Log configuration
        logger.info(f"Deathmatch area: {self.deathmatch_area}")
        logger.info(f"Usage tag: {self.usage_tag}")
        logger.info(f"Input mapgrouppos file: {self.mapgrouppos_file}")
        logger.info(f"Input mapgroupproto file: {self.mapgroupproto_file}")
        logger.info(f"Filtered buildings output file: {self.filtered_pos_file}")
        logger.info(f"Final proto output file: {self.proto_output_file}")

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
        if path is None:
            return None
            
        # Add timestamp to filename using base class method
        name, ext = os.path.splitext(os.path.basename(path))
        timestamped_filename = self.generate_timestamped_filename(name, ext.lstrip("."))
        
        if os.path.isabs(path):
            # Keep the same directory for absolute paths
            return self.resolve_path(os.path.join(os.path.dirname(path), timestamped_filename))
        else:
            # Relative path - put in output directory
            return os.path.join(self.output_dir, timestamped_filename)

    def run(self) -> bool:
        """
        Run the Deathmatch Configuration Tool.
        
        Returns:
            True if successful, False otherwise
        """
        # Step 1: Filter buildings by coordinates
        if not self.filter_buildings():
            logger.error("Building filtering failed. Aborting.")
            return False
            
        # Steps 2 & 3: Configure proto file (remove all tags, add custom tag to filtered buildings)
        if not self.configure_proto():
            logger.error("Proto file configuration failed.")
            return False
        
        logger.info("DayZ Deathmatch server configuration completed successfully!")
        return True


def main():
    """
    Main entry point for the Deathmatch Configuration Tool.
    """
    parser = argparse.ArgumentParser(
        description=
            'Configure DayZ Deathmatch server by filtering buildings and customizing loot spawns.\n'
            'Features:\n'
            '  - Filter buildings within a specified coordinate box\n'
            '  - Remove all existing usage tags from mapgroupproto\n'
            '  - Apply custom usage tag only to buildings within the coordinate box\n'
            '  - Add timestamps to output filenames automatically\n'
            '  - All output files will be placed in the directory specified by general.output_path config',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Files
    parser.add_argument('--mapgrouppos', '-p',
                      default='mapgrouppos.xml',
                      help='Path to the source mapgrouppos.xml file')
    
    parser.add_argument('--pos-output', '-f',
                      help='Filename for the filtered buildings output file (defaults to deathmatch_<original filename> with timestamp)')
    
    parser.add_argument('--mapgroupproto', '-m',
                      default='mapgroupproto.xml',
                      help='Path to the source mapgroupproto.xml file')
    
    parser.add_argument('--proto_output', '-o',
                      help='Filename for the final output proto file (defaults to deathmatch_<original filename> with timestamp)')
    
    # Coordinates
    parser.add_argument('--ur-x', '-ux',
                      type=float,
                      required=True,
                      help='Upper right X coordinate of the deathmatch area')
    
    parser.add_argument('--ur-y', '-uy',
                      type=float,
                      required=True,
                      help='Upper right Y coordinate of the deathmatch area')
    
    parser.add_argument('--ll-x', '-lx',
                      type=float,
                      required=True,
                      help='Lower left X coordinate of the deathmatch area')
    
    parser.add_argument('--ll-y', '-ly',
                      type=float,
                      required=True,
                      help='Lower left Y coordinate of the deathmatch area')
    
    # Usage tag
    parser.add_argument('--usage-tag', '-u',
                      default='Deathmatch',
                      help='Usage tag to apply (determines loot spawning)')
    
    # Logging options
    parser.add_argument('--verbose', '-v',
                      action='store_true',
                      help='Enable verbose logging')
    
    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Initialize tool with config
    config = DayZTool.load_config(args.profile)
    tool = DeathmatchConfigTool(config)
    tool.setup_from_args(args)
    
    # Run the tool
    success = tool.run()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

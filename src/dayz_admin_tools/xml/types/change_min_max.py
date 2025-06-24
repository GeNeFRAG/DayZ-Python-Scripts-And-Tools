"""
Change Min Max Tool

A tool for batch-updating quantmin and quantmax values in types.xml files.
Useful for quickly adjusting item quantities across multiple items matching a pattern.
Uses the 'paths.types_file' from the profile configuration by default.
"""

import xml.etree.ElementTree as ET
import argparse
import sys
import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Dict, Set

# Add support for the config system
from ...base import XMLTool, DayZTool

__all__ = ['ChangeMinMaxTool', 'main']

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


class ChangeMinMaxTool(XMLTool):
    """
    Tool for changing quantmin and quantmax values in types.xml files.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the ChangeMinMax tool.
        
        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)
        
        # Initialize common directories
        self.initialize_directories()
        
        # Get backup directory from config
        self.backup_dir = self.get_config('general.backup_directory', '../backups')
        
        # Resolve the backup directory path to an absolute path
        self.backup_dir = self.resolve_path(self.backup_dir)
        
        # Create backup directory if it doesn't exist
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Ensure default_types_file from config is set
        if not self.default_types_file:
            self.default_types_file = self.get_config('paths.types_file')
            if not self.default_types_file:
                logger.warning("No default types.xml file path configured in profile")
            else:
                logger.debug(f"Using default types file from config: {self.default_types_file}")
            
        logger.debug(f"Backup directory: {self.backup_dir}")
        logger.debug(f"Default types file: {self.default_types_file}")

    def update_quantities(self, xml_file: str, pattern: str, quantmin: int, 
                         quantmax: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Update quantmin and quantmax values for types matching the pattern,
        except where values are -1.
        
        Args:
            xml_file: Path to types.xml
            pattern: Wildcard pattern to match type names
            quantmin: New quantmin value
            quantmax: New quantmax value
            
        Returns:
            Tuple of (changes, skipped) lists
        """
        logger.info(f"Updating quantities in {xml_file} for pattern '{pattern}'")
        logger.info(f"Setting quantmin={quantmin}, quantmax={quantmax}")
        
        # Resolve the input XML file path
        xml_file_abs = self.resolve_path(xml_file)
        
        # Create a backup before making changes - use direct file copy to preserve all content exactly
        try:
            from pathlib import Path
            from datetime import datetime
            import shutil
            
            # Format backup filename using base class method
            source_path = Path(xml_file_abs)
            backup_filename = self.generate_timestamped_filename(source_path.stem, source_path.suffix.lstrip("."))
            backup_path = Path(self.backup_dir) / backup_filename
            
            # Ensure backup directory exists
            os.makedirs(Path(self.backup_dir), exist_ok=True)
            
            # Copy the file directly to preserve comments and all content
            shutil.copy2(str(source_path), str(backup_path))
            
            logger.info(f"Created backup with preserved comments at: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}")
            raise RuntimeError(f"Failed to create backup: {str(e)}")
        
        try:
            # Read the XML with comments preserved
            root = self.read_xml_with_comments(xml_file_abs)
            changes = []
            skipped = []
            
            # Use filter_types_by_name from the base class
            matching_types = self.filter_types_by_name(root, pattern)
            
            # Use get_type_values from base class to extract current values
            for type_elem in matching_types:
                type_values = self.get_type_values(type_elem, ['quantmin', 'quantmax'])
                type_name = type_values['name']
                old_min = type_values.get('quantmin')
                old_max = type_values.get('quantmax')
                
                # Skip if elements don't exist or either value is -1
                if not old_min or not old_max or old_min == '-1' or old_max == '-1':
                    skipped.append({
                        'name': type_name,
                        'min': old_min,
                        'max': old_max
                    })
                    logger.debug(f"Skipping '{type_name}' because quantmin={old_min}, quantmax={old_max}")
                    continue
                
                # Update the values
                min_elem = type_elem.find('quantmin')
                max_elem = type_elem.find('quantmax')
                
                min_elem.text = str(quantmin)
                max_elem.text = str(quantmax)
                
                changes.append({
                    'name': type_name,
                    'old_min': old_min,
                    'old_max': old_max,
                    'new_min': quantmin,
                    'new_max': quantmax
                })
                logger.debug(f"Updating '{type_name}': quantmin={old_min}->{quantmin}, quantmax={old_max}->{quantmax}")
            
            if changes:
                # Use write_xml from base class - will now handle comment preservation better with our fixed method
                self.write_xml(root, xml_file_abs, pretty=True, xml_declaration=True)
                logger.info(f"Updated {len(changes)} types in {xml_file_abs}")
                
            return changes, skipped
            
        except Exception as e:
            logger.error(f"Error processing XML file: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            raise RuntimeError(f"Error processing XML file: {str(e)}")

    def run(self, pattern: str, quantmin: int, quantmax: int, 
            xml_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the ChangeMinMax tool.
        
        Args:
            pattern: Wildcard pattern to match type names
            quantmin: New quantmin value
            quantmax: New quantmax value
            xml_file: Path to types.xml file (uses paths.types_file from config if None)
            
        Returns:
            Dictionary with results information
        """
        # Validate input
        if quantmin > quantmax:
            logger.error("Error: quantmin cannot be greater than quantmax")
            return {"error": "quantmin cannot be greater than quantmax"}
        
        # First check if an explicit XML file was provided
        if xml_file:
            file_path = xml_file
        else:
            # Otherwise use the types_file from the profile config
            file_path = self.default_types_file
            
        if not file_path:
            logger.error("No types.xml file specified and no 'paths.types_file' configured in profile")
            return {"error": "No types.xml file specified and no 'paths.types_file' configured in profile"}
        
        # Resolve the file path
        file_path = self.resolve_path(file_path)
        logger.info(f"Using types.xml file: {file_path}")
        logger.info(f"Backups will be stored in: {self.backup_dir}")
        
        try:
            changes, skipped = self.update_quantities(
                file_path, 
                pattern, 
                quantmin, 
                quantmax
            )
            
            if not changes and not skipped:
                logger.warning(f"No types found matching pattern: {pattern}")
                return {
                    "warning": f"No types found matching pattern: {pattern}"
                }
            
            # Return results
            return {
                "success": True,
                "file": file_path,
                "changes": changes,
                "skipped": skipped,
                "changes_count": len(changes),
                "skipped_count": len(skipped),
                "backup_directory": self.backup_dir
            }
                
        except FileNotFoundError:
            logger.error(f"Error: Could not find file '{file_path}'")
            return {"error": f"Could not find file '{file_path}'"}
        except ET.ParseError:
            logger.error(f"Error: Could not parse XML file '{file_path}'")
            return {"error": f"Could not parse XML file '{file_path}'"}
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return {"error": str(e)}


def main():
    """
    Main entry point for the command-line script.
    """
    parser = argparse.ArgumentParser(
        description='Update quantmin and quantmax values in types.xml (except where -1)'
    )
    parser.add_argument('--pattern', required=True,
        help='Wildcard pattern to match type names (e.g., "Ammo*")'
    )
    parser.add_argument('--quantmin', type=int, required=True,
        help='New quantmin value'
    )
    parser.add_argument('--quantmax', type=int, required=True,
        help='New quantmax value'
    )
    parser.add_argument('--xml', 
        help='Path to types.xml file (uses paths.types_file from profile config if not specified)'
    )
    
    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)
    
    args = parser.parse_args()
    
    # Load configuration
    config = DayZTool.load_config(args.profile)
    
    # Set up console logging for user output
    setup_console_logging()
    
    # Initialize the tool
    tool = ChangeMinMaxTool(config)
    
    # Run the tool
    result = tool.run(
        args.pattern,
        args.quantmin,
        args.quantmax,
        args.xml
    )
    
    if "error" in result:
        logger.error(f"Error: {result['error']}")
        sys.exit(1)
    elif "warning" in result:
        logger.warning(result["warning"])
        sys.exit(0)
    
    # Process results
    changes = result["changes"]
    skipped = result["skipped"]
    
    if changes:
        logger.info(f"\nTypes updated ({len(changes)}):")
        for change in changes:
            logger.info(f"\n- {change['name']}:")
            logger.info(f"  quantmin: {change['old_min']} → {change['new_min']}")
            logger.info(f"  quantmax: {change['old_max']} → {change['new_max']}")
    
    if skipped:
        logger.info(f"\nSkipped types with -1 values ({len(skipped)}):")
        for skip in skipped:
            logger.info(f"\n- {skip['name']}:")
            logger.info(f"  quantmin: {skip['min']}")
            logger.info(f"  quantmax: {skip['max']}")
    
    logger.info(f"\nSummary:")
    logger.info(f"- Updated {len(changes)} types")
    logger.info(f"- Skipped {len(skipped)} types")
    logger.info(f"- Backup saved to: {result['backup_directory']}")

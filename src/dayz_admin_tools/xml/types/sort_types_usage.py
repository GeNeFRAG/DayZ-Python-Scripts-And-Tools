"""
Sort Types Usage Tool

A tool for sorting items in a types.xml file by their usage categories and adding an index.
This provides a better organization for large types.xml files, making them easier to navigate.
"""

import argparse
import logging
import os
from typing import Dict,Optional, Any

# Add support for the config system
# Import ET from base to ensure consistency between lxml and standard ElementTree
from ...base import XMLTool, HAS_LXML, DayZTool, ET

__all__ = ['SortTypesUsageTool', 'main']

# Configure logging
logger = logging.getLogger(__name__)


class SortTypesUsageTool(XMLTool):
    """Tool for sorting items in types.xml by usage categories."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the sort types usage tool.
        
        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)
        
        # Initialize common directories
        self.initialize_directories()
        
        # Get backup directory from config
        self.backup_dir = self.get_config('general.backup_directory', 'backups')
        
        # Create backup directory if it doesn't exist
        os.makedirs(self.resolve_path(self.backup_dir), exist_ok=True)
        
        # Ensure default_types_file from config is set
        if not self.default_types_file:
            self.default_types_file = self.get_config('paths.types_file')
            
        logger.debug(f"Backup directory: {self.backup_dir}")
        logger.debug(f"Default types file: {self.default_types_file}")
    
    def organize_types_xml(self, xml_file: str) -> None:
        """
        Organize and sort the types.xml file by usage categories.
        
        Args:
            xml_file: Path to the types.xml file
        """
        logger.info(f"Reading and organizing {xml_file}")
        
        # Use the base class method to sort the XML file by usage categories
        self.sort_xml_by_usage(xml_file, xml_file, add_index=True)
        
        logger.info(f"Sorted XML written back to {xml_file}")
    
    def run(self, xml_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the sort types usage tool.
        
        Args:
            xml_file: Optional path to types.xml file (uses paths.types_file from config if None)
            
        Returns:
            Dictionary with results information
        """
        try:
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
            
            # Create backup
            backup_file = self.backup_file(file_path, self.backup_dir)
            logger.info(f"Created backup: {backup_file}")
            
            # Sort and organize the types.xml file
            self.organize_types_xml(file_path)
            
            return {
                "success": True,
                "file": file_path,
                "backup_file": backup_file
            }
                
        except FileNotFoundError:
            logger.error(f"Error: Could not find file '{file_path}'")
            return {"error": f"Could not find file '{file_path}'"}
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return {"error": str(e)}


def main():
    """Main function for the sort types usage tool."""
    parser = argparse.ArgumentParser(
        description='Sort types.xml by usage categories and add indexes for better organization.'
    )
    parser.add_argument('--xml', 
        help='Path to types.xml file (uses paths.types_file from profile config if not specified)'
    )
    
    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = SortTypesUsageTool.load_config(args.profile)
        
        # Create and run the tool
        tool = SortTypesUsageTool(config)
        result = tool.run(args.xml if args.xml else None)
        
        if "error" in result:
            logger.error(f"Error: {result['error']}")
            return 1
            
        logger.info(f"\nSuccessfully organized types.xml:")
        logger.info(f"- File: {result['file']}")
        logger.info(f"- Backup created at: {result['backup_file']}")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        logger.debug(traceback.format_exc())
        return 1
        
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

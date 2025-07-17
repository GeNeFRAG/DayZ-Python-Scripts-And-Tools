"""
Sum Static Mildrop Items Tool

A tool that sums items in a static military drop event configuration 
and generates a count of each item type for further analysis.
"""

import logging
import argparse
from typing import Dict, Optional, Any

from .static_event_counter import EventCounter
from ...base import DayZTool

__all__ = ['SumStaticMilDropItemsTool', 'main']

# Configure logging
logger = logging.getLogger(__name__)


class SumStaticMilDropItemsTool(EventCounter):
    """Tool for summing items in static military drops."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the sum static mil drop items tool.
        
        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)
        
        # Set default ignore types for mildrop event
        self.ignore_types = {"Land_Container_1Moh_DE", "Wreck_UH1Y"}
    
    def run(self, events_path: Optional[str] = None, groups_path: Optional[str] = None, 
            output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the sum static mil drop items tool.
        
        Args:
            events_path: Path to the events.xml file (uses paths.events_file from config if None)
            groups_path: Path to the cfgeventgroups.xml file (uses paths.eventgroups_file from config if None)
            output_path: Path to the output CSV file (defaults to md_loot.csv in output directory)
            
        Returns:
            Dictionary with results information
        """
        # Call the shared implementation with StaticMildrop-specific parameters
        result = super().run(
            events_path=events_path,
            groups_path=groups_path,
            output_path=output_path or "md_loot.csv",
            event_pattern=None,
            specific_event="StaticMildrop",
            group_name="Mildrop"
        )
        
        # Add mildrop-specific information
        if "success" in result:
            result["ignored_types"] = list(self.ignore_types)
            
        return result


def main():
    """Main function for the sum static mil drop items tool."""
    parser = argparse.ArgumentParser(
        description='Sum items in a static military drop event configuration.'
    )
    parser.add_argument('--events', 
        help='Path to the events.xml file (uses paths.events_file from config if not specified)',
        dest='events_xml'
    )
    parser.add_argument('--groups', 
        help='Path to the cfgeventgroups.xml file (uses paths.eventgroups_file from config if not specified)',
        dest='groups_xml'
    )
    parser.add_argument('--output', 
        help='Path to the output CSV file (defaults to md_loot.csv in standard output directory)',
        dest='output_csv'
    )
    parser.add_argument('--debug', 
        help='Enable debug logging',
        action='store_true'
    )
    
    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)
    
    args = parser.parse_args()
    
    # Set up logging level
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format='%(message)s')
    
    try:
        # Load configuration
        config = SumStaticMilDropItemsTool.load_config(args.profile)
        
        # Create and run the tool
        tool = SumStaticMilDropItemsTool(config)
        logger.debug("Initialized tool with configuration")
        
        result = tool.run(args.events_xml, args.groups_xml, args.output_csv)
        
        if "error" in result:
            logger.error(f"Error during tool execution: {result['error']}")
            return 1
        
        # Display results
        logger.info("\nAnalysis complete:")
        logger.info(f"- Events file: {result['events_file']}")
        logger.info(f"- Groups file: {result['groups_file']}")
        logger.info(f"- Event active: {'Yes' if result['active'] else 'No'}")
        total_items = 0
        if result['active']:
            total_items = result['total_items']
            logger.info(f"- Nominal value: {result['nominal']}")
            logger.info(f"- Total items: {total_items}")
            logger.info(f"- Ignored types: {', '.join(result['ignored_types'])}")
        logger.info(f"- Results written to: {result['output_file']}")
        
        # Print total count for shell script consumption
        print(f"TOTAL_COUNT={total_items}")
        
        # Return total count
        return total_items
        
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
        if args.debug:
            import traceback
            logger.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

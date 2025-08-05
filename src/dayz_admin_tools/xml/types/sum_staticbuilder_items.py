"""
Sum Static Builder Items Tool

A tool that sums items in static builder events configuration 
and generates a count of each item type for further analysis.
"""

import logging
import argparse
from typing import Dict, Optional, Any

from .static_event_counter import EventCounter
from ...base import DayZTool

__all__ = ['SumStaticBuilderItemsTool', 'main']

# Configure logging
logger = logging.getLogger(__name__)


class SumStaticBuilderItemsTool(EventCounter):
    """Tool for summing items in static builder events."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the sum static builder items tool.
        
        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)
    
    def run(self, events_path: Optional[str] = None, groups_path: Optional[str] = None, 
            output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the sum static builder items tool.
        
        Args:
            events_path: Path to the events.xml file (uses paths.events_file from config if None)
            groups_path: Path to the cfgeventgroups.xml file (uses paths.eventgroups_file from config if None)
            output_path: Path to the output CSV file (defaults to sb_loot.csv in output directory)
            
        Returns:
            Dictionary with results information
        """
        # Call the shared implementation with StaticBuilder-specific parameters
        return super().run(
            events_path=events_path,
            groups_path=groups_path,
            output_path=output_path,
            event_pattern="StaticBuilder_",
            group_name="SkullsMaterials"
        )


def main():
    """Main function for the sum static builder items tool."""
    parser = argparse.ArgumentParser(
        description='Sum items in static builder events configuration.'
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
        help='Path to the output CSV file (defaults to sb_loot.csv in standard output directory)',
        dest='output_csv'
    )
    
    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)
    
    args = parser.parse_args()
    
    try:
        # Load configuration using the static method from the tool class
        config = SumStaticBuilderItemsTool.load_config(args.profile)
        
        # Create and run the tool
        tool = SumStaticBuilderItemsTool(config)
        result = tool.run(args.events_xml, args.groups_xml, args.output_csv)
        
        if "error" in result:
            logger.error(f"Error: {result['error']}")
            return 1
            
        # Display results
        total_items = result['total_items']
        logger.info(f"\nAnalysis complete:")
        logger.info(f"- Events file: {result['events_file']}")
        logger.info(f"- Groups file: {result['groups_file']}")
        logger.info(f"- Event spawns file: {result['eventspawns_file']}")
        logger.info(f"- Event consistency validation: {'PASSED' if result['validation']['valid'] else 'FAILED'}")
        logger.info(f"- Active StaticBuilder events: {result['active_events']}")
        logger.info(f"- Total items: {total_items}")
        logger.info(f"- Results written to: {result['output_file']}")
        
        # Display validation details if requested
        validation = result['validation']
        if not validation['valid']:
            logger.warning("\nValidation Issues Found:")
            if validation['events_without_spawns']:
                logger.warning(f"Events without spawn positions: {', '.join(validation['events_without_spawns'])}")
            if validation['spawns_without_events']:
                logger.warning(f"Spawn positions without event definitions: {', '.join(validation['spawns_without_events'])}")
        
        # Print total count for shell script consumption
        print(f"TOTAL_COUNT={total_items}")
        
        # Return total count
        return total_items
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        import traceback
        logging.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

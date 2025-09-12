"""
Sum Static Mildrop Items Tool

A tool that sums items in static military drop event configurations 
and generates a count of each item type for further analysis.

Supports three modes:
- Standard: Analyzes StaticMildrop events with Mildrop groups
- Special: Analyzes StaticMildropSpecial events with MildropSpecial groups  
- Both: Analyzes both types simultaneously and provides combined totals
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
    """
    Tool for summing items in static military drops.
    
    This tool can analyze different types of mildrop events:
    - StaticMildrop events with Mildrop groups (standard)
    - StaticMildropSpecial events with MildropSpecial groups (special)
    - Both types simultaneously for comprehensive analysis
    
    The tool automatically generates appropriate output filenames based on the event type
    and provides detailed analysis results including item counts and totals.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, 
                 event_pattern: str = "StaticMildrop", 
                 group_name: str = "Mildrop") -> None:
        """
        Initialize the sum static mil drop items tool.
        
        Args:
            config: Optional configuration dictionary
            event_pattern: Event pattern to match (e.g., "StaticMildrop", "StaticMildropSpecial")
            group_name: Group name to analyze (e.g., "Mildrop", "MildropSpecial")
        """
        super().__init__(config)
        
        # Store event configuration
        self.event_pattern = event_pattern
        self.group_name = group_name
        
        # Set default ignore types for mildrop event
        self.ignore_types = {"Land_Container_1Moh_DE", "Wreck_UH1Y"}
    
    @classmethod
    def for_standard_mildrop(cls, config: Optional[Dict[str, Any]] = None) -> 'SumStaticMilDropItemsTool':
        """
        Create a tool instance for standard mildrop events (StaticMildrop/Mildrop).
        
        Args:
            config: Optional configuration dictionary
            
        Returns:
            Configured tool instance for standard mildrop events
        """
        return cls(config=config, event_pattern="StaticMildrop", group_name="Mildrop")
    
    @classmethod
    def for_special_mildrop(cls, config: Optional[Dict[str, Any]] = None) -> 'SumStaticMilDropItemsTool':
        """
        Create a tool instance for special mildrop events (StaticMildropSpecial/MildropSpecial).
        
        Args:
            config: Optional configuration dictionary
            
        Returns:
            Configured tool instance for special mildrop events
        """
        return cls(config=config, event_pattern="StaticMildropSpecial", group_name="MildropSpecial")
    
    @classmethod
    def run_both_analyses(cls, config: Optional[Dict[str, Any]] = None,
                         events_path: Optional[str] = None,
                         groups_path: Optional[str] = None,
                         output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Run both standard and special mildrop analyses.
        
        Args:
            config: Optional configuration dictionary
            events_path: Path to the events.xml file
            groups_path: Path to the cfgeventgroups.xml file
            output_path: Base output path (will be used as prefix for separate files)
            
        Returns:
            Dictionary with combined results from both analyses
        """
        # Create tool instances
        standard_tool = cls.for_standard_mildrop(config)
        special_tool = cls.for_special_mildrop(config)
        
        # Run analyses
        standard_result = standard_tool.run(events_path, groups_path, output_path)
        special_result = special_tool.run(events_path, groups_path, output_path)
        
        # Combine results
        combined_result = {
            "standard": standard_result,
            "special": special_result,
            "combined_total": 0,
            "success": True
        }
        
        # Calculate combined totals
        if "success" in standard_result and standard_result.get("active", False):
            combined_result["combined_total"] += standard_result.get("total_items", 0)
        if "success" in special_result and special_result.get("active", False):
            combined_result["combined_total"] += special_result.get("total_items", 0)
        
        # Check for errors
        if "error" in standard_result or "error" in special_result:
            combined_result["success"] = False
            errors = []
            if "error" in standard_result:
                errors.append(f"Standard: {standard_result['error']}")
            if "error" in special_result:
                errors.append(f"Special: {special_result['error']}")
            combined_result["error"] = "; ".join(errors)
        
        return combined_result
    
    def run(self, events_path: Optional[str] = None, groups_path: Optional[str] = None, 
            output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the sum static mil drop items tool.
        
        Args:
            events_path: Path to the events.xml file (uses paths.events_file from config if None)
            groups_path: Path to the cfgeventgroups.xml file (uses paths.eventgroups_file from config if None)
            output_path: Path to the output CSV file (defaults to pattern-specific filename in output directory)
            
        Returns:
            Dictionary with results information
        """
        # Generate default output filename based on event pattern
        if not output_path:
            if self.event_pattern == "StaticMildropSpecial":
                output_path = "md_special_loot.csv"
            else:
                output_path = "md_loot.csv"
        
        # Call the shared implementation with configured parameters
        result = super().run(
            events_path=events_path,
            groups_path=groups_path,
            output_path=output_path,
            event_pattern=self.event_pattern,
            group_name=self.group_name
        )
        
        # Add mildrop-specific information
        if "success" in result:
            result["ignored_types"] = list(self.ignore_types)
            result["event_pattern"] = self.event_pattern
            result["group_name"] = self.group_name
            
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
        help='Path to the output CSV file (defaults to pattern-specific filename in standard output directory)',
        dest='output_csv'
    )
    parser.add_argument('--type', 
        help='Type of mildrop to analyze: "standard" for StaticMildrop/Mildrop, "special" for StaticMildropSpecial/MildropSpecial, or "both" to analyze both types (default: standard)',
        dest='mildrop_type',
        choices=['standard', 'special', 'both'],
        default='standard'
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
        
        # Handle different analysis types
        if args.mildrop_type == 'both':
            logger.info("Analyzing both standard and special mildrop events...")
            
            # Analyze standard mildrop
            standard_tool = SumStaticMilDropItemsTool.for_standard_mildrop(config)
            logger.debug("Initialized tool for StaticMildrop/Mildrop events")
            standard_result = standard_tool.run(args.events_xml, args.groups_xml, args.output_csv)
            
            if "error" in standard_result:
                logger.error(f"Error during standard mildrop analysis: {standard_result['error']}")
                return 1
            
            # Analyze special mildrop
            special_tool = SumStaticMilDropItemsTool.for_special_mildrop(config)
            logger.debug("Initialized tool for StaticMildropSpecial/MildropSpecial events")
            special_result = special_tool.run(args.events_xml, args.groups_xml, args.output_csv)
            
            if "error" in special_result:
                logger.error(f"Error during special mildrop analysis: {special_result['error']}")
                return 1
            
            # Display combined results
            logger.info("\n=== COMBINED ANALYSIS COMPLETE ===")
            
            # Standard mildrop results
            logger.info(f"\n--- Standard Mildrop (StaticMildrop/Mildrop) ---")
            logger.info(f"- Events file: {standard_result['events_file']}")
            logger.info(f"- Groups file: {standard_result['groups_file']}")
            logger.info(f"- Event active: {'Yes' if standard_result['active'] else 'No'}")
            standard_total = 0
            if standard_result['active']:
                standard_total = standard_result['total_items']
                logger.info(f"- Nominal value: {standard_result['nominal']}")
                logger.info(f"- Total items: {standard_total}")
            logger.info(f"- Results written to: {standard_result['output_file']}")
            
            # Special mildrop results
            logger.info(f"\n--- Special Mildrop (StaticMildropSpecial/MildropSpecial) ---")
            logger.info(f"- Events file: {special_result['events_file']}")
            logger.info(f"- Groups file: {special_result['groups_file']}")
            logger.info(f"- Event active: {'Yes' if special_result['active'] else 'No'}")
            special_total = 0
            if special_result['active']:
                special_total = special_result['total_items']
                logger.info(f"- Nominal value: {special_result['nominal']}")
                logger.info(f"- Total items: {special_total}")
            logger.info(f"- Results written to: {special_result['output_file']}")
            
            # Combined totals
            combined_total = standard_total + special_total
            logger.info(f"\n--- Combined Totals ---")
            logger.info(f"- Standard mildrop total: {standard_total}")
            logger.info(f"- Special mildrop total: {special_total}")
            logger.info(f"- Combined total: {combined_total}")
            
            # Print total count for shell script consumption
            print(f"STANDARD_COUNT={standard_total}")
            print(f"SPECIAL_COUNT={special_total}")
            print(f"TOTAL_COUNT={combined_total}")
            
            return combined_total
            
        else:
            # Handle single type analysis (existing logic)
            if args.mildrop_type == 'special':
                tool = SumStaticMilDropItemsTool.for_special_mildrop(config)
                logger.debug("Initialized tool for StaticMildropSpecial/MildropSpecial events")
            else:
                tool = SumStaticMilDropItemsTool.for_standard_mildrop(config)
                logger.debug("Initialized tool for StaticMildrop/Mildrop events")
            
            result = tool.run(args.events_xml, args.groups_xml, args.output_csv)
            
            if "error" in result:
                logger.error(f"Error during tool execution: {result['error']}")
                return 1
            
            # Display results
            logger.info("\nAnalysis complete:")
            logger.info(f"- Event pattern: {result['event_pattern']}")
            logger.info(f"- Group name: {result['group_name']}")
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

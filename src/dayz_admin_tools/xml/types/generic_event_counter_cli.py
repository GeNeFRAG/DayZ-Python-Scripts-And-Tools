"""
Generic Static Event Counter CLI Tool

A configurable command-line tool for counting items in static events.
Event types are defined in the configuration file.
"""

import logging
import argparse
from typing import Dict, Optional, Any

from .static_event_counter import GenericEventCounter
from ...base import DayZTool

__all__ = ['main']

logger = logging.getLogger(__name__)


def display_results(result: Dict[str, Any], event_type: Optional[str] = None) -> int:
    """
    Display results for the analysis.

    Args:
        result: Analysis result dictionary
        event_type: Optional event type name for display

    Returns:
        Total item count (0 if error)
    """
    if "error" in result:
        logger.error(f"Error during tool execution: {result['error']}")
        return 0

    # Display results
    logger.info("\nAnalysis complete:")
    if event_type:
        logger.info(f"- Event type: {event_type}")
    logger.info(f"- Event pattern: {result['event_pattern']}")
    logger.info(f"- Group name: {result['group_name']}")
    logger.info(f"- Events file: {result['events_file']}")
    logger.info(f"- Groups file: {result['groups_file']}")
    logger.info(f"- Event spawns file: {result['eventspawns_file']}")
    logger.info(f"- Event consistency validation: {'PASSED' if result['validation']['valid'] else 'FAILED'}")
    logger.info(f"- Event active: {'Yes' if result['active'] else 'No'}")
    
    total_items = 0
    if result['active']:
        total_items = result['total_items']
        logger.info(f"- Active events: {result['active_events']}")
        logger.info(f"- Nominal value: {result['nominal']}")
        logger.info(f"- Total items: {total_items}")
        if result.get('ignored_types'):
            logger.info(f"- Ignored types: {', '.join(result['ignored_types'])}")
    logger.info(f"- Results written to: {result['output_file']}")

    # Display validation details if there were issues
    validation = result['validation']
    if not validation['valid']:
        logger.warning("\nValidation Issues Found:")
        if validation['events_without_spawns']:
            logger.warning(f"Events without spawn positions: {', '.join(validation['events_without_spawns'])}")
        if validation['spawns_without_events']:
            logger.warning(
                f"Spawn positions without event definitions: {', '.join(validation['spawns_without_events'])}")

    # Print total count for shell script consumption
    print(f"TOTAL_COUNT={total_items}")

    return total_items


def main():
    """Main function for the generic static event counter tool."""
    parser = argparse.ArgumentParser(
        description='Count items in static events using configurable event definitions.'
    )
    parser.add_argument('--type',
                        help='Event type to analyze (from config event_definitions)',
                        dest='event_type'
                        )
    parser.add_argument('--list-types',
                        help='List all available event types from configuration',
                        action='store_true',
                        dest='list_types'
                        )
    parser.add_argument('--events',
                        help='Path to the events.xml file (uses paths.events_file from config if not specified)',
                        dest='events_xml'
                        )
    parser.add_argument('--groups',
                        help='Path to the cfgeventgroups.xml file (uses paths.event_groups_file from config if not '
                             'specified)',
                        dest='groups_xml'
                        )
    parser.add_argument('--output',
                        help='Path to the output CSV file (uses event type configuration if not specified)',
                        dest='output_csv'
                        )
    parser.add_argument('--pattern',
                        help='Event pattern to match (overrides event type configuration)',
                        dest='event_pattern'
                        )
    parser.add_argument('--group',
                        help='Group name to analyze (overrides event type configuration)',
                        dest='group_name'
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
        config = GenericEventCounter.load_config(args.profile)
        tool = GenericEventCounter(config)

        # Handle list types request
        if args.list_types:
            available_types = tool.list_available_event_types()
            if available_types:
                logger.info("Available event types:")
                for event_type in available_types:
                    definition = tool.get_event_definition(event_type)
                    logger.info(f"  {event_type}: {definition.get('description', 'No description')}")
                    logger.info(f"    Pattern: {definition['event_pattern']}")
                    logger.info(f"    Group: {definition['group_name']}")
                    logger.info(f"    Output: {definition['output_file']}")
                    if definition.get('ignore_types'):
                        logger.info(f"    Ignores: {', '.join(definition['ignore_types'])}")
                    logger.info("")
            else:
                logger.warning("No event types configured in event_definitions")
            return 0

        # Handle event type vs manual configuration
        if args.event_type:
            # Use configured event type
            logger.info(f"Analyzing event type: {args.event_type}")
            result = tool.run_by_event_type(
                event_type=args.event_type,
                events_path=args.events_xml,
                groups_path=args.groups_xml,
                output_path=args.output_csv
            )
            return 0 if display_results(result, args.event_type) > 0 else 1

        elif args.event_pattern and args.group_name:
            # Use manual configuration
            logger.info(f"Using manual configuration - Pattern: {args.event_pattern}, Group: {args.group_name}")
            result = tool.run(
                events_path=args.events_xml,
                groups_path=args.groups_xml,
                output_path=args.output_csv,
                event_pattern=args.event_pattern,
                group_name=args.group_name
            )
            return 0 if display_results(result) > 0 else 1

        else:
            # Show help - neither event type nor manual config provided
            logger.error("Error: Must specify either --type (event type) or both --pattern and --group")
            logger.info("\nUse --list-types to see available configured event types")
            logger.info("Or provide --pattern and --group for manual configuration")
            return 1

    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
        if args.debug:
            import traceback
            logger.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
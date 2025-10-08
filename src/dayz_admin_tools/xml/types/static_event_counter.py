"""
Generic Static Event Counter

A configurable tool for counting items in static events.
Event definitions are configured in the config file rather than hardcoded.
"""

import logging
from typing import Dict, Optional, Any, List
from collections import Counter
import xml.etree.ElementTree as ET

from ...base import EventAnalyzerTool

logger = logging.getLogger(__name__)


class GenericEventCounter(EventAnalyzerTool):
    """
    Generic tool for counting items in static events.
    Event configurations are loaded from the config file.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the generic event counter.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)
        self.initialize_directories()

    def get_event_definition(self, event_type: str) -> Dict[str, Any]:
        """
        Get event definition from configuration.

        Args:
            event_type: The type of event to get definition for

        Returns:
            Dictionary with event definition

        Raises:
            ValueError: If event type is not configured
        """
        event_definitions = self.get_config('event_definitions', {})
        
        if event_type not in event_definitions:
            available_types = list(event_definitions.keys())
            raise ValueError(f"Event type '{event_type}' not found in configuration. "
                           f"Available types: {available_types}")
        
        definition = event_definitions[event_type]
        
        # Validate required fields
        required_fields = ['event_pattern', 'group_name', 'output_file']
        missing_fields = [field for field in required_fields if field not in definition]
        if missing_fields:
            raise ValueError(f"Event definition for '{event_type}' missing required fields: {missing_fields}")
        
        return definition

    def list_available_event_types(self) -> List[str]:
        """
        List all available event types from configuration.

        Returns:
            List of available event type names
        """
        event_definitions = self.get_config('event_definitions', {})
        return list(event_definitions.keys())

    def validate_event_consistency(self, events_path: str, eventspawns_path: str,
                                   event_pattern: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate that event definitions are consistent between events.xml and cfgeventspawns.xml.

        This checks that:
        1. Every event defined in events.xml has corresponding spawn positions in cfgeventspawns.xml
        2. Every event with spawn positions in cfgeventspawns.xml has a definition in events.xml

        Args:
            events_path: Path to the events.xml file
            eventspawns_path: Path to the cfgeventspawns.xml file
            event_pattern: Optional pattern to filter events (e.g., "StaticBuilder_"). If provided,
                          only events matching this pattern will be validated.

        Returns:
            Dictionary with validation results

        Raises:
            ValueError: If inconsistencies are found between the files
        """
        if event_pattern:
            logger.info(f"Validating event consistency for events matching pattern '{event_pattern}*'")
        else:
            logger.info("Validating event consistency between events.xml and cfgeventspawns.xml")

        # Read events.xml to get defined events
        logger.info(f"Reading events from: {events_path}")
        events_root = self.read_xml(events_path)
        defined_events = set()

        for event in events_root.findall('event'):
            event_name = event.get('name')
            if event_name:
                if event_pattern is None or event_name.startswith(event_pattern):
                    defined_events.add(event_name)

        # Read cfgeventspawns.xml to get events with spawn positions
        logger.info(f"Reading event spawns from: {eventspawns_path}")
        eventspawns_root = self.read_xml(eventspawns_path)
        spawned_events = set()

        for event in eventspawns_root.findall('event'):
            event_name = event.get('name')
            if event_name:
                if event_pattern is None or event_name.startswith(event_pattern):
                    spawned_events.add(event_name)

        # Find inconsistencies
        events_without_spawns = defined_events - spawned_events
        spawns_without_events = spawned_events - defined_events

        # Log findings
        if event_pattern:
            logger.info(f"Found {len(defined_events)} events matching '{event_pattern}*' defined in events.xml")
            logger.info(
                f"Found {len(spawned_events)} events matching '{event_pattern}*' with spawn positions in "
                f"cfgeventspawns.xml")
        else:
            logger.info(f"Found {len(defined_events)} events defined in events.xml")
            logger.info(f"Found {len(spawned_events)} events with spawn positions in cfgeventspawns.xml")

        validation_result = {
            "valid": len(events_without_spawns) == 0 and len(spawns_without_events) == 0,
            "pattern": event_pattern,
            "defined_events": sorted(defined_events),
            "spawned_events": sorted(spawned_events),
            "events_without_spawns": sorted(events_without_spawns),
            "spawns_without_events": sorted(spawns_without_events)
        }

        if not validation_result["valid"]:
            error_messages = []

            if events_without_spawns:
                error_messages.append(
                    f"Events matching '{event_pattern}*' defined in events.xml but missing spawn positions in "
                    f"cfgeventspawns.xml: {', '.join(sorted(events_without_spawns))}"
                )

            if spawns_without_events:
                error_messages.append(
                    f"Events matching '{event_pattern}*' with spawn positions in cfgeventspawns.xml but missing "
                    f"definitions in events.xml: {', '.join(sorted(spawns_without_events))}"
                )

            error_message = "; ".join(error_messages)
            logger.error(f"Event consistency validation failed: {error_message}")
            raise ValueError(f"Event consistency validation failed: {error_message}")

        if event_pattern:
            logger.info(
                f"Event consistency validation passed - all events matching '{event_pattern}*' have matching "
                f"definitions and spawn positions")
        else:
            logger.info(
                "Event consistency validation passed - all events have matching definitions and spawn positions")
        return validation_result

    def count_items_from_events(self,
                                events_path: str,
                                groups_path: str,
                                event_pattern: str,
                                group_name: str,
                                ignore_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Count items from events matching a pattern.

        Args:
            events_path: Path to the events.xml file
            groups_path: Path to the cfgeventgroups.xml file
            event_pattern: Pattern to match event names
            group_name: Name of the group to analyze
            ignore_types: Optional list of item types to ignore

        Returns:
            Dictionary with analysis results
        """
        if not event_pattern:
            raise ValueError("event_pattern must be specified")

        # Read events XML
        logger.info(f"Reading events from: {events_path}")
        events_root = self.read_xml(events_path)

        active_events = []
        combined_counts = Counter()
        total_nominal = 0
        ignore_set = set(ignore_types or [])

        # Find all events matching the pattern
        for event in events_root.findall('event'):
            name = event.get('name', '')
            if name.startswith(event_pattern):
                is_active, nominal = self.get_event_config(events_root, name)
                if is_active:
                    active_events.append(name)
                    total_nominal += nominal
                    result = self.analyze_static_event(events_path, groups_path, name, group_name)
                    
                    # Filter out ignored types
                    filtered_counts = Counter()
                    for item_type, count in result["item_counts"].items():
                        if item_type not in ignore_set:
                            filtered_counts[item_type] = count
                    
                    combined_counts.update(filtered_counts)

        logger.info(f"Found {len(active_events)} active events matching '{event_pattern}*'")

        return {
            "active": bool(active_events),
            "active_events": active_events,
            "nominal": total_nominal,
            "item_counts": combined_counts,
            "group_name": group_name,
            "ignored_types": list(ignore_set)
        }

    def run_by_event_type(self, event_type: str,
                          events_path: Optional[str] = None,
                          groups_path: Optional[str] = None,
                          output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the counter for a specific event type defined in configuration.

        Args:
            event_type: The event type name from configuration
            events_path: Path to the events.xml file (uses config if None)
            groups_path: Path to the cfgeventgroups.xml file (uses config if None)
            output_path: Path to the output CSV file (uses config if None)

        Returns:
            Dictionary with results information
        """
        # Get event definition from config
        event_def = self.get_event_definition(event_type)
        
        # Use configured values if not provided
        if not output_path:
            output_path = event_def['output_file']
        
        # Get ignore types from definition (optional)
        ignore_types = event_def.get('ignore_types', [])
        
        # Call the generic run method
        result = self.run(
            events_path=events_path,
            groups_path=groups_path,
            output_path=output_path,
            event_pattern=event_def['event_pattern'],
            group_name=event_def['group_name'],
            ignore_types=ignore_types
        )
        
        # Add event type information
        if "success" in result:
            result["event_type"] = event_type
            result["event_definition"] = event_def
        
        return result

    def run(self, events_path: Optional[str] = None,
            groups_path: Optional[str] = None,
            output_path: Optional[str] = None,
            event_pattern: Optional[str] = None,
            group_name: Optional[str] = None,
            ignore_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run the static event counter.

        Args:
            events_path: Path to the events.xml file (uses config if None)
            groups_path: Path to the cfgeventgroups.xml file (uses config if None)
            output_path: Path to the output CSV file
            event_pattern: Pattern to match event names
            group_name: Name of the group to analyze
            ignore_types: List of item types to ignore

        Returns:
            Dictionary with results information
        """
        logger.info("Starting generic static event counter")

        # Validate required parameters
        if not event_pattern:
            raise ValueError("event_pattern must be specified")
        if not group_name:
            raise ValueError("group_name must be specified")

        # Use config paths if not provided
        if not events_path:
            events_path = self.get_config('paths.events_file')
            if not events_path:
                msg = "No events file specified and no 'paths.events_file' configured in profile"
                logger.error(msg)
                return {"error": msg}

        if not groups_path:
            groups_path = self.get_config('paths.event_groups_file')
            if not groups_path:
                msg = "No groups file specified and no 'paths.eventgroups_file' configured in profile"
                logger.error(msg)
                return {"error": msg}

        try:
            # Resolve paths
            events_path = self.resolve_path(events_path)
            groups_path = self.resolve_path(groups_path)

            # Get eventspawns path for validation
            eventspawns_path = self.get_config('paths.eventspawns_file')
            if not eventspawns_path:
                msg = "No 'paths.eventspawns_file' configured in profile for event consistency validation"
                logger.error(msg)
                return {"error": msg}
            eventspawns_path = self.resolve_path(eventspawns_path)

            # Validate event consistency between events.xml and cfgeventspawns.xml
            logger.info("Performing event consistency validation...")
            try:
                validation_result = self.validate_event_consistency(events_path, eventspawns_path, event_pattern)
                logger.info("Event consistency validation completed successfully")
            except ValueError as e:
                logger.error(f"Event consistency validation failed: {str(e)}")
                return {"error": str(e)}

            # Create output path if not provided
            if not output_path:
                output_path = self.get_config('event_counter.default_output_file', 'event_loot.csv')

            # Count items
            result = self.count_items_from_events(
                events_path,
                groups_path,
                event_pattern=event_pattern,
                group_name=group_name,
                ignore_types=ignore_types
            )

            # Write the results to a CSV file
            csv_path = self.write_item_counts(result["item_counts"], output_path)

            # Return results
            return {
                "success": True,
                "events_file": events_path,
                "groups_file": groups_path,
                "eventspawns_file": eventspawns_path,
                "output_file": csv_path,
                "active": result["active"],
                "active_events": result.get("active_events", []),
                "nominal": result["nominal"],
                "total_items": sum(result["item_counts"].values()),
                "group_name": result["group_name"],
                "ignored_types": result.get("ignored_types", []),
                "event_pattern": event_pattern,
                "validation": validation_result
            }

        except FileNotFoundError as e:
            logger.error(f"Error: Could not find file - {e}")
            return {"error": str(e)}
        except ET.ParseError as e:
            logger.error(f"Error: Invalid XML format - {e}")
            return {"error": f"Invalid XML format: {e}"}
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return {"error": str(e)}


# Backward compatibility alias
EventCounter = GenericEventCounter

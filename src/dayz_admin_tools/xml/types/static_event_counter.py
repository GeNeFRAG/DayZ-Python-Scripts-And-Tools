"""
Static Event Counter

A reusable tool for counting items in static events.
"""

import logging
from typing import Dict, Optional, Any, Set
from collections import Counter
import xml.etree.ElementTree as ET

from ...base import EventAnalyzerTool

logger = logging.getLogger(__name__)


class EventCounter(EventAnalyzerTool):
    """
    Tool for counting items in static events.
    Can process either a specific event or multiple events matching a pattern.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the static event counter.
        
        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)
        
        # Initialize common directories
        self.initialize_directories()

    def validate_event_consistency(self, events_path: str, eventspawns_path: str) -> Dict[str, Any]:
        """
        Validate that event definitions are consistent between events.xml and cfgeventspawns.xml.
        
        This checks that:
        1. Every event defined in events.xml has corresponding spawn positions in cfgeventspawns.xml
        2. Every event with spawn positions in cfgeventspawns.xml has a definition in events.xml
        
        Args:
            events_path: Path to the events.xml file
            eventspawns_path: Path to the cfgeventspawns.xml file
            
        Returns:
            Dictionary with validation results
            
        Raises:
            ValueError: If inconsistencies are found between the files
        """
        logger.info("Validating event consistency between events.xml and cfgeventspawns.xml")
        
        # Read events.xml to get defined events
        logger.info(f"Reading events from: {events_path}")
        events_root = self.read_xml(events_path)
        defined_events = set()
        
        for event in events_root.findall('event'):
            event_name = event.get('name')
            if event_name:
                defined_events.add(event_name)
        
        # Read cfgeventspawns.xml to get events with spawn positions
        logger.info(f"Reading event spawns from: {eventspawns_path}")
        eventspawns_root = self.read_xml(eventspawns_path)
        spawned_events = set()
        
        for event in eventspawns_root.findall('event'):
            event_name = event.get('name')
            if event_name:
                spawned_events.add(event_name)
        
        # Find inconsistencies
        events_without_spawns = defined_events - spawned_events
        spawns_without_events = spawned_events - defined_events
        
        # Log findings
        logger.info(f"Found {len(defined_events)} events defined in events.xml")
        logger.info(f"Found {len(spawned_events)} events with spawn positions in cfgeventspawns.xml")
        
        validation_result = {
            "valid": len(events_without_spawns) == 0 and len(spawns_without_events) == 0,
            "defined_events": sorted(defined_events),
            "spawned_events": sorted(spawned_events),
            "events_without_spawns": sorted(events_without_spawns),
            "spawns_without_events": sorted(spawns_without_events)
        }
        
        if not validation_result["valid"]:
            # Build detailed error message
            error_messages = []
            
            if events_without_spawns:
                error_messages.append(
                    f"Events defined in events.xml but missing spawn positions in cfgeventspawns.xml: "
                    f"{', '.join(sorted(events_without_spawns))}"
                )
            
            if spawns_without_events:
                error_messages.append(
                    f"Events with spawn positions in cfgeventspawns.xml but missing definitions in events.xml: "
                    f"{', '.join(sorted(spawns_without_events))}"
                )
            
            error_message = "; ".join(error_messages)
            logger.error(f"Event consistency validation failed: {error_message}")
            
            # Raise error to stop execution
            raise ValueError(f"Event consistency validation failed: {error_message}")
        
        logger.info("Event consistency validation passed - all events have matching definitions and spawn positions")
        return validation_result
    
    def count_items_from_events(self, 
                             events_path: str, 
                             groups_path: str,
                             event_pattern: Optional[str] = None,
                             specific_event: Optional[str] = None,
                             group_name: Optional[str] = "SkullsMaterials") -> Dict[str, Any]:
        """
        Count items from either a specific event or events matching a pattern.
        
        Args:
            events_path: Path to the events.xml file
            groups_path: Path to the cfgeventgroups.xml file
            event_pattern: Pattern to match event names (e.g., "StaticBuilder_")
            specific_event: Name of a specific event to analyze
            group_name: Name of the group to analyze
            
        Returns:
            Dictionary with analysis results
        """
        if not event_pattern and not specific_event:
            raise ValueError("Either event_pattern or specific_event must be specified")
        
        # Read events XML
        logger.info(f"Reading events from: {events_path}")
        events_root = self.read_xml(events_path)
        
        active_events = []
        combined_counts = Counter()
        total_nominal = 0
        
        # Find events based on pattern or specific event
        if specific_event:
            # Analyze a specific event
            is_active, nominal = self.get_event_config(events_root, specific_event)
            if is_active:
                active_events.append(specific_event)
                total_nominal = nominal
                result = self.analyze_static_event(events_path, groups_path, specific_event, group_name)
                combined_counts.update(result["item_counts"])
        else:
            # Find all events matching the pattern
            for event in events_root.findall('event'):
                name = event.get('name', '')
                if name.startswith(event_pattern):
                    is_active, nominal = self.get_event_config(events_root, name)
                    if is_active:
                        active_events.append(name)
                        total_nominal += nominal
                        result = self.analyze_static_event(events_path, groups_path, name, group_name)
                        combined_counts.update(result["item_counts"])
        
        if specific_event:
            logger.info(f"Analyzing {specific_event} event with nominal={total_nominal}")
        else:
            logger.info(f"Found {len(active_events)} active events matching '{event_pattern}*'")
        
        return {
            "active": bool(active_events),
            "active_events": active_events,
            "nominal": total_nominal,
            "item_counts": combined_counts,
            "group_name": group_name
        }
    
    def run(self, events_path: Optional[str] = None, 
            groups_path: Optional[str] = None,
            output_path: Optional[str] = None,
            event_pattern: Optional[str] = None,
            specific_event: Optional[str] = None,
            group_name: Optional[str] = "SkullsMaterials") -> Dict[str, Any]:
        """
        Run the static event counter.
        
        Args:
            events_path: Path to the events.xml file (uses paths.events_file from config if None)
            groups_path: Path to the cfgeventgroups.xml file (uses paths.eventgroups_file from config if None)
            output_path: Path to the output CSV file
            event_pattern: Pattern to match event names (e.g., "StaticBuilder_")
            specific_event: Name of a specific event to analyze
            group_name: Name of the group to analyze
            
        Returns:
            Dictionary with results information
        """
        logger.info("Starting static event counter")
        
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
                validation_result = self.validate_event_consistency(events_path, eventspawns_path)
                logger.info("Event consistency validation completed successfully")
            except ValueError as e:
                logger.error(f"Event consistency validation failed: {str(e)}")
                return {"error": str(e)}
            
            # Create output path if not provided
            if not output_path:
                if specific_event and specific_event == "StaticMildrop":
                    output_path = "md_loot.csv"
                else:
                    output_path = "sb_loot.csv"
            
            # Count items
            result = self.count_items_from_events(
                events_path, 
                groups_path,
                event_pattern=event_pattern,
                specific_event=specific_event,
                group_name=group_name
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

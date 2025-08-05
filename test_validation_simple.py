#!/usr/bin/env python3
"""
Test validation functionality with sample XML data.
"""

import tempfile
import os
import xml.etree.ElementTree as ET

# Sample events.xml content
events_xml_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<events>
    <event name="StaticBuilder_Test1">
        <nominal>1</nominal>
        <active>1</active>
    </event>
    <event name="StaticBuilder_Test2">
        <nominal>2</nominal>
        <active>1</active>
    </event>
    <event name="StaticMildrop">
        <nominal>1</nominal>
        <active>1</active>
    </event>
    <event name="OnlyInEvents">
        <nominal>1</nominal>
        <active>1</active>
    </event>
</events>
"""

# Sample cfgeventspawns.xml content
eventspawns_xml_content = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<eventposdef>
    <event name="StaticBuilder_Test1">
        <pos x="100" z="100" a="0" />
    </event>
    <event name="StaticBuilder_Test2">
        <pos x="200" z="200" a="0" />
    </event>
    <event name="StaticMildrop">
        <pos x="300" z="300" a="0" />
    </event>
    <event name="OnlyInSpawns">
        <pos x="400" z="400" a="0" />
    </event>
</eventposdef>
"""

def validate_event_consistency_simple(events_path: str, eventspawns_path: str):
    """Simple version of the validation function for testing."""
    
    # Read events.xml
    events_tree = ET.parse(events_path)
    events_root = events_tree.getroot()
    defined_events = set()
    
    for event in events_root.findall('event'):
        event_name = event.get('name')
        if event_name:
            defined_events.add(event_name)
    
    # Read cfgeventspawns.xml
    eventspawns_tree = ET.parse(eventspawns_path)
    eventspawns_root = eventspawns_tree.getroot()
    spawned_events = set()
    
    for event in eventspawns_root.findall('event'):
        event_name = event.get('name')
        if event_name:
            spawned_events.add(event_name)
    
    # Find inconsistencies
    events_without_spawns = defined_events - spawned_events
    spawns_without_events = spawned_events - defined_events
    
    return {
        "valid": len(events_without_spawns) == 0 and len(spawns_without_events) == 0,
        "defined_events": sorted(defined_events),
        "spawned_events": sorted(spawned_events),
        "events_without_spawns": sorted(events_without_spawns),
        "spawns_without_events": sorted(spawns_without_events)
    }

def test_validation():
    """Test the validation functionality."""
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as events_file:
        events_file.write(events_xml_content)
        events_path = events_file.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as spawns_file:
        spawns_file.write(eventspawns_xml_content)
        spawns_path = spawns_file.name
    
    try:
        print("Testing event validation with sample data...")
        result = validate_event_consistency_simple(events_path, spawns_path)
        
        print(f"Validation result: {'PASSED' if result['valid'] else 'FAILED'}")
        print(f"Events defined: {result['defined_events']}")
        print(f"Events with spawn positions: {result['spawned_events']}")
        
        if result['events_without_spawns']:
            print(f"Events without spawn positions: {result['events_without_spawns']}")
            
        if result['spawns_without_events']:
            print(f"Spawn positions without event definitions: {result['spawns_without_events']}")
        
        # Test should detect the inconsistency
        expected_events_without_spawns = ["OnlyInEvents"]
        expected_spawns_without_events = ["OnlyInSpawns"]
        
        if (result['events_without_spawns'] == expected_events_without_spawns and
            result['spawns_without_events'] == expected_spawns_without_events):
            print("✓ Validation correctly detected expected inconsistencies")
            return True
        else:
            print("✗ Validation did not detect expected inconsistencies")
            return False
            
    finally:
        # Clean up temporary files
        os.unlink(events_path)
        os.unlink(spawns_path)

if __name__ == "__main__":
    import sys
    success = test_validation()
    print(f"Test {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)

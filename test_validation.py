#!/usr/bin/env python3
"""
Test script for event validation functionality.
"""

import sys
import os
import logging

# Add the src directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import the base classes first
from dayz_admin_tools.base import EventAnalyzerTool

# Import the EventCounter directly from the file
import importlib.util
spec = importlib.util.spec_from_file_location("static_event_counter", 
    os.path.join(os.path.dirname(__file__), 'src', 'dayz_admin_tools', 'xml', 'types', 'static_event_counter.py'))
static_event_counter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(static_event_counter)
EventCounter = static_event_counter.EventCounter

def test_validation():
    """Test the event validation functionality."""
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Create a test configuration
    config = {
        'paths': {
            'events_file': '/Users/gerhard.froehlich/Library/CloudStorage/OneDrive-RaiffeisenBankInternationalGroup/Code/DayZ-CHERNARUS-PvPe-Bunker-Trader-Boosted-Loot-Server-For-Console/db/events.xml',
            'eventspawns_file': '/Users/gerhard.froehlich/Library/CloudStorage/OneDrive-RaiffeisenBankInternationalGroup/Code/DayZ-CHERNARUS-PvPe-Bunker-Trader-Boosted-Loot-Server-For-Console/cfgeventspawns.xml',
            'event_groups_file': '/Users/gerhard.froehlich/Library/CloudStorage/OneDrive-RaiffeisenBankInternationalGroup/Code/DayZ-CHERNARUS-PvPe-Bunker-Trader-Boosted-Loot-Server-For-Console/cfgeventgroups.xml'
        },
        'general': {
            'output_path': 'output'
        }
    }
    
    # Create the tool
    tool = EventCounter(config)
    
    try:
        # Test the validation
        events_path = config['paths']['events_file']
        eventspawns_path = config['paths']['eventspawns_file']
        
        if not os.path.exists(events_path):
            print(f"Events file not found: {events_path}")
            return False
            
        if not os.path.exists(eventspawns_path):
            print(f"Event spawns file not found: {eventspawns_path}")
            return False
        
        print("Testing event validation...")
        result = tool.validate_event_consistency(events_path, eventspawns_path)
        
        print(f"Validation result: {'PASSED' if result['valid'] else 'FAILED'}")
        print(f"Events defined: {len(result['defined_events'])}")
        print(f"Events with spawn positions: {len(result['spawned_events'])}")
        
        if result['events_without_spawns']:
            print(f"Events without spawn positions: {result['events_without_spawns']}")
            
        if result['spawns_without_events']:
            print(f"Spawn positions without event definitions: {result['spawns_without_events']}")
            
        return result['valid']
        
    except ValueError as e:
        print(f"Validation failed with error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_validation()
    sys.exit(0 if success else 1)

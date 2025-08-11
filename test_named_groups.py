#!/usr/bin/env python3
"""Test script to verify named capture groups are working correctly."""

import re
from datetime import datetime

# Test the new named group patterns
def test_named_groups():
    print("Testing named capture groups...")
    
    # Example log lines
    test_lines = [
        '14:32:45 | Player "TestPlayer" (id=76561198123456789) is connected',
        '14:35:12 | Player "VictimPlayer" (id=76561198987654321 pos=<4521.45, 12.67, 9876.32>) [HP: 85.5] hit by Player "AttackerPlayer" (id=76561198111222333 pos=<4520.12, 12.67, 9875.89>) into Head(0) for 10.0 damage (Bullet_556x45) with Mlock-91 from 15.5 meters',
        '14:36:01 | Player "BuilderPlayer" (id=76561198444555666 pos=<1234.56, 10.0, 7890.12>) Built WoodenFence on WoodenFenceKit with Shovel'
    ]
    
    # Test patterns
    patterns = {
        'connection': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\)\s*is connected'),
        'hit': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<victim_name>[^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=(?P<victim_id>[A-F0-9]+)\s*pos=<(?P<victim_x>[0-9.-]+),\s*(?P<victim_y>[0-9.-]+),\s*(?P<victim_z>[0-9.-]+)>\)\s*\[HP:\s*(?P<victim_hp>[0-9.]+)\]\s*hit by Player\s*"(?P<attacker_name>[^"]+?)"\s*\(id=(?P<attacker_id>[A-F0-9]+)\s*pos=<(?P<attacker_x>[0-9.-]+),\s*(?P<attacker_y>[0-9.-]+),\s*(?P<attacker_z>[0-9.-]+)>\)\s*into\s*(?P<hit_location>[^(]+)\((?P<hit_location_id>\d+)\)\s*for\s*(?P<damage>[0-9.]+)\s+damage\s*\((?P<ammo>[^)]+)\)(?:\s*with\s+(?P<weapon>[^\s]+)(?:\s+from\s+(?P<distance>[0-9.]+)\s+meters)?)?'),
        'building': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*(?P<action>Built|Dismantled)\s+(?P<structure>[^\s]+)\s+(?P<on_or_from>on|from)\s+(?P<parent>[^\s]+)\s+with\s+(?P<tool>[^\s]+)$')
    }
    
    for line in test_lines:
        print(f"\nTesting: {line}")
        matched = False
        
        for pattern_name, pattern in patterns.items():
            match = pattern.match(line)
            if match:
                print(f"  ✓ Matched pattern: {pattern_name}")
                print(f"    Named groups: {match.groupdict()}")
                matched = True
                break
        
        if not matched:
            print("  ✗ No pattern matched")
    
    print("\nTest complete!")

if __name__ == "__main__":
    test_named_groups()

#!/usr/bin/env python3
"""Debug script to test hit pattern matching"""

import re
from datetime import datetime

# The hit pattern from the analyzer
hit_pattern = re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<victim_name>[^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=(?P<victim_id>[A-F0-9]+)\s*pos=<(?P<victim_x>[0-9.-]+),\s*(?P<victim_y>[0-9.-]+),\s*(?P<victim_z>[0-9.-]+)>\)\s*\[HP:\s*(?P<victim_hp>[0-9.]+)\]\s*hit by Player\s*"(?P<attacker_name>[^"]+?)"\s*\(id=(?P<attacker_id>[A-F0-9]+)\s*pos=<(?P<attacker_x>[0-9.-]+),\s*(?P<attacker_y>[0-9.-]+),\s*(?P<attacker_z>[0-9.-]+)>\)\s*into\s*(?P<hit_location>[^(]+)\((?P<hit_location_id>\d+)\)\s*for\s*(?P<damage>[0-9.]+)\s+damage\s*\((?P<ammo>[^)]+)\)(?:\s*with\s+(?P<weapon>[^\s]+)(?:\s+from\s+(?P<distance>[0-9.]+)\s+meters)?)?')

# The problematic line
test_line = '20:44:33 | Player "OPT1MUS PR1ME88" (id=FA4853B3450C044D176EE3C2B68EE69DD3708CFA pos=<3241.3, 13048.3, 202.9>)[HP: 98.9] hit by Player "Player15957802" (id=1A7771D7DAE68AF9F7A56561D85F19B29F62F1A1 pos=<3241, 13047.3, 202.9>) into RightHand(47) for 10 damage (MeleeFist)'

print("Testing hit pattern...")
print(f"Test line: {test_line}")
print(f"Pattern: {hit_pattern.pattern}")
print()

match = hit_pattern.match(test_line)
if match:
    print("✅ MATCH FOUND!")
    print("Groups:")
    for name, value in match.groupdict().items():
        print(f"  {name}: {value}")
else:
    print("❌ NO MATCH")
    
    # Let's try to debug by breaking down the pattern
    print("\nDebugging...")
    
    # Test simpler patterns step by step
    simple_patterns = [
        (r'(?P<time>\d{2}:\d{2}:\d{2})', "Time"),
        (r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<victim_name>[^"]+?)"', "Time + victim name"),
        (r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<victim_name>[^"]+?)"\s*\(id=(?P<victim_id>[A-F0-9]+)', "Time + victim + ID"),
        (r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<victim_name>[^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=(?P<victim_id>[A-F0-9]+)\s*pos=<(?P<victim_x>[0-9.-]+),\s*(?P<victim_y>[0-9.-]+),\s*(?P<victim_z>[0-9.-]+)>\)', "Time + victim + ID + pos"),
        (r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<victim_name>[^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=(?P<victim_id>[A-F0-9]+)\s*pos=<(?P<victim_x>[0-9.-]+),\s*(?P<victim_y>[0-9.-]+),\s*(?P<victim_z>[0-9.-]+)>\)\s*\[HP:\s*(?P<victim_hp>[0-9.]+)\]', "Time + victim + ID + pos + HP"),
    ]
    
    for pattern, desc in simple_patterns:
        test_pattern = re.compile(pattern)
        match = test_pattern.match(test_line)
        print(f"{desc}: {'✅' if match else '❌'}")
        if match:
            print(f"  Groups: {match.groupdict()}")
    
    # Let's check where the pattern actually fails
    print("\nTesting the full pattern with search instead of match:")
    search_match = hit_pattern.search(test_line)
    if search_match:
        print("✅ SEARCH FOUND!")
        print("Groups:")
        for name, value in search_match.groupdict().items():
            print(f"  {name}: {value}")
    else:
        print("❌ NO SEARCH MATCH")

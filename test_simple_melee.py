#!/usr/bin/env python3

import re

def test_melee_parsing():
    # Define the hit pattern from the code
    hit_pattern = re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<victim_name>[^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=(?P<victim_id>[A-F0-9]+)\s*pos=<(?P<victim_x>[0-9.-]+),\s*(?P<victim_y>[0-9.-]+),\s*(?P<victim_z>[0-9.-]+)>\)\s*\[HP:\s*(?P<victim_hp>[0-9.]+)\]\s*hit by Player\s*"(?P<attacker_name>[^"]+?)"\s*\(id=(?P<attacker_id>[A-F0-9]+)\s*pos=<(?P<attacker_x>[0-9.-]+),\s*(?P<attacker_y>[0-9.-]+),\s*(?P<attacker_z>[0-9.-]+)>\)\s*into\s*(?P<hit_location>[^(]+)\((?P<hit_location_id>\d+)\)\s*for\s*(?P<damage>[0-9.]+)\s+damage\s*\((?P<ammo>[^)]+)\)(?:\s*with\s+(?P<weapon>[^\s]+)(?:\s+from\s+(?P<distance>[0-9.]+)\s+meters)?)?')
    
    # Test line that was being mapped as "Unknown"
    test_line = '20:44:33 | Player "OPT1MUS PR1ME88" (id=FA4853B3450C044D176EE3C2B68EE69DD3708CFA pos=<3241.3, 13048.3, 202.9>)[HP: 98.9] hit by Player "Player15957802" (id=1A7771D7DAE68AF9F7A56561D85F19B29F62F1A1 pos=<3241, 13047.3, 202.9>) into RightHand(47) for 10 damage (MeleeFist)'
    
    print(f"Testing line: {test_line}")
    print()
    
    match = hit_pattern.match(test_line)
    
    if match:
        print("✅ Pattern matches!")
        print("Named groups found:")
        for name, value in match.groupdict().items():
            if value is not None:
                print(f"  {name}: '{value}'")
        print()
        
        # Extract ammo and weapon as the code does
        ammo = match.group('ammo') if match.group('ammo') else ''
        try:
            weapon = match.group('weapon') if match.group('weapon') else 'Unknown'
        except:
            weapon = 'Unknown'
        
        print(f"Before melee fix:")
        print(f"  ammo: '{ammo}'")
        print(f"  weapon: '{weapon}'")
        
        # Apply the melee logic
        if weapon == 'Unknown' and ammo:
            melee_weapons = ['MeleeFist', 'MeleeAxe', 'MeleeKnife', 'MeleeBat', 'MeleeShovel', 
                           'MeleeHammer', 'MeleeMachete', 'MeleePipe', 'MeleeCrowbar']
            if any(melee in ammo for melee in melee_weapons):
                weapon = ammo
                print(f"🔧 Applied melee fix: {ammo} -> {weapon}")
        
        print(f"After melee fix:")
        print(f"  ammo: '{ammo}'")
        print(f"  weapon: '{weapon}'")
        
    else:
        print("❌ Pattern does not match!")

if __name__ == "__main__":
    test_melee_parsing()

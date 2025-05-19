import xml.etree.ElementTree as ET
import csv
from collections import Counter
import sys

if len(sys.argv) != 4:
    print("Usage: python sum_staticbuilder_items.py <events.xml> <cfgeventgroups.xml> <output.csv>")
    sys.exit(1)

events_path = sys.argv[1]
groups_path = sys.argv[2]
output_csv = sys.argv[3]

print(f"Reading events from: {events_path}")
tree = ET.parse(events_path)
root = tree.getroot()
staticbuilder_events = []
for event in root.findall('event'):
    name = event.attrib.get('name', '')
    active = event.find('active')
    if name.startswith('StaticBuilder_') and active is not None and active.text.strip() == "1":
        staticbuilder_events.append(name)
print(f"Found {len(staticbuilder_events)} active StaticBuilder_* events.")

print(f"Reading group 'SkullsMaterials' from: {groups_path}")
tree = ET.parse(groups_path)
root = tree.getroot()
item_counts = Counter()
group_found = False
for group in root.findall('group'):
    if group.attrib.get('name') == "SkullsMaterials":
        group_found = True
        for child in group.findall('child'):
            item_type = child.attrib.get('type')
            if item_type:
                item_counts[item_type] += len(staticbuilder_events)
        break

if not group_found:
    print("Warning: Group 'SkullsMaterials' not found in cfgeventgroups.xml.")

print(f"Found {sum(item_counts.values())} items in group 'SkullsMaterials' (multiplied by {len(staticbuilder_events)} active events). Writing output to: {output_csv}")

with open(output_csv, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["item", "count"])
    for item in sorted(item_counts):
        writer.writerow([item, item_counts[item]])

print("Done.")

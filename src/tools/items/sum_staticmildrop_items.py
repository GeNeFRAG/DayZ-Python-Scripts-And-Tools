import xml.etree.ElementTree as ET
import csv
from collections import Counter
import sys

if len(sys.argv) != 4:
    print("Usage: python sum_staticmildrop_items.py <events.xml> <cfgeventgroups.xml> <output.csv>")
    sys.exit(1)

events_path = sys.argv[1]
groups_path = sys.argv[2]
output_csv = sys.argv[3]

print(f"Reading events from: {events_path}")
tree = ET.parse(events_path)
root = tree.getroot()
nominal = 0
event_active = False
for event in root.findall('event'):
    name = event.attrib.get('name', '')
    if name == "StaticMildrop":
        active_elem = event.find('active')
        if active_elem is not None and active_elem.text.strip() == "1":
            event_active = True
            nominal_elem = event.find('nominal')
            if nominal_elem is not None:
                try:
                    nominal = int(nominal_elem.text.strip())
                except Exception:
                    nominal = 0
        break

if not event_active:
    print("Warning: StaticMildrop event is not active. No loot will be counted.")
    # Write empty CSV with header and exit
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["item", "count"])
    print(f"StaticMildrop event inactive. Created empty CSV at: {output_csv}")
    sys.exit(0)

if nominal == 0:
    print("Warning: Could not find <nominal> value for StaticMildrop event, or it is 0. No loot will be counted.")

print(f"StaticMildrop nominal value: {nominal}")

print(f"Reading group 'Mildrop' from: {groups_path}")
tree = ET.parse(groups_path)
root = tree.getroot()
item_counts = Counter()
group_found = False
ignore_types = {"Land_Container_1Moh_DE", "Wreck_UH1Y"}
for group in root.findall('group'):
    if group.attrib.get('name') == "Mildrop":
        group_found = True
        for child in group.findall('child'):
            item_type = child.attrib.get('type')
            if item_type and item_type not in ignore_types:
                item_counts[item_type] += nominal
        break

if not group_found:
    print("Warning: Group 'Mildrop' not found in cfgeventgroups.xml.")

print(f"Found {sum(item_counts.values())} items in group 'Mildrop' (multiplied by nominal={nominal}, ignoring {', '.join(ignore_types)}). Writing output to: {output_csv}")

with open(output_csv, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["item", "count"])
    for item in sorted(item_counts):
        writer.writerow([item, item_counts[item]])

print("Done.")

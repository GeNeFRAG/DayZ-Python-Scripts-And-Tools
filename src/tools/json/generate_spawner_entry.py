import sys
import xml.etree.ElementTree as ET
import json
import argparse

def parse_item_amount_pos(s):
    parts = s.split(':')
    if len(parts) != 5:
        raise argparse.ArgumentTypeError(f"Invalid item spec '{s}', must be <item>:<amount>:<x>:<y>:<z>")
    name, amount, x, y, z = parts
    if not amount.isdigit() or int(amount) < 1:
        raise argparse.ArgumentTypeError(f"Invalid amount '{amount}' for item '{name}'")
    try:
        x, y, z = float(x), float(y), float(z)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid coordinates for item '{name}'")
    return (name, int(amount), [x, y, z])

parser = argparse.ArgumentParser(
    description="Generate DayZ object spawner JSON entries from command line."
)
parser.add_argument("types_xml", help="Path to types.xml")
parser.add_argument("items", nargs='+', type=parse_item_amount_pos, help="Item(s) in format <item>:<amount>:<x>:<y>:<z>")

parser.add_argument("--ypr", default="0 0 0", help="YPR (default: '0 0 0')")
parser.add_argument("--scale", type=float, default=1.0, help="Scale (default: 1.0)")
parser.add_argument("--enableCEPersistence", type=int, default=0, help="enableCEPersistence (default: 0)")
parser.add_argument("--customString", default="", help="customString (default: empty)")
parser.add_argument("--output", "-o", default=None, help="Output file (default: stdout)")

args = parser.parse_args()

try:
    tree = ET.parse(args.types_xml)
    root = tree.getroot()
except Exception as e:
    print(f"Error reading types.xml: {e}", file=sys.stderr)
    sys.exit(1)

type_names = set(t.attrib.get("name") for t in root.findall("type"))
for name, _, _ in args.items:
    if name not in type_names:
        print(f"Item '{name}' not found in types.xml", file=sys.stderr)
        sys.exit(1)

ypr_list = [float(v) for v in args.ypr.split()]
objects = []
for name, amount, pos in args.items:
    for _ in range(amount):
        obj = {
            "name": name,
            "pos": pos,
            "ypr": ypr_list,
            "scale": args.scale,
            "enableCEPersistency": args.enableCEPersistence,
            "customString": args.customString
        }
        objects.append(obj)

result = json.dumps({"Objects": objects}, indent=4)
if args.output:
    with open(args.output, "w") as f:
        f.write(result)
else:
    print(result)

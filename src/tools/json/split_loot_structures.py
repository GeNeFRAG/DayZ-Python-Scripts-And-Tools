import json
import argparse
import xml.etree.ElementTree as ET
import os

def parse_args():
    parser = argparse.ArgumentParser(description="Split DayZ JSON objects into loot and structures based on types.xml.")
    parser.add_argument("--types-xml", required=True, help="Path to types.xml")
    parser.add_argument("--input-json", required=True, help="Input JSON file with objects")
    parser.add_argument("--loot-json", required=True, help="Output JSON file for loot objects")
    parser.add_argument("--structures-json", required=True, help="Output JSON file for structure objects")
    args = parser.parse_args()
    # Error handling for file existence
    if not os.path.isfile(args.types_xml):
        parser.error(f"types.xml file not found: {args.types_xml}")
    if not os.path.isfile(args.input_json):
        parser.error(f"Input JSON file not found: {args.input_json}")
    return args

def normalize(name):
    # Lowercase and remove underscores for loose matching
    return name.lower().replace("_", "")

def get_loot_types(xml_path):
    loot_types = set()
    norm_map = {}
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for type_elem in root.findall('type'):
        name = type_elem.get('name')
        if name:
            loot_types.add(name.strip())
            norm_map[normalize(name.strip())] = name.strip()
    return loot_types, norm_map

def split_objects(json_path, loot_types, norm_map):
    with open(json_path, "r") as f:
        data = json.load(f)
    loot_objs = []
    struct_objs = []
    for obj in data.get("Objects", []):
        obj_name = obj.get("name", "").strip()
        norm_name = normalize(obj_name)
        # If matched in types.xml, it's loot
        if norm_name in norm_map:
            obj["name"] = norm_map[norm_name]
            loot_objs.append(obj)
        else:
            # If not matched, move to loot unless it starts with Land_ or StaticObj_
            if obj_name.startswith("Land_") or obj_name.startswith("StaticObj_"):
                struct_objs.append(obj)
            else:
                loot_objs.append(obj)
    return loot_objs, struct_objs

def write_json(path, objects):
    with open(path, "w") as f:
        json.dump({"Objects": objects}, f, indent=4)

def main():
    args = parse_args()
    loot_types, norm_map = get_loot_types(args.types_xml)
    loot_objs, struct_objs = split_objects(args.input_json, loot_types, norm_map)
    # Debug: print names identified as structures
    for obj in struct_objs:
        print(f"Identified as structure: {obj.get('name', '').strip()}")
    write_json(args.loot_json, loot_objs)
    write_json(args.structures_json, struct_objs)
    print(f"Loot objects: {len(loot_objs)}, Structure objects: {len(struct_objs)}")

if __name__ == "__main__":
    main()

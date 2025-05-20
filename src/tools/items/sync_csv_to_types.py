"""
This script updates the nominal and minimum values in a types.xml file based on counts from a CSV file.

Usage:
    python update_nom_min_types.py <csv_file> <input_xml_file> <output_xml_file>

Arguments:
    csv_file: Path to the input CSV file containing item counts.
    input_xml_file: Path to the input types.xml file.
    output_xml_file: Path to the output XML file where updates will be saved.

Example:
    python update_nom_min_types.py counts.csv types.xml updated_types.xml
"""

import csv
from lxml import etree as ET
import argparse

def read_csv_counts(csv_file):
    """
    Reads item counts from a CSV file.

    Args:
        csv_file (str): Path to the CSV file.

    Returns:
        dict: A dictionary with item names as keys and counts as values.
    """
    counts = {}
    with open(csv_file, mode='r') as file:
        reader = csv.DictReader(file)
        if 'item' not in reader.fieldnames or 'count' not in reader.fieldnames:
            raise KeyError(f"CSV file must contain 'item' and 'count' columns. Found columns: {reader.fieldnames}")
        for row in reader:
            counts[row['item']] = int(row['count'])
    if not counts:
        print(f"Warning: CSV file '{csv_file}' is empty. No items will be updated.")
    return counts

def sort_items_alphabetically(items):
    """
    Sorts items alphabetically by their 'name' attribute.

    Args:
        items (list): List of XML elements representing items.

    Returns:
        list: Sorted list of XML elements.
    """
    return sorted(items, key=lambda x: x.get('name'))

def sort_items_by_category(items):
    """
    Sorts items by their 'category' attribute. Items with multiple categories are grouped into combined sections.

    Args:
        items (list): List of XML elements representing items.

    Returns:
        dict: Dictionary with categories as keys and lists of items as values.
    """
    categories = {}
    for item in items:
        category = item.get('category')
        if category:
            category_list = category.split(',')
            category_key = ', '.join(sorted(category_list))
            if category_key not in categories:
                categories[category_key] = []
            categories[category_key].append(item)
    return categories

def sort_items_by_usage(items):
    """
    Sorts items by their 'usage' attribute. Items with multiple usages are grouped into combined sections.
    Items with no usage are grouped under 'NO USAGE' category.

    Args:
        items (list): List of XML elements representing items.

    Returns:
        dict: Dictionary with usages as keys and lists of items as values.
    """
    usages = {}
    no_usage_items = []

    for item in items:
        usage_elements = item.findall('usage')
        if not usage_elements:
            no_usage_items.append(item)
            continue
            
        usage_list = [usage.get('name') for usage in usage_elements]
        if usage_list:
            usage_key = ', '.join(sorted(usage_list))
            if usage_key not in usages:
                usages[usage_key] = []
            usages[usage_key].append(item)

    # Sort items within each usage category alphabetically
    for usage_key in usages:
        usages[usage_key] = sorted(usages[usage_key], key=lambda x: x.get('name'))

    # Add the "NO USAGE" category with sorted items
    if no_usage_items:
        usages["NO USAGE"] = sorted(no_usage_items, key=lambda x: x.get('name'))

    return usages

def update_types_xml(input_xml_file, output_xml_file, counts):
    """
    Updates the nominal and minimum values in the types.xml file based on the counts.

    Args:
        input_xml_file (str): Path to the input types.xml file.
        output_xml_file (str): Path to the output XML file.
        counts (dict): A dictionary with item names as keys and counts as values.
    """
    parser = ET.XMLParser(remove_blank_text=False)
    tree = ET.parse(input_xml_file, parser)
    root = tree.getroot()

    items = root.findall('.//type')
    sorted_items = sort_items_alphabetically(items)
    usages = sort_items_by_usage(sorted_items)

    for item in sorted_items:
        name = item.get('name')
        nominal = item.find('nominal')
        min_val = item.find('min')
        
        if name in counts and nominal is not None and int(nominal.text) != 0:
            nominal_before = nominal.text
            min_val_before = min_val.text if min_val is not None else None
            
            nominal.text = str(int(nominal.text) + counts[name])
            if min_val is not None:
                min_val.text = str(int(min_val.text) + counts[name])
            
            if nominal.text != nominal_before or (min_val is not None and min_val.text != min_val_before):
                print(f"Updated {name}: nominal={nominal_before}>{nominal.text}, min={min_val_before}>{min_val.text if min_val is not None else 'N/A'}")

    # Clear the root and add initial newline
    root.clear()
    root.text = '\n'  # This adds the newline after <types>
    
    # Create index comment
    index_text = "INDEX OF CATEGORIES:\n"
    index_text += "==================================================\n"
    for i, usage in enumerate(sorted(usages.keys()), 1):
        index_text += f"[{usage.upper()}]\n"
    index_text += "=================================================="
    
    index_comment = ET.Comment(index_text)
    root.append(index_comment)
    index_comment.tail = '\n\n'

    # Add categories and their items
    for usage, items in sorted(usages.items()):
        comment = ET.Comment(f" ################ [{usage.upper()}] ################")
        root.append(comment)
        comment.tail = '\n'
        
        for item in items:
            root.append(item)
            item.tail = '\n'
        
        # Add extra newline between categories
        if items:
            items[-1].tail = '\n\n'

    tree.write(output_xml_file, pretty_print=True, xml_declaration=True, encoding='UTF-8')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Update types.xml with counts from a CSV file.')
    parser.add_argument('csv_file', help='Path to the input CSV file')
    parser.add_argument('input_xml_file', help='Path to the input types.xml file')
    parser.add_argument('output_xml_file', help='Path to the output XML file')

    args = parser.parse_args()

    counts = read_csv_counts(args.csv_file)
    update_types_xml(args.input_xml_file, args.output_xml_file, counts)

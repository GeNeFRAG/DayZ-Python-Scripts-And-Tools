"""
Sum Items JSON Tool

Process multiple JSON files containing objects with "name" attributes,
aggregate the counts of each unique name (excluding those starting with "StaticObj_" or "Land_"),
and output the results to a CSV file.
"""

import json
import argparse
import os
import csv
import logging
from collections import Counter
from typing import Dict, Any, Optional, List, Set

# Import JSONTool from base.py
from ..base import JSONTool, XMLTool

__all__ = ['SumItemsJson', 'main']


class SumItemsJson(JSONTool, XMLTool):
    """
    Aggregate and count items from multiple DayZ JSON files.
    
    This tool processes multiple JSON files containing objects with "name" attributes,
    aggregates the counts of each unique name, and outputs the results to a CSV file.
    The tool can filter out static objects or include all object types.
    It can also validate items against a types.xml file.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the SumItemsJson tool.
        
        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.initialize_directories()
        # output_dir is already set in initialize_directories() from the base class
    
    def run(self, json_files: List[str], output_csv: Optional[str] = None, types_xml: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Process multiple JSON files and count item occurrences.
        
        Args:
            json_files: List of JSON file paths to process
            output_csv: Path to the output CSV file. If None or a relative path,
                      it will be stored in the standard output directory.
            types_xml: Optional path to a types.xml file to validate items against.
                      If None, will use the default_types_file from config.
            
        Returns:
            Dictionary of item names and their counts
        """
        return self.process_json_files(json_files, output_csv, types_xml)

    def process_json_files(self, json_files: List[str], output_csv: Optional[str] = None, types_xml: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Process multiple JSON files and count item occurrences.
        
        Args:
            json_files: List of JSON file paths to process
            output_csv: Path to the output CSV file. If None or a relative path,
                      it will be stored in the standard output directory.
                      If None, a default name will be generated.
            types_xml: Optional path to a types.xml file to validate items against.
                      If None, will use the default_types_file from config.
            
        Returns:
            Dictionary of item names and their counts and validation info
        """
        # Parse types.xml if provided to get valid item names
        valid_items = self.parse_types_xml(types_xml)
        has_types_file = len(valid_items) > 0
        
        if has_types_file:
            self.logger.info(f"Validating items against types.xml with {len(valid_items)} items")
        else:
            self.logger.warning("No types.xml file provided or none found, items won't be validated")
        
        # Initialize a Counter to aggregate counts
        name_counts = Counter()
        
        # Process each file
        for filename in json_files:
            self.logger.info(f"Processing {filename}")
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                
                if "Objects" in data:
                    for obj in data["Objects"]:
                        if "name" in obj:
                            name = obj["name"]
                            
                            # Skip static objects
                            if name.startswith("StaticObj_") or name.startswith("Land_"):
                                continue
                                
                            name_counts[name] += 1
                else:
                    self.logger.warning(f"No 'Objects' key found in {filename}")
                    
            except (json.JSONDecodeError, FileNotFoundError) as e:
                self.logger.error(f"Error processing {filename}: {e}")
        
        # Create a dictionary with counts and validation info
        item_data = {}
        for name, count in sorted(name_counts.items()):
            item_data[name] = {
                'count': count,
                'valid': not has_types_file or name in valid_items
            }
            
        # Determine the output CSV path
        if output_csv is None:
            # Generate a default filename based on the number of files processed
            output_csv = f"json_loot.csv"
        
        # Let write_csv handle the path resolution - just pass the filename
        # which will be resolved with output_dir in the base class method
        output_path = output_csv if os.path.isabs(output_csv) else output_csv
        
        # Ensure output directories exist
        self.ensure_dir(os.path.dirname(output_path))
        
        # Create data rows for CSV, excluding invalid items
        data_rows = []
        for name, info in item_data.items():
            # Only include valid items
            if info['valid']:
                row = {
                    'item': name, 
                    'count': info['count']
                }
                data_rows.append(row)
            
        headers = ['item', 'count']
        
        # Use the write_csv method from FileBasedTool
        output_path = self.write_csv(data_rows, output_path, headers)
        
        # Count valid and total items for logging
        valid_item_count = len(data_rows)
        total_item_count = len(item_data)
        
        self.logger.info(f"Processed {len(json_files)} files, found {total_item_count} unique items")
        
        # Log statistics about item filtering
        if has_types_file:
            invalid_item_count = total_item_count - valid_item_count
            self.logger.info(f"Item validation: {valid_item_count} valid items included, {invalid_item_count} invalid items excluded")
        
        self.logger.info(f"Results written to {output_path}")
        
        return item_data

    def parse_types_xml(self, types_xml_path: Optional[str] = None) -> Set[str]:
        """
        Parse types.xml and extract all valid item names using base class methods.
        
        Args:
            types_xml_path: Path to types.xml file. If None, uses the default_types_file from config.
            
        Returns:
            A set of valid item names from types.xml
        """
        valid_items = set()
        
        # If no specific path is provided, use the default from config
        if not types_xml_path and hasattr(self, 'default_types_file') and self.default_types_file:
            types_xml_path = self.default_types_file
            
        if not types_xml_path:
            self.logger.warning("No types.xml file provided and none found in configuration")
            return valid_items
            
        try:
            # Use the read_xml method from XMLTool base class
            root = self.read_xml(types_xml_path)
            self.logger.info(f"Parsing types.xml from {types_xml_path}")
            
            # Extract all type names using the base class method to process type elements
            for type_elem in root.findall('.//type'):
                # Use get_type_values from base class with an empty list since we only need the name attribute
                values = self.get_type_values(type_elem, [])
                name = values.get('name')
                if name:
                    valid_items.add(name)
                    
            self.logger.info(f"Found {len(valid_items)} valid items in types.xml")
            
        except (FileNotFoundError, IOError) as e:
            self.logger.error(f"Error parsing types.xml: {e}")
            
        return valid_items

def main():
    """
    Main function to run the item counter as a command-line tool.
    """
    parser = argparse.ArgumentParser(
        description="Sum items from multiple DayZ JSON files and output to CSV."
    )
    parser.add_argument("--output", "-o", dest="output_csv", 
                      help="Path to the output CSV file. If not provided, a default name will be generated in the standard output directory.")
    parser.add_argument("--types-xml", "-t", dest="types_xml",
                      help="Path to types.xml file for item validation. If not provided, uses the default from config.")
    parser.add_argument("json_files", nargs='+', help="JSON files to process")
    
    # Add standard arguments from base class
    from ..base import DayZTool
    DayZTool.add_standard_arguments(parser)
    args = parser.parse_args()
    
    # Load configuration using the static method from DayZTool
    config = DayZTool.load_config(args.profile)
    
    # Create and run the tool
    counter = SumItemsJson(config)
    result = counter.run(args.json_files, args.output_csv, args.types_xml)
    
    # Display a summary
    total_items = len(result)
    valid_items = sum(1 for info in result.values() if info['valid'])
    invalid_items = total_items - valid_items
    
    print(f"Processed {len(args.json_files)} files, found {total_items} unique items")
    print(f"Output directory: {counter.output_dir}")
    print(f"CSV output: {valid_items} valid items included, {invalid_items} invalid items excluded")
    
    if invalid_items > 0:
        print("\nItems not found in types.xml may need to be added or could be typos.")


if __name__ == '__main__':
    main()

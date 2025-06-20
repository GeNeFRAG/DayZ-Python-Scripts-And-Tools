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
from typing import Dict, Any, Optional, List

# Import JSONTool from base.py
from ..base import JSONTool

__all__ = ['SumItemsJson', 'main']


class SumItemsJson(JSONTool):
    """
    Aggregate and count items from multiple DayZ JSON files.
    
    This tool processes multiple JSON files containing objects with "name" attributes,
    aggregates the counts of each unique name, and outputs the results to a CSV file.
    The tool can filter out static objects or include all object types.
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
    
    def run(self, json_files: List[str], output_csv: Optional[str] = None) -> Dict[str, int]:
        """
        Process multiple JSON files and count item occurrences.
        
        Args:
            json_files: List of JSON file paths to process
            output_csv: Path to the output CSV file. If None or a relative path,
                      it will be stored in the standard output directory.
            
        Returns:
            Dictionary of item names and their counts
        """
        return self.process_json_files(json_files, output_csv)

    def process_json_files(self, json_files: List[str], output_csv: Optional[str] = None) -> Dict[str, int]:
        """
        Process multiple JSON files and count item occurrences.
        
        Args:
            json_files: List of JSON file paths to process
            output_csv: Path to the output CSV file. If None or a relative path,
                      it will be stored in the standard output directory.
                      If None, a default name will be generated.
            
        Returns:
            Dictionary of item names and their counts
        """
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
        
        # Convert Counter to sorted dictionary (alphabetically by name)
        sorted_counts = dict(sorted(name_counts.items()))
        
        # Determine the output CSV path
        if output_csv is None:
            # Generate a default filename based on the number of files processed
            output_csv = f"json_loot.csv"
        
        # Let write_csv handle the path resolution - just pass the filename
        # which will be resolved with output_dir in the base class method
        output_path = output_csv if os.path.isabs(output_csv) else output_csv
        
        # Ensure output directories exist
        self.ensure_dir(os.path.dirname(output_path))
        
        # Use write_csv method from FileBasedTool if it contains CSV writing functionality
        # Otherwise use our own implementation
        data_rows = [{'item': name, 'count': count} for name, count in sorted_counts.items()]
        headers = ['item', 'count']
        
        try:
            # Use the write_csv method from FileBasedTool
            output_path = self.write_csv(data_rows, output_path, headers)
            self.logger.info(f"Processed {len(json_files)} files, found {len(sorted_counts)} unique items")
            self.logger.info(f"Results written to {output_path}")
            self.logger.info(f"Output directory: {self.output_dir}")
        except AttributeError:
            # Fall back to our own implementation
            try:
                with open(output_path, 'w', newline='') as csvfile:
                    csv_writer = csv.writer(csvfile)
                    csv_writer.writerow(headers)
                    
                    for name, count in sorted_counts.items():
                        csv_writer.writerow([name, count])
                    
                self.logger.info(f"Results written to {output_path}")
                self.logger.info(f"Output directory: {self.output_dir}")
                self.logger.info(f"Processed {len(json_files)} files, found {len(sorted_counts)} unique items")
                
            except IOError as e:
                self.logger.error(f"Error writing to {output_path}: {e}")
        
        return sorted_counts


# Standard arguments are now added from the base DayZTool class


def main():
    """
    Main function to run the item counter as a command-line tool.
    """
    parser = argparse.ArgumentParser(
        description="Sum items from multiple DayZ JSON files and output to CSV."
    )
    parser.add_argument("--output", "-o", dest="output_csv", 
                      help="Path to the output CSV file. If not provided, a default name will be generated in the standard output directory.")
    parser.add_argument("json_files", nargs='+', help="JSON files to process")
    
    # Add standard arguments from base class
    from ..base import DayZTool
    DayZTool.add_standard_arguments(parser)
    args = parser.parse_args()
    
    # Load configuration using the static method from DayZTool
    config = DayZTool.load_config(args.profile)
    
    # Create and run the tool
    counter = SumItemsJson(config)
    result = counter.run(args.json_files, args.output_csv)
    
    # Display a summary
    print(f"Processed {len(args.json_files)} files, found {len(result)} unique items")
    print(f"Output directory: {counter.output_dir}")


if __name__ == '__main__':
    main()

"""
Compare Types Tool

A tool for comparing two types.xml files and identifying differences between them.
This is useful for analyzing changes between different versions of a server
or between different server configurations.
"""

import xml.etree.ElementTree as ET
import csv
import argparse
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add support for the config system
from ...base import XMLTool, DayZTool

__all__ = ['CompareTypesTool', 'main']

# Configure logging
logger = logging.getLogger(__name__)


def setup_console_logging():
    """Set up console logging for user-visible output."""
    # Create console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    
    # Create a simple formatter without timestamps for cleaner user output
    formatter = logging.Formatter('%(message)s')
    console.setFormatter(formatter)
    
    # Add the handler to the logger
    logger.addHandler(console)


class CompareTypesTool(XMLTool):
    """
    Tool for comparing values between two types.xml files.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the CompareTypes tool.
        
        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)
        
        # Initialize common directories
        self.initialize_directories()

    def extract_values(self, xml_file: str) -> Dict[str, Dict[str, Optional[int]]]:
        """
        Extract values from a types.xml file.
        
        Args:
            xml_file: Path to the XML file
            
        Returns:
            Dictionary of item names mapped to their values
        """
        logger.info(f"Extracting values from {xml_file}")
        
        # Define the elements we want to extract
        elements = ["nominal", "min", "restock", "lifetime", "quantmin", "quantmax", "cost"]
        
        try:
            # Use build_type_dict from base class
            values = self.build_type_dict(xml_file, elements)
            
            # Convert string values to integers where possible
            for item_name, item_values in values.items():
                for key, value in item_values.items():
                    try:
                        if value is not None:
                            # Handle both string digits and floating point strings
                            if isinstance(value, str) and (value.isdigit() or (value.replace('.', '', 1).isdigit() and value.count('.') <= 1)):
                                item_values[key] = int(float(value))
                            elif isinstance(value, (int, float)):
                                item_values[key] = int(value)
                    except (ValueError, AttributeError):
                        logger.warning(f"Non-numeric value found for {item_name}.{key}: {value}")
                        item_values[key] = None
                        
            logger.info(f"Extracted {len(values)} items from {xml_file}")
            return values
            
        except ET.ParseError as e:
            logger.error(f"Invalid XML format in {xml_file}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error extracting values from {xml_file}: {e}")
            raise

    def compare_values(self, file1_values: Dict[str, Dict[str, Optional[int]]], 
                      file2_values: Dict[str, Dict[str, Optional[int]]]) -> List[Dict[str, Any]]:
        """
        Compare values between two dictionaries of item values.
        
        Args:
            file1_values: Values from the first file
            file2_values: Values from the second file
            
        Returns:
            List of dictionaries containing the differences
        """
        logger.info("Comparing values between files")
        
        differences = []
        # Get a sorted list of all unique item names
        all_items = sorted(set(file1_values.keys()) | set(file2_values.keys()))
        
        # Define fields to compare
        fields = ["nominal", "lifetime", "restock", "min", "quantmin", "quantmax"]
        
        for item in all_items:
            file1_vals = file1_values.get(item, {})
            file2_vals = file2_values.get(item, {})
            
            # Skip if values are identical
            if file1_vals == file2_vals:
                continue
                
            # Create diff record
            diff_record = {"item": item}
            has_differences = False
            
            # Compare each field
            for field in fields:
                val1 = file1_vals.get(field)
                val2 = file2_vals.get(field)
                diff = self._calc_diff(val1, val2)
                
                # Only add to diff record if there's an actual difference
                if val1 != val2:
                    has_differences = True
                    diff_record.update({
                        f"file1_{field}": val1,
                        f"file2_{field}": val2,
                        f"{field}_diff": diff
                    })
            
            # Only append records that have actual differences
            if has_differences:
                differences.append(diff_record)
        
        logger.info(f"Found {len(differences)} differences between files")
        return differences

    def _calc_diff(self, val1: Optional[int], val2: Optional[int]) -> Optional[int]:
        """
        Calculate the difference between two values.
        
        Args:
            val1: First value
            val2: Second value
            
        Returns:
            Difference between val1 and val2, or None if values are not comparable
        """
        if val1 is not None and val2 is not None:
            try:
                # Convert values to integers if they're not already
                val1_int = int(val1) if not isinstance(val1, int) else val1
                val2_int = int(val2) if not isinstance(val2, int) else val2
                return val1_int - val2_int
            except (ValueError, TypeError):
                logger.warning(f"Cannot calculate difference between non-numeric values: {val1} and {val2}")
                return None
        return None

    def write_differences_to_csv(self, differences: List[Dict[str, Any]], output_csv_file: str) -> str:
        """
        Write differences to a CSV file.
        
        Args:
            differences: List of dictionaries containing the differences
            output_csv_file: Path to the output CSV file
            
        Returns:
            Path to the created CSV file
        """
        if not differences:
            logger.warning("No differences found to write to CSV")
            return self.write_csv([], output_csv_file, ["item"])
        
        # Get all unique headers from the differences
        headers = set(["item"])  # Always include item name
        for diff in differences:
            headers.update(diff.keys())
        
        # Sort headers to ensure consistent column order
        sorted_headers = sorted(list(headers), key=lambda x: (
            # Ensure "item" is first
            "0" if x == "item" else
            # Group related columns together
            "1" + x.split("_")[1] if x.startswith("file1_") else
            "2" + x.split("_")[1] if x.startswith("file2_") else
            "3" + x if x.endswith("_diff") else
            "4" + x
        ))
        
        # Use the base class write_csv method
        csv_path = self.write_csv(differences, output_csv_file, sorted_headers)
        logger.info(f"Differences written to {csv_path}")
        return csv_path

    def run(self, file1: str, file2: str, output_csv: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the CompareTypes tool.
        
        Args:
            file1: Path to the first XML file
            file2: Path to the second XML file
            output_csv: Path to the output CSV file
            
        Returns:
            Dictionary with results information
        """
        try:
            # Resolve file paths
            file1_path = self.resolve_path(file1)
            file2_path = self.resolve_path(file2)
            
            # Generate default output path if not specified
            if not output_csv:
                # Add timestamp to the output file name
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_name = f"types_comparison_{Path(file1).stem}_{Path(file2).stem}_{timestamp}.csv"
                # Use the standard output path from the general.output_path config
                output_dir = self.get_config('general.output_path', self.output_dir)
                output_csv = os.path.join(output_dir, base_name)
            
            logger.info(f"Comparing {file1_path} to {file2_path}")
            
            # Extract and compare values
            file1_values = self.extract_values(file1_path)
            file2_values = self.extract_values(file2_path)
            differences = self.compare_values(file1_values, file2_values)
            
            # Write results to CSV
            self.write_differences_to_csv(differences, output_csv)
            
            return {
                "success": True,
                "output_file": output_csv,
                "differences_count": len(differences),
                "file1_items": len(file1_values),
                "file2_items": len(file2_values)
            }
            
        except FileNotFoundError as e:
            logger.error(f"Error: Could not find file - {e}")
            return {"error": str(e)}
        except ET.ParseError as e:
            logger.error(f"Error: Invalid XML format - {e}")
            return {"error": f"Invalid XML format: {e}"}
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return {"error": str(e)}


def main():
    """
    Main entry point for the command-line script.
    """
    parser = argparse.ArgumentParser(
        description="Compare values between two types.xml files and output differences to a CSV file."
    )
    parser.add_argument("types_xml1", help="Path to the first types.xml file")
    parser.add_argument("types_xml2", help="Path to the second types.xml file")
    parser.add_argument("--output-dir", help="Directory to store output files (overrides general.output_path from config)")
    
    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)

    args = parser.parse_args()
    
    # Load configuration
    config = DayZTool.load_config(args.profile)
    
    # Set up console logging for user output
    setup_console_logging()
    
    # Initialize the tool
    tool = CompareTypesTool(config)
    
    # Handle output path
    output_path = None
    if args.output_dir:
        # If output dir is specified, generate a filename with timestamp in that directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"types_comparison_{Path(args.types_xml1).stem}_{Path(args.types_xml2).stem}_{timestamp}.csv"
        output_path = os.path.join(args.output_dir, base_name)
    
    # Run the tool
    result = tool.run(args.types_xml1, args.types_xml2, output_path)
    
    if "error" in result:
        logger.error(f"Error: {result['error']}")
        exit(1)
    
    logger.info(f"Comparison complete. Found {result['differences_count']} differences.")
    logger.info(f"Results written to {result['output_file']}")


if __name__ == "__main__":
    setup_console_logging()
    main()

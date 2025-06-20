"""
Types to Excel Tool

A tool for converting DayZ types.xml files to Excel spreadsheet format and back.
This makes it easier to edit and manage large types.xml files using spreadsheet software.
"""

import xml.etree.ElementTree as ET
import logging
import os
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add support for the config system
from ...base import XMLTool, DayZTool, HAS_LXML

try:
    import pandas as pd
    import openpyxl
except ImportError:
    raise ImportError("This tool requires pandas and openpyxl. Install with: pip install pandas openpyxl")

__all__ = ['TypesToExcelTool', 'main']

# Configure logging
logger = logging.getLogger(__name__)


class TypesToExcelTool(XMLTool):
    """Tool for converting between DayZ types.xml and Excel formats."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the types to excel tool.
        
        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)
        
        # Initialize common directories
        self.initialize_directories()
        
        # Get reference and output types files from config
        self.types_file_ref = self.get_config('paths.types_file_ref')
        self.types_file = self.get_config('paths.types_file')

        # Define standard columns
        self.flag_columns = [
            'count_in_cargo',
            'count_in_hoarder',
            'count_in_map',
            'count_in_player',
            'crafted',
            'deloot'
        ]
        
        self.numeric_fields = ['nominal', 'lifetime', 'restock', 'min', 'quantmin', 'quantmax', 'cost']
    
    def collect_named_values(self, root, element_name: str) -> List[str]:
        """
        Collect all unique values of the 'name' attribute for a given element type.
        Uses base class methods for consistency.
        
        Args:
            root: XML root element
            element_name: Name of the elements to collect from
            
        Returns:
            List of sorted unique name values
        """
        values = set()
        for type_elem in self.filter_types_by_name(root):
            for elem in type_elem.findall(element_name):
                name = elem.get('name', '')
                if name:
                    values.add(name)
        return sorted(values)

    def get_type_data(self, type_elem, usage_columns: List[str], tier_columns: List[str]) -> Dict[str, Any]:
        """
        Extract all relevant data from a type element using base class methods.
        
        Args:
            type_elem: The type element to process
            usage_columns: List of known usage names
            tier_columns: List of known tier names
            
        Returns:
            Dictionary containing all extracted data
        """
        # Get basic type values using base class method
        item = self.get_type_values(type_elem, self.numeric_fields)
        
        # Handle flags attributes
        flags_elem = type_elem.find('flags')
        if flags_elem is not None:
            for flag in self.flag_columns:
                try:
                    item[flag] = int(flags_elem.get(flag, '0'))
                except ValueError:
                    item[flag] = flags_elem.get(flag, '')
        else:
            for flag in self.flag_columns:
                item[flag] = ''
        
        # Handle named elements (usage, value, category)
        category_elem = type_elem.find('category')
        item['category'] = category_elem.get('name', '') if category_elem is not None else ''
        
        # Handle usage tags as separate columns
        current_usage = {u.get('name', '') for u in type_elem.findall('usage')}
        for usage in usage_columns:
            item[f'usage_{usage}'] = 'X' if usage in current_usage else ''
        
        # Handle tier values as separate columns
        current_tiers = {v.get('name', '') for v in type_elem.findall('value')}
        for tier in tier_columns:
            item[f'tier_{tier}'] = 'X' if tier in current_tiers else ''
        
        return item
    
    def xml_to_excel(self, xml_file: str, excel_file: str) -> bool:
        """
        Convert a types.xml file to Excel format.
        Uses base class methods for XML handling.
        
        Args:
            xml_file: Path to the input XML file
            excel_file: Path to the output Excel file
            
        Returns:
            Whether the conversion was successful
        """
        try:
            # Resolve paths
            xml_path = self.resolve_path(xml_file)
            excel_path = self.resolve_path(excel_file)
            
            logger.info(f"Converting {xml_path} to Excel format")
            
            # Parse the XML using base class method with comment preservation
            root = self.read_xml_with_comments(xml_path)
            
            # Collect all possible usage and tier values using helper method
            usage_columns = self.collect_named_values(root, 'usage')
            tier_columns = self.collect_named_values(root, 'value')
            
            # Use base class method to get sorted items
            items = self.filter_types_by_name(root)
            
            # Prepare data for DataFrame
            data = []
            for type_elem in items:
                item_data = self.get_type_data(type_elem, usage_columns, tier_columns)
                data.append(item_data)
            
            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Convert empty strings to NaN for numeric columns
            numeric_columns = self.numeric_fields + self.flag_columns
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(excel_path), exist_ok=True)
            
            # Save to Excel with appropriate formatting
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
                worksheet = writer.sheets['Sheet1']
                
                # Format columns appropriately
                for idx, column in enumerate(df.columns, 1):
                    letter = openpyxl.utils.get_column_letter(idx)
                    if column in numeric_columns:
                        # Format numeric columns as numbers
                        for cell in worksheet[letter][1:]:  # Skip header row
                            if cell.value is not None:
                                cell.number_format = '0'
                    else:
                        # Format other columns as text
                        for cell in worksheet[letter][1:]:  # Skip header row
                            cell.number_format = '@'
            
            logger.info(f"Successfully exported to {excel_path}")
            return True
        except Exception as e:
            logger.error(f"Error during XML to Excel conversion: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def create_type_element(self, row: pd.Series, use_lxml: bool = False) -> Any:
        """
        Create a type element from a row of Excel data.
        
        Args:
            row: Pandas Series containing the row data
            use_lxml: Whether to use lxml.etree (if True and available) or standard ElementTree
            
        Returns:
            ElementTree Element for the type
        """
        if use_lxml and HAS_LXML:
            from lxml import etree as LxmlET
            type_elem = LxmlET.Element('type')
            type_elem.set('name', str(row['name']))
            
            # Set text on the type element to ensure proper indentation
            type_elem.text = '\n    '  # Child elements indented 4 spaces from type
            
            # Add numeric fields
            for i, field in enumerate(self.numeric_fields):
                if pd.notna(row.get(field, pd.NA)):
                    elem = LxmlET.SubElement(type_elem, field)
                    elem.text = str(int(row[field]))
                    # Add formatting for proper indentation
                    elem.tail = '\n\t\t'
        else:
            type_elem = ET.Element('type')
            type_elem.set('name', str(row['name']))
            
            # Set text on the type element to ensure proper indentation
            type_elem.text = '\n    '  # Child elements indented 4 spaces from type
            
            # Add numeric fields
            for i, field in enumerate(self.numeric_fields):
                if pd.notna(row.get(field, pd.NA)):
                    elem = ET.SubElement(type_elem, field)
                    elem.text = str(int(row[field]))
                    # Add formatting for proper indentation
                    elem.tail = '\n\t\t'
        
        # Add flags
        flags = {col: val for col, val in row.items() 
                if col in self.flag_columns and pd.notna(val)}
        if flags:
            if use_lxml and HAS_LXML:
                flags_elem = LxmlET.SubElement(type_elem, 'flags')
                flags_elem.tail = '\n\t\t'
            else:
                flags_elem = ET.SubElement(type_elem, 'flags')
                flags_elem.tail = '\n\t\t'
            
            for flag, value in flags.items():
                flags_elem.set(flag, str(int(value)))
        
        # Add category if present
        if pd.notna(row.get('category', pd.NA)) and row['category']:
            if use_lxml and HAS_LXML:
                category_elem = LxmlET.SubElement(type_elem, 'category')
                category_elem.tail = '\n\t\t'
            else:
                category_elem = ET.SubElement(type_elem, 'category')
                category_elem.tail = '\n\t\t'
            category_elem.set('name', str(row['category']))
        
        # Add usage values
        usage_cols = [col for col in row.index if col.startswith('usage_')]
        for i, col in enumerate(usage_cols):
            if pd.notna(row[col]) and row[col] == 'X':
                if use_lxml and HAS_LXML:
                    usage_elem = LxmlET.SubElement(type_elem, 'usage')
                    usage_elem.tail = '\n\t\t'
                else:
                    usage_elem = ET.SubElement(type_elem, 'usage')
                    usage_elem.tail = '\n\t\t'
                usage_elem.set('name', col[6:])  # Remove 'usage_' prefix
        
        # Add tier values
        tier_cols = [col for col in row.index if col.startswith('tier_')]
        for i, col in enumerate(tier_cols):
            is_last_element = i == len(tier_cols) - 1 and not any(pd.notna(row[c]) and row[c] == 'X' for c in usage_cols)
            
            if pd.notna(row[col]) and row[col] == 'X':
                if use_lxml and HAS_LXML:
                    value_elem = LxmlET.SubElement(type_elem, 'value')
                    if not is_last_element:
                        value_elem.tail = '\n\t\t'
                    else:
                        value_elem.tail = '\n\t'  # Last element needs different indentation
                else:
                    value_elem = ET.SubElement(type_elem, 'value')
                    if not is_last_element:
                        value_elem.tail = '\n\t\t'
                    else:
                        value_elem.tail = '\n\t'  # Last element needs different indentation
                value_elem.set('name', col[5:])  # Remove 'tier_' prefix
        
        # If we have any child elements, make sure the last one has proper formatting
        children = list(type_elem)
        if children:
            last_child = children[-1]
            last_child.tail = '\n\t'  # Proper indentation for closing tag
        
        return type_elem

    def excel_to_xml(self, excel_file: str, xml_file: str) -> bool:
        """
        Convert an Excel file back to types.xml format.
        Uses base class methods for XML handling.
        
        Args:
            excel_file: Path to the input Excel file
            xml_file: Path to the output XML file
            
        Returns:
            Whether the conversion was successful
        """
        try:
            # Resolve paths
            excel_path = self.resolve_path(excel_file)
            xml_path = self.resolve_path(xml_file)
            
            logger.info(f"Converting {excel_path} to XML format")
            
            # Read Excel file
            df = pd.read_excel(excel_path)
            
            # Create root element - use lxml if available
            use_lxml = HAS_LXML
            
            if use_lxml:
                from lxml import etree as LxmlET
                root = LxmlET.Element('types')
                # Set text to ensure proper formatting with newlines between elements
                root.text = '\n  '  # Correct indentation for type elements
            else:
                root = ET.Element('types')
                # Set text to ensure proper formatting with newlines between elements
                root.text = '\n  '  # Correct indentation for type elements
                
            # Convert each row to a type element using the same ElementTree implementation
            for i, (_, row) in enumerate(df.iterrows()):
                type_elem = self.create_type_element(row, use_lxml=use_lxml)
                # Add tail to each type element for proper formatting
                if i < len(df) - 1:  # All elements except the last one
                    type_elem.tail = '\n  '  # Correct indentation for next type element
                else:  # Last element
                    type_elem.tail = '\n'  # No indentation for closing tag
                root.append(type_elem)
            
            # Use base class method to create sorted root organized by usage categories
            # This replaces our custom sorting logic with the shared implementation
            organized_root = self.create_sorted_by_usage_root(root, add_index=True)
            
            # Write XML using base class method (preserves comments and indentation)
            # Post-processing will handle indentation
            self.write_xml(organized_root, xml_path, pretty=True)
            
            logger.info(f"Successfully converted Excel to {xml_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to convert Excel to XML: {str(e)}")
            return False
    
    def run(self, input_path: Optional[str] = None, output_path: Optional[str] = None, to_excel: bool = True) -> int:
        """
        Run the types to excel tool.
        
        Args:
            input_path: Input file path (if None, uses config paths)
            output_path: Output file path (if None, uses config paths or generates name)
            to_excel: Whether to convert to Excel (True) or to XML (False)
            
        Returns:
            0 on success, 1 on failure
        """
        try:
            # Handle input path
            if not input_path:
                if to_excel:
                    # When converting to Excel, use types_file_ref as input
                    input_path = self.types_file_ref
                    if not input_path:
                        msg = "No input file specified and no 'paths.types_file_ref' configured in profile"
                        logger.error(msg)
                        return 1
                else:
                    # When converting to XML, expect Excel file in output directory
                    if not self.types_file_ref:
                        msg = "No 'paths.types_file_ref' configured in profile for Excel filename generation"
                        logger.error(msg)
                        return 1
                    input_path = self.generate_output_filename(self.types_file_ref, '.xlsx')

            # Handle output path
            if not output_path:
                if to_excel:
                    # Generate Excel filename in output directory
                    output_path = self.generate_output_filename(input_path, '.xlsx')
                else:
                    # When converting from Excel to XML, generate a filename in the output directory
                    # Extract the base name from the input Excel file
                    input_basename = os.path.basename(input_path)
                    input_name = os.path.splitext(input_basename)[0]
                    
                    # If the input name already has "_updated", remove it for cleaner output
                    if input_name.endswith("_updated"):
                        input_name = input_name[:-8]
                    
                    # Generate output path with a meaningful suffix
                    output_name = f"{input_name}_from_excel.xml"
                    output_path = os.path.join(self.output_dir, output_name)
                    
                    logger.info(f"Generated output XML path: {output_path}")

            logger.info(f"{'XML to Excel' if to_excel else 'Excel to XML'} conversion")
            logger.info(f"Input: {input_path}")
            logger.info(f"Output: {output_path}")

            if to_excel:
                # Convert XML to Excel
                if self.xml_to_excel(input_path, output_path):
                    logger.info("XML to Excel conversion completed successfully")
                    return 0
                else:
                    logger.error("XML to Excel conversion failed")
                    return 1
            else:
                # Convert Excel to XML
                if self.excel_to_xml(input_path, output_path):
                    logger.info("Excel to XML conversion completed successfully")
                    return 0
                else:
                    logger.error("Excel to XML conversion failed")
                    return 1
                    
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return 1
    
    def generate_output_filename(self, reference_file: str, extension: str = '.xml') -> str:
        """
        Generate an output filename based on the reference file.
        
        Args:
            reference_file: Path to the reference file
            extension: File extension to use (default: '.xml')
            
        Returns:
            Generated output path in the configured output directory
        """
        ref_path = Path(reference_file)
        output_name = f"{ref_path.stem}_updated{extension}"
        return os.path.join(self.output_dir, output_name)
            
def main():
    """Main function for the types to excel tool."""
    parser = argparse.ArgumentParser(
        description='Convert between DayZ types.xml and Excel format. ' +
                   'When converting to Excel, uses paths.types_file_ref as input if not specified. ' +
                   'When converting to XML, uses paths.types_file as output if not specified.'
    )
    parser.add_argument('--to-excel', action='store_true', 
                       help='Convert XML to Excel (default behavior)')
    parser.add_argument('--to-xml', action='store_true', 
                       help='Convert Excel back to XML')
    parser.add_argument('--input', 
                       help='Input file path (if not specified, uses config paths)')
    parser.add_argument('--output',
                       help='Output file path (if not specified, uses config paths or generates name)')
    
    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)
    
    args = parser.parse_args()

    # Default to XML to Excel conversion if neither specified
    if not args.to_excel and not args.to_xml:
        args.to_excel = True

    if args.to_excel and args.to_xml:
        parser.error("Cannot specify both --to-excel and --to-xml")
    
    try:
        # Load configuration
        config = DayZTool.load_config(args.profile)
        
        # Create and run the tool
        tool = TypesToExcelTool(config)
        return tool.run(args.input, args.output, args.to_excel)
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        import traceback
        logging.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

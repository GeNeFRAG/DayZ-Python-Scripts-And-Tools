"""
Base classes for DayZ Admin Tools.

This module provides base classes used throughout the package.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Set, Tuple
from collections import OrderedDict, Counter
from datetime import datetime
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Import standard ElementTree first
import xml.etree.ElementTree as StdET

# Check if lxml is available
try:
    from lxml import etree as LxmlET
    HAS_LXML = True
    # Use lxml for ET
    ET = LxmlET
except ImportError:
    # Use standard ElementTree
    ET = StdET
    logger.warning("lxml not available. Using standard ElementTree which may not preserve formatting.")
    HAS_LXML = False

# Custom ElementTree class for preserving comments with standard ElementTree
class StdCommentedTreeBuilder(StdET.TreeBuilder):
    """Custom TreeBuilder for standard ElementTree that preserves comments."""
    def comment(self, data):
        self.start(StdET.Comment, {})
        self.data(data)
        self.end(StdET.Comment)

class DayZTool(ABC):
    """Base class for all DayZ admin tools."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the tool.
        
        Args:
            config: Optional configuration dictionary.
        """
        self.config = config or {}
        self.setup_logging()
    
    @staticmethod
    def add_standard_arguments(parser):
        """
        Add standard arguments that should be consistent across all command-line tools.
        
        This helper ensures all DayZ Admin Tools have consistent command-line interfaces.
        
        Args:
            parser: The ArgumentParser instance to add arguments to
        """
        parser.add_argument("--profile", default=None,
                          help="Configuration profile to use (default: use default profile)")
        parser.add_argument("--console", action="store_true",
                          help="Log detailed output summary (in addition to regular logging)")
    
    @staticmethod
    def load_config(profile: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from a specified profile.
        
        Args:
            profile: Name of the profile to load. If None, uses the default profile.
            
        Returns:
            The configuration dictionary.
        """
        from config.config import Config
        
        config_obj = Config(profile=profile)
        config_data = config_obj.get()
        
        # Set up logging based on config
        log_level = config_data.get('general', {}).get('log_level', 'INFO').upper()
        
        # Reset any existing handlers to avoid duplicated logs
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        # Apply logging configuration
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Also set the log level for the root logger
        logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))
        
        logging.debug(f"Logging initialized with level: {log_level}")
        
        return config_data

    def setup_logging(self, level: int = logging.INFO):
        """
        Set up logging for this tool.
        
        Args:
            level: The logging level to use.
        """
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(level=level, format=log_format)
        
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: The configuration key.
            default: Default value if the key is not found.
            
        Returns:
            The configuration value, or the default if not found.
        """
        parts = key.split('.')
        value = self.config
        
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
                
        return value
        
    @abstractmethod
    def run(self) -> Any:
        """
        Run the tool. Must be implemented by subclasses.
        
        Returns:
            The result of running the tool.
        """
        pass

class FileBasedTool(DayZTool):
    """Base class for tools that work with files."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the file-based tool.
        
        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        self.log_dir = None
        self.output_dir = None
        self.default_types_file = None
        
    def initialize_directories(self):
        """
        Initialize common directories from configuration.
        Sets up log and output directories.
        """
        # Get log and output directories from config
        self.log_dir = self.get_config('general.log_download_path', 'logs')
        self.output_dir = self.get_config('general.output_path', 'output')
        self.default_types_file = self.get_config('paths.types_file', None)
        
        # Resolve the paths
        resolved_log_dir = self.resolve_path(self.log_dir)
        resolved_output_dir = self.resolve_path(self.output_dir)
        
        # Create directories if they don't exist
        if self.log_dir:
            os.makedirs(resolved_log_dir, exist_ok=True)
            logger.info(f"Log directory: {resolved_log_dir}")
            
        if self.output_dir:
            os.makedirs(resolved_output_dir, exist_ok=True)
            logger.info(f"Output directory: {resolved_output_dir}")
            
        if self.default_types_file:
            logger.debug(f"Default types file: {self.resolve_path(self.default_types_file)}")
        
    def resolve_path(self, path: str) -> str:
        """
        Resolve a path, expanding user paths and environment variables.
        
        Args:
            path: The path to resolve.
            
        Returns:
            The resolved absolute path.
        """
        expanded_path = os.path.expanduser(os.path.expandvars(path))
        return os.path.abspath(expanded_path)
        
    def ensure_dir(self, directory: str) -> str:
        """
        Ensure a directory exists, create it if it doesn't.
        
        Args:
            directory: The directory path.
            
        Returns:
            The absolute path to the directory.
        """
        path = Path(self.resolve_path(directory))
        os.makedirs(path, exist_ok=True)
        return str(path)
        
    def backup_file(self, file_path: str, backup_dir: Optional[str] = None) -> str:
        """
        Create a backup of a file.
        
        Args:
            file_path: Path to the file to back up.
            backup_dir: Directory to store the backup in.
            
        Returns:
            Path to the backup file.
        """
        from datetime import datetime
        import shutil
        
        source_path = Path(self.resolve_path(file_path))
        
        if backup_dir:
            backup_path = Path(self.ensure_dir(backup_dir)) / f"{source_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{source_path.suffix}"
        else:
            backup_path = source_path.with_name(f"{source_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{source_path.suffix}")
        
        shutil.copy2(str(source_path), str(backup_path))
        logger.info(f"Created backup: {backup_path}")
        return str(backup_path)
    
    def write_csv(self, data_rows: List, output_path: str, headers: List[str] = None) -> str:
        """
        Write data to a CSV file.
        
        Args:
            data_rows: List of dictionaries with data to write
            output_path: Path to the output CSV file
            headers: Optional list of header columns (if None, uses keys from first row)
            
        Returns:
            Absolute path to the created CSV file
        """
        import csv
        
        # Check if the path already includes the output directory to avoid nesting
        if hasattr(self, 'output_dir') and self.output_dir:
            output_dir_norm = os.path.normpath(self.output_dir)
            output_path_norm = os.path.normpath(output_path)
            
            # Only join with output_dir if the path doesn't already start with it
            # and if it's not an absolute path
            if not os.path.isabs(output_path) and not output_path_norm.startswith(output_dir_norm):
                output_path = os.path.join(self.output_dir, output_path)
        
        resolved_path = self.resolve_path(output_path)
        logger.debug(f"Writing CSV to {resolved_path}")
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
        
        if not data_rows:
            logger.warning("No data to write to CSV.")
            with open(resolved_path, "w", newline="") as f:
                if headers:
                    writer = csv.writer(f)
                    writer.writerow(headers)
            logger.info(f"Empty CSV file created at {resolved_path}")
            return resolved_path
        
        # Get headers from the first row if not provided
        if headers is None and data_rows:
            if isinstance(data_rows[0], dict):
                headers = list(data_rows[0].keys())
        
        with open(resolved_path, "w", newline="") as f:
            if isinstance(data_rows[0], dict) and headers:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data_rows)
            else:
                writer = csv.writer(f)
                if headers:
                    writer.writerow(headers)
                writer.writerows(data_rows)
        
        logger.info(f"Results written to {resolved_path}")
        return resolved_path
    
    def read_csv(self, csv_file: str, required_columns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Read data from a CSV file.
        
        Args:
            csv_file: Path to the CSV file to read
            required_columns: Optional list of column names that must be present
            
        Returns:
            List of dictionaries representing the CSV rows
            
        Raises:
            FileNotFoundError: If the CSV file doesn't exist
            KeyError: If required columns are missing
        """
        import csv
        
        resolved_path = self.resolve_path(csv_file)
        
        if not os.path.exists(resolved_path):
            raise FileNotFoundError(f"CSV file not found: {resolved_path}")
        
        data_rows = []
        
        with open(resolved_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Check for required columns
            if required_columns:
                missing_columns = set(required_columns) - set(reader.fieldnames)
                if missing_columns:
                    raise KeyError(f"Required columns missing from CSV: {missing_columns}. Available columns: {reader.fieldnames}")
            
            # Read all rows
            for row in reader:
                data_rows.append(dict(row))
        
        logger.info(f"Read {len(data_rows)} rows from {resolved_path}")
        return data_rows
    
    def generate_timestamped_filename(self, base_name: str, extension: str, prefix: str = "", suffix: str = "") -> str:
        """
        Generate a filename with a timestamp.
        
        Args:
            base_name: The base name for the file
            extension: File extension (without the dot)
            prefix: Optional prefix to add before the timestamp
            suffix: Optional suffix to add after the timestamp
            
        Returns:
            A filename in the format: base_name_prefix_YYYYMMDD_HHMMSS_suffix.extension
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Handle prefix and suffix
        prefix_str = f"{prefix}_" if prefix else ""
        suffix_str = f"_{suffix}" if suffix else ""
        
        # Construct filename
        filename = f"{base_name}_{prefix_str}{timestamp}{suffix_str}.{extension}"
        
        # Clean up double underscores or other formatting issues
        filename = filename.replace("__", "_").replace("__", "_")
        
        return filename
    
    def get_timestamp_str(self, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        Get a formatted timestamp string.
        
        Args:
            format_str: The datetime format string (default: "%Y-%m-%d %H:%M:%S")
            
        Returns:
            A timestamp string in the specified format
        """
        return datetime.now().strftime(format_str)
    
class XMLTool(FileBasedTool):
    """Base class for tools that work with XML files."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the XML tool.
        
        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        
        # Check if lxml is available and log a warning if not
        if not HAS_LXML:
            logger.warning("lxml is not installed. For best results, install lxml: pip install lxml")

    # _indent method removed in favor of using the more reliable _post_process_xml method
        
    def read_xml(self, file_path: str, preserve_comments: bool = False):
        """
        Read an XML file.
        
        Args:
            file_path: Path to the XML file.
            preserve_comments: Whether to preserve XML comments.
            
        Returns:
            The root element of the XML file.
        """
        import xml.etree.ElementTree as ET
        
        resolved_path = self.resolve_path(file_path)
        logger.info(f"Reading XML file: {resolved_path}")
        
        if preserve_comments:
            # Use appropriate parser based on available libraries
            if HAS_LXML:
                # lxml has built-in comment handling
                parser = LxmlET.XMLParser(remove_comments=False)
                return LxmlET.parse(resolved_path, parser=parser).getroot()
            else:
                # Use our custom comment handler with standard ElementTree
                parser = StdET.XMLParser(target=StdCommentedTreeBuilder())
                return StdET.parse(resolved_path, parser=parser).getroot()
        else:
            return ET.parse(resolved_path).getroot()
    def _post_process_xml(self, file_path: str, pretty: bool = True) -> None:
        """
        Post-process an XML file for proper formatting.
        This uses the xml.dom.minidom library to ensure consistent and correct indentation.
        
        Args:
            file_path: Path to the XML file to format
            pretty: Whether to apply pretty formatting
        """
        if not pretty:
            return
            
        try:
            import xml.dom.minidom as minidom
            
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
                
            # Parse and format the XML
            parsed_dom = minidom.parseString(xml_content)
            
            # Format with two spaces for indentation
            formatted_xml = parsed_dom.toprettyxml(indent="    ")
            
            # Fix extra whitespace that minidom tends to add
            lines = formatted_xml.splitlines()
            formatted_lines = [line for line in lines if line.strip()]
            
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(formatted_lines))
                
            logger.info(f"Applied XML formatting with minidom to: {file_path}")
                
            logger.info(f"Applied post-processing formatting to XML file: {file_path}")
        except Exception as e:
            logger.warning(f"Could not post-process XML file for formatting: {str(e)}")

        
    def write_xml(self, root, file_path: str, pretty: bool = True, xml_declaration: bool = True):
        """
        Write an XML element tree to a file.
        
        Args:
            root: The root element to write.
            file_path: Path to the output file.
            pretty: Whether to format the XML with indentation.
            xml_declaration: Whether to include XML declaration.
        """
        resolved_path = self.resolve_path(file_path)
        logger.info(f"Writing XML file: {resolved_path}")
        
        # Make sure target directory exists
        self.ensure_dir(os.path.dirname(resolved_path))
        
        try:
            # Choose the appropriate XML library based on what's available
            if HAS_LXML:
                # Use lxml for better comment handling
                if pretty:
                    # Apply pretty formatting if requested
                    xml_str = LxmlET.tostring(
                        root, 
                        encoding="utf-8", 
                        pretty_print=True,
                        xml_declaration=xml_declaration
                    )
                else:
                    xml_str = LxmlET.tostring(
                        root, 
                        encoding="utf-8", 
                        xml_declaration=xml_declaration
                    )
                
                # Write the file
                with open(resolved_path, 'wb') as f:
                    f.write(xml_str)
                    
                logger.info(f"XML file written successfully using lxml: {resolved_path}")
            else:
                # Use standard ElementTree
                tree = StdET.ElementTree(root)
                
                # Write the file
                tree.write(resolved_path, encoding="utf-8", xml_declaration=xml_declaration)
                logger.info(f"XML file written successfully using standard ElementTree: {resolved_path}")
                
            # Apply post-processing for consistent formatting
            if pretty:
                self._post_process_xml(resolved_path, pretty=True)
                
        except Exception as e:
            logger.error(f"Error writing XML file: {str(e)}")
            
            # Fallback method - direct file copy for preservation
            try:
                # If we have backup in place already, we can restore from it
                # Otherwise, try a raw string approach
                logger.warning(f"Trying fallback method for writing XML...")
                
                # Create string representation manually
                xml_str = StdET.tostring(root, encoding="unicode")
                
                # Add XML declaration if requested
                if xml_declaration:
                    header = '<?xml version="1.0" encoding="utf-8"?>\n'
                    xml_content = header + xml_str
                else:
                    xml_content = xml_str
                
                # Write to file
                with open(resolved_path, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                    
                logger.info(f"XML file written with fallback method: {resolved_path}")
            except Exception as e2:
                logger.error(f"Fallback method also failed: {str(e2)}")
                raise RuntimeError(f"Failed to write XML file: {str(e)} (Fallback error: {str(e2)})")
    
    def read_xml_with_comments(self, file_path: str):
        """
        Read an XML file preserving comments.
        
        Args:
            file_path: Path to the XML file.
            
        Returns:
            The root element of the XML file with preserved comments.
        """
        # This is a convenience method that calls read_xml with preserve_comments=True
        try:
            return self.read_xml(file_path, preserve_comments=True)
        except Exception as e:
            logger.error(f"Error reading XML with comments: {str(e)}")
            
            # Alternative approach - use direct parsing based on available libraries
            resolved_path = self.resolve_path(file_path)
            
            if HAS_LXML:
                try:
                    parser = LxmlET.XMLParser(remove_comments=False)
                    return LxmlET.parse(resolved_path, parser).getroot()
                except Exception as lxml_error:
                    logger.error(f"lxml parsing failed: {str(lxml_error)}")
                    raise RuntimeError(f"Failed to parse XML with comments: {str(e)}")
            else:
                # Without lxml, we have limited options for comment preservation
                logger.warning("Comment preservation might be limited without lxml installed")
                return StdET.parse(resolved_path).getroot()
    
    def filter_types_by_name(self, root, pattern: str = None):
        """
        Filter types by a name pattern using fnmatch.
        
        Args:
            root: XML root element
            pattern: Wildcard pattern to match type names
            
        Returns:
            List of matching type elements
        """
        if not pattern:
            return root.findall("type")
            
        import fnmatch
        return [
            type_elem for type_elem in root.findall("type")
            if 'name' in type_elem.attrib and fnmatch.fnmatch(type_elem.attrib['name'], pattern)
        ]
    
    def get_type_values(self, type_elem, element_names: List[str]):
        """
        Extract multiple element values from a type element.
        
        Args:
            type_elem: The type element to extract from
            element_names: List of element names to extract
            
        Returns:
            Dictionary of element names to their values
        """
        values = {}
        name = type_elem.get('name', '')
        values['name'] = name
        
        for elem_name in element_names:
            elem = type_elem.find(elem_name)
            values[elem_name] = elem.text if elem is not None else None
        
        return values
    
    def build_type_dict(self, xml_file: str, elements: List[str] = None):
        """
        Build a dictionary of types and their element values from an XML file.
        
        Args:
            xml_file: Path to the XML file
            elements: List of elements to extract (default: all child elements)
            
        Returns:
            Dictionary mapping type names to their element values
        """
        root = self.read_xml(xml_file)
        type_dict = {}
        
        for type_elem in root.findall("type"):
            name = type_elem.get('name')
            if not name:
                continue
                
            type_dict[name] = {}
            
            if elements:
                # Extract only specified elements
                for elem_name in elements:
                    elem = type_elem.find(elem_name)
                    type_dict[name][elem_name] = elem.text if elem is not None else None
            else:
                # Extract all child elements
                for child in type_elem:
                    type_dict[name][child.tag] = child.text
        
        return type_dict
    
    def sort_items_alphabetically(self, items):
        """
        Sorts items alphabetically by their 'name' attribute.

        Args:
            items: List of XML elements representing items.

        Returns:
            Sorted list of XML elements.
        """
        return sorted(items, key=lambda x: x.get('name'))

    def sort_items_by_usage(self, items):
        """
        Sorts items by their 'usage' attribute. Items with multiple usages are grouped into combined sections.
        Items with no usage are grouped under 'NO USAGE' category.

        Args:
            items: List of XML elements representing items.

        Returns:
            Dictionary with usages as keys and lists of items as values.
        """
        usages = {}
        no_usage_items = []

        for item in items:
            usage_elements = item.findall('usage')
            if not usage_elements:
                no_usage_items.append(item)
                continue
                
            usage_list = [usage.text for usage in usage_elements if usage.text]
            if usage_list:
                usage_key = ', '.join(sorted(usage_list))
                if usage_key not in usages:
                    usages[usage_key] = []
                usages[usage_key].append(item)

        # Sort items within each usage category alphabetically
        for usage_key in usages:
            usages[usage_key] = self.sort_items_alphabetically(usages[usage_key])

        # Add the "NO USAGE" category with sorted items
        if no_usage_items:
            usages["NO USAGE"] = self.sort_items_alphabetically(no_usage_items)

        # Return OrderedDict with sorted keys
        return OrderedDict(sorted(usages.items()))
    
    def create_index_comment(self, usages):
        """
        Creates an index comment for the usage categories.
        
        Args:
            usages: Dictionary with usage names as keys.
            
        Returns:
            String containing the formatted index text.
        """
        index_text = "INDEX OF CATEGORIES:\n"
        index_text += "==================================================\n"
        for i, usage in enumerate(sorted(usages.keys()), 1):
            index_text += f" {i:2d}. {usage.upper()}\n"
        index_text += "=================================================="
        return index_text
    
    def organize_types_xml(self, input_xml_file: str, output_xml_file: str):
        """
        Organizes the types.xml file by sorting items into usage categories.

        Args:
            input_xml_file: Path to the input types.xml file.
            output_xml_file: Path to the output XML file.
        """
        resolved_input = self.resolve_path(input_xml_file)
        resolved_output = self.resolve_path(output_xml_file)
        
        if HAS_LXML:
            parser = ET.XMLParser(remove_blank_text=False)
            tree = ET.parse(resolved_input, parser)
        else:
            tree = ET.parse(resolved_input)
            
        root = tree.getroot()

        items = root.findall('.//type')
        logger.info(f"Found {len(items)} items in {input_xml_file}")
        
        sorted_items = self.sort_items_alphabetically(items)
        usages = self.sort_items_by_usage(sorted_items)
        logger.info(f"Organized items into {len(usages)} usage categories")

        # Clear the root and add initial newline
        root.clear()
        root.text = '\n'  # This adds the newline after <types>
        
        # Create index comment
        index_text = self.create_index_comment(usages)
        
        if HAS_LXML:
            index_comment = ET.Comment(index_text)
            root.append(index_comment)
            index_comment.tail = '\n\n'

            # Add categories and their items
            for usage, items in usages.items():
                comment = ET.Comment(f" ################ [{usage.upper()}] ################")
                root.append(comment)
                comment.tail = '\n'
                
                for item in items:
                    root.append(item)
                    item.tail = '\n'
                
                # Add extra newline between categories
                if items:
                    items[-1].tail = '\n\n'

            # Ensure output directory exists
            output_path = Path(resolved_output)
            os.makedirs(output_path.parent, exist_ok=True)
            
            tree.write(str(output_path), pretty_print=True, xml_declaration=True, encoding='UTF-8')
        else:
            # Fallback for standard ElementTree
            logger.warning("Using standard ElementTree - formatting may not be preserved correctly")
            
            # Add index as a comment
            root.append(ET.Comment(index_text))
            
            # Add categories and their items
            for usage, items in usages.items():
                root.append(ET.Comment(f" ################ [{usage.upper()}] ################"))
                
                for item in items:
                    root.append(item)
            
            # Ensure output directory exists
            output_path = Path(resolved_output)
            os.makedirs(output_path.parent, exist_ok=True)
            
            tree.write(str(output_path), encoding='UTF-8', xml_declaration=True)
        
        logger.info(f"Organized types.xml saved to {output_xml_file}")

    def get_types_by_usage(self, root) -> Dict[str, List]:
        """
        Group types by their usage categories.
        
        Args:
            root: XML root element
            
        Returns:
            Dictionary mapping usage names to lists of type elements
        """
        types_by_usage = {}
        
        for type_elem in self.filter_types_by_name(root):
            # Find all usage elements
            usage_elements = type_elem.findall('usage')
            
            if not usage_elements:
                # No usage elements found, add to "NO USAGE" category
                if "NO USAGE" not in types_by_usage:
                    types_by_usage["NO USAGE"] = []
                types_by_usage["NO USAGE"].append(type_elem)
                continue
            
            # Collect all usage names for this item
            usage_list = [usage.get('name') for usage in usage_elements if usage.get('name')]
            if usage_list:
                usage_key = ', '.join(sorted(usage_list))
                if usage_key not in types_by_usage:
                    types_by_usage[usage_key] = []
                types_by_usage[usage_key].append(type_elem)
            else:
                # Empty usage elements, add to "NO USAGE" category
                if "NO USAGE" not in types_by_usage:
                    types_by_usage["NO USAGE"] = []
                types_by_usage["NO USAGE"].append(type_elem)
        
        # Sort items within each usage group by name
        for usage_name in types_by_usage:
            types_by_usage[usage_name].sort(key=lambda x: x.get('name', ''))
            
        return types_by_usage

    def create_sorted_by_usage_root(self, root, add_index: bool = True) -> Any:
        """
        Create a new XML root with types sorted by usage categories.
        
        Args:
            root: Original XML root element
            add_index: Whether to add an index of categories at the top
            
        Returns:
            New XML root element with sorted types
        """
        # Get types organized by usage
        types_by_usage = self.get_types_by_usage(root)
        
        # Create a new root element using the same Element class as the input root
        if HAS_LXML and root.__class__.__module__ == 'lxml.etree':
            # Using lxml
            new_root = LxmlET.Element('types')
        else:
            # Using standard ElementTree
            new_root = StdET.Element('types')
        
        # Add initial newline
        new_root.text = '\n'
        
        # Add index if requested
        if add_index:
            index_text = "INDEX OF CATEGORIES:\n"
            index_text += "==================================================\n"
            for i, usage in enumerate(sorted(types_by_usage.keys()), 1):
                index_text += f" {i:2d}. {usage.upper()}\n"
            index_text += "=================================================="
            
            if HAS_LXML:
                index_comment = LxmlET.Comment(index_text)
                new_root.append(index_comment)
                index_comment.tail = '\n\n'
            else:
                index_comment = StdET.Comment(index_text)
                new_root.append(index_comment)
                # Unfortunately standard ElementTree doesn't support setting tail on comments
        
        # Add categories and their items
        for usage_name in sorted(types_by_usage.keys()):
            # Add a comment for the usage group
            comment_text = f" ################ [{usage_name.upper()}] ################"
            if HAS_LXML:
                comment = LxmlET.Comment(comment_text)
                new_root.append(comment)
                comment.tail = '\n'
            else:
                comment = StdET.Comment(comment_text)
                new_root.append(comment)
                # Unfortunately standard ElementTree doesn't support setting tail on comments
            
            # Add all items in this usage group
            items = types_by_usage[usage_name]
            for item in items:
                new_root.append(item)
                if HAS_LXML:
                    item.tail = '\n'
            
            # Add extra newline between categories
            if items and HAS_LXML:
                items[-1].tail = '\n\n'
        
        return new_root

    def sort_xml_by_usage(self, xml_file: str, output_file: str = None, add_index: bool = True) -> str:
        """
        Sort types in an XML file by usage categories and write to output file.
        
        Args:
            xml_file: Path to the input XML file
            output_file: Path to the output XML file (if None, overwrites input)
            add_index: Whether to add an index of categories at the top
            
        Returns:
            Path to the output file
        """
        if output_file is None:
            output_file = xml_file
            
        # Read XML file with comments preserved
        root = self.read_xml_with_comments(xml_file)
        
        # Create new sorted root
        new_root = self.create_sorted_by_usage_root(root, add_index)
        
        # Write to output file
        self.write_xml(new_root, output_file, pretty=True, xml_declaration=True)
        
        return output_file
    
    def create_ordered_attributes(self, elem, order: List[str] = None, attribute_map: Dict[str, str] = None):
        """
        Create a dictionary of attributes with a specific order.
        
        Args:
            elem: Element containing attributes.
            order: List of attribute names in desired order.
            attribute_map: Dictionary of attribute values to override.
            
        Returns:
            Dictionary with ordered attributes.
        """
        if order is None:
            order = ['name', 'lootmax']  # Default: name first, then lootmax
            
        attrs = {}
        
        # Add attributes in specified order
        for attr in order:
            # If attribute override map is provided and contains this attribute,
            # use that value instead
            if attribute_map and attr in attribute_map:
                attrs[attr] = attribute_map[attr]
            # Otherwise if the element has this attribute, copy it
            elif attr in elem.attrib:
                attrs[attr] = elem.get(attr)
                
        # Add remaining attributes not in the specified order
        for attr, value in elem.attrib.items():
            if attr not in order:
                attrs[attr] = value
                
        return attrs
    
    def copy_element_with_structure(self, elem, parent, order: List[str] = None, 
                                   attribute_maps: Dict[str, Dict[str, str]] = None):
        """
        Copy an element and all its children, preserving comments and with ordered attributes.
        
        Args:
            elem: Element to copy.
            parent: Parent element to attach the copy to.
            order: List of attribute names in desired order.
            attribute_maps: Dictionary mapping element key to attribute override map.
            
        Returns:
            The copied element.
        """
        if isinstance(elem.tag, str):  # Normal element
            # Get element key for attribute map lookup
            elem_key = None
            if attribute_maps and 'name' in elem.attrib:
                elem_name = elem.get('name')
                # Check if this element is in the attribute map
                for key in attribute_maps:
                    if key == elem_name or key == elem.tag:
                        elem_key = key
                        break
            
            # Get attribute override map if this element has one
            attribute_map = attribute_maps.get(elem_key, {}) if attribute_maps else None
            
            # Create ordered attributes
            attrs = self.create_ordered_attributes(elem, order, attribute_map)
            
            # Create new element with the attributes
            new_elem = ET.SubElement(parent, elem.tag, attrs)
            
            # Copy text content
            if elem.text and elem.text.strip():
                new_elem.text = elem.text
                
            # Recursively copy children
            for child in elem:
                self.copy_element_with_structure(child, new_elem, order, attribute_maps)
                
            # Copy tail text
            if elem.tail and elem.tail.strip():
                new_elem.tail = elem.tail
                
            return new_elem
            
        else:  # Comment or processing instruction
            if elem.tag is ET.Comment:
                comment = ET.Comment(elem.text)
                parent.append(comment)
                if elem.tail and elem.tail.strip():
                    comment.tail = elem.tail
                return comment
            else:
                return None
            
    def _build_xml_lookup(self, elem, lookup_dict, key_attrs, parent_key=None):
        """
        Build a lookup dictionary of elements from an XML structure.
        
        Args:
            elem: Current element to process
            lookup_dict: Dictionary to populate
            key_attrs: List of attribute names to use as keys
            parent_key: Key of parent element (for hierarchical lookup)
        """
        # Skip comments
        if not isinstance(elem.tag, str):
            return
            
        # Create key for this element
        elem_key = None
        for key_attr in key_attrs:
            if key_attr in elem.attrib:
                elem_key = elem.get(key_attr)
                break
                
        if elem_key:
            # Store element attributes
            full_key = f"{parent_key}/{elem_key}" if parent_key else elem_key
            lookup_dict[full_key] = dict(elem.attrib)
            
        # Process child elements
        for child in elem:
            if isinstance(child.tag, str):  # Skip comments
                self._build_xml_lookup(child, lookup_dict, key_attrs, 
                                     parent_key=elem_key if elem_key else parent_key)
                

    
class EventAnalyzerTool(XMLTool):
    """Base class for tools that analyze static events and their groups."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the static event analyzer tool.
        
        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)
        self.ignore_types: Set[str] = set()
        
    def get_event_config(self, events_root, event_name: str) -> Tuple[bool, int]:
        """
        Get event configuration (active status and nominal value).
        
        Args:
            events_root: Root element of events.xml
            event_name: Name of the event to find
            
        Returns:
            Tuple of (is_active, nominal_value)
        """
        for event in events_root.findall('event'):
            values = self.get_type_values(event, ['active', 'nominal'])
            if values.get('name') == event_name:
                active = values.get('active', '0').strip() == '1'
                try:
                    nominal = int(values.get('nominal', '0').strip())
                except ValueError:
                    nominal = 0
                return active, nominal
        return False, 0
        
    def get_group_items(self, groups_root, group_name: str) -> Counter:
        """
        Get item counts from a specific group.
        
        Args:
            groups_root: Root element of cfgeventgroups.xml
            group_name: Name of the group to find
            
        Returns:
            Counter with item types and their counts
        """
        item_counts = Counter()
        
        for group in groups_root.findall('.//group'):
            values = self.get_type_values(group, [])
            if values.get('name') == group_name:
                for child in group.findall('child'):
                    item_type = child.get('type')
                    if item_type and item_type not in self.ignore_types:
                        item_counts[item_type] += 1
                return item_counts  # Return after finding the group
        
        logger.warning(f"Group '{group_name}' not found.")
        return item_counts
        
    def write_item_counts(self, item_counts: Counter, output_path: str) -> str:
        """
        Write item counts to a CSV file.
        
        Args:
            item_counts: Counter of item types and their counts
            output_path: Path to the output CSV file
            
        Returns:
            Path to the written CSV file
        """
        data_rows = [
            {"item": item, "count": count} 
            for item, count in sorted(item_counts.items())
        ]
        return self.write_csv(data_rows, output_path, headers=["item", "count"])
        
    def analyze_static_event(self, events_path: str, groups_path: str, 
                           event_name: str, group_name: str) -> Dict[str, Any]:
        """
        Analyze a static event and its associated group.
        
        Args:
            events_path: Path to the events.xml file
            groups_path: Path to the cfgeventgroups.xml file
            event_name: Name of the event to analyze
            group_name: Name of the group to analyze
            
        Returns:
            Dictionary with analysis results
        """
        # Check events.xml for event configuration
        logger.info(f"Reading events from: {events_path}")
        events_root = self.read_xml(events_path)
        
        event_active, nominal = self.get_event_config(events_root, event_name)
        
        if not event_active:
            logger.warning(f"{event_name} event is not active. No loot will be counted.")
            return {
                "active": False,
                "nominal": 0,
                "item_counts": Counter()
            }
        
        if nominal == 0:
            logger.warning(f"Could not find <nominal> value for {event_name} event, or it is 0.")
        
        logger.info(f"{event_name} nominal value: {nominal}")
        
        # Check cfgeventgroups.xml for group configuration
        logger.info(f"Reading group '{group_name}' from: {groups_path}")
        groups_root = self.read_xml(groups_path)
        
        # Get item counts from group
        base_counts = self.get_group_items(groups_root, group_name)
        
        # Multiply counts by nominal if needed
        item_counts = Counter()
        for item, count in base_counts.items():
            item_counts[item] = count * nominal
        
        return {
            "active": event_active,
            "nominal": nominal,
            "item_counts": item_counts
        }
class JSONTool(FileBasedTool):
    """Base class for tools that work with JSON files."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the JSON tool.
        
        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        self.initialize_directories()
        
    def read_json(self, file_path: str) -> Any:
        """
        Read a JSON file.
        
        Args:
            file_path: Path to the JSON file.
            
        Returns:
            The parsed JSON content.
            
        Raises:
            json.JSONDecodeError: If the file contains invalid JSON.
            FileNotFoundError: If the file doesn't exist.
        """
        import json
        
        resolved_path = self.resolve_path(file_path)
        logger.debug(f"Reading JSON file: {resolved_path}")
        
        with open(resolved_path, 'r') as f:
            return json.load(f)
            
    def write_json(self, data: Any, file_path: str, indent: int = 2) -> str:
        """
        Write data to a JSON file.
        
        Args:
            data: The data to write.
            file_path: Path to the output file.
            indent: Number of spaces for indentation (default: 2).
            
        Returns:
            The absolute path to the created file.
            
        Raises:
            IOError: If the file cannot be written.
        """
        import json
        
        # Check if the path already includes the output directory to avoid nesting
        if hasattr(self, 'output_dir') and self.output_dir:
            output_dir_norm = os.path.normpath(self.output_dir)
            file_path_norm = os.path.normpath(file_path)
            
            # Only join with output_dir if the path doesn't already start with it
            if not os.path.isabs(file_path) and not file_path_norm.startswith(output_dir_norm):
                file_path = os.path.join(self.output_dir, file_path)
        
        resolved_path = self.resolve_path(file_path)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
        
        with open(resolved_path, 'w') as f:
            json.dump(data, f, indent=indent)
            
        logger.info(f"JSON data written to {resolved_path}")
        return resolved_path
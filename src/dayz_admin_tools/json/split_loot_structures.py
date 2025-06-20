"""
Split Loot Structures Tool

Split DayZ JSON objects into loot and structures based on types.xml.
Takes a JSON file containing mixed objects and separates them based on 
whether they are defined as loot in types.xml.
"""

import json
import argparse
import xml.etree.ElementTree as ET
import os
from typing import Dict, Any, Optional, Set

# Import base class and logger
from ..base import JSONTool, logger

__all__ = ['SplitLootStructures', 'main']

# Configuration loading is now handled by DayZTool.load_config()


class SplitLootStructures(JSONTool):
    """
    Split DayZ JSON objects into loot and structures based on types.xml.
    
    This tool separates objects in a JSON file into loot items and
    structures based on whether they appear in types.xml as lootable items.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the SplitLootStructures tool.
        
        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
       
        # Initialize loot type sets
        self.loot_types = set()
        self.normalized_map = {}
        
    def run(self, types_xml: str, input_json: str, 
            loot_json: Optional[str] = None, 
            structures_json: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the tool to split objects into loot and structures.
        
        Args:
            types_xml: Path to the types.xml file
            input_json: Path to the input JSON file with mixed objects
            loot_json: Path to save the loot objects JSON file. If None, a default path
                      will be used in the standard output directory.
            structures_json: Path to save the structures JSON file. If None, a default path
                           will be used in the standard output directory.
            
        Returns:
            Dictionary with results including counts of each type
        """
        return self.split_objects(types_xml, input_json, loot_json, structures_json)

    def normalize(self, name: str) -> str:
        """
        Normalize a name for loose matching.
        
        Args:
            name: The name to normalize
            
        Returns:
            Normalized name (lowercase with no underscores)
        """
        return name.lower().replace("_", "")

    def get_loot_types(self, xml_path: str) -> Set[str]:
        """
        Extract loot item types from types.xml.
        
        Args:
            xml_path: Path to the types.xml file
            
        Returns:
            Set of loot item names
        """
        logger.info(f"Loading loot types from {xml_path}")
        loot_types = set()
        norm_map = {}
        
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            for type_elem in root.findall('type'):
                name = type_elem.get('name')
                if name:
                    # Store the original name
                    loot_types.add(name)
                    
                    # Create a mapping from normalized to original name
                    norm_name = self.normalize(name)
                    norm_map[norm_name] = name
            
            logger.info(f"Loaded {len(loot_types)} loot types from types.xml")
            
        except (ET.ParseError, FileNotFoundError) as e:
            logger.error(f"Error loading types.xml: {e}")
            raise
            
        self.loot_types = loot_types
        self.normalized_map = norm_map
        
        return loot_types

    def split_objects(self, types_xml: str, input_json: str, 
                     loot_json: Optional[str] = None, 
                     structures_json: Optional[str] = None) -> Dict[str, Any]:
        """
        Split objects in a JSON file into loot and structures.
        
        Args:
            types_xml: Path to the types.xml file
            input_json: Path to the input JSON file with mixed objects
            loot_json: Path to save the loot objects JSON file. If None, a default path
                      will be used in the standard output directory.
            structures_json: Path to save the structures JSON file. If None, a default path
                           will be used in the standard output directory.
            
        Returns:
            Dictionary with results including counts of each type
        """
        # Get loot types from types.xml
        self.get_loot_types(types_xml)
        
        # Load the input JSON file using read_json from the base class
        try:
            data = self.read_json(input_json)
                
            if "Objects" not in data:
                logger.error(f"Invalid JSON format: 'Objects' key not found in {input_json}")
                return {'error': 'Invalid JSON format'}
                
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error reading input JSON: {e}")
            return {'error': str(e)}
        
        # Create output structures
        loot_data = {"Objects": []}
        structures_data = {"Objects": []}
        
        # Process each object and track loot item counts
        loot_summary = {}
        
        for obj in data["Objects"]:
            if "name" not in obj:
                logger.warning(f"Object without 'name' found, skipping")
                continue
                
            name = obj["name"]
            normalized = self.normalize(name)
            
            # Determine if it's loot or structure
            if name in self.loot_types or normalized in self.normalized_map:
                loot_data["Objects"].append(obj)
                # Add to loot summary count
                if name in loot_summary:
                    loot_summary[name] += 1
                else:
                    loot_summary[name] = 1
            else:
                structures_data["Objects"].append(obj)
        
        # Determine output file paths, using standard output directory if not specified
        input_basename = os.path.basename(input_json)
        input_stem = os.path.splitext(input_basename)[0]
        
        if loot_json is None:
            loot_json = os.path.join(self.output_dir, f"{input_stem}_loot.json")
        elif not os.path.isabs(loot_json):
            loot_json = os.path.join(self.output_dir, loot_json)
        
        if structures_json is None:
            structures_json = os.path.join(self.output_dir, f"{input_stem}_structures.json")
        elif not os.path.isabs(structures_json):
            structures_json = os.path.join(self.output_dir, structures_json)
        
        # Ensure output directories exist
        self.ensure_dir(os.path.dirname(loot_json))
        self.ensure_dir(os.path.dirname(structures_json))
        
        # No backups are created
        
        # Save the output files using write_json from the base class
        try:
            loot_output_path = self.write_json(loot_data, loot_json, indent=2)
            logger.info(f"Saved {len(loot_data['Objects'])} loot objects to {loot_output_path}")
                
            structures_output_path = self.write_json(structures_data, structures_json, indent=2)
            logger.info(f"Saved {len(structures_data['Objects'])} structure objects to {structures_output_path}")
                
        except IOError as e:
            logger.error(f"Error saving output files: {e}")
            return {'error': str(e)}
        
        # Prepare results
        result = {
            'total_objects': len(data["Objects"]),
            'loot_objects': len(loot_data["Objects"]),
            'structure_objects': len(structures_data["Objects"]),
            'loot_file': loot_output_path,
            'structures_file': structures_output_path,
            'loot_summary': dict(sorted(loot_summary.items(), key=lambda x: x[1], reverse=True))
        }
        
        return result
def main():
    """
    Main function to run the object splitter as a command-line tool.
    """
    parser = argparse.ArgumentParser(
        description="Split DayZ JSON objects into loot and structures based on types.xml."
    )
    parser.add_argument("--types-xml", required=False,
                      help="Path to types.xml (defaults to paths.types_file from config)")
    parser.add_argument("--input-json", required=True,
                      help="Input JSON file with objects")
    parser.add_argument("--loot-json", default=None,
                      help="Output JSON file for loot objects. If not specified, a default path in the standard output directory will be used.")
    parser.add_argument("--structures-json", default=None,
                      help="Output JSON file for structure objects. If not specified, a default path in the standard output directory will be used.")

    # Add standard arguments from base class
    from ..base import DayZTool
    DayZTool.add_standard_arguments(parser)
    args = parser.parse_args()
    
    # Load configuration using the static method from DayZTool
    config = DayZTool.load_config(args.profile)
    
    # Create and run the tool
    splitter = SplitLootStructures(config)
    
    try:
        # Get types.xml path from config if not provided
        types_xml_path = args.types_xml
        if not types_xml_path:
            types_xml_path = splitter.get_config('paths.types_file')
            logger.info(f"Using types.xml from config: {types_xml_path}")
            
        # Check if input files exist
        if not types_xml_path or not os.path.isfile(types_xml_path):
            parser.error(f"types.xml file not found: {types_xml_path}")
            
        if not os.path.isfile(args.input_json):
            parser.error(f"Input JSON file not found: {args.input_json}")
            
        # Use the run method which is required by the base class
        results = splitter.run(
            types_xml_path, 
            args.input_json, 
            args.loot_json, 
            args.structures_json
        )
        
        if 'error' not in results:
            logger.info(f"Split completed successfully:")
            logger.info(f"  Total objects: {results['total_objects']}")
            logger.info(f"  Loot objects: {results['loot_objects']}")
            logger.info(f"  Structure objects: {results['structure_objects']}")
            logger.info(f"  Loot file: {results['loot_file']}")
            logger.info(f"  Structures file: {results['structures_file']}")
            logger.info(f"  Output directory: {splitter.output_dir}")
            
            # Additional output when --console flag is used
            if args.console:
                logger.info("\nSummary:")
                logger.info(f"Input JSON file: {args.input_json}")
                logger.info(f"Types.xml file: {types_xml_path}")
                if 'loot_summary' in results and results['loot_summary']:
                    logger.info("\nTop 10 loot items:")
                    for item_name, count in list(results['loot_summary'].items())[:10]:
                        logger.info(f"  - {item_name}: {count}x")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    main()

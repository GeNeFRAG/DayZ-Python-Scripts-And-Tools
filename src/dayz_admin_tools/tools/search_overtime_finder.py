"""
Search Overtime Finder Tool

Find unique items causing search overtime and performance drops in DayZ server logs.
Supports processing multiple log files and wildcard patterns (e.g. *.RPT).
"""

import re
import argparse
import logging
import os
import glob
from typing import Dict, Any, Optional, Set, List
from datetime import datetime
from collections import Counter

# Import the base tool classes
from ..base import DayZTool, FileBasedTool

__all__ = ['SearchOvertimeFinder', 'main']

# Configure logging
logger = logging.getLogger(__name__)


class SearchOvertimeFinder(FileBasedTool):
    """
    Tool to find items causing search overtime and performance drops in server logs.
    
    This tool analyzes server RPT logs to identify items that are:
    1. Causing search overtime (excessive search time to place items)
    2. Hard to place (causing performance drops)
    
    The tool tracks how often each issue occurs for each item, helping to
    prioritize which items need configuration adjustments most urgently.

    It also exports CSV reports with details about each problematic item.
    These items often indicate configuration issues with loot spawning.
    """
    
    # Class constants
    TOP_ITEMS_DISPLAY_LIMIT = 5  # Number of top items to display in console output
    
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the search overtime finder tool.
        
        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        self.initialize_directories()
        self.load_patterns()
        self.files_processed = 0
        
    def load_patterns(self) -> None:
        """Load and compile the regex patterns for parsing log files."""
        # Get patterns from config
        patterns = self.get_config('search_overtime_finder.patterns', {})
        
        # Load patterns - using exactly the same regex patterns as in the original script
        overtime_pattern = patterns.get('overtime', 'Item \\[\\d+\\] causing search overtime: \"(.*?)\"')
        hard_to_place_pattern = patterns.get(
            'hard_to_place', 
            'LootRespawner\\] \\(PRIDummy\\) :: Item \\[\\d+\\] is hard to place, performance drops: \"(.*?)\"'
        )
        
        # Compile patterns
        self.patterns = {
            'overtime': re.compile(overtime_pattern),
            'hard_to_place': re.compile(hard_to_place_pattern)
        }
        
        logger.debug(f"Loaded regex patterns: overtime: '{overtime_pattern}'")
        logger.debug(f"Loaded regex patterns: hard_to_place: '{hard_to_place_pattern}'")
        
    def validate_log_file(self, file_path: str) -> bool:
        """
        Validate that a log file exists and is readable.
        
        Args:
            file_path: Path to the log file to validate.
            
        Returns:
            True if file is valid, False otherwise.
        """
        if not os.path.exists(file_path):
            logger.error(f"Log file does not exist: {file_path}")
            return False
            
        if not os.path.isfile(file_path):
            logger.error(f"Path is not a file: {file_path}")
            return False
            
        if not os.access(file_path, os.R_OK):
            logger.error(f"Log file is not readable: {file_path}")
            return False
            
        return True
        
    def process_log_file(self, file_path: str) -> Dict[str, Dict[str, int]]:
        """
        Process a single log file to extract search overtime and hard to place items.
        
        Args:
            file_path: Path to the log file.
            
        Returns:
            Dictionary with two keys: 'overtime', 'hard_to_place'.
            Each contains a dictionary of item names to occurrence counts.
        """
        logger.info(f"Processing log file: {file_path}")
        
        # Validate log file first
        if not self.validate_log_file(file_path):
            logger.warning(f"Skipping invalid log file: {file_path}")
            return {
                'overtime': Counter(),
                'hard_to_place': Counter()
            }
        
        # Initialize results structure with Counter objects to track occurrences
        results = {
            'overtime': Counter(),
            'hard_to_place': Counter()
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # Check for search overtime entries
                    match = self.patterns['overtime'].search(line)
                    if match:
                        item_name = match.group(1)
                        results['overtime'][item_name] += 1
                        
                    # Check for hard to place entries
                    match = self.patterns['hard_to_place'].search(line)
                    if match:
                        item_name = match.group(1)
                        results['hard_to_place'][item_name] += 1
            
            # Update processed files counter
            self.files_processed += 1
            logger.info(
                f"Found {sum(results['overtime'].values())} search overtime occurrences "
                f"for {len(results['overtime'])} unique items"
            )
            logger.info(
                f"Found {sum(results['hard_to_place'].values())} hard to place occurrences "
                f"for {len(results['hard_to_place'])} unique items"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing log file {file_path}: {str(e)}")
            return results
            
    def export_results(self, results: Dict[str, Set[str]], prefix: str = "problematic_items") -> Dict[str, str]:
        """
        Export results to CSV files.
        
        Args:
            results: Dictionary with the combined results from all log files.
            prefix: Prefix for the output files.
            
        Returns:
            Dictionary with paths to the generated CSV files.
        """
        # Generate timestamp for report
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        outputs = {}
        
        # Export search overtime items
        overtime_file = self.generate_timestamped_filename(f"{prefix}_overtime", "csv")
        if results['overtime']:
            # Convert set to list of dictionaries for CSV export
            overtime_data = []
            
            # Add timestamp as the first row
            overtime_data.append({"Report Generated": current_timestamp})
            
            # Add an empty row for better readability
            overtime_data.append({})
            
            # Add item data
            for item_name, count in sorted(results['overtime'].items(), key=lambda x: x[1], reverse=True):
                overtime_data.append({"item_name": item_name, "occurrences": count})
            
            # Use write_csv from FileBasedTool
            file_path = self.write_csv(overtime_data, overtime_file, 
                                    headers=["Report Generated", "item_name", "occurrences"])
            
            outputs['overtime'] = file_path
            logger.info(f"Search overtime results saved to: {overtime_file} (timestamp: {current_timestamp})")
        
        # Export hard to place items
        hard_place_file = self.generate_timestamped_filename(f"{prefix}_hard_to_place", "csv")
        if results['hard_to_place']:
            # Convert set to list of dictionaries for CSV export
            hard_place_data = []
            
            # Add timestamp as the first row
            hard_place_data.append({"Report Generated": current_timestamp})
            
            # Add an empty row for better readability
            hard_place_data.append({})
            
            # Add item data
            for item_name, count in sorted(results['hard_to_place'].items(), key=lambda x: x[1], reverse=True):
                hard_place_data.append({"item_name": item_name, "occurrences": count})
            
            # Use write_csv from FileBasedTool
            file_path = self.write_csv(hard_place_data, hard_place_file, 
                                     headers=["Report Generated", "item_name", "occurrences"])
            
            outputs['hard_to_place'] = file_path
            logger.info(f"Hard to place items saved to: {hard_place_file} (timestamp: {current_timestamp})")
        
        return outputs
        
    def run(self, 
            log_file_patterns: List[str], 
            output_dir: Optional[str] = None, 
            prefix: str = "problematic_items") -> Dict[str, Any]:
        """
        Run the search overtime finder tool.
        
        Args:
            log_file_patterns: List of file patterns to process.
            output_dir: Optional directory to output results to.
            prefix: Prefix for the output files.
            
        Returns:
            Dictionary with the results and report paths.
        """
        # Update output directory if specified
        if output_dir:
            self.output_dir = output_dir
            
        # Initialize results with Counter objects to track occurrences
        combined_results = {
            'overtime': Counter(),
            'hard_to_place': Counter()
        }
        
        # Expand file patterns and process each file
        all_files = []
        for pattern in log_file_patterns:
            matched_files = glob.glob(pattern)
            all_files.extend(matched_files)
            
        if not all_files:
            logger.warning(f"No files found matching the patterns: {log_file_patterns}")
            return {
                'error': f"No files found matching the patterns: {log_file_patterns}",
                'files_processed': 0
            }
            
        # Process each file and merge results
        for file_path in all_files:
            file_results = self.process_log_file(file_path)
            
            # Merge results by adding the counts
            combined_results['overtime'] += file_results['overtime']
            combined_results['hard_to_place'] += file_results['hard_to_place']
        
        # Export results
        report_paths = self.export_results(combined_results, prefix)
        
        return {
            'files_processed': self.files_processed,
            'problematic_items': {
                'overtime': [
                    f"{item} (count: {count})" 
                    for item, count in combined_results['overtime'].most_common()
                ],
                'hard_to_place': [
                    f"{item} (count: {count})" 
                    for item, count in combined_results['hard_to_place'].most_common()
                ]
            },
            'reports': report_paths
        }


def _expand_log_file_patterns(patterns: List[str], default_log_dir: str) -> List[str]:
    """
    Expand wildcard patterns in log file paths and handle default directory.
    
    Args:
        patterns: List of file patterns to expand.
        default_log_dir: Default log directory for when no files are specified.
        
    Returns:
        List of expanded file paths.
    """
    if not patterns:
        default_pattern = os.path.join(default_log_dir, "*.RPT")
        patterns = [default_pattern]
        logging.info(f"No log files specified, using default pattern: {default_pattern}")
    
    log_files = []
    for pattern in patterns:
        if '*' in pattern or '?' in pattern:
            expanded = glob.glob(pattern)
            if not expanded:
                logging.warning(f"No files found matching pattern: {pattern}")
            log_files.extend(expanded)
        else:
            log_files.append(pattern)
    
    return log_files


def _display_results(result: Dict[str, Any]) -> None:
    """
    Display the analysis results to the console.
    
    Args:
        result: Dictionary containing the analysis results.
    """
    logging.info(f"Processed {result.get('files_processed', 0)} log files")
    
    if 'problematic_items' in result:
        logging.info("\nProblematic Items Found:")
        items = result['problematic_items']
        logging.info(f"Search Overtime: {len(items['overtime'])} unique items")
        logging.info(f"Hard to Place: {len(items['hard_to_place'])} unique items")
        
        # Display top items of each category
        for category, items_list in items.items():
            if items_list:
                top_limit = SearchOvertimeFinder.TOP_ITEMS_DISPLAY_LIMIT
                top_items = items_list[:top_limit] if len(items_list) > top_limit else items_list
                category_title = category.replace('_', ' ').title()
                logging.info(f"\nTop {min(top_limit, len(items_list))} {category_title} Items:")
                for item in top_items:
                    logging.info(f"  {item}")
    
    # Display report paths
    if 'reports' in result:
        logging.info("\nReports Generated:")
        for report_type, file_path in result['reports'].items():
            logging.info(f"{report_type.replace('_', ' ').title()}: {file_path}")


def main() -> int:
    """
    Main entry point for the command-line tool.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(description='Find unique items causing search overtime and performance drops.')
    parser.add_argument('log_files', type=str, nargs='*', 
                       help='Path to log file(s). Supports wildcards like *.RPT. '
                            'If not specified, uses RPT files from log_download_path.')
    parser.add_argument('--output', '-o', type=str, help='Directory to export results to')
    parser.add_argument('--prefix', type=str, default="problematic_items", help='Prefix for exported files')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Add standard arguments from DayZTool
    DayZTool.add_standard_arguments(parser)
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = DayZTool.load_config(args.profile)
    except Exception as e:
        logging.error(f"Error loading configuration: {e}")
        return 1
    
    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run the tool
    tool = SearchOvertimeFinder(config)
    
    try:
        # Expand file patterns using helper function
        log_files = _expand_log_file_patterns(args.log_files, tool.log_dir)
                
        if not log_files:
            logging.error("No log files found matching the specified patterns.")
            return 1
            
        # Run the tool
        result = tool.run(log_files, args.output, args.prefix)
        
        # Display results using helper function
        _display_results(result)
        
        return 0
        
    except Exception as e:
        logging.error(f"Error: {e}")
        import traceback
        logging.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
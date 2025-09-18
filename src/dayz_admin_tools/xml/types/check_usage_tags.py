"""
Check Usage Tags Tool

A tool for validating usage tags in DayZ XML files against a cfglimitsdefinition.xml file.
This ensures that all usage tags in types.xml and mapgroupproto.xml files are properly defined.
Uses 'paths.types_file', 'paths.mapgroupproto_file', and 'paths.cfglimitsdefinition_file' from the profile
configuration by default. By default, it checks both types.xml and mapgroupproto.xml in a single run.
"""

import xml.etree.ElementTree as ET
import sys
import logging
import argparse
from typing import Dict, Any, Optional, Set

# Add support for the config system
from ...base import XMLTool, DayZTool

__all__ = ['CheckUsageTagsTool', 'main']

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


class CheckUsageTagsTool(XMLTool):
    """
    Tool for validating usage tags in DayZ XML files.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the CheckUsageTags tool.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)

        # Initialize common directories
        self.initialize_directories()

        # Additional default file paths
        self.default_cfglimits_file = self.get_config('paths.cfglimitsdefinition_file', None)
        self.default_mapgroupproto_file = self.get_config('paths.mapgroupproto_file', None)

        logger.debug(f"Default cfglimits file: {self.default_cfglimits_file}")
        logger.debug(f"Default mapgroupproto file: {self.default_mapgroupproto_file}")

    def get_valid_usages(self, xml_file: str) -> Set[str]:
        """
        Get the set of valid usage tags from a cfglimitsdefinition.xml file.

        Args:
            xml_file: Path to the cfglimitsdefinition.xml file

        Returns:
            Set of valid usage tag names
        """
        logger.info(f"Reading valid usages from {xml_file}")

        try:
            # Use base class read_xml method
            root = self.read_xml(xml_file)

            # Extract usage names from all usage elements
            valid_usages = {
                usage.get('name')
                for usage in root.findall('.//usage')
                if usage.get('name') is not None
            }

            if not valid_usages:
                logger.warning("No valid usage tags found in cfglimitsdefinition.xml")
                return set()

            logger.info(f"Found {len(valid_usages)} valid usage tags")
            logger.debug(f"Valid usages: {', '.join(sorted(valid_usages))}")

            return valid_usages

        except Exception as e:
            logger.error(f"Error reading valid usages from {xml_file}: {e}")
            raise

    def check_invalid_usages_proto(self, xml_file: str, valid_usages: Set[str]) -> Dict[str, Dict[str, int]]:
        """
        Check for invalid usage tags in a mapgroupproto.xml file.

        Args:
            xml_file: Path to the mapgroupproto.xml file
            valid_usages: Set of valid usage tag names

        Returns:
            Dictionary where keys are invalid usage names and values are dictionaries mapping
            group names to occurrence counts
        """
        logger.info(f"Checking for invalid usages in {xml_file}")

        try:
            root = self.read_xml(xml_file)
            # Track invalid usages with group names and counts
            invalid_usages_data = {}  # {usage_name: {group_name: count}}

            # First build a dictionary of all groups and their usages
            groups = {}
            for group in root.findall('.//group'):
                group_name = group.get('name', 'Unknown Group')
                usage_elems = group.findall('.//usage')
                if usage_elems:
                    groups[group_name] = [
                        usage.get('name') for usage in usage_elems
                        if usage.get('name') is not None
                    ]

            # Check each group's usages against valid_usages
            for group_name, usages in groups.items():
                invalid = [usage for usage in usages if usage not in valid_usages]
                if invalid:
                    for usage in invalid:
                        # Initialize if this is the first encounter of this usage
                        if usage not in invalid_usages_data:
                            invalid_usages_data[usage] = {}

                        # Increment count for this group or set to 1
                        if group_name in invalid_usages_data[usage]:
                            invalid_usages_data[usage][group_name] += 1
                        else:
                            invalid_usages_data[usage][group_name] = 1

                        logger.warning(f"Invalid usage '{usage}' found in group '{group_name}'")

            if not invalid_usages_data:
                logger.info("No invalid usage tags found.")
            else:
                # Count total occurrences
                total_groups = sum(len(groups) for groups in invalid_usages_data.values())
                total_occurrences = sum(sum(counts.values()) for counts in invalid_usages_data.values())
                logger.warning(
                    f"Found {len(invalid_usages_data)} invalid usage tags across {total_groups} groups "
                    f"with {total_occurrences} total occurrences")

                # Log the top 5 most common invalid usages for quick reference
                sorted_usages = sorted(
                    [(usage, sum(counts.values())) for usage, counts in invalid_usages_data.items()],
                    key=lambda x: x[1],
                    reverse=True
                )
                if sorted_usages:
                    logger.info("Top invalid usages by occurrence:")
                    for usage, count in sorted_usages[:5]:
                        logger.info(f"  '{usage}': {count} occurrences")

            return invalid_usages_data

        except Exception as e:
            logger.error(f"Error checking usages in {xml_file}: {e}")
            raise

    def check_invalid_usages_types(self, xml_file: str, valid_usages: Set[str]) -> Dict[str, int]:
        """
        Check for invalid usage tags in a types.xml file.

        Args:
            xml_file: Path to the types.xml file
            valid_usages: Set of valid usage tag names

        Returns:
            Dictionary of undefined usage tag names with their occurrence counts
        """
        logger.info(f"Checking for invalid usages in {xml_file}")

        try:
            root = self.read_xml(xml_file)
            # Track both the undefined usages and their counts
            undefined_usages = {}

            # Use filter_types_by_name from base class to get all types
            for type_elem in self.filter_types_by_name(root):
                type_name = type_elem.get('name', 'Unknown Type')
                # Get values for the usage element
                values = self.get_type_values(type_elem, ['usage'])

                if values.get('usage') is not None:
                    if values['usage'] not in valid_usages:
                        # Add or increment the count for this undefined usage
                        if values['usage'] in undefined_usages:
                            undefined_usages[values['usage']] += 1
                        else:
                            undefined_usages[values['usage']] = 1
                        logger.warning(f"Invalid usage '{values['usage']}' found in type '{type_name}'")

            if not undefined_usages:
                logger.info("No invalid usage tags found.")
            else:
                total_occurrences = sum(undefined_usages.values())
                logger.warning(
                    f"Found {len(undefined_usages)} invalid usage tags with {total_occurrences} total occurrences")
                # Log the top 5 most common invalid usages for quick reference
                sorted_usages = sorted(undefined_usages.items(), key=lambda x: x[1], reverse=True)
                if sorted_usages:
                    logger.info("Top invalid usages by occurrence:")
                    for usage, count in sorted_usages[:5]:
                        logger.info(f"  '{usage}': {count} occurrences")

            return undefined_usages

        except Exception as e:
            logger.error(f"Error checking usages in {xml_file}: {e}")
            raise

    def run(self, cfglimits_file: Optional[str] = None, xml_file: Optional[str] = None, check_both: bool = True,
            csv_file: Optional[str] = None, summary_csv_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the CheckUsageTags tool.

        Args:
            cfglimits_file: Path to the cfglimitsdefinition.xml file (uses paths.cfglimitsdefinition_file
                           from config if None)
            xml_file: Path to the XML file to check (uses paths.types_file or paths.mapgroupproto_file
                     from config if None)
            check_both: If True and xml_file is None, checks both types.xml and mapgroupproto.xml
            csv_file: Optional path for the CSV output file (uses general.output_path from config if None)
            summary_csv_file: Optional path for the summary CSV output file (uses general.output_path
                             from config if None)

        Returns:
            Dictionary with results information
        """
        # Use config values if parameters aren't specified
        if not cfglimits_file:
            cfglimits_file = self.default_cfglimits_file
            if not cfglimits_file:
                logger.error("No cfglimits file specified and no 'paths.cfglimitsdefinition_file' configured "
                             "in profile")
                return {"error": "No cfglimits file specified and no 'paths.cfglimitsdefinition_file' "
                        "configured in profile"}

        # Resolve the cfglimits file path
        cfglimits_path = self.resolve_path(cfglimits_file)

        # If we should check both file types and no specific xml_file is specified
        if check_both and not xml_file:
            types_file = self.default_types_file
            mapgroupproto_file = self.default_mapgroupproto_file

            if not types_file:
                logger.error("No 'paths.types_file' configured in profile")
                return {"error": "No 'paths.types_file' configured in profile"}

            if not mapgroupproto_file:
                logger.error("No 'paths.mapgroupproto_file' configured in profile")
                return {"error": "No 'paths.mapgroupproto_file' configured in profile"}

            # Process both files
            return self.check_both_files(cfglimits_path, types_file, mapgroupproto_file, csv_file, summary_csv_file)

        # If only one file should be checked
        if not xml_file:
            # Default to types file if no xml file is specified
            xml_file = self.default_types_file
            if not xml_file:
                logger.error("No XML file specified and no 'paths.types_file' configured in profile")
                return {"error": "No XML file specified and no 'paths.types_file' configured in profile"}

        # Resolve the XML file path
        xml_path = self.resolve_path(xml_file)

        logger.info(f"Checking usage tags in {xml_path} against {cfglimits_path}")

        try:
            # Get valid usages
            valid_usages = self.get_valid_usages(cfglimits_path)

            result = {
                "success": True,
                "file_checked": xml_path,
                "cfglimits_file": cfglimits_path,
                "valid_usages_count": len(valid_usages)
            }

            # Check the appropriate file type
            if 'mapgroupproto' in xml_path.lower():
                invalid_usages = self.check_invalid_usages_proto(xml_path, valid_usages)
                result["file_type"] = "mapgroupproto"
                result["invalid_usages_count"] = len(invalid_usages)
                result["invalid_usages"] = invalid_usages

            elif 'types' in xml_path.lower():
                undefined_usages = self.check_invalid_usages_types(xml_path, valid_usages)
                result["file_type"] = "types"
                result["invalid_usages_count"] = len(undefined_usages)
                result["invalid_usages"] = undefined_usages  # Store the full dict with counts

            else:
                logger.error("Unsupported XML file type. Please provide either a mapgroupproto.xml or "
                             "types.xml file.")
                return {"error": "Unsupported XML file type. Please provide either a mapgroupproto.xml or "
                        "types.xml file."}

            # Export results to CSV
            csv_path = self.export_results_to_csv(result, csv_file)
            result["csv_file"] = csv_path

            # Export summary to CSV with just invalid usage tags and their counts
            if result["invalid_usages_count"] > 0:
                summary_path = self.export_summary_csv(result, summary_csv_file)
                result["summary_csv_file"] = summary_path

            return result

        except FileNotFoundError as e:
            logger.error(f"Error: Could not find file - {e}")
            return {"error": str(e)}
        except ET.ParseError as e:
            logger.error(f"Error: Invalid XML format - {e}")
            return {"error": f"Invalid XML format: {e}"}
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return {"error": str(e)}

    def check_both_files(self, cfglimits_path: str, types_file: str, mapgroupproto_file: str,
                         csv_file: Optional[str] = None, summary_csv_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Check both types.xml and mapgroupproto.xml files against cfglimitsdefinition.xml.

        Args:
            cfglimits_path: Path to the cfglimitsdefinition.xml file
            types_file: Path to the types.xml file
            mapgroupproto_file: Path to the mapgroupproto.xml file
            csv_file: Optional path for the CSV output file (uses general.output_path from config if not specified)
            summary_csv_file: Optional path for the summary CSV output file (uses general.output_path from config
                             if not specified)

        Returns:
            Dictionary with combined results
        """
        # Resolve paths
        types_path = self.resolve_path(types_file)
        mapgroupproto_path = self.resolve_path(mapgroupproto_file)

        logger.info(f"Checking usage tags in both {types_path} and {mapgroupproto_path} against {cfglimits_path}")

        try:
            # Get valid usages (do this only once)
            valid_usages = self.get_valid_usages(cfglimits_path)

            # Check types.xml
            types_undefined_usages = self.check_invalid_usages_types(types_path, valid_usages)

            # Check mapgroupproto.xml
            mapgroup_invalid_usages = self.check_invalid_usages_proto(mapgroupproto_path, valid_usages)

            # Combine results
            result = {
                "success": True,
                "cfglimits_file": cfglimits_path,
                "valid_usages_count": len(valid_usages),
                "types_file": types_path,
                "mapgroupproto_file": mapgroupproto_path,
                "types_file_invalid_count": len(types_undefined_usages),
                "types_file_invalid_usages": types_undefined_usages,  # Store the full dict with counts
                "mapgroupproto_invalid_count": len(mapgroup_invalid_usages),
                "mapgroupproto_invalid_usages": mapgroup_invalid_usages,
                "total_invalid_count": len(types_undefined_usages) + len(mapgroup_invalid_usages),
                "checked_both_files": True
            }

            # Export results to CSV
            csv_path = self.export_results_to_csv(result, csv_file)
            result["csv_file"] = csv_path

            # Export summary to CSV with just invalid usage tags and their counts
            if result["total_invalid_count"] > 0:
                summary_path = self.export_summary_csv(result, summary_csv_file)
                result["summary_csv_file"] = summary_path

            return result

        except FileNotFoundError as e:
            logger.error(f"Error: Could not find file - {e}")
            return {"error": f"Could not find file: {e}"}
        except ET.ParseError as e:
            logger.error(f"Error: Invalid XML format - {e}")
            return {"error": f"Invalid XML format: {e}"}
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            return {"error": str(e)}

    def export_results_to_csv(self, result: Dict[str, Any], csv_file: Optional[str] = None) -> str:
        """
        Export check results to a CSV file.

        Args:
            result: The results dictionary from the check
            csv_file: Path to the output CSV file (generated in output_dir if None)

        Returns:
            Path to the created CSV file
        """
        # Generate default filename if not provided
        if not csv_file:
            filename = self.generate_timestamped_filename("usage_tags_check", "csv")
            csv_file = filename

        # Prepare CSV data
        csv_rows = []

        if result.get("checked_both_files"):
            # Use separate headers for each file type with counts
            headers = ["File", "Invalid Usage", "Count", "Group"]

            # Add types.xml invalid usages with counts
            for usage, count in result["types_file_invalid_usages"].items():
                csv_rows.append({
                    "File": "types.xml",
                    "Invalid Usage": usage,
                    "Count": count,
                    "Group": "N/A"
                })

            # Add mapgroupproto.xml invalid usages with counts
            for usage_name, groups_dict in result["mapgroupproto_invalid_usages"].items():
                for group_name, count in groups_dict.items():
                    csv_rows.append({
                        "File": "mapgroupproto.xml",
                        "Invalid Usage": usage_name,
                        "Count": count,
                        "Group": group_name
                    })
        else:
            file_type = result.get("file_type", "unknown")

            if file_type == "mapgroupproto":
                headers = ["Invalid Usage", "Count", "Group"]

                # Add mapgroupproto.xml invalid usages with counts
                for usage_name, groups_dict in result["invalid_usages"].items():
                    for group_name, count in groups_dict.items():
                        csv_rows.append({
                            "Invalid Usage": usage_name,
                            "Count": count,
                            "Group": group_name
                        })
            else:  # types.xml
                headers = ["Invalid Usage", "Count"]

                # Add types.xml invalid usages with counts
                for usage, count in result["invalid_usages"].items():
                    csv_rows.append({
                        "Invalid Usage": usage,
                        "Count": count
                    })

        # Use the base class write_csv method
        csv_path = self.write_csv(csv_rows, csv_file, headers)
        logger.info(f"Results written to {csv_path}")
        return csv_path

    def export_summary_csv(self, result: Dict[str, Any], csv_file: Optional[str] = None) -> str:
        """
        Export a summary of invalid usage tags and their total counts to a CSV file.

        Args:
            result: The results dictionary from the check
            csv_file: Path to the output CSV file (generated in output_dir if None)

        Returns:
            Path to the created CSV file
        """
        # Generate default filename if not provided
        if not csv_file:
            filename = self.generate_timestamped_filename("usage_tags_summary", "csv")
            csv_file = filename

        # Prepare summary data
        summary = {}  # {usage_name: total_count}

        if result.get("checked_both_files"):
            # Add counts from types.xml
            for usage, count in result["types_file_invalid_usages"].items():
                summary[usage] = summary.get(usage, 0) + count

            # Add counts from mapgroupproto.xml
            for usage_name, groups_dict in result["mapgroupproto_invalid_usages"].items():
                total_for_usage = sum(groups_dict.values())
                summary[usage_name] = summary.get(usage_name, 0) + total_for_usage
        else:
            file_type = result.get("file_type", "unknown")

            if file_type == "mapgroupproto":
                # Add counts from mapgroupproto.xml
                for usage_name, groups_dict in result["invalid_usages"].items():
                    total_for_usage = sum(groups_dict.values())
                    summary[usage_name] = summary.get(usage_name, 0) + total_for_usage
            else:  # types.xml
                # Add counts from types.xml
                for usage, count in result["invalid_usages"].items():
                    summary[usage] = count

        # Sort by count (descending)
        sorted_summary = sorted(summary.items(), key=lambda x: x[1], reverse=True)

        # Create CSV rows
        csv_rows = [{"Usage": usage, "Total Count": count} for usage, count in sorted_summary]
        headers = ["Usage", "Total Count"]

        # Use the base class write_csv method
        csv_path = self.write_csv(csv_rows, csv_file, headers)
        logger.info(f"Summary CSV written to {csv_path}")
        return csv_path


def main():
    """
    Main entry point for the command-line script.
    """
    parser = argparse.ArgumentParser(
        description="Validate usage tags in DayZ XML files against cfglimitsdefinition.xml"
    )
    parser.add_argument("--cfglimits",
                        help="Path to the cfglimitsdefinition.xml file (uses paths.cfglimitsdefinition_file "
                        "from profile config if not specified)")
    parser.add_argument("--xml_file",
                        help="Path to a specific XML file to check (if not specified, both types.xml and "
                        "mapgroupproto.xml from config will be checked)")
    parser.add_argument("--mapgroupproto_only", action="store_true",
                        help="Check only mapgroupproto.xml instead of both files (uses paths.mapgroupproto_file "
                        "from profile config)")
    parser.add_argument("--types_only", action="store_true",
                        help="Check only types.xml instead of both files (uses paths.types_file "
                        "from profile config)")
    parser.add_argument("--csv",
                        help="Custom path for CSV output file (uses general.output_path from profile config "
                        "if not specified)")
    parser.add_argument("--summary-csv",
                        help="Custom path for summary CSV output file with invalid usage tags and their counts "
                        "(uses general.output_path from profile config if not specified)")

    # Add standard arguments (profile, etc.)
    DayZTool.add_standard_arguments(parser)

    args = parser.parse_args()

    # Load configuration
    config = DayZTool.load_config(args.profile)

    # Set up console logging for user output
    setup_console_logging()

    # Initialize the tool
    tool = CheckUsageTagsTool(config)

    # Determine which XML file(s) to check
    xml_file = args.xml_file
    check_both = True

    if args.xml_file:
        # If a specific file is provided, only check that one
        check_both = False
    elif args.mapgroupproto_only:
        xml_file = tool.default_mapgroupproto_file
        check_both = False
    elif args.types_only:
        xml_file = tool.default_types_file
        check_both = False

    # Run the tool with the appropriate settings
    result = tool.run(args.cfglimits, xml_file, check_both=check_both, csv_file=args.csv,
                      summary_csv_file=args.summary_csv)

    if "error" in result:
        logger.error(f"Error: {result['error']}")
        sys.exit(1)

    # Display CSV output path if available
    if "csv_file" in result:
        logger.info(f"\nResults exported to CSV: {result['csv_file']}")

    # Display summary CSV output path if available
    if "summary_csv_file" in result:
        logger.info(f"Summary CSV exported to: {result['summary_csv_file']}")

    # Display results
    if "checked_both_files" in result and result["checked_both_files"]:
        logger.info(f"\n=== CHECKING BOTH FILES AGAINST {result['valid_usages_count']} VALID USAGE TAGS ===")

        # Display types.xml results
        logger.info(f"\n1. TYPES.XML CHECK ({result['types_file']})")
        if result["types_file_invalid_count"] > 0:
            logger.info(f"   Found {result['types_file_invalid_count']} invalid usage tags in types.xml:")
            for usage in result["types_file_invalid_usages"]:
                logger.info(f"   - Invalid usage '{usage}'")
        else:
            logger.info("   No invalid usage tags found in types.xml.")

        # Display mapgroupproto.xml results
        logger.info(f"\n2. MAPGROUPPROTO.XML CHECK ({result['mapgroupproto_file']})")
        if result["mapgroupproto_invalid_count"] > 0:
            logger.info(f"   Found {result['mapgroupproto_invalid_count']} invalid usage tags in mapgroupproto.xml:")
            for group_name, usage_name in result["mapgroupproto_invalid_usages"]:
                logger.info(f"   - Invalid usage '{usage_name}' found in group '{group_name}'")
        else:
            logger.info("   No invalid usage tags found in mapgroupproto.xml.")

        # Display summary
        logger.info(f"\nTotal invalid usage tags found: {result['total_invalid_count']}")

    elif "file_type" in result and result["file_type"] == "mapgroupproto":
        if result["invalid_usages_count"] > 0:
            logger.info(f"\nFound {result['invalid_usages_count']} invalid usage tags in mapgroupproto file:")
            for group_name, usage_name in result["invalid_usages"]:
                logger.info(f"- Invalid usage '{usage_name}' found in group '{group_name}'")
        else:
            logger.info("No invalid usage tags found in mapgroupproto file.")
    elif "file_type" in result:  # types.xml
        if result["invalid_usages_count"] > 0:
            logger.info(f"\nFound {result['invalid_usages_count']} invalid usage tags in types file:")
            for usage in result["invalid_usages"]:
                logger.info(f"- Invalid usage '{usage}'")
        else:
            logger.info("No invalid usage tags found in types file.")

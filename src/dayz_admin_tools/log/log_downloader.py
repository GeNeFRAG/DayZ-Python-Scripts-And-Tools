"""
Nitrado Log Downloader

This module provides functionality for downloading log files from a Nitrado-hosted DayZ server.
With support for filtering by date ranges, filename patterns, and saved filter profiles.
"""

import argparse
import sys
import fnmatch
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from dayz_admin_tools.nitrado.api_client import NitradoAPIClient
from ..base import FileBasedTool, DayZTool
from .log_filter_profiles import LogFilterProfile

# Configure logger
logger = logging.getLogger(__name__)


class NitradoLogDownloader(FileBasedTool):
    """Tool for downloading log files from a Nitrado-hosted DayZ server."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the log downloader.

        Args:
            config: Optional configuration dictionary.
        """
        super().__init__(config)
        self.initialize_directories()
        self.api_client = NitradoAPIClient(config)
        self.filter_profiles = LogFilterProfile()

    def get_logs_info(self, log_directory: str = None) -> List[Dict[str, Any]]:
        """
        Get log files information from the server with standardized format.

        Args:
            log_directory: Optional custom directory path for logs.

        Returns:
            List of file stats, or empty list if an error occurred.
        """
        logger.info("Getting log files information from Nitrado...")

        if log_directory is None:
            # Use relative path without leading slash - should be relative to remote_base_path
            log_directory = f"games/{self.api_client.server_id}/ftproot/dayzxb/config/"

        try:
            # Get file entries directly using the API client's list_files method
            file_entries = self.api_client.list_files(log_directory)

            if not file_entries:
                logger.warning(f"No file entries returned for {log_directory}")
                return []

            # Convert to standardized format
            file_stats = [
                {
                    "path": file["path"],
                    "modified_at": datetime.fromtimestamp(
                        file["modified_at"]
                    ).isoformat() if isinstance(file["modified_at"], (int, float)) else file["modified_at"],
                    "name": file["name"],
                }
                for file in file_entries
                if file["type"] == "file"
            ]

            logger.info(f"Successfully fetched {len(file_stats)} log file stats from Nitrado")
            return file_stats
        except Exception as e:
            logger.error(f"Error fetching log files: {e}")
            return []

    def filter_and_download_logs(
        self,
        file_stats: List[Dict[str, Any]],
        output_dir: str = ".",
        start_date: str = None,
        end_date: str = None,
        filename_patterns: List[str] = None,
        latest_default: bool = True,
        download_all: bool = False
    ) -> bool:
        """
        Filter and download log files based on various criteria.
        By default, downloads all .RPT and .ADM files.

        Args:
            file_stats: List of file statistics
            output_dir: Directory to save the downloaded files
            start_date: Start date in D.M.YYYY format (e.g., 01.06.2023)
            end_date: End date in D.M.YYYY format (e.g., 30.06.2023)
            filename_patterns: List of Unix-style filename patterns
            latest_default: If True, download all .RPT and .ADM files when no other filters match
            download_all: If True, download all .RPT and .ADM files

        Returns:
            bool: True if any files were downloaded successfully, False otherwise
        """
        if not file_stats:
            logger.warning("No file stats provided")
            return False

        filtered_files = []

        # Check for default patterns from config
        default_patterns = self.get_config('log_filtering.default_patterns')
        if filename_patterns is None and default_patterns:
            filename_patterns = default_patterns
            logger.info(f"Using default patterns from config: {filename_patterns}")

        # If download_all is specified, download all .RPT and .ADM files
        if download_all:
            filtered_files = [
                f for f in file_stats if f['name'].endswith('.RPT') or f['name'].endswith('.ADM')
            ]
            logger.info(f"Selected all .RPT and .ADM files: {len(filtered_files)} files")
        else:
            # Apply filters if provided
            date_filtered = False
            pattern_filtered = False

            # Apply date filters if provided
            if start_date or end_date:
                try:
                    # Convert D.M.YYYY format to datetime objects
                    start_dt = datetime.strptime(start_date, "%d.%m.%Y") if start_date else datetime.min
                    end_dt = datetime.strptime(end_date, "%d.%m.%Y") if end_date else datetime.max

                    # Set time components for proper range filtering
                    if start_date:
                        start_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                    if end_date:
                        end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

                    logger.debug(f"Filtering files from {start_dt} to {end_dt}")
                    filtered_files = [
                        f for f in file_stats
                        if start_dt <= datetime.fromisoformat(f['modified_at']) <= end_dt
                    ]
                    date_filtered = True
                    logger.info(
                        f"Filtered files based on date range ({start_date or 'any'} to "
                        f"{end_date or 'any'}): {len(filtered_files)} files")
                except ValueError as e:
                    logger.error(f"Error parsing dates. Use D.M.YYYY format (e.g., 01.06.2023): {e}")
                    return False

            # Apply filename patterns if provided
            if filename_patterns:
                pattern_base = filtered_files if date_filtered else file_stats
                filtered_files = [
                    f for f in pattern_base
                    if any(fnmatch.fnmatch(f['name'].lower(), pattern.lower()) for pattern in filename_patterns)
                ]
                pattern_filtered = True
                logger.info(f"Filtered files based on filename patterns: {len(filtered_files)} files")

            # If no specific filters applied and latest_default is True,
            # get all .RPT and .ADM files
            if not (date_filtered or pattern_filtered) and latest_default:
                # Get all RPT and ADM files as fallback
                filtered_files = [
                    f for f in file_stats if f['name'].endswith('.RPT') or f['name'].endswith('.ADM')
                ]
                logger.info(f"Selected all .RPT and .ADM files: {len(filtered_files)} files")

        if not filtered_files:
            logger.warning("No files matched the specified criteria")
            return False

        # Ensure output directory exists
        output_path = Path(self.ensure_dir(output_dir))

        # Download matched files
        success = True
        success_count = 0

        for file in filtered_files:
            logger.info(f"Downloading {file['name']} (Modified: {file['modified_at']})")

            try:
                # Download the file content using the API client
                content = self.api_client.download_file(file['path'])

                # Save to specified output directory
                file_path = output_path / file['name']

                # Save the file locally
                with open(file_path, 'wb') as f:
                    f.write(content)

                logger.info(f"Successfully saved: {file_path}")
                success_count += 1

            except Exception as e:
                logger.error(f"Error downloading/saving {file['name']}: {e}")
                success = False

        logger.info(f"Downloaded {success_count} of {len(filtered_files)} files to {output_dir}")
        return success

    def apply_filter_profile(self, profile_name: str) -> Dict[str, Any]:
        """
        Apply a saved filter profile.

        Args:
            profile_name: Name of the filter profile

        Returns:
            Dictionary with filter settings
        """
        # Load the profile
        profile = self.filter_profiles.load_profile(profile_name)
        if not profile:
            logger.warning(f"Filter profile '{profile_name}' not found or empty.")

        return profile

    def save_filter_profile(self, profile_name: str, start_date: str = None,
                            end_date: str = None, filename_patterns: List[str] = None,
                            description: str = None) -> bool:
        """
        Save current filter settings as a profile.

        Args:
            profile_name: Name to save the profile as
            start_date: Start date in D.M.YYYY format (e.g., 01.06.2023)
            end_date: End date in D.M.YYYY format (e.g., 30.06.2023)
            filename_patterns: List of Unix-style filename patterns
            description: Optional description of the profile

        Returns:
            bool: True if saved successfully
        """
        return self.filter_profiles.save_profile(
            profile_name,
            start_date=start_date,
            end_date=end_date,
            filename_patterns=filename_patterns,
            description=description
        )

    def list_filter_profiles(self) -> List[Dict[str, Any]]:
        """
        List all available filter profiles.

        Returns:
            List of profile info dictionaries
        """
        return self.filter_profiles.list_profiles()

    def run(
        self,
        output_dir: str = None,
        start_date: str = None,
        end_date: str = None,
        filename_patterns: List[str] = None,
        filter_profile: str = None,
        latest_default: bool = True,
        download_all: bool = False,
        save_profile: str = None
    ) -> Dict[str, Any]:
        """
        Run the log downloader with the specified parameters.

        Args:
            output_dir: Directory to save the downloaded files. If None, uses general.log_download_path from config.
            start_date: Start date in D.M.YYYY format (e.g., 01.06.2023)
            end_date: End date in D.M.YYYY format (e.g., 30.06.2023)
            filename_patterns: List of Unix-style filename patterns
            filter_profile: Name of a saved filter profile to apply
            latest_default: If True, download all .RPT and .ADM files when no other filters match
            download_all: If True, download all .RPT and .ADM files
            save_profile: If provided, save these filter settings as a profile with this name

        Returns:
            Dictionary with download results and metadata
        """
        # Use the standard output path from config if not specified
        if output_dir is None:
            output_dir = self.get_config('general.log_download_path', self.log_dir or '.')
            logger.info(f"Using log directory from config: {output_dir}")
            if output_dir == '.' or output_dir == self.log_dir:
                logger.warning("Using default log directory. Consider setting 'general.log_download_path' in config.")

        # Log the output directory for better debugging
        logger.debug(f"Log downloader configured with output_dir: {output_dir}")
        logger.debug(f"Using config: {self.config}")
        # Apply filter profile if specified
        if filter_profile:
            profile = self.apply_filter_profile(filter_profile)
            if profile:
                # Override any unspecified parameters with profile values
                if start_date is None:
                    start_date = profile.get('start_date')
                if end_date is None:
                    end_date = profile.get('end_date')
                if not filename_patterns and 'filename_patterns' in profile:
                    filename_patterns = profile.get('filename_patterns')

        # Save the filter profile if requested
        if save_profile:
            self.save_filter_profile(
                save_profile,
                start_date=start_date,
                end_date=end_date,
                filename_patterns=filename_patterns
            )
            logger.info(f"Filter settings saved as profile '{save_profile}'")

        # Get log files information
        file_stats = self.get_logs_info()
        if not file_stats:
            return {
                "success": False,
                "error": "Failed to retrieve log files information",
                "downloaded_files": 0,
                "total_files": 0,
                "output_dir": output_dir
            }

        # Apply filters and download files
        success = self.filter_and_download_logs(
            file_stats,
            output_dir=output_dir,
            start_date=start_date,
            end_date=end_date,
            filename_patterns=filename_patterns,
            latest_default=latest_default,
            download_all=download_all
        )

        return {
            "success": success,
            "output_dir": output_dir,
            "filter_applied": {
                "start_date": start_date,
                "end_date": end_date,
                "filename_patterns": filename_patterns,
                "filter_profile": filter_profile,
                "download_all": download_all
            },
            "profile_saved": save_profile if save_profile else None
        }


def main():
    parser = argparse.ArgumentParser(
        description="Download DayZ server logs with filters from a Nitrado server"
    )

    # Use the standard argument function from DayZTool for profile
    # Note that add_standard_arguments adds to the main parser, not a group
    DayZTool.add_standard_arguments(parser)

    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save logs to (default: uses general.log_download_path from "
             "config if available, otherwise current directory)",
    )
    output_group.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )

    # Filter options group
    filter_group = parser.add_argument_group('Filter Options')
    filter_group.add_argument(
        "--start-date",
        help="Start date for log files (D.M.YYYY format, e.g., 01.06.2023)",
    )
    filter_group.add_argument(
        "--end-date",
        help="End date for log files (D.M.YYYY format, e.g., 30.06.2023)",
    )
    filter_group.add_argument(
        "--pattern",
        action="append",
        help='Filename pattern (e.g., "*.RPT" or "script_*.ADM"). Can be specified multiple times.',
    )
    filter_group.add_argument(
        "--no-default",
        action="store_true",
        help="Disable downloading all .RPT and .ADM files when no other filters match",
    )
    filter_group.add_argument(
        "--all",
        action="store_true",
        help="Download all .RPT and .ADM files",
    )

    # Filter profile options
    profile_group = parser.add_argument_group('Filter Profile Management')
    profile_action = profile_group.add_mutually_exclusive_group()
    profile_action.add_argument(
        "--filter-profile",
        help="Use a saved filter profile",
    )
    profile_action.add_argument(
        "--save-filter",
        metavar="NAME",
        help="Save current filter settings as a named profile",
    )
    profile_action.add_argument(
        "--list-filters",
        action="store_true",
        help="List all available filter profiles",
    )
    profile_group.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format when listing filter profiles",
    )
    profile_action.add_argument(
        "--create-common-filters",
        action="store_true",
        help="Create a set of common filter profiles",
    )
    profile_action.add_argument(
        "--delete-filter",
        metavar="NAME",
        help="Delete a filter profile",
    )

    args = parser.parse_args()

    # Load configuration (either from profile or legacy config)
    config = DayZTool.load_config(args.profile)
    if not config:
        logger.error(f"Failed to load configuration profile: {args.profile}")
        return 1

    # Override logging level if verbose flag is set
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled via command line flag")

    logger.info(f"Using configuration profile: {args.profile}")
    logger.debug(f"Full configuration: {config}")
    # Initialize log downloader
    downloader = NitradoLogDownloader(config)

    # Handle filter profile operations
    if args.list_filters:
        profiles = downloader.list_filter_profiles()
        if not profiles:
            print("No filter profiles found.")
            return 0

        print("\nAvailable Log Filter Profiles:")

        # Format and print profiles in a simple text format
        for profile in profiles:
            name = profile["name"]
            description = profile.get("description", "")
            start_date = profile.get("start_date") or "Any"
            end_date = profile.get("end_date") or "Any"
            patterns = ", ".join(profile.get("filename_patterns", [])) or "None"

            print(f"\n{name}:")
            print(f"  Description: {description}")
            print(f"  Date Range: {start_date} to {end_date}")
            print(f"  File Patterns: {patterns}")

        # Also offer JSON output if requested
        if args.json:
            import json
            print("\nJSON Format:")
            print(json.dumps(profiles, indent=2))
        return 0

    elif args.create_common_filters:
        downloader.filter_profiles.create_common_filters()
        print("Created common filter profiles.")
        return 0

    elif args.delete_filter:
        if downloader.filter_profiles.delete_profile(args.delete_filter):
            print(f"Deleted filter profile: {args.delete_filter}")
            return 0
        else:
            print(f"Failed to delete filter profile: {args.delete_filter}")
            return 1

    # Determine the output directory (CLI arg or from config)
    output_dir = args.output_dir
    if output_dir is None:
        output_dir = config.get('general', {}).get('log_download_path', '.')
        logger.info(f"Using log directory from config: {output_dir}")
        if output_dir == '.':
            logger.warning("Could not find 'general.log_download_path' in config, using current directory as fallback.")

    # Run the downloader with specified options
    result = downloader.run(
        output_dir=output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        filename_patterns=args.pattern,
        filter_profile=args.filter_profile,
        latest_default=not args.no_default,
        download_all=args.all,
        save_profile=args.save_filter
    )

    return 0 if result.get("success", False) else 1


if __name__ == "__main__":
    sys.exit(main())

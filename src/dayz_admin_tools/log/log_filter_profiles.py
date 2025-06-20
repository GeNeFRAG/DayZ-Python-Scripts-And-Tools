"""
Log Filter Profiles

This module provides functionality to manage log filter profiles for more efficient
filtering by date ranges and file patterns.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ..base import JSONTool, DayZTool, logger

__all__ = ['LogFilterProfile', 'main']


class LogFilterProfile(JSONTool):
    """Class for managing log filter profiles using JSON storage."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the log filter profile manager.
        
        Args:
            config: Configuration dictionary.
        """
        super().__init__(config)
        
        # Check config for profile directory or use default
        config_dir = self.get_config('log.filter_profiles_dir')
        
        if config_dir:
            self.config_dir = Path(self.resolve_path(config_dir))
        else:
            # Use config directory in user's home by default
            home_dir = Path.home()
            self.config_dir = home_dir / ".dayz_admin_tools" / "log_profiles"
            
        # Ensure directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Log filter profiles directory: {self.config_dir}")
    
    def run(self) -> Dict[str, Any]:
        """
        Run the profile manager (required by base class).
        
        Returns:
            Dictionary with profile manager status
        """
        profiles = self.list_profiles()
        return {
            "status": "active",
            "profiles_dir": str(self.config_dir),
            "profile_count": len(profiles)
        }
        
    def save_profile(self, name: str, start_date: str = None, end_date: str = None, 
                    filename_patterns: List[str] = None, description: str = None) -> bool:
        """
        Save a filter profile.
        
        Args:
            name: Name for the profile
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            filename_patterns: List of filename patterns
            description: Optional description of the profile
            
        Returns:
            True if successful, False otherwise
        """
        profile = {
            "start_date": start_date,
            "end_date": end_date,
            "filename_patterns": filename_patterns or [],
            "description": description or f"Filter profile created on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "created_at": datetime.now().isoformat()
        }
        
        try:
            profile_path = str(self.config_dir / f"{name}.json")
            self.write_json(profile, profile_path)
            logger.info(f"Saved log filter profile '{name}'")
            return True
        except Exception as e:
            logger.error(f"Error saving log filter profile: {e}")
            return False
    
    def load_profile(self, name: str) -> Dict[str, Any]:
        """
        Load a filter profile.
        
        Args:
            name: Profile name
            
        Returns:
            Dictionary with filter settings
        """
        profile_path = self.config_dir / f"{name}.json"
        
        if not profile_path.exists():
            logger.warning(f"Profile '{name}' does not exist")
            return {}
            
        try:
            profile = self.read_json(str(profile_path))
            logger.info(f"Loaded log filter profile '{name}'")
            return profile
        except Exception as e:
            logger.error(f"Error loading log filter profile: {e}")
            return {}
    
    def delete_profile(self, name: str) -> bool:
        """
        Delete a filter profile.
        
        Args:
            name: Profile name
            
        Returns:
            True if successful, False otherwise
        """
        profile_path = self.config_dir / f"{name}.json"
        
        if not profile_path.exists():
            logger.warning(f"Profile '{name}' does not exist")
            return False
            
        try:
            profile_path.unlink()
            logger.info(f"Deleted log filter profile '{name}'")
            return True
        except Exception as e:
            logger.error(f"Error deleting log filter profile: {e}")
            return False
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        """
        List all available filter profiles.
        
        Returns:
            List of profile info dictionaries
        """
        profiles = []
        
        for file_path in self.config_dir.glob("*.json"):
            try:
                profile = self.read_json(str(file_path))
                    
                profile_name = file_path.stem
                profiles.append({
                    "name": profile_name,
                    "description": profile.get("description", ""),
                    "start_date": profile.get("start_date"),
                    "end_date": profile.get("end_date"),
                    "filename_patterns": profile.get("filename_patterns", []),
                    "created_at": profile.get("created_at")
                })
            except Exception as e:
                logger.error(f"Error loading profile from {file_path}: {e}")
        
        return profiles
        
    def create_common_filters(self) -> None:
        """Create a set of common filter profiles if they don't already exist."""
        # Yesterday's logs
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")
        self.save_profile(
            "yesterday",
            start_date=yesterday_str,
            end_date=yesterday_str,
            description="Logs from yesterday"
        )
        
        # Last week
        week_ago = datetime.now() - timedelta(days=7)
        week_ago_str = week_ago.strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        self.save_profile(
            "last_week",
            start_date=week_ago_str,
            end_date=today,
            description="Logs from the last 7 days"
        )
        
        # Common patterns
        self.save_profile(
            "all_rpt",
            filename_patterns=["*.RPT"],
            description="All RPT log files"
        )
        
        self.save_profile(
            "all_adm",
            filename_patterns=["*.ADM"],
            description="All ADM log files"
        )


def main():
    """
    Command-line interface for the log filter profiles tool.
    """
    import argparse
    
    # DayZTool is already imported at the top level
    
    parser = argparse.ArgumentParser(description='Manage DayZ log filter profiles')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Create profile command
    create_parser = subparsers.add_parser('create', help='Create a new profile')
    create_parser.add_argument('name', help='Name for the profile')
    create_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    create_parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    create_parser.add_argument('--patterns', help='Comma-separated list of filename patterns')
    create_parser.add_argument('--description', help='Description of the profile')
    
    # View profile command
    view_parser = subparsers.add_parser('view', help='View a specific profile')
    view_parser.add_argument('name', help='Name of the profile to view')
    
    # Delete profile command
    delete_parser = subparsers.add_parser('delete', help='Delete a profile')
    delete_parser.add_argument('name', help='Name of the profile to delete')
    
    # Common options
    # Use the standard argument function from DayZTool for profile
    DayZTool.add_standard_arguments(parser)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Load configuration and create the profile manager
    config = DayZTool.load_config(args.profile)
    profile_manager = LogFilterProfile(config)
    
    # Execute the appropriate command
    return _execute_command(args, profile_manager, parser)


def _execute_command(args, profile_manager, parser):
    """
    Execute the selected command based on arguments.
    
    Args:
        args: Command-line arguments
        profile_manager: LogFilterProfile instance
        parser: ArgumentParser instance for help display
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    if args.command == 'list':
        profiles = profile_manager.list_profiles()
        if not profiles:
            logger.info("No profiles found.")
            return 0
            
        logger.info(f"Found {len(profiles)} profiles:")
        for i, profile in enumerate(profiles, 1):
            logger.info(f"{i}. {profile['name']}: {profile['description']}")
            if profile['start_date'] or profile['end_date']:
                date_range = f"Dates: {profile['start_date'] or 'any'} to {profile['end_date'] or 'any'}"
                logger.info(f"   {date_range}")
            if profile['filename_patterns']:
                logger.info(f"   Patterns: {', '.join(profile['filename_patterns'])}")
        return 0
    
    elif args.command == 'create':
        patterns = args.patterns.split(',') if args.patterns else []
        success = profile_manager.save_profile(
            args.name,
            start_date=args.start_date,
            end_date=args.end_date,
            filename_patterns=patterns,
            description=args.description
        )
        if success:
            logger.info(f"Profile '{args.name}' created successfully.")
            return 0
        else:
            logger.error(f"Failed to create profile '{args.name}'.")
            return 1
    
    elif args.command == 'view':
        profile = profile_manager.load_profile(args.name)
        if not profile:
            logger.error(f"Profile '{args.name}' not found.")
            return 1
            
        logger.info(f"Profile: {args.name}")
        logger.info(f"Description: {profile.get('description', 'None')}")
        logger.info(f"Date range: {profile.get('start_date', 'any')} to {profile.get('end_date', 'any')}")
        logger.info(f"Filename patterns: {', '.join(profile.get('filename_patterns', []) or ['None'])}")
        logger.info(f"Created at: {profile.get('created_at', 'Unknown')}")
        return 0
    
    elif args.command == 'delete':
        success = profile_manager.delete_profile(args.name)
        if success:
            logger.info(f"Profile '{args.name}' deleted successfully.")
            return 0
        else:
            logger.error(f"Failed to delete profile '{args.name}'.")
            return 1
    
    elif args.command == 'create-common':
        profile_manager.create_common_filters()
        logger.info("Common filter profiles created successfully.")
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())

"""
DayZ ADM Log Analyzer

This module provides comprehensive analysis of DayZ AdminLog (ADM) files,
extracting player behavior statistics, combat analytics, building activity,
and administrative insights.
"""

import argparse
import csv
import logging
import re
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from ..base import FileBasedTool

logger = logging.getLogger(__name__)


@dataclass
class PlayerEvent:
    """Represents a single player event from the ADM log."""
    timestamp: datetime
    player_name: str
    player_id: str
    event_type: str
    position: Optional[Tuple[float, float, float]] = None
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class CombatEvent:
    """Represents a combat event between players."""
    timestamp: datetime
    attacker_name: str
    attacker_id: str
    victim_name: str
    victim_id: str
    weapon: str
    damage: float
    hit_location: str
    distance: float
    attacker_pos: Optional[Tuple[float, float, float]] = None
    victim_pos: Optional[Tuple[float, float, float]] = None
    kill: bool = False


@dataclass
class PlayerSession:
    """Represents a player's gaming session."""
    player_name: str
    player_id: str
    connect_time: datetime
    disconnect_time: Optional[datetime] = None
    positions: List[Tuple[datetime, float, float, float]] = None
    deaths: int = 0
    
    def __post_init__(self):
        if self.positions is None:
            self.positions = []
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get session duration."""
        if self.disconnect_time:
            return self.disconnect_time - self.connect_time
        return None
    
    @property
    def distance_traveled(self) -> float:
        """Calculate total distance traveled during session."""
        if len(self.positions) < 2:
            return 0.0
        
        total_distance = 0.0
        for i in range(1, len(self.positions)):
            prev_pos = self.positions[i-1][1:]  # Skip timestamp
            curr_pos = self.positions[i][1:]    # Skip timestamp
            
            # Calculate 3D distance
            distance = ((curr_pos[0] - prev_pos[0]) ** 2 + 
                       (curr_pos[1] - prev_pos[1]) ** 2 + 
                       (curr_pos[2] - prev_pos[2]) ** 2) ** 0.5
            total_distance += distance
            
        return total_distance


@dataclass
class ParseResult:
    """Result of parsing a single line."""
    event: Optional[PlayerEvent] = None
    error: Optional[str] = None
    line_number: int = 0
    raw_line: str = ""


@dataclass 
class ParseSummary:
    """Summary of parsing results including error reporting."""
    total_lines: int = 0
    parsed_events: int = 0
    malformed_lines: int = 0
    malformed_samples: List[str] = None
    connections: int = 0
    disconnections: int = 0
    combat_events: int = 0
    deaths: int = 0
    building_events: int = 0
    emotes: int = 0
    teleported_events: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.malformed_samples is None:
            self.malformed_samples = []


class DayZADMParser:
    """
    Parser that yields events from DayZ AdminLog files.
    
    Separates parsing concerns from analysis, providing a clean interface
    for consuming events and collecting parse error statistics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the parser with configuration."""
        self.config = config or {}
        self._setup_patterns()
    
    def _setup_patterns(self):
        """Setup regex patterns for parsing different event types."""
        # Pre-compiled regex patterns for performance using named capture groups
        # Patterns are grouped and commented by event type for clarity
        self.patterns = {
            # --- Connection/Disconnection Events ---
            'connection': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\)\s*is connected'),
            'disconnection': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\)\s*has been disconnected'),

            # --- Player State/Status Events ---
            'unconscious': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*is unconscious'),
            'conscious': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*regained consciousness'),
            'suicide': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=(?P<player_id>[A-F0-9]+)(?:\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>)?\)\s*committed suicide'),
            'emote': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*performed (?P<emote>[^\s]+)(?:\s+with\s+(?P<emote_item>[^\s]+))?'),

            # --- Combat Events ---
            'hit': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<victim_name>[^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=(?P<victim_id>[A-F0-9]+)\s*pos=<(?P<victim_x>[0-9.-]+),\s*(?P<victim_y>[0-9.-]+),\s*(?P<victim_z>[0-9.-]+)>\)\s*\[HP:\s*(?P<victim_hp>[0-9.]+)\]\s*hit by Player\s*"(?P<attacker_name>[^"]+?)"\s*\(id=(?P<attacker_id>[A-F0-9]+)\s*pos=<(?P<attacker_x>[0-9.-]+),\s*(?P<attacker_y>[0-9.-]+),\s*(?P<attacker_z>[0-9.-]+)>\)\s*into\s*(?P<hit_location>[^(]+)\((?P<hit_location_id>\d+)\)\s*for\s*(?P<damage>[0-9.]+)\s+damage\s*\((?P<ammo>[^)]+)\)(?:\s*with\s+(?P<weapon>[^\s]+)(?:\s+from\s+(?P<distance>[0-9.]+)\s+meters)?)?'),
            'kill': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<victim_name>[^"]+?)"\s*\(DEAD\)\s*\(id=(?P<victim_id>[A-F0-9]+)\s*pos=<(?P<victim_x>[0-9.-]+),\s*(?P<victim_y>[0-9.-]+),\s*(?P<victim_z>[0-9.-]+)>\)\s*killed by Player\s*"(?P<attacker_name>[^"]+?)"\s*\(id=(?P<attacker_id>[A-F0-9]+)\s*pos=<(?P<attacker_x>[0-9.-]+),\s*(?P<attacker_y>[0-9.-]+),\s*(?P<attacker_z>[0-9.-]+)>\)\s*with\s*(?P<weapon>[^\s]+)\s*from\s*(?P<distance>[0-9.]+)\s+meters'),
            'env_hit': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\[HP:\s*(?P<hp>[0-9.]+)\]\s+hit by\s+(?P<attacker>[^\s]+)\s+with\s+(?P<weapon>[^\s]+)'),
            'env_hit_simple': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\[HP:\s*(?P<hp>[0-9.]+)\]\s*hit by\s+(?P<attacker>[^\s]+)$'),
            'explosion_hit': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\[HP:\s*(?P<hp>[0-9.]+)\]\s+hit by explosion\s+\((?P<explosion_type>[^)]+)\)'),
            'death': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(DEAD\)\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*died\.\s+Stats>\s+Water:\s+(?P<water>[0-9.]+)\s+Energy:\s+(?P<energy>[0-9.]+)\s+Bleed sources:\s+(?P<bleed_sources>\d+)'),
            'death_other': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(DEAD\)\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s+killed by\s+(?P<killer>[^\s]+)'),

            # --- Building/Construction Events ---
            'building': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*(?P<action>Built|Dismantled)\s+(?P<structure>[^\s]+)\s+(?P<on_or_from>on|from)\s+(?P<parent>[^\s]+)\s+with\s+(?P<tool>[^\s]+)$'),
            'packed': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s+packed\s+(?P<structure>.+?)\s+with\s+(?P<tool>[^\s]+)$'),
            'placed': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s+placed\s+(?P<structure>.+)$'),
            'folded': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s+folded\s+(?P<structure>.+)$'),

            # --- Teleportation Events ---
            'teleported': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*was teleported from:\s*<(?P<from_x>[0-9.-]+),\s*(?P<from_y>[0-9.-]+),\s*(?P<from_z>[0-9.-]+)>\s*to:\s*<(?P<to_x>[0-9.-]+),\s*(?P<to_y>[0-9.-]+),\s*(?P<to_z>[0-9.-]+)>\.\s*Reason:\s*(?P<reason>.+)$'),

            # --- Fallback/Player Position ---
            # Match simple position lines that end after the position coordinates
            'player_position': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-F0-9]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*$')
        }

        # --- Special/Other Events from config ---
        special_events_cfg = self.config.get('special_events', {})
        if special_events_cfg.get('enabled', False):
            for event in special_events_cfg.get('events', []):
                name = event.get('name')
                regexp = event.get('regexp')
                if name and regexp:
                    try:
                        self.patterns[name] = re.compile(rf'(?P<time>\d{{2}}:\d{{2}}:\d{{2}})\s*\|\s*{regexp}')
                    except Exception as e:
                        logger.error(f"Failed to compile special event regexp for '{name}': {e}")
    
    def parse_file(self, log_file: str, max_malformed_samples: int = 10) -> tuple[List[PlayerEvent], List[CombatEvent], ParseSummary]:
        """
        Parse an ADM log file and yield events.
        
        Args:
            log_file: Path to the ADM log file
            max_malformed_samples: Maximum number of malformed line samples to collect
            
        Returns:
            Tuple of (events, combat_events, parse_summary)
        """
        events = []
        combat_events = []
        summary = ParseSummary()
        
        log_path = Path(log_file)
        if not log_path.exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")
        
        logger.info(f"Parsing ADM log file: {log_path}")
        
        # Extract date from filename for timestamp parsing
        base_date = self._extract_date_from_filename(str(log_path))
        
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_number, line in enumerate(f, 1):
                summary.total_lines += 1
                line = line.strip()
                
                if not line or line.startswith('#'):
                    continue
                
                parse_result = self._parse_line(line, base_date, line_number)
                
                if parse_result.event:
                    events.append(parse_result.event)
                    summary.parsed_events += 1
                    
                    # Update event type counters
                    event_type = parse_result.event.event_type
                    if event_type == 'connection':
                        summary.connections += 1
                    elif event_type == 'disconnection':
                        summary.disconnections += 1
                    elif event_type in ['building', 'placed', 'folded', 'packed']:
                        summary.building_events += 1
                    elif event_type == 'emote':
                        summary.emotes += 1
                    elif event_type == 'teleported':
                        summary.teleported_events += 1
                    elif event_type == 'death':
                        summary.deaths += 1
                    
                    # Handle combat events
                    if hasattr(parse_result.event.details, 'get') and parse_result.event.details.get('combat_event'):
                        combat_events.append(parse_result.event.details['combat_event'])
                        summary.combat_events += 1
                    
                    # Update timestamps
                    timestamp = parse_result.event.timestamp
                    if summary.start_time is None or timestamp < summary.start_time:
                        summary.start_time = timestamp
                    if summary.end_time is None or timestamp > summary.end_time:
                        summary.end_time = timestamp
                        
                elif parse_result.error:
                    summary.malformed_lines += 1
                    if len(summary.malformed_samples) < max_malformed_samples:
                        sample = f"Line {line_number}: {parse_result.raw_line[:100]}{'...' if len(parse_result.raw_line) > 100 else ''}"
                        summary.malformed_samples.append(sample)
        
        logger.info(f"Parsed {summary.parsed_events} events from {summary.total_lines} lines")
        if summary.malformed_lines > 0:
            logger.warning(f"Found {summary.malformed_lines} malformed lines")
        
        return events, combat_events, summary
    
    def _extract_date_from_filename(self, filename: str) -> datetime:
        """Extract date from log filename, fallback to current date."""
        try:
            # Try to extract date from filename like "ADM-2023-01-15.log"
            import re
            match = re.search(r'(\d{4})-(\d{2})-(\d{2})', filename)
            if match:
                year, month, day = match.groups()
                return datetime(int(year), int(month), int(day))
        except Exception as e:
            logger.debug(f"Could not extract date from filename '{filename}': {e}")
        
        # Fallback to current date
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def _parse_line(self, line: str, base_date: datetime, line_number: int) -> ParseResult:
        """Parse a single log line into a ParseResult."""
        logger.debug(f"PARSING LINE {line_number}: {line}")
        
        for event_type, pattern in self.patterns.items():
            try:
                match = pattern.match(line)
                if match:
                    logger.debug(f"MATCHED EVENT TYPE: {event_type}")
                    event = self._create_event_from_match(event_type, match, base_date, line)
                    if event:
                        return ParseResult(event=event, line_number=line_number, raw_line=line)
                    else:
                        return ParseResult(
                            error=f"Failed to create event from match for type {event_type}",
                            line_number=line_number,
                            raw_line=line
                        )
            except Exception as e:
                logger.debug(f"Error matching pattern {event_type}: {e}")
                continue
        
        logger.debug(f"NO PATTERN MATCHED FOR LINE {line_number}")
        return ParseResult(
            error="No pattern matched",
            line_number=line_number,
            raw_line=line
        )
    
    # Move all the helper methods from DayZADMAnalyzer here...
    # (I'll implement the key ones to keep this manageable)
    
    def _safe_group_access(self, groups: tuple, index: int, default: str = "Unknown") -> str:
        """Safely access regex group by index, returning default if index out of range or None."""
        try:
            if index < len(groups) and groups[index] is not None:
                return groups[index]
            return default
        except (IndexError, TypeError):
            return default
    
    def _safe_group_float(self, groups: tuple, index: int, default: float = 0.0) -> float:
        """Safely access regex group as float, returning default if index out of range, None, or conversion fails."""
        try:
            if index < len(groups) and groups[index] is not None:
                return float(groups[index])
            return default
        except (IndexError, TypeError, ValueError):
            return default
    
    def _safe_group_int(self, groups: tuple, index: int, default: int = 0) -> int:
        """Safely access regex group as int, returning default if index out of range, None, or conversion fails."""
        try:
            if index < len(groups) and groups[index] is not None:
                return int(groups[index])
            return default
        except (IndexError, TypeError, ValueError):
            return default

    def _safe_position_extract(self, groups: tuple, x_index: int, y_index: int, z_index: int) -> Optional[Tuple[float, float, float]]:
        """Safely extract position coordinates from regex groups."""
        try:
            if (x_index < len(groups) and y_index < len(groups) and z_index < len(groups) and
                groups[x_index] is not None and groups[y_index] is not None and groups[z_index] is not None):
                return (float(groups[x_index]), float(groups[y_index]), float(groups[z_index]))
            return None
        except (IndexError, TypeError, ValueError):
            return None

    # Named group access methods for improved readability
    def _safe_named_group_access(self, match, group_name: str, default: str = "Unknown") -> str:
        """Safely access regex named group, returning default if group doesn't exist or is None."""
        try:
            value = match.group(group_name)
            if value is not None:
                return value.strip()
            else:
                return default
        except (IndexError, TypeError, AttributeError):
            return default
    
    def _safe_named_group_float(self, match, group_name: str, default: float = 0.0) -> float:
        """Safely access regex named group as float, returning default if group doesn't exist, is None, or conversion fails."""
        try:
            value = match.group(group_name)
            if value is not None:
                return float(value)
            else:
                return default
        except (IndexError, TypeError, ValueError, AttributeError):
            return default
    
    def _safe_named_group_int(self, match, group_name: str, default: int = 0) -> int:
        """Safely access regex named group as int, returning default if group doesn't exist, is None, or conversion fails."""
        try:
            value = match.group(group_name)
            if value is not None:
                return int(value)
            else:
                return default
        except (IndexError, TypeError, ValueError, AttributeError):
            return default

    def _safe_position_extract_named(self, match, x_name: str, y_name: str, z_name: str) -> Optional[Tuple[float, float, float]]:
        """Safely extract position coordinates from regex named groups."""
        try:
            x = match.group(x_name)
            y = match.group(y_name)
            z = match.group(z_name)
            if x is not None and y is not None and z is not None:
                return (float(x), float(y), float(z))
            else:
                return None
        except (IndexError, TypeError, ValueError, AttributeError):
            return None
    
    def _create_timestamp(self, time_str: str, base_date: datetime) -> datetime:
        """Create a timestamp from time string and base date, handling day rollover correctly."""
        try:
            time_parts = time_str.split(':')
            timestamp = base_date.replace(
                hour=int(time_parts[0]),
                minute=int(time_parts[1]),
                second=int(time_parts[2])
            )
            
            # Handle day rollover (if timestamp is more than 12 hours behind base_date, assume next day)
            if (base_date - timestamp).total_seconds() > 43200:  # 12 hours
                timestamp += timedelta(days=1)
                
            return timestamp
        except Exception as e:
            logger.error(f"Error creating timestamp from '{time_str}': {e}")
            return base_date
    
    def _create_event_from_match(self, event_type: str, match, base_date: datetime, line: str) -> Optional[PlayerEvent]:
        """Create a PlayerEvent from a regex match - includes combat event creation."""
        try:
            # Use named groups for better readability
            time_str = self._safe_named_group_access(match, 'time', "00:00:00")
            details = {'raw_line': line}
            
            # Parse timestamp using helper method
            timestamp = self._create_timestamp(time_str, base_date)
            
            # Handle different event types using named groups
            if event_type in ['connection', 'disconnection']:
                player_name = self._safe_named_group_access(match, 'player_name')
                player_id = self._safe_named_group_access(match, 'player_id')
                position = None
                
            elif event_type == 'player_position':
                player_name = self._safe_named_group_access(match, 'player_name')
                player_id = self._safe_named_group_access(match, 'player_id')
                position = self._safe_position_extract_named(match, 'x', 'y', 'z')
                
            elif event_type in ['unconscious', 'conscious']:
                player_name = self._safe_named_group_access(match, 'player_name')
                player_id = self._safe_named_group_access(match, 'player_id')
                position = self._safe_position_extract_named(match, 'x', 'y', 'z')
                
            elif event_type == 'suicide':
                player_name = self._safe_named_group_access(match, 'player_name')
                player_id = self._safe_named_group_access(match, 'player_id')
                position = self._safe_position_extract_named(match, 'x', 'y', 'z')
                
            elif event_type == 'emote':
                player_name = self._safe_named_group_access(match, 'player_name')
                player_id = self._safe_named_group_access(match, 'player_id')
                position = self._safe_position_extract_named(match, 'x', 'y', 'z')
                emote = self._safe_named_group_access(match, 'emote', '')
                emote_item = self._safe_named_group_access(match, 'emote_item', '')
                details.update({
                    'emote': emote,
                    'emote_item': emote_item
                })
                
            elif event_type == 'hit':
                # Combat event - create CombatEvent in details ONLY for player vs player combat
                victim_name = self._safe_named_group_access(match, 'victim_name')
                victim_id = self._safe_named_group_access(match, 'victim_id')
                victim_pos = self._safe_position_extract_named(match, 'victim_x', 'victim_y', 'victim_z')
                victim_hp = self._safe_named_group_float(match, 'victim_hp')
                
                attacker_name = self._safe_named_group_access(match, 'attacker_name')
                attacker_id = self._safe_named_group_access(match, 'attacker_id')
                attacker_pos = self._safe_position_extract_named(match, 'attacker_x', 'attacker_y', 'attacker_z')
                
                hit_location = self._safe_named_group_access(match, 'hit_location', 'unknown')
                damage = self._safe_named_group_float(match, 'damage')
                ammo = self._safe_named_group_access(match, 'ammo', '')
                weapon = self._safe_named_group_access(match, 'weapon', 'Unknown')
                distance = self._safe_named_group_float(match, 'distance')
                
                # Handle melee weapons: if no weapon specified but ammo contains melee weapon, use ammo as weapon
                if weapon == 'Unknown' and ammo:
                    # Check if ammo field contains a melee weapon
                    melee_weapons = ['MeleeFist', 'MeleeAxe', 'MeleeKnife', 'MeleeBat', 'MeleeShovel', 
                                   'MeleeHammer', 'MeleeMachete', 'MeleePipe', 'MeleeCrowbar']
                    if any(melee in ammo for melee in melee_weapons):
                        weapon = ammo
                
                # Check if this is a kill (victim has DEAD in original line or HP is 0)
                is_kill = victim_hp == 0.0 or "(DEAD)" in line
                
                # Only create combat event for player vs player combat
                # Check that attacker_name is not empty and doesn't contain generic identifiers
                if (attacker_name and attacker_name != "Unknown" and 
                    not attacker_name.startswith("Environment") and
                    not attacker_name.startswith("Explosion") and
                    victim_name and victim_name != "Unknown"):
                    
                    combat_event = CombatEvent(
                        timestamp=timestamp,
                        attacker_name=attacker_name,
                        attacker_id=attacker_id,
                        victim_name=victim_name,
                        victim_id=victim_id,
                        weapon=weapon,
                        damage=damage,
                        hit_location=hit_location,
                        distance=distance,
                        attacker_pos=attacker_pos,
                        victim_pos=victim_pos,
                        kill=is_kill
                    )
                    
                    details['combat_event'] = combat_event
                
                player_name = victim_name
                player_id = victim_id
                position = victim_pos
                
            elif event_type == 'kill':
                # Kill event - we already handle kills in hit events, so just track as regular event
                player_name = self._safe_named_group_access(match, 'victim_name')
                player_id = self._safe_named_group_access(match, 'victim_id')
                position = self._safe_position_extract_named(match, 'victim_x', 'victim_y', 'victim_z')
                # No combat_event created for kill events - already handled in hit events
                
            elif event_type in ['env_hit', 'env_hit_simple']:
                # Environmental hit - do NOT create combat event for these
                player_name = self._safe_named_group_access(match, 'player_name')
                player_id = self._safe_named_group_access(match, 'player_id')
                position = self._safe_position_extract_named(match, 'x', 'y', 'z')
                # No combat_event created for environmental damage
                
            elif event_type == 'explosion_hit':
                # Explosion hit - do NOT create combat event for these unless from player weapons
                player_name = self._safe_named_group_access(match, 'player_name')
                player_id = self._safe_named_group_access(match, 'player_id')
                position = self._safe_position_extract_named(match, 'x', 'y', 'z')
                # No combat_event created for explosion damage
                
            elif event_type in ['death', 'death_other']:
                # Death events
                player_name = self._safe_named_group_access(match, 'player_name')
                player_id = self._safe_named_group_access(match, 'player_id')
                position = self._safe_position_extract_named(match, 'x', 'y', 'z')
                
                if event_type == 'death':
                    # Additional stats for regular death
                    water = self._safe_named_group_float(match, 'water')
                    energy = self._safe_named_group_float(match, 'energy')
                    bleed_sources = self._safe_named_group_int(match, 'bleed_sources')
                    details.update({
                        'water': water,
                        'energy': energy,
                        'bleed_sources': bleed_sources
                    })
                elif event_type == 'death_other':
                    # Death by specific cause
                    killer = self._safe_named_group_access(match, 'killer', 'Unknown')
                    details['killer'] = killer
                    
            elif event_type in ['building', 'packed', 'placed', 'folded']:
                # Building/construction events
                player_name = self._safe_named_group_access(match, 'player_name')
                player_id = self._safe_named_group_access(match, 'player_id')
                position = self._safe_position_extract_named(match, 'x', 'y', 'z')
                
                if event_type == 'building':
                    action = self._safe_named_group_access(match, 'action', '')
                    structure = self._safe_named_group_access(match, 'structure', '')
                    tool = self._safe_named_group_access(match, 'tool', '')
                    parent = self._safe_named_group_access(match, 'parent', '')
                    details.update({
                        'action': action,
                        'structure': structure,
                        'tool': tool,
                        'parent': parent
                    })
                else:
                    # packed, placed, folded
                    structure = self._safe_named_group_access(match, 'structure', '')
                    tool = self._safe_named_group_access(match, 'tool', '') if event_type == 'packed' else ''
                    details.update({
                        'action': event_type,
                        'structure': structure,
                        'tool': tool
                    })
                    
            elif event_type == 'teleported':
                # Teleportation event
                player_name = self._safe_named_group_access(match, 'player_name')
                player_id = self._safe_named_group_access(match, 'player_id')
                position = self._safe_position_extract_named(match, 'x', 'y', 'z')
                
                from_pos = self._safe_position_extract_named(match, 'from_x', 'from_y', 'from_z')
                to_pos = self._safe_position_extract_named(match, 'to_x', 'to_y', 'to_z')
                reason = self._safe_named_group_access(match, 'reason', '')
                
                # Calculate teleport distance safely
                teleport_distance = 0.0
                if from_pos and to_pos:
                    teleport_distance = ((to_pos[0] - from_pos[0]) ** 2 + 
                                       (to_pos[1] - from_pos[1]) ** 2 + 
                                       (to_pos[2] - from_pos[2]) ** 2) ** 0.5
                
                # Extract restricted area name if present
                restricted_area = None
                if "Restricted Area:" in reason:
                    try:
                        restricted_area = reason.split("Restricted Area:")[1].strip()
                    except:
                        restricted_area = None
                
                details.update({
                    'from_position': from_pos,
                    'to_position': to_pos,
                    'reason': reason,
                    'restricted_area': restricted_area,
                    'teleport_distance': teleport_distance
                })
                
            else:
                # Generic parsing for other event types (special events, etc.)
                player_name = self._safe_named_group_access(match, 'player_name', 'Unknown')
                player_id = self._safe_named_group_access(match, 'player_id', 'Unknown')
                position = self._safe_position_extract_named(match, 'x', 'y', 'z')
            
            return PlayerEvent(
                timestamp=timestamp,
                player_name=player_name,
                player_id=player_id,
                event_type=event_type,
                position=position,
                details=details
            )
        except Exception as e:
            logger.error(f"Error creating event from match for type {event_type}: {e}")
            return None


class DayZADMAnalyzer(FileBasedTool):
    """
    Analyzes DayZ AdminLog (ADM) files to extract player behavior statistics.
    
    This tool provides comprehensive analytics including:
    - Player session statistics
    - Combat analytics  
    - Building/construction activity
    - Movement and positioning analysis
    - Administrative insights and anomaly detection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the ADM analyzer."""
        super().__init__(config)
        self.initialize_directories()

        # Data storage (must be initialized for all use cases)
        self.events: List[PlayerEvent] = []
        self.combat_events: List[CombatEvent] = []
        self.player_sessions: Dict[str, List[PlayerSession]] = defaultdict(list)
        self.current_sessions: Dict[str, PlayerSession] = {}

        # Cached derived maps for performance optimization
        self._events_by_player: Optional[Dict[str, List[PlayerEvent]]] = None
        self._combat_events_by_attacker: Optional[Dict[str, List[CombatEvent]]] = None
        self._combat_events_by_victim: Optional[Dict[str, List[CombatEvent]]] = None
        self._player_id_to_name: Optional[Dict[str, str]] = None
        self._cache_dirty: bool = True
        
        # Parser for handling log file parsing
        self.parser = DayZADMParser(config)
        
        # Parse error tracking
        self.parse_summary: Optional[ParseSummary] = None
        
    def _invalidate_cache(self):
        """Invalidate cached derived maps when data changes."""
        self._events_by_player = None
        self._combat_events_by_attacker = None
        self._combat_events_by_victim = None
        self._player_id_to_name = None
        self._cache_dirty = True
    
    def _ensure_cache_valid(self):
        """Ensure cached derived maps are built and up to date."""
        if not self._cache_dirty and self._events_by_player is not None:
            return
            
        # Build events_by_player cache
        self._events_by_player = defaultdict(list)
        for event in self.events:
            if event.player_id:
                self._events_by_player[event.player_id].append(event)
        
        # Build combat_events_by_attacker cache
        self._combat_events_by_attacker = defaultdict(list)
        for event in self.combat_events:
            if event.attacker_id and event.attacker_id.strip():
                self._combat_events_by_attacker[event.attacker_id].append(event)
        
        # Build combat_events_by_victim cache
        self._combat_events_by_victim = defaultdict(list)
        for event in self.combat_events:
            if event.victim_id and event.victim_id.strip():
                self._combat_events_by_victim[event.victim_id].append(event)
        
        # Build player_id_to_name cache
        self._player_id_to_name = {}
        for event in self.events:
            if event.player_id and event.player_name:
                self._player_id_to_name[event.player_id] = event.player_name
        
        self._cache_dirty = False
    
    def get_events_by_player(self, player_id: str) -> List[PlayerEvent]:
        """Get all events for a specific player using cached lookup."""
        self._ensure_cache_valid()
        return self._events_by_player.get(player_id, [])
    
    def get_combat_events_by_attacker(self, player_id: str) -> List[CombatEvent]:
        """Get all combat events where player is the attacker using cached lookup."""
        self._ensure_cache_valid()
        return self._combat_events_by_attacker.get(player_id, [])
    
    def get_combat_events_by_victim(self, player_id: str) -> List[CombatEvent]:
        """Get all combat events where player is the victim using cached lookup."""
        self._ensure_cache_valid()
        return self._combat_events_by_victim.get(player_id, [])
    
    def get_player_name(self, player_id: str) -> str:
        """Get player name for a player ID using cached lookup."""
        self._ensure_cache_valid()
        return self._player_id_to_name.get(player_id, "Unknown")
        
    def parse_log_file(self, log_file: str) -> Dict[str, Any]:
        """
        Parse a DayZ ADM log file using the decoupled parser.
        
        Args:
            log_file: Path to the ADM log file
            
        Returns:
            Dictionary containing parsing results and statistics
        """
        log_path = self.resolve_path(log_file)
        logger.info(f"Parsing ADM log file: {log_path}")
        
        # Use the decoupled parser to get events and error statistics
        events, combat_events, parse_summary = self.parser.parse_file(log_path)
        
        # Store the parse summary for error reporting
        self.parse_summary = parse_summary
        
        # Process events through the analyzer
        for event in events:
            self.events.append(event)
            
            # Handle specific event types for session management
            if event.event_type == 'connection':
                self._handle_connection(event)
            elif event.event_type == 'disconnection':
                self._handle_disconnection(event)
            
            # Handle position tracking for active sessions
            if event.position and event.player_id in self.current_sessions:
                session = self.current_sessions[event.player_id]
                session.positions.append((event.timestamp, *event.position))
        
        # Store combat events
        self.combat_events.extend(combat_events)
        
        # Invalidate cache after all events are processed
        self._invalidate_cache()
                        
        # Close any remaining open sessions
        for session in self.current_sessions.values():
            if session.disconnect_time is None:
                session.disconnect_time = parse_summary.end_time
            self.player_sessions[session.player_id].append(session)
        self.current_sessions.clear()
        
        # Convert parse summary to legacy format for compatibility
        parse_stats = {
            'total_lines': parse_summary.total_lines,
            'parsed_events': parse_summary.parsed_events,
            'malformed_lines': parse_summary.malformed_lines,
            'malformed_samples': parse_summary.malformed_samples,
            'connections': parse_summary.connections,
            'disconnections': parse_summary.disconnections,
            'combat_events': parse_summary.combat_events,
            'deaths': parse_summary.deaths,
            'building_events': parse_summary.building_events,
            'emotes': parse_summary.emotes,
            'teleported_events': parse_summary.teleported_events,
            'start_time': parse_summary.start_time,
            'end_time': parse_summary.end_time
        }
        
        logger.info(f"Parsed {parse_stats['parsed_events']} events from {parse_stats['total_lines']} lines")
        if parse_stats['malformed_lines'] > 0:
            logger.warning(f"Found {parse_stats['malformed_lines']} malformed lines")
            
        return parse_stats
    
    def get_parse_error_report(self) -> Dict[str, Any]:
        """
        Get detailed error report from the last parsing operation for data quality assessment.
        
        This method provides comprehensive error statistics including malformed line counts,
        sample problematic lines, and error rates. Essential for production log analysis
        where data quality matters.
        
        Returns:
            Dictionary containing:
            - malformed_lines: Number of lines that couldn't be parsed
            - malformed_samples: List of sample malformed lines (up to configured limit)
            - error_rate: Percentage of malformed lines
            - total_lines: Total lines processed
            - parsed_events: Successfully parsed events
            
        Example:
            analyzer = DayZADMAnalyzer()
            analyzer.parse_log_file("server.adm")
            error_report = analyzer.get_parse_error_report()
            
            if error_report['error_rate'] > 5.0:
                logger.warning(f"High error rate: {error_report['error_rate']:.2f}%")
                for sample in error_report['malformed_samples']:
                    logger.warning(f"Malformed line: {sample}")
        """
        if not self.parse_summary:
            return {
                'malformed_lines': 0,
                'malformed_samples': [],
                'error_rate': 0.0
            }
        
        error_rate = 0.0
        if self.parse_summary.total_lines > 0:
            error_rate = (self.parse_summary.malformed_lines / self.parse_summary.total_lines) * 100
        
        return {
            'malformed_lines': self.parse_summary.malformed_lines,
            'malformed_samples': self.parse_summary.malformed_samples,
            'error_rate': error_rate,
            'total_lines': self.parse_summary.total_lines,
            'parsed_events': self.parse_summary.parsed_events
        }
        
    def _extract_date_from_filename(self, filepath: str) -> datetime:
        """Extract date from ADM log filename."""
        # Pattern: DayZServer_X1_x64_2025-07-29_16-04-37.ADM
        filename = Path(filepath).name
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})', filename)
        
        if date_match:
            date_str = date_match.group(1)
            time_str = date_match.group(2).replace('-', ':')
            return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        else:
            # Fallback to current date
            logger.warning(f"Could not extract date from filename: {filename}")
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def _parse_line(self, line: str, base_date: datetime) -> Optional[PlayerEvent]:
        """Parse a single log line into a PlayerEvent."""
        # DEBUG: print the line being parsed
        logger.debug(f"PARSING LINE: {line}")
        for event_type, pattern in self.patterns.items():
            match = pattern.match(line)
            if match:
                logger.debug(f"MATCHED EVENT TYPE: {event_type}")
                return self._create_event_from_match(event_type, match, base_date, line)
        logger.debug("NO PATTERN MATCHED FOR LINE")
        return None
    
    def _create_timestamp(self, time_str: str, base_date: datetime) -> datetime:
        """Create a timestamp from time string and base date, handling day rollover correctly."""
        time_parts = time_str.split(':')
        timestamp = base_date.replace(
            hour=int(time_parts[0]),
            minute=int(time_parts[1]),
            second=int(time_parts[2])
        )
        
        # Handle day rollover - compare against base date (date only, not time)
        base_date_only = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
        if timestamp < base_date_only:
            timestamp += timedelta(days=1)
            
        return timestamp

    def _create_event_from_match(self, event_type: str, match, base_date: datetime, line: str) -> PlayerEvent:
        """Create a PlayerEvent from a regex match."""
        groups = match.groups()
        time_str = self._safe_group_access(groups, 0, "00:00:00")
        details = {'raw_line': line}
        # ...existing code...
        # --- Config-driven special events ---
        special_events_cfg = (self.config or {}).get('special_events', {})
        special_event_names = set(e.get('name') for e in special_events_cfg.get('events', [])) if special_events_cfg.get('enabled', False) else set()
        if event_type in special_event_names:
            # Generic handler for config-driven special events
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            # Try to extract position if present (groups 3,4,5)
            position = self._safe_position_extract(groups, 3, 4, 5)
            details.update({'event': event_type, 'raw_groups': groups})
            # Optionally, extract more details if the config provides a 'fields' list in the future
            return PlayerEvent(
                timestamp=self._create_timestamp(time_str, base_date),
                player_name=player_name,
                player_id=player_id,
                event_type=event_type,
                position=position,
                details=details
            )
        # (No hardcoded treasure_hunt block; handled by config-driven special event logic above)
        elif event_type == 'packed':
            # Special event for packed (building event)
            logger.debug(f"PACKED EVENT GROUPS: {groups}")
            # Use safe access instead of rigid length check
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            position = self._safe_position_extract(groups, 3, 4, 5)
            structure = self._safe_group_access(groups, 6)
            tool = self._safe_group_access(groups, 7)
            
            details.update({
                'action': 'packed',
                'structure': structure,
                'parent': '',
                'tool': tool
            })
            # Return PlayerEvent immediately to avoid further processing and tuple index errors
            return PlayerEvent(
                timestamp=self._create_timestamp(time_str, base_date),
                player_name=player_name,
                player_id=player_id,
                event_type='building',
                position=position,
                details=details
            )
        # ...existing code...
        
        # Parse timestamp using helper method
        timestamp = self._create_timestamp(time_str, base_date)
        
        if event_type in ['connection', 'disconnection']:
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            position = None
        
        elif event_type == 'player_position':
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            position = self._safe_position_extract(groups, 3, 4, 5)

        elif event_type in ['placed', 'folded']:
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            position = self._safe_position_extract(groups, 3, 4, 5)
            
        elif event_type == 'death':
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            position = self._safe_position_extract(groups, 3, 4, 5)
            details.update({
                'water': self._safe_group_float(groups, 6),
                'energy': self._safe_group_float(groups, 7),
                'bleed_sources': self._safe_group_int(groups, 8)
            })
            
        elif event_type == 'hit':
            # Victim is the first player mentioned
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            victim_pos = self._safe_position_extract(groups, 3, 4, 5)
            victim_hp = self._safe_group_float(groups, 6)
            attacker_name = self._safe_group_access(groups, 7)
            attacker_id = self._safe_group_access(groups, 8)
            attacker_pos = self._safe_position_extract(groups, 9, 10, 11)
            hit_location = self._safe_group_access(groups, 12, "unknown").strip()
            # DEBUG: log all groups for hit event
            logger.debug(f"HIT GROUPS: {groups}")
            damage = self._safe_group_float(groups, 14)  # Use damage from "for X damage" part
            ammo = self._safe_group_access(groups, 15)
            
            # Robustly assign weapon and distance for all cases
            weapon = None
            distance = None
            # If both weapon and distance are present (16 and 17), assign accordingly
            if len(groups) > 17 and groups[16] is not None and groups[17] is not None:
                weapon = self._safe_group_access(groups, 16).strip()
                distance = self._safe_group_float(groups, 17)
            # If only weapon is present (16), assign weapon, distance remains None
            elif len(groups) > 16 and groups[16] is not None:
                weapon = self._safe_group_access(groups, 16).strip()
                distance = None
            # If only ammo is present (15), treat as weapon for legacy lines
            elif len(groups) > 15 and groups[15] is not None:
                weapon = self._safe_group_access(groups, 15).strip()
                distance = None

            position = victim_pos
            details.update({
                'attacker_name': attacker_name,
                'attacker_id': attacker_id,
                'attacker_pos': attacker_pos,
                'victim_hp': victim_hp,
                'hit_location': hit_location,
                'damage': damage,
                'ammo': ammo,
                'weapon': weapon,
                'distance': distance
            })

            # Create combat event
            combat_event = CombatEvent(
                timestamp=timestamp,
                attacker_name=attacker_name,
                attacker_id=attacker_id,
                victim_name=player_name,
                victim_id=player_id,
                weapon=weapon if weapon is not None else '',
                damage=damage,
                hit_location=hit_location,
                distance=distance if distance is not None else 0.0,
                attacker_pos=attacker_pos,
                victim_pos=victim_pos
            )
            self.combat_events.append(combat_event)
            self._invalidate_cache()  # Invalidate cache when combat data changes

        elif event_type == 'env_hit':
            # Environmental hit (e.g., hit by Fence with BarbedWireHit)
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            victim_pos = self._safe_position_extract(groups, 3, 4, 5)
            victim_hp = self._safe_group_float(groups, 6)
            attacker_name = self._safe_group_access(groups, 7)  # e.g., Fence
            weapon = self._safe_group_access(groups, 8)         # e.g., BarbedWireHit
            position = victim_pos
            details.update({
                'attacker_name': attacker_name,
                'attacker_id': None,
                'attacker_pos': None,
                'victim_hp': victim_hp,
                'hit_location': None,
                'damage': None,
                'ammo': None,
                'weapon': weapon,
                'distance': None
            })

        elif event_type == 'env_hit_simple':
            # Simple environmental hit (e.g., hit by FallDamageHealth)
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            victim_pos = self._safe_position_extract(groups, 3, 4, 5)
            victim_hp = self._safe_group_float(groups, 6)
            attacker_name = self._safe_group_access(groups, 7)  # e.g., FallDamageHealth
            position = victim_pos
            details.update({
                'attacker_name': attacker_name,
                'attacker_id': None,
                'attacker_pos': None,
                'victim_hp': victim_hp,
                'hit_location': None,
                'damage': None,
                'ammo': None,
                'weapon': attacker_name,
                'distance': None
            })

        elif event_type == 'explosion_hit':
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            victim_pos = self._safe_position_extract(groups, 3, 4, 5)
            victim_hp = self._safe_group_float(groups, 6)
            explosion_type = self._safe_group_access(groups, 7)
            position = victim_pos
            details.update({
                'attacker_name': 'explosion',
                'attacker_id': None,
                'attacker_pos': None,
                'victim_hp': victim_hp,
                'hit_location': None,
                'damage': None,
                'ammo': None,
                'weapon': explosion_type,
                'distance': None
            })

        elif event_type == 'death_other':
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            victim_pos = self._safe_position_extract(groups, 3, 4, 5)
            killer = self._safe_group_access(groups, 6)
            position = victim_pos
            # Map animal classnames to friendly names and special event types
            animal_map = {
                'Animal_UrsusArctos': ('Bear', 'death_by_bear'),
                'Animal_CanisLupus_Grey': ('Wolf', 'death_by_wolf'),
                'Animal_CanisLupus_White': ('Wolf', 'death_by_wolf'),
            }
            if killer in animal_map:
                friendly, special_event = animal_map[killer]
                details.update({
                    'attacker_name': friendly,
                    'attacker_id': None,
                    'attacker_pos': None,
                    'weapon': None,
                    'distance': None,
                    'kill': True,
                    'special_event': special_event
                })
                event_type = special_event
            else:
                details.update({
                    'attacker_name': killer,
                    'attacker_id': None,
                    'attacker_pos': None,
                    'weapon': None,
                    'distance': None,
                    'kill': True
                })
            
        elif event_type == 'kill':
            player_name = self._safe_group_access(groups, 1)  # Victim
            player_id = self._safe_group_access(groups, 2)
            victim_pos = self._safe_position_extract(groups, 3, 4, 5)
            attacker_name = self._safe_group_access(groups, 6)
            attacker_id = self._safe_group_access(groups, 7)
            attacker_pos = self._safe_position_extract(groups, 8, 9, 10)
            weapon = self._safe_group_access(groups, 11).strip()
            distance = self._safe_group_float(groups, 12)

            position = victim_pos
            details.update({
                'attacker_name': attacker_name,
                'attacker_id': attacker_id,
                'attacker_pos': attacker_pos,
                'weapon': weapon,
                'distance': distance,
                'kill': True
            })

            # Aggregate all hit events at the kill timestamp for this attacker/victim
            total_damage = 0.0
            hit_locations = []
            events_to_remove = set()
            for idx, prev_event in enumerate(self.combat_events):
                if (
                    prev_event.attacker_id == attacker_id and
                    prev_event.victim_id == player_id and
                    prev_event.timestamp == timestamp and
                    not prev_event.kill
                ):
                    total_damage += prev_event.damage
                    if prev_event.hit_location:
                        hit_locations.append(prev_event.hit_location)
                    events_to_remove.add(idx)

            # Remove hit events at the kill timestamp to avoid double-counting in stats
            # Create new list without the events to remove
            self.combat_events = [event for idx, event in enumerate(self.combat_events) 
                                if idx not in events_to_remove]

            # If no hits at the same timestamp, fallback to previous logic (most recent hit in 30s window)
            if total_damage == 0.0:
                for prev_event in reversed(self.combat_events):
                    if (
                        prev_event.attacker_id == attacker_id and
                        prev_event.victim_id == player_id and
                        abs((timestamp - prev_event.timestamp).total_seconds()) < 30
                    ):
                        total_damage = prev_event.damage
                        hit_locations = [prev_event.hit_location] if prev_event.hit_location else []
                        break

            combat_event = CombatEvent(
                timestamp=timestamp,
                attacker_name=attacker_name,
                attacker_id=attacker_id,
                victim_name=player_name,
                victim_id=player_id,
                weapon=weapon,
                damage=total_damage,
                hit_location=", ".join(hit_locations),
                distance=distance,
                attacker_pos=attacker_pos,
                victim_pos=victim_pos,
                kill=True
            )
            self.combat_events.append(combat_event)
            self._invalidate_cache()  # Invalidate cache when combat data changes
            
        elif event_type in ['suicide', 'unconscious', 'conscious', 'emote']:
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            # For suicide, pos may be missing
            position = self._safe_position_extract(groups, 3, 4, 5)

            if event_type == 'emote':
                details['emote'] = self._safe_group_access(groups, 6)
                
        elif event_type == 'building':
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            position = self._safe_position_extract(groups, 3, 4, 5)
            action = self._safe_group_access(groups, 6)  # Built or Dismantled
            structure = self._safe_group_access(groups, 7)
            # on_or_from = groups[8]  # 'on' or 'from', not used in details
            parent = self._safe_group_access(groups, 9)
            tool = self._safe_group_access(groups, 10)
            details.update({
                'action': action,
                'structure': structure,
                'parent': parent,
                'tool': tool
            })
            
        elif event_type == 'teleported':
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            current_pos = self._safe_position_extract(groups, 3, 4, 5)
            from_pos = self._safe_position_extract(groups, 6, 7, 8)
            to_pos = self._safe_position_extract(groups, 9, 10, 11)
            reason = self._safe_group_access(groups, 12).strip()
            
            position = current_pos  # Use current position as the event position
            
            # Extract restricted area name if present
            restricted_area = None
            if "Restricted Area:" in reason:
                try:
                    restricted_area = reason.split("Restricted Area:")[-1].strip()
                except:
                    restricted_area = None
            
            # Calculate teleport distance safely
            teleport_distance = 0.0
            if from_pos and to_pos:
                teleport_distance = ((to_pos[0] - from_pos[0]) ** 2 + 
                                   (to_pos[1] - from_pos[1]) ** 2 + 
                                   (to_pos[2] - from_pos[2]) ** 2) ** 0.5
            
            details.update({
                'from_position': from_pos,
                'to_position': to_pos,
                'reason': reason,
                'restricted_area': restricted_area,
                'teleport_distance': teleport_distance
            })
            
        else:
            # Generic parsing for other event types
            player_name = self._safe_group_access(groups, 1)
            player_id = self._safe_group_access(groups, 2)
            position = None
            
        return PlayerEvent(
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            event_type=event_type,
            position=position,
            details=details
        )
    
    def _handle_connection(self, event: PlayerEvent):
        """Handle player connection event."""
        # Close any existing session for this player
        if event.player_id in self.current_sessions:
            existing_session = self.current_sessions[event.player_id]
            existing_session.disconnect_time = event.timestamp
            self.player_sessions[event.player_id].append(existing_session)
        
        # Start new session
        session = PlayerSession(
            player_name=event.player_name,
            player_id=event.player_id,
            connect_time=event.timestamp
        )
        self.current_sessions[event.player_id] = session
    
    def _handle_disconnection(self, event: PlayerEvent):
        """Handle player disconnection event."""
        if event.player_id in self.current_sessions:
            session = self.current_sessions[event.player_id]
            session.disconnect_time = event.timestamp
            self.player_sessions[event.player_id].append(session)
            del self.current_sessions[event.player_id]
    
    def generate_player_statistics(self) -> Dict[str, Any]:
        """Generate comprehensive player statistics."""
        stats = {
            'total_unique_players': len(self.player_sessions),
            'total_sessions': sum(len(sessions) for sessions in self.player_sessions.values()),
            'players': {}
        }
        
        for player_id, sessions in self.player_sessions.items():
            if not sessions:
                continue
                
            player_name = sessions[0].player_name
            total_playtime = sum(s.duration.total_seconds() if s.duration else 0 for s in sessions)
            total_distance = sum(s.distance_traveled for s in sessions)
            
            # Count player events using cached lookup
            player_events = self.get_events_by_player(player_id)
            player_combat_as_victim = self.get_combat_events_by_victim(player_id)
            
            # Count all deaths for reporting
            deaths = len([e for e in player_events if e.event_type == 'death'])
            # Count only deaths caused by another player for K/D
            deaths_by_player = len([e for e in player_combat_as_victim if e.kill])
            suicides = len([e for e in player_events if e.event_type == 'suicide'])
            emotes = len([e for e in player_events if e.event_type == 'emote'])
            building_actions = len([e for e in player_events if e.event_type in ('building', 'placed', 'folded', 'packed')])
            teleported_events = len([e for e in player_events if e.event_type == 'teleported'])
            deaths_by_bear = len([e for e in player_events if e.event_type == 'death_by_bear'])
            deaths_by_wolf = len([e for e in player_events if e.event_type == 'death_by_wolf'])
            
            # PvP-only combat statistics using cached lookups
            player_combat_as_attacker = self.get_combat_events_by_attacker(player_id)
            
            kills_pvp = len([e for e in player_combat_as_attacker if e.kill])
            # Filter for valid PvP events (both attacker and victim must be valid player IDs)
            pvp_hits_dealt = [e for e in player_combat_as_attacker if e.victim_id and e.victim_id.strip() and e.attacker_id != e.victim_id]
            pvp_hits_taken = [e for e in player_combat_as_victim if e.attacker_id and e.attacker_id.strip() and e.attacker_id != e.victim_id]
            
            hits_dealt_pvp = len(pvp_hits_dealt)
            hits_taken_pvp = len(pvp_hits_taken)
            damage_dealt_pvp = sum(e.damage for e in pvp_hits_dealt)
            damage_taken_pvp = sum(e.damage for e in pvp_hits_taken)

            stats['players'][player_id] = {
                'name': player_name,
                'sessions': len(sessions),
                'total_playtime_hours': total_playtime / 3600,
                'avg_session_time_minutes': (total_playtime / len(sessions) / 60) if sessions else 0,
                'total_distance_traveled': total_distance,
                'deaths': deaths,
                'suicides': suicides,
                'kills (PvP)': kills_pvp,
                'kd_ratio (PvP)': kills_pvp / max(deaths_by_player, 1),
                'hits_dealt (PvP)': hits_dealt_pvp,
                'hits_taken (PvP)': hits_taken_pvp,
                'damage_dealt (PvP)': damage_dealt_pvp,
                'damage_taken (PvP)': damage_taken_pvp,
                'accuracy (PvP)': (kills_pvp / max(hits_dealt_pvp, 1)) * 100 if hits_dealt_pvp > 0 else 0,
                'emotes': emotes,
                'building_actions': building_actions,
                'teleported_events': teleported_events,
                'avg_damage_per_hit (PvP)': damage_dealt_pvp / max(hits_dealt_pvp, 1) if hits_dealt_pvp > 0 else 0,
                'deaths_by_bear': deaths_by_bear,
                'deaths_by_wolf': deaths_by_wolf
            }
        
        return stats
    
    def generate_combat_statistics(self) -> Dict[str, Any]:
        """Generate combat-focused statistics."""
        if not self.combat_events:
            return {'message': 'No combat events found'}
        
        stats = {
            'total_combat_events': len(self.combat_events),
            'total_kills': len([e for e in self.combat_events if e.kill]),
            'weapon_usage': Counter(e.weapon for e in self.combat_events),
            'hit_locations': Counter(e.hit_location for e in self.combat_events),
            'average_damage': sum(e.damage for e in self.combat_events) / len(self.combat_events),
            'average_engagement_distance': sum(e.distance for e in self.combat_events) / len(self.combat_events),
            'combat_hotspots': {},
            'deadliest_weapons': {},
            'most_active_combatants': {}
        }
        
        # Analyze combat hotspots (grid-based)
        hotspots = defaultdict(int)
        for event in self.combat_events:
            if event.victim_pos:
                # Create 500m grid squares
                grid_x = int(event.victim_pos[0] // 500) * 500
                grid_y = int(event.victim_pos[1] // 500) * 500
                hotspots[(grid_x, grid_y)] += 1
        
        # Top 10 hotspots
        stats['combat_hotspots'] = dict(sorted(hotspots.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Deadliest weapons (by kill rate)
        weapon_stats = defaultdict(lambda: {'hits': 0, 'kills': 0, 'total_damage': 0})
        for event in self.combat_events:
            weapon_stats[event.weapon]['hits'] += 1
            weapon_stats[event.weapon]['total_damage'] += event.damage
            if event.kill:
                weapon_stats[event.weapon]['kills'] += 1
        
        for weapon, data in weapon_stats.items():
            kill_rate = (data['kills'] / data['hits']) * 100 if data['hits'] > 0 else 0
            avg_damage = data['total_damage'] / data['hits'] if data['hits'] > 0 else 0
            stats['deadliest_weapons'][weapon] = {
                'kill_rate': kill_rate,
                'average_damage': avg_damage,
                'total_hits': data['hits'],
                'total_kills': data['kills']
            }
        
        # Most active combatants
        combatant_activity = defaultdict(lambda: {'attacks': 0, 'kills': 0})
        for event in self.combat_events:
            combatant_activity[event.attacker_name]['attacks'] += 1
            if event.kill:
                combatant_activity[event.attacker_name]['kills'] += 1
        
        stats['most_active_combatants'] = dict(sorted(
            combatant_activity.items(), 
            key=lambda x: x[1]['attacks'], 
            reverse=True
        )[:10])
        
        return stats
    
    def detect_anomalies(self) -> Dict[str, Any]:
        """Detect potentially suspicious or anomalous behavior."""
        anomalies = {
            'excessive_suicides': [],
            'rapid_reconnections': [],
            'suspicious_movement': [],
            'high_damage_dealers': [],
            'stat_padding_suspects': [],
            'frequent_teleports': []
        }
        
        # Excessive suicides (more than 5 in a session)
        for player_id, sessions in self.player_sessions.items():
            for session in sessions:
                if not session.duration:
                    continue
                    
                # Use cached lookup and filter by session time
                all_player_events = self.get_events_by_player(player_id)
                player_events = [e for e in all_player_events
                               if session.connect_time <= e.timestamp <= (session.disconnect_time or datetime.now())]
                
                suicides = len([e for e in player_events if e.event_type == 'suicide'])
                session_hours = session.duration.total_seconds() / 3600
                
                if suicides > 5 or (session_hours > 0 and suicides / session_hours > 3):
                    anomalies['excessive_suicides'].append({
                        'player_name': session.player_name,
                        'player_id': player_id,
                        'suicides': suicides,
                        'session_duration_hours': session_hours
                    })
        
        # Rapid reconnections (less than 30 seconds between disconnect and reconnect)
        for player_id, sessions in self.player_sessions.items():
            if len(sessions) < 2:
                continue
                
            sorted_sessions = sorted(sessions, key=lambda s: s.connect_time)
            rapid_reconnects = 0
            
            for i in range(1, len(sorted_sessions)):
                prev_session = sorted_sessions[i-1]
                curr_session = sorted_sessions[i]
                
                if prev_session.disconnect_time:
                    gap = curr_session.connect_time - prev_session.disconnect_time
                    if gap.total_seconds() < 30:
                        rapid_reconnects += 1
            
            if rapid_reconnects > 3:
                anomalies['rapid_reconnections'].append({
                    'player_name': sorted_sessions[0].player_name,
                    'player_id': player_id,
                    'rapid_reconnects': rapid_reconnects,
                    'total_sessions': len(sessions)
                })
        
        # High damage dealers (suspiciously high damage per hit)
        combat_stats = defaultdict(lambda: {'total_damage': 0, 'hits': 0})
        for event in self.combat_events:
            # Filter out environmental damage (None or empty attacker_id)
            if event.attacker_id and event.attacker_id.strip():
                combat_stats[event.attacker_id]['total_damage'] += event.damage
                combat_stats[event.attacker_id]['hits'] += 1
        
        for player_id, stats in combat_stats.items():
            if stats['hits'] > 0:
                avg_damage = stats['total_damage'] / stats['hits']
                if avg_damage > 150:  # Suspiciously high average damage
                    player_name = self.get_player_name(player_id)
                    anomalies['high_damage_dealers'].append({
                        'player_name': player_name,
                        'player_id': player_id,
                        'average_damage': avg_damage,
                        'total_hits': stats['hits']
                    })
        
        # Frequent teleportations (more than 3 teleports per session)
        for player_id, sessions in self.player_sessions.items():
            for session in sessions:
                if not session.duration:
                    continue
                    
                # Use cached lookup and filter by session time
                all_player_events = self.get_events_by_player(player_id)
                player_events = [e for e in all_player_events
                               if session.connect_time <= e.timestamp <= (session.disconnect_time or datetime.now())]
                
                teleports = len([e for e in player_events if e.event_type == 'teleported'])
                session_hours = session.duration.total_seconds() / 3600
                
                if teleports > 3 or (session_hours > 0 and teleports / session_hours > 2):
                    anomalies['frequent_teleports'].append({
                        'player_name': session.player_name,
                        'player_id': player_id,
                        'teleports': teleports,
                        'session_duration_hours': session_hours
                    })
        
        return anomalies
    
    def export_to_csv(self, output_prefix: str) -> List[str]:
        """
        Export analysis results to CSV files.
        
        Args:
            output_prefix: Prefix for output filenames
            
        Returns:
            List of created file paths
        """
        created_files = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Player statistics
        player_stats = self.generate_player_statistics()
        # --- Config-driven special events ---
        special_events_cfg = (self.config or {}).get('special_events', {})
        special_event_names = [e.get('name') for e in special_events_cfg.get('events', [])] if special_events_cfg.get('enabled', False) else []
        # Count special events per player using cached lookups
        special_event_counts = {name: {} for name in special_event_names}
        self._ensure_cache_valid()  # Ensure cache is built
        for player_id, events in self._events_by_player.items():
            for event in events:
                if event.event_type in special_event_names:
                    special_event_counts[event.event_type][player_id] = special_event_counts[event.event_type].get(player_id, 0) + 1

        if player_stats['players']:
            player_csv = self.resolve_path(f"{self.output_dir}/{output_prefix}_player_stats_{timestamp}.csv")
            with open(player_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Standard columns
                columns = [
                    'Player Name', 'Sessions', 'Total Playtime (Hours)',
                    'Avg Session Time (Minutes)', 'Distance Traveled', 'Deaths', 'Suicides',
                    'Kills (PvP)', 'K/D Ratio (PvP)', 'Hits Dealt (PvP)', 'Hits Taken (PvP)', 'Damage Dealt (PvP)',
                    'Damage Taken (PvP)', 'Avg Damage Per Hit (PvP)', 'Accuracy % (PvP)', 'Emotes', 'Building Actions',
                    'Teleported Events', 'Deaths by Bear', 'Deaths by Wolf'
                ]
                # Add special event columns
                columns += [f"{name.replace('_', ' ').title()} Events" for name in special_event_names]
                writer.writerow(columns)
                for player_id, stats in player_stats['players'].items():
                    row = [
                        stats['name'], stats['sessions'],
                        round(stats['total_playtime_hours'], 2),
                        round(stats['avg_session_time_minutes'], 2),
                        round(stats['total_distance_traveled'], 2),
                        stats['deaths'], stats['suicides'], stats['kills (PvP)'],
                        round(stats['kd_ratio (PvP)'], 2), stats['hits_dealt (PvP)'], stats['hits_taken (PvP)'],
                        round(stats['damage_dealt (PvP)'], 2), round(stats['damage_taken (PvP)'], 2),
                        round(stats['avg_damage_per_hit (PvP)'], 2), round(stats['accuracy (PvP)'], 2), stats['emotes'], stats['building_actions'],
                        stats['teleported_events'], stats.get('deaths_by_bear', 0),
                        stats.get('deaths_by_wolf', 0)
                    ]
                    # Add special event counts
                    for name in special_event_names:
                        row.append(special_event_counts[name].get(player_id, 0))
                    writer.writerow(row)
            created_files.append(player_csv)
            logger.info(f"Player statistics exported to: {player_csv}")
        
        # Combat events
        if self.combat_events:
            combat_csv = self.resolve_path(f"{self.output_dir}/{output_prefix}_combat_events_{timestamp}.csv")
            with open(combat_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp', 'Attacker Name', 'Victim Name',
                    'Weapon', 'Damage', 'Hit Location', 'Distance', 'Kill',
                    'Attacker X', 'Attacker Y', 'Attacker Z',
                    'Victim X', 'Victim Y', 'Victim Z'
                ])
                for event in self.combat_events:
                    writer.writerow([
                        event.timestamp.isoformat(),
                        event.attacker_name,
                        event.victim_name,
                        event.weapon, event.damage, event.hit_location, event.distance,
                        event.kill,
                        event.attacker_pos[0] if event.attacker_pos else '',
                        event.attacker_pos[1] if event.attacker_pos else '',
                        event.attacker_pos[2] if event.attacker_pos else '',
                        event.victim_pos[0] if event.victim_pos else '',
                        event.victim_pos[1] if event.victim_pos else '',
                        event.victim_pos[2] if event.victim_pos else ''
                    ])
            created_files.append(combat_csv)
            logger.info(f"Combat events exported to: {combat_csv}")

        # Teleportation events
        teleport_events = [e for e in self.events if e.event_type == 'teleported']
        if teleport_events:
            teleport_csv = self.resolve_path(f"{self.output_dir}/{output_prefix}_teleport_events_{timestamp}.csv")
            with open(teleport_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp', 'Player Name', 'From X', 'From Y', 'From Z',
                    'To X', 'To Y', 'To Z', 'Distance', 'Reason', 'Restricted Area'
                ])
                for event in teleport_events:
                    details = event.details or {}
                    from_pos = details.get('from_position', (None, None, None))
                    to_pos = details.get('to_position', (None, None, None))
                    writer.writerow([
                        event.timestamp.isoformat(),
                        event.player_name,
                        from_pos[0], from_pos[1], from_pos[2],
                        to_pos[0], to_pos[1], to_pos[2],
                        round(details.get('teleport_distance', 0), 2),
                        details.get('reason', ''),
                        details.get('restricted_area', '')
                    ])
            created_files.append(teleport_csv)
            logger.info(f"Teleportation events exported to: {teleport_csv}")

        # Building activities report (includes building, packed, placed, folded)
        building_events = [e for e in self.events if e.event_type in ('building', 'packed', 'placed', 'folded')]
        if building_events:
            building_csv = self.resolve_path(f"{self.output_dir}/{output_prefix}_building_events_{timestamp}.csv")
            with open(building_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp', 'Player Name', 'Action', 'Structure', 'Tool', 'X', 'Y', 'Z'
                ])
                for event in building_events:
                    details = event.details or {}
                    action = details.get('action', '')
                    structure = details.get('structure', '')
                    tool = details.get('tool', '')
                    # For placed and folded events, extract structure from details or fallback to event_type
                    if event.event_type == 'placed':
                        action = 'placed'
                        if not structure:
                            raw = details.get('raw_line', '')
                            if ' placed ' in raw:
                                structure = raw.split(' placed ')[-1].strip()
                    elif event.event_type == 'folded':
                        action = 'folded'
                        if not structure:
                            raw = details.get('raw_line', '')
                            if ' folded ' in raw:
                                structure = raw.split(' folded ')[-1].strip()
                    elif event.event_type == 'building':
                        # If structure or tool missing, try to extract from raw_line
                        if not structure or (tool is None):
                            raw = details.get('raw_line', '')
                            import re as _re
                            m = _re.search(r'\)\s*(Built|Dismantled|placed) ([^\s]+)(?: with ([^\s]+))?', raw)
                            if m:
                                if not action:
                                    action = m.group(1)
                                if not structure:
                                    structure = m.group(2)
                                if tool is None and m.lastindex >= 3:
                                    tool = m.group(3) if m.group(3) else ''
                        if tool is None:
                            tool = ''
                    # Always use event.position for all building-related events
                    x, y, z = ('', '', '')
                    if event.position:
                        x, y, z = event.position
                    writer.writerow([
                        event.timestamp.isoformat(),
                        event.player_name,
                        action,
                        structure,
                        tool,
                        x, y, z
                    ])
            created_files.append(building_csv)
            logger.info(f"Building activities exported to: {building_csv}")
        
        # Player sessions
        sessions_csv = self.resolve_path(f"{self.output_dir}/{output_prefix}_sessions_{timestamp}.csv")
        with open(sessions_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Player Name', 'Connect Time', 'Disconnect Time',
                'Duration (Minutes)', 'Distance Traveled', 'Position Count'
            ])
            for player_id, sessions in self.player_sessions.items():
                for session in sessions:
                    duration_minutes = session.duration.total_seconds() / 60 if session.duration else 0
                    writer.writerow([
                        session.player_name,
                        session.connect_time.isoformat(),
                        session.disconnect_time.isoformat() if session.disconnect_time else '',
                        round(duration_minutes, 2),
                        round(session.distance_traveled, 2),
                        len(session.positions)
                    ])
        created_files.append(sessions_csv)
        logger.info(f"Player sessions exported to: {sessions_csv}")
        
        return created_files
    
    def run(self, log_file: str, export_csv: bool = True, output_prefix: str = "adm_analysis", skip_parse: bool = False) -> Dict[str, Any]:
        """
        Run the complete ADM log analysis.
        
        Args:
            log_file: Path to the ADM log file
            export_csv: Whether to export results to CSV
            output_prefix: Prefix for output files
            
        Returns:
            Dictionary containing all analysis results
        """
        logger.info("Starting DayZ ADM log analysis")
        if not skip_parse:
            # Parse the log file
            parse_stats = self.parse_log_file(log_file)
        else:
            # Use already aggregated data, estimate parse_stats from events
            parse_stats = {
                'total_lines': None,
                'parsed_events': len(self.events),
                'connections': None,
                'disconnections': None,
                'combat_events': len(self.combat_events),
                'deaths': None,
                'building_events': None,
                'emotes': None,
                'start_time': self.events[0].timestamp if self.events else None,
                'end_time': self.events[-1].timestamp if self.events else None
            }
        # Generate statistics
        player_stats = self.generate_player_statistics()
        combat_stats = self.generate_combat_statistics()
        anomalies = self.detect_anomalies()
        
        # Get error reporting for data quality assessment
        error_report = self.get_parse_error_report()
        
        results = {
            'parse_statistics': parse_stats,
            'player_statistics': player_stats,
            'combat_statistics': combat_stats,
            'anomalies': anomalies,
            'error_report': error_report,
            'summary': {
                'analysis_timestamp': datetime.now().isoformat(),
                'log_file': log_file,
                'total_events_parsed': len(self.events),
                'unique_players': len(self.player_sessions),
                'total_combat_events': len(self.combat_events),
                'data_quality': {
                    'error_rate': error_report['error_rate'],
                    'malformed_lines': error_report['malformed_lines']
                },
                'analysis_time_range': {
                    'start': parse_stats['start_time'].isoformat() if parse_stats['start_time'] else None,
                    'end': parse_stats['end_time'].isoformat() if parse_stats['end_time'] else None
                }
            }
        }
        # Export to CSV if requested
        if export_csv:
            created_files = self.export_to_csv(output_prefix)
            results['exported_files'] = created_files
        logger.info("ADM log analysis completed successfully")
        return results


def main():
    """Command line interface for the DayZ ADM Log Analyzer."""

    parser = argparse.ArgumentParser(
        description="Analyze DayZ AdminLog (ADM) files for player behavior statistics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --profile my_server
  %(prog)s --adm-file logs/DayZServer_X1_x64_2025-07-29_16-04-37.ADM
  %(prog)s --no-csv --output-prefix "server_analysis"
  %(prog)s --profile my_server --console
        """
    )

    parser.add_argument(
        '--adm-file',
        help='Path to a specific DayZ ADM log file to analyze (overrides default directory scan)'
    )

    parser.add_argument(
        '--no-csv',
        action='store_true',
        help='Skip CSV export (only generate console output)'
    )

    parser.add_argument(
        '--output-prefix',
        default='adm_analysis',
        help='Prefix for output files (default: adm_analysis)'
    )

    # Add standard DayZ tool arguments
    DayZADMAnalyzer.add_standard_arguments(parser)

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.console else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Load configuration
        config = DayZADMAnalyzer.load_config(args.profile)

        # Create analyzer
        analyzer = DayZADMAnalyzer(config)

        # Determine log files to analyze
        if args.adm_file:
            log_files = [args.adm_file]
        else:
            # Use log_dir from analyzer (set by base class)
            log_dir = analyzer.log_dir
            log_pattern = '*.ADM'
            log_files = sorted(Path(log_dir).glob(log_pattern))
            if not log_files:
                raise FileNotFoundError(f"No ADM log files found in directory: {log_dir}")
            log_files = [str(f) for f in log_files]



        # Clear analyzer data structures before aggregation
        analyzer.events.clear()
        analyzer.combat_events.clear()
        analyzer.player_sessions.clear()
        analyzer.current_sessions.clear()

        # Aggregate all log files before running analysis
        for log_file in log_files:
            analyzer.parse_log_file(log_file)

        # Now run analysis on the aggregated data
        results = analyzer.run(
            log_file="multiple files",
            export_csv=not args.no_csv,
            output_prefix=args.output_prefix,
            skip_parse=True
        )


        # Markdown report generation for summary highlights
        player_stats = results['player_statistics']
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = analyzer.output_dir if hasattr(analyzer, 'output_dir') else '.'
        md_report_path = analyzer.resolve_path(f"{output_dir}/{args.output_prefix}_summary_{timestamp}.md")

        md_lines = []
        summary = results['summary']
        md_lines.append(f"**DayZ ADM Log Analysis Summary (Aggregated)**\n")
        md_lines.append(f"- Log File(s): {summary['log_file']}")
        md_lines.append(f"- Analysis Time: {summary['analysis_timestamp']}")
        md_lines.append(f"- Time Range: {summary['analysis_time_range']['start']} to {summary['analysis_time_range']['end']}")
        md_lines.append(f"- Total Events Parsed: {summary['total_events_parsed']:,}")
        md_lines.append(f"- Unique Players: {summary['unique_players']}")
        md_lines.append(f"- Combat Events: {summary['total_combat_events']}")
        
        # Add teleportation event summary
        teleport_events = [e for e in analyzer.events if e.event_type == 'teleported']
        teleported_players = len([p for p in player_stats.get('players', {}) if player_stats['players'][p].get('teleported_events', 0) > 0])
        restricted_violations = len([e for e in teleport_events if e.details and 'RestrictedArea' in (e.details.get('reason', ''))])
        avg_distance = 0
        if teleport_events:
            total_distance = sum([e.details.get('teleport_distance', 0) for e in teleport_events if e.details])
            avg_distance = round(total_distance / len(teleport_events), 2)
        
        md_lines.append(f"- Teleportation Events: {len(teleport_events)}")
        md_lines.append(f"- Teleported Players: {teleported_players}")
        md_lines.append(f"- Restricted Area Violations: {restricted_violations}")
        md_lines.append(f"- Average Teleport Distance: {avg_distance} meters")



        # --- Config-driven special events for Markdown summary ---
        special_events_cfg = (analyzer.config or {}).get('special_events', {})
        special_event_names = [e.get('name') for e in special_events_cfg.get('events', [])] if special_events_cfg.get('enabled', False) else []
        # Count special events globally
        special_event_counts_global = {name: 0 for name in special_event_names}
        for e in analyzer.events:
            if e.event_type in special_event_names:
                special_event_counts_global[e.event_type] += 1

        # Top 10 Most Active Players (by playtime)
        if player_stats.get('players'):
            sorted_players = sorted(
                player_stats['players'].items(),
                key=lambda x: x[1]['total_playtime_hours'],
                reverse=True
            )
            md_lines.append(f"\n**Top 10 Most Active Players (by playtime):**")
            for idx, (player_id, stats) in enumerate(sorted_players[:10], 1):
                md_lines.append(f"* {stats['name']}: {stats['total_playtime_hours']:.1f}h, {stats.get('kills (PvP)', 0)} kills (PvP), {stats.get('deaths', 0)} deaths, {stats.get('kd_ratio (PvP)', 0):.2f} K/D (PvP)")

        # Special event counts
        if special_event_names:
            md_lines.append(f"\n**Special Events:**")
            for name in special_event_names:
                md_lines.append(f"* {name.replace('_', ' ').title()}: {special_event_counts_global[name]} occurrences")

        # Deaths by Bear and Wolf (special events)
        total_bear = sum(stats.get('deaths_by_bear', 0) for stats in player_stats['players'].values())
        total_wolf = sum(stats.get('deaths_by_wolf', 0) for stats in player_stats['players'].values())
        md_lines.append(f"\n**Special Animal Deaths:**")
        md_lines.append(f"* Deaths by Bear: {total_bear}")
        md_lines.append(f"* Deaths by Wolf: {total_wolf}")

        # Top 10 Most Active Builders
        sorted_builders = sorted(
            player_stats['players'].items(),
            key=lambda x: x[1].get('building_actions', 0),
            reverse=True
        )
        md_lines.append(f"\n**Top 10 Most Active Builders:**")
        for idx, (player_id, stats) in enumerate(sorted_builders[:10], 1):
            md_lines.append(f"* {stats['name']}: {stats.get('building_actions', 0)} building actions")

        # Most weapon used (exclude Melee)
        combat_stats = results['combat_statistics']
        if isinstance(combat_stats, dict) and 'weapon_usage' in combat_stats:
            weapon_usage = combat_stats['weapon_usage']
            filtered_weapons = [(w, c) for w, c in weapon_usage.items() if w and 'melee' not in w.lower() and w.lower() != '']
            filtered_weapons.sort(key=lambda x: x[1], reverse=True)
            md_lines.append(f"\n**Most Weapon Used (excluding Melee):**")
            for idx, (weapon, count) in enumerate(filtered_weapons[:5], 1):
                md_lines.append(f"* {weapon}: {count} hits")

        # Top Killer
        if player_stats.get('players'):
            top_killer = max(player_stats['players'].items(), key=lambda x: x[1].get('kills (PvP)', 0), default=None)
            if top_killer and top_killer[1].get('kills (PvP)', 0) > 0:
                md_lines.append(f"\n**Top Killer (PvP):**")
                md_lines.append(f"* {top_killer[1]['name']}: {top_killer[1].get('kills (PvP)', 0)} kills (PvP), {top_killer[1].get('kd_ratio (PvP)', 0):.2f} K/D (PvP)")

        # Top Damage

        if player_stats.get('players'):
            top_damage = max(player_stats['players'].items(), key=lambda x: x[1].get('damage_dealt (PvP)', 0), default=None)
            if top_damage and top_damage[1].get('damage_dealt (PvP)', 0) > 0:
                md_lines.append(f"\n**Top Damage (PvP):**")
                md_lines.append(f"* {top_damage[1]['name']}: {top_damage[1].get('damage_dealt (PvP)', 0):.1f} total damage (PvP)")

        # Top K/D Ratio (PvP)
        if player_stats.get('players'):
            # Consider all players, even those with 0 deaths (K/D = kills / max(deaths, 1))
            kd_players = [(pid, stats) for pid, stats in player_stats['players'].items() if stats.get('kd_ratio (PvP)', 0) > 0]
            if kd_players:
                top_kd = max(kd_players, key=lambda x: x[1].get('kd_ratio (PvP)', 0))
                md_lines.append(f"\n**Top K/D Ratio (PvP):**")
                md_lines.append(f"* {top_kd[1]['name']}: {top_kd[1].get('kd_ratio (PvP)', 0):.2f} K/D (PvP)")

        # Suspicious/Anomalous Events
        anomalies = results.get('anomalies', {})
        if anomalies:
            md_lines.append(f"\n**Suspicious/Anomalous Events:**")
            # Rapid Reconnections
            rapid_reconnections = anomalies.get('rapid_reconnections', [])
            if rapid_reconnections:
                md_lines.append(f"* Rapid Reconnections:")
                for entry in rapid_reconnections:
                    md_lines.append(f"    - {entry['player_name']} ({entry['player_id']}): {entry['rapid_reconnects']} rapid reconnects in {entry['total_sessions']} sessions")
            # High Damage Dealers
            high_damage_dealers = anomalies.get('high_damage_dealers', [])
            if high_damage_dealers:
                md_lines.append(f"* High Damage Dealers:")
                for entry in high_damage_dealers:
                    md_lines.append(f"    - {entry['player_name']} ({entry['player_id']}): {entry['average_damage']:.2f} avg damage over {entry['total_hits']} hits")

        # Write Markdown report
        with open(md_report_path, 'w', encoding='utf-8') as f:
            for line in md_lines:
                f.write(line + '\n')
        print(f"\nMarkdown summary exported to: {md_report_path}") 

        print("\nAnalysis completed successfully!")

        return 0

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        if args.console:
            raise
        return 1


if __name__ == '__main__':
    exit(main())

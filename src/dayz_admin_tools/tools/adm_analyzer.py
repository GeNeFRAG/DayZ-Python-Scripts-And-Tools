"""
DayZ ADM Log Analyzer

This module provides comprehensive analysis of DayZ AdminLog (ADM) files,
extracting player behavior statistics, combat analytics, building activity,
and administrative insights.

Features:
- Player session tracking and statistics
- Combat event analysis with duplicate detection
- Environmental and explosion damage tracking
- Animal death mapping (Bear/Wolf) with special event types
- Building and construction activity monitoring
- Performance optimizations with cached configurations
- Comprehensive data enrichment for analytics
- Ban event verification via Nitrado API integration (targeted checking)

Recent Improvements:
- Added targeted ban event verification to identify false positives
- Only checks ban status for players appearing in ban-related log events
- Distinguishes between verified bans and false positive events
- Fixed functional regressions in environmental/explosion hit events
- Added intelligent duplicate combat event detection
- Performance optimizations with cached special event names
- Enhanced data quality with comprehensive event details
- Backward compatibility maintained while improving accuracy
- Fixed player ID regex patterns to match lowercase hex and hyphens ([A-Fa-f0-9-]+)
- Fixed inconsistent _last_events management with unified MAX_LAST_EVENTS constant
- Converted teleport distance reporting from meters to kilometers for better readability
"""

import argparse
import csv
import logging
import re
from collections import defaultdict, Counter
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from ..base import FileBasedTool
from ..nitrado.api_client import NitradoAPIClient

logger = logging.getLogger(__name__)

# Constants
MAX_LAST_EVENTS = 20  # Maximum number of recent events to keep in memory for analysis


def format_european_number(value, decimal_places=None):
    """
    Format numbers using European conventions:
    - Period (.) as thousand separator  
    - Comma (,) as decimal separator
    """
    if value is None:
        if decimal_places is not None:
            # Return "0,00" format when decimal places are requested
            formatted = f"{0.0:,.{decimal_places}f}"
            return formatted.replace(',', '|TEMP|').replace('.', ',').replace('|TEMP|', '.')
        return "0"
    
    if isinstance(value, (int, float)):
        if decimal_places is not None:
            # Format with specific decimal places AND thousand separators
            formatted = f"{float(value):,.{decimal_places}f}"
        else:
            # Auto-format based on type
            if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
                formatted = f"{int(value):,}"
            else:
                formatted = f"{value:,.2f}"
        
        # Replace comma with temporary placeholder, then dot with comma, then placeholder with dot
        formatted = formatted.replace(',', '|TEMP|').replace('.', ',').replace('|TEMP|', '.')
        return formatted
    
    return str(value)


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
        """Calculate total distance traveled during session, filtering out teleportations."""
        if len(self.positions) < 2:
            return 0.0
        
        total_distance = 0.0
        max_reasonable_speed = DayZADMAnalyzer.MAX_REASONABLE_SPEED_M_PER_MIN  # 30 km/h vehicle speed
        
        for i in range(1, len(self.positions)):
            prev_timestamp = self.positions[i-1][0]
            curr_timestamp = self.positions[i][0]
            prev_pos = self.positions[i-1][1:]  # Skip timestamp
            curr_pos = self.positions[i][1:]    # Skip timestamp
            
            # Calculate 3D distance
            distance = ((curr_pos[0] - prev_pos[0]) ** 2 + 
                       (curr_pos[1] - prev_pos[1]) ** 2 + 
                       (curr_pos[2] - prev_pos[2]) ** 2) ** 0.5
            
            # Calculate time difference in minutes
            time_diff = (curr_timestamp - prev_timestamp).total_seconds() / DayZADMAnalyzer.SECONDS_PER_MINUTE
            
            # Skip if time difference is too small to avoid division by zero
            if time_diff < 0.1:  # Less than 6 seconds
                continue
                
            # Calculate speed (meters per minute)
            speed = distance / time_diff
            
            # Filter out teleportations, deaths, and respawns (unrealistic speeds)
            if speed <= max_reasonable_speed:
                total_distance += distance
            # Optionally log filtered movements for debugging
            # else:
            #     print(f"Filtered teleportation: {distance:.1f}m in {time_diff:.1f}min = {speed:.1f}m/min")
            
        return total_distance


@dataclass
class ParseResult:
    """Result of parsing a single line."""
    event: Optional[PlayerEvent] = None
    combat_events: List['CombatEvent'] = None
    error: Optional[str] = None
    line_number: int = 0
    raw_line: str = ""
    
    def __post_init__(self):
        if self.combat_events is None:
            self.combat_events = []


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


@dataclass
class HandlerResult:
    """Result carrier for event handler functions."""
    event: Optional[PlayerEvent] = None
    combat_events: List[CombatEvent] = None
    handled: bool = True  # True if line was successfully processed, even if no event created
    
    def __post_init__(self):
        if self.combat_events is None:
            self.combat_events = []


class DayZADMParser:
    """
    Parser that yields events from DayZ AdminLog files.
    
    Separates parsing concerns from analysis, providing a clean interface
    for consuming events and collecting parse error statistics.
    
    Features:
    - Comprehensive regex patterns for all DayZ ADM event types
    - Performance optimizations with cached special event names
    - Intelligent duplicate detection for combat events
    - Enhanced data enrichment for environmental and explosion events
    - Animal death mapping with friendly names and special event types
    
    Attributes:
        MELEE_AMMO (set): Class-level constant for melee weapon detection
        _special_event_names (set): Cached special event names for performance
        _recent_combat_events (list): Recent combat events for duplicate detection
    """
    
    # Class-level constants for performance optimization
    MELEE_AMMO = {
        'MeleeFist', 'MeleeAxe', 'MeleeKnife', 'MeleeBat', 'MeleeShovel',
        'MeleeHammer', 'MeleeMachete', 'MeleePipe', 'MeleeCrowbar', 'MeleeSoft'
    }  # Cached set for efficient melee weapon detection
    
    def __init__(self, 
                 config: Optional[Dict[str, Any]] = None, 
                 start_datetime: Optional[datetime] = None, 
                 end_datetime: Optional[datetime] = None):
        """
        Initialize the parser with configuration.
        
        Args:
            config: Optional configuration dictionary
            start_datetime: Optional start date and time filter. If only date is provided, time defaults to 00:00:00.
            end_datetime: Optional end date and time filter. If only date is provided, time defaults to 23:59:59.
        """
        self.config = config or {}
        self.last_timestamp = None  # Track last timestamp for midnight rollover detection
        self._last_events = []  # Track recent events for death stats association
        self.start_datetime = start_datetime  # Start date filter
        self.end_datetime = end_datetime  # End date filter
        
        # Cache special event names to avoid repeated list creation
        special_events_cfg = self.config.get('special_events', {})
        if special_events_cfg.get('enabled', False):
            self._special_event_names = {e.get('name') for e in special_events_cfg.get('events', [])}
        else:
            self._special_event_names = set()
        
        self._setup_patterns()
    
    def _setup_patterns(self):
        """Setup regex patterns for parsing different event types."""
        # Pre-compiled regex patterns for performance using named capture groups
        # Patterns are grouped and commented by event type for clarity
        self.patterns = {
            # --- Connection/Disconnection Events ---
            'connection': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\)\s*is connected'),
            'disconnection': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\)\s*has been disconnected'),
            'banned_connection_attempt': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=Unknown\)\s*has been disconnected'),

            # --- Player State/Status Events ---
            'unconscious': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*is unconscious'),
            'conscious': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*regained consciousness'),
            'suicide': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=(?P<player_id>[A-Fa-f0-9-]+)(?:\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>)?\)\s*committed suicide'),
            'death_stats': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(DEAD\)\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*died\.\s*Stats>\s*Water:\s*(?P<water>[0-9.]+)\s*Energy:\s*(?P<energy>[0-9.]+)\s*Bleed sources:\s*(?P<bleed_sources>\d+)'),
            'bledout': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(DEAD\)\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*bled out'),
            'respawn': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(DEAD\)\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*is choosing to respawn'),
            'emote': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*performed (?P<emote>[^\s]+)(?:\s+with\s+(?P<emote_item>[^\s]+))?'),
            'tripwire_hit': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\[HP:\s*(?P<hp>[0-9.]+)\]\s*hit by\s+TripwireTrap\s+into\s+\((?P<hit_location>-?\d+)\)\s+for\s+(?P<damage>[0-9.]+)\s+damage\s+\(TripWireHit\)'),

            # --- Combat Events ---
            'hit': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<victim_name>[^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=(?P<victim_id>[A-Fa-f0-9-]+)\s*pos=<(?P<victim_x>[0-9.-]+),\s*(?P<victim_y>[0-9.-]+),\s*(?P<victim_z>[0-9.-]+)>\)\s*\[HP:\s*(?P<victim_hp>[0-9.]+)\]\s*hit by Player\s*"(?P<attacker_name>[^"]+?)"\s*\(id=(?P<attacker_id>[A-Fa-f0-9-]+)\s*pos=<(?P<attacker_x>[0-9.-]+),\s*(?P<attacker_y>[0-9.-]+),\s*(?P<attacker_z>[0-9.-]+)>\)\s*into\s*(?P<hit_location>[^(]+)\((?P<hit_location_id>\d+)\)\s*for\s*(?P<damage>[0-9.]+)\s+damage\s*\((?P<ammo>[^)]+)\)(?:\s*with\s+(?P<weapon>[^\s]+)(?:\s+from\s+(?P<distance>[0-9.]+)\s+meters)?)?'),
            'kill': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<victim_name>[^"]+?)"\s*\(DEAD\)\s*\(id=(?P<victim_id>[A-Fa-f0-9-]+)\s*pos=<(?P<victim_x>[0-9.-]+),\s*(?P<victim_y>[0-9.-]+),\s*(?P<victim_z>[0-9.-]+)>\)\s*killed by Player\s*"(?P<attacker_name>[^"]+?)"\s*\(id=(?P<attacker_id>[A-Fa-f0-9-]+)\s*pos=<(?P<attacker_x>[0-9.-]+),\s*(?P<attacker_y>[0-9.-]+),\s*(?P<attacker_z>[0-9.-]+)>\)\s*with\s*(?P<weapon>[^\s]+)\s*from\s*(?P<distance>[0-9.]+)\s+meters'),
            'env_hit': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\[HP:\s*(?P<hp>[0-9.]+)\]\s+hit by\s+(?P<attacker>[^\s]+)\s+with\s+(?P<weapon>[^\s]+)'),
            'env_hit_simple': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\[HP:\s*(?P<hp>[0-9.]+)\]\s*hit by\s+(?P<attacker>[^\s]+)$'),
            'explosion_hit': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\[HP:\s*(?P<hp>[0-9.]+)\]\s+hit by explosion\s+\((?P<explosion_type>[^)]+)\)'),
            'death_player': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(DEAD\)\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s+killed by\s+(?P<killer>[^\s]+)'),
            'death_fall': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(DEAD\)\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\[HP:\s*0\]\s+hit by\s+FallDamageHealth'),
            'combat_log_unconscious': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*is disconnecting while being unconscious'),

            # --- Building/Construction Events ---
            'building': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*(?P<action>Built|Dismantled)\s+(?P<structure>[^\s]+)\s+(?P<on_or_from>on|from)\s+(?P<parent>[^\s]+)\s+with\s+(?P<tool>[^\s]+)$'),
            'mounted': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)Player\s+[^<]*<[^>]*>\s+(?P<action>Mounted)\s+(?P<structure>[^\s]+)\s+on\s+(?P<parent>.+)$'),
            'unmounted': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)Player\s+[^<]*<[^>]*>\s+(?P<action>Unmounted)\s+(?P<structure>[^\s]+)\s+from\s+(?P<parent>.+)$'),
            'raisedflag': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s+has\s+(?P<action>raised)\s+(?P<structure>[^\s]+)\s+on\s+(?P<parent>[^\s]+)\s+at\s+<[0-9.-]+,\s*[0-9.-]+,\s*[0-9.-]+>$'),
            'builtbaseon': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)Built\s+(?P<action>base)\s+on\s+(?P<parent>[^\s]+)\s+with\s+(?P<tool>.+)$'),
            'dismantle': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)(?P<action>Dismantled)\s+(?P<structure>[^\s]+(?: [^\s]+)*)\s+from\s+(?P<parent>[^\s]+)\s+with\s+(?P<tool>.+)$'),
            'repaired': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*(?P<action>repaired)\s+(?P<structure>[^\s]+)\s+with\s+(?P<tool>[^\s]+)$'),
            'packed': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s+packed\s+(?P<structure>.+?)\s+with\s+(?P<tool>[^\s]+)$'),
            'placed': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s+placed\s+(?P<structure>.+)$'),
            'folded': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s+folded\s+(?P<structure>.+)$'),

            # --- Teleportation Events ---
            'teleported': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*was teleported from:\s*<(?P<from_x>[0-9.-]+),\s*(?P<from_y>[0-9.-]+),\s*(?P<from_z>[0-9.-]+)>\s*to:\s*<(?P<to_x>[0-9.-]+),\s*(?P<to_y>[0-9.-]+),\s*(?P<to_z>[0-9.-]+)>\.\s*Reason:\s*(?P<reason>.+)$'),

            # --- Fallback/Player Position ---
            # Match simple position lines that end after the position coordinates
            'player_position': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)\s*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)\s*$'),
            
            # --- Player List Entry (Informational) ---
            # Match player list entries with dead players - these don't add information to kill events
            'player_list_dead': re.compile(r'(?P<time>\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"(?P<player_name>[^"]+?)"\s*\(DEAD\)\s*\(id=(?P<player_id>[A-Fa-f0-9-]+)[\s\)]*pos=<(?P<x>[0-9.-]+),\s*(?P<y>[0-9.-]+),\s*(?P<z>[0-9.-]+)>\)?\s*$')
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
    
    def parse_file(self, log_file: str, max_malformed_samples: int = 10, debug_skipped_file: Optional[str] = None, append_debug: bool = False) -> tuple[List[PlayerEvent], List[CombatEvent], ParseSummary]:
        """
        Parse an ADM log file and yield events.
        
        If start_datetime or end_datetime are set in the parser instance, log entries
        will be filtered by their timestamps.
        
        Args:
            log_file: Path to the ADM log file
            max_malformed_samples: Maximum number of malformed line samples to collect
            debug_skipped_file: Optional path to write all skipped/malformed lines for debugging
            append_debug: If True, append to debug file instead of overwriting
            
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
        
        # Setup debug file for skipped lines if requested
        debug_file = None
        if debug_skipped_file:
            try:
                mode = 'a' if append_debug else 'w'
                debug_file = open(debug_skipped_file, mode, encoding='utf-8')
                if not append_debug:
                    debug_file.write(f"# Debug output for skipped/malformed lines\n")
                    debug_file.write(f"# Generated at: {datetime.now().isoformat()}\n")
                    debug_file.write(f"# Format: [LINE_NUMBER] ORIGINAL_LINE\n\n")
                else:
                    debug_file.write(f"\n# === Parsing file: {log_path} ===\n")
                logger.info(f"Debug skipped lines will be {'appended to' if append_debug else 'written to'}: {debug_skipped_file}")
            except Exception as e:
                logger.warning(f"Could not open debug file '{debug_skipped_file}': {e}")
                debug_file = None
        
        # Extract date from filename for timestamp parsing
        base_date = self._extract_date_from_filename(str(log_path))
        
        # Reset timestamp tracker for new file
        self.last_timestamp = None
        
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_number, line in enumerate(f, 1):
                summary.total_lines += 1
                line = line.strip()
                
                if not line or line.startswith('#'):
                    if debug_file and line:  # Only write non-empty comment lines
                        debug_file.write(f"[{line_number:>6}] COMMENT: {line}\n")
                    continue
                
                parse_result = self._parse_line(line, base_date, line_number)
                
                if parse_result.event:
                    events.append(parse_result.event)
                    summary.parsed_events += 1
                    
                    # Track recent events for death stats association
                    self._last_events.append(parse_result.event)
                    # Keep only last MAX_LAST_EVENTS events to prevent memory bloat
                    if len(self._last_events) > MAX_LAST_EVENTS:
                        self._last_events = self._last_events[-MAX_LAST_EVENTS:]
                    
                    # Update event type counters
                    event_type = parse_result.event.event_type
                    if event_type == 'connection':
                        summary.connections += 1
                    elif event_type == 'disconnection':
                        summary.disconnections += 1
                    elif event_type in ['building', 'mounted', 'unmounted', 'placed', 'folded', 'packed', 'repaired', 'raisedflag', 'builtbaseon', 'dismantle']:
                        summary.building_events += 1
                    elif event_type == 'emote':
                        summary.emotes += 1
                    elif event_type == 'teleported':
                        summary.teleported_events += 1
                    elif event_type in ['bledout', 'death_player', 'death_fall', 'death_by_bear', 'death_by_wolf', 'death_by_explosion', 'death_by_zombie', 'suicide']:
                        summary.deaths += 1
                    
                    # Handle combat events from ParseResult (proper separation of concerns)
                    if parse_result.combat_events:
                        combat_events.extend(parse_result.combat_events)
                        summary.combat_events += len(parse_result.combat_events)
                    
                    # Update timestamps
                    timestamp = parse_result.event.timestamp
                    if summary.start_time is None or timestamp < summary.start_time:
                        summary.start_time = timestamp
                    if summary.end_time is None or timestamp > summary.end_time:
                        summary.end_time = timestamp
                        
                elif parse_result.error:
                    summary.malformed_lines += 1
                    
                    # Write to debug file if enabled
                    if debug_file:
                        debug_file.write(f"[{line_number:>6}] MALFORMED: {line}\n")
                        if parse_result.error:
                            debug_file.write(f"         ERROR: {parse_result.error}\n")
                        debug_file.write("\n")
                    
                    if len(summary.malformed_samples) < max_malformed_samples:
                        sample = f"Line {line_number}: {parse_result.raw_line[:self.LINE_SAMPLE_MAX_LENGTH]}{'...' if len(parse_result.raw_line) > self.LINE_SAMPLE_MAX_LENGTH else ''}"
                        summary.malformed_samples.append(sample)
        
        # Close debug file if it was opened
        if debug_file:
            try:
                debug_file.write(f"\n# End of debug output - Total malformed lines: {summary.malformed_lines}\n")
                debug_file.close()
                logger.info(f"Debug file closed: {debug_skipped_file}")
            except Exception as e:
                logger.warning(f"Error closing debug file: {e}")
        
        logger.info(f"Parsed {summary.parsed_events} events from {summary.total_lines} lines")
        if summary.malformed_lines > 0:
            logger.warning(f"Found {summary.malformed_lines} malformed lines")
            if debug_skipped_file:
                logger.info(f"Malformed lines written to debug file: {debug_skipped_file}")
        
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
        """
        Parse a single log line into a ParseResult.
        
        Lines will be filtered by timestamp if start_datetime or end_datetime are set.
        
        Args:
            line: Raw log line to parse
            base_date: Base date for timestamp calculation
            line_number: Line number for error reporting
            
        Returns:
            ParseResult object containing parsed event and combat events
        """
        logger.debug(f"PARSING LINE {line_number}: {line}")
        
        for event_type, pattern in self.patterns.items():
            try:
                match = pattern.match(line)
                if match:
                    # Extract time and create timestamp for date filtering
                    time_str = self._safe_named_group_access(match, 'time', "00:00:00")
                    log_timestamp = self._create_timestamp(time_str, base_date)
                    
                    # Apply date filters if specified
                    if self.start_datetime and log_timestamp < self.start_datetime:
                        logger.debug(f"Skipping line {line_number}: timestamp {log_timestamp} before start date {self.start_datetime}")
                        continue
                    if self.end_datetime and log_timestamp > self.end_datetime:
                        logger.debug(f"Skipping line {line_number}: timestamp {log_timestamp} after end date {self.end_datetime}")
                        continue
                    logger.debug(f"MATCHED EVENT TYPE: {event_type}")
                    handler_result = self._create_event_from_match(event_type, match, base_date, line)
                    
                    # If not handled, continue to next pattern
                    if not handler_result.handled:
                        continue
                    
                    # Create ParseResult with event and combat_events properly separated
                    return ParseResult(
                        event=handler_result.event,
                        combat_events=handler_result.combat_events,
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
        """
        Safely access regex named group as float with comprehensive error handling.
        
        This method prevents None propagation by ensuring numeric defaults
        are returned when regex groups are missing, None, or invalid.
        
        Args:
            match: Regex match object
            group_name: Name of the regex group to access
            default: Default value to return on error (defaults to 0.0)
            
        Returns:
            Float value from regex group or default value
            
        Error Handling:
        - Missing groups return default
        - None values return default  
        - Invalid conversions return default
        - Prevents None propagation in numeric calculations
        """
        try:
            value = match.group(group_name)
            if value is not None:
                return float(value)
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
        """Create a timestamp from time string and base date, handling midnight rollover correctly."""
        try:
            time_parts = time_str.split(':')
            parsed_time = time(
                hour=int(time_parts[0]),
                minute=int(time_parts[1]),
                second=int(time_parts[2])
            )
            
            # Combine base date with parsed time
            timestamp = datetime.combine(base_date.date(), parsed_time)
            
            # Handle midnight rollover: if current time < last timestamp, add 1 day
            if self.last_timestamp and timestamp < self.last_timestamp:
                timestamp += timedelta(days=1)
                
            # Update last timestamp tracker
            self.last_timestamp = timestamp
                
            return timestamp
        except Exception as e:
            logger.error(f"Error creating timestamp from '{time_str}': {e}")
            # Fallback timestamp
            fallback = base_date.replace(hour=0, minute=0, second=0)
            if self.last_timestamp:
                self.last_timestamp = fallback
            return fallback
    
    def _base_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> Tuple[datetime, str, str, Dict[str, Any]]:
        """Create base event data common to all event types."""
        time_str = self._safe_named_group_access(match, 'time', "00:00:00")
        timestamp = self._create_timestamp(time_str, base_date)
        player_name = self._safe_named_group_access(match, 'player_name', 'Unknown')
        player_id = self._safe_named_group_access(match, 'player_id', 'Unknown')
        details = {'raw_line': raw_line}
        return timestamp, player_name, player_id, details

    def _create_player_event(self, event_type: str, match, base_date: datetime, raw_line: str, 
                           position: Optional[Tuple[float, float, float]] = None,
                           extra_details: Optional[Dict[str, Any]] = None,
                           override_player_id: Optional[str] = None,
                           override_player_name: Optional[str] = None) -> PlayerEvent:
        """
        Factory method to create PlayerEvent instances with common setup.
        
        Args:
            event_type: Type of the event
            match: Regex match object
            base_date: Base date for timestamp creation
            raw_line: Original log line
            position: Optional position tuple (x, y, z)
            extra_details: Optional additional details to merge
            override_player_id: Optional override for player_id
            override_player_name: Optional override for player_name
            
        Returns:
            PlayerEvent instance with all common setup applied
        """
        timestamp, player_name, player_id, details = self._base_event(event_type, match, base_date, raw_line)
        
        # Apply overrides if provided
        if override_player_id is not None:
            player_id = override_player_id
        if override_player_name is not None:
            player_name = override_player_name
        
        # Merge extra details if provided
        if extra_details:
            details.update(extra_details)
        
        return PlayerEvent(
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            event_type=event_type,
            position=position,
            details=details
        )

    def _dispatch_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Dispatch event parsing to appropriate handler based on event type."""
        # Map event types to their handlers
        handlers = {
            'connection': self._handle_connection_event,
            'disconnection': self._handle_disconnection_event,
            'banned_connection_attempt': self._handle_banned_connection_event,
            'player_position': self._handle_position_event,
            'player_list_dead': self._handle_player_list_dead_event,
            'unconscious': self._handle_state_event,
            'conscious': self._handle_state_event,
            'suicide': self._handle_state_event,
            'death_stats': self._handle_death_stats_event,
            'bledout': self._handle_state_event,
            'respawn': self._handle_state_event,
            'emote': self._handle_state_event,
            'tripwire_hit': self._handle_state_event,
            'hit': self._handle_hit_event,
            'kill': self._handle_kill_event,
            'env_hit': self._handle_env_hit_event,
            'env_hit_simple': self._handle_env_hit_simple_event,
            'explosion_hit': self._handle_explosion_event,
            'death_player': self._handle_death_other_event,
            'death_fall': self._handle_death_other_event,
            'combat_log_unconscious': self._handle_combat_log_event,
            'building': self._handle_building_event,
            'mounted': self._handle_building_event,
            'unmounted': self._handle_building_event,
            'raisedflag': self._handle_building_event,
            'builtbaseon': self._handle_building_event,
            'dismantle': self._handle_building_event,
            'repaired': self._handle_building_event,
            'packed': self._handle_packed_event,
            'placed': self._handle_placed_event,
            'folded': self._handle_folded_event,
            'teleported': self._handle_teleported_event,
        }
        
        # Check for special event types from cached set
        if event_type in self._special_event_names:
            return self._handle_special_event(event_type, match, base_date, raw_line)
        
        # Dispatch to specific handler or fallback to generic
        handler = handlers.get(event_type, self._handle_generic_event)
        return handler(event_type, match, base_date, raw_line)

    def _handle_connection_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle connection and disconnection events."""
        event = self._create_player_event(event_type, match, base_date, raw_line)
        return HandlerResult(event=event)

    def _handle_disconnection_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle disconnection events."""
        return self._handle_connection_event(event_type, match, base_date, raw_line)

    def _handle_banned_connection_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle banned player connection attempts (id=Unknown disconnections)."""
        extra_details = {
            'reason': 'banned_player_attempt',
            'banned': True,
            'administrative_action': True
        }
        
        event = self._create_player_event(
            event_type, match, base_date, raw_line,
            override_player_id="Unknown",
            extra_details=extra_details
        )
        return HandlerResult(event=event)

    def _handle_position_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle player position events."""
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        event = self._create_player_event(event_type, match, base_date, raw_line, position=position)
        return HandlerResult(event=event)

    def _handle_player_list_dead_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle player list entries for dead players - these are informational only."""
        # These events are just player list snapshots showing dead players
        # They don't provide new information beyond the original kill/suicide events
        # We track them but don't create events to avoid duplication
        logger.debug(f"Player list dead entry (informational): {raw_line}")
        return HandlerResult(event=None)  # No event created

    def _handle_state_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle state events (unconscious, conscious, suicide, emote)."""
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        extra_details = {}
        
        # Handle emote-specific details
        if event_type == 'emote':
            emote = self._safe_named_group_access(match, 'emote', '')
            emote_item = self._safe_named_group_access(match, 'emote_item', '')
            extra_details.update({
                'emote': emote,
                'emote_item': emote_item
            })
        
        # Handle tripwire hit specific details
        elif event_type == 'tripwire_hit':
            hp = self._safe_named_group_float(match, 'hp', 0.0)
            hit_location = self._safe_named_group_access(match, 'hit_location', '')
            damage = self._safe_named_group_float(match, 'damage', 0.0)
            extra_details.update({
                'hp': hp,
                'hit_location': hit_location,
                'damage': damage,
                'attacker': 'TripwireTrap'
            })
        
        event = self._create_player_event(
            event_type, match, base_date, raw_line,
            position=position,
            extra_details=extra_details if extra_details else None
        )
        return HandlerResult(event=event)

    def _handle_death_stats_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle death statistics events that follow suicide events."""
        timestamp, player_name, player_id, details = self._base_event(event_type, match, base_date, raw_line)
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        
        # Extract death statistics data
        water = self._safe_named_group_float(match, 'water', 0.0)
        energy = self._safe_named_group_float(match, 'energy', 0.0) 
        bleed_sources = int(self._safe_named_group_float(match, 'bleed_sources', 0.0))
        
        details.update({
            'water': water,
            'energy': energy,
            'bleed_sources': bleed_sources
        })
        
        # Look for a corresponding suicide event within the last few events
        # This will associate the death stats with the suicide event
        if hasattr(self, '_last_events') and self._last_events:
            for recent_event in reversed(self._last_events[-MAX_LAST_EVENTS:]):  # Check recent events
                if (recent_event.player_id == player_id and 
                    recent_event.event_type == 'suicide' and
                    abs((timestamp - recent_event.timestamp).total_seconds()) < 60):  # Within 1 minute
                    # Add death stats to the suicide event details
                    recent_event.details.update({
                        'death_stats': {
                            'water': water,
                            'energy': energy,
                            'bleed_sources': bleed_sources
                        }
                    })
                    break
        
        # Create the death stats event (for tracking purposes)
        event = PlayerEvent(
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            event_type=event_type,
            position=position,
            details=details
        )
        return HandlerResult(event=event)

    def _handle_hit_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """
        Handle hit events with comprehensive combat analytics and duplicate detection.
        
        This method processes hit events and creates combat analytics with
        intelligent duplicate detection to prevent double-counting when
        both hit and kill events occur for the same engagement.
        
        Args:
            event_type: The type of event ('hit')
            match: Regex match object containing event data
            base_date: Base date for timestamp calculation
            raw_line: Original log line for debugging
            
        Returns:
            HandlerResult containing both the base hit event and any combat events
            
        Features:
        - Ensures numeric defaults don't propagate None values
        - Creates comprehensive CombatEvent analytics
        - Implements duplicate detection within 1-second windows
        - Tracks damage, health, distance, and weapon details
        """
        timestamp, _, _, details = self._base_event(event_type, match, base_date, raw_line)
        
        # Extract hit event data
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
            if any(melee in ammo for melee in self.MELEE_AMMO):
                weapon = ammo
        
        # Check if this is a kill (victim has DEAD in original line or HP is 0)
        is_kill = victim_hp == 0.0 or "(DEAD)" in raw_line
        
        combat_events = []
        
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
                distance=distance or 0.0,  # ensure float
                attacker_pos=attacker_pos,
                victim_pos=victim_pos,
                kill=is_kill
            )
            
            combat_events.append(combat_event)
            
            # Track recent combat events to help avoid duplicates in kill events
            if not hasattr(self, '_recent_combat_events'):
                self._recent_combat_events = []
            self._recent_combat_events.append(combat_event)
            # Keep only recent events to prevent memory bloat
            if len(self._recent_combat_events) > self.MAX_RECENT_COMBAT_EVENTS:
                self._recent_combat_events = self._recent_combat_events[-self.TRIMMED_RECENT_EVENTS_SIZE:]
        
        event = PlayerEvent(
            timestamp=timestamp,
            player_name=victim_name,
            player_id=victim_id,
            event_type=event_type,
            position=victim_pos,
            details=details
        )
        
        return HandlerResult(event=event, combat_events=combat_events)

    def _handle_kill_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """
        Handle kill events with intelligent duplicate detection.
        
        This method processes kill events and creates combat events only when
        there isn't a recent corresponding hit event, preventing duplicates
        while ensuring standalone kills are captured for PvP analytics.
        
        Args:
            event_type: The type of event ('kill')
            match: Regex match object containing event data
            base_date: Base date for timestamp calculation
            raw_line: Original log line for debugging
            
        Returns:
            HandlerResult containing the event and combat events
            
        Features:
        - Duplicate detection within 1-second window
        - Comprehensive combat event creation for standalone kills
        - Memory-efficient recent event tracking
        - Backward compatibility with existing analytics
        """
        timestamp, _, _, details = self._base_event(event_type, match, base_date, raw_line)
        v_name = self._safe_named_group_access(match, 'victim_name')
        v_id = self._safe_named_group_access(match, 'victim_id')
        v_pos = self._safe_position_extract_named(match, 'victim_x', 'victim_y', 'victim_z')
        a_name = self._safe_named_group_access(match, 'attacker_name')
        a_id = self._safe_named_group_access(match, 'attacker_id')
        a_pos = self._safe_position_extract_named(match, 'attacker_x', 'attacker_y', 'attacker_z')
        weapon = self._safe_named_group_access(match, 'weapon', '')
        dist = self._safe_named_group_float(match, 'distance')

        # Check if we already have a recent combat event for this kill
        # Kill events typically come after hit events, so we should avoid duplicates
        recent_combat_event = None
        if hasattr(self, '_recent_combat_events'):
            # Look for a recent combat event with the same participants and timestamp
            for ce in reversed(self._recent_combat_events[-5:]):  # Check last 5 events
                if (ce.attacker_name == a_name and ce.victim_name == v_name and 
                    abs((ce.timestamp - timestamp).total_seconds()) <= 1.0):  # Within 1 second
                    recent_combat_event = ce
                    break

        combat_events = []
        
        # Only create a combat event if we don't have a recent one (standalone kill)
        if not recent_combat_event:
            ce = CombatEvent(
                timestamp=timestamp,
                attacker_name=a_name, attacker_id=a_id,
                victim_name=v_name, victim_id=v_id,
                weapon=weapon,
                damage=0.0,              # Kill events don't have damage info
                hit_location="",
                distance=dist or 0.0,
                attacker_pos=a_pos, victim_pos=v_pos,
                kill=True
            )
            combat_events.append(ce)
            # Track recent combat events to avoid duplicates
            if not hasattr(self, '_recent_combat_events'):
                self._recent_combat_events = []
            self._recent_combat_events.append(ce)
            # Keep only recent events to prevent memory bloat
            if len(self._recent_combat_events) > self.MAX_RECENT_COMBAT_EVENTS:
                self._recent_combat_events = self._recent_combat_events[-self.TRIMMED_RECENT_EVENTS_SIZE:]

        event = PlayerEvent(
            timestamp=timestamp,
            player_name=v_name,
            player_id=v_id,
            event_type=event_type,
            position=v_pos,
            details={
                **details,
                'attacker_name': a_name,
                'attacker_id': a_id,
                'attacker_pos': a_pos,
                'weapon': weapon,
                'distance': dist,
                'kill': True
            }
        )

        return HandlerResult(event, combat_events)

    def _handle_env_hit_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """
        Handle environmental hit events with comprehensive data enrichment.
        
        This method processes environmental damage events (e.g., fall damage,
        structure damage) and enriches them with attacker, weapon, and health
        information to maintain consistency with combat analytics.
        
        Args:
            event_type: The type of event ('env_hit')
            match: Regex match object containing event data
            base_date: Base date for timestamp calculation
            raw_line: Original log line for debugging
            
        Returns:
            HandlerResult containing the enriched event
            
        Enriched Details:
        - victim_hp: Player health after hit
        - attacker_name: Environmental damage source
        - weapon: Weapon or damage type
        - Standardized damage tracking fields
        """
        timestamp, player_name, player_id, details = self._base_event(event_type, match, base_date, raw_line)
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        hp = self._safe_named_group_float(match, 'hp')
        attacker = self._safe_named_group_access(match, 'attacker', '')
        weapon = self._safe_named_group_access(match, 'weapon', '')
        details.update({
            'victim_hp': hp,
            'attacker_name': attacker,
            'attacker_id': None,
            'attacker_pos': None,
            'hit_location': None,
            'damage': None,
            'ammo': None,
            'weapon': weapon,
            'distance': None,
        })
        
        event = PlayerEvent(
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            event_type=event_type,
            position=position,
            details=details
        )
        return HandlerResult(event=event)

    def _handle_env_hit_simple_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle simple environmental hit events."""
        timestamp, player_name, player_id, details = self._base_event(event_type, match, base_date, raw_line)
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        hp = self._safe_named_group_float(match, 'hp')
        attacker = self._safe_named_group_access(match, 'attacker', '')
        details.update({
            'victim_hp': hp,
            'attacker_name': attacker,
            'attacker_id': None,
            'attacker_pos': None,
            'hit_location': None,
            'damage': None,
            'ammo': None,
            'weapon': attacker,  # in simple form weapon == attacker token
            'distance': None,
        })
        
        event = PlayerEvent(
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            event_type=event_type,
            position=position,
            details=details
        )
        return HandlerResult(event=event)

    def _handle_explosion_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """
        Handle explosion hit events with comprehensive damage tracking.
        
        This method processes explosion damage events and enriches them with
        attacker information, weapon details, and health tracking to provide
        complete combat analytics for explosive encounters.
        
        Args:
            event_type: The type of event ('explosion')
            match: Regex match object containing event data
            base_date: Base date for timestamp calculation
            raw_line: Original log line for debugging
            
        Returns:
            HandlerResult containing the enriched explosion event
            
        Enriched Details:
        - victim_hp: Player health after explosion
        - attacker_name: Source of explosive damage
        - weapon: Explosive weapon type
        - Full damage tracking for analytics
        """
        timestamp, player_name, player_id, details = self._base_event(event_type, match, base_date, raw_line)
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        hp = self._safe_named_group_float(match, 'hp')
        explosion_type = self._safe_named_group_access(match, 'explosion_type', 'Explosion')
        details.update({
            'victim_hp': hp,
            'attacker_name': 'explosion',
            'attacker_id': None,
            'attacker_pos': None,
            'hit_location': None,
            'damage': None,
            'ammo': None,
            'weapon': explosion_type,
            'distance': None,
        })
        
        event = PlayerEvent(
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            event_type=event_type,
            position=position,
            details=details
        )
        return HandlerResult(event=event)

    def _handle_death_other_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """
        Handle player death events by other causes including animal deaths and environmental fatalities.
        
        This method processes player deaths caused by non-player entities and categorizes them appropriately,
        with special handling for animal deaths that require attacker mapping
        and classification as special events.
        
        Args:
            event_type: The type of event ('death_player')
            match: Regex match object containing event data
            base_date: Base date for timestamp calculation
            raw_line: Original log line for debugging
            
        Returns:
            HandlerResult containing the processed death event
            
        Processing Logic:
        - Maps animal classnames to readable names
        - Identifies deaths as 'special' events when needed
        - Tracks attacker information for animal kills
        - Maintains consistent death tracking format
        """
        timestamp, player_name, player_id, details = self._base_event(event_type, match, base_date, raw_line)
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        
        # Handle fall damage deaths differently
        if event_type == 'death_fall':
            details.update({
                'attacker_name': 'Fall Damage',
                'attacker_id': None,
                'attacker_pos': None,
                'weapon': 'FallDamageHealth',
                'distance': None,
                'kill': True,
                'killer': 'FallDamageHealth'
            })
            ev_type = event_type
        else:
            # Death by specific cause (other deaths)
            killer = self._safe_named_group_access(match, 'killer', 'Unknown')
            ev_type = event_type
            animal_map = {
                'Animal_UrsusArctos': ('Bear', 'death_by_bear'),
                'Animal_CanisLupus_Grey': ('Wolf', 'death_by_wolf'),
                'Animal_CanisLupus_White': ('Wolf', 'death_by_wolf'),
            }
            
            # Check for explosion deaths (grenades, mines, etc.)
            explosion_keywords = ['6-M7', 'Claymore', 'M18', 'RGD', 'M67', 'Mine', 'Grenade', 'Explosion']
            is_explosion = any(keyword in killer for keyword in explosion_keywords)
            
            # Check for zombie deaths
            is_zombie = killer.startswith('Zmb')
            
            if killer in animal_map:
                friendly, ev_type = animal_map[killer]
                details.update({
                    'attacker_name': friendly,
                    'attacker_id': None,
                    'attacker_pos': None,
                    'weapon': None,
                    'distance': None,
                    'kill': True,
                    'special_event': ev_type,
                })
            elif is_explosion:
                ev_type = 'death_by_explosion'
                details.update({
                    'attacker_name': killer,
                    'attacker_id': None,
                    'attacker_pos': None,
                    'weapon': killer,
                    'distance': None,
                    'kill': True,
                    'special_event': ev_type,
                })
            elif is_zombie:
                ev_type = 'death_by_zombie'
                details.update({
                    'attacker_name': killer,
                    'attacker_id': None,
                    'attacker_pos': None,
                    'weapon': None,
                    'distance': None,
                    'kill': True,
                    'special_event': ev_type,
                })
            else:
                details.update({
                    'attacker_name': killer,
                    'attacker_id': None,
                    'attacker_pos': None,
                    'weapon': None,
                    'distance': None,
                    'kill': True,
                })
            details['killer'] = killer
        
        event = PlayerEvent(
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            event_type=ev_type,
            position=position,
            details=details
        )
        return HandlerResult(event=event)

    def _handle_combat_log_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """
        Handle combat logging events where players disconnect while unconscious.
        
        This method tracks instances of potential combat logging where players
        disconnect from the server while in an unconscious state, which may
        indicate an attempt to avoid consequences of PvP combat.
        
        Args:
            event_type: The type of event ('combat_log_unconscious')
            match: Regex match object containing event data
            base_date: Base date for timestamp calculation
            raw_line: Original log line for debugging
            
        Returns:
            HandlerResult containing the processed combat log event
        """
        timestamp, player_name, player_id, details = self._base_event(event_type, match, base_date, raw_line)
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        
        # Mark as combat event for tracking
        details.update({
            'reason': 'disconnect_while_unconscious',
            'combat_logging': True
        })
        
        event = PlayerEvent(
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            event_type=event_type,
            position=position,
            details=details
        )
        return HandlerResult(event=event)

    def _handle_building_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle building/construction events."""
        timestamp, player_name, player_id, details = self._base_event(event_type, match, base_date, raw_line)
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        
        action = self._safe_named_group_access(match, 'action', '')
        structure = self._safe_named_group_access(match, 'structure', '')
        tool = self._safe_named_group_access(match, 'tool', '')
        parent = self._safe_named_group_access(match, 'parent', '')
        
        # Special handling for builtbaseon event type
        if event_type == 'builtbaseon':
            action = 'Built base on'
            structure = 'base'
            
        details.update({
            'action': action,
            'structure': structure,
            'tool': tool,
            'parent': parent
        })
        
        event = PlayerEvent(
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            event_type=event_type,
            position=position,
            details=details
        )
        return HandlerResult(event=event)

    def _handle_packed_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle packed events."""
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        
        structure = self._safe_named_group_access(match, 'structure', '')
        tool = self._safe_named_group_access(match, 'tool', '')
        extra_details = {
            'action': event_type,
            'structure': structure,
            'tool': tool
        }
        
        event = self._create_player_event(
            event_type, match, base_date, raw_line,
            position=position,
            extra_details=extra_details
        )
        return HandlerResult(event=event)

    def _handle_placed_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle placed events."""
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        
        structure = self._safe_named_group_access(match, 'structure', '')
        extra_details = {
            'action': event_type,
            'structure': structure,
            'tool': ''
        }
        
        event = self._create_player_event(
            event_type, match, base_date, raw_line,
            position=position,
            extra_details=extra_details
        )
        return HandlerResult(event=event)

    def _handle_folded_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle folded events."""
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        
        structure = self._safe_named_group_access(match, 'structure', '')
        extra_details = {
            'action': event_type,
            'structure': structure,
            'tool': ''
        }
        
        event = self._create_player_event(
            event_type, match, base_date, raw_line,
            position=position,
            extra_details=extra_details
        )
        return HandlerResult(event=event)

    def _handle_teleported_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle teleportation events."""
        timestamp, player_name, player_id, details = self._base_event(event_type, match, base_date, raw_line)
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
        
        event = PlayerEvent(
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            event_type=event_type,
            position=position,
            details=details
        )
        return HandlerResult(event=event)

    def _handle_special_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle config-driven special events."""
        timestamp, player_name, player_id, details = self._base_event(event_type, match, base_date, raw_line)
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        
        event = PlayerEvent(
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            event_type=event_type,
            position=position,
            details=details
        )
        return HandlerResult(event=event)

    def _handle_generic_event(self, event_type: str, match, base_date: datetime, raw_line: str) -> HandlerResult:
        """Handle generic/fallback events."""
        timestamp, player_name, player_id, details = self._base_event(event_type, match, base_date, raw_line)
        position = self._safe_position_extract_named(match, 'x', 'y', 'z')
        
        event = PlayerEvent(
            timestamp=timestamp,
            player_name=player_name,
            player_id=player_id,
            event_type=event_type,
            position=position,
            details=details
        )
        return HandlerResult(event=event)
    
    def _create_event_from_match(self, event_type: str, match, base_date: datetime, line: str) -> HandlerResult:
        """Create a HandlerResult from a regex match - includes combat event creation."""
        try:
            # Dispatch to handler-based system
            result = self._dispatch_event(event_type, match, base_date, line)
            return result
        except Exception as e:
            logger.error(f"Error creating event from match for type {event_type}: {e}")
            return HandlerResult()


class DayZADMAnalyzer(FileBasedTool):
    """
    Analyzes DayZ AdminLog (ADM) files to extract player behavior statistics.
    
    This tool provides comprehensive analytics including:
    - Player session statistics with duration and distance tracking
    - Combat analytics with duplicate detection and comprehensive event data
    - Building/construction activity monitoring
    - Movement and positioning analysis
    - Administrative insights and anomaly detection
    - Environmental and explosion damage tracking
    - Animal death analysis with special event mapping
    
    Features:
    - Intelligent duplicate combat event detection
    - Performance optimizations with cached configurations
    - Enhanced data enrichment for all event types
    - Comprehensive CSV export capabilities
    - Markdown summary generation
    - Backward compatibility with existing analytics
    
    Recent Improvements:
    - Fixed environmental/explosion hits to include attacker/weapon details
    - Added animal death mapping (Bear/Wolf) with special event types
    - Implemented intelligent duplicate detection for combat events
    - Performance optimizations with cached special event names
    - Enhanced kill event tracking for comprehensive PvP analytics
    """
    
    # Time and duration constants
    ENGAGEMENT_TIMEOUT_SECONDS = 60
    DUPLICATE_EVENT_WINDOW_SECONDS = 60
    SECONDS_PER_MINUTE = 60.0
    SECONDS_PER_HOUR = 3600
    
    # Collection size limits
    MAX_RECENT_COMBAT_EVENTS = 100
    TRIMMED_RECENT_EVENTS_SIZE = 50
    DEFAULT_MAX_MALFORMED_SAMPLES = 10
    
    # Analysis constants
    COMBAT_GRID_SIZE_METERS = 500
    TOP_RESULTS_LIMIT = 10
    METERS_PER_KILOMETER = 1000
    LINE_SAMPLE_MAX_LENGTH = 100
    PERCENTAGE_MULTIPLIER = 100
    
    # Speed thresholds
    MAX_REASONABLE_SPEED_M_PER_MIN = 500.0  # 30 km/h vehicle speed
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the ADM analyzer."""
        super().__init__(config)
        self.initialize_directories()

        # Data storage (must be initialized for all use cases)
        self.events: List[PlayerEvent] = []
        self.combat_events: List[CombatEvent] = []
        self.player_sessions: Dict[str, List[PlayerSession]] = defaultdict(list)
        self.current_sessions: Dict[str, PlayerSession] = {}
        
        # Track recent events for death stats association
        self._last_events: List[PlayerEvent] = []

        # Cached derived maps for performance optimization
        self._events_by_player: Optional[Dict[str, List[PlayerEvent]]] = None
        self._combat_events_by_attacker: Optional[Dict[str, List[CombatEvent]]] = None
        
        # Cache special event names to avoid repeated list creation
        special_events_cfg = self.config.get('special_events', {})
        if special_events_cfg.get('enabled', False):
            self._special_event_names = {e.get('name') for e in special_events_cfg.get('events', [])}
        else:
            self._special_event_names = set()
        self._combat_events_by_victim: Optional[Dict[str, List[CombatEvent]]] = None
        self._player_id_to_name: Optional[Dict[str, str]] = None
        self._cache_dirty: bool = True
        
        # Parser for handling log file parsing
        self.parser = DayZADMParser(config)
        
        # Parse error tracking
        self.parse_summary: Optional[ParseSummary] = None
        
        # Initialize Nitrado API client for ban checking (optional)
        self.nitrado_client: Optional[NitradoAPIClient] = None
        
        # Try to initialize Nitrado client if configuration is available
        if self.config and self.config.get('api_token') and self.config.get('service_id'):
            try:
                self.nitrado_client = NitradoAPIClient(config)
                logger.info("Nitrado API client initialized for ban checking")
            except Exception as e:
                logger.warning(f"Failed to initialize Nitrado API client: {e}")
                self.nitrado_client = None
        
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
        
    def _invalidate_cache(self):
        """Invalidate cached derived maps when data changes."""
        self._events_by_player = None
        self._combat_events_by_attacker = None
        self._combat_events_by_victim = None
        self._player_id_to_name = None
        self._cache_dirty = True
    
    def _get_ban_status(self, player_identifier: str) -> Optional[bool]:
        """
        Check if a player is currently banned using the Nitrado API client.
        
        Args:
            player_identifier: Player ID, Steam ID, or name to check
            
        Returns:
            True if banned, False if not banned, None if unable to check
        """
        if not self.nitrado_client:
            return None
            
        try:
            return self.nitrado_client.is_player_banned(player_identifier)
        except Exception as e:
            logger.warning(f"Failed to check ban status for player '{player_identifier}': {e}")
            return None
    
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
        
    def parse_log_file(self, log_file: str, debug_skipped_file: Optional[str] = None, append_debug: bool = False, start_datetime: Optional[datetime] = None, end_datetime: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Parse a DayZ ADM log file using the decoupled parser.
        
        Args:
            log_file: Path to the ADM log file
            debug_skipped_file: Optional path to write skipped/malformed lines for debugging
            append_debug: If True, append to debug file instead of overwriting
            start_datetime: Optional start date and time filter. If only date is provided, time defaults to 00:00:00.
            end_datetime: Optional end date and time filter. If only date is provided, time defaults to 23:59:59.
            
        Returns:
            Dictionary containing parsing results and statistics
        """
        log_path = self.resolve_path(log_file)
        
        # Check if file date is within the specified range
        if start_datetime or end_datetime:
            file_date = self._extract_date_from_filename(str(log_path))
            
            if start_datetime and file_date < start_datetime.replace(hour=0, minute=0, second=0, microsecond=0):
                logger.info(f"Skipping log file {log_path}: before start date {start_datetime}")
                return {
                    'total_lines': 0,
                    'parsed_events': 0,
                    'malformed_lines': 0,
                    'connections': 0,
                    'disconnections': 0,
                    'combat_events': 0,
                    'deaths': 0,
                    'building_events': 0,
                    'emotes': 0,
                    'teleported_events': 0
                }
                
            if end_datetime and file_date > end_datetime.replace(hour=23, minute=59, second=59, microsecond=999999):
                logger.info(f"Skipping log file {log_path}: after end date {end_datetime}")
                return {
                    'total_lines': 0,
                    'parsed_events': 0,
                    'malformed_lines': 0,
                    'connections': 0,
                    'disconnections': 0,
                    'combat_events': 0,
                    'deaths': 0,
                    'building_events': 0,
                    'emotes': 0,
                    'teleported_events': 0
                }
        
        logger.info(f"Parsing ADM log file: {log_path}")
        
        # Update parser date filters
        self.parser.start_datetime = start_datetime
        self.parser.end_datetime = end_datetime
        
        # Use the decoupled parser to get events and error statistics
        events, combat_events, parse_summary = self.parser.parse_file(log_path, debug_skipped_file=debug_skipped_file, append_debug=append_debug)
        
        # Store the parse summary for error reporting
        self.parse_summary = parse_summary
        
        # Process events through the analyzer
        for event in events:
            self.events.append(event)
            
            # Track recent events for death stats association
            self._last_events.append(event)
            # Keep only last MAX_LAST_EVENTS events to prevent memory bloat
            if len(self._last_events) > MAX_LAST_EVENTS:
                self._last_events = self._last_events[-MAX_LAST_EVENTS:]
            
            # Also update parser's _last_events for real-time association
            self.parser._last_events = self._last_events
            
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
            error_rate = (self.parse_summary.malformed_lines / self.parse_summary.total_lines) * self.PERCENTAGE_MULTIPLIER
        
        return {
            'malformed_lines': self.parse_summary.malformed_lines,
            'malformed_samples': self.parse_summary.malformed_samples,
            'error_rate': error_rate,
            'total_lines': self.parse_summary.total_lines,
            'parsed_events': self.parse_summary.parsed_events
        }
        
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
    
    def _count_unique_kills(self, combat_events: List) -> int:
        """
        Count unique kills by grouping rapid-fire kills to the same victim.
        
        This prevents counting multiple rapid-fire hits to the same victim
        as separate kills by using a more sophisticated approach that looks
        for distinct kill engagements separated by reasonable time gaps.
        
        Args:
            combat_events: List of combat events where this player was the attacker
            
        Returns:
            Number of unique kills (unique victim engagements)
        """
        kill_events = [e for e in combat_events if e.kill]
        if not kill_events:
            return 0
        
        # Sort by timestamp to process in chronological order
        kill_events.sort(key=lambda x: x.timestamp)
        
        # Track unique kill engagements as (victim_id, engagement_start_time)
        unique_kill_engagements = []
        
        for event in kill_events:
            victim_id = event.victim_id
            current_time = event.timestamp
            
            # Check if this is part of an existing engagement (within 60 seconds of a previous kill of same victim)
            is_new_engagement = True
            
            for prev_victim_id, prev_time in unique_kill_engagements:
                if prev_victim_id == victim_id:
                    time_diff = (current_time - prev_time).total_seconds()
                    if time_diff <= self.ENGAGEMENT_TIMEOUT_SECONDS:  # Same engagement
                        is_new_engagement = False
                        break
            
            if is_new_engagement:
                unique_kill_engagements.append((victim_id, current_time))
        
        return len(unique_kill_engagements)
    
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
            
            # Count all deaths for reporting (includes all death types)
            deaths = len([e for e in player_events if e.event_type in ['bledout', 'death_player', 'death_fall', 'death_by_bear', 'death_by_wolf', 'death_by_explosion', 'death_by_zombie', 'suicide']])
            # Count only deaths caused by another player for K/D
            deaths_by_player = len([e for e in player_combat_as_victim if e.kill])
            suicides = len([e for e in player_events if e.event_type == 'suicide'])
            emotes = len([e for e in player_events if e.event_type == 'emote'])
            tripwire_hits = len([e for e in player_events if e.event_type == 'tripwire_hit'])
            combat_logs = len([e for e in player_events if e.event_type == 'combat_log_unconscious'])
            building_actions = len([e for e in player_events if e.event_type in ('building', 'mounted', 'unmounted', 'raisedflag', 'builtbaseon', 'dismantle', 'repaired', 'placed', 'folded', 'packed')])
            teleported_events = len([e for e in player_events if e.event_type == 'teleported'])
            deaths_by_bear = len([e for e in player_events if e.event_type == 'death_by_bear'])
            deaths_by_wolf = len([e for e in player_events if e.event_type == 'death_by_wolf'])
            deaths_by_fall = len([e for e in player_events if e.event_type == 'death_fall'])
            deaths_by_explosion = len([e for e in player_events if e.event_type == 'death_by_explosion'])
            deaths_by_zombie = len([e for e in player_events if e.event_type == 'death_by_zombie'])
            
            # PvP-only combat statistics using cached lookups
            player_combat_as_attacker = self.get_combat_events_by_attacker(player_id)
            
            # Count unique kills by grouping rapid-fire kills to the same victim
            kills_pvp = self._count_unique_kills(player_combat_as_attacker)
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
                'total_playtime_hours': total_playtime / self.SECONDS_PER_HOUR,
                'avg_session_time_minutes': (total_playtime / len(sessions) / self.SECONDS_PER_MINUTE) if sessions else 0,
                'total_distance_traveled': total_distance,
                'deaths': deaths,
                'suicides': suicides,
                'kills (PvP)': kills_pvp,
                'kd_ratio (PvP)': kills_pvp / max(deaths_by_player, 1),
                'hits_dealt (PvP)': hits_dealt_pvp,
                'hits_taken (PvP)': hits_taken_pvp,
                'damage_dealt (PvP)': damage_dealt_pvp,
                'damage_taken (PvP)': damage_taken_pvp,
                'accuracy (PvP)': (kills_pvp / max(hits_dealt_pvp, 1)) * self.PERCENTAGE_MULTIPLIER if hits_dealt_pvp > 0 else 0,
                'emotes': emotes,
                'tripwire_hits': tripwire_hits,
                'combat_logs': combat_logs,
                'building_actions': building_actions,
                'teleported_events': teleported_events,
                'avg_damage_per_hit (PvP)': damage_dealt_pvp / max(hits_dealt_pvp, 1) if hits_dealt_pvp > 0 else 0,
                'deaths_by_bear': deaths_by_bear,
                'deaths_by_wolf': deaths_by_wolf,
                'deaths_by_fall': deaths_by_fall,
                'deaths_by_explosion': deaths_by_explosion,
                'deaths_by_zombie': deaths_by_zombie
            }
        
        return stats
    
    def get_banned_players_summary(self) -> Dict[str, Any]:
        """
        Verify ban status for players who appear in ban-related events in the logs.
        This helps identify false positives in ban-related log events.
        
        Returns:
            Dictionary with banned player verification results
        """
        if not self.nitrado_client:
            return {
                'error': 'Nitrado API not available - configure api_token and service_id',
                'banned_players': [],
                'total_banned_in_logs': 0,
                'ban_check_available': False
            }
        
        # Find players who appear in ban-related events
        ban_event_players = set()
        
        # Look for banned connection attempts
        for event in self.events:
            if event.event_type == 'banned_connection_attempt':
                ban_event_players.add((event.player_id, event.player_name))
        
        if not ban_event_players:
            return {
                'banned_players': [],
                'total_banned_in_logs': 0,
                'total_players_checked': 0,
                'api_errors': 0,
                'ban_check_available': True,
                'note': 'No ban-related events found in logs'
            }
        
        banned_players = []
        verified_bans = 0
        false_positives = 0
        api_errors = 0
        
        for player_id, player_name in ban_event_players:
            try:
                ban_status = self._get_ban_status(player_id)
                if ban_status is False:  # Try name if ID check failed
                    ban_status = self._get_ban_status(player_name)
                
                if ban_status is True:
                    verified_bans += 1
                    # Get player statistics if they have sessions
                    sessions = self.player_sessions.get(player_id, [])
                    if sessions:
                        player_events = self.get_events_by_player(player_id)
                        total_playtime = sum(s.duration.total_seconds() if s.duration else 0 for s in sessions)
                        last_seen = max(s.end_time for s in sessions if s.end_time) if sessions else None
                    else:
                        player_events = []
                        total_playtime = 0
                        last_seen = None
                    
                    banned_players.append({
                        'player_id': player_id,
                        'player_name': player_name,
                        'sessions': len(sessions),
                        'total_playtime_hours': total_playtime / self.SECONDS_PER_HOUR,
                        'total_events': len(player_events),
                        'last_seen': last_seen,
                        'verified': True
                    })
                elif ban_status is False:
                    false_positives += 1
                    # Add false positive to results for investigation
                    banned_players.append({
                        'player_id': player_id,
                        'player_name': player_name,
                        'sessions': 0,
                        'total_playtime_hours': 0,
                        'total_events': 0,
                        'last_seen': None,
                        'verified': False,
                        'note': 'False positive - not actually banned'
                    })
                else:  # ban_status is None (API error)
                    api_errors += 1
                    
            except Exception as e:
                logger.warning(f"Error checking ban status for player {player_name} ({player_id}): {e}")
                api_errors += 1
        
        return {
            'banned_players': banned_players,
            'total_banned_in_logs': verified_bans,
            'false_positives': false_positives,
            'total_players_checked': len(ban_event_players),
            'api_errors': api_errors,
            'ban_check_available': True
        }
    
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
                # Create grid squares for combat hotspot analysis
                grid_x = int(event.victim_pos[0] // self.COMBAT_GRID_SIZE_METERS) * self.COMBAT_GRID_SIZE_METERS
                grid_y = int(event.victim_pos[1] // self.COMBAT_GRID_SIZE_METERS) * self.COMBAT_GRID_SIZE_METERS
                hotspots[(grid_x, grid_y)] += 1
        
        # Top hotspots
        stats['combat_hotspots'] = dict(sorted(hotspots.items(), key=lambda x: x[1], reverse=True)[:self.TOP_RESULTS_LIMIT])
        
        # Deadliest weapons (by kill rate)
        weapon_stats = defaultdict(lambda: {'hits': 0, 'kills': 0, 'total_damage': 0})
        for event in self.combat_events:
            weapon_stats[event.weapon]['hits'] += 1
            weapon_stats[event.weapon]['total_damage'] += event.damage
            if event.kill:
                weapon_stats[event.weapon]['kills'] += 1
        
        for weapon, data in weapon_stats.items():
            kill_rate = (data['kills'] / data['hits']) * self.PERCENTAGE_MULTIPLIER if data['hits'] > 0 else 0
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
        # Placeholder for future anomaly detection implementations
        anomalies = {}
        return anomalies
    
    def export_to_csv(self, output_prefix: str) -> List[str]:
        """
        Export analysis results to CSV files.
        
        Creates the following CSV exports:
        - Player statistics: Aggregated player metrics with special events
        - Combat events: PvP hit/kill events with details
        - Player state events: Connection, consciousness, emotes, respawns, etc.
        - Environmental combat events: Environmental hits, explosions, deaths, combat logging
        - Teleportation events: Player teleportation with coordinates and reasons
        - Building events: Construction, mounting, dismantling activities
        - Player sessions: Connection sessions with duration and distance
        
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
        # Count special events per player using cached lookups
        special_event_counts = {name: {} for name in self._special_event_names}
        self._ensure_cache_valid()  # Ensure cache is built
        for player_id, events in self._events_by_player.items():
            for event in events:
                if event.event_type in self._special_event_names:
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
                    'Teleported Events', 'Deaths by Bear', 'Deaths by Wolf', 'Deaths by Fall', 'Deaths by Explosion', 'Deaths by Zombies'
                ]
                # Add special event columns
                columns += [f"{name.replace('_', ' ').title()} Events" for name in self._special_event_names]
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
                        stats.get('deaths_by_wolf', 0), stats.get('deaths_by_fall', 0),
                        stats.get('deaths_by_explosion', 0), stats.get('deaths_by_zombie', 0)
                    ]
                    # Add special event counts
                    for name in self._special_event_names:
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
                    'To X', 'To Y', 'To Z', 'Distance (km)', 'Reason', 'Restricted Area'
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
                        round(details.get('teleport_distance', 0) / self.METERS_PER_KILOMETER, 3),  # Convert to kilometers
                        details.get('reason', ''),
                        details.get('restricted_area', '')
                    ])
            created_files.append(teleport_csv)
            logger.info(f"Teleportation events exported to: {teleport_csv}")

        # Player state events - all player activity events
        player_state_event_types = {
            'connection', 'disconnection', 'unconscious', 'conscious', 'respawn', 'bledout', 
            'emote', 'tripwire_hit', 'player_position',
            # Player activity events
            'building', 'dismantle', 'placed', 'raisedflag', 'suicide', 'teleported',
            # Combat-related player events  
            'death_by_explosion', 'hit', 'kill',
            # Environmental damage events
            'env_hit', 'env_hit_simple', 'explosion_hit'
        }
        player_state_events = [e for e in self.events if e.event_type in player_state_event_types]
        if player_state_events:
            player_state_csv = self.resolve_path(f"{self.output_dir}/{output_prefix}_player_state_events_{timestamp}.csv")
            with open(player_state_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp', 'Player Name', 'Player ID', 'Event Type', 'X', 'Y', 'Z', 'Details'
                ])
                for event in player_state_events:
                    details = event.details or {}
                    # Extract relevant details based on event type
                    details_str = ''
                    if event.event_type == 'emote':
                        emote = details.get('emote', '')
                        emote_item = details.get('emote_item', '')
                        details_str = f"Emote: {emote}" + (f" with {emote_item}" if emote_item else "")
                    elif event.event_type == 'tripwire_hit':
                        damage = details.get('damage', '')
                        hp = details.get('hp', '')
                        hit_location = details.get('hit_location', '')
                        details_str = f"Damage: {damage}, HP: {hp}, Hit Location: {hit_location}"
                    elif event.event_type in ('unconscious', 'conscious'):
                        details_str = f"State change: {event.event_type}"
                    elif event.event_type in ('connection', 'disconnection'):
                        details_str = f"Session: {event.event_type}"
                    elif event.event_type in ('respawn', 'bledout'):
                        details_str = f"Death event: {event.event_type}"
                    
                    writer.writerow([
                        event.timestamp.isoformat(),
                        event.player_name,
                        event.player_id,
                        event.event_type,
                        event.position[0] if event.position else '',
                        event.position[1] if event.position else '',
                        event.position[2] if event.position else '',
                        details_str
                    ])
            created_files.append(player_state_csv)
            logger.info(f"Player state events exported to: {player_state_csv}")

        # Environmental combat events (env_hit, env_hit_simple, explosion_hit, death_player, death_fall, death_by_explosion, death_by_zombie, combat_log_unconscious)
        env_combat_events = [e for e in self.events if e.event_type in ('env_hit', 'env_hit_simple', 'explosion_hit', 'death_player', 'death_fall', 'death_by_explosion', 'death_by_zombie', 'combat_log_unconscious')]
        if env_combat_events:
            env_combat_csv = self.resolve_path(f"{self.output_dir}/{output_prefix}_environmental_combat_events_{timestamp}.csv")
            with open(env_combat_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp', 'Player Name', 'Player ID', 'Event Type', 'Attacker/Source', 'Weapon/Method', 
                    'Damage', 'HP', 'X', 'Y', 'Z', 'Details'
                ])
                for event in env_combat_events:
                    details = event.details or {}
                    # Extract relevant details based on event type
                    attacker = ''
                    weapon = ''
                    damage = ''
                    hp = ''
                    details_str = ''
                    
                    if event.event_type == 'env_hit':
                        attacker = details.get('attacker_name', '')
                        weapon = details.get('weapon', '')
                        hp = details.get('victim_hp', '')
                        details_str = f"Environmental hit by {attacker}"
                    elif event.event_type == 'env_hit_simple':
                        attacker = details.get('attacker_name', '')
                        hp = details.get('victim_hp', '')
                        weapon = details.get('weapon', attacker)  # Use attacker as weapon for simple form
                        details_str = f"Environmental hit by {attacker}"
                    elif event.event_type == 'explosion_hit':
                        explosion_type = details.get('weapon', '')  # Explosion handler stores it as 'weapon'
                        hp = details.get('victim_hp', '')
                        attacker = 'Explosion'
                        weapon = explosion_type
                        details_str = f"Explosion hit: {explosion_type}"
                    elif event.event_type == 'death_player':
                        killer = details.get('killer', '')
                        attacker = killer
                        details_str = f"Killed by {killer}"
                    elif event.event_type == 'death_fall':
                        attacker = 'Fall Damage'
                        weapon = 'FallDamageHealth'
                        details_str = "Death by fall damage"
                    elif event.event_type == 'death_by_explosion':
                        killer = details.get('killer', '')
                        attacker = killer
                        weapon = killer
                        details_str = f"Death by explosion: {killer}"
                    elif event.event_type == 'death_by_zombie':
                        killer = details.get('killer', '')
                        attacker = killer
                        details_str = f"Death by zombie: {killer}"
                    elif event.event_type == 'combat_log_unconscious':
                        details_str = "Disconnected while unconscious (combat logging)"
                    
                    writer.writerow([
                        event.timestamp.isoformat(),
                        event.player_name,
                        event.player_id,
                        event.event_type,
                        attacker,
                        weapon,
                        damage,
                        hp,
                        event.position[0] if event.position else '',
                        event.position[1] if event.position else '',
                        event.position[2] if event.position else '',
                        details_str
                    ])
            created_files.append(env_combat_csv)
            logger.info(f"Environmental combat events exported to: {env_combat_csv}")

        # Building activities report (includes building, mounted, unmounted, raisedflag, builtbaseon, dismantle, repaired, packed, placed, folded)
        building_events = [e for e in self.events if e.event_type in ('building', 'mounted', 'unmounted', 'raisedflag', 'builtbaseon', 'dismantle', 'repaired', 'packed', 'placed', 'folded')]
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
    
    def run(self, log_file: str, export_csv: bool = True, output_prefix: str = "adm_analysis", skip_parse: bool = False, start_datetime: datetime = None, end_datetime: datetime = None) -> Dict[str, Any]:
        """
        Run the complete ADM log analysis.
        
        Args:
            log_file: Path to the ADM log file
            export_csv: Whether to export results to CSV
            output_prefix: Prefix for output files
            skip_parse: Skip parsing if data is already loaded
            start_datetime: Optional start time filter
            end_datetime: Optional end time filter
            
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
        
        # Check for banned players (automatic)
        banned_players_summary = self.get_banned_players_summary()
        
        # Get error reporting for data quality assessment
        error_report = self.get_parse_error_report()
        
        # Count building events directly from the events list for accuracy
        building_events_count = len([e for e in self.events if e.event_type in ('building', 'mounted', 'unmounted', 'raisedflag', 'builtbaseon', 'dismantle', 'repaired', 'packed', 'placed', 'folded')])
        
        results = {
            'parse_statistics': parse_stats,
            'player_statistics': player_stats,
            'combat_statistics': combat_stats,
            'anomalies': anomalies,
            'banned_players': banned_players_summary,
            'error_report': error_report,
            'summary': {
                'analysis_timestamp': datetime.now().isoformat(),
                'log_file': log_file,
                'total_events_parsed': len(self.events),
                'unique_players': len(self.player_sessions),
                'total_combat_events': len(self.combat_events),
                'building_events': building_events_count,
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

    parser.add_argument(
        '--debug-skipped',
        action='store_true',
        help='Write skipped/malformed log lines to a separate debug file for analysis'
    )

    parser.add_argument(
        '--start-date', 
        help='Start date in DD.MM.YYYY format with optional time HH:MM:SS (e.g., 01.06.2023 or 01.06.2023 14:30:00). If only date is provided, time defaults to 00:00:00.', 
        type=str
    )
    
    parser.add_argument(
        '--end-date', 
        help='End date in DD.MM.YYYY format with optional time HH:MM:SS (e.g., 30.06.2023 or 30.06.2023 23:59:59). If only date is provided, time defaults to 23:59:59.', 
        type=str
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
        
        # Parse start and end datetimes
        start_datetime = None
        end_datetime = None
        
        if args.start_date:
            try:
                # Try parsing with time component
                try:
                    start_datetime = datetime.strptime(args.start_date, "%d.%m.%Y %H:%M:%S")
                except ValueError:
                    # If that fails, try parsing with just the date and set time to midnight
                    start_datetime = datetime.strptime(args.start_date, "%d.%m.%Y").replace(hour=0, minute=0, second=0)
                logger.info(f"Using start date filter: {start_datetime}")
            except ValueError:
                raise ValueError(f"Invalid start date format. Use DD.MM.YYYY [HH:MM:SS] format (e.g., 01.06.2023 or 01.06.2023 14:30:00)")
        
        if args.end_date:
            try:
                # Try parsing with time component
                try:
                    end_datetime = datetime.strptime(args.end_date, "%d.%m.%Y %H:%M:%S")
                except ValueError:
                    # If that fails, try parsing with just the date and set time to end of day
                    end_datetime = datetime.strptime(args.end_date, "%d.%m.%Y").replace(hour=23, minute=59, second=59)
                logger.info(f"Using end date filter: {end_datetime}")
            except ValueError:
                raise ValueError(f"Invalid end date format. Use DD.MM.YYYY [HH:MM:SS] format (e.g., 30.06.2023 or 30.06.2023 23:59:59)")

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

        # Setup debug file path if debug-skipped is enabled
        debug_skipped_file = None
        if args.debug_skipped:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = analyzer.output_dir if hasattr(analyzer, 'output_dir') else '.'
            debug_skipped_file = analyzer.resolve_path(f"{output_dir}/{args.output_prefix}_skipped_lines_{timestamp}.txt")
            logger.info(f"Debug mode enabled - skipped lines will be written to: {debug_skipped_file}")

        # Aggregate all log files before running analysis
        for i, log_file in enumerate(log_files):
            # For multiple files, append to debug file after the first one
            append_debug = (i > 0) if debug_skipped_file else False
            analyzer.parse_log_file(log_file, debug_skipped_file=debug_skipped_file, 
                                append_debug=append_debug,
                                start_datetime=start_datetime,
                                end_datetime=end_datetime)

        # Now run analysis on the aggregated data
        results = analyzer.run(
            log_file="multiple files",
            export_csv=not args.no_csv,
            output_prefix=args.output_prefix,
            skip_parse=True,
            start_datetime=start_datetime,
            end_datetime=end_datetime
        )


        # Markdown report generation for summary highlights
        player_stats = results['player_statistics']
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = analyzer.output_dir if hasattr(analyzer, 'output_dir') else '.'
        md_report_path = analyzer.resolve_path(f"{output_dir}/{args.output_prefix}_summary_{timestamp}.md")

        md_lines = []
        summary = results['summary']
        
        # Format timestamps for better readability
        analysis_time = datetime.fromisoformat(summary['analysis_timestamp']).strftime("%d-%m-%Y %H:%M:%S")
        start_time = datetime.fromisoformat(summary['analysis_time_range']['start']).strftime("%d-%m-%Y %H:%M:%S") if summary['analysis_time_range']['start'] else 'Unknown'
        end_time = datetime.fromisoformat(summary['analysis_time_range']['end']).strftime("%d-%m-%Y %H:%M:%S") if summary['analysis_time_range']['end'] else 'Unknown'
        
        md_lines.append(f"**DayZ ADM Log Analysis Summary (Aggregated)**\n")
        md_lines.append(f"## Overview")
        md_lines.append(f"- Log File(s): {summary['log_file']}")
        md_lines.append(f"- Analysis Time: {analysis_time}")
        md_lines.append(f"- Time Range: {start_time} to {end_time}")
        md_lines.append(f"- Total Events Parsed: {format_european_number(summary['total_events_parsed'])}")
        md_lines.append(f"- Unique Players: {format_european_number(summary['unique_players'])}")
        
        # Calculate total distance traveled by all players
        total_distance_all_players = 0
        if player_stats.get('players'):
            for player_id, stats in player_stats['players'].items():
                total_distance_all_players += stats.get('total_distance_traveled', 0)
        
        # Convert meters to kilometers
        total_distance_km = total_distance_all_players / DayZADMAnalyzer.METERS_PER_KILOMETER
        
        # Count special events globally (computed once and reused)
        special_event_counts_global = {name: 0 for name in analyzer._special_event_names}
        for e in analyzer.events:
            if e.event_type in analyzer._special_event_names:
                special_event_counts_global[e.event_type] += 1
        
        md_lines.append(f"\n## Server Activity Statistics")
        md_lines.append(f"- Total Distance Traveled: {format_european_number(round(total_distance_km, 1))} km")
        md_lines.append(f"- Building Events: {format_european_number(summary['building_events'])}")
        md_lines.append(f"- Combat Events: {format_european_number(summary['total_combat_events'])}")
        if analyzer._special_event_names:
            total_special_events = sum(special_event_counts_global.values())
            if total_special_events > 0:
                # Find the most common special event for summary
                most_common_event = max(special_event_counts_global.items(), key=lambda x: x[1])
                if most_common_event[1] > 0:
                    md_lines.append(f"- Special Events: {format_european_number(most_common_event[1])} ({most_common_event[0].replace('_', ' ').title()})")
        
        # Add teleportation and combat logging event summary
        teleport_events = [e for e in analyzer.events if e.event_type == 'teleported']
        teleported_players = len([p for p in player_stats.get('players', {}) if player_stats['players'][p].get('teleported_events', 0) > 0])
        restricted_violations = len([e for e in teleport_events if e.details and 'RestrictedArea' in (e.details.get('reason', ''))])
        avg_distance = 0
        if teleport_events:
            total_distance = sum([e.details.get('teleport_distance', 0) for e in teleport_events if e.details])
            avg_distance = round((total_distance / len(teleport_events)) / DayZADMAnalyzer.METERS_PER_KILOMETER, 3)  # Convert to kilometers
        
        combat_log_events = [e for e in analyzer.events if e.event_type == 'combat_log_unconscious']
        total_combat_logs = sum(stats.get('combat_logs', 0) for stats in player_stats['players'].values())
        combat_log_players = len([p for p in player_stats.get('players', {}) if player_stats['players'][p].get('combat_logs', 0) > 0])
        
        # Calculate banned connection attempts
        banned_connection_events = [e for e in analyzer.events if e.event_type == 'banned_connection_attempt']
        total_banned_connections = len(banned_connection_events)
        
        md_lines.append(f"\n## Administrative Events")
        md_lines.append(f"- Teleported Players: {format_european_number(teleported_players)}")
        md_lines.append(f"- Restricted Area Violations: {format_european_number(restricted_violations)}")
        md_lines.append(f"- Average Teleport Distance: {format_european_number(avg_distance, 3)} km")
        md_lines.append(f"- Combat Logging Events: {format_european_number(total_combat_logs)}")
        md_lines.append(f"- Players with Combat Logs: {format_european_number(combat_log_players)}")
        md_lines.append(f"- Banned Connection Attempts: {format_european_number(total_banned_connections)}")
        
        # Banned Players Summary
        banned_summary = results.get('banned_players', {})
        if banned_summary.get('ban_check_available'):
            if banned_summary.get('note'):
                md_lines.append(f"- Ban Event Verification: {banned_summary['note']}")
            else:
                verified_count = banned_summary.get('total_banned_in_logs', 0)
                false_positives = banned_summary.get('false_positives', 0)
                total_checked = banned_summary.get('total_players_checked', 0)
                api_errors = banned_summary.get('api_errors', 0)
                md_lines.append(f"- Ban Event Verification: {format_european_number(verified_count)} verified, {format_european_number(false_positives)} false positives ({format_european_number(total_checked)} ban events checked)")
                if api_errors > 0:
                    md_lines.append(f"- Ban Check API Errors: {format_european_number(api_errors)}")
        else:
            md_lines.append(f"- Ban Event Verification: Not available (configure Nitrado API)")

        # --- Config-driven special events for Markdown summary ---
        # (special_event_counts_global already computed above)

        md_lines.append(f"\n## Player Activity Rankings")

        # Top 10 Most Active Players (by playtime)
        if player_stats.get('players'):
            sorted_players = sorted(
                player_stats['players'].items(),
                key=lambda x: x[1]['total_playtime_hours'],
                reverse=True
            )
            md_lines.append(f"\n### Top 10 Most Active Players (by playtime)")
            for player_id, stats in sorted_players[:10]:
                playtime = format_european_number(stats['total_playtime_hours'], 1)
                kills = format_european_number(stats.get('kills (PvP)', 0))
                deaths = format_european_number(stats.get('deaths', 0))
                kd_ratio = format_european_number(stats.get('kd_ratio (PvP)', 0), 2)
                md_lines.append(f"* {stats['name']}: {playtime}h, {kills} kills (PvP), {deaths} deaths, {kd_ratio} K/D (PvP)")

        # Top 10 Most Active Builders
        sorted_builders = sorted(
            player_stats['players'].items(),
            key=lambda x: x[1].get('building_actions', 0),
            reverse=True
        )
        md_lines.append(f"\n### Top 10 Most Active Builders")
        for player_id, stats in sorted_builders[:10]:
            building_actions = format_european_number(stats.get('building_actions', 0))
            md_lines.append(f"* {stats['name']}: {building_actions} building actions")

        md_lines.append(f"\n## Combat Statistics")

        # Top 5 Killers (PvP)
        if player_stats.get('players'):
            killer_players = [(pid, stats) for pid, stats in player_stats['players'].items() if stats.get('kills (PvP)', 0) > 0]
            top_killers = sorted(killer_players, key=lambda x: x[1].get('kills (PvP)', 0), reverse=True)[:5]
            
            if top_killers:
                md_lines.append(f"\n### Top 5 Killers (PvP)")
                for pid, stats in top_killers:
                    kills = format_european_number(stats.get('kills (PvP)', 0))
                    kd_ratio = format_european_number(stats.get('kd_ratio (PvP)', 0), 2)
                    md_lines.append(f"* {stats['name']}: {kills} kills (PvP), {kd_ratio} K/D (PvP)")

        # Top Damage Dealer (PvP)
        if player_stats.get('players'):
            top_damage = max(player_stats['players'].items(), key=lambda x: x[1].get('damage_dealt (PvP)', 0), default=None)
            if top_damage and top_damage[1].get('damage_dealt (PvP)', 0) > 0:
                damage = format_european_number(top_damage[1].get('damage_dealt (PvP)', 0), 1)
                md_lines.append(f"\n### Top Damage Dealer (PvP)")
                md_lines.append(f"* {top_damage[1]['name']}: {damage} total damage (PvP)")

        # Top K/D Ratio (PvP)
        if player_stats.get('players'):
            kd_players = [(pid, stats) for pid, stats in player_stats['players'].items() if stats.get('kd_ratio (PvP)', 0) > 0]
            if kd_players:
                top_kd = max(kd_players, key=lambda x: x[1].get('kd_ratio (PvP)', 0))
                kd_ratio = format_european_number(top_kd[1].get('kd_ratio (PvP)', 0), 2)
                md_lines.append(f"\n### Top K/D Ratio (PvP)")
                md_lines.append(f"* {top_kd[1]['name']}: {kd_ratio} K/D (PvP)")

        # Most Used Weapons (excluding Melee)
        combat_stats = results['combat_statistics']
        if isinstance(combat_stats, dict) and 'weapon_usage' in combat_stats:
            weapon_usage = combat_stats['weapon_usage']
            filtered_weapons = [(w, c) for w, c in weapon_usage.items() if w and 'melee' not in w.lower() and w.lower() != '']
            filtered_weapons.sort(key=lambda x: x[1], reverse=True)
            md_lines.append(f"\n### Most Used Weapons (excluding Melee)")
            for weapon, count in filtered_weapons[:5]:
                formatted_count = format_european_number(count)
                md_lines.append(f"* {weapon}: {formatted_count} hits")

        md_lines.append(f"\n## Environmental Events")

        # Special Events
        if analyzer._special_event_names:
            md_lines.append(f"\n### Special Events")
            for name in analyzer._special_event_names:
                count = format_european_number(special_event_counts_global[name])
                md_lines.append(f"* {name.replace('_', ' ').title()}: {count} occurrences")

        # Environmental Deaths
        total_bear = sum(stats.get('deaths_by_bear', 0) for stats in player_stats['players'].values())
        total_wolf = sum(stats.get('deaths_by_wolf', 0) for stats in player_stats['players'].values())
        total_fall = sum(stats.get('deaths_by_fall', 0) for stats in player_stats['players'].values())
        total_explosion = sum(stats.get('deaths_by_explosion', 0) for stats in player_stats['players'].values())
        total_zombie = sum(stats.get('deaths_by_zombie', 0) for stats in player_stats['players'].values())
        md_lines.append(f"\n### Environmental Deaths")
        md_lines.append(f"* Deaths by Fall: {format_european_number(total_fall)}")
        md_lines.append(f"* Deaths by Explosion: {format_european_number(total_explosion)}")
        md_lines.append(f"* Deaths by Zombies: {format_european_number(total_zombie)}")
        md_lines.append(f"* Deaths by Bear: {format_european_number(total_bear)}")
        md_lines.append(f"* Deaths by Wolf: {format_european_number(total_wolf)}")

        # Combat Logging Events
        if combat_log_events:
            md_lines.append(f"\n### Combat Logging Events")
            for event in combat_log_events:
                timestamp_str = event.timestamp.strftime('%d-%m-%Y %H:%M:%S') if event.timestamp else 'Unknown'
                md_lines.append(f"* {timestamp_str}: Player \"{event.player_name}\" disconnected while unconscious")

        md_lines.append(f"\n## Security & Anomalies")

        # Banned Connection Attempts
        if banned_connection_events:
            md_lines.append(f"\n### Banned Connection Attempts")
            for event in banned_connection_events:
                timestamp_str = event.timestamp.strftime('%d-%m-%Y %H:%M:%S') if event.timestamp else 'Unknown'
                md_lines.append(f"* {timestamp_str}: Player \"{event.player_name}\" attempted to connect (banned) (verified)")

        # Write Markdown report
        with open(md_report_path, 'w', encoding='utf-8') as f:
            for line in md_lines:
                f.write(line + '\n')
        print(f"\nMarkdown summary exported to: {md_report_path}") 

        # Report debug file location if it was created
        if debug_skipped_file and Path(debug_skipped_file).exists():
            print(f"Debug file with skipped lines: {debug_skipped_file}")

        print("\nAnalysis completed successfully!")

        return 0

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        if args.console:
            raise
        return 1


if __name__ == '__main__':
    exit(main())

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

        # Use self.log_dir from base class for log directory

        # Pre-compiled regex patterns for performance
        # Patterns are grouped and commented by event type for clarity
        self.patterns = {
            # --- Connection/Disconnection Events ---
            'connection': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\)\s*is connected'),
            'disconnection': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\)\s*has been disconnected'),

            # --- Player State/Status Events ---
            'unconscious': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)\s*is unconscious'),
            'conscious': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)\s*regained consciousness'),
            'suicide': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=([A-F0-9]+)(?:\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>)?\)\s*committed suicide'),
            'emote': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)\s*performed ([^\s]+)(?: with ([^\s]+))?'),

            # --- Combat Events ---
            'hit': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)\s*\[HP: ([0-9.]+)\]\s*hit by Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)\s*into\s*([^(]+)\((\d+)\)\s*for\s*([0-9.]+) damage\s*\(([^)]+)\)(?: with ([^\)]+) from ([0-9.]+) meters)?'),
            'kill': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(DEAD\)\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)\s*killed by Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)\s*with\s*([^"]+?)\s*from\s*([0-9.]+) meters'),
            'env_hit': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)\[HP: ([0-9.]+)\] hit by ([^\s]+) with ([^\s]+)'),
            'env_hit_simple': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)\[HP: ([0-9.]+)\]\s*hit by ([^\s]+)$'),
            'explosion_hit': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*(?:\(DEAD\)\s*)?\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)\[HP: ([0-9.]+)\] hit by explosion \(([^)]+)\)'),
            'death': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(DEAD\)\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)\s*died\. Stats> Water: ([0-9.]+) Energy: ([0-9.]+) Bleed sources: (\d+)'),
            'death_other': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(DEAD\)\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\) killed by ([^\s]+)'),

            # --- Building/Construction Events ---
            'building': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)\s*(Built|Dismantled) ([^\s]+) (on|from) ([^\s]+) with ([^\s]+)$'),
            'packed': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\) packed (.+?) with ([^\s]+)$'),
            'placed': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\) placed (.+)$'),
            'folded': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\) folded (.+)$'),

            # --- Fallback/Player List ---
            'player_list': re.compile(r'(\d{2}:\d{2}:\d{2})\s*\|\s*Player\s*"([^"]+?)"\s*\(id=([A-F0-9]+)\s*pos=<([0-9.-]+),\s*([0-9.-]+),\s*([0-9.-]+)>\)(?!.*(placed|Built|Dismantled|folded|hit by|killed by))')
        }

        # --- Special/Other Events from config ---
        special_events_cfg = (self.config or {}).get('special_events', {})
        if special_events_cfg.get('enabled', False):
            for event in special_events_cfg.get('events', []):
                name = event.get('name')
                regexp = event.get('regexp')
                if name and regexp:
                    try:
                        self.patterns[name] = re.compile(rf'(\d{{2}}:\d{{2}}:\d{{2}})\s*\|\s*{regexp}')
                    except Exception as e:
                        logger.error(f"Failed to compile special event regexp for '{name}': {e}")
        
    def parse_log_file(self, log_file: str) -> Dict[str, Any]:
        """
        Parse a DayZ ADM log file.
        
        Args:
            log_file: Path to the ADM log file
            
        Returns:
            Dictionary containing parsing results and statistics
        """
        log_path = self.resolve_path(log_file)
        
        if not Path(log_path).exists():
            raise FileNotFoundError(f"Log file not found: {log_path}")
        
        logger.info(f"Parsing ADM log file: {log_path}")

        
        parse_stats = {
            'total_lines': 0,
            'parsed_events': 0,
            'connections': 0,
            'disconnections': 0,
            'combat_events': 0,
            'deaths': 0,
            'building_events': 0,
            'emotes': 0,
            'start_time': None,
            'end_time': None
        }
        
        # Extract date from filename for timestamp parsing
        base_date = self._extract_date_from_filename(log_path)
        
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                parse_stats['total_lines'] += 1
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Try to parse the line with different patterns
                event = self._parse_line(line, base_date)
                if event:
                    self.events.append(event)
                    parse_stats['parsed_events'] += 1
                    # Update timestamps
                    if parse_stats['start_time'] is None or event.timestamp < parse_stats['start_time']:
                        parse_stats['start_time'] = event.timestamp
                    if parse_stats['end_time'] is None or event.timestamp > parse_stats['end_time']:
                        parse_stats['end_time'] = event.timestamp
                    # Update specific event counters
                    if event.event_type == 'connection':
                        parse_stats['connections'] += 1
                        self._handle_connection(event)
                    elif event.event_type == 'disconnection':
                        parse_stats['disconnections'] += 1
                        self._handle_disconnection(event)
                    elif event.event_type in ['hit', 'kill']:
                        parse_stats['combat_events'] += 1
                    elif event.event_type == 'death':
                        parse_stats['deaths'] += 1
                    elif event.event_type == 'building':
                        parse_stats['building_events'] += 1
                    elif event.event_type == 'emote':
                        parse_stats['emotes'] += 1
                    # Handle position tracking for active sessions
                    if event.position and event.player_id in self.current_sessions:
                        session = self.current_sessions[event.player_id]
                        session.positions.append((event.timestamp, *event.position))
                        
        # Close any remaining open sessions
        for session in self.current_sessions.values():
            if session.disconnect_time is None:
                session.disconnect_time = parse_stats['end_time']
            self.player_sessions[session.player_id].append(session)
        self.current_sessions.clear()
        
        logger.info(f"Parsed {parse_stats['parsed_events']} events from {parse_stats['total_lines']} lines")
        return parse_stats
        
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
    
    def _create_event_from_match(self, event_type: str, match, base_date: datetime, line: str) -> PlayerEvent:
        """Create a PlayerEvent from a regex match."""
        groups = match.groups()
        time_str = groups[0]
        details = {'raw_line': line}
        # ...existing code...
        # --- Config-driven special events ---
        special_events_cfg = (self.config or {}).get('special_events', {})
        special_event_names = set(e.get('name') for e in special_events_cfg.get('events', [])) if special_events_cfg.get('enabled', False) else set()
        if event_type in special_event_names:
            # Generic handler for config-driven special events
            player_name = groups[1] if len(groups) > 1 else "Unknown"
            player_id = groups[2] if len(groups) > 2 else "Unknown"
            # Try to extract position if present (groups 3,4,5)
            try:
                position = (float(groups[3]), float(groups[4]), float(groups[5]))
            except Exception:
                position = None
            details.update({'event': event_type, 'raw_groups': groups})
            # Optionally, extract more details if the config provides a 'fields' list in the future
            return PlayerEvent(
                timestamp=base_date.replace(
                    hour=int(time_str.split(':')[0]),
                    minute=int(time_str.split(':')[1]),
                    second=int(time_str.split(':')[2])
                ),
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
            if len(groups) == 8:
                player_name = groups[1]
                player_id = groups[2]
                try:
                    position = (float(groups[3]), float(groups[4]), float(groups[5]))
                except Exception as e:
                    logger.error(f"Error parsing position for packed event: {e}")
                    position = None
                structure = groups[6]
                tool = groups[7]
                details.update({
                    'action': 'packed',
                    'structure': structure,
                    'parent': '',
                    'tool': tool
                })
                # Return PlayerEvent immediately to avoid further processing and tuple index errors
                return PlayerEvent(
                    timestamp=base_date.replace(
                        hour=int(time_str.split(':')[0]),
                        minute=int(time_str.split(':')[1]),
                        second=int(time_str.split(':')[2])
                    ),
                    player_name=player_name,
                    player_id=player_id,
                    event_type='building',
                    position=position,
                    details=details
                )
            else:
                logger.error(f"Malformed packed event, skipping: {groups}")
                return None
        # ...existing code...
        
        # Parse timestamp
        time_parts = time_str.split(':')
        timestamp = base_date.replace(
            hour=int(time_parts[0]),
            minute=int(time_parts[1]),
            second=int(time_parts[2])
        )
        
        # Handle day rollover
        if timestamp < base_date:
            timestamp += timedelta(days=1)
        
        if event_type in ['connection', 'disconnection']:
            player_name = groups[1]
            player_id = groups[2]
            position = None
            
        elif event_type == 'player_list':
            player_name = groups[1]
            player_id = groups[2]
            position = (float(groups[3]), float(groups[4]), float(groups[5]))

        elif event_type in ['placed', 'folded']:
            player_name = groups[1]
            player_id = groups[2]
            try:
                position = (float(groups[3]), float(groups[4]), float(groups[5]))
            except Exception as e:
                logger.error(f"Error parsing position for {event_type} event: {e}")
                position = None
            
        elif event_type == 'death':
            player_name = groups[1]
            player_id = groups[2]
            position = (float(groups[3]), float(groups[4]), float(groups[5]))
            details.update({
                'water': float(groups[6]),
                'energy': float(groups[7]),
                'bleed_sources': int(groups[8])
            })
            
        elif event_type == 'hit':
            # Victim is the first player mentioned
            player_name = groups[1]
            player_id = groups[2]
            victim_pos = (float(groups[3]), float(groups[4]), float(groups[5]))
            victim_hp = float(groups[6])
            attacker_name = groups[7]
            attacker_id = groups[8]
            attacker_pos = (float(groups[9]), float(groups[10]), float(groups[11]))
            hit_location = groups[12].strip()
            # DEBUG: log all groups for hit event
            logger.debug(f"HIT GROUPS: {groups}")
            damage = float(groups[13])
            ammo = groups[14]
            # Robustly assign weapon and distance for all cases
            weapon = None
            distance = None
            # If both weapon and distance are present (17 and 18), assign accordingly
            if len(groups) > 17 and groups[16] is not None and groups[17] is not None:
                weapon = groups[16].strip()
                try:
                    distance = float(groups[17])
                except (TypeError, ValueError):
                    distance = None
            # If only weapon is present (16), assign weapon, distance remains None
            elif len(groups) > 16 and groups[16] is not None:
                weapon = groups[16].strip()
                distance = None
            # If only ammo is present (15), treat as weapon for legacy lines
            elif len(groups) > 15 and groups[15] is not None:
                weapon = groups[15].strip()
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

        elif event_type == 'env_hit':
            # Environmental hit (e.g., hit by Fence with BarbedWireHit)
            player_name = groups[1]
            player_id = groups[2]
            victim_pos = (float(groups[3]), float(groups[4]), float(groups[5]))
            victim_hp = float(groups[6])
            attacker_name = groups[7]  # e.g., Fence
            weapon = groups[8]         # e.g., BarbedWireHit
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
            player_name = groups[1]
            player_id = groups[2]
            victim_pos = (float(groups[3]), float(groups[4]), float(groups[5]))
            victim_hp = float(groups[6])
            attacker_name = groups[7]  # e.g., FallDamageHealth
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
            player_name = groups[1]
            player_id = groups[2]
            victim_pos = (float(groups[3]), float(groups[4]), float(groups[5]))
            victim_hp = float(groups[6])
            explosion_type = groups[7]
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
            player_name = groups[1]
            player_id = groups[2]
            victim_pos = (float(groups[3]), float(groups[4]), float(groups[5]))
            killer = groups[6]
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
            player_name = groups[1]  # Victim
            player_id = groups[2]
            victim_pos = (float(groups[3]), float(groups[4]), float(groups[5]))
            attacker_name = groups[6]
            attacker_id = groups[7]
            attacker_pos = (float(groups[8]), float(groups[9]), float(groups[10]))
            weapon = groups[11].strip()
            distance = float(groups[12])

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
            hit_indices = []
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
                    hit_indices.append(idx)

            # Remove hit events at the kill timestamp to avoid double-counting in stats
            for idx in reversed(hit_indices):
                del self.combat_events[idx]

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
            
        elif event_type in ['suicide', 'unconscious', 'conscious', 'emote']:
            player_name = groups[1]
            player_id = groups[2]
            # For suicide, pos may be missing
            if event_type == 'suicide' and groups[3] is None:
                position = None
            else:
                try:
                    position = (float(groups[3]), float(groups[4]), float(groups[5]))
                except (TypeError, ValueError, IndexError):
                    position = None

            if event_type == 'emote':
                details['emote'] = groups[6]
                
        elif event_type == 'building':
            player_name = groups[1]
            player_id = groups[2]
            position = (float(groups[3]), float(groups[4]), float(groups[5]))
            action = groups[6]  # Built or Dismantled
            structure = groups[7]
            # on_or_from = groups[8]  # 'on' or 'from', not used in details
            parent = groups[9]
            tool = groups[10]
            details.update({
                'action': action,
                'structure': structure,
                'parent': parent,
                'tool': tool
            })
            
        else:
            # Generic parsing for other event types
            player_name = groups[1] if len(groups) > 1 else "Unknown"
            player_id = groups[2] if len(groups) > 2 else "Unknown"
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
            
            # Count player events
            player_events = [e for e in self.events if e.player_id == player_id]
            # Count all deaths for reporting
            deaths = len([e for e in player_events if e.event_type == 'death'])
            # Count only deaths caused by another player for K/D
            deaths_by_player = len([e for e in self.combat_events if e.victim_id == player_id and e.kill])
            suicides = len([e for e in player_events if e.event_type == 'suicide'])
            emotes = len([e for e in player_events if e.event_type == 'emote'])
            building_actions = len([e for e in player_events if e.event_type in ('building', 'placed', 'folded', 'packed')])
            deaths_by_bear = len([e for e in player_events if e.event_type == 'death_by_bear'])
            deaths_by_wolf = len([e for e in player_events if e.event_type == 'death_by_wolf'])
            
            # PvP-only combat statistics (add (PvP) suffix to keys)
            kills_pvp = len([e for e in self.combat_events if e.attacker_id == player_id and e.kill])
            hits_dealt_pvp = len([e for e in self.combat_events if e.attacker_id == player_id and e.victim_id and e.attacker_id and e.attacker_id != '' and e.victim_id != '' and e.attacker_id != e.victim_id])
            hits_taken_pvp = len([e for e in self.combat_events if e.victim_id == player_id and e.attacker_id and e.victim_id and e.attacker_id != '' and e.victim_id != '' and e.attacker_id != e.victim_id])
            damage_dealt_pvp = sum(e.damage for e in self.combat_events if e.attacker_id == player_id and e.victim_id and e.attacker_id and e.attacker_id != '' and e.victim_id != '' and e.attacker_id != e.victim_id)
            damage_taken_pvp = sum(e.damage for e in self.combat_events if e.victim_id == player_id and e.attacker_id and e.victim_id and e.attacker_id != '' and e.victim_id != '' and e.attacker_id != e.victim_id)

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
            'stat_padding_suspects': []
        }
        
        # Excessive suicides (more than 5 in a session)
        for player_id, sessions in self.player_sessions.items():
            for session in sessions:
                if not session.duration:
                    continue
                    
                player_events = [e for e in self.events 
                               if e.player_id == player_id 
                               and session.connect_time <= e.timestamp <= (session.disconnect_time or datetime.now())]
                
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
            combat_stats[event.attacker_id]['total_damage'] += event.damage
            combat_stats[event.attacker_id]['hits'] += 1
        
        for player_id, stats in combat_stats.items():
            if stats['hits'] > 0:
                avg_damage = stats['total_damage'] / stats['hits']
                if avg_damage > 150:  # Suspiciously high average damage
                    player_name = next((e.player_name for e in self.events if e.player_id == player_id), "Unknown")
                    anomalies['high_damage_dealers'].append({
                        'player_name': player_name,
                        'player_id': player_id,
                        'average_damage': avg_damage,
                        'total_hits': stats['hits']
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
        # Count special events per player
        special_event_counts = {name: {} for name in special_event_names}
        for e in self.events:
            if e.event_type in special_event_names:
                pid = getattr(e, 'player_id', None)
                if pid:
                    special_event_counts[e.event_type][pid] = special_event_counts[e.event_type].get(pid, 0) + 1

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
                    'Deaths by Bear', 'Deaths by Wolf'
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
                        stats.get('deaths_by_bear', 0),
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
        results = {
            'parse_statistics': parse_stats,
            'player_statistics': player_stats,
            'combat_statistics': combat_stats,
            'anomalies': anomalies,
            'summary': {
                'analysis_timestamp': datetime.now().isoformat(),
                'log_file': log_file,
                'total_events_parsed': len(self.events),
                'unique_players': len(self.player_sessions),
                'total_combat_events': len(self.combat_events),
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

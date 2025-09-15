"""
Event Spawn Plotter Tool

This tool reads cfgeventspawns.xml files and plots event spawn positions on a map image.
It reuses plotting logic from kopfgeldtracker.py to visualize event spawns.
"""

import sys
import os
from typing import Dict, Any, List, Tuple, Optional
import matplotlib.pyplot as plt
from PIL import Image
import argparse
import logging
from pathlib import Path

from dayz_admin_tools.base import XMLTool

logger = logging.getLogger(__name__)


class EventSpawnPlotterTool(XMLTool):
    """
    A tool for plotting event spawn positions from cfgeventspawns.xml onto a map image.
    
    This class reads XML configuration files containing event spawn positions and
    visualizes them on a map using matplotlib and PIL.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, map_width: int = None, map_height: int = None, 
                 show_coordinates: bool = None, show_legend: bool = None):
        """
        Initialize the Event Spawn Plotter Tool.
        
        Args:
            config: Configuration dictionary from Config class
            map_width: Width of the map in meters (default: from config or 15360 for Chernarus)
            map_height: Height of the map in meters (default: from config or 15360 for Chernarus)
            show_coordinates: Whether to show coordinate labels (default: from config or True)
            show_legend: Whether to show legend (default: from config or True)
        """
        super().__init__(config)
        self.initialize_directories()
        
        # Get map dimensions from config or use provided/default values
        self.map_width = map_width or int(self.get_config('event_spawn_plotter.map_width', 15360))
        self.map_height = map_height or int(self.get_config('event_spawn_plotter.map_height', 15360))
        
        # Get plotting configuration from config
        esp_config = self.config.get('event_spawn_plotter', {}) if self.config else {}
        
        self.default_output_dpi = int(esp_config.get('output_dpi', 300))
        self.default_marker_size = int(esp_config.get('marker_size', 50))
        self.default_marker_color = esp_config.get('marker_color', 'red')
        self.default_marker_alpha = float(esp_config.get('marker_alpha', 0.7))
        
        coords_from_config = bool(esp_config.get('show_coordinates', True))
        legend_from_config = bool(esp_config.get('show_legend', True))
        
        self.show_coordinates = show_coordinates if show_coordinates is not None else coords_from_config
        self.show_legend = show_legend if show_legend is not None else legend_from_config
        
    def read_event_spawns(self, xml_file_path: str) -> Dict[str, List[Tuple[float, float]]]:
        """
        Read event spawn positions from cfgeventspawns.xml file.
        
        Args:
            xml_file_path: Path to the cfgeventspawns.xml file
            
        Returns:
            Dictionary mapping event names to lists of (x, z) coordinate tuples
            
        Raises:
            FileNotFoundError: If the XML file doesn't exist
            RuntimeError: If the XML file is malformed
        """
        resolved_path = self.resolve_path(xml_file_path)
        if not Path(resolved_path).exists():
            raise FileNotFoundError(f"XML file not found: {resolved_path}")
        
        try:
            root = self.read_xml(resolved_path)
        except Exception as e:
            raise RuntimeError(f"Failed to parse XML file: {e}")
        
        events = {}
        
        for event in root.findall('event'):
            event_name = event.get('name')
            if not event_name:
                continue
                
            positions = []
            for pos in event.findall('pos'):
                try:
                    x = float(pos.get('x', 0))
                    z = float(pos.get('z', 0))
                    positions.append((x, z))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid coordinates in event {event_name}: {e}")
                    continue
            
            if positions:
                events[event_name] = positions
                logger.debug(f"Found {len(positions)} positions for event '{event_name}'")
        
        logger.info(f"Loaded {len(events)} events from {resolved_path}")
        return events
    
    def read_player_spawns(self, xml_file_path: str) -> Dict[str, List[Tuple[float, float]]]:
        """
        Read player spawn positions from cfgplayerspawnpoints.xml file.
        
        Args:
            xml_file_path: Path to the cfgplayerspawnpoints.xml file
            
        Returns:
            Dictionary mapping spawn types to lists of (x, z) coordinate tuples
            Keys will be: 'fresh', 'hop', 'travel', and optionally group names like 'hop_Balota', 'travel_Cherno'
            
        Raises:
            FileNotFoundError: If the XML file doesn't exist
            RuntimeError: If the XML file is malformed
        """
        resolved_path = self.resolve_path(xml_file_path)
        if not Path(resolved_path).exists():
            raise FileNotFoundError(f"XML file not found: {resolved_path}")
        
        try:
            root = self.read_xml(resolved_path)
        except Exception as e:
            raise RuntimeError(f"Failed to parse XML file: {e}")
        
        spawn_types = {}
        
        # Process each spawn type (fresh, hop, travel)
        for spawn_type in ['fresh', 'hop', 'travel']:
            spawn_section = root.find(spawn_type)
            if spawn_section is None:
                continue
                
            positions = []
            grouped_positions = {}
            
            # Find generator_posbubbles section
            posbubbles = spawn_section.find('generator_posbubbles')
            if posbubbles is not None:
                # Process individual pos elements (not in groups)
                for pos in posbubbles.findall('pos'):
                    try:
                        x = float(pos.get('x', 0))
                        z = float(pos.get('z', 0))
                        positions.append((x, z))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid coordinates in {spawn_type} spawn: {e}")
                        continue
                
                # Process group elements
                for group in posbubbles.findall('group'):
                    group_name = group.get('name')
                    if not group_name:
                        continue
                        
                    group_positions = []
                    for pos in group.findall('pos'):
                        try:
                            x = float(pos.get('x', 0))
                            z = float(pos.get('z', 0))
                            group_positions.append((x, z))
                            positions.append((x, z))  # Also add to main list
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Invalid coordinates in {spawn_type} group {group_name}: {e}")
                            continue
                    
                    if group_positions:
                        grouped_positions[f"{spawn_type}_{group_name}"] = group_positions
                        logger.debug(f"Found {len(group_positions)} positions for group '{spawn_type}_{group_name}'")
            
            if positions:
                spawn_types[spawn_type] = positions
                logger.debug(f"Found {len(positions)} total positions for spawn type '{spawn_type}'")
            
            # Add grouped positions to the result
            spawn_types.update(grouped_positions)
        
        logger.info(f"Loaded {len(spawn_types)} spawn type configurations from {resolved_path}")
        return spawn_types
    
    def plot_event_positions(self, map_image_path: str, event_positions: List[Tuple[float, float]], 
                           event_name: str, output_path: str = None, title: str = None) -> str:
        """
        Plot event positions on the map image.
        
        Args:
            map_image_path: Path to the map image file
            event_positions: List of (x, z) coordinate tuples
            event_name: Name of the event being plotted
            output_path: Path for output image (default: auto-generated)
            title: Custom title for the plot (None or empty string = no title)
            
        Returns:
            Path to the generated output image
            
        Raises:
            FileNotFoundError: If the map image file doesn't exist
        """
        resolved_map_path = self.resolve_path(map_image_path)
        if not Path(resolved_map_path).exists():
            raise FileNotFoundError(f"Map image not found: {resolved_map_path}")
        
        try:
            map_img = Image.open(resolved_map_path)
        except Exception as e:
            raise Exception(f"Failed to load map image: {e}")
        
        img_width, img_height = map_img.size
        
        # Convert coordinates to pixel positions
        x_pixels, y_pixels = [], []
        for x, z in event_positions:
            x_ratio = x / self.map_width
            z_ratio = z / self.map_height
            x_pixel = int(x_ratio * img_width)
            y_pixel = int((1 - z_ratio) * img_height)  # Flip Y axis for image coordinates
            x_pixels.append(x_pixel)
            y_pixels.append(y_pixel)
        
        # Create the plot
        plt.figure(figsize=(12, 12))
        plt.imshow(map_img)
        
        # Plot points with a distinct color and marker
        scatter_kwargs = {
            'color': self.default_marker_color,
            'alpha': self.default_marker_alpha,
            's': self.default_marker_size,
            'edgecolors': 'black',
            'linewidth': 0.5
        }
        
        # Add label only if legend is enabled
        if self.show_legend:
            scatter_kwargs['label'] = f'{event_name} ({len(event_positions)} spawns)'
            
        plt.scatter(x_pixels, y_pixels, **scatter_kwargs)
        
        # Add coordinate annotations for each point if enabled
        if self.show_coordinates:
            for i, (x, z) in enumerate(event_positions):
                plt.annotate(f'({x:.0f}, {z:.0f})', 
                            xy=(x_pixels[i], y_pixels[i]), 
                            xytext=(x_pixels[i] + 20, y_pixels[i] - 20), 
                            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", lw=0.5, alpha=0.8),
                            fontsize=6, ha="left", va="top",
                            arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
        
        # Set title and legend
        if title:
            # Use custom title (if not empty string)
            plt.title(title, fontsize=14, fontweight='bold')
        # If title is None or empty string, don't set any title
        
        if self.show_legend:
            plt.legend(loc='upper right')
        plt.axis('off')
        
        # Generate output filename if not provided
        if output_path is None:
            safe_event_name = "".join(c for c in event_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            base_name = f"event_spawn_map_{safe_event_name.replace(' ', '_')}"
            output_filename = self.generate_timestamped_filename(base_name, "jpg")
            output_path = os.path.join(self.output_dir, output_filename)
        else:
            output_path = self.resolve_path(output_path)
        
        # Ensure output directory exists
        self.ensure_dir(os.path.dirname(output_path))
        
        # Save the plot
        plt.savefig(output_path, dpi=self.default_output_dpi, bbox_inches='tight', facecolor='white')
        plt.close()  # Close the figure to free memory
        
        logger.info(f"Map saved to: {output_path}")
        return output_path
    
    def get_available_events(self, xml_file_path: str) -> List[str]:
        """
        Get a list of all available event names from the XML file.
        
        Args:
            xml_file_path: Path to the cfgeventspawns.xml file
            
        Returns:
            List of event names
        """
        events = self.read_event_spawns(xml_file_path)
        return list(events.keys())
    
    def get_available_player_spawns(self, xml_file_path: str) -> List[str]:
        """
        Get a list of all available player spawn types from the XML file.
        
        Args:
            xml_file_path: Path to the cfgplayerspawnpoints.xml file
            
        Returns:
            List of spawn type names (including grouped spawns)
        """
        spawns = self.read_player_spawns(xml_file_path)
        return list(spawns.keys())
    
    def run(self, xml_file_path: str, map_file_path: str, event_name: str = None, 
            spawn_type: str = None, output_path: str = None, 
            mode: str = "events", title: str = None) -> Dict[str, Any]:
        """
        Complete workflow to plot spawns from XML file onto map.
        
        Args:
            xml_file_path: Path to the XML file (cfgeventspawns.xml or cfgplayerspawnpoints.xml)
            map_file_path: Path to the map image file
            event_name: Name of the event to plot (for events mode)
            spawn_type: Name of the spawn type to plot (for player-spawns mode)
            output_path: Optional output path for the generated image
            mode: Either "events" or "player-spawns" to determine which type to plot
            title: Custom title for the plot (None or empty string = no title)
            
        Returns:
            Dictionary with results including output path and statistics
            
        Raises:
            ValueError: If the event/spawn name is not found in the XML file
        """
        if mode == "events":
            if not event_name:
                raise ValueError("event_name is required for events mode")
            
            events = self.read_event_spawns(xml_file_path)
            
            if event_name not in events:
                available_events = list(events.keys())
                raise ValueError(f"Event '{event_name}' not found. Available events: {available_events}")
            
            positions = events[event_name]
            plot_name = event_name
            logger.info(f"Plotting {len(positions)} spawn positions for event '{event_name}'")
            
        elif mode == "player-spawns":
            if not spawn_type:
                raise ValueError("spawn_type is required for player-spawns mode")
            
            spawns = self.read_player_spawns(xml_file_path)
            
            if spawn_type not in spawns:
                available_spawns = list(spawns.keys())
                raise ValueError(f"Spawn type '{spawn_type}' not found. Available spawn types: {available_spawns}")
            
            positions = spawns[spawn_type]
            plot_name = f"Player Spawns: {spawn_type}"
            logger.info(f"Plotting {len(positions)} spawn positions for player spawn type '{spawn_type}'")
            
        else:
            raise ValueError(f"Invalid mode '{mode}'. Must be 'events' or 'player-spawns'")
        
        output_file = self.plot_event_positions(map_file_path, positions, plot_name, output_path, title)
        
        return {
            "success": True,
            "mode": mode,
            "name": event_name if mode == "events" else spawn_type,
            "plot_name": plot_name,
            "spawn_count": len(positions),
            "output_file": output_file,
            "xml_file": self.resolve_path(xml_file_path),
            "map_file": self.resolve_path(map_file_path)
        }


def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(
        description="Plot event spawn positions from cfgeventspawns.xml or player spawn positions from cfgplayerspawnpoints.xml onto a map image",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Event spawns
    %(prog)s --event StaticHeliCrash
    %(prog)s --event StaticContaminatedArea --output contaminated_areas.jpg
    %(prog)s --event StaticMildrop --no-coordinates --no-legend
    %(prog)s --list-events
    
    # Player spawns  
    %(prog)s --player-spawns --spawn-type fresh
    %(prog)s --player-spawns --spawn-type hop_Balota --output hop_balota_spawns.jpg
    %(prog)s --player-spawns --list-spawns
    %(prog)s --player-spawns  # Uses default spawn type from config

Configuration:
    - paths.eventspawns_file: Path to cfgeventspawns.xml
    - paths.player_spawns_file: Path to cfgplayerspawnpoints.xml
    - event_spawn_plotter.map_file: Path to map image file
    - event_spawn_plotter.map_width/map_height: Map dimensions in meters
    - event_spawn_plotter.show_coordinates: Show coordinate labels (default: true)
    - event_spawn_plotter.show_legend: Show legend (default: true)
    - event_spawn_plotter.default_spawn_type: Default spawn type for player-spawns mode (default: fresh)
        """
    )
    
    # Add standard DayZ tool arguments
    XMLTool.add_standard_arguments(parser)
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--player-spawns", action="store_true",
                           help="Plot player spawn points instead of event spawns")
    
    # Event-specific arguments
    parser.add_argument("--event",
                       help="Name of the event to plot (for event mode)")
    parser.add_argument("--list-events", action="store_true",
                       help="List all available events in the XML file and exit")
    
    # Player spawn-specific arguments  
    parser.add_argument("--spawn-type",
                       help="Name of the spawn type to plot (for player-spawns mode, defaults to config value)")
    parser.add_argument("--list-spawns", action="store_true",
                       help="List all available player spawn types and exit")
    
    # Common arguments
    parser.add_argument("--output", 
                       help="Output path for generated image (default: auto-generated)")
    parser.add_argument("--title",
                       help="Custom title for the plot (if not specified, no title is shown; use any text for custom title)")
    parser.add_argument("--no-coordinates", action="store_true",
                       help="Disable coordinate labels on spawn points")
    parser.add_argument("--no-legend", action="store_true",
                       help="Disable legend display")
    
    args = parser.parse_args()
    
    # Load configuration
    config = XMLTool.load_config(profile=args.profile)
    
    # Determine mode
    mode = "player-spawns" if args.player_spawns else "events"
    
    # Get XML file path from config
    paths = config.get('paths', {})
    
    if mode == "events":
        xml_file_path = paths.get('eventspawns_file')
        if not xml_file_path:
            parser.error("paths.eventspawns_file must be configured")
    else:  # player-spawns
        xml_file_path = paths.get('player_spawns_file')
        if not xml_file_path:
            parser.error("paths.player_spawns_file must be configured")
    
    # Get event spawn plotter config
    esp_config = config.get('event_spawn_plotter', {})
    map_file_path = esp_config.get('map_file')
    map_width = esp_config.get('map_width', 15360)
    map_height = esp_config.get('map_height', 15360)
    
    if not map_file_path:
        parser.error("event_spawn_plotter.map_file must be configured")
    
    # Create tool instance
    tool = EventSpawnPlotterTool(
        config=config, 
        map_width=map_width, 
        map_height=map_height,
        show_coordinates=False if args.no_coordinates else None,
        show_legend=False if args.no_legend else None
    )
    
    try:
        if args.list_events:
            if mode != "events":
                parser.error("--list-events can only be used in events mode")
            # List available events
            events = tool.get_available_events(xml_file_path)
            print(f"\nAvailable events in {xml_file_path}:")
            print("=" * 50)
            for i, event in enumerate(sorted(events), 1):
                print(f"{i:3d}. {event}")
            print(f"\nTotal: {len(events)} events")
            return
        
        if args.list_spawns:
            if mode != "player-spawns":
                parser.error("--list-spawns can only be used in player-spawns mode")
            # List available player spawns
            spawns = tool.get_available_player_spawns(xml_file_path)
            print(f"\nAvailable player spawn types in {xml_file_path}:")
            print("=" * 60)
            for i, spawn in enumerate(sorted(spawns), 1):
                print(f"{i:3d}. {spawn}")
            print(f"\nTotal: {len(spawns)} spawn types")
            return
        
        # Validate required arguments based on mode
        if mode == "events":
            if not args.event:
                parser.error("--event is required for events mode")
            plot_result = tool.run(
                xml_file_path=xml_file_path,
                map_file_path=map_file_path,
                event_name=args.event,
                output_path=args.output,
                mode=mode,
                title=args.title
            )
        else:  # player-spawns
            # Get default spawn type from config if not specified
            spawn_type = args.spawn_type
            if not spawn_type:
                spawn_type = esp_config.get('default_spawn_type', 'fresh')
                logger.info(f"Using default spawn type from config: {spawn_type}")
            
            plot_result = tool.run(
                xml_file_path=xml_file_path,
                map_file_path=map_file_path,
                spawn_type=spawn_type,
                output_path=args.output,
                mode=mode,
                title=args.title
            )
        
        print(f"\nSuccess! Spawn map generated:")
        print(f"Mode: {plot_result['mode']}")
        print(f"Name: {plot_result['name']}")
        print(f"Plot title: {plot_result['plot_name']}")
        print(f"Spawn count: {plot_result['spawn_count']}")
        print(f"Output file: {plot_result['output_file']}")
        
        if args.console:
            logger.info(f"Spawn plotting completed: {plot_result}")
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
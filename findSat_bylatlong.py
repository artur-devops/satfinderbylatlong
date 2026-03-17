#!/usr/bin/env python3
"""
Satellite Beam Finder - STANDALONE VERSION
No external libraries required! Uses only built-in Python modules.
Find which satellite beams cover a given geographic point and display carrier information.
"""

import json
import sys
from typing import List, Dict, Any, Optional, Tuple, Union

# ============================================================================
# Point-in-Polygon algorithm (ray casting method)
# No external dependencies - pure Python implementation
# ============================================================================

def point_in_polygon(point_lon: float, point_lat: float, polygon: List[List[float]]) -> bool:
    """
    Check if a point is inside a polygon using the ray casting algorithm.
    
    Args:
        point_lon: Longitude of the point
        point_lat: Latitude of the point
        polygon: List of [lon, lat] points defining the polygon (closed or open)
    
    Returns:
        True if the point is inside the polygon, False otherwise
    """
    # Make sure polygon is closed (first point equals last point)
    if polygon[0] != polygon[-1]:
        polygon = polygon + [polygon[0]]
    
    inside = False
    n = len(polygon) - 1  # Last point is the same as first, so we check edges up to n-1
    
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[i + 1]
        
        # Check if the point is exactly on a vertex or edge
        # First, handle horizontal edges to avoid division by zero
        if y1 == y2:
            if y1 == point_lat and min(x1, x2) <= point_lon <= max(x1, x2):
                return True  # Point is on horizontal edge
        else:
            # Check if point is on the line segment
            if min(x1, x2) <= point_lon <= max(x1, x2) and min(y1, y2) <= point_lat <= max(y1, y2):
                # Check collinearity
                cross = (point_lon - x1) * (y2 - y1) - (point_lat - y1) * (x2 - x1)
                if abs(cross) < 1e-10:  # Point is on the edge
                    return True
        
        # Ray casting algorithm
        # Check if the edge crosses the horizontal ray at point_lat
        if ((y1 > point_lat) != (y2 > point_lat)):
            # Calculate x coordinate of intersection
            x_intersect = x1 + (point_lat - y1) * (x2 - x1) / (y2 - y1)
            if x_intersect == point_lon:
                return True  # Point is on the edge
            if x_intersect > point_lon:
                inside = not inside
    
    return inside


# ============================================================================
# Data structures and main finder class
# ============================================================================

class CarrierInfo:
    """Store carrier (transponder) information."""
    
    def __init__(self, beam_id: int, center_freq: float, polarization: str, 
                 symbol_rate: float, carrier_type: str):
        self.beam_id = beam_id
        self.center_freq = center_freq
        self.polarization = polarization
        self.symbol_rate = symbol_rate
        self.carrier_type = carrier_type
    
    def __repr__(self) -> str:
        return (f"Beam {self.beam_id}: {self.center_freq/1000000:.3f} MHz, "
                f"RX:{self.polarization}, {self.symbol_rate:,.0f} symbols/s")


class BeamInfo:
    """Store beam contour and associated carrier information."""
    
    def __init__(self, satellite_id: str, satellite_longitude: Optional[float], 
                 beam_id: int, points: List[List[float]]):
        self.satellite_id = satellite_id
        self.satellite_longitude = satellite_longitude
        self.beam_id = beam_id
        self.points = points  # Store original points for verification
        self.carriers: List[CarrierInfo] = []  # Associated carriers
    
    def add_carrier(self, carrier: CarrierInfo) -> None:
        """Add a carrier to this beam."""
        self.carriers.append(carrier)
    
    def __repr__(self) -> str:
        lon_str = f"@{self.satellite_longitude}°" if self.satellite_longitude is not None else ""
        return f"{self.satellite_id}{lon_str} - Beam {self.beam_id} ({len(self.carriers)} carriers)"


class SatelliteBeamFinder:
    """Standalone satellite beam finder with no external dependencies."""
    
    def __init__(self, json_file_path: str):
        """
        Initialize the finder by loading and processing satellite data.
        
        Args:
            json_file_path: Path to the JSON file with satellite configuration
        """
        self.json_file_path = json_file_path
        self.beams: Dict[int, BeamInfo] = {}  # Index by beam_id for quick lookup
        self.beam_list: List[BeamInfo] = []  # List for iteration
        self.error_count = 0
        self.warning_count = 0
        self.load_data()
    
    def load_data(self) -> None:
        """Load satellite data from JSON file and extract beam polygons and carriers."""
        print(f"📂 Loading data from: {self.json_file_path}")
        
        satellites = self._load_satellite_data()
        if satellites:
            self._extract_all_beams(satellites)
            self._link_carriers_to_beams(satellites)
            print(f"✓ Successfully loaded {len(self.beam_list)} beam contours with carriers")
            if self.warning_count > 0:
                print(f"⚠️  Warnings: {self.warning_count} (invalid contours skipped)")
            if self.error_count > 0:
                print(f"✗ Errors: {self.error_count}")
        else:
            print("✗ Failed to load satellite data")
            sys.exit(1)
    
    def _load_satellite_data(self) -> Optional[List[Dict]]:
        """Load and parse the JSON file."""
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("CONSTELLATION", {}).get("SATELLITES", [])
        except FileNotFoundError:
            print(f"✗ ERROR: File '{self.json_file_path}' not found!")
            print("  Please make sure the JSON file is in the same directory as this script.")
            return None
        except json.JSONDecodeError as e:
            print(f"✗ ERROR: Invalid JSON format - {e}")
            return None
    
    def _extract_all_beams(self, satellites: List[Dict]) -> None:
        """Extract beam contours from all satellites."""
        for sat in satellites:
            self._extract_beams_from_satellite(sat)
    
    def _extract_beams_from_satellite(self, satellite: Dict) -> None:
        """
        Extract all beam contours from a single satellite.
        
        Args:
            satellite: Dictionary containing satellite data
        """
        sat_id = satellite.get("satellite_id", "Unknown")
        sat_lon = satellite.get("longitude", None)
        
        beams = satellite.get("BEAM", [])
        if not beams:
            return
        
        for beam in beams:
            beam_id = beam.get("beam_id")
            if beam_id is None:
                continue
                
            contours = beam.get("CONTOUR", [])
            
            for contour_idx, contour in enumerate(contours):
                # Process only polygon type contours (type=1)
                if contour.get("type") == 1:
                    points = contour.get("points", [])
                    self._validate_and_store_beam(sat_id, sat_lon, beam_id, contour_idx, points)
    
    def _validate_and_store_beam(self, sat_id: str, sat_lon: Optional[float], 
                                 beam_id: int, contour_idx: int, points: List[List[float]]) -> None:
        """
        Validate contour points and store as a beam.
        
        Args:
            sat_id: Satellite identifier
            sat_lon: Satellite longitude
            beam_id: Beam identifier
            contour_idx: Contour index within the beam
            points: List of [lon, lat] points defining the contour
        """
        if len(points) < 3:
            self.warning_count += 1
            return  # Not enough points to form a polygon
        
        # Check if all points are valid numbers
        for i, point in enumerate(points):
            if len(point) != 2:
                self.warning_count += 1
                return
            try:
                float(point[0])
                float(point[1])
            except (ValueError, TypeError):
                self.warning_count += 1
                return
        
        # Create or update beam
        if beam_id not in self.beams:
            beam_info = BeamInfo(
                satellite_id=sat_id,
                satellite_longitude=sat_lon,
                beam_id=beam_id,
                points=points
            )
            self.beams[beam_id] = beam_info
            self.beam_list.append(beam_info)
        else:
            # For beams with multiple contours, we keep the first one
            # (assuming they represent the same coverage area)
            pass
    
    def _link_carriers_to_beams(self, satellites: List[Dict]) -> None:
        """Link carrier information to their respective beams."""
        carrier_count = 0
        
        for satellite in satellites:
            carriers = satellite.get("CARRIER", [])
            for carrier in carriers:
                beam_id = carrier.get("beam_id")
                if beam_id is None or beam_id not in self.beams:
                    continue
                
                # Extract carrier information
                center_freq = carrier.get("center_freq", 0)
                polarization = carrier.get("polarization", "Unknown")
                symbol_rate = carrier.get("symbol_rate", 0)
                carrier_type = carrier.get("carrier_type", "Unknown")
                
                # Create and link carrier
                carrier_info = CarrierInfo(
                    beam_id=beam_id,
                    center_freq=center_freq,
                    polarization=polarization,
                    symbol_rate=symbol_rate,
                    carrier_type=carrier_type
                )
                
                self.beams[beam_id].add_carrier(carrier_info)
                carrier_count += 1
        
        print(f"✓ Linked {carrier_count} carriers to beams")
    
    def find_beams_at_point(self, longitude: float, latitude: float) -> List[BeamInfo]:
        """
        Find all beams that contain the specified point.
        
        Args:
            longitude: Point longitude (-180 to 180)
            latitude: Point latitude (-90 to 90)
        
        Returns:
            List of BeamInfo objects for matching beams
        """
        results = []
        
        for beam in self.beam_list:
            if point_in_polygon(longitude, latitude, beam.points):
                results.append(beam)
        
        return results
    
    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about loaded data."""
        satellites = set(beam.satellite_id for beam in self.beam_list)
        total_carriers = sum(len(beam.carriers) for beam in self.beam_list)
        return {
            "satellites": len(satellites),
            "beams": len(self.beam_list),
            "carriers": total_carriers
        }


# ============================================================================
# User interface functions
# ============================================================================

def clear_screen():
    """Clear the terminal screen."""
    import os
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print application header."""
    print("=" * 80)
    print("                 SATELLITE BEAM FINDER - STANDALONE")
    print("=" * 80)
    print("  No external libraries required! Find beams covering your location")
    print("  and see all available carriers with frequencies and polarization.")
    print("\n  📍 IMPORTANT: Enter coordinates in correct order:")
    print("     LONGITUDE = East/West position (-180 to 180)")
    print("     LATITUDE  = North/South position (-90 to 90)")
    print("=" * 80)


def print_help():
    """Print help information."""
    print("\n📖 HOW TO USE:")
    print("  • Enter LONGITUDE first (example: 19.95 for 19.95°E)")
    print("  • Enter LATITUDE second (example: 54.65 for 54.65°N)")
    print("  • Type 'exit', 'quit', or press Ctrl+C to exit")
    print("  • Type 'stats' to see loaded data statistics")
    print("  • Type 'list' to list all available satellites")
    print()


def validate_coordinate(value: str, coord_type: str) -> Optional[float]:
    """
    Validate and parse a coordinate string.
    
    Args:
        value: Input string
        coord_type: 'longitude' or 'latitude' for error messages
    
    Returns:
        Parsed float value or None if invalid
    """
    try:
        val = float(value)
        
        if coord_type == 'longitude':
            if -180 <= val <= 180:
                return val
            else:
                print(f"⚠️  Longitude must be between -180 and 180 (got {val})")
                return None
        else:  # latitude
            if -90 <= val <= 90:
                return val
            else:
                print(f"⚠️  Latitude must be between -90 and 90 (got {val})")
                return None
                
    except ValueError:
        print(f"⚠️  Please enter a valid number for {coord_type}")
        return None


def format_frequency(freq_hz: float) -> str:
    """Format frequency in Hz to MHz or GHz for display."""
    if freq_hz >= 1e9:
        return f"{freq_hz/1e9:.3f} GHz"
    else:
        return f"{freq_hz/1e6:.3f} MHz"


def format_symbol_rate(sr_hz: float) -> str:
    """Format symbol rate in Hz to symbols/s with thousand separators."""
    return f"{sr_hz:,.0f} symbols/s"


def display_beam_results(beams: List[BeamInfo], lon: float, lat: float) -> None:
    """
    Display beam search results with carrier information.
    
    Args:
        beams: List of matching beams
        lon: Longitude of search point
        lat: Latitude of search point
    """
    print("\n" + "=" * 80)
    if beams:
        print(f"✅ FOUND {len(beams)} BEAM(S) covering ({lon}°, {lat}°):\n")
        
        for i, beam in enumerate(beams, 1):
            lon_str = f" (at {beam.satellite_longitude}°)" if beam.satellite_longitude is not None else ""
            print(f"   {i}. 📡 {beam.satellite_id}{lon_str}")
            print(f"      └─ Beam ID: {beam.beam_id}")
            
            if beam.carriers:
                print(f"         Available carriers:")
                for j, carrier in enumerate(beam.carriers, 1):
                    freq_str = format_frequency(carrier.center_freq)
                    sr_str = format_symbol_rate(carrier.symbol_rate)
                    print(f"            {j}. {freq_str} | RX:{carrier.polarization} | {sr_str} | {carrier.carrier_type}")
            else:
                print(f"         No carrier information available for this beam")
            print()
    else:
        print(f"❌ NO BEAMS found covering ({lon}°, {lat}°)")
        print("   The point may be outside all satellite coverage areas.")
    print("=" * 80)


def main():
    """Main program loop."""
    clear_screen()
    print_header()
    
    # Initialize the finder
    finder = SatelliteBeamFinder("CONSTELLATION_OPT.json")
    
    # Show initial statistics
    stats = finder.get_statistics()
    print(f"\n📊 LOADED DATA: {stats['satellites']} satellites, {stats['beams']} beams, {stats['carriers']} carriers")
    
    print_help()
    
    # Main interaction loop
    while True:
        try:
            # Get input
            print("\n" + "-" * 50)
            print("📌 Enter coordinates (LONGITUDE first, then LATITUDE):")
            lon_input = input("   LONGITUDE (-180 to 180) > ").strip().lower()
            
            # Handle special commands
            if lon_input in ['exit', 'quit', 'q']:
                break
            if lon_input == 'stats':
                stats = finder.get_statistics()
                print(f"\n📊 Statistics: {stats['satellites']} satellites, {stats['beams']} beams, {stats['carriers']} carriers")
                continue
            if lon_input == 'list':
                satellites = sorted(set(beam.satellite_id for beam in finder.beam_list))
                print(f"\n📡 Available satellites ({len(satellites)}):")
                for i, sat in enumerate(satellites, 1):
                    # Count beams for this satellite
                    beam_count = sum(1 for beam in finder.beam_list if beam.satellite_id == sat)
                    print(f"   {i:2d}. {sat} ({beam_count} beams)")
                continue
            if lon_input == 'help':
                print_help()
                continue
            
            lat_input = input("   LATITUDE  (-90 to 90)   > ").strip().lower()
            
            if lat_input in ['exit', 'quit', 'q']:
                break
            
            # Validate coordinates
            lon = validate_coordinate(lon_input, 'longitude')
            if lon is None:
                continue
                
            lat = validate_coordinate(lat_input, 'latitude')
            if lat is None:
                continue
            
            # Find matching beams
            print(f"\n🔍 Searching for beams covering longitude {lon}°, latitude {lat}°...")
            results = finder.find_beams_at_point(lon, lat)
            
            # Display results with carrier information
            display_beam_results(results, lon, lat)
            
        except KeyboardInterrupt:
            print("\n\n👋 Exiting...")
            break
    
    print("\nThank you for using Satellite Beam Finder!")
    print("=" * 80)


if __name__ == "__main__":
    main()
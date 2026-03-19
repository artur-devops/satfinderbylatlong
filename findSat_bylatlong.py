#!/usr/bin/env python3
"""
Satellite Beam Finder - STANDALONE VERSION
FIXED: Using simple 2D ray casting algorithm
"""

import json
import sys
from typing import List, Dict, Any, Optional, Tuple, Union

# ============================================================================
# SIMPLE 2D RAY CASTING ALGORITHM - THIS WORKS!
# ============================================================================

def point_in_polygon(point_lon: float, point_lat: float, polygon: List[List[float]]) -> bool:
    """
    SIMPLE RAY CASTING ALGORITHM (2D)
    Properly handles longitude and latitude
    
    Args:
        point_lon: Longitude of the point (-180 to 180)
        point_lat: Latitude of the point (-90 to 90)
        polygon: List of [lon, lat] points defining the polygon
    
    Returns:
        True if point is inside polygon, False otherwise
    """
    # First, do a quick bounding box check
    min_lon = min(p[0] for p in polygon)
    max_lon = max(p[0] for p in polygon)
    min_lat = min(p[1] for p in polygon)
    max_lat = max(p[1] for p in polygon)
    
    # Quick reject - if point is outside bounding box, it's outside polygon
    if point_lat < min_lat or point_lat > max_lat:
        return False
    
    # Check if polygon crosses the 180° meridian
    crosses_180 = False
    for i in range(len(polygon)):
        lon1, _ = polygon[i]
        lon2, _ = polygon[(i + 1) % len(polygon)]
        # If one longitude is near 180°E and another near 180°W
        if (lon1 > 150 and lon2 < -150) or (lon1 < -150 and lon2 > 150):
            crosses_180 = True
            break
    
    # If polygon crosses 180°, normalize all longitudes to 0-360 range
    if crosses_180:
        normalized_polygon = []
        for lon, lat in polygon:
            if lon < 0:
                normalized_polygon.append([lon + 360, lat])
            else:
                normalized_polygon.append([lon, lat])
        
        # Normalize point longitude
        check_lon = point_lon if point_lon >= 0 else point_lon + 360
        check_lat = point_lat
    else:
        normalized_polygon = polygon
        check_lon = point_lon
        check_lat = point_lat
    
    # Ray casting algorithm
    inside = False
    n = len(normalized_polygon)
    
    for i in range(n):
        x1, y1 = normalized_polygon[i]
        x2, y2 = normalized_polygon[(i + 1) % n]
        
        # Check if the edge crosses the horizontal line at point_lat
        # Edge must span vertically across the point's latitude
        if ((y1 > check_lat) != (y2 > check_lat)):
            # Calculate x coordinate of intersection
            if y2 != y1:  # Avoid division by zero
                x_intersect = x1 + (check_lat - y1) * (x2 - x1) / (y2 - y1)
                
                # Count intersections to the right of the point
                if x_intersect > check_lon:
                    inside = not inside
    
    return inside


# ============================================================================
# Data structures (same as before but with FIXED coordinate handling)
# ============================================================================

class CarrierInfo:
    """Store carrier (transponder) information."""
    
    def __init__(self, beam_id: int, center_freq: float, polarization: str, 
                 symbol_rate: float, carrier_type: str, satellite_id: str = ""):
        self.beam_id = beam_id
        self.center_freq = center_freq
        self.polarization = polarization
        self.symbol_rate = symbol_rate
        self.carrier_type = carrier_type
        self.satellite_id = satellite_id


class BeamInfo:
    """Store beam contour and associated carrier information."""
    
    def __init__(self, satellite_id: str, satellite_longitude: Optional[float], 
                 beam_id: int, points: List[List[float]]):
        self.satellite_id = satellite_id
        self.satellite_longitude = satellite_longitude
        self.beam_id = beam_id
        self.points = points  # Now in [lon, lat] format
        self.carriers: List[CarrierInfo] = []
    
    def add_carrier(self, carrier: CarrierInfo) -> None:
        """Add a carrier to this beam."""
        self.carriers.append(carrier)
    
    def get_bounding_box(self) -> Tuple[float, float, float, float]:
        """Return (min_lon, max_lon, min_lat, max_lat)"""
        lons = [p[0] for p in self.points]
        lats = [p[1] for p in self.points]
        return (min(lons), max(lons), min(lats), max(lats))


class SatelliteBeamFinder:
    """Satellite beam finder with FIXED geometry handling."""
    
    def __init__(self, json_file_path: str):
        self.json_file_path = json_file_path
        self.beams: Dict[str, BeamInfo] = {}
        self.beam_list: List[BeamInfo] = []
        self.satellites: Dict[str, Dict] = {}
        self.error_count = 0
        self.warning_count = 0
        self.load_data()
    
    def load_data(self) -> None:
        """Load satellite data from JSON file."""
        print(f"📂 Loading data from: {self.json_file_path}")
        
        satellites = self._load_satellite_data()
        if satellites:
            self._extract_satellite_info(satellites)
            self._extract_all_beams(satellites)
            self._link_carriers_to_beams(satellites)
            print(f"✓ Loaded {len(self.beam_list)} beam contours")
            if self.warning_count > 0:
                print(f"⚠️  Warnings: {self.warning_count}")
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
            return None
        except json.JSONDecodeError as e:
            print(f"✗ ERROR: Invalid JSON format - {e}")
            return None
    
    def _extract_satellite_info(self, satellites: List[Dict]) -> None:
        """Extract satellite information for later use."""
        for satellite in satellites:
            sat_id = satellite.get("satellite_id", "Unknown")
            sat_lon = satellite.get("longitude", None)
            self.satellites[sat_id] = {
                'longitude': sat_lon,
                'satellite_id': sat_id
            }
    
    def _extract_all_beams(self, satellites: List[Dict]) -> None:
        """Extract beam contours from all satellites."""
        for sat in satellites:
            self._extract_beams_from_satellite(sat)
    
    def _extract_beams_from_satellite(self, satellite: Dict) -> None:
        """
        Extract all beam contours from a single satellite.
        FIXED: Coordinates in JSON are [LATITUDE, LONGITUDE]
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
            
            for contour in contours:
                # Process only polygon type contours (type=1)
                if contour.get("type") == 1:
                    points = contour.get("points", [])
                    self._validate_and_store_beam(sat_id, sat_lon, beam_id, points)
    
    def _validate_and_store_beam(self, sat_id: str, sat_lon: Optional[float], 
                                 beam_id: int, points: List[List[float]]) -> None:
        """
        Validate contour points and store as a beam.
        FIXED: JSON stores [LATITUDE, LONGITUDE], convert to [LONGITUDE, LATITUDE]
        """
        if len(points) < 3:
            self.warning_count += 1
            return
        
        # Convert from [LATITUDE, LONGITUDE] to [LONGITUDE, LATITUDE]
        converted_points = []
        for point in points:
            if len(point) != 2:
                self.warning_count += 1
                return
            try:
                lat = float(point[0])  # First value is latitude
                lon = float(point[1])  # Second value is longitude
                
                # Basic validation
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    self.warning_count += 1
                    return
                
                # Store as [LONGITUDE, LATITUDE]
                converted_points.append([lon, lat])
                
            except (ValueError, TypeError):
                self.warning_count += 1
                return
        
        # Use satellite+beam_id as unique key
        unique_key = f"{sat_id}_{beam_id}"
        
        if unique_key not in self.beams:
            beam_info = BeamInfo(
                satellite_id=sat_id,
                satellite_longitude=sat_lon,
                beam_id=beam_id,
                points=converted_points
            )
            self.beams[unique_key] = beam_info
            self.beam_list.append(beam_info)
    
    def _link_carriers_to_beams(self, satellites: List[Dict]) -> None:
        """Link carrier information to their respective beams."""
        carrier_count = 0
        
        for satellite in satellites:
            sat_id = satellite.get("satellite_id", "Unknown")
            carriers = satellite.get("CARRIER", [])
            
            for carrier in carriers:
                beam_id = carrier.get("beam_id")
                if beam_id is None:
                    continue
                
                unique_key = f"{sat_id}_{beam_id}"
                
                if unique_key not in self.beams:
                    continue
                
                center_freq = carrier.get("center_freq", 0)
                polarization = carrier.get("polarization", "Unknown")
                symbol_rate = carrier.get("symbol_rate", 0)
                carrier_type = carrier.get("carrier_type", "Unknown")
                
                carrier_info = CarrierInfo(
                    beam_id=beam_id,
                    center_freq=center_freq,
                    polarization=polarization,
                    symbol_rate=symbol_rate,
                    carrier_type=carrier_type,
                    satellite_id=sat_id
                )
                
                self.beams[unique_key].add_carrier(carrier_info)
                carrier_count += 1
        
        print(f"✓ Linked {carrier_count} carriers to beams")
    
    def find_beams_at_point(self, longitude: float, latitude: float) -> List[BeamInfo]:
        """
        Find all beams that contain the specified point.
        Uses SIMPLE 2D ray casting algorithm.
        """
        results = []
        
        # For debugging, print first few beams
        print("\nDEBUG: First 3 beams loaded:")
        for i, beam in enumerate(self.beam_list[:3]):
            bbox = beam.get_bounding_box()
            print(f"  {i+1}. {beam.satellite_id} beam {beam.beam_id}:")
            print(f"     Bounding box: lon [{bbox[0]:.1f}°, {bbox[1]:.1f}°], lat [{bbox[2]:.1f}°, {bbox[3]:.1f}°]")
            print(f"     First point: [lon={beam.points[0][0]:.1f}°, lat={beam.points[0][1]:.1f}°]")
        
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
# User interface functions (same as before)
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
    """Validate and parse a coordinate string."""
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
    """Display beam search results with carrier information."""
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
            print("\n" + "-" * 50)
            print("📌 Enter coordinates (LONGITUDE first, then LATITUDE):")
            lon_input = input("   LONGITUDE (-180 to 180) > ").strip().lower()
            
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
                    beam_count = sum(1 for beam in finder.beam_list if beam.satellite_id == sat)
                    lon = next((beam.satellite_longitude for beam in finder.beam_list if beam.satellite_id == sat), None)
                    lon_str = f" at {lon}°" if lon is not None else ""
                    print(f"   {i:2d}. {sat}{lon_str} ({beam_count} beams)")
                continue
            if lon_input == 'help':
                print_help()
                continue
            
            lat_input = input("   LATITUDE  (-90 to 90)   > ").strip().lower()
            
            if lat_input in ['exit', 'quit', 'q']:
                break
            
            lon = validate_coordinate(lon_input, 'longitude')
            if lon is None:
                continue
                
            lat = validate_coordinate(lat_input, 'latitude')
            if lat is None:
                continue
            
            print(f"\n🔍 Searching for beams covering longitude {lon}°, latitude {lat}°...")
            results = finder.find_beams_at_point(lon, lat)
            
            display_beam_results(results, lon, lat)
            
        except KeyboardInterrupt:
            print("\n\n👋 Exiting...")
            break
    
    print("\nThank you for using Satellite Beam Finder!")
    print("=" * 80)


if __name__ == "__main__":
    main()
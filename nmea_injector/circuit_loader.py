#!/usr/bin/env python3
"""
Circuit loader for F1 circuits from GeoJSON data.

This module handles loading and parsing F1 circuit data from the circuits.geojson file
and provides utilities for working with circuit waypoints.
"""

import json
import os
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class CircuitInfo:
    """Information about an F1 circuit."""
    id: str
    name: str
    location: str
    opened: int
    first_gp: int
    length: int  # meters
    altitude: int  # meters above sea level
    coordinates: List[Tuple[float, float]]  # (longitude, latitude) pairs


class CircuitLoader:
    """Loads and manages F1 circuit data."""
    
    def __init__(self, geojson_path: Optional[str] = None):
        """Initialize circuit loader.
        
        Args:
            geojson_path: Path to circuits.geojson file. If None, uses default path.
        """
        if geojson_path is None:
            # Default to circuits.geojson in the same directory as this module
            geojson_path = os.path.join(os.path.dirname(__file__), 'circuits.geojson')
        
        self.geojson_path = geojson_path
        self._circuits: Dict[str, CircuitInfo] = {}
        self._loaded = False
    
    def load_circuits(self) -> None:
        """Load circuits from GeoJSON file."""
        if self._loaded:
            return
            
        try:
            with open(self.geojson_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if data.get('type') != 'FeatureCollection':
                raise ValueError("Invalid GeoJSON format: expected FeatureCollection")
            
            for feature in data.get('features', []):
                if feature.get('type') != 'Feature':
                    continue
                
                properties = feature.get('properties', {})
                geometry = feature.get('geometry', {})
                
                if geometry.get('type') != 'LineString':
                    continue
                
                # Extract circuit information
                circuit_id = properties.get('id', '')
                name = properties.get('Name', '')
                location = properties.get('Location', '')
                opened = properties.get('opened', 0)
                first_gp = properties.get('firstgp', 0)
                length = properties.get('length', 0)
                altitude = properties.get('altitude', 0)
                
                # Extract coordinates (convert from [lon, lat] to (lon, lat) tuples)
                coordinates = []
                for coord in geometry.get('coordinates', []):
                    if len(coord) >= 2:
                        # GeoJSON uses [longitude, latitude] order
                        coordinates.append((coord[0], coord[1]))
                
                if coordinates and circuit_id and name:
                    circuit = CircuitInfo(
                        id=circuit_id,
                        name=name,
                        location=location,
                        opened=opened,
                        first_gp=first_gp,
                        length=length,
                        altitude=altitude,
                        coordinates=coordinates
                    )
                    self._circuits[circuit_id] = circuit
            
            self._loaded = True
            print(f"Loaded {len(self._circuits)} F1 circuits from {self.geojson_path}")
            
        except Exception as e:
            print(f"Error loading circuits: {e}")
            self._circuits = {}
    
    def get_circuits(self) -> Dict[str, CircuitInfo]:
        """Get all available circuits.
        
        Returns:
            Dictionary mapping circuit IDs to CircuitInfo objects.
        """
        if not self._loaded:
            self.load_circuits()
        return self._circuits.copy()
    
    def get_circuit(self, circuit_id: str) -> Optional[CircuitInfo]:
        """Get a specific circuit by ID.
        
        Args:
            circuit_id: The circuit ID (e.g., 'gb-1948' for Silverstone)
            
        Returns:
            CircuitInfo object or None if not found.
        """
        if not self._loaded:
            self.load_circuits()
        return self._circuits.get(circuit_id)
    
    def get_circuit_names(self) -> List[Tuple[str, str]]:
        """Get list of circuit names for display.
        
        Returns:
            List of (circuit_id, display_name) tuples sorted by location.
        """
        if not self._loaded:
            self.load_circuits()
        
        circuits = []
        for circuit_id, circuit in self._circuits.items():
            display_name = f"{circuit.name} ({circuit.location})"
            circuits.append((circuit_id, display_name))
        
        # Sort by location, then by name
        circuits.sort(key=lambda x: (self._circuits[x[0]].location, self._circuits[x[0]].name))
        return circuits
    
    def convert_to_waypoints(self, circuit_id: str) -> List[Tuple[float, float]]:
        """Convert circuit coordinates to waypoint format.
        
        Args:
            circuit_id: The circuit ID
            
        Returns:
            List of (latitude, longitude) tuples for waypoint targeting.
            Returns empty list if circuit not found.
        """
        circuit = self.get_circuit(circuit_id)
        if not circuit:
            return []
        
        # Convert from (longitude, latitude) to (latitude, longitude) format
        # and optionally downsample for reasonable waypoint count
        waypoints = []
        coords = circuit.coordinates
        
        # For very detailed circuits, take every Nth point to avoid too many waypoints
        step = max(1, len(coords) // 50)  # Aim for ~50 waypoints maximum
        
        for i in range(0, len(coords), step):
            lon, lat = coords[i]
            waypoints.append((lat, lon))
        
        # Ensure we include the last point if it wasn't included by stepping
        if len(coords) > 1 and len(waypoints) > 0:
            last_coord = coords[-1]
            last_waypoint = waypoints[-1]
            # Check if the last coordinate is different from the last waypoint
            if abs(last_coord[1] - last_waypoint[0]) > 1e-6 or abs(last_coord[0] - last_waypoint[1]) > 1e-6:
                lon, lat = coords[-1]
                waypoints.append((lat, lon))
        
        return waypoints


# Global circuit loader instance
_circuit_loader = None


def get_circuit_loader() -> CircuitLoader:
    """Get the global circuit loader instance."""
    global _circuit_loader
    if _circuit_loader is None:
        _circuit_loader = CircuitLoader()
    return _circuit_loader


def get_available_circuits() -> List[Tuple[str, str]]:
    """Get list of available F1 circuits.
    
    Returns:
        List of (circuit_id, display_name) tuples.
    """
    return get_circuit_loader().get_circuit_names()


def get_circuit_waypoints(circuit_id: str) -> List[Tuple[float, float]]:
    """Get waypoints for a specific F1 circuit.
    
    Args:
        circuit_id: The circuit ID
        
    Returns:
        List of (latitude, longitude) waypoints.
    """
    return get_circuit_loader().convert_to_waypoints(circuit_id)


if __name__ == "__main__":
    # Test the circuit loader
    loader = CircuitLoader()
    circuits = loader.get_circuits()
    
    print(f"\nFound {len(circuits)} F1 circuits:")
    for circuit_id, circuit in circuits.items():
        print(f"- {circuit.name} ({circuit.location}) - {len(circuit.coordinates)} points")
    
    # Test waypoint conversion for Silverstone
    silverstone_waypoints = get_circuit_waypoints('gb-1948')
    if silverstone_waypoints:
        print(f"\nSilverstone waypoints: {len(silverstone_waypoints)} points")
        print(f"First waypoint: {silverstone_waypoints[0]}")
        print(f"Last waypoint: {silverstone_waypoints[-1]}")
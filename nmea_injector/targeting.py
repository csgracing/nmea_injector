"""
Abstract base classes and interfaces for targeting strategies.

This module defines the core targeting interface that all targeting
implementations must follow, ensuring consistent behavior across
linear, circular, and waypoint targeting modes.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional, Dict, Any, List
import math


# Export all targeting classes for easy importing
__all__ = [
    'TargetingStrategy',
    'StaticTargeting', 
    'LinearTargeting',
    'CircularTargeting',
    'WaypointTargeting',
    'calculate_distance_km',
    'calculate_bearing',
    'move_position'
]


class TargetingStrategy(ABC):
    """
    Abstract base class for all targeting strategies.
    
    This interface defines the contract that all targeting implementations
    must follow to work with the NMEA simulator.
    """
    
    def __init__(self):
        self._is_active = True
        self._total_distance_traveled = 0.0
        self._start_time = None
        
    @abstractmethod
    def get_next_position(self, current_lat: float, current_lon: float, 
                         current_heading: float, duration_seconds: float,
                         current_speed_kph: float) -> Tuple[float, float, float, float]:
        """
        Calculate the next position and heading based on current state.
        
        Args:
            current_lat: Current latitude in decimal degrees
            current_lon: Current longitude in decimal degrees  
            current_heading: Current heading in degrees (0-360)
            duration_seconds: Time step duration in seconds
            current_speed_kph: Current speed in km/h
            
        Returns:
            Tuple of (new_lat, new_lon, new_heading, new_speed_kph)
        """
        pass
    
    @abstractmethod
    def is_complete(self) -> bool:
        """
        Check if the targeting strategy has completed its objective.
        
        Returns:
            True if targeting is complete, False otherwise
        """
        pass
    
    @abstractmethod
    def reset(self):
        """
        Reset the targeting strategy to its initial state.
        """
        pass
    
    @abstractmethod
    def get_progress(self) -> float:
        """
        Get the current progress as a percentage (0.0 to 1.0).
        
        Returns:
            Progress percentage, or -1.0 if progress is not applicable
        """
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status information for display/debugging.
        
        Returns:
            Dictionary containing status information
        """
        pass
    
    def set_active(self, active: bool):
        """Enable or disable this targeting strategy."""
        self._is_active = active
        
    def is_active(self) -> bool:
        """Check if this targeting strategy is currently active."""
        return self._is_active
    
    def get_distance_traveled(self) -> float:
        """Get total distance traveled in kilometers."""
        return self._total_distance_traveled
    
    def _add_distance(self, distance_km: float):
        """Internal method to track total distance traveled."""
        self._total_distance_traveled += distance_km


class StaticTargeting(TargetingStrategy):
    """
    A simple targeting strategy that keeps the GPS position static.
    This is useful for testing or when no movement is desired.
    """
    
    def __init__(self):
        super().__init__()
        
    def get_next_position(self, current_lat: float, current_lon: float,
                         current_heading: float, duration_seconds: float,
                         current_speed_kph: float) -> Tuple[float, float, float, float]:
        """Keep position static - no movement."""
        return current_lat, current_lon, current_heading, 0.0
    
    def is_complete(self) -> bool:
        """Static targeting never completes."""
        return False
    
    def reset(self):
        """Nothing to reset for static targeting."""
        pass
        
    def get_progress(self) -> float:
        """Progress not applicable for static targeting."""
        return -1.0
        
    def get_status(self) -> Dict[str, Any]:
        """Return status information."""
        return {
            "type": "static",
            "active": self._is_active,
            "description": "GPS position held static"
        }


def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on Earth.
    
    Args:
        lat1, lon1: First point coordinates in decimal degrees
        lat2, lon2: Second point coordinates in decimal degrees
        
    Returns:
        Distance in kilometers
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    # Earth's radius in kilometers
    earth_radius_km = 6371.0
    return earth_radius_km * c


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the initial bearing from point 1 to point 2.
    
    Args:
        lat1, lon1: Starting point coordinates in decimal degrees
        lat2, lon2: Ending point coordinates in decimal degrees
        
    Returns:
        Bearing in degrees (0-360)
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlon = lon2_rad - lon1_rad
    
    y = math.sin(dlon) * math.cos(lat2_rad)
    x = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon))
    
    bearing = math.atan2(y, x)
    bearing = math.degrees(bearing)
    
    # Normalize to 0-360 degrees
    return (bearing + 360) % 360


def move_position(lat: float, lon: float, bearing: float, distance_km: float) -> Tuple[float, float]:
    """
    Move a position by a given distance and bearing.
    
    Args:
        lat, lon: Starting position in decimal degrees
        bearing: Bearing in degrees (0-360)
        distance_km: Distance to move in kilometers
        
    Returns:
        Tuple of (new_lat, new_lon) in decimal degrees
    """
    # Earth's radius in kilometers
    earth_radius_km = 6371.0
    
    # Convert to radians
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing)
    
    # Calculate new position
    angular_distance = distance_km / earth_radius_km
    
    new_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(angular_distance) +
        math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing_rad)
    )
    
    new_lon_rad = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat_rad),
        math.cos(angular_distance) - math.sin(lat_rad) * math.sin(new_lat_rad)
    )
    
    return math.degrees(new_lat_rad), math.degrees(new_lon_rad)


class LinearTargeting(TargetingStrategy):
    """
    Linear targeting strategy that moves GPS position toward a single target point.
    
    This replicates and enhances the original nmeasim targeting behavior,
    with options for what to do when reaching the target.
    """
    
    def __init__(self, target_lat: float, target_lon: float, 
                 speed_kph: float = 50.0, stop_at_target: bool = True,
                 arrival_threshold_meters: float = 10.0):
        """
        Initialize linear targeting.
        
        Args:
            target_lat: Target latitude in decimal degrees
            target_lon: Target longitude in decimal degrees
            speed_kph: Travel speed in km/h
            stop_at_target: If True, stop when reaching target; if False, continue past
            arrival_threshold_meters: Distance threshold to consider "arrived" at target
        """
        super().__init__()
        self.target_lat = target_lat
        self.target_lon = target_lon
        self.speed_kph = speed_kph
        self.stop_at_target = stop_at_target
        self.arrival_threshold_meters = arrival_threshold_meters
        
        self._initial_distance_km = None
        self._arrived = False
        
    def get_next_position(self, current_lat: float, current_lon: float,
                         current_heading: float, duration_seconds: float,
                         current_speed_kph: float) -> Tuple[float, float, float, float]:
        """Calculate next position moving toward target."""
        
        if not self._is_active:
            return current_lat, current_lon, current_heading, 0.0
            
        # Calculate distance to target
        distance_to_target_km = calculate_distance_km(
            current_lat, current_lon, self.target_lat, self.target_lon
        )
        
        # Store initial distance for progress calculation
        if self._initial_distance_km is None:
            self._initial_distance_km = distance_to_target_km
            
        # Check if we've arrived
        distance_to_target_m = distance_to_target_km * 1000
        if distance_to_target_m <= self.arrival_threshold_meters:
            self._arrived = True
            if self.stop_at_target:
                return current_lat, current_lon, current_heading, 0.0
        
        # Calculate bearing to target
        target_bearing = calculate_bearing(
            current_lat, current_lon, self.target_lat, self.target_lon
        )
        
        # Calculate distance to travel this step
        distance_this_step_km = (self.speed_kph / 3600.0) * duration_seconds
        
        # Don't overshoot if stopping at target
        if self.stop_at_target and distance_this_step_km > distance_to_target_km:
            distance_this_step_km = distance_to_target_km
            
        # Move toward target
        new_lat, new_lon = move_position(
            current_lat, current_lon, target_bearing, distance_this_step_km
        )
        
        # Track total distance
        self._add_distance(distance_this_step_km)
        
        return new_lat, new_lon, target_bearing, self.speed_kph
    
    def is_complete(self) -> bool:
        """Check if we've arrived at the target (only relevant if stop_at_target=True)."""
        return self._arrived and self.stop_at_target
    
    def reset(self):
        """Reset targeting to initial state."""
        self._initial_distance_km = None
        self._arrived = False
        self._total_distance_traveled = 0.0
        
    def get_progress(self) -> float:
        """Get progress toward target as percentage (0.0 to 1.0)."""
        if self._initial_distance_km is None or self._initial_distance_km == 0:
            return 0.0
            
        current_distance_km = calculate_distance_km(
            0, 0, self.target_lat, self.target_lon  # This needs current position
        )
        
        progress = 1.0 - (current_distance_km / self._initial_distance_km)
        return max(0.0, min(1.0, progress))
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status information."""
        return {
            "type": "linear",
            "active": self._is_active,
            "target_lat": self.target_lat,
            "target_lon": self.target_lon,
            "speed_kph": self.speed_kph,
            "stop_at_target": self.stop_at_target,
            "arrived": self._arrived,
            "distance_traveled_km": self._total_distance_traveled,
            "initial_distance_km": self._initial_distance_km
        }
        
    def update_target(self, new_lat: float, new_lon: float):
        """Update the target coordinates."""
        self.target_lat = new_lat
        self.target_lon = new_lon
        self._initial_distance_km = None  # Recalculate on next step
        self._arrived = False


class CircularTargeting(TargetingStrategy):
    """
    Circular targeting strategy that moves GPS in a circular pattern.
    
    Perfect for simulating vehicles doing laps around a track or
    following circular routes.
    """
    
    def __init__(self, center_lat: float, center_lon: float, 
                 radius_meters: float, angular_velocity_deg_per_sec: float = 5.0,
                 clockwise: bool = True, start_angle_degrees: float = 0.0):
        """
        Initialize circular targeting.
        
        Args:
            center_lat: Center point latitude in decimal degrees
            center_lon: Center point longitude in decimal degrees
            radius_meters: Radius of circle in meters
            angular_velocity_deg_per_sec: Speed of rotation in degrees per second
            clockwise: True for clockwise rotation, False for counter-clockwise
            start_angle_degrees: Starting angle in degrees (0 = North, 90 = East)
        """
        super().__init__()
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.radius_meters = radius_meters
        self.angular_velocity = angular_velocity_deg_per_sec
        self.clockwise = clockwise
        self.start_angle = start_angle_degrees
        
        self._current_angle = start_angle_degrees
        self._total_angle_traveled = 0.0
        self._laps_completed = 0
        
    def get_next_position(self, current_lat: float, current_lon: float,
                         current_heading: float, duration_seconds: float,
                         current_speed_kph: float) -> Tuple[float, float, float, float]:
        """Calculate next position along circular path."""
        
        if not self._is_active:
            return current_lat, current_lon, current_heading, 0.0
            
        # Calculate angle change for this time step
        angle_delta = self.angular_velocity * duration_seconds
        if not self.clockwise:
            angle_delta = -angle_delta
            
        self._current_angle = (self._current_angle + angle_delta) % 360
        self._total_angle_traveled += abs(angle_delta)
        
        # Check for completed laps
        if self._total_angle_traveled >= 360:
            self._laps_completed = int(self._total_angle_traveled / 360)
        
        # Convert angle to position on circle
        radius_km = self.radius_meters / 1000.0
        position_lat, position_lon = move_position(
            self.center_lat, self.center_lon, self._current_angle, radius_km
        )
        
        # Calculate heading (tangent to circle)
        if self.clockwise:
            heading = (self._current_angle + 90) % 360
        else:
            heading = (self._current_angle - 90) % 360
            
        # Calculate speed based on angular velocity and radius
        # v = ωr (linear velocity = angular velocity × radius)
        angular_velocity_rad_per_sec = math.radians(self.angular_velocity)
        speed_m_per_sec = angular_velocity_rad_per_sec * self.radius_meters
        speed_kph = speed_m_per_sec * 3.6
        
        # Track distance (arc length = radius × angle in radians)
        arc_length_km = radius_km * math.radians(abs(angle_delta))
        self._add_distance(arc_length_km)
        
        return position_lat, position_lon, heading, speed_kph
    
    def is_complete(self) -> bool:
        """Circular targeting never completes (runs indefinitely)."""
        return False
    
    def reset(self):
        """Reset to initial state."""
        self._current_angle = self.start_angle
        self._total_angle_traveled = 0.0
        self._laps_completed = 0
        self._total_distance_traveled = 0.0
        
    def get_progress(self) -> float:
        """Get progress through current lap (0.0 to 1.0)."""
        return (self._total_angle_traveled % 360) / 360.0
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status information."""
        return {
            "type": "circular",
            "active": self._is_active,
            "center_lat": self.center_lat,
            "center_lon": self.center_lon,
            "radius_meters": self.radius_meters,
            "angular_velocity": self.angular_velocity,
            "clockwise": self.clockwise,
            "current_angle": self._current_angle,
            "laps_completed": self._laps_completed,
            "distance_traveled_km": self._total_distance_traveled,
            "current_lap_progress": self.get_progress()
        }
    
    def get_laps_completed(self) -> int:
        """Get number of complete laps."""
        return self._laps_completed
        
    def update_center(self, new_lat: float, new_lon: float):
        """Update the center point of the circle."""
        self.center_lat = new_lat
        self.center_lon = new_lon


class WaypointTargeting(TargetingStrategy):
    """
    Waypoint targeting strategy that follows a series of GPS coordinates.
    
    Perfect for F1 race circuits or any complex route with specific
    waypoints that need to be followed in sequence.
    """
    
    def __init__(self, waypoints: List[Tuple[float, float]], speed_kph: float = 100.0, 
                 loop: bool = True, arrival_threshold_meters: float = 20.0):
        """
        Initialize waypoint targeting.
        
        Args:
            waypoints: List of (lat, lon) tuples defining the route
            speed_kph: Travel speed in km/h
            loop: If True, return to first waypoint after completing all
            arrival_threshold_meters: Distance threshold to consider "arrived" at waypoint
        """
        super().__init__()
        if not waypoints or len(waypoints) < 2:
            raise ValueError("At least 2 waypoints are required")
            
        self.waypoints = [(float(lat), float(lon)) for lat, lon in waypoints]
        self.speed_kph = speed_kph
        self.loop = loop
        self.arrival_threshold_meters = arrival_threshold_meters
        
        self._current_waypoint_index = 0
        self._laps_completed = 0
        self._total_route_distance_km = None
        self._completed = False
        
    def get_next_position(self, current_lat: float, current_lon: float,
                         current_heading: float, duration_seconds: float,
                         current_speed_kph: float) -> Tuple[float, float, float, float]:
        """Calculate next position moving toward current target waypoint."""
        
        if not self._is_active or self._completed:
            return current_lat, current_lon, current_heading, 0.0
            
        # Get current target waypoint
        if self._current_waypoint_index >= len(self.waypoints):
            if self.loop:
                self._current_waypoint_index = 0
                self._laps_completed += 1
            else:
                self._completed = True
                return current_lat, current_lon, current_heading, 0.0
                
        target_lat, target_lon = self.waypoints[self._current_waypoint_index]
        
        # Calculate distance to current target waypoint
        distance_to_waypoint_km = calculate_distance_km(
            current_lat, current_lon, target_lat, target_lon
        )
        
        # Check if we've reached this waypoint
        distance_to_waypoint_m = distance_to_waypoint_km * 1000
        if distance_to_waypoint_m <= self.arrival_threshold_meters:
            # Move to next waypoint
            self._current_waypoint_index += 1
            
            # If we've reached the end
            if self._current_waypoint_index >= len(self.waypoints):
                if self.loop:
                    self._current_waypoint_index = 0
                    self._laps_completed += 1
                    target_lat, target_lon = self.waypoints[0]
                else:
                    self._completed = True
                    return current_lat, current_lon, current_heading, 0.0
            else:
                target_lat, target_lon = self.waypoints[self._current_waypoint_index]
                
            # Recalculate distance to new target
            distance_to_waypoint_km = calculate_distance_km(
                current_lat, current_lon, target_lat, target_lon
            )
        
        # Calculate bearing to current target waypoint
        target_bearing = calculate_bearing(
            current_lat, current_lon, target_lat, target_lon
        )
        
        # Calculate distance to travel this step
        distance_this_step_km = (self.speed_kph / 3600.0) * duration_seconds
        
        # Don't overshoot the current waypoint
        if distance_this_step_km > distance_to_waypoint_km:
            distance_this_step_km = distance_to_waypoint_km
            
        # Move toward current target waypoint
        new_lat, new_lon = move_position(
            current_lat, current_lon, target_bearing, distance_this_step_km
        )
        
        # Track total distance
        self._add_distance(distance_this_step_km)
        
        return new_lat, new_lon, target_bearing, self.speed_kph
    
    def is_complete(self) -> bool:
        """Check if route is complete (only relevant if loop=False)."""
        return self._completed
    
    def reset(self):
        """Reset to start of route."""
        self._current_waypoint_index = 0
        self._laps_completed = 0
        self._completed = False
        self._total_distance_traveled = 0.0
        self._total_route_distance_km = None
        
    def get_progress(self) -> float:
        """Get progress through current lap (0.0 to 1.0)."""
        if not self.waypoints:
            return 0.0
            
        # Calculate progress based on current waypoint index
        return self._current_waypoint_index / len(self.waypoints)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status information."""
        current_target = None
        if (self._current_waypoint_index < len(self.waypoints) and 
            not self._completed):
            current_target = self.waypoints[self._current_waypoint_index]
            
        return {
            "type": "waypoint",
            "active": self._is_active,
            "total_waypoints": len(self.waypoints),
            "current_waypoint_index": self._current_waypoint_index,
            "current_target": current_target,
            "speed_kph": self.speed_kph,
            "loop": self.loop,
            "laps_completed": self._laps_completed,
            "completed": self._completed,
            "distance_traveled_km": self._total_distance_traveled,
            "current_lap_progress": self.get_progress()
        }
    
    def get_laps_completed(self) -> int:
        """Get number of complete laps."""
        return self._laps_completed
    
    def get_current_target_waypoint(self) -> Optional[Tuple[float, float]]:
        """Get the current target waypoint coordinates."""
        if (self._current_waypoint_index < len(self.waypoints) and 
            not self._completed):
            return self.waypoints[self._current_waypoint_index]
        return None
    
    def add_waypoint(self, lat: float, lon: float, index: Optional[int] = None):
        """Add a waypoint to the route."""
        waypoint = (float(lat), float(lon))
        if index is None:
            self.waypoints.append(waypoint)
        else:
            self.waypoints.insert(index, waypoint)
            
    def remove_waypoint(self, index: int):
        """Remove a waypoint from the route."""
        if 0 <= index < len(self.waypoints) and len(self.waypoints) > 2:
            self.waypoints.pop(index)
            # Adjust current index if necessary
            if self._current_waypoint_index >= index:
                self._current_waypoint_index = max(0, self._current_waypoint_index - 1)
    
    def calculate_total_route_distance(self) -> float:
        """Calculate the total distance of the complete route in kilometers."""
        if self._total_route_distance_km is not None:
            return self._total_route_distance_km
            
        total_distance = 0.0
        for i in range(len(self.waypoints) - 1):
            lat1, lon1 = self.waypoints[i]
            lat2, lon2 = self.waypoints[i + 1]
            total_distance += calculate_distance_km(lat1, lon1, lat2, lon2)
            
        # If looping, add distance from last waypoint back to first
        if self.loop and len(self.waypoints) > 2:
            last_lat, last_lon = self.waypoints[-1]
            first_lat, first_lon = self.waypoints[0]
            total_distance += calculate_distance_km(last_lat, last_lon, first_lat, first_lon)
            
        self._total_route_distance_km = total_distance
        return total_distance
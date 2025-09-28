"""
Provides a GUI for the NMEA simulator with map visualization and various targeting modes.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from tkinter.font import Font
import threading
import time
from datetime import datetime
from collections import deque
from typing import Optional, Dict, Any
import json

# Try to import map component - fallback gracefully if not available
try:
    import tkintermapview
    MAP_AVAILABLE = True
except ImportError:
    MAP_AVAILABLE = False

# Try to import PIL for custom icons
try:
    from PIL import Image, ImageDraw, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from .simulator import Simulator
from .targeting import (
    StaticTargeting, LinearTargeting, CircularTargeting, WaypointTargeting,
    TargetingStrategy
)
from .circuit_loader import get_available_circuits, get_circuit_waypoints
from .models import GpsReceiver
from .constants import TargetingMode


class EnhancedNMEAGUI:
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("NMEA Injector")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 700)
        
        # Initialize simulator
        self.gps = GpsReceiver(lat=51.5074, lon=-0.1278, kph=50.0)
        self.simulator = Simulator(gps=self.gps)
        
        # GUI state
        self.is_running = False
        self.current_targeting_mode = tk.StringVar(value="static")
        self.nmea_buffer = deque(maxlen=1000)  # Store last 1000 NMEA sentences
        self.last_displayed_count = 0  # Track how many sentences we've already displayed
        self.position_trail = deque(maxlen=200)  # Store positions for map (will be dynamically adjusted)
        
        # Map performance optimizations
        self.map_update_pending = False
        self.last_map_update = 0
        self._last_map_pos = None
        self.trail_length = tk.IntVar(value=50)  # Initialize trail length control
        self.map_update_rate = tk.StringVar(value="Normal (2Hz)")  # Initialize update rate
        
        # Trail point markers and data storage
        self.trail_markers = []  # Store trail point markers for interactivity
        self.trail_data = deque(maxlen=200)  # Store detailed data for each trail point
        self.show_trail_points = tk.BooleanVar(value=True)  # Show individual dots
        
        # Statistics tracking
        self.total_sentences_generated = 0
        self.last_stats_update = time.time()
        self.sentences_in_last_second = 0
        
        # Threading
        self.gui_update_thread = None
        self.stop_updates = threading.Event()
        
        # Setup GUI components
        self.setup_style()
        self.setup_layout()
        self.setup_menu()
        self.setup_controls()
        self.setup_map()
        self.setup_nmea_panel()
        self.setup_status_bar()
        
        # Initial state
        self.update_targeting_controls()
        self.schedule_gui_updates()
        
        # Create custom trail marker icon
        self.trail_marker_icon = self.create_trail_marker_icon()
        
    def create_trail_marker_icon(self):
        """Create a custom circle icon for trail markers."""
        if not PIL_AVAILABLE:
            return None
            
        try:
            # Create a small circular icon
            size = 16  # Slightly larger for better visibility
            image = Image.new('RGBA', (size, size), (0, 0, 0, 0))  # Transparent background
            draw = ImageDraw.Draw(image)
            
            # Draw filled circle with gradient-like effect
            margin = 1
            # Outer circle (darker)
            draw.ellipse([margin, margin, size-margin, size-margin], 
                        fill=(255, 140, 0, 255),    # Orange fill
                        outline=(200, 80, 0, 255),  # Darker orange outline
                        width=2)
            
            # Inner highlight circle for 3D effect
            highlight_margin = 3
            draw.ellipse([highlight_margin, highlight_margin, size-highlight_margin, size-highlight_margin], 
                        fill=(255, 200, 100, 180),  # Lighter orange center
                        outline=None)
            
            # Convert to PhotoImage for tkinter
            photo_image = ImageTk.PhotoImage(image)
            print("Created custom trail marker icon successfully")
            return photo_image
            
        except Exception as e:
            print(f"Error creating trail marker icon: {e}")
            return None
            
    def create_alternative_icon(self, color="orange"):
        """Create alternative marker icons with different colors."""
        if not PIL_AVAILABLE:
            return None
            
        try:
            size = 14
            image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            
            # Color mapping
            colors = {
                "orange": ((255, 140, 0, 255), (200, 80, 0, 255)),
                "blue": ((0, 140, 255, 255), (0, 80, 200, 255)),
                "green": ((140, 255, 0, 255), (80, 200, 0, 255)),
                "red": ((255, 80, 80, 255), (200, 40, 40, 255))
            }
            
            fill_color, outline_color = colors.get(color, colors["orange"])
            
            # Simple filled circle
            draw.ellipse([1, 1, size-1, size-1], 
                        fill=fill_color,
                        outline=outline_color,
                        width=1)
            
            return ImageTk.PhotoImage(image)
            
        except Exception as e:
            print(f"Error creating {color} icon: {e}")
            return None
        
    def setup_style(self):
        """Configure GUI styling."""
        style = ttk.Style()
        
        # Configure notebook style for better visibility
        style.configure('Targeting.TNotebook.Tab', padding=[8, 4])
        
    def setup_layout(self):
        """Create the main 3-panel layout."""
        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create paned window for resizable panels
        self.paned_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Controls (300px default width)
        self.control_frame = ttk.Frame(self.paned_window, width=300)
        self.paned_window.add(self.control_frame, weight=0)
        
        # Center panel - Map (flexible width)
        self.map_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(self.map_frame, weight=1)
        
        # Right panel - NMEA Data (400px default width)
        self.nmea_frame = ttk.Frame(self.paned_window, width=400)
        self.paned_window.add(self.nmea_frame, weight=0)
        
    def setup_menu(self):
        """Create menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load Configuration...", command=self.load_config)
        file_menu.add_command(label="Save Configuration...", command=self.save_config)
        file_menu.add_separator()
        file_menu.add_command(label="Import Waypoints...", command=self.import_waypoints)
        file_menu.add_command(label="Export Waypoints...", command=self.export_waypoints)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Reset Map View", command=self.reset_map_view)
        view_menu.add_command(label="Clear NMEA Buffer", command=self.clear_nmea_buffer)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="F1 Circuit Presets", command=self.show_f1_presets)
        tools_menu.add_command(label="Export NMEA Data...", command=self.export_nmea_data)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        
    def setup_controls(self):
        """Create the control panel."""
        # Control panel title
        title_label = ttk.Label(self.control_frame, text="NMEA Simulator Controls", 
                               font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Create notebook for organized controls
        self.control_notebook = ttk.Notebook(self.control_frame)
        self.control_notebook.pack(fill=tk.BOTH, expand=True, padx=5)
        
        # Targeting tab
        self.targeting_frame = ttk.Frame(self.control_notebook)
        self.control_notebook.add(self.targeting_frame, text="Targeting")
        self.setup_targeting_controls()
        
        # GPS Configuration tab
        self.gps_frame = ttk.Frame(self.control_notebook)
        self.control_notebook.add(self.gps_frame, text="GPS Config")
        self.setup_gps_controls()
        
        # Output tab
        self.output_frame = ttk.Frame(self.control_notebook)
        self.control_notebook.add(self.output_frame, text="Output")
        self.setup_output_controls()
        
        # Main control buttons
        button_frame = ttk.Frame(self.control_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        self.start_button = ttk.Button(button_frame, text="Start Simulation", 
                                      command=self.start_simulation, style='Accent.TButton')
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_button = ttk.Button(button_frame, text="Stop Simulation", 
                                     command=self.stop_simulation, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)
        
    def setup_targeting_controls(self):
        """Create targeting mode controls."""
        # Targeting mode selection
        mode_frame = ttk.LabelFrame(self.targeting_frame, text="Targeting Mode", padding=10)
        mode_frame.pack(fill=tk.X, padx=5, pady=5)
        
        modes = [
            ("Static", "static"),
            ("Linear", "linear"), 
            ("Circular", "circular"),
            ("Waypoint", "waypoint")
        ]
        
        for text, value in modes:
            rb = ttk.Radiobutton(mode_frame, text=text, variable=self.current_targeting_mode,
                                value=value, command=self.update_targeting_controls)
            rb.pack(anchor=tk.W)
            
        # Dynamic parameter frame
        self.param_frame = ttk.LabelFrame(self.targeting_frame, text="Parameters", padding=10)
        self.param_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Initialize parameter variables
        self.target_lat = tk.DoubleVar(value=48.8566)
        self.target_lon = tk.DoubleVar(value=2.3522) 
        self.target_speed = tk.DoubleVar(value=100.0)
        self.circle_center_lat = tk.DoubleVar(value=51.5074)
        self.circle_center_lon = tk.DoubleVar(value=-0.1278)
        self.circle_radius = tk.DoubleVar(value=1000.0)
        self.circle_angular_velocity = tk.DoubleVar(value=5.0)
        self.circle_clockwise = tk.BooleanVar(value=True)
        
    def update_targeting_controls(self):
        """Update the parameter controls based on selected targeting mode."""
        # Clear existing parameter widgets
        for widget in self.param_frame.winfo_children():
            widget.destroy()
            
        mode = self.current_targeting_mode.get()
        
        if mode == "static":
            ttk.Label(self.param_frame, text="GPS position will remain static").pack(anchor=tk.W)
            
        elif mode == "linear":
            self.create_linear_controls()
            
        elif mode == "circular":
            self.create_circular_controls()
            
        elif mode == "waypoint":
            self.create_waypoint_controls()
            
    def create_linear_controls(self):
        """Create controls for linear targeting."""
        # Target coordinates
        ttk.Label(self.param_frame, text="Target Latitude:").pack(anchor=tk.W)
        ttk.Entry(self.param_frame, textvariable=self.target_lat, width=20).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Label(self.param_frame, text="Target Longitude:").pack(anchor=tk.W)
        ttk.Entry(self.param_frame, textvariable=self.target_lon, width=20).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Label(self.param_frame, text="Speed (km/h):").pack(anchor=tk.W)
        ttk.Entry(self.param_frame, textvariable=self.target_speed, width=20).pack(anchor=tk.W, pady=(0, 5))
        
        # Set target from map button
        ttk.Button(self.param_frame, text="Set Target from Map", 
                  command=self.set_target_from_map).pack(anchor=tk.W, pady=5)
                  
    def create_circular_controls(self):
        """Create controls for circular targeting."""
        ttk.Label(self.param_frame, text="Center Latitude:").pack(anchor=tk.W)
        ttk.Entry(self.param_frame, textvariable=self.circle_center_lat, width=20).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Label(self.param_frame, text="Center Longitude:").pack(anchor=tk.W)
        ttk.Entry(self.param_frame, textvariable=self.circle_center_lon, width=20).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Label(self.param_frame, text="Radius (meters):").pack(anchor=tk.W)
        ttk.Entry(self.param_frame, textvariable=self.circle_radius, width=20).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Label(self.param_frame, text="Angular Velocity (°/sec):").pack(anchor=tk.W)
        ttk.Entry(self.param_frame, textvariable=self.circle_angular_velocity, width=20).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Checkbutton(self.param_frame, text="Clockwise", variable=self.circle_clockwise).pack(anchor=tk.W)
        
    def create_waypoint_controls(self):
        """Create controls for waypoint targeting."""
        
        # F1 Circuit Selection
        circuit_frame = ttk.LabelFrame(self.param_frame, text="F1 Circuits", padding="5")
        circuit_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(circuit_frame, text="Select F1 Circuit:").pack(anchor='w')
        
        circuit_select_frame = ttk.Frame(circuit_frame)
        circuit_select_frame.pack(fill='x', pady=(5, 0))
        
        self.circuit_var = tk.StringVar(value="")
        self.circuit_combo = ttk.Combobox(circuit_select_frame, textvariable=self.circuit_var, 
                                         state="readonly", width=40)
        self.circuit_combo.pack(side='left', fill='x', expand=True, padx=(0, 5))
        
        # Auto-load circuit when selection changes
        self.circuit_combo.bind('<<ComboboxSelected>>', lambda e: self.load_selected_circuit())
        
        load_circuit_btn = ttk.Button(circuit_select_frame, text="Reload", 
                                     command=lambda: print("DEBUG: Reload Circuit button clicked!") or self.load_selected_circuit())
        load_circuit_btn.pack(side='right')
        
        # Load available circuits into combobox
        try:
            circuits = get_available_circuits()
            print(f"DEBUG: Got {len(circuits)} circuits")
            circuit_values = [f"{name}" for circuit_id, name in circuits]
            print(f"DEBUG: First 3 circuit values: {circuit_values[:3]}")
            self.circuit_combo['values'] = circuit_values
            # Store mapping from display names to IDs
            self.circuit_id_map = {name: circuit_id for circuit_id, name in circuits}
            print(f"DEBUG: Created circuit_id_map with {len(self.circuit_id_map)} entries")
        except Exception as e:
            print(f"Warning: Could not load F1 circuits: {e}")
            import traceback
            traceback.print_exc()
            self.circuit_id_map = {}
        
        # Waypoint list
        ttk.Label(self.param_frame, text="Waypoints:").pack(anchor=tk.W, pady=(10, 0))
        
        # Waypoint listbox with scrollbar
        waypoint_frame = ttk.Frame(self.param_frame)
        waypoint_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.waypoint_listbox = tk.Listbox(waypoint_frame, height=6)
        scrollbar = ttk.Scrollbar(waypoint_frame, orient=tk.VERTICAL, command=self.waypoint_listbox.yview)
        self.waypoint_listbox.config(yscrollcommand=scrollbar.set)
        
        self.waypoint_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Initialize with empty waypoints - will be populated by F1 circuit selection
        self.waypoints = []
        self.update_waypoint_list()
        
        # Waypoint buttons
        btn_frame = ttk.Frame(self.param_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="Add Waypoint", command=self.add_waypoint).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Remove", command=self.remove_waypoint).pack(side=tk.LEFT)
        
        # Speed setting
        speed_frame = ttk.Frame(self.param_frame)
        speed_frame.pack(fill=tk.X, pady=5)
        ttk.Label(speed_frame, text="Speed (km/h):").pack(side=tk.LEFT)
        ttk.Entry(speed_frame, textvariable=self.target_speed, width=10).pack(side=tk.LEFT, padx=5)
        
    def setup_gps_controls(self):
        """Create GPS configuration controls.""" 
        # Current position
        pos_frame = ttk.LabelFrame(self.gps_frame, text="Current Position", padding=10)
        pos_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.current_lat = tk.DoubleVar(value=self.gps.lat)
        self.current_lon = tk.DoubleVar(value=self.gps.lon)
        self.current_alt = tk.DoubleVar(value=self.gps.altitude or 0.0)
        
        ttk.Label(pos_frame, text="Latitude:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(pos_frame, textvariable=self.current_lat, width=15).grid(row=0, column=1, padx=5)
        
        ttk.Label(pos_frame, text="Longitude:").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(pos_frame, textvariable=self.current_lon, width=15).grid(row=1, column=1, padx=5)
        
        ttk.Label(pos_frame, text="Altitude (m):").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(pos_frame, textvariable=self.current_alt, width=15).grid(row=2, column=1, padx=5)
        
        # Satellite configuration
        sat_frame = ttk.LabelFrame(self.gps_frame, text="Satellites", padding=10)
        sat_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.num_sats = tk.IntVar(value=self.gps.num_sats)
        ttk.Label(sat_frame, text="Number of Satellites:").pack(anchor=tk.W)
        ttk.Scale(sat_frame, from_=4, to=20, variable=self.num_sats, orient=tk.HORIZONTAL).pack(fill=tk.X)
        
    def setup_output_controls(self):
        """Create output configuration controls."""
        # NMEA sentence selection
        nmea_frame = ttk.LabelFrame(self.output_frame, text="NMEA Sentences", padding=10)
        nmea_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.nmea_sentences = {
            'GGA': tk.BooleanVar(value=True),
            'GLL': tk.BooleanVar(value=True),
            'GSA': tk.BooleanVar(value=True),
            'GSV': tk.BooleanVar(value=True),
            'RMC': tk.BooleanVar(value=True),
            'VTG': tk.BooleanVar(value=True),
            'ZDA': tk.BooleanVar(value=True)
        }
        
        for sentence, var in self.nmea_sentences.items():
            ttk.Checkbutton(nmea_frame, text=sentence, variable=var).pack(anchor=tk.W)
            
        # Update interval
        interval_frame = ttk.Frame(self.output_frame)
        interval_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(interval_frame, text="Update Interval (seconds):").pack(anchor=tk.W)
        self.update_interval = tk.DoubleVar(value=1.0)
        ttk.Entry(interval_frame, textvariable=self.update_interval, width=10).pack(anchor=tk.W)
        
    def setup_map(self):
        """Create the interactive map panel."""
        # Map panel title
        map_title = ttk.Label(self.map_frame, text="GPS Position Visualization", 
                             font=('Arial', 12, 'bold'))
        map_title.pack(pady=(0, 5))
        
        if MAP_AVAILABLE:
            try:
                # Create the map widget with caching enabled
                self.map_widget = tkintermapview.TkinterMapView(
                    self.map_frame, width=600, height=500, corner_radius=0
                )
                self.map_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                
                # Enable tile caching for better performance
                self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png", max_zoom=22)
                
                # Set initial position (London)
                self.map_widget.set_position(51.5074, -0.1278)
                self.map_widget.set_zoom(10)
                
                # Add GPS position marker
                self.gps_marker = self.map_widget.set_marker(
                    51.5074, -0.1278, text="GPS", marker_color_circle="red",
                    marker_color_outside="darkred", text_color="white"
                )
                
                # Map interaction bindings
                self.map_widget.add_right_click_menu_command(
                    "Set as Target", command=self.map_right_click_target
                )
                self.map_widget.add_right_click_menu_command(
                    "Add Waypoint", command=self.map_right_click_waypoint
                )
                
                # Performance optimization: Reduce map update frequency during zoom/pan
                self.map_update_pending = False
                self.last_map_update = 0
                
                # Map controls frame
                map_controls = ttk.Frame(self.map_frame)
                map_controls.pack(fill=tk.X, padx=5, pady=5)
                
                ttk.Button(map_controls, text="Reset View", command=self.reset_map_view).pack(side=tk.LEFT, padx=5)
                ttk.Button(map_controls, text="Follow GPS", command=self.follow_gps).pack(side=tk.LEFT, padx=5)
                ttk.Button(map_controls, text="Clear Trail", command=self.clear_trail).pack(side=tk.LEFT, padx=5)
                
                # Debug button for testing trail point info
                ttk.Button(map_controls, text="Test Point Info", command=self.test_trail_point_info).pack(side=tk.LEFT, padx=5)
                
                # Trail display option
                self.show_trail = tk.BooleanVar(value=True)
                trail_check = ttk.Checkbutton(map_controls, text="Show Trail", variable=self.show_trail,
                                            command=self.toggle_trail_visibility)
                trail_check.pack(side=tk.LEFT, padx=10)
                
                # Trail points option
                self.show_trail_points = tk.BooleanVar(value=True)
                points_check = ttk.Checkbutton(map_controls, text="Show Points", variable=self.show_trail_points,
                                             command=self.toggle_trail_points)
                points_check.pack(side=tk.LEFT, padx=5)
                
                # Trail length control
                trail_frame = ttk.Frame(map_controls)
                trail_frame.pack(side=tk.LEFT, padx=10)
                ttk.Label(trail_frame, text="Trail Points:").pack(side=tk.LEFT)
                self.trail_length = tk.IntVar(value=50)
                trail_spin = ttk.Spinbox(trail_frame, from_=10, to=200, width=5, textvariable=self.trail_length,
                                        command=self.update_trail_settings)
                trail_spin.pack(side=tk.LEFT, padx=2)
                trail_spin.bind('<Return>', lambda e: self.update_trail_settings())
                
                # Performance settings
                perf_frame = ttk.Frame(map_controls)
                perf_frame.pack(side=tk.LEFT, padx=10)
                ttk.Label(perf_frame, text="Update Rate:").pack(side=tk.LEFT)
                
                self.map_update_rate = tk.StringVar(value="Normal")
                update_combo = ttk.Combobox(perf_frame, textvariable=self.map_update_rate,
                                          values=["Fast (10Hz)", "Normal (2Hz)", "Slow (1Hz)"],
                                          width=10, state="readonly")
                update_combo.pack(side=tk.LEFT, padx=2)
                
                # Map layers
                layer_frame = ttk.Frame(map_controls)
                layer_frame.pack(side=tk.RIGHT)
                ttk.Label(layer_frame, text="Layer:").pack(side=tk.LEFT)
                
                self.map_layer = tk.StringVar(value="OpenStreetMap")
                layer_combo = ttk.Combobox(layer_frame, textvariable=self.map_layer, 
                                          values=["OpenStreetMap", "Google normal", "Google satellite"], 
                                          width=15, state="readonly")
                layer_combo.pack(side=tk.LEFT, padx=5)
                layer_combo.bind('<<ComboboxSelected>>', self.change_map_layer)
                
            except Exception as e:
                self.create_fallback_map(f"Map initialization failed: {e}")
        else:
            self.create_fallback_map("tkintermapview not installed")
            
    def create_fallback_map(self, reason):
        """Create a fallback display when map is not available."""
        fallback_frame = ttk.Frame(self.map_frame, relief=tk.SUNKEN, borderwidth=2)
        fallback_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        ttk.Label(fallback_frame, text="Map Visualization", 
                 font=('Arial', 16, 'bold')).pack(pady=20)
        ttk.Label(fallback_frame, text=f"({reason})", 
                 font=('Arial', 10)).pack()
        
        # Simple text-based position display
        self.position_display = scrolledtext.ScrolledText(
            fallback_frame, height=15, width=60, state=tk.DISABLED
        )
        self.position_display.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
    def setup_nmea_panel(self):
        """Create the NMEA data stream panel."""
        # NMEA panel title
        nmea_title = ttk.Label(self.nmea_frame, text="NMEA Data Stream", 
                              font=('Arial', 12, 'bold'))
        nmea_title.pack(pady=(0, 5))
        
        # NMEA controls
        control_frame = ttk.Frame(self.nmea_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.nmea_paused = tk.BooleanVar(value=False)
        ttk.Checkbutton(control_frame, text="Pause", variable=self.nmea_paused).pack(side=tk.LEFT)
        
        ttk.Button(control_frame, text="Clear", command=self.clear_nmea_buffer).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Export", command=self.export_nmea_data).pack(side=tk.LEFT, padx=5)
        
        # NMEA data display
        nmea_display_frame = ttk.Frame(self.nmea_frame)
        nmea_display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.nmea_text = scrolledtext.ScrolledText(
            nmea_display_frame, height=20, width=50, font=('Consolas', 9),
            state=tk.DISABLED, wrap=tk.NONE
        )
        self.nmea_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure text colors for different NMEA sentence types
        self.nmea_text.tag_config("GGA", foreground="blue")
        self.nmea_text.tag_config("RMC", foreground="green") 
        self.nmea_text.tag_config("GSV", foreground="purple")
        self.nmea_text.tag_config("GSA", foreground="orange")
        self.nmea_text.tag_config("timestamp", foreground="gray")
        
        # Statistics display
        stats_frame = ttk.LabelFrame(self.nmea_frame, text="Statistics", padding=5)
        stats_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.sentences_count = tk.StringVar(value="Sentences: 0")
        self.sentences_per_sec = tk.StringVar(value="Rate: 0.0/sec")
        
        ttk.Label(stats_frame, textvariable=self.sentences_count).pack(anchor=tk.W)
        ttk.Label(stats_frame, textvariable=self.sentences_per_sec).pack(anchor=tk.W)
        
    def setup_status_bar(self):
        """Create the status bar."""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Status labels
        self.status_position = tk.StringVar(value="Position: 51.5074, -0.1278")
        self.status_speed = tk.StringVar(value="Speed: 0.0 km/h")
        self.status_mode = tk.StringVar(value="Mode: Static")
        self.status_running = tk.StringVar(value="Status: Stopped")
        
        ttk.Label(self.status_frame, textvariable=self.status_position).pack(side=tk.LEFT, padx=10)
        ttk.Separator(self.status_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Label(self.status_frame, textvariable=self.status_speed).pack(side=tk.LEFT, padx=10)
        ttk.Separator(self.status_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Label(self.status_frame, textvariable=self.status_mode).pack(side=tk.LEFT, padx=10)
        ttk.Separator(self.status_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Label(self.status_frame, textvariable=self.status_running).pack(side=tk.LEFT, padx=10)
        
    def update_waypoint_list(self):
        """Update the waypoint listbox display."""
        if hasattr(self, 'waypoint_listbox'):
            self.waypoint_listbox.delete(0, tk.END)
            for i, (lat, lon) in enumerate(self.waypoints):
                self.waypoint_listbox.insert(tk.END, f"{i+1}: {lat:.6f}, {lon:.6f}")
                
    def start_simulation(self):
        """Start the NMEA simulation."""
        try:
            # Apply current GPS settings
            self.gps.lat = self.current_lat.get()
            self.gps.lon = self.current_lon.get()
            self.gps.altitude = self.current_alt.get()
            self.gps.num_sats = self.num_sats.get()
            
            # Configure NMEA output
            enabled_sentences = [name for name, var in self.nmea_sentences.items() if var.get()]
            self.gps.output = tuple(enabled_sentences)
            
            # Set update interval
            self.simulator.interval = self.update_interval.get()
            
            # Configure targeting based on selected mode
            mode = self.current_targeting_mode.get()
            
            if mode == "static":
                targeting = StaticTargeting()
            elif mode == "linear":
                targeting = LinearTargeting(
                    target_lat=self.target_lat.get(),
                    target_lon=self.target_lon.get(),
                    speed_kph=self.target_speed.get()
                )
            elif mode == "circular":
                targeting = CircularTargeting(
                    center_lat=self.circle_center_lat.get(),
                    center_lon=self.circle_center_lon.get(),
                    radius_meters=self.circle_radius.get(),
                    angular_velocity_deg_per_sec=self.circle_angular_velocity.get(),
                    clockwise=self.circle_clockwise.get()
                )
            elif mode == "waypoint":
                targeting = WaypointTargeting(
                    waypoints=self.waypoints,
                    speed_kph=self.target_speed.get(),
                    loop=True
                )
            
            self.simulator.set_targeting(targeting)
            
            # Start the simulator (non-blocking)
            self.simulator.serve(blocking=False)
            
            # Update UI state
            self.is_running = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_running.set("Status: Running")
            
            # Start GUI update thread
            if not self.gui_update_thread or not self.gui_update_thread.is_alive():
                self.stop_updates.clear()
                self.gui_update_thread = threading.Thread(target=self.gui_update_loop, daemon=True)
                self.gui_update_thread.start()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start simulation: {e}")
            
    def stop_simulation(self):
        """Stop the NMEA simulation."""
        try:
            self.simulator.kill()
            self.stop_updates.set()
            
            # Update UI state
            self.is_running = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.status_running.set("Status: Stopped")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop simulation: {e}")
            
    def gui_update_loop(self):
        """Background thread for updating GUI with simulation data - optimized for performance."""
        last_sentence_count = 0
        last_time = time.time()
        update_counter = 0
        sentences_this_second = 0
        
        while not self.stop_updates.is_set():
            try:
                if self.is_running:
                    # Get latest NMEA sentences
                    with self.simulator.lock:
                        sentences = self.simulator.gps.get_output()
                        current_pos = (self.simulator.gps.lat, self.simulator.gps.lon)
                        current_speed = self.simulator.gps.kph or 0.0
                        current_heading = self.simulator.gps.heading or 0.0
                    
                    # Update NMEA buffer and display
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    sentence_count_this_update = len(sentences)
                    
                    for sentence in sentences:
                        self.nmea_buffer.append((timestamp, sentence))
                        self.total_sentences_generated += 1
                    
                    sentences_this_second += sentence_count_this_update
                    
                    # Schedule GUI updates on main thread with reduced frequency
                    update_counter += 1
                    
                    # Always update NMEA display (it's fast)
                    if sentences:  # Only if there are new sentences
                        self.root.after(0, self.update_nmea_display)
                    
                    # Update map less frequently to reduce lag
                    if update_counter % 2 == 0:  # Every 2nd update (reduce to 5Hz)
                        self.root.after(0, self.update_map_position, current_pos[0], current_pos[1])
                    
                    # Update status bar even less frequently
                    if update_counter % 5 == 0:  # Every 5th update (reduce to 2Hz)
                        self.root.after(0, self.update_status_bar, current_pos, current_speed)
                    
                    # Calculate sentence rate every second
                    current_time = time.time()
                    if current_time - last_time >= 1.0:  # Update every second
                        # Use sentences generated in this second, not buffer length
                        rate = sentences_this_second / (current_time - last_time)
                        
                        # Update GUI on main thread
                        self.root.after(0, self.update_statistics, self.total_sentences_generated, rate)
                        
                        # Reset for next second
                        sentences_this_second = 0
                        last_time = current_time
                        
                time.sleep(0.1)  # Update at 10Hz, but with intelligent throttling
                
            except Exception as e:
                print(f"GUI update error: {e}")
                break
                
    def update_statistics(self, total_count, rate):
        """Update statistics display on main thread."""
        try:
            self.sentences_count.set(f"Sentences: {total_count}")
            self.sentences_per_sec.set(f"Rate: {rate:.1f}/sec")
        except Exception as e:
            print(f"Statistics update error: {e}")
    
    def schedule_gui_updates(self):
        """Schedule periodic GUI updates - statistics now handled by background thread."""
        # Statistics are now handled by the gui_update_loop background thread
        # This method can be used for other periodic updates if needed
        self.root.after(1000, self.schedule_gui_updates)  # Keep running for consistency
        
    def update_nmea_display(self):
        """Update the NMEA data display."""
        if self.nmea_paused.get():
            return
            
        # Add new sentences to display
        if hasattr(self, 'nmea_text'):
            self.nmea_text.config(state=tk.NORMAL)
            
            # Only display new sentences since last update
            buffer_len = len(self.nmea_buffer)
            
            if buffer_len > self.last_displayed_count:
                # Get only the new sentences
                new_sentences = list(self.nmea_buffer)[self.last_displayed_count:]
                
                # Clear the text widget periodically to prevent memory issues
                current_lines = int(self.nmea_text.index('end-1c').split('.')[0])
                if current_lines > 1000:  # If more than 1000 lines, clear and keep recent
                    self.nmea_text.delete('1.0', 'end')
                    # Reset counter since we cleared the display
                    self.last_displayed_count = max(0, buffer_len - 500)
                    new_sentences = list(self.nmea_buffer)[self.last_displayed_count:]
                    
                # Display only new sentences
                for timestamp, sentence in new_sentences:
                    # Add timestamp
                    self.nmea_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
                    
                    # Add sentence with appropriate color
                    sentence_type = sentence.split(',')[0][3:6] if len(sentence) > 6 else "UNK"
                    self.nmea_text.insert(tk.END, f"{sentence}\n", sentence_type)
                    
                # Update our counter
                self.last_displayed_count = buffer_len
                
            # Auto-scroll to bottom
            self.nmea_text.see(tk.END)
            self.nmea_text.config(state=tk.DISABLED)
            
    def update_map_position(self, lat, lon):
        """Update GPS position on the map with performance optimizations and proper error handling."""
        current_time = time.time()
        
        # Validate input coordinates
        if lat is None or lon is None:
            print(f"Warning: Invalid coordinates - lat: {lat}, lon: {lon}")
            return
            
        # Get update rate setting
        try:
            rate_setting = self.map_update_rate.get()
            if "Fast" in rate_setting:
                update_interval = 0.1  # 10Hz
            elif "Normal" in rate_setting:
                update_interval = 0.5  # 2Hz  
            else:  # Slow
                update_interval = 1.0  # 1Hz
        except:
            update_interval = 0.5  # Default fallback
            
        # Throttle map updates to prevent lag
        if current_time - self.last_map_update < update_interval:
            return
            
        self.last_map_update = current_time
        
        if MAP_AVAILABLE and hasattr(self, 'map_widget'):
            try:
                # Update GPS marker position efficiently
                if hasattr(self, 'gps_marker'):
                    # Only update if position changed significantly (reduce unnecessary updates)
                    if hasattr(self, '_last_map_pos') and self._last_map_pos is not None:
                        try:
                            last_lat, last_lon = self._last_map_pos
                            # Only update if moved more than ~1 meter (rough calculation)
                            if abs(lat - last_lat) < 0.00001 and abs(lon - last_lon) < 0.00001:
                                return
                        except (TypeError, ValueError) as e:
                            print(f"Position comparison error: {e}")
                            # Continue with update anyway
                    
                    self.gps_marker.set_position(lat, lon)
                    self._last_map_pos = (lat, lon)
                else:
                    # Create new GPS marker
                    try:
                        self.gps_marker = self.map_widget.set_marker(
                            lat, lon, text="GPS", marker_color_circle="red",
                            marker_color_outside="darkred", text_color="white"
                        )
                        self._last_map_pos = (lat, lon)
                        print(f"Created GPS marker at {lat:.6f}, {lon:.6f}")
                    except Exception as e:
                        print(f"Failed to create GPS marker: {e}")
                        return
                    
                # Add to position trail (limit trail length for performance)
                current_time = time.time()
                
                # Get current GPS data from simulator for detailed info
                try:
                    with self.simulator.lock:
                        current_speed = self.simulator.gps.kph or 0.0
                        current_heading = self.simulator.gps.heading or 0.0
                        targeting_status = self.simulator.get_targeting_status()
                except:
                    current_speed = 0.0
                    current_heading = 0.0
                    targeting_status = {}
                
                # Store detailed trail data
                trail_point_data = {
                    'lat': lat,
                    'lon': lon,
                    'speed_kph': current_speed,
                    'heading': current_heading,
                    'timestamp': current_time,
                    'index': len(self.trail_data),
                    'targeting_info': targeting_status
                }
                
                self.position_trail.append((lat, lon))
                self.trail_data.append(trail_point_data)
                
                print(f"Trail length: {len(self.position_trail)}, Show trail: {self.show_trail.get()}")
                
                # Update trail visualization if enabled
                if self.show_trail.get() and len(self.position_trail) > 1:
                    try:
                        # More frequent trail updates for better visibility
                        if (len(self.position_trail) % 2 == 0 or  # Every 2 points
                            not hasattr(self, 'trail_path')):     # Or if no trail exists
                            
                            # Remove old trail to prevent memory leaks
                            if hasattr(self, 'trail_path'):
                                try:
                                    self.trail_path.delete()
                                    print("Deleted old trail")
                                except Exception as e:
                                    print(f"Error deleting old trail: {e}")
                                    
                            # Draw new trail with user-controlled length
                            try:
                                max_trail_points = self.trail_length.get()
                            except:
                                max_trail_points = 50  # fallback
                                
                            trail_coords = list(self.position_trail)[-max_trail_points:]
                            print(f"Drawing trail with {len(trail_coords)} points")
                            
                            if len(trail_coords) >= 2:
                                try:
                                    self.trail_path = self.map_widget.set_path(
                                        trail_coords, color="blue", width=3
                                    )
                                    print(f"Successfully created trail path with {len(trail_coords)} points")
                                    
                                    # Add interactive trail point markers using alternative approach
                                    self.create_trail_point_markers_alternative()
                                    
                                except Exception as e:
                                    print(f"Trail drawing error: {e}")
                                    print(f"Trail coords sample: {trail_coords[:3]}...")
                                    
                    except Exception as e:
                        print(f"Trail update error: {e}")
                        
                elif not self.show_trail.get() and hasattr(self, 'trail_path'):
                    # Hide trail if disabled
                    try:
                        self.trail_path.delete()
                        delattr(self, 'trail_path')
                        self.clear_trail_markers()  # Also clear markers
                        print("Trail hidden")
                    except Exception as e:
                        print(f"Error hiding trail: {e}")
                        
            except Exception as e:
                print(f"Map update error: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Fallback text display
            if hasattr(self, 'position_display'):
                self.position_display.config(state=tk.NORMAL)
                self.position_display.insert(tk.END, f"Position: {lat:.6f}, {lon:.6f}\n")
                
                # Limit fallback display lines for performance
                lines = self.position_display.get(1.0, tk.END).split('\n')
                if len(lines) > 100:  # Keep only last 100 lines
                    self.position_display.delete(1.0, f"{len(lines)-100}.0")
                    
                self.position_display.see(tk.END)
                self.position_display.config(state=tk.DISABLED)
                
    def update_status_bar(self, position, speed):
        """Update the status bar with current information."""
        lat, lon = position
        self.status_position.set(f"Position: {lat:.6f}, {lon:.6f}")
        self.status_speed.set(f"Speed: {speed:.1f} km/h")
        
        mode = self.current_targeting_mode.get().title()
        self.status_mode.set(f"Mode: {mode}")
        
        # Note: Sentence count and rate updated by update_statistics method
        
    # Map interaction methods
    def reset_map_view(self):
        """Reset map view to current GPS position."""
        if MAP_AVAILABLE and hasattr(self, 'map_widget'):
            lat = self.gps.lat or 51.5074
            lon = self.gps.lon or -0.1278
            self.map_widget.set_position(lat, lon)
            self.map_widget.set_zoom(10)
            
    def follow_gps(self):
        """Center map on current GPS position."""
        if MAP_AVAILABLE and hasattr(self, 'map_widget'):
            if hasattr(self, 'gps_marker') and hasattr(self, '_last_map_pos'):
                try:
                    if self._last_map_pos:
                        lat, lon = self._last_map_pos
                        self.map_widget.set_position(lat, lon)
                except Exception as e:
                    print(f"Follow GPS error: {e}")
                
    def clear_trail(self):
        """Clear the GPS position trail for better performance."""
        try:
            self.position_trail.clear()
            self.trail_data.clear()
            self.clear_trail_markers()
            
            if hasattr(self, 'trail_path'):
                self.trail_path.delete()
                delattr(self, 'trail_path')
                
        except Exception as e:
            print(f"Error clearing trail: {e}")
            
    def update_trail_settings(self):
        """Update trail settings when user changes trail length."""
        try:
            new_length = self.trail_length.get()
            # Adjust the deque maxlen by recreating it
            current_trail = list(self.position_trail)
            self.position_trail = deque(current_trail[-new_length:], maxlen=max(200, new_length))
            
            # Force redraw trail with new length
            if hasattr(self, 'trail_path'):
                self.trail_path.delete()
                delattr(self, 'trail_path')
            
            print(f"Updated trail length to {new_length} points")
                
        except Exception as e:
            print(f"Error updating trail settings: {e}")
            
    def toggle_trail_visibility(self):
        """Toggle trail visibility when checkbox is clicked."""
        try:
            if self.show_trail.get():
                print("Trail visibility enabled")
                # Force redraw trail if we have positions
                if len(self.position_trail) > 1:
                    self.redraw_trail()
            else:
                print("Trail visibility disabled")
                # Hide trail and markers
                if hasattr(self, 'trail_path'):
                    self.trail_path.delete()
                    delattr(self, 'trail_path')
                self.clear_trail_markers()
        except Exception as e:
            print(f"Error toggling trail visibility: {e}")
            
    def redraw_trail(self):
        """Force redraw the trail with current settings."""
        try:
            if not self.show_trail.get() or len(self.position_trail) < 2:
                return
                
            # Remove existing trail
            if hasattr(self, 'trail_path'):
                self.trail_path.delete()
                delattr(self, 'trail_path')
                
            # Get trail coordinates
            max_trail_points = self.trail_length.get()
            trail_coords = list(self.position_trail)[-max_trail_points:]
            
            if len(trail_coords) >= 2 and MAP_AVAILABLE and hasattr(self, 'map_widget'):
                self.trail_path = self.map_widget.set_path(
                    trail_coords, color="blue", width=3
                )
                print(f"Redrawn trail with {len(trail_coords)} points")
                
                # Update trail markers
                self.create_trail_point_markers_alternative()
                
        except Exception as e:
            print(f"Error redrawing trail: {e}")
            
    def update_trail_markers(self):
        """Update interactive trail point markers."""
        if not MAP_AVAILABLE or not hasattr(self, 'map_widget'):
            return
            
        try:
            # Remove existing trail markers
            self.clear_trail_markers()
            
            if not self.show_trail_points.get() or len(self.trail_data) < 2:
                return
                
            # Get trail points to display
            max_trail_points = self.trail_length.get()
            trail_points = list(self.trail_data)[-max_trail_points:]
            
            # Create small clickable markers for each trail point
            for i, point_data in enumerate(trail_points):
                try:
                    # Create a small marker for each point - no text to keep them small
                    marker = self.map_widget.set_marker(
                        point_data['lat'], point_data['lon'],
                        text="",  # No text to make them small dots
                        marker_color_circle="orange",
                        marker_color_outside=""
                    )
                    
                    # Store marker with associated data
                    marker_info = {
                        'marker': marker,
                        'data': point_data,
                        'index': i
                    }
                    self.trail_markers.append(marker_info)
                    
                    # Bind click event using tkinter binding on the marker's canvas item
                    # We'll use a different approach - store the data and check clicks
                    marker._data = point_data  # Store data directly on marker
                    
                except Exception as e:
                    print(f"Error creating marker {i}: {e}")
                    continue
                
            print(f"Created {len(self.trail_markers)} interactive trail point markers")
            
            # Set up click detection for the map
            self.setup_map_click_detection()
            
        except Exception as e:
            print(f"Error updating trail markers: {e}")
            
    def setup_map_click_detection(self):
        """Set up click detection for trail markers."""
        try:
            if hasattr(self, 'map_widget') and hasattr(self.map_widget, 'canvas'):
                # Bind click events to the map canvas
                self.map_widget.canvas.bind("<Button-1>", self.on_map_click)
        except Exception as e:
            print(f"Error setting up click detection: {e}")
            
    def on_map_click(self, event):
        """Handle clicks on the map to detect trail marker clicks."""
        try:
            if not self.trail_markers:
                return
                
            # Get click coordinates
            click_x = event.x
            click_y = event.y
            
            # Check if click is near any trail marker
            for marker_info in self.trail_markers:
                marker = marker_info['marker']
                
                # Get marker position on canvas (approximate)
                try:
                    # This is a rough approximation - we'll check if click is close to marker
                    marker_lat = marker_info['data']['lat']
                    marker_lon = marker_info['data']['lon']
                    
                    # Convert marker position to canvas coordinates (this is approximate)
                    # Since we can't easily get exact canvas coords, we'll use a different approach
                    # We'll show info for the closest marker to click
                    
                    # For now, let's use a simple distance-based approach
                    # This is a simplified implementation
                    pass
                    
                except Exception as e:
                    print(f"Error checking marker click: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error handling map click: {e}")
            
    def create_trail_point_markers_alternative(self):
        """Create clickable markers for trail points using the correct command parameter."""
        try:
            # Remove existing trail markers
            self.clear_trail_markers()
            
            if not self.show_trail_points.get() or len(self.trail_data) < 2:
                return
                
            # Get trail points to display  
            max_trail_points = self.trail_length.get()
            trail_points = list(self.trail_data)[-max_trail_points:]
            
            # Create clickable markers for trail points
            for i, point_data in enumerate(trail_points):
                try:
                    # Create marker with custom icon and command callback
                    if self.trail_marker_icon and PIL_AVAILABLE:
                        # Use custom circle icon
                        marker = self.map_widget.set_marker(
                            point_data['lat'], point_data['lon'],
                            icon=self.trail_marker_icon,
                            command=lambda marker_obj, data=point_data, idx=i: self.on_trail_marker_click(marker_obj, data, idx)
                        )
                        print(f"Created custom icon marker {i}")
                    else:
                        # Fallback to text marker
                        marker_text = f"•"  # Small dot character
                        marker = self.map_widget.set_marker(
                            point_data['lat'], point_data['lon'],
                            text=marker_text,
                            marker_color_circle="orange",
                            marker_color_outside="darkorange",
                            text_color="white",
                            font=("Arial", 10),
                            command=lambda marker_obj, data=point_data, idx=i: self.on_trail_marker_click(marker_obj, data, idx)
                        )
                        print(f"Created fallback text marker {i}")
                    
                    # Store marker info
                    self.trail_markers.append({
                        'marker': marker,
                        'data': point_data,
                        'index': i
                    })
                    
                    print(f"Created clickable marker {i} at {point_data['lat']:.6f}, {point_data['lon']:.6f}")
                    
                except Exception as e:
                    print(f"Error creating trail marker {i}: {e}")
                    continue
                    
            print(f"Created {len(self.trail_markers)} clickable trail point markers")
            
        except Exception as e:
            print(f"Error creating trail point markers: {e}")
            
    def on_trail_marker_click(self, marker_obj, point_data, index):
        """Handle clicks on trail point markers."""
        try:
            print(f"Trail marker {index} clicked!")
            print(f"Marker position: {marker_obj.position}")
            print(f"Point data: lat={point_data['lat']:.6f}, lon={point_data['lon']:.6f}")
            
            # Show the detailed information popup
            self.show_point_info(point_data)
            
        except Exception as e:
            print(f"Error handling trail marker click: {e}")
            messagebox.showerror("Error", f"Failed to show trail point info: {e}")
            
    def setup_global_marker_menu(self):
        """Set up a global menu system for trail markers."""
        try:
            # Add a global right-click menu item for showing nearest trail point
            if hasattr(self.map_widget, 'add_right_click_menu_command'):
                self.map_widget.add_right_click_menu_command(
                    "Show Nearest Trail Point Info",
                    command=self.show_nearest_trail_point_info
                )
                print("Added global trail point info menu")
        except Exception as e:
            print(f"Error setting up global marker menu: {e}")
            
    def show_nearest_trail_point_info(self, coordinates):
        """Show info for the trail point nearest to the clicked coordinates."""
        try:
            if not self.trail_markers:
                messagebox.showinfo("No Data", "No trail points available")
                return
                
            click_lat, click_lon = coordinates
            
            # Find the nearest trail point
            min_distance = float('inf')
            nearest_point = None
            
            for marker_info in self.trail_markers:
                point_data = marker_info['data']
                distance = self.calculate_distance_between_points(
                    click_lat, click_lon,
                    point_data['lat'], point_data['lon']
                )
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_point = point_data
                    
            if nearest_point and min_distance < 100:  # Within 100 meters
                self.show_point_info(nearest_point)
            else:
                messagebox.showinfo("No Data", f"No trail points within 100m of click location")
                
        except Exception as e:
            print(f"Error showing nearest trail point: {e}")
            messagebox.showerror("Error", f"Failed to show trail point info: {e}")
            
    def show_point_info_with_index(self, point_data, index):
        """Show detailed information about a trail point with index."""
        try:
            print(f"Showing info for trail point {index}")
            self.show_point_info(point_data)
        except Exception as e:
            print(f"Error showing point info for index {index}: {e}")
            
    def test_trail_point_info(self):
        """Test method to show info for the latest trail point."""
        try:
            if not self.trail_data:
                messagebox.showinfo("No Data", "No trail points available yet. Start simulation first!")
                return
                
            # Show info for the most recent trail point
            latest_point = list(self.trail_data)[-1]
            print("Testing trail point info with latest point...")
            self.show_point_info(latest_point)
            
        except Exception as e:
            print(f"Error testing trail point info: {e}")
            messagebox.showerror("Error", f"Failed to test trail point info: {e}")
            
    def clear_trail_markers(self):
        """Clear all trail point markers."""
        try:
            for marker_info in self.trail_markers:
                try:
                    marker_info['marker'].delete()
                except:
                    pass
            self.trail_markers.clear()
        except Exception as e:
            print(f"Error clearing trail markers: {e}")
            
    def toggle_trail_points(self):
        """Toggle trail point markers visibility."""
        try:
            if self.show_trail_points.get():
                print("Trail points enabled")
                self.create_trail_point_markers_alternative()
            else:
                print("Trail points disabled")
                self.clear_trail_markers()
        except Exception as e:
            print(f"Error toggling trail points: {e}")
            
    def calculate_distance_between_points(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two GPS points in meters."""
        import math
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in meters
        earth_radius = 6371000
        return earth_radius * c
        
    def show_point_info(self, point_data):
        """Show detailed information about a trail point."""
        try:
            # Calculate distances to previous and next points
            point_index = point_data['index']
            
            # Find previous and next points
            prev_distance = next_distance = "N/A"
            prev_point = next_point = None
            
            trail_list = list(self.trail_data)
            if point_index > 0:
                prev_point = trail_list[point_index - 1]
                prev_distance = self.calculate_distance_between_points(
                    point_data['lat'], point_data['lon'],
                    prev_point['lat'], prev_point['lon']
                )
                prev_distance = f"{prev_distance:.1f}m"
                
            if point_index < len(trail_list) - 1:
                next_point = trail_list[point_index + 1]
                next_distance = self.calculate_distance_between_points(
                    point_data['lat'], point_data['lon'],
                    next_point['lat'], next_point['lon']
                )
                next_distance = f"{next_distance:.1f}m"
            
            # Format timestamp
            from datetime import datetime
            timestamp = datetime.fromtimestamp(point_data['timestamp'])
            time_str = timestamp.strftime("%H:%M:%S.%f")[:-3]
            
            # Create info message
            info_text = f"""Trail Point #{point_data['index'] + 1}
            
📍 Position:
   Latitude: {point_data['lat']:.6f}°
   Longitude: {point_data['lon']:.6f}°

🏎️ Motion Data:
   Speed: {point_data['speed_kph']:.1f} km/h
   Heading: {point_data['heading']:.1f}°
   
📏 Distances:
   To Previous: {prev_distance}
   To Next: {next_distance}
   
⏰ Time: {time_str}

🎯 Targeting Mode: {point_data.get('targeting_info', {}).get('type', 'Unknown')}"""

            # Show info dialog
            messagebox.showinfo(f"Trail Point #{point_data['index'] + 1}", info_text)
            
        except Exception as e:
            print(f"Error showing point info: {e}")
            messagebox.showerror("Error", f"Failed to show point information: {e}")
                
    def change_map_layer(self, event=None):
        """Change the map layer/tile server with better error handling."""
        if MAP_AVAILABLE and hasattr(self, 'map_widget'):
            try:
                layer = self.map_layer.get()
                if layer == "OpenStreetMap":
                    # Use OpenStreetMap tiles with multiple servers for better reliability
                    self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
                elif layer == "Google normal":
                    # Google Maps normal view
                    self.map_widget.set_tile_server("https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}")
                elif layer == "Google satellite":
                    # Google Maps satellite view
                    self.map_widget.set_tile_server("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}")
                    
                # Force a small refresh by slightly adjusting the view
                current_pos = self.map_widget.get_position()
                self.map_widget.set_position(current_pos[0], current_pos[1])
                
            except Exception as e:
                print(f"Map layer change error: {e}")
                messagebox.showwarning("Map Layer", "Failed to change map layer. Please try again.")
                
    def map_right_click_target(self, coordinates):
        """Handle right-click on map to set target."""
        lat, lon = coordinates
        if self.current_targeting_mode.get() == "linear":
            self.target_lat.set(lat)
            self.target_lon.set(lon)
            messagebox.showinfo("Target Set", f"Linear target set to {lat:.6f}, {lon:.6f}")
        elif self.current_targeting_mode.get() == "circular":
            self.circle_center_lat.set(lat)
            self.circle_center_lon.set(lon)
            messagebox.showinfo("Center Set", f"Circular center set to {lat:.6f}, {lon:.6f}")
            
    def map_right_click_waypoint(self, coordinates):
        """Handle right-click on map to add waypoint."""
        if self.current_targeting_mode.get() == "waypoint":
            lat, lon = coordinates
            self.waypoints.append((lat, lon))
            self.update_waypoint_list()
            messagebox.showinfo("Waypoint Added", f"Added waypoint at {lat:.6f}, {lon:.6f}")
            
    def set_target_from_map(self):
        """Enable map click to set target mode."""
        messagebox.showinfo("Set Target", "Right-click on the map to set the target location.")
        
    # Waypoint management
    def add_waypoint(self):
        """Add a new waypoint via dialog."""
        dialog = WaypointDialog(self.root)
        if dialog.result:
            lat, lon = dialog.result
            self.waypoints.append((lat, lon))
            self.update_waypoint_list()
            
    def remove_waypoint(self):
        """Remove selected waypoint."""
        if hasattr(self, 'waypoint_listbox'):
            selection = self.waypoint_listbox.curselection()
            if selection:
                index = selection[0]
                if 0 <= index < len(self.waypoints):
                    self.waypoints.pop(index)
                    self.update_waypoint_list()
    
    def load_selected_circuit(self):
        """Load the selected F1 circuit into waypoints."""
        try:
            selected_name = self.circuit_var.get()
            print(f"DEBUG: Selected circuit name: '{selected_name}'")
            print(f"DEBUG: Available circuit_id_map keys: {list(self.circuit_id_map.keys())[:5]}...")  # Show first 5
            
            if not selected_name or selected_name not in self.circuit_id_map:
                messagebox.showwarning("No Circuit Selected", "Please select an F1 circuit first.")
                return
            
            circuit_id = self.circuit_id_map[selected_name]
            print(f"DEBUG: Circuit ID: {circuit_id}")
            
            waypoints = get_circuit_waypoints(circuit_id)
            print(f"DEBUG: Loaded {len(waypoints)} waypoints for {selected_name}")
            
            if not waypoints:
                messagebox.showerror("Circuit Error", f"Could not load waypoints for circuit: {selected_name}")
                return
            
            # Replace existing waypoints with circuit waypoints
            self.waypoints = waypoints
            print(f"DEBUG: Set self.waypoints to {len(self.waypoints)} waypoints")
            self.update_waypoint_list()
            print(f"DEBUG: Updated waypoint list display")
            
            # Teleport GPS to the starting position of the circuit
            if waypoints:
                start_lat, start_lon = waypoints[0]
                self.current_lat.set(start_lat)
                self.current_lon.set(start_lon)
                print(f"DEBUG: Teleported GPS to {start_lat}, {start_lon}")
                
                # If simulation is running, restart it with new waypoints
                if self.is_running:
                    self.stop_simulation()
                    self.root.after(100, self.start_simulation)  # Brief delay to ensure clean restart
            
            messagebox.showinfo("Circuit Loaded", 
                              f"Loaded {len(waypoints)} waypoints for {selected_name}\nGPS teleported to starting position: {start_lat:.6f}, {start_lon:.6f}")
            
        except Exception as e:
            print(f"DEBUG: Exception in load_selected_circuit: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Circuit Load Error", f"Error loading circuit: {str(e)}")
                    
                    
    # File operations
    def load_config(self):
        """Load configuration from file."""
        filename = filedialog.askopenfilename(
            title="Load Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r') as f:
                    config = json.load(f)
                self.apply_config(config)
                messagebox.showinfo("Success", "Configuration loaded successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load configuration: {e}")
                
    def save_config(self):
        """Save current configuration to file."""
        filename = filedialog.asksaveasfilename(
            title="Save Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                config = self.get_current_config()
                with open(filename, 'w') as f:
                    json.dump(config, f, indent=2)
                messagebox.showinfo("Success", "Configuration saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save configuration: {e}")
                
    def import_waypoints(self):
        """Import waypoints from file."""
        filename = filedialog.askopenfilename(
            title="Import Waypoints",
            filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            try:
                if filename.endswith('.json'):
                    with open(filename, 'r') as f:
                        data = json.load(f)
                        self.waypoints = data.get('waypoints', [])
                elif filename.endswith('.csv'):
                    import csv
                    with open(filename, 'r') as f:
                        reader = csv.reader(f)
                        self.waypoints = [(float(row[0]), float(row[1])) for row in reader if len(row) >= 2]
                        
                self.update_waypoint_list()
                messagebox.showinfo("Success", f"Imported {len(self.waypoints)} waypoints!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import waypoints: {e}")
                
    def export_waypoints(self):
        """Export waypoints to file."""
        if not self.waypoints:
            messagebox.showwarning("Warning", "No waypoints to export!")
            return
            
        filename = filedialog.asksaveasfilename(
            title="Export Waypoints",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            try:
                if filename.endswith('.json'):
                    with open(filename, 'w') as f:
                        json.dump({'waypoints': self.waypoints}, f, indent=2)
                elif filename.endswith('.csv'):
                    import csv
                    with open(filename, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerows(self.waypoints)
                        
                messagebox.showinfo("Success", "Waypoints exported successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export waypoints: {e}")
                
    def export_nmea_data(self):
        """Export NMEA data to file."""
        if not self.nmea_buffer:
            messagebox.showwarning("Warning", "No NMEA data to export!")
            return
        
        # Generate timestamp-based filename
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{timestamp}.nmea"
            
        filename = filedialog.asksaveasfilename(
            title="Export NMEA Data",
            initialfile=default_filename,
            defaultextension=".nmea",
            filetypes=[("NMEA files", "*.nmea"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    for timestamp, sentence in self.nmea_buffer:
                        # Export only the NMEA sentence without timestamp
                        f.write(f"{sentence}\n")
                messagebox.showinfo("Success", f"NMEA data exported successfully!\n{len(self.nmea_buffer)} sentences exported.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export NMEA data: {e}")
                
    def clear_nmea_buffer(self):
        """Clear the NMEA data buffer and display."""
        self.nmea_buffer.clear()
        if hasattr(self, 'nmea_text'):
            self.nmea_text.config(state=tk.NORMAL)
            self.nmea_text.delete(1.0, tk.END)
            self.nmea_text.config(state=tk.DISABLED)
            
    # Utility methods
    def get_current_config(self):
        """Get current configuration as dictionary."""
        return {
            'targeting_mode': self.current_targeting_mode.get(),
            'gps': {
                'lat': self.current_lat.get(),
                'lon': self.current_lon.get(),
                'altitude': self.current_alt.get(),
                'num_sats': self.num_sats.get()
            },
            'linear': {
                'target_lat': self.target_lat.get(),
                'target_lon': self.target_lon.get(),
                'speed': self.target_speed.get()
            },
            'circular': {
                'center_lat': self.circle_center_lat.get(),
                'center_lon': self.circle_center_lon.get(),
                'radius': self.circle_radius.get(),
                'angular_velocity': self.circle_angular_velocity.get(),
                'clockwise': self.circle_clockwise.get()
            },
            'waypoints': self.waypoints,
            'nmea_sentences': {name: var.get() for name, var in self.nmea_sentences.items()},
            'update_interval': self.update_interval.get()
        }
        
    def apply_config(self, config):
        """Apply configuration from dictionary."""
        if 'targeting_mode' in config:
            self.current_targeting_mode.set(config['targeting_mode'])
            
        if 'gps' in config:
            gps_config = config['gps']
            self.current_lat.set(gps_config.get('lat', 51.5074))
            self.current_lon.set(gps_config.get('lon', -0.1278))
            self.current_alt.set(gps_config.get('altitude', 0.0))
            self.num_sats.set(gps_config.get('num_sats', 12))
            
        if 'linear' in config:
            linear_config = config['linear']
            self.target_lat.set(linear_config.get('target_lat', 48.8566))
            self.target_lon.set(linear_config.get('target_lon', 2.3522))
            self.target_speed.set(linear_config.get('speed', 100.0))
            
        if 'circular' in config:
            circular_config = config['circular']
            self.circle_center_lat.set(circular_config.get('center_lat', 51.5074))
            self.circle_center_lon.set(circular_config.get('center_lon', -0.1278))
            self.circle_radius.set(circular_config.get('radius', 1000.0))
            self.circle_angular_velocity.set(circular_config.get('angular_velocity', 5.0))
            self.circle_clockwise.set(circular_config.get('clockwise', True))
            
        if 'waypoints' in config:
            self.waypoints = config['waypoints']
            self.update_waypoint_list()
            
        if 'nmea_sentences' in config:
            sentences_config = config['nmea_sentences']
            for name, value in sentences_config.items():
                if name in self.nmea_sentences:
                    self.nmea_sentences[name].set(value)
                    
        if 'update_interval' in config:
            self.update_interval.set(config['update_interval'])
            
        self.update_targeting_controls()
        
    def show_f1_presets(self):
        """Show F1 circuit presets dialog."""
        PresetDialog(self.root, self)
        
    def show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "About",
            "NMEA Injector\n\n"
            "A professional GPS simulation tool with advanced targeting modes:\n"
            "• Linear targeting for point-to-point navigation\n"
            "• Circular targeting for track simulation\n"
            "• Waypoint targeting for complex circuits\n\n"
            "Perfect for F1 telemetry, hardware testing, and navigation development."
        )
        
    def on_closing(self):
        """Handle application closing."""
        if self.is_running:
            self.stop_simulation()
        self.stop_updates.set()
        self.root.destroy()
        
    def run(self):
        """Start the GUI application."""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


class WaypointDialog:
    """Dialog for adding waypoints manually."""
    
    def __init__(self, parent):
        self.result = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add Waypoint")
        self.dialog.geometry("300x150")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (300 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (150 // 2)
        self.dialog.geometry(f"300x150+{x}+{y}")
        
        # Create form
        ttk.Label(self.dialog, text="Latitude:").grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        self.lat_var = tk.DoubleVar(value=51.5074)
        ttk.Entry(self.dialog, textvariable=self.lat_var, width=20).grid(row=0, column=1, padx=10, pady=5)
        
        ttk.Label(self.dialog, text="Longitude:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        self.lon_var = tk.DoubleVar(value=-0.1278)
        ttk.Entry(self.dialog, textvariable=self.lon_var, width=20).grid(row=1, column=1, padx=10, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="OK", command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).pack(side=tk.LEFT, padx=5)
        
        # Wait for dialog to close
        self.dialog.wait_window()
        
    def ok_clicked(self):
        try:
            self.result = (self.lat_var.get(), self.lon_var.get())
            self.dialog.destroy()
        except tk.TclError:
            messagebox.showerror("Error", "Please enter valid coordinates!")
            
    def cancel_clicked(self):
        self.dialog.destroy()


class PresetDialog:
    """Dialog for selecting F1 circuit presets."""
    
    def __init__(self, parent, gui):
        self.gui = gui
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("F1 Circuit Presets")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # F1 circuit presets
        self.circuits = {
            "Silverstone": [
                (52.0786, -1.0169), (52.0798, -1.0158), (52.0823, -1.0142),
                (52.0847, -1.0167), (52.0855, -1.0201), (52.0834, -1.0223),
                (52.0803, -1.0235), (52.0775, -1.0198), (52.0761, -1.0164), (52.0769, -1.0138)
            ],
            "Monaco": [
                (43.7347, 7.4205), (43.7342, 7.4198), (43.7338, 7.4195),
                (43.7335, 7.4201), (43.7340, 7.4210), (43.7345, 7.4208)
            ],
            "Spa-Francorchamps": [
                (50.4371, 5.9701), (50.4380, 5.9720), (50.4390, 5.9740),
                (50.4385, 5.9760), (50.4375, 5.9750), (50.4365, 5.9720)
            ]
        }
        
        # Circuit list
        ttk.Label(self.dialog, text="Select F1 Circuit:", font=('Arial', 12, 'bold')).pack(pady=10)
        
        self.circuit_listbox = tk.Listbox(self.dialog, height=8)
        for circuit in self.circuits.keys():
            self.circuit_listbox.insert(tk.END, circuit)
        self.circuit_listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Load Circuit", command=self.load_circuit).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
        
    def load_circuit(self):
        selection = self.circuit_listbox.curselection()
        if selection:
            circuit_name = list(self.circuits.keys())[selection[0]]
            waypoints = self.circuits[circuit_name]
            
            # Load waypoints into GUI
            self.gui.waypoints = waypoints
            self.gui.current_targeting_mode.set("waypoint")
            self.gui.update_targeting_controls()
            self.gui.update_waypoint_list()
            
            # Set starting position to first waypoint
            if waypoints:
                self.gui.current_lat.set(waypoints[0][0])
                self.gui.current_lon.set(waypoints[0][1])
                
            messagebox.showinfo("Success", f"Loaded {circuit_name} circuit with {len(waypoints)} waypoints!")
            self.dialog.destroy()


def main():
    """Main entry point for the GUI application."""
    try:
        app = EnhancedNMEAGUI()
        app.run()
    except Exception as e:
        print(f"Failed to start GUI: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
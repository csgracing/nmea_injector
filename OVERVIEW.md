# NMEA Injector: Technical Overview

### Purpose

`nmea_injector` is a configurable NMEA 0183 GPS data simulator. It is designed for testing GPS-dependent hardware or software by providing a realistic, controllable stream of NMEA sentences without requiring a live GPS signal. The application is built with Python, using Tkinter for the GUI.

### Core Architecture

The application's architecture is designed around a clear separation of concerns, primarily dividing the UI, simulation engine, and movement logic. This makes the system modular and extensible.

It employs a multi-threaded model to ensure a responsive UI:
1.  **Main Thread**: Runs the Tkinter event loop for the GUI.
2.  **Simulation Thread**: A background thread that handles the core simulation loop, including position calculations and NMEA sentence generation. This prevents the UI from freezing during simulation.
3.  **GUI Update Thread**: A background thread that fetches data from the simulator and schedules updates to the UI components on the main thread, acting as a bridge between the simulation and the UI.

### Component Breakdown

**1. UI Layer (`gui.py`)**
*   **Role**: Manages the application's state and all user interaction. It acts as a client to the simulation engine.
*   **Functionality**:
    *   Constructs the `Simulator` instance and configures it based on user input (e.g., selecting a targeting mode, setting speed).
    *   Instantiates the appropriate `TargetingStrategy` and injects it into the `Simulator`.
    *   Communicates with the `Simulator` thread to start/stop the simulation.
    *   Retrieves data from the simulator to update the `tkintermapview` visualization and the NMEA data panel.

**2. Simulation Core (`simulator.py`)**
*   **Role**: Orchestrates the entire simulation.
*   **Functionality**:
    *   The `Simulator` class holds a `GpsReceiver` model, which represents the current state of the simulated device (position, speed, satellites, etc.).
    *   The `serve()` method spawns the main simulation loop in a background `threading.Thread`.
    *   It utilizes the **Strategy design pattern** by delegating all movement calculations to a `TargetingStrategy` object. This decouples the simulation loop from the specifics of any movement algorithm.

**3. Strategy Layer (`targeting.py`)**
*   **Role**: Encapsulates the algorithms for GPS movement.
*   **Functionality**:
    *   Defines the `TargetingStrategy` abstract base class, which establishes a contract for all movement algorithms. The key method is `get_next_position()`.
    *   This design allows new movement patterns to be added with no modification to the `Simulator` class.
    *   Concrete implementations include:
        *   `StaticTargeting`: No movement.
        *   `LinearTargeting`: Moves towards a fixed coordinate.
        *   `CircularTargeting`: Follows a circular path.
        *   `WaypointTargeting`: Follows a sequence of coordinates. Supports both manual (fixed speed) and dynamic speed control modes with configurable vehicle performance profiles.
    *   **Vehicle Profile System**: The `VEHICLE_PROFILES` dictionary defines performance characteristics (top speed, acceleration rates, braking rates, minimum corner speeds) for different vehicle types (F1, Go-Kart, Bicycle).
    *   **Path Smoothing Engine**: Raw waypoints are converted into high-resolution smooth curves using scipy spline interpolation for precise movement control.
    *   **Curvature Analysis**: Speed decisions use path curvature calculations. Uses Menger curvature formula to calculate radius of curvature at each point, providing physically accurate speed control.
    *   **Anti-Chattering Logic**: Sliding sub-windows analyze multiple points ahead to find the tightest upcoming curve, ensuring stable speed control on complex waypoint data.

**4. Data Loading (`circuit_loader.py`)**
*   **Role**: A utility module that acts as a data provider for the `WaypointTargeting` strategy.
*   **Functionality**:
    *   Parses waypoint data from the `circuits.geojson` file.
    *   Decouples the waypoint data source from the movement logic itself.

### Execution Flow

1.  **Instantiation**: The `EnhancedNMEAGUI` class initializes a `Simulator` instance.
2.  **Configuration**: User selections in the GUI lead to the instantiation of a specific `TargetingStrategy`. For `WaypointTargeting`, the GUI determines the operational mode:
    *   Manual mode: Instantiated with fixed `speed_kph` parameter
    *   Dynamic mode: Instantiated with `mode='dynamic'` and `speed_profile` key, which triggers initialization of vehicle-specific performance parameters from `VEHICLE_PROFILES`
3.  **Activation**: The chosen strategy is injected into the `Simulator` via `set_targeting()`. When the user clicks "Start," `simulator.serve(blocking=False)` is called, launching the simulation in a background thread.
4.  **Simulation Loop (Background Thread)**:
    *   The loop iterates at a configurable frequency (e.g., 5 Hz).
    *   Within a thread lock, it calls `__step()`, which delegates to the active `TargetingStrategy`'s `get_next_position()` method.
    *   For `WaypointTargeting` in dynamic mode, this triggers the turn analysis algorithm and speed calculation before position updates.
    *   The strategy returns the new GPS state (lat, lon, heading, speed), where speed reflects either the fixed value (manual mode) or the dynamically calculated value (dynamic mode).
    *   The `Simulator` updates its internal `GpsReceiver` model, which in turn generates the corresponding NMEA sentence strings.
5.  **UI Update Loop (Background Thread)**:
    *   This loop fetches the latest NMEA sentences and GPS state from the `Simulator`.
    *   To maintain thread safety with Tkinter, it uses `root.after()` to schedule the actual UI component updates on the main thread.

### WaypointTargeting: Technical Implementation

The `WaypointTargeting` class implements movement simulation with two operational modes:

**Constructor Parameters**:
*   `mode`: Either `'manual'` (fixed speed) or `'dynamic'` (vehicle profile-based)
*   `speed_profile`: String key into `VEHICLE_PROFILES` dictionary when using dynamic mode
*   `waypoints`: List of (lat, lon) tuples defining the route
*   `arrival_threshold_meters`: Distance threshold for waypoint completion detection

**Dynamic Speed Control Algorithm** (Curvature-Based):
1.  **Path Preprocessing**: Raw waypoints cleaned to remove duplicate start/end points, then converted to smooth splines using `scipy.interpolate.splprep` with cubic interpolation
2.  **High-Resolution Path**: Original waypoints expanded 20x into smooth curves for precise curvature analysis
3.  **Vehicle Position Tracking**: Real-time closest-point detection on the smoothed path eliminates waypoint-to-waypoint jumping
4.  **Curvature Analysis**: `_calculate_radius_of_curvature()` uses Menger curvature formula on triplets of points to calculate actual curve tightness
5.  **Anti-Chattering**: Each analysis point examines a 15-point sub-window ahead, using the minimum radius found to prevent speed oscillations
6.  **Speed Target Mapping**: 
    *   High-speed sections (radius >500): Target top speed
    *   Tight corners (radius <50m): Target minimum corner speed
    *   Medium curves: Linear interpolation between speed limits
7.  **Proactive Braking**: Existing braking distance calculations now use the more stable curvature-based speed targets
8.  **Physics Integration**: Speed adjusted using vehicle-specific acceleration/braking rates with proper time-step integration

### Architecture Diagram
```mermaid
flowchart TD
    subgraph "User Interface (gui.py)"
        A[GUI Controls] --> B{Start/Stop};
        C[Map View] --> D[GPS Marker & Trail];
        E[NMEA Data Panel];
    end

    subgraph "Simulation Engine (simulator.py)"
        F[Simulator] -- Manages --> G[GpsReceiver Model];
        F -- Uses --> H{Targeting Strategy};
    end

    subgraph "Movement Logic (targeting.py)"
        H -- Is a --> I[StaticTargeting];
        H -- Is a --> J[LinearTargeting];
        H -- Is a --> K[CircularTargeting];
        H -- Is a --> L[WaypointTargeting];
    end

    subgraph "Data Sources"
        M[circuits.geojson] -- Loaded by --> N[circuit_loader.py];
    end

    B -- "Start" --> F;
    F -- "Updates" --> G;
    F -- "Generates" --> O[NMEA Sentences];
    
    subgraph "GUI Update Loop"
        P[GUI Thread] -- "Fetches" --> O;
        P -- "Updates" --> C;
        P -- "Updates" --> E;
    end

    A -- "Selects Circuit" --> N;
    N -- "Provides Waypoints" --> L;
    F -- "Sets Strategy" --> L;

    style F fill:#51355e,stroke:#333,stroke-width:2px
    style H fill:#3c4063,stroke:#333,stroke-width:2px
```

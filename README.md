
#  NMEA Simulator (nmea_injector) <img width="65" height="65" alt="icon" src="https://github.com/user-attachments/assets/13e8460c-e595-41aa-a759-9275b8a6008a" />

A NMEA GPS simulator with GUI, F1 race circuits, and targeting capabilities.

## Quick Start

### Installation
```bash
pip install -e .
```

### Launch GUI
```bash
# After installation, run:
nmea_injector

# Or alternatively:
nmea_injector-gui
```

### For Developers
If you're looking to contribute or understand the codebase, the **[Overview](OVERVIEW.md)** provides a detailed breakdown of the project's structure, components, and data flow.

##  Features
<img width="3839" height="2086" alt="demo" src="https://github.com/user-attachments/assets/d35a8d03-d224-48fd-b6b2-de6b290aae54" />

### GUI
- **Map Visualization**: Normal and satellite view modes
- **Real-Time Tracking**: Current and historical GPS data points
- **Point Details**: Clickable data points with comprehensive information

### NMEA Data Generation
- **Targeting Modes**:
  -  **Static**: Fixed position simulation
  -  **Linear**: Straight-line movement
  -  **Circular**: Circular path simulation
  -  **Waypoints**: F1 race circuit navigation

### F1 Race Circuits
- **Realistic Data**: Preset Formula 1 tracks for authentic GPS simulation


### Data Output & Configuration
- **Live NMEA Stream**: Real-time exportable data feed
- **Sentence Types**: Configurable NMEA sentence output (GGA, GLL, GSA, etc.)
- **Satellite Control**: Adjustable number of simulated satellites

## In Progress

### Edge Case & Load Testing
- [ ] **Data Integrity Testing**
  - [ ] Invalid checksums simulation
  - [ ] Malformed sentence generation
  - [ ] Satellite signal fluctuation
  - [ ] GPS data jumps and inconsistencies
  - [ ] Stale data scenarios

- [ ] **Performance Testing**
  - [ ] High-frequency system load testing
  - [ ] Data burst simulation
  - [ ] Stress testing capabilities

### Integration
- [ ] **CAN Bus Support**: Native CAN-specific output format
- [ ] **CLI Documentation**: Comprehensive command-line interface guide
- [ ] **API Integration**: Programmatic access to simulator functions

### Known Issues
- The data stream in the GUI may occasionally stop updating with new data.

## Designed for

### NMEA Compliance & Hardware
- **NMEA Standard**: [NMEA 0183](https://gpsd.gitlab.io/gpsd/NMEA.html) compliant GPS data simulation
- **Target Hardware**: [Vector CANgps Module](https://cdn.vector.com/cms/content/products/gl_logger/Docs/LoggerAccessories_ProductInformation_EN.pdf) (page 11, 5 Hz data rate)
- **Output Formats**: 
  - RS232 in NMEA0183 format
  - CAN bus integration


## Credits

- **[nmeasim](https://gitlab.com/nmeasim/nmeasim)** - Core NMEA simulation foundation
- **[F1 Circuits GPS Data](https://github.com/bacinger/f1-circuits)** - Formula 1 circuit waypoint coordinates
- **[nmeagen.org](https://nmeagen.org/)** - NMEA sentence validation and testing

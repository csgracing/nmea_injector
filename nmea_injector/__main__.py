#!/usr/bin/env python3
"""
Main entry point for nmea-injector package.
Launches the GUI application when package is run directly.
"""

if __name__ == "__main__":
    try:
        # Try relative import first (when run as module)
        from .gui import main
    except ImportError:
        # Fall back to absolute import (when run as script)
        from nmea_injector.gui import main
    
    main()
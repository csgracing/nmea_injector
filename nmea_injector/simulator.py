import datetime
import math
import threading
import time
from random import random
from sys import stdout
from typing import Optional

from . import models
from .targeting import TargetingStrategy, StaticTargeting


class Simulator(object):
    '''
    NMEA simulator with pluggable targeting strategies.
    
    Provides simulated NMEA output based on a models.GnssReceiver instance.
    Supports satellite model perturbation, random walk heading adjustment,
    and advanced targeting modes (linear, circular, waypoint).
    '''

    def __init__(self, gps=None, glonass=None, static=False, heading_variation=45):
        ''' 
        Initialise the  GPS simulator instance.
        
        Args:
            gps: GPS receiver model instance
            glonass: Glonass receiver model instance (optional)
            static: If True, GPS position remains static
            heading_variation: Maximum random heading variation in degrees
        '''
        self.__worker = None
        self.__run = threading.Event()
        self.lock = threading.Lock()  # Initialize lock first
        
        # Stream-based data collection for GUI
        self._sentence_stream = []  # Buffer for new sentences since last read
        self._stream_lock = threading.Lock()  # Separate lock for stream operations
        
        # Automatic file logging
        self._auto_log_file = None
        self._log_file_handle = None
        
        if gps is None:
            gps = models.GpsReceiver()
        self.gps = gps
        self.glonass = glonass
        self.gnss = [gps]
        if glonass is not None:
            self.gnss.append(glonass)
            
        self.heading_variation = heading_variation
        self.static = static
        
        #  targeting system
        self._targeting_strategy: Optional[TargetingStrategy] = None
        if static:
            self._targeting_strategy = StaticTargeting()
            
        # Legacy compatibility - will be converted to LinearTargeting when set
        self._target = None  # Initialize private variable
        
        self.interval = 1.0
        self.step = 1.0
        self.delimiter = '\r\n'

    def set_targeting(self, strategy: TargetingStrategy):
        """
        Set the targeting strategy for GPS movement simulation.
        
        Args:
            strategy: A targeting strategy instance (LinearTargeting, CircularTargeting, etc.)
        """
        with self.lock:
            self._targeting_strategy = strategy
            
    def get_targeting(self) -> Optional[TargetingStrategy]:
        """Get the current targeting strategy."""
        return self._targeting_strategy
        
    def clear_targeting(self):
        """Remove any targeting strategy (GPS will remain static)."""
        with self.lock:
            self._targeting_strategy = StaticTargeting()

    @property
    def target(self):
        """Legacy property for backward compatibility."""
        return self._target
        
    @target.setter
    def target(self, value):
        """Legacy property setter - converts to LinearTargeting for compatibility."""
        self._target = value
        if value is not None:
            from .targeting import LinearTargeting
            lat, lon = value
            linear_targeting = LinearTargeting(
                target_lat=lat, 
                target_lon=lon,
                speed_kph=self.gps.kph if self.gps.kph else 50.0
            )
            self.set_targeting(linear_targeting)
        else:
            self.clear_targeting()

    def __step(self, duration=1.0):
        '''
        simulation step that uses pluggable targeting strategies.
        
        Iterates a simulation step for the specified duration in seconds,
        moving the GPS instance and updating state based on the current
        targeting strategy.
        
        Should be called while under lock conditions.
        '''
        if self.static and self._targeting_strategy is None:
            return

        duration_hrs = duration / 3600.0

        # Update satellite perturbations (same as original)
        for gnss in self.gnss:
            if gnss.date_time is not None and (
                    gnss.num_sats > 0 or gnss.has_rtc):
                gnss.date_time += datetime.timedelta(seconds=duration)

            perturbation = math.sin(gnss.date_time.second * math.pi / 30) / 2
            for satellite in gnss.satellites:
                satellite.snr += perturbation
                satellite.elevation += perturbation
                satellite.azimuth += perturbation

            #  GPS movement using targeting strategies
            if gnss.has_fix and self._targeting_strategy is not None:
                if self._targeting_strategy.is_active():
                    # Get next position from targeting strategy
                    new_lat, new_lon, new_heading, new_speed = self._targeting_strategy.get_next_position(
                        current_lat=gnss.lat or 0.0,
                        current_lon=gnss.lon or 0.0,
                        current_heading=gnss.heading or 0.0,
                        duration_seconds=duration,
                        current_speed_kph=gnss.kph or 0.0
                    )
                    
                    # Update GPS state
                    gnss.lat = new_lat
                    gnss.lon = new_lon
                    gnss.heading = new_heading
                    gnss.kph = new_speed
                    
                    # Apply heading variation if specified
                    if self.heading_variation and gnss.heading is not None:
                        rand_heading = (random() - 0.5) * self.heading_variation
                        gnss.heading = (gnss.heading + rand_heading) % 360
                        
                else:
                    # Targeting strategy is inactive - apply legacy random walk
                    if self.heading_variation and gnss.heading is not None:
                        rand_heading = (random() - 0.5) * self.heading_variation
                        gnss.heading = (gnss.heading + rand_heading) % 360
                    gnss.move(duration)

    def __write(self, output, sentence, delimiter):
        string = f'{sentence}{delimiter}'
        try:
            output.write(string)
        except TypeError:
            output.write(string.encode())

    def __action(self, output, delimiter):
        ''' Worker thread action for the GPS simulator - outputs data to the specified output at 1PPS.
        '''
        self.__run.set()
        while self.__run.is_set():
            start = time.monotonic()
            if self.__run.is_set():
                with self.lock:
                    sentences = []
                    for gnss in self.gnss:
                        sentences += gnss.get_output()
                    
                    # Add to stream for GUI consumption
                    if sentences:
                        self._add_to_stream(sentences)
                        
            if self.__run.is_set():
                for sentence in sentences:
                    if not self.__run.is_set():
                        break
                    self.__write(output, sentence, delimiter)

            if self.__run.is_set():
                time.sleep(0.1)  # Minimum sleep to avoid long lock ups
            while self.__run.is_set() and time.monotonic() - start < self.interval:
                time.sleep(0.1)
            if self.__run.is_set():
                with self.lock:
                    if self.step == self.interval:
                        self.__step(time.monotonic() - start)
                    else:
                        self.__step(self.step)

    def serve(self, output=None, blocking=True, delimiter='\r\n'):
        ''' Start serving GPS simulator to the file-like output (default stdout).
            and optionally blocks until an exception (e.g KeyboardInterrupt).
        '''
        if output is None:
            output = stdout
        self.kill()
        self.__worker = threading.Thread(
            target=self.__action,
            kwargs=dict(output=output, delimiter=delimiter))
        self.__worker.daemon = True
        self.__worker.start()
        if blocking:
            try:
                while self.__worker.is_alive():
                    self.__worker.join(60)
            except:
                self.kill()

    def kill(self):
        ''' Issue the kill command to the GPS simulator thread and wait for it to die.
        '''
        try:
            while self.__worker and self.__worker.is_alive():
                self.__run.clear()
                self.__worker.join(0.1)
        except KeyboardInterrupt:
            pass
        # Note: We don't automatically stop auto-logging here because
        # kill() is called by serve() to clean up before starting a new thread

    def is_running(self):
        ''' Is the simulator currently running?
        '''
        return self.__run.is_set() or self.__worker and self.__worker.is_alive()

    def get_output(self, duration):
        ''' Instantaneous generator for the GPS simulator.
        Yields one NMEA sentence at a time, without the EOL.
        '''
        with self.lock:
            start = self.gps.date_time
        now = start
        while (now - start).total_seconds() < duration:
            with self.lock:
                output = []
                for gnss in self.gnss:
                    output += gnss.get_output()
                for sentence in output:
                    yield sentence
                self.__step(self.step)
                now = self.gps.date_time

    def generate(self, duration, output=None, delimiter='\r\n'):
        ''' Instantaneous generator for the GPS simulator.
        Synchronously writes data to a file-like output (stdout by default).
        '''
        if output is None:
            output = stdout
        for sentence in self.get_output(duration):
            self.__write(output, sentence, delimiter)

    def output_latest(self, output=None, delimiter='\r\n'):
        '''Output the latest fix to a specified file-like output (stdout by default).
        '''
        if output is None:
            output = stdout
        with self.lock:
            for gnss in self.gnss:
                for sentence in gnss.get_output():
                    self.__write(output, sentence, delimiter)
                    
    def get_targeting_status(self):
        """Get status information about the current targeting strategy."""
        if self._targeting_strategy is None:
            return {"type": "none", "active": False}
        return self._targeting_strategy.get_status()

    def start_auto_logging(self, filename=None):
        """Start automatic logging of all NMEA sentences to a file."""
        import os
        
        if filename is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create logs directory in the current working directory
            logs_dir = os.path.join(os.getcwd(), "logs")
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)
                print(f"Created logs directory: {logs_dir}")
            
            filename = os.path.join(logs_dir, f"nmea_log_{timestamp}.nmea")
        
        try:
            if self._log_file_handle:
                self.stop_auto_logging()
            
            self._auto_log_file = os.path.abspath(filename)
            self._log_file_handle = open(self._auto_log_file, 'w', encoding='utf-8', buffering=1)  # Line buffered
            print(f"Started automatic NMEA logging to: {self._auto_log_file}")
            
            return self._auto_log_file
        except Exception as e:
            print(f"Failed to start auto logging: {e}")
            import traceback
            traceback.print_exc()
            return None

    def stop_auto_logging(self):
        """Stop automatic logging and close the file."""
        if self._log_file_handle:
            try:
                self._log_file_handle.flush()
                self._log_file_handle.close()
                print(f"Stopped automatic NMEA logging to: {self._auto_log_file}")
            except Exception as e:
                print(f"Error closing log file: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self._log_file_handle = None
                self._auto_log_file = None

    def get_log_filename(self):
        """Get the current auto log filename, if logging is active."""
        return self._auto_log_file

    def get_new_sentences(self):
        """Get all new NMEA sentences since the last call to this method."""
        with self._stream_lock:
            new_sentences = self._sentence_stream.copy()
            self._sentence_stream.clear()
            return new_sentences

    def _add_to_stream(self, sentences):
        """Add sentences to the stream buffer and log to file if active."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Millisecond precision
        
        with self._stream_lock:
            for sentence in sentences:
                sentence_with_timestamp = (timestamp, sentence)
                self._sentence_stream.append(sentence_with_timestamp)
                
                # Auto-log to file if active
                if self._log_file_handle:
                    try:
                        self._log_file_handle.write(f"{sentence}\n")
                        self._log_file_handle.flush()  # Ensure data is written to disk immediately
                    except Exception as e:
                        print(f"Error writing to log file: {e}")
                        # Don't stop the stream, just log the error
"""Scale driver for serial communication with the weight scale."""

import asyncio
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import serial

from app.models import WeightSample
from app.config import Settings

logger = logging.getLogger(__name__)

# Regex pattern to extract weight readings
# Matches: "S 00.072kg" or "U 06.250kg" (with optional trailing character)
WEIGHT_PATTERN = re.compile(r'([US])\s*(\d+\.?\d*)kg')


def parse_weight_data(data: str) -> Optional[WeightSample]:
    """Parse weight data from serial buffer and return the latest reading.
    
    Args:
        data: Raw string data from serial port
        
    Returns:
        WeightSample with the latest reading, or None if no valid reading found
    """
    # Clean the data: strip whitespace and remove null characters
    cleaned = data.strip().replace('\x00', '')
    
    if not cleaned:
        return None
    
    # Find all matches in the buffer
    matches = WEIGHT_PATTERN.findall(cleaned)
    
    if not matches:
        return None
    
    # Use the last match as the most recent reading
    status, kg_str = matches[-1]
    
    try:
        kg_value = float(kg_str)
        # Clamp negative values to 0
        grams = max(0.0, kg_value * 1000.0)
        
        return WeightSample(
            grams=grams,
            timestamp=datetime.now(timezone.utc),
            status=status
        )
    except ValueError:
        logger.warning(f"Failed to parse weight value: {kg_str}")
        return None


def find_last_match_position(data: str) -> int:
    """Find the position after the last complete weight match.
    
    Returns the index where we should trim the buffer to keep only
    remaining unprocessed data.
    """
    last_pos = 0
    for match in WEIGHT_PATTERN.finditer(data):
        # Move past the 'kg' and any trailing character (a, b, c, d, etc.)
        end_pos = match.end()
        # Check if there's a trailing status character after 'kg'
        if end_pos < len(data) and data[end_pos].isalpha():
            end_pos += 1
        last_pos = end_pos
    return last_pos


def auto_detect_serial_port(baudrate: int = 9600) -> Optional[str]:
    """Auto-detect the scale's serial port.
    
    Checks /dev/ttyUSB0 through /dev/ttyUSB10 for a working connection.
    
    Args:
        baudrate: Baud rate to use for testing connections
        
    Returns:
        Path to the first successfully opened serial port, or None
    """
    for i in range(11):  # 0 to 10
        port_path = f"/dev/ttyUSB{i}"
        
        if not Path(port_path).exists():
            continue
            
        try:
            # Try to open the port briefly
            with serial.Serial(port_path, baudrate=baudrate, timeout=0.5) as ser:
                logger.info(f"Successfully detected serial port: {port_path}")
                return port_path
        except (serial.SerialException, OSError) as e:
            logger.debug(f"Could not open {port_path}: {e}")
            continue
    
    logger.warning("No serial port found in /dev/ttyUSB0-10")
    return None


class ScaleDriver:
    """Driver for reading weight data from a serial-connected scale.
    
    This class manages serial communication with the scale hardware,
    continuously reading data in a background task and maintaining
    the latest weight reading in memory.
    """
    
    def __init__(self, settings: Settings):
        """Initialize the scale driver.
        
        Args:
            settings: Application settings containing serial port configuration
        """
        self._settings = settings
        self._serial: Optional[serial.Serial] = None
        self._latest_reading: Optional[WeightSample] = None
        self._lock = threading.Lock()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._buffer = ""
        self._reconnect_delay = 2.0  # seconds between reconnection attempts
        
    async def start(self) -> None:
        """Start the background reading task."""
        if self._running:
            logger.warning("ScaleDriver already running")
            return
            
        self._running = True
        self._task = asyncio.create_task(self._read_loop())
        logger.info("ScaleDriver started")
        
    async def stop(self) -> None:
        """Stop the background reading task and close serial connection."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            
        self._close_serial()
        logger.info("ScaleDriver stopped")
        
    def get_latest(self) -> Optional[WeightSample]:
        """Get the latest weight reading (thread-safe).
        
        Returns:
            The most recent WeightSample, or None if no reading available
        """
        with self._lock:
            return self._latest_reading
            
    def _set_latest(self, sample: WeightSample) -> None:
        """Set the latest weight reading (thread-safe)."""
        with self._lock:
            self._latest_reading = sample
            
    def _open_serial(self) -> bool:
        """Open the serial connection.
        
        Returns:
            True if connection was successful, False otherwise
        """
        port = self._settings.SCALE_PORT
        baudrate = self._settings.SCALE_BAUDRATE
        
        # Auto-detect if no port specified
        if port is None:
            port = auto_detect_serial_port(baudrate)
            if port is None:
                logger.error("Failed to auto-detect serial port")
                return False
                
        try:
            self._serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=0.1
            )
            logger.info(f"Connected to serial port: {port} at {baudrate} baud")
            return True
        except (serial.SerialException, OSError) as e:
            logger.error(f"Failed to open serial port {port}: {e}")
            self._serial = None
            return False
            
    def _close_serial(self) -> None:
        """Close the serial connection."""
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
                logger.info("Serial connection closed")
            except Exception as e:
                logger.warning(f"Error closing serial connection: {e}")
        self._serial = None
        
    async def _read_loop(self) -> None:
        """Main reading loop that runs in the background."""
        first_reading_logged = False
        
        while self._running:
            # Ensure we have a serial connection
            if self._serial is None or not self._serial.is_open:
                if not self._open_serial():
                    logger.warning(f"Retrying serial connection in {self._reconnect_delay}s...")
                    await asyncio.sleep(self._reconnect_delay)
                    continue
                    
            try:
                # Read available data
                if self._serial.in_waiting > 0:
                    raw_data = self._serial.read(self._serial.in_waiting)
                    try:
                        decoded = raw_data.decode('ascii', errors='ignore')
                        self._buffer += decoded
                    except Exception as e:
                        logger.warning(f"Failed to decode serial data: {e}")
                        
                    # Try to parse the buffer
                    sample = parse_weight_data(self._buffer)
                    
                    if sample is not None:
                        self._set_latest(sample)
                        
                        if not first_reading_logged:
                            logger.info(f"First valid weight reading: {sample.grams}g")
                            first_reading_logged = True
                            
                        # Trim the buffer to keep only unprocessed data
                        trim_pos = find_last_match_position(self._buffer)
                        if trim_pos > 0:
                            self._buffer = self._buffer[trim_pos:]
                            
                        # Prevent buffer from growing too large
                        if len(self._buffer) > 1000:
                            self._buffer = self._buffer[-500:]
                            
                # Sleep to avoid busy loop
                await asyncio.sleep(self._settings.SCALE_READ_INTERVAL_MS / 1000.0)
                
            except serial.SerialException as e:
                logger.error(f"Serial communication error: {e}")
                self._close_serial()
                self._buffer = ""
                await asyncio.sleep(self._reconnect_delay)
                
            except Exception as e:
                logger.error(f"Unexpected error in read loop: {e}")
                await asyncio.sleep(self._reconnect_delay)



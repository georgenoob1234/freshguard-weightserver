"""Tests for the scale driver parsing logic."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from app.scale_driver import (
    parse_weight_data,
    find_last_match_position,
    auto_detect_serial_port,
    WEIGHT_PATTERN
)


class TestWeightPattern:
    """Tests for the weight regex pattern."""
    
    def test_matches_stable_reading(self):
        """Test matching stable (S) readings."""
        match = WEIGHT_PATTERN.search("S 00.072kg")
        assert match is not None
        assert match.group(1) == "S"
        assert match.group(2) == "00.072"
        
    def test_matches_unstable_reading(self):
        """Test matching unstable (U) readings."""
        match = WEIGHT_PATTERN.search("U 06.250kg")
        assert match is not None
        assert match.group(1) == "U"
        assert match.group(2) == "06.250"
        
    def test_matches_with_trailing_character(self):
        """Test matching readings with trailing status character."""
        match = WEIGHT_PATTERN.search("S 00.072kgd")
        assert match is not None
        assert match.group(2) == "00.072"
        
    def test_matches_zero_weight(self):
        """Test matching zero weight."""
        match = WEIGHT_PATTERN.search("S 00.000kga")
        assert match is not None
        assert match.group(2) == "00.000"


class TestParseWeightData:
    """Tests for the parse_weight_data function."""
    
    def test_parse_simple_reading(self):
        """Test parsing a simple weight reading."""
        sample = parse_weight_data("S 00.072kgd")
        assert sample is not None
        assert sample.grams == 72.0
        assert sample.status == "S"
        
    def test_parse_returns_last_match(self):
        """Test that parser returns the last match from concatenated data."""
        data = "S 00.072kgdS 00.072kgdU 06.250kgf"
        sample = parse_weight_data(data)
        assert sample is not None
        assert sample.grams == 6250.0
        assert sample.status == "U"
        
    def test_parse_multiple_unstable_readings(self):
        """Test parsing multiple unstable readings."""
        data = "U 00.319kglU 00.555kgbU 00.503kga"
        sample = parse_weight_data(data)
        assert sample is not None
        assert sample.grams == 503.0
        assert sample.status == "U"
        
    def test_parse_zero_weight(self):
        """Test parsing zero weight returns 0 grams."""
        sample = parse_weight_data("S 00.000kga")
        assert sample is not None
        assert sample.grams == 0.0
        
    def test_parse_large_weight(self):
        """Test parsing a large weight value."""
        sample = parse_weight_data("S 12.345kgx")
        assert sample is not None
        assert sample.grams == 12345.0
        
    def test_parse_empty_string_returns_none(self):
        """Test parsing empty string returns None."""
        sample = parse_weight_data("")
        assert sample is None
        
    def test_parse_whitespace_only_returns_none(self):
        """Test parsing whitespace-only string returns None."""
        sample = parse_weight_data("   \n\t  ")
        assert sample is None
        
    def test_parse_garbage_data_returns_none(self):
        """Test parsing garbage data returns None."""
        sample = parse_weight_data("garbage data without weight")
        assert sample is None
        
    def test_parse_strips_null_characters(self):
        """Test that null characters are stripped from data."""
        sample = parse_weight_data("S\x00 00.100\x00kga")
        assert sample is not None
        assert sample.grams == 100.0
        
    def test_parse_partial_data_returns_none(self):
        """Test parsing partial/incomplete data."""
        sample = parse_weight_data("S 00.")
        assert sample is None
        
    def test_timestamp_is_utc(self):
        """Test that parsed sample has UTC timestamp."""
        sample = parse_weight_data("S 00.100kga")
        assert sample is not None
        assert sample.timestamp.tzinfo == timezone.utc
        
    def test_parse_no_space_after_status(self):
        """Test parsing when there's no space after status character."""
        sample = parse_weight_data("S00.100kg")
        assert sample is not None
        assert sample.grams == 100.0


class TestFindLastMatchPosition:
    """Tests for the find_last_match_position function."""
    
    def test_find_position_single_match(self):
        """Test finding position after single match."""
        data = "S 00.072kgd"
        pos = find_last_match_position(data)
        # Should be at position after 'kg' and 'd'
        assert pos == len(data)
        
    def test_find_position_multiple_matches(self):
        """Test finding position after multiple matches."""
        data = "S 00.072kgdU 06.250kgf"
        pos = find_last_match_position(data)
        assert pos == len(data)
        
    def test_find_position_no_match(self):
        """Test finding position when no matches."""
        data = "garbage"
        pos = find_last_match_position(data)
        assert pos == 0
        
    def test_find_position_with_trailing_data(self):
        """Test finding position with trailing unparsed data."""
        data = "S 00.072kgdS 00.0"
        pos = find_last_match_position(data)
        # Should be after first complete match
        assert pos == 11  # "S 00.072kgd" is 11 chars


class TestAutoDetectSerialPort:
    """Tests for auto_detect_serial_port function."""
    
    @patch('app.scale_driver.Path')
    @patch('app.scale_driver.serial.Serial')
    def test_auto_detect_finds_first_available(self, mock_serial, mock_path):
        """Test auto-detection finds first available port."""
        # ttyUSB0 doesn't exist, ttyUSB1 does
        mock_path.return_value.exists.side_effect = [False, True]
        mock_serial.return_value.__enter__ = Mock()
        mock_serial.return_value.__exit__ = Mock()
        
        result = auto_detect_serial_port()
        
        assert result == "/dev/ttyUSB1"
        
    @patch('app.scale_driver.Path')
    def test_auto_detect_returns_none_when_no_ports(self, mock_path):
        """Test auto-detection returns None when no ports exist."""
        mock_path.return_value.exists.return_value = False
        
        result = auto_detect_serial_port()
        
        assert result is None
        
    @patch('app.scale_driver.Path')
    @patch('app.scale_driver.serial.Serial')
    def test_auto_detect_skips_failed_ports(self, mock_serial, mock_path):
        """Test auto-detection skips ports that fail to open."""
        import serial
        mock_path.return_value.exists.return_value = True
        # First port fails, second succeeds
        mock_serial.side_effect = [
            serial.SerialException("Port in use"),
            MagicMock()
        ]
        
        result = auto_detect_serial_port()
        
        assert result == "/dev/ttyUSB1"


class TestScaleDriverIntegration:
    """Integration tests for ScaleDriver with mocked serial."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = Mock()
        settings.SCALE_PORT = "/dev/ttyUSB0"
        settings.SCALE_BAUDRATE = 9600
        settings.SCALE_READ_INTERVAL_MS = 10
        return settings
    
    def test_driver_initialization(self, mock_settings):
        """Test driver can be initialized."""
        from app.scale_driver import ScaleDriver
        
        driver = ScaleDriver(mock_settings)
        
        assert driver.get_latest() is None
        assert driver._running is False



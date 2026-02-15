"""Tests for the Weight Service API endpoints."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import WeightSample, WeightResponse, HealthResponse, TareResponse
from app.api import router
from app.deps import get_scale_driver


@pytest.fixture
def mock_driver():
    """Create a mock ScaleDriver."""
    driver = Mock()
    driver.get_latest.return_value = None
    return driver


@pytest.fixture
def app(mock_driver):
    """Create a test app with mocked dependencies."""
    # Create a fresh app without the lifespan that starts real ScaleDriver
    test_app = FastAPI()
    test_app.include_router(router)
    
    # Override the dependency
    test_app.dependency_overrides[get_scale_driver] = lambda: mock_driver
    
    return test_app


@pytest.fixture
def client(app):
    """Create a test client."""
    with TestClient(app) as client:
        yield client


class TestReadEndpoint:
    """Tests for POST /read endpoint."""
    
    def test_read_returns_weight_response(self, client, mock_driver):
        """Test successful weight reading."""
        timestamp = datetime(2025, 12, 4, 21, 36, 15, 123456, tzinfo=timezone.utc)
        mock_driver.get_latest.return_value = WeightSample(
            grams=123.4,
            timestamp=timestamp,
            status="S"
        )
        
        response = client.post("/read", json={})
        
        assert response.status_code == 200
        data = response.json()
        assert data["grams"] == 123.4
        assert "timestamp" in data
        
    def test_read_returns_503_when_no_data(self, client, mock_driver):
        """Test 503 response when no weight data available."""
        mock_driver.get_latest.return_value = None
        
        response = client.post("/read", json={})
        
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "No weight data available yet"
        
    def test_read_returns_zero_grams(self, client, mock_driver):
        """Test reading returns zero grams correctly."""
        timestamp = datetime.now(timezone.utc)
        mock_driver.get_latest.return_value = WeightSample(
            grams=0.0,
            timestamp=timestamp,
            status="S"
        )
        
        response = client.post("/read", json={})
        
        assert response.status_code == 200
        data = response.json()
        assert data["grams"] == 0.0
        
    def test_read_accepts_empty_body(self, client, mock_driver):
        """Test endpoint accepts empty request body."""
        timestamp = datetime.now(timezone.utc)
        mock_driver.get_latest.return_value = WeightSample(
            grams=100.0,
            timestamp=timestamp
        )
        
        # Empty body
        response = client.post("/read", json={})
        assert response.status_code == 200
        
    def test_read_content_type_json(self, client, mock_driver):
        """Test response has correct content type."""
        timestamp = datetime.now(timezone.utc)
        mock_driver.get_latest.return_value = WeightSample(
            grams=100.0,
            timestamp=timestamp
        )
        
        response = client.post("/read", json={})
        
        assert response.headers["content-type"] == "application/json"


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""
    
    def test_health_returns_ok(self, client, mock_driver):
        """Test health endpoint returns ok status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        
    def test_health_has_reading_false_when_no_data(self, client, mock_driver):
        """Test has_reading is False when no data available."""
        mock_driver.get_latest.return_value = None
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["has_reading"] is False
        
    def test_health_has_reading_true_when_data_available(self, client, mock_driver):
        """Test has_reading is True when data is available."""
        timestamp = datetime.now(timezone.utc)
        mock_driver.get_latest.return_value = WeightSample(
            grams=100.0,
            timestamp=timestamp
        )
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["has_reading"] is True


class TestTareEndpoint:
    """Tests for POST /tare endpoint."""
    
    def test_tare_returns_stub_response(self, client, mock_driver):
        """Test tare endpoint returns stub response."""
        response = client.post("/tare")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not implemented" in data["message"].lower()


class TestWeightResponseFormat:
    """Tests for weight response format matching Brain's WeightReading model."""
    
    def test_response_matches_brain_model(self, client, mock_driver):
        """Test response format matches Brain's expected WeightReading model."""
        timestamp = datetime(2025, 12, 4, 21, 36, 15, 123456, tzinfo=timezone.utc)
        mock_driver.get_latest.return_value = WeightSample(
            grams=123.4,
            timestamp=timestamp
        )
        
        response = client.post("/read", json={})
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields exist
        assert "grams" in data
        assert "timestamp" in data
        
        # Verify grams is a float >= 0
        assert isinstance(data["grams"], (int, float))
        assert data["grams"] >= 0.0
        
        # Verify timestamp is ISO-8601 format
        # The timestamp should be parseable as datetime
        assert isinstance(data["timestamp"], str)
        parsed_timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        assert parsed_timestamp is not None

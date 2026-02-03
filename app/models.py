"""Pydantic models for the Weight Service API."""

from pydantic import BaseModel, Field
from datetime import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class WeightSample:
    """Internal representation of a weight reading from the scale."""
    grams: float
    timestamp: datetime
    status: Optional[str] = None  # 'S' for stable, 'U' for unstable


class WeightResponse(BaseModel):
    """Response model for the /read endpoint.
    
    This matches the Brain's WeightReading Pydantic model exactly.
    """
    grams: float = Field(ge=0.0, description="Weight in grams, must be >= 0")
    timestamp: datetime = Field(description="ISO-8601 UTC timestamp of the reading")


class HealthResponse(BaseModel):
    """Response model for the /health endpoint."""
    status: str = "ok"
    has_reading: bool = False


class TareResponse(BaseModel):
    """Response model for the /tare endpoint."""
    success: bool
    message: str = ""



"""API routes for the Weight Service."""

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_scale_driver
from app.models import WeightResponse, HealthResponse, TareResponse
from app.scale_driver import ScaleDriver

router = APIRouter()


@router.post("/read", response_model=WeightResponse)
async def read_weight(driver: ScaleDriver = Depends(get_scale_driver)) -> WeightResponse:
    """Read the current weight from the scale.
    
    Returns the latest weight reading in grams with a UTC timestamp.
    The Brain service polls this endpoint frequently (e.g. every 150ms).
    
    Returns:
        WeightResponse with grams and timestamp
        
    Raises:
        HTTPException 503: If no weight data is available yet
    """
    sample = driver.get_latest()
    
    if sample is None:
        raise HTTPException(
            status_code=503,
            detail="No weight data available yet"
        )
    
    return WeightResponse(
        grams=sample.grams,
        timestamp=sample.timestamp
    )


@router.get("/health", response_model=HealthResponse)
async def health_check(driver: ScaleDriver = Depends(get_scale_driver)) -> HealthResponse:
    """Health check endpoint.
    
    Returns:
        HealthResponse with status and has_reading indicator
    """
    sample = driver.get_latest()
    
    return HealthResponse(
        status="ok",
        has_reading=sample is not None
    )


@router.post("/tare", response_model=TareResponse)
async def tare_scale(driver: ScaleDriver = Depends(get_scale_driver)) -> TareResponse:
    """Tare (zero) the scale.
    
    This is a stub implementation. If the hardware supports taring via
    serial commands, this endpoint can be extended to send the appropriate
    command to the scale.
    
    Returns:
        TareResponse with success status and message
    """
    # Stub implementation - actual tare would require sending a command to the scale
    return TareResponse(
        success=False,
        message="Tare not implemented - please tare the scale manually"
    )



"""FastAPI application factory and lifecycle management."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.config import get_settings
from app.deps import set_scale_driver
from app.scale_driver import ScaleDriver


def setup_logging() -> None:
    """Configure application logging."""
    settings = get_settings()
    
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Reduce noise from uvicorn access logs in production
    if settings.APP_ENV == "prod":
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    settings = get_settings()
    logger = logging.getLogger(__name__)
    
    # Startup
    logger.info("Starting Weight Service...")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Serial port: {settings.SCALE_PORT or 'auto-detect'}")
    logger.info(f"Baud rate: {settings.SCALE_BAUDRATE}")
    
    # Create and start the scale driver
    driver = ScaleDriver(settings)
    set_scale_driver(driver)
    await driver.start()
    
    logger.info(f"Weight Service ready on port {settings.WEIGHT_SERVICE_PORT}")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("Shutting down Weight Service...")
    await driver.stop()
    logger.info("Weight Service stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    setup_logging()
    settings = get_settings()
    
    app = FastAPI(
        title="Weight Service",
        description="Microservice for reading weight data from a serial-connected scale",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Include API routes
    app.include_router(router)
    
    return app


# Create the app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.WEIGHT_SERVICE_PORT,
        reload=settings.APP_ENV == "dev"
    )



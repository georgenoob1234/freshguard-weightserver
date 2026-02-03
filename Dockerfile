# ============================================================================
# Weight Service Dockerfile
# Multi-stage build for minimal production image
# ============================================================================

# -----------------------------------------------------------------------------
# Build stage: Install dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# -----------------------------------------------------------------------------
# Final stage: Runtime image
# -----------------------------------------------------------------------------
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Service configuration defaults
ENV SERVICE_PORT=8100 \
    APP_ENV=prod \
    WEIGHT_SERVICE_PORT=8100 \
    LOG_LEVEL=INFO

WORKDIR /app

# Create non-root user for security
RUN useradd -ms /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Ensure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code
COPY --chown=appuser:appuser app/ ./app/

# Switch to non-root user
USER appuser

# Expose the service port (documentation)
EXPOSE ${SERVICE_PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${WEIGHT_SERVICE_PORT}/health')" || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]


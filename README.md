Will be deprecated.

# Weight Service

A FastAPI microservice for reading weight data from a serial-connected scale. Part of the FruitStack computer vision system.

## Features

- **Real-time weight reading** via `/read` endpoint
- **Health monitoring** via `/health` endpoint
- **Tare support** via `/tare` endpoint (stub implementation)
- Auto-detection of USB serial devices (`/dev/ttyUSB0-10`)
- Configurable via environment variables

## API Endpoints

| Method | Endpoint  | Description                          |
|--------|-----------|--------------------------------------|
| POST   | `/read`   | Get current weight in grams          |
| GET    | `/health` | Health check with reading status     |
| POST   | `/tare`   | Tare/zero the scale (stub)           |

## Configuration

Environment variables (all optional with sensible defaults):

| Variable                | Default    | Description                           |
|-------------------------|------------|---------------------------------------|
| `WEIGHT_SERVICE_PORT`   | `8100`     | HTTP server port                      |
| `APP_ENV`               | `dev`      | Environment (`dev` or `prod`)         |
| `SCALE_PORT`            | auto       | Serial port (e.g., `/dev/ttyUSB0`)    |
| `SCALE_BAUDRATE`        | `9600`     | Serial baud rate                      |
| `SCALE_READ_INTERVAL_MS`| `10`       | Polling interval in milliseconds      |
| `LOG_LEVEL`             | `INFO`     | Logging level                         |

## Local Development

### Prerequisites

- Python 3.10+
- A USB serial scale (or mock for testing)

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload

# Or use the convenience script
./uvicorn.sh
```

### Running Tests

```bash
pytest
```

---

## Docker

### Building the Image

```bash
docker build -t weight-service:latest .
```

### Running the Container

Basic run (no serial device access):

```bash
docker run --rm -p 8100:8100 weight-service:latest
```

With serial device access (for real scale hardware):

```bash
docker run --rm -p 8100:8100 \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  -e SCALE_PORT=/dev/ttyUSB0 \
  weight-service:latest
```

With full configuration:

```bash
docker run --rm -p 8100:8100 \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  -e WEIGHT_SERVICE_PORT=8100 \
  -e APP_ENV=prod \
  -e SCALE_PORT=/dev/ttyUSB0 \
  -e SCALE_BAUDRATE=9600 \
  -e LOG_LEVEL=INFO \
  weight-service:latest
```

### Using Docker Compose

```bash
# Start the service
docker compose up -d

# View logs
docker compose logs -f

# Stop the service
docker compose down
```

To enable serial device access, uncomment the `devices` section in `docker-compose.yml`.

### Health Check

The container includes a built-in health check. You can also verify manually:

```bash
curl http://localhost:8100/health
```

Expected response:
```json
{"status": "ok", "has_reading": true}
```

### Environment Variables for Docker

| Variable              | Default | Description                              |
|-----------------------|---------|------------------------------------------|
| `SERVICE_PORT`        | `8100`  | Container port (for documentation)       |
| `WEIGHT_SERVICE_PORT` | `8100`  | Application listening port               |
| `APP_ENV`             | `prod`  | Set to `prod` in container               |
| `SCALE_PORT`          | auto    | Serial device path inside container      |
| `SCALE_BAUDRATE`      | `9600`  | Serial communication speed               |
| `LOG_LEVEL`           | `INFO`  | Logging verbosity                        |

---

## Integration

This service is designed to be polled by the Brain service at high frequency (e.g., every 150ms). The `/read` endpoint returns:

```json
{
  "grams": 150.5,
  "timestamp": "2024-01-15T10:30:00.123456Z"
}
```

If no weight data is available yet, it returns HTTP 503.


# ── KiteFuel x402-provider — production Dockerfile ────────────────────────────
# Standalone FastAPI service that handles x402 payment-required flows.
# Runs on port 9000; all secrets supplied by Railway env vars at runtime.

FROM python:3.12-slim

# System-level dependencies (curl for health checks)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY . .

EXPOSE 9000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:9000/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "2"]

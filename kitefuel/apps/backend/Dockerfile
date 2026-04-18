# ── KiteFuel backend — production Dockerfile ──────────────────────────────────
# Base: slim Python 3.12 image (smaller attack surface than full image)
# Startup order:  alembic upgrade head  →  uvicorn main:app
# All secrets are supplied at runtime by Railway env vars; nothing is hardcoded.

FROM python:3.12-slim

# System-level dependencies for psycopg2 / web3 native extensions
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer-cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Runtime port
EXPOSE 8000

# Health check (Railway / load balancers call /health before routing traffic)
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run migrations then start the server.
# Using shell form so && works; Railway injects DATABASE_URL via env.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2"]

# ============================================================
# Stage 1: builder — install dependencies
# ============================================================
# Pinned: 2026-03-23
FROM python:3.12-slim@sha256:0bbd3d5f3abb2024c1b92ce69e8bdfefa17c248999827c34e2ed52ba0772da1b AS builder

WORKDIR /app

# Install build-time dependencies for compiling C extensions (psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies into an isolated prefix so we can copy them cleanly
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy application source
COPY . .

# ============================================================
# Stage 2: production — minimal runtime image
# ============================================================
# Pinned: 2026-03-23
FROM python:3.12-slim@sha256:0bbd3d5f3abb2024c1b92ce69e8bdfefa17c248999827c34e2ed52ba0772da1b AS production

WORKDIR /app

# Install only the runtime shared library (libpq5), not the dev headers
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group for running the application
RUN groupadd --system --gid 1001 appgroup \
    && useradd --system --uid 1001 --gid appgroup --no-create-home appuser

# Copy installed Python packages from the builder stage
COPY --from=builder /install /usr/local

# Copy application source from the builder stage
COPY --from=builder /app /app

# Set production environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8000

# Ensure the appuser owns the application directory
RUN chown -R appuser:appgroup /app

# Healthcheck — calls the /health endpoint; requires curl (installed above)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Run as non-root
USER appuser

# Production server: 4 workers, no --reload, bind to all interfaces
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*", \
     "--access-log"]

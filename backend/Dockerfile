# ============================================================
# Stage 1: builder — install dependencies
# ============================================================
# Pinned: 2026-03-23
FROM python:3.12-slim@sha256:0bbd3d5f3abb2024c1b92ce69e8bdfefa17c248999827c34e2ed52ba0772da1b AS builder

WORKDIR /app

# Refresh base packages and install build-time dependencies for compiling C extensions.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
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

# Refresh base packages in the runtime image.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
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

# Ensure start.sh is executable
RUN chmod +x /app/start.sh

# Ensure the appuser owns the application directory
RUN chown -R appuser:appgroup /app

# Healthcheck — calls the /health endpoint using the Python stdlib
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read()" || exit 1

EXPOSE 8000

# Run as non-root
USER appuser

# Production server with migration retry logic
CMD ["bash", "start.sh"]

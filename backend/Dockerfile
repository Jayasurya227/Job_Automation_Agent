# ==============================================================================
# Autonomous AI Job Application Agent - Backend Dockerfile
# Production-Hardened Multi-Tenant Container (Python 3.11 + Playwright Chromium)
# ==============================================================================

FROM python:3.11-slim-bookworm AS production

# Security & Optimization Environment Variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=8000 \
    HOST=0.0.0.0

# Install runtime system packages (curl for healthchecks, ca-certificates, tzdata)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set up dedicated non-root application user and directories
RUN groupadd -r -g 1001 appgroup && \
    useradd -r -u 1001 -g appgroup -d /app -s /bin/bash appuser && \
    mkdir -p /app/data/users /app/output /ms-playwright && \
    chown -R appuser:appgroup /app /ms-playwright

WORKDIR /app

# Layer 1: Copy and install Python dependencies (leveraging Docker layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Layer 2: Install Playwright Chromium and required headless OS libraries
RUN playwright install --with-deps chromium && \
    chown -R appuser:appgroup /ms-playwright

# Layer 3: Copy backend application source code and entrypoint
COPY . /app/
RUN chmod +x /app/docker-entrypoint.sh && \
    chown -R appuser:appgroup /app

# Switch to least-privileged non-root user
USER appuser

# Expose internal FastAPI service port
EXPOSE 8000

# Declare persistent volumes for SQLite DB, user vaults, and generated outputs
VOLUME ["/app/data", "/app/output"]

# Automated Docker Healthcheck against FastAPI /api/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Production Entrypoint & Command
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

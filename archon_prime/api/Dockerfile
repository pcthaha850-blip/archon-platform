# ARCHON PRIME API - Production Container
# Multi-stage build for minimal attack surface

# ============================================================
# Stage 1: Builder
# ============================================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# ============================================================
# Stage 2: Production Runtime
# ============================================================
FROM python:3.11-slim as runtime

# Security: Run as non-root user
RUN groupadd -r archon && useradd -r -g archon archon

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=archon:archon . .

# Environment defaults (override in compose/k8s)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    HOST=0.0.0.0 \
    PORT=8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

# Expose port
EXPOSE ${PORT}

# Switch to non-root user
USER archon

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "archon_prime.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--loop", "uvloop", "--http", "httptools"]

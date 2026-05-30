# =============================================================================
# COBOL Moderniser — Autonomous COBOL to Python Migration Pipeline
# =============================================================================
# This Dockerfile builds a containerised version of the 5-agent COBOL
# Moderniser pipeline.  It supports two execution modes:
#
#   1. Offline mode (default):  --no-ai  skips the Anthropic API call
#   2. AI mode:                 requires ANTHROPIC_API_KEY environment variable
#
# Usage:
#   docker build -t cobol-moderniser .
#   docker run --rm -v $(pwd)/sample_cobol:/app/sample_cobol \
#              -v $(pwd)/output:/app/output cobol-moderniser --no-ai
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1 — Builder
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# Install build dependencies (if any packages need compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy and install Python dependencies into a virtual environment
# Using a venv allows easy copying to the final stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2 — Production
# -----------------------------------------------------------------------------
FROM python:3.11-slim

LABEL maintainer="Kannan Swamy"
LABEL version="0.1.0"
LABEL description="COBOL Moderniser -- Autonomous COBOL to Python migration"

# Security: create non-root user with fixed UID 1000
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appgroup . .

# Ensure output directories exist and are writable by appuser
RUN mkdir -p /app/output /app/agents /app/tests/generated && \
    chown -R appuser:appgroup /app/output /app/agents /app/tests/generated

# Switch to non-root user
USER appuser

# Optional environment variable for Anthropic API (AI mode)
# Set this at runtime with  -e ANTHROPIC_API_KEY=...  when not using --no-ai
ENV ANTHROPIC_API_KEY=""

# ENTRYPOINT is the pipeline runner
ENTRYPOINT ["python", "demo/run_pipeline.py"]

# Default to offline mode so the image runs without any external credentials
CMD ["--no-ai"]

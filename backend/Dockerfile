# ── Stage 1: Build ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./



# Install production dependencies only (no dev dependencies)
RUN uv sync --frozen --no-dev --no-install-project && \
uv cache clean

# Download the Xgboost without gpu support
RUN uv pip install xgboost --force-reinstall --no-deps --index-url https://pypi.org/simple

# Copy the rest of the application code
COPY app/ app/
COPY main.py ./

# Install the project itself
RUN uv sync --frozen --no-dev && \
    uv cache clean

# ── Stage 2: Production ─────────────────────────────────────────────────────
FROM python:3.12-slim AS production

# Install runtime dependencies for native extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgomp1 \
        libblas3 \
        liblapack3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user early
RUN useradd -m -u 1000 appuser

# Create the persistent data directory for the SQLite auth DB and grant
# the app user write access. Without this, Docker mounts the named volume
# at /data as a root-owned directory and the non-root appuser cannot
# create the database file (sqlite3.OperationalError: unable to open database file).
RUN mkdir -p /data && chown appuser:appuser /data

WORKDIR /app

# Copy the virtual environment and application from the builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/app /app/app
COPY --from=builder --chown=appuser:appuser /app/main.py /app/main.py

# Switch to non-root user
USER appuser

# Make the venv available on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Set default environment variables
# Default environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose Cloud Run default port
EXPOSE 8080

# Use exec in a shell so uvicorn dynamically binds to $PORT and handles OS signals
CMD ["sh", "-c", "exec uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]

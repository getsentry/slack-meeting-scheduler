# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies to a virtual environment
RUN uv sync --frozen --no-dev

# Copy source code
COPY src/ ./src/
COPY main.py ./

# Set proper permissions for non-root user (UID 65532)
RUN chown -R 65532:65532 /app

# Runtime stage - distroless
FROM gcr.io/distroless/python3-debian12:nonroot

WORKDIR /app

# Copy Python dependencies from builder with proper ownership
COPY --from=builder --chown=65532:65532 /app/.venv/lib/python3.11/site-packages /app/site-packages

# Copy application code with proper ownership
COPY --from=builder --chown=65532:65532 /app/src /app/src
COPY --from=builder --chown=65532:65532 /app/main.py /app/

# Set Python path to include site-packages
ENV PYTHONPATH=/app/site-packages:/app

# Explicitly set non-root user (distroless nonroot uses UID 65532)
USER 65532:65532

# Expose port (Cloud Run will override this)
EXPOSE 8080

# Run the application
ENTRYPOINT ["python3", "-m", "src.main"]

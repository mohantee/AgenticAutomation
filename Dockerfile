# Production Dockerfile for AgenticAutomation Web Dashboard & API
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    ENV=prod \
    STORAGE_BACKEND=s3

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging configuration and install dependencies + gunicorn
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "gunicorn>=22.0.0" .

# Copy application source code and web UI assets
COPY src/ ./src/
COPY ui/ ./ui/

# Health check for ECS
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose port for ECS Fargate / ALB
EXPOSE 5000

# Run with Gunicorn WSGI production server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "agenticautomation.api.server:create_app()"]

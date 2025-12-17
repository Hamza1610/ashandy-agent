# Production Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies
# libpq-dev is needed for building psycopg2 (if using the binary version this might be optional but good for stability)
# curl for healthchecks
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Create a non-root user for security (optional but recommended for production)
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Run application
# Host 0.0.0.0 is crucial for Docker networking
# --proxy-headers tells Uvicorn to trust headers (important behind Nginx/AWS LB)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

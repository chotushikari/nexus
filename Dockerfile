# Dockerfile for NEXUS API (Google Cloud Run deployment)
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements & install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir fastapi uvicorn pydantic google-adk google-cloud-firestore google-genai

# Copy application source code
COPY apps/api/nexus_api ./nexus_api
COPY data ./data

# Expose port (Cloud Run sets PORT env variable, defaults to 8000)
ENV PORT=8000
EXPOSE 8000

# Start production server
CMD exec uvicorn nexus_api.main:app --host 0.0.0.0 --port $PORT --workers 2

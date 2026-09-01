FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"

COPY nexus_api ./nexus_api

ENV PORT=8080
CMD ["sh", "-c", "uvicorn nexus_api.main:app --host 0.0.0.0 --port ${PORT}"]


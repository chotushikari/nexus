$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "apps/api"
uvicorn nexus_api.application:app --host 127.0.0.1 --port 8000 --reload


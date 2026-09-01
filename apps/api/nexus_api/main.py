# Entry‑point for uvicorn:  uvicorn nexus_api.main:app
# All routes and routers live in application.py – we just re‑export the app here
# so that the standard invocation works out of the box.
from nexus_api.application import app  # noqa: F401  (re-export)

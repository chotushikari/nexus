from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexus_api.core.config import settings
from nexus_api.core.logging import configure_logging, get_logger
from nexus_api.routers import agents, approvals, demo, enterprise, events, missions, security
from nexus_api.services.capabilities import capabilities
from nexus_api.services.storage import store

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log the persistence choice and rehydrate durable state.

    Rehydration is what makes §21/§22 true: a mission created before a restart is
    readable again, so the browser is a client and not the execution engine.
    """
    configure_logging(settings.log_level)
    if not store.agents:
        store.seed_agents_from_roster()
    counts = store.rehydrate()
    logger.info(
        "app.startup",
        environment=settings.environment,
        enterpriseId=settings.enterprise_id,
        enterpriseName=settings.enterprise_name,
        storeBackend=store.backend,
        storeNote=store.backend_note,
        geminiModel=settings.gemini_model,
        plannerEnabled=settings.enable_gemini_planner,
        adkEnabled=settings.enable_adk,
        rehydrated=counts,
    )
    yield
    logger.info("app.shutdown", storeBackend=store.backend)


def create_app() -> FastAPI:
    app = FastAPI(
        title="NEXUS API",
        version="0.2.0",
        description="Backend for governed autonomous enterprise agents.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # Browser origins allowed to call the API. Defaults to any origin; pin
    # CORS_ORIGINS in production to the deployed frontend origins. The app
    # uses no cookies, so wildcard and credentials are never combined.
    configured = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    origins = configured or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials="*" not in origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, object]:
        """Health plus an honest capability report.

        `capabilities.gemini` / `.adk` / `.firestore` are `true` only when a real
        call to that service has succeeded in this process. `details` explains
        why a capability is false (SDK missing, no credentials, disabled, or the
        exact error from the last attempt).
        """
        report = capabilities.report()
        return {
            "status": "ok",
            "service": "nexus-api",
            "environment": settings.environment,
            "enterpriseId": settings.enterprise_id,
            "enterpriseName": settings.enterprise_name,
            "storeBackend": store.backend,
            "storeWriteError": store.write_error,
            "capabilities": report.model_dump(mode="json"),
        }

    app.include_router(demo.router)
    app.include_router(enterprise.router)
    app.include_router(missions.router)
    app.include_router(approvals.router)
    app.include_router(agents.router)
    app.include_router(security.router)
    app.include_router(events.router)
    return app


app = create_app()

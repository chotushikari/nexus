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

    # Allow the Next.js dev server to call the API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
            "http://localhost:3002",
        ],
        allow_credentials=True,
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

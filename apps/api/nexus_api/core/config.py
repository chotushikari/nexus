"""Central configuration for the NEXUS backend.

Every value that describes the demo narrative (enterprise name, vendor under
evaluation) lives here so that no module hard-codes a brand. Every value that
describes a Google dependency (model id, project, database) lives here so that a
capability can be switched off without editing code.
"""

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Gemini model ids
# ---------------------------------------------------------------------------
# NOTE: model ids MUST be confirmed against the hackathon's approved model list
# before submission. This sandbox has no network egress, so the id below could
# not be verified against the live `models.list` endpoint at build time.
# `gemini-3.5-flash` was previously hard-coded in this file and in
# `.env.local.example`; it is not a model id we could verify, so the default has
# been changed to `gemini-2.0-flash`, which is a real, generally-available
# Flash-class model. Known Flash-class candidates, newest first:
#   gemini-2.5-flash, gemini-2.0-flash, gemini-2.0-flash-lite
# Override with the GEMINI_MODEL environment variable once confirmed.
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_GEMINI_MODEL_LITE = "gemini-2.0-flash-lite"


class StoreBackend(str, Enum):
    """Which persistence backend `DualStore` should prefer."""

    auto = "auto"
    memory = "memory"
    file = "file"
    firestore = "firestore"


class Settings(BaseSettings):
    environment: str = "local"

    # ── Enterprise identity (single source of truth for the demo narrative) ──
    enterprise_id: str = "meridian-industrial"
    enterprise_name: str = "Meridian Industrial"
    default_vendor_id: str = "kestrel-components"
    default_vendor_name: str = "Kestrel Components"

    # ── Google Cloud ────────────────────────────────────────────────────────
    google_cloud_project: str = "nexus-enterprise-demo"
    google_cloud_location: str = "us-central1"
    firestore_database: str = "nexus-db"

    # ── Gemini ──────────────────────────────────────────────────────────────
    gemini_model: str = DEFAULT_GEMINI_MODEL
    gemini_model_lite: str = DEFAULT_GEMINI_MODEL_LITE
    # Read from GEMINI_API_KEY or GOOGLE_API_KEY. Never commit a real value.
    gemini_api_key: str | None = None
    google_api_key: str | None = None
    google_genai_use_vertexai: bool = False

    # ── Capability switches ─────────────────────────────────────────────────
    enable_gemini_planner: bool = True
    enable_adk: bool = True

    # ── Planner bounds ──────────────────────────────────────────────────────
    planner_timeout_seconds: float = 25.0
    planner_max_attempts: int = 2  # one call + at most one retry
    planner_max_tasks: int = 12

    # ── Agent / mission bounds (circuit breakers) ───────────────────────────
    demo_mode: bool = True
    agent_max_iterations: int = 10
    agent_max_tool_calls: int = 5
    agent_max_attempts: int = 3
    mission_max_runtime_minutes: int = 15
    mission_max_tool_calls: int = 50
    mission_max_tasks: int = 20
    adk_timeout_seconds: float = 20.0

    # ── Persistence ─────────────────────────────────────────────────────────
    store_backend: StoreBackend = StoreBackend.auto
    nexus_state_dir: str = ".nexus-state"

    # ── Logging ─────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # Comma-separated browser origins allowed to call the API. Empty means
    # allow any origin (no cookies are used, so this is safe for the demo).
    cors_origins: str = ""

    # Minimum wall-clock seconds a task runs. Synthetic tools return in
    # milliseconds, which makes a mission blink past the office visual;
    # pacing throttles the REAL execution so it stays observable.
    task_pacing_seconds: float = 2.5

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_gemini_api_key(self) -> str | None:
        """Gemini key from either supported env var, or None when unset."""
        return self.gemini_api_key or self.google_api_key or None

    @property
    def mission_timeout_seconds(self) -> float:
        return self.mission_max_runtime_minutes * 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

"""Shared pytest configuration and fixtures for the NEXUS backend suite.

--------------------------------------------------------------------------------
SANDBOX EXECUTION NOTE (read this before trusting any claim about this suite)
--------------------------------------------------------------------------------
These tests were authored in an environment with **no network egress and no pip
index**, where `pytest`, `pydantic`, `fastapi` and `httpx` were all
`ModuleNotFoundError`. They therefore could **not** be executed as written in
that sandbox. They are ordinary pytest tests intended to run on a machine with
`apps/api`'s dev dependencies installed:

    python -m pip install -e "apps/api[dev]"
    python -m pytest                      # from the repo root

For a dependency-free check of what *can* be verified without pydantic — pytest
collection configuration, duplicate/stale test files, a syntax pass over every
source and test file, dataset consistency for the tree the API resolves, and the
prompt-injection fixture against the real pattern list — run:

    python tests/manual_verify.py

`manual_verify.py` uses only the standard library and states plainly what it
cannot check (all executed backend behaviour).
--------------------------------------------------------------------------------

Design rules for this suite:

* No test may reach the network. The Gemini planner is exercised by patching
  `planner._build_client` / `planner._generate`, never by calling out.
* Every test that mutates global singletons (`store`, `capabilities`, `settings`)
  gets them reset by the autouse `reset_runtime` fixture.
* Durable state is redirected to a per-test `tmp_path`, so running the suite
  never touches the developer's real `.nexus-state/`.
* Anything that genuinely needs credentials is marked `@pytest.mark.integration`
  and skips cleanly when they are absent.
"""

from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"

# `nexus_api` lives under apps/api. pytest.ini also sets `pythonpath`, but keep
# this so a bare `pytest tests/test_x.py` from any cwd still imports cleanly.
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def _importable(module: str) -> bool:
    try:
        importlib.import_module(module)
    except ImportError:
        return False
    return True


# Resolved once, at collection time, so skip reasons are accurate.
HAVE_PYDANTIC = _importable("pydantic") and _importable("pydantic_settings")
HAVE_FASTAPI = _importable("fastapi")
HAVE_HTTPX = _importable("httpx")
HAVE_GENAI = _importable("google.genai")
HAVE_ADK = _importable("google.adk.agents")
HAVE_FIRESTORE = _importable("google.cloud.firestore")


def requires_backend() -> None:
    """Call at module import time in tests that import `nexus_api`.

    `nexus_api.schemas.domain` is pydantic-based and `nexus_api.core.config` is
    pydantic-settings-based, so the whole backend is unimportable without them.
    """
    pytest.importorskip("pydantic", reason="pydantic is required to import nexus_api")
    pytest.importorskip(
        "pydantic_settings", reason="pydantic-settings is required by nexus_api.core.config"
    )


def requires_api() -> None:
    """Call at module import time in tests that use `fastapi.testclient`."""
    requires_backend()
    pytest.importorskip("fastapi", reason="fastapi is required for the HTTP contract tests")
    pytest.importorskip("httpx", reason="httpx is required by fastapi.testclient")


def credentials_present() -> bool:
    """True when a real Gemini credential is configured for this process."""
    if not HAVE_PYDANTIC:
        return False
    from nexus_api.core.config import settings

    return bool(settings.resolved_gemini_api_key) or settings.google_genai_use_vertexai


# ── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_runtime(tmp_path, monkeypatch):
    """Isolate every test from every other test.

    * the global `store` is pointed at a per-test durable directory and cleared;
    * the capability registry is reset, so one test's mocked Gemini success
      cannot make a later `/api/health` assertion pass for the wrong reason;
    * the ADK agent cache is cleared;
    * Gemini credentials are forced absent unless a test opts back in, so the
      default posture under test is the honest no-credentials posture.
    """
    if not HAVE_PYDANTIC:
        yield
        return

    from nexus_api.core.config import StoreBackend, settings
    from nexus_api.services import adk_runtime
    from nexus_api.services.capabilities import capabilities
    from nexus_api.services.storage import store

    monkeypatch.setattr(settings, "gemini_api_key", None, raising=False)
    monkeypatch.setattr(settings, "google_api_key", None, raising=False)
    monkeypatch.setattr(settings, "google_genai_use_vertexai", False, raising=False)

    state_dir = tmp_path / "nexus-state"
    store.configure(StoreBackend.file, state_dir)
    store.reset()
    capabilities.reset()
    adk_runtime.clear_agent_cache()

    yield

    store.reset()
    capabilities.reset()
    adk_runtime.clear_agent_cache()
    # Restore an in-memory backend so a later module that forgets to configure
    # the store does not silently inherit a deleted tmp directory.
    store.configure(StoreBackend.memory, None)


@pytest.fixture()
def seeded_store(reset_runtime):
    """The global store with the real 20-agent roster loaded."""
    from nexus_api.services.storage import store

    store.seed_agents_from_roster()
    return store


@pytest.fixture()
def roster(seeded_store):
    """`dict[agentId, AgentCard]` straight from `data/agents/roster.json`."""
    return dict(seeded_store.agents)


@pytest.fixture()
def client(seeded_store):
    """FastAPI `TestClient` **without** lifespan.

    Use for pure request/response contract checks. Background mission tasks do
    not survive here, because each request runs on its own portal loop — use
    `live_client` when the mission must keep running between requests.
    """
    requires_api()
    from fastapi.testclient import TestClient

    from nexus_api.application import create_app

    return TestClient(create_app())


@pytest.fixture()
def live_client(seeded_store):
    """FastAPI `TestClient` used as a context manager, so lifespan runs and one
    event loop stays alive across requests — which is what a background mission
    task needs in order to make progress between polls."""
    requires_api()
    from fastapi.testclient import TestClient

    from nexus_api.application import create_app

    with TestClient(create_app()) as instance:
        yield instance


@pytest.fixture()
def stub_execution(monkeypatch, reset_runtime):
    """Neutralise the background mission runner.

    For tests that only care about the *response* to `POST /api/missions`, this
    keeps the request cheap and — more importantly — stops a background task
    being abandoned when a non-context-manager `TestClient` tears its portal loop
    down, which otherwise produces "Task was destroyed but it is pending" noise.
    """
    if not HAVE_PYDANTIC:
        pytest.skip("pydantic is required")
    from nexus_api.services.mission import mission_service

    async def noop(mission_id: str) -> None:
        return None

    monkeypatch.setattr(mission_service, "_plan_and_run", noop)
    return mission_service


# ── helpers ─────────────────────────────────────────────────────────────────

# Statuses a mission passes *through*. Polling stops once it leaves this set.
NON_TERMINAL = {"created", "planning", "running"}


def poll_mission(client, mission_id: str, timeout: float = 60.0, interval: float = 0.05):
    """Poll `GET /api/missions/{id}` until the mission settles.

    Missions run in a background asyncio task on the `TestClient` portal's event
    loop. That loop is *not* the loop an `async def` test runs on, so
    `mission_service.wait_for_mission` cannot be awaited across the boundary —
    poll over HTTP instead, which is also what a real client does.

    Returns the last mission payload. Raises `AssertionError` on timeout so the
    failure names the status the mission was stuck in.
    """
    deadline = time.monotonic() + timeout
    payload: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/missions/{mission_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] not in NON_TERMINAL:
            return payload
        time.sleep(interval)
    raise AssertionError(
        f"mission {mission_id} did not settle within {timeout}s "
        f"(last status: {payload.get('status')!r})"
    )

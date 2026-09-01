"""Honest degradation: the system must never claim a capability it lacks.

SANDBOX NOTE: authored where pytest/pydantic/fastapi were unavailable, so this
file was NOT executed at authoring time. See tests/conftest.py.

The `reset_runtime` fixture forces Gemini credentials absent, so the default
posture under test is the no-credentials posture. What this file proves:

  * with no credentials the mission plan reports
    `planSource == "deterministic_fallback"` and `planModel is None`;
  * `/api/health` reports `gemini = adk = firestore = false`, and `details`
    explains *why* each one is false rather than staying silent;
  * a capability flag can only become `true` after a real call succeeded in this
    process — installing an SDK is not enough, and neither is configuring a key;
  * agent reasoning produced without ADK is labelled as deterministic in the
    payload the UI reads, not passed off as model output;
  * the tests that would need real credentials are marked `integration` and skip
    cleanly.
"""

from __future__ import annotations

import pytest

from conftest import credentials_present, poll_mission, requires_backend

requires_backend()

from nexus_api.core.config import settings  # noqa: E402
from nexus_api.schemas.domain import PlanSource, StartMissionRequest  # noqa: E402
from nexus_api.services import adk_runtime, planner as planner_module  # noqa: E402
from nexus_api.services.capabilities import capabilities  # noqa: E402
from nexus_api.services.mission import mission_service  # noqa: E402
from nexus_api.services.storage import store  # noqa: E402


# ── the capability registry itself ──────────────────────────────────────────


def test_a_fresh_registry_claims_nothing():
    capabilities.reset()

    report = capabilities.report()

    assert report.gemini is False
    assert report.adk is False
    assert report.firestore is False


def test_recorded_failure_does_not_set_a_capability_true():
    """The subtle bug this guards: a `record_failure` that flips the flag, or a
    report that infers `true` from "the SDK is installed"."""
    capabilities.reset()
    capabilities.record_failure("gemini", "no GEMINI_API_KEY configured")
    capabilities.record_failure("adk", "google-adk not importable")
    capabilities.record_failure("firestore", "no credentials")

    report = capabilities.report()

    assert report.gemini is False
    assert report.adk is False
    assert report.firestore is False
    assert "no GEMINI_API_KEY configured" in report.details["gemini_last"]


def test_only_a_recorded_success_sets_a_capability_true():
    capabilities.reset()
    capabilities.record_success("gemini", "planned a mission")

    report = capabilities.report()

    assert report.gemini is True
    assert report.adk is False
    assert report.firestore is False
    assert capabilities.exercised("gemini") is True


def test_sdk_installed_is_reported_separately_from_exercised():
    """`gemini_sdk_installed` and `gemini` must be distinct facts, so "the
    library is present" is never confused with "the call worked"."""
    capabilities.reset()
    installed, _ = planner_module.gemini_sdk_status()

    report = capabilities.report()

    assert report.details["gemini_sdk_installed"] == str(installed).lower()
    assert report.gemini is False, "an installed SDK must not imply an exercised capability"


def test_report_explains_why_gemini_is_false(monkeypatch):
    capabilities.reset()
    monkeypatch.setattr(settings, "gemini_api_key", None, raising=False)
    monkeypatch.setattr(settings, "google_api_key", None, raising=False)
    monkeypatch.setattr(settings, "google_genai_use_vertexai", False, raising=False)

    details = capabilities.report().details

    assert details["gemini_configured"] == "no_credentials"
    assert details["gemini_model"] == settings.gemini_model
    assert details["planner_enabled"] == str(settings.enable_gemini_planner).lower()
    assert "gemini_sdk" in details


def test_report_survives_a_registry_reset_without_lying_about_the_store():
    """`store_backend` and the data-dir facts are recomputed on every call, so a
    reset cannot leave `/api/health` reporting a stale backend."""
    capabilities.reset()

    details = capabilities.report().details

    assert details["store_backend"] == store.backend
    assert "data_dir" in details
    assert details["data_dir_complete"] in {"true", "false"}


def test_health_report_data_dir_is_complete():
    """A partial or shadowed `data/` tree silently empties the department list and
    hides vendor records, so `/api/health` must be able to say so."""
    details = capabilities.report().details

    assert details["data_dir_complete"] == "true", (
        f"resolved data dir is incomplete: missing {details['data_dir_missing']} "
        f"under {details['data_dir']}"
    )


# ── the mission-level honesty claim ─────────────────────────────────────────


async def test_no_credentials_means_deterministic_fallback(seeded_store):
    mission = await mission_service.start_mission(StartMissionRequest())
    settled = await mission_service.wait_for_mission(mission.id, 60.0)

    assert settled.planSource == PlanSource.deterministic_fallback
    assert settled.planSource.value == "deterministic_fallback"
    assert settled.planModel is None
    assert settled.planNotes and "Gemini was not used" in settled.planNotes
    assert settled.degraded["planner"] == settled.planNotes
    assert capabilities.exercised("gemini") is False


async def test_reasoning_without_adk_is_labelled_deterministic(seeded_store):
    installed, _ = adk_runtime.adk_sdk_status()
    if installed:
        pytest.skip("google-adk is installed; covered by the integration-marked test")

    mission = await mission_service.start_mission(StartMissionRequest())
    settled = await mission_service.wait_for_mission(mission.id, 60.0)

    reasoned = [task for task in settled.tasks if task.reasoning]
    assert reasoned, "no task produced any reasoning at all"
    for task in reasoned:
        assert task.reasoningRuntime == adk_runtime.FALLBACK_RUNTIME
        assert task.reasoning.startswith("[deterministic summary"), (
            "deterministic text must be labelled where the UI can see it"
        )
    assert "adk" in settled.degraded
    assert capabilities.exercised("adk") is False


def test_adk_fallback_never_pretends_to_be_a_model(seeded_store):
    """Unit-level check on the fallback text itself."""
    agent = store.get_agent("david-brooks")
    reasoning = adk_runtime._fallback(
        agent, "Assess risk", {"risk_calculator": {"riskScore": 75}}, "google-adk not importable", None
    )

    assert reasoning.degraded is True
    assert reasoning.runtime == adk_runtime.FALLBACK_RUNTIME
    assert reasoning.runtime != adk_runtime.ADK_RUNTIME
    assert "no model reasoning" in reasoning.text
    assert reasoning.error == "google-adk not importable"


def test_agent_instruction_comes_from_the_real_system_prompt(seeded_store):
    """Tier-1 agents have a system prompt on disk; the ADK layer must use it
    rather than a generated stub, or the "real ADK agents" claim is hollow."""
    for agent_id in ("alex-morgan", "elena-rao", "marcus-chen", "david-brooks", "sarah-patel"):
        agent = store.get_agent(agent_id)
        instruction, source = adk_runtime.load_instruction(agent)

        assert agent.systemPromptPath, f"{agent_id} has no systemPromptPath"
        assert source == agent.systemPromptPath, (
            f"{agent_id} fell back to a card-derived instruction; the prompt file at "
            f"{adk_runtime.PROJECT_ROOT / agent.systemPromptPath} was not readable"
        )
        assert len(instruction) > 100


# ── /api/health ─────────────────────────────────────────────────────────────


def test_health_reports_no_google_capability_without_credentials(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["enterpriseId"] == settings.enterprise_id
    assert body["enterpriseName"] == settings.enterprise_name

    reported = body["capabilities"]
    assert reported["gemini"] is False
    assert reported["adk"] is False
    assert reported["firestore"] is False
    # Every false flag must come with an explanation.
    details = reported["details"]
    assert details["gemini_configured"] == "no_credentials"
    assert "gemini_sdk" in details
    assert "adk_sdk" in details
    assert details["store_backend"] == body["storeBackend"]


def test_health_never_reports_firestore_without_a_client(client):
    body = client.get("/api/health").json()

    assert body["capabilities"]["firestore"] is False
    assert body["storeBackend"] in {"memory", "file"}, (
        "no Firestore credentials are configured, so the backend must not be firestore"
    )


def test_enterprise_summary_reports_the_same_capabilities_as_health(client):
    health = client.get("/api/health").json()["capabilities"]
    enterprise = client.get("/api/enterprise").json()

    assert enterprise["capabilities"]["gemini"] == health["gemini"]
    assert enterprise["capabilities"]["adk"] == health["adk"]
    assert enterprise["capabilities"]["firestore"] == health["firestore"]
    assert enterprise["id"] == settings.enterprise_id
    assert enterprise["name"] == settings.enterprise_name
    assert enterprise["defaultVendorId"] == settings.default_vendor_id
    assert enterprise["storeBackend"] == health["details"]["store_backend"]


def test_enterprise_summary_is_not_empty(client):
    """A shadowed `data/` tree previously reported zero departments while the
    endpoint still returned 200."""
    body = client.get("/api/enterprise").json()

    assert len(body["departments"]) >= 12
    assert body["counts"]["departments"] == len(body["departments"])
    assert body["counts"]["agentsTotal"] == 20
    assert body["counts"]["agentsOnline"] >= 1, (
        "every roster card reported offline — check AgentStatus normalisation"
    )
    assert body["counts"]["agentsOnline"] <= body["counts"]["agentsTotal"]
    assert all(department["agentCount"] >= 0 for department in body["departments"])


def test_health_gemini_flag_flips_only_after_a_successful_plan(live_client):
    """The end-to-end honesty check across a mission: a run with no credentials
    must leave `/api/health` reporting `gemini: false`."""
    assert live_client.get("/api/health").json()["capabilities"]["gemini"] is False

    response = live_client.post("/api/missions", json={})
    assert response.status_code == 202
    settled = poll_mission(live_client, response.json()["id"], timeout=60.0)

    assert settled["planSource"] == "deterministic_fallback"
    assert settled["planModel"] is None
    assert live_client.get("/api/health").json()["capabilities"]["gemini"] is False


# ── genuinely credentialled paths ───────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.skipif(
    not credentials_present(), reason="no Gemini credentials configured (GEMINI_API_KEY)"
)
async def test_real_gemini_plan_is_labelled_gemini(seeded_store, roster):
    """Only runs with real credentials. Hits the network by design."""
    from nexus_api.services.planner import mission_planner

    result = await mission_planner.plan(
        "mission-integration",
        "Verify the vendor, clear compliance, assess financial risk, onboard.",
        settings.default_vendor_id,
        roster,
    )

    assert result.source == PlanSource.gemini
    assert result.model == settings.gemini_model
    assert result.tasks
    assert capabilities.exercised("gemini") is True


@pytest.mark.integration
@pytest.mark.skipif(
    not credentials_present(), reason="no Gemini credentials configured (GEMINI_API_KEY)"
)
async def test_real_adk_run_is_labelled_google_adk(seeded_store):
    """Only runs with real credentials and google-adk installed."""
    pytest.importorskip("google.adk.agents", reason="google-adk is not installed")

    agent = store.get_agent("elena-rao")
    reasoning = await adk_runtime.run_agent_reasoning(
        agent=agent,
        objective="Verify the vendor.",
        task_title="Verify the vendor",
        tool_results={"company_search": {"id": settings.default_vendor_id}},
        session_id="mission-integration:task-research",
    )

    assert reasoning.runtime == adk_runtime.ADK_RUNTIME
    assert reasoning.degraded is False
    assert capabilities.exercised("adk") is True


@pytest.mark.integration
@pytest.mark.skipif(
    not credentials_present(), reason="no Gemini credentials configured (GEMINI_API_KEY)"
)
def test_configured_gemini_model_id_is_plausible():
    """The model id is a submission risk: it could not be verified against the
    live `models.list` endpoint in an offline sandbox."""
    assert settings.gemini_model
    assert settings.gemini_model.startswith("gemini-")

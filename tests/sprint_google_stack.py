"""Google SDK integration checks.

SANDBOX NOTE: authored where none of the Google SDKs (nor pytest) were
installable, so this file was NOT executed at authoring time.

This file previously imported `google.adk.agents`, `google.genai` and
`google.cloud.firestore` at module scope. With those SDKs absent that is a
**collection error**, which takes the whole run down rather than skipping one
file — so the imports are now guarded with `pytest.importorskip` and everything
that needs a real SDK is marked `integration`.

It also asserted the model id `gemini-3.5-flash`, which was never verifiable
against any published model list. The id now comes from configuration
(`settings.gemini_model`) so there is a single place to correct it.
"""

from __future__ import annotations

import pytest

from conftest import HAVE_ADK, HAVE_FIRESTORE, HAVE_GENAI, requires_backend

requires_backend()

from nexus_api.core.config import settings  # noqa: E402
from nexus_api.services import adk_runtime, planner  # noqa: E402

adk_only = pytest.mark.skipif(not HAVE_ADK, reason="google-adk is not installed")
genai_only = pytest.mark.skipif(not HAVE_GENAI, reason="google-genai is not installed")
firestore_only = pytest.mark.skipif(
    not HAVE_FIRESTORE, reason="google-cloud-firestore is not installed"
)


# ── these run everywhere: they assert honest *reporting* of SDK presence ─────


def test_sdk_status_helpers_never_raise():
    """`/api/health` calls these on every request, so they must be safe with or
    without the SDKs present."""
    gemini_installed, gemini_note = planner.gemini_sdk_status()
    adk_installed, adk_note = adk_runtime.adk_sdk_status()

    assert isinstance(gemini_installed, bool)
    assert isinstance(adk_installed, bool)
    assert gemini_note and adk_note
    assert gemini_installed is HAVE_GENAI
    assert adk_installed is HAVE_ADK


def test_descriptor_fallback_is_returned_when_the_adk_sdk_is_absent():
    if HAVE_ADK:
        pytest.skip("google-adk is installed; the real-Agent path is asserted below")

    built = adk_runtime.build_adk_descriptor(
        agent_id="alex-morgan",
        name="alex_morgan",
        model=settings.gemini_model,
        instruction="Create a mission plan and delegate to specialists.",
    )

    assert isinstance(built, adk_runtime.AdkAgentDescriptor)
    assert built.runtime == "fallback-descriptor"
    assert built.name == "alex_morgan"
    assert built.model == settings.gemini_model


def test_adk_agent_names_are_valid_identifiers(seeded_store):
    """ADK rejects agent names that are not Python identifiers, and roster ids use
    hyphens — so the sanitiser must be exercised even without the SDK."""
    for agent in seeded_store.list_agents():
        name = adk_runtime._adk_agent_name(agent.id)
        assert name.isidentifier(), f"{agent.id} -> {name}"


def test_adk_enabled_requires_both_the_switch_and_the_sdk(monkeypatch):
    monkeypatch.setattr(settings, "enable_adk", False, raising=False)
    assert adk_runtime.adk_enabled() is False

    monkeypatch.setattr(settings, "enable_adk", True, raising=False)
    assert adk_runtime.adk_enabled() is HAVE_ADK


def test_configured_model_id_is_a_single_source_of_truth():
    """`gemini-3.5-flash` used to be hard-coded in tests, config and
    `.env.local.example`. It is not a model id that could be verified offline."""
    assert settings.gemini_model
    assert settings.gemini_model != "gemini-3.5-flash", (
        "gemini-3.5-flash is not a verifiable model id; set GEMINI_MODEL instead"
    )
    assert settings.gemini_model.startswith("gemini-")


# ── these need the SDKs actually installed ──────────────────────────────────


@pytest.mark.integration
@adk_only
def test_google_adk_agent_can_be_constructed():
    from google.adk.agents import Agent

    built = adk_runtime.build_adk_descriptor(
        agent_id="alex-morgan",
        name="alex_morgan",
        model=settings.gemini_model,
        instruction="Create a mission plan and delegate to specialists.",
    )

    assert isinstance(built, Agent)
    assert built.name == "alex_morgan"
    assert built.model == settings.gemini_model


@pytest.mark.integration
@adk_only
def test_roster_cards_build_real_adk_agents(seeded_store):
    from google.adk.agents import Agent

    for agent_id in ("alex-morgan", "elena-rao", "david-brooks"):
        built, source = adk_runtime.build_agent_for_card(seeded_store.get_agent(agent_id))
        assert isinstance(built, Agent)
        assert source.endswith("system_prompt.md")


@pytest.mark.integration
@genai_only
def test_gemini_client_class_is_importable():
    from google import genai

    assert genai.Client is not None


@pytest.mark.integration
@firestore_only
def test_firestore_client_class_is_importable():
    from google.cloud import firestore

    assert firestore.Client is not None

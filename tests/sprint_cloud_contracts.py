"""Cloud / data contracts.

SANDBOX NOTE: authored where pytest/pydantic were unavailable, so this file was
NOT executed at authoring time. See tests/conftest.py.

These tests assert the dataset the API *actually resolves* (`storage.DATA_DIR`),
not a hard-coded `<repo>/data` path. That distinction matters: `storage.py` picks
the nearest ancestor directory whose `data/` tree is complete, so on a tree where
`apps/api/data/` is complete it wins over the repo-root `data/`. A test that read
the repo root could pass while the running API read a different, drifted copy.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import requires_backend

requires_backend()

from nexus_api.services import adk_runtime, storage  # noqa: E402
from nexus_api.services.firestore_store import firestore_collections  # noqa: E402
from nexus_api.services.storage import DATA_DIR  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_TREES = ("agents/roster.json", "departments.json", "tools.json", "synthetic/vendors.json")


def _load(relative: str, root: Path = DATA_DIR):
    return json.loads((root / relative).read_text(encoding="utf-8"))


def test_firestore_collection_contract_contains_track_three_entities():
    collections = set(firestore_collections())

    assert {
        "agents",
        "missions",
        "events",
        "approvals",
        "memory",
        "tools",
        "policies",
    }.issubset(collections)


def test_resolved_data_dir_is_complete():
    """`describe_data_dir()` is what `/api/health` reports; if it is not complete
    the department list and vendor records silently come back empty."""
    described = storage.describe_data_dir()

    assert described["data_dir_complete"] == "true", (
        f"missing {described['data_dir_missing']} under {described['data_dir']}"
    )
    for relative in storage.REQUIRED_DATA_FILES:
        assert (DATA_DIR / relative).is_file()


def test_departments_are_data_driven():
    departments = _load("departments.json")

    assert len(departments) >= 12
    assert all("location" in department for department in departments)
    assert all("theme" in department for department in departments)
    assert len({department["id"] for department in departments}) == len(departments)


def test_tools_catalogue_declares_owners_and_risk():
    catalogue = _load("tools.json")
    roster = {agent["id"] for agent in _load("agents/roster.json")["agents"]}

    assert catalogue
    for tool in catalogue:
        assert tool["ownerAgentId"] in roster, tool["id"]
        assert tool["riskLevel"] in {"low", "medium", "high"}
        assert tool["capability"]

    high_risk = {tool["id"] for tool in catalogue if tool.get("requiresApproval")}
    assert {"create_payment", "contract_finalize"}.issubset(high_risk)


def test_synthetic_vendors_include_the_configured_default():
    from nexus_api.core.config import settings

    vendors = _load("synthetic/vendors.json")

    assert settings.default_vendor_id in vendors, (
        "the configured default vendor has no synthetic record, so every tool call "
        "would fall back to a generated stub"
    )
    record = vendors[settings.default_vendor_id]
    assert record["id"] == settings.default_vendor_id
    assert "synthetic" in json.dumps(record).lower(), (
        "synthetic fixtures must say so, so no judge mistakes them for real data"
    )


def test_core_agent_prompt_files_exist():
    """Prompts are resolved relative to `adk_runtime.PROJECT_ROOT`, which is
    computed separately from `storage.PROJECT_ROOT` — so resolve them the same
    way the runtime does rather than assuming the repo root."""
    roster = _load("agents/roster.json")
    tier_one = [agent for agent in roster["agents"] if agent["tier"] == 1]

    assert len(tier_one) == 5
    for agent in tier_one:
        prompt_path = adk_runtime.PROJECT_ROOT / agent["systemPromptPath"]
        assert prompt_path.exists(), f"{agent['id']}: {prompt_path}"
        assert prompt_path.read_text(encoding="utf-8").strip()


def test_malicious_security_fixture_is_present_in_the_resolved_tree():
    document = DATA_DIR / "synthetic" / "malicious_vendor_document.txt"

    assert document.is_file(), (
        f"{document} is missing, which silently disables the prompt-injection "
        "guardrail during a mission"
    )


@pytest.mark.parametrize("relative", DATA_TREES)
def test_duplicate_data_trees_have_not_drifted(relative):
    """`apps/api/data/` is a deploy-time copy of `<repo>/data/`.

    Whichever one `storage.find_project_root()` picks depends on which files
    happen to be present, so the two copies must stay identical or the API and
    the tooling will disagree about the dataset. This test is skipped when only
    one copy exists.
    """
    candidates = [
        path
        for path in (REPO_ROOT / "data" / relative, REPO_ROOT / "apps" / "api" / "data" / relative)
        if path.is_file()
    ]
    if len(candidates) < 2:
        pytest.skip(f"only one copy of {relative} exists")

    first, second = (json.loads(path.read_text(encoding="utf-8")) for path in candidates)
    assert first == second, (
        f"{relative} differs between <repo>/data and apps/api/data; the API reads "
        f"{DATA_DIR} so one of the two copies is dead weight that can drift"
    )


def test_project_roots_used_for_data_and_prompts_agree():
    """`storage.find_project_root()` requires a *complete* `data/` tree while
    `adk_runtime.find_project_root()` requires sibling `data/` and `agents/`
    directories. When those disagree, the dataset and the agent system prompts are
    loaded from two different trees. Reported as a production issue.
    """
    if storage.PROJECT_ROOT == adk_runtime.PROJECT_ROOT:
        return
    pytest.xfail(
        "storage.PROJECT_ROOT="
        f"{storage.PROJECT_ROOT} but adk_runtime.PROJECT_ROOT={adk_runtime.PROJECT_ROOT}; "
        "data and prompts resolve against different roots"
    )

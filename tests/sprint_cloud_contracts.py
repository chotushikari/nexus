import json
from pathlib import Path

from nexus_api.services.firestore_store import firestore_collections


ROOT = Path(__file__).resolve().parents[1]


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


def test_departments_are_data_driven():
    departments = json.loads((ROOT / "data" / "departments.json").read_text(encoding="utf-8"))

    assert len(departments) >= 12
    assert all("location" in department for department in departments)
    assert all("theme" in department for department in departments)


def test_core_agent_prompt_files_exist():
    roster = json.loads((ROOT / "data" / "agents" / "roster.json").read_text(encoding="utf-8"))
    tier_one = [agent for agent in roster["agents"] if agent["tier"] == 1]

    assert len(tier_one) == 5
    for agent in tier_one:
        prompt_path = ROOT / agent["systemPromptPath"]
        assert prompt_path.exists(), agent["systemPromptPath"]
        assert prompt_path.read_text(encoding="utf-8").strip()


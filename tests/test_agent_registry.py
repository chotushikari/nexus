"""Agent roster contract.

SANDBOX NOTE: authored where pytest/pydantic/fastapi were unavailable, so this
file was NOT executed at authoring time. See tests/conftest.py.

The roster in `data/agents/roster.json` is the source of truth for who exists,
what they own, and what they are allowed to touch. These tests pin the parts the
policy engine and the planner depend on, so a roster edit cannot silently break
least-privilege or produce an unexecutable plan.
"""

from __future__ import annotations

import pytest

from conftest import requires_backend

requires_backend()

from nexus_api.services.planner import IMPLEMENTED_TOOLS  # noqa: E402
from nexus_api.services.policy import POLICY_RULES, TOOL_CAPABILITIES  # noqa: E402

CORE_AGENTS = ("alex-morgan", "elena-rao", "marcus-chen", "david-brooks", "sarah-patel")


def test_roster_seeds_twenty_agents_across_three_tiers(seeded_store):
    agents = seeded_store.list_agents()

    assert len(agents) == 20
    assert {agent.tier.value for agent in agents} == {1, 2, 3}
    assert len([agent for agent in agents if agent.tier.value == 1]) == 5


def test_agent_ids_are_unique(seeded_store):
    agents = seeded_store.list_agents()
    assert len({agent.id for agent in agents}) == len(agents)


@pytest.mark.parametrize("agent_id", CORE_AGENTS)
def test_core_agent_has_an_identity_and_a_system_prompt(agent_id, seeded_store):
    agent = seeded_store.get_agent(agent_id)

    assert agent.identity.principal
    assert agent.identity.scopes
    assert agent.tier.value == 1
    assert agent.systemPromptPath, f"{agent_id} has no system prompt"
    assert agent.departmentId


def test_finance_agent_owns_the_payment_tool_and_the_finance_scopes(seeded_store):
    agent = seeded_store.get_agent("david-brooks")

    assert agent.codename == "The Ledger"
    assert "financial.read" in agent.identity.scopes
    assert "create_payment" in agent.tools
    # ...but does not hold the write capability outright: that is what makes the
    # approval gate meaningful rather than decorative.
    assert "payment.write" not in agent.identity.scopes


def test_every_tool_owned_by_a_tier_one_agent_has_a_capability_mapping(seeded_store):
    """An unmapped tool falls through to `capability = tool`, which usually means
    a silent default-deny at runtime instead of a clear configuration error."""
    unmapped = []
    for agent_id in CORE_AGENTS:
        for tool in seeded_store.get_agent(agent_id).tools:
            if tool not in TOOL_CAPABILITIES:
                unmapped.append((agent_id, tool))

    assert unmapped == []


def test_implemented_tools_are_all_owned_by_someone(seeded_store):
    """A tool the runtime can dispatch but nobody owns is unreachable code."""
    owned = {tool for agent in seeded_store.list_agents() for tool in agent.tools}
    orphans = sorted(IMPLEMENTED_TOOLS - owned)

    assert orphans == []


def test_every_policy_rule_names_a_real_agent(seeded_store):
    unknown = sorted(agent_id for agent_id in POLICY_RULES if agent_id not in seeded_store.agents)

    assert unknown == []


def test_agents_endpoint_returns_the_full_roster(client):
    response = client.get("/api/agents")

    assert response.status_code == 200
    agents = response.json()
    assert len(agents) == 20
    assert {agent["tier"] for agent in agents} == {1, 2, 3}
    assert {agent["id"] for agent in agents} >= set(CORE_AGENTS)


def test_single_agent_endpoint_exposes_identity_and_tools(client):
    agent = client.get("/api/agents/david-brooks").json()

    assert agent["codename"] == "The Ledger"
    assert "financial.read" in agent["identity"]["scopes"]
    assert "create_payment" in agent["tools"]


def test_capabilities_endpoint_matches_the_card(client):
    agent = client.get("/api/agents/marcus-chen").json()
    capabilities = client.get("/api/agents/marcus-chen/capabilities").json()

    assert capabilities == agent["capabilities"]
    assert "sanctions.check" in capabilities


def test_unknown_agent_is_a_404(client):
    assert client.get("/api/agents/not-a-real-agent").status_code == 404
    assert client.get("/api/agents/not-a-real-agent/capabilities").status_code == 404


def test_seed_demo_reports_the_roster_size(client):
    response = client.post("/api/demo/seed")

    assert response.status_code == 200
    assert response.json() == {"status": "seeded", "agents": 20}

def test_seed_demo_loads_twenty_agent_cards(client):
    response = client.post("/api/demo/seed")

    assert response.status_code == 200
    assert response.json()["agents"] == 20

    agents = client.get("/api/agents").json()
    assert len(agents) == 20
    assert {agent["tier"] for agent in agents} == {1, 2, 3}


def test_core_agent_has_identity_and_tools(client):
    client.post("/api/demo/seed")

    response = client.get("/api/agents/david-brooks")

    assert response.status_code == 200
    agent = response.json()
    assert agent["codename"] == "The Ledger"
    assert "financial.read" in agent["identity"]["scopes"]
    assert "create_payment" in agent["tools"]


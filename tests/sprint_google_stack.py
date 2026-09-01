from google.adk.agents import Agent
from google import genai
from google.cloud import firestore

from nexus_api.services.adk_runtime import build_adk_descriptor


def test_google_adk_agent_can_be_constructed():
    agent = build_adk_descriptor(
        agent_id="alex-morgan",
        name="alex_morgan",
        model="gemini-3.5-flash",
        instruction="Create a mission plan and delegate to specialists.",
    )

    assert isinstance(agent, Agent)
    assert agent.name == "alex_morgan"
    assert agent.model == "gemini-3.5-flash"


def test_gemini_and_firestore_clients_are_importable():
    assert genai.Client is not None
    assert firestore.Client is not None


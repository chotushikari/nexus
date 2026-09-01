from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from nexus_api.schemas.domain import AgentCard
from nexus_api.services.policy import ApprovalRequiredError, PolicyViolationError
from nexus_api.services.storage import store
from nexus_api.services.tools import execute_tool

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentCard])
async def list_agents() -> list[AgentCard]:
    if not store.agents:
        store.seed_agents_from_roster()
    return store.list_agents()


@router.get("/{agent_id}", response_model=AgentCard)
async def get_agent(agent_id: str) -> AgentCard:
    try:
        if not store.agents:
            store.seed_agents_from_roster()
        return store.get_agent(agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent not found") from exc


@router.get("/{agent_id}/capabilities", response_model=list[str])
async def get_capabilities(agent_id: str) -> list[str]:
    try:
        if not store.agents:
            store.seed_agents_from_roster()
        return store.get_agent(agent_id).capabilities
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="agent not found") from exc


class InvokePayload(BaseModel):
    tool: str
    payload: dict[str, Any] = {}
    missionId: str = "adhoc"
    approved_approval_id: str | None = None


@router.post("/{agent_id}/invoke", response_model=dict)
async def invoke_agent(agent_id: str, body: InvokePayload) -> dict:
    """Ad-hoc single tool call.

    Routed through `execute_tool`, so the same least-privilege policy gate and
    approval flow apply here as inside a mission. There is no bypass path.
    """
    if not store.agents:
        store.seed_agents_from_roster()
    if agent_id not in store.agents:
        raise HTTPException(status_code=404, detail="agent not found")
    try:
        return execute_tool(
            mission_id=body.missionId,
            agent_id=agent_id,
            tool=body.tool,
            payload=body.payload,
            approved_approval_id=body.approved_approval_id,
        )
    except PolicyViolationError as exc:
        raise HTTPException(status_code=403, detail=f"policy denied: {exc}") from exc
    except ApprovalRequiredError as exc:
        raise HTTPException(
            status_code=409,
            detail={"reason": str(exc), "approvalId": exc.approvalId},
        ) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

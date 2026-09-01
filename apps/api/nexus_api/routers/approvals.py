from fastapi import APIRouter, HTTPException

from nexus_api.schemas.domain import Approval, ApprovalDecisionRequest, ApprovalStatus, Mission
from nexus_api.services.mission import mission_service
from nexus_api.services.storage import store

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("", response_model=list[Approval])
async def list_approvals(status: ApprovalStatus | None = None) -> list[Approval]:
    return store.list_approvals(status)


@router.get("/{approval_id}", response_model=Approval)
async def get_approval(approval_id: str) -> Approval:
    try:
        return store.get_approval(approval_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="approval not found") from exc


@router.post("/{approval_id}/decision", response_model=Mission)
async def decide_approval(approval_id: str, request: ApprovalDecisionRequest) -> Mission:
    """Record the operator decision and resume the parked branch in the
    background. Returns the mission as it stands right after the decision."""
    try:
        return mission_service.decide_approval(approval_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="approval not found") from exc

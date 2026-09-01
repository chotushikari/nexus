from fastapi import APIRouter

from nexus_api.schemas.domain import DepartmentCard, EnterpriseCounts, EnterpriseSummary
from nexus_api.services.enterprise import aggregate_counts, enterprise_summary, load_departments

router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])


@router.get("", response_model=EnterpriseSummary)
async def get_enterprise() -> EnterpriseSummary:
    """Enterprise identity, department layout, and live aggregate counts.

    The frontend header reads this instead of hard-coding a company name.
    """
    return enterprise_summary()


@router.get("/departments", response_model=list[DepartmentCard])
async def get_departments() -> list[DepartmentCard]:
    return load_departments()


@router.get("/counts", response_model=EnterpriseCounts)
async def get_counts() -> EnterpriseCounts:
    return aggregate_counts()

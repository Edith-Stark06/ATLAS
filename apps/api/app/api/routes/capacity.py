from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.capacity import (
    AgentPlanRead,
    CapacityPlanRead,
    CapacityRequest,
    ConstraintRead,
)
from app.services import capacity_service

router = APIRouter(prefix="/capacity", tags=["capacity"])


@router.post("/plan", response_model=CapacityPlanRead)
async def plan_capacity(
    request: CapacityRequest, db: AsyncSession = Depends(get_db)
) -> CapacityPlanRead:
    """Project what growing a job would demand of governance.

    A read-only projection despite being a POST — the request carries the
    operator's own figures (reviewer availability, handling time), which do
    not belong in a query string, and nothing is persisted.

    The useful part of the answer is the binding constraint. Adding agents
    does not help when what runs out first is human review, and a plan that
    reports only a headline number hides exactly that.
    """
    try:
        plan = await capacity_service.plan_capacity(
            db,
            request.capability,
            multiplier=request.multiplier,
            days=request.days,
            reviewer_days_available=request.reviewer_days_available,
            review_minutes=request.review_minutes,
        )
    except capacity_service.CohortNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    binding = plan.binding

    return CapacityPlanRead(
        capability=plan.capability,
        window_days=plan.window_days,
        multiplier=plan.multiplier,
        current_daily=plan.current_daily,
        target_daily=plan.target_daily,
        constraints=[
            ConstraintRead(
                key=c.key,
                label=c.label,
                available=c.available,
                required=c.required,
                unit=c.unit,
                detail=c.detail,
                headroom=c.headroom,
                satisfied=c.satisfied,
                shortfall=c.shortfall,
            )
            for c in plan.constraints
        ],
        binding_constraint=binding.key if binding else None,
        feasible=plan.feasible,
        unallocated_daily=plan.unallocated_daily,
        agents=[
            AgentPlanRead(
                agent_id=a.agent_id,
                agent_name=a.agent_name,
                action=a.action,
                current_daily=a.current_daily,
                recommended_daily=a.recommended_daily,
                change_pct=a.change_pct,
                reason=a.reason,
            )
            for a in plan.agents
        ],
        assumptions=plan.assumptions,
        out_of_scope=plan.out_of_scope,
    )

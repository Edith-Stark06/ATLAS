from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pagination import set_total_count
from app.core.database import get_db
from app.models import (
    ActivityItem,
    Agent,
    Decision,
    Policy,
    SimulationRun,
)
from app.schemas.governance import (
    ActivityItemRead,
    AgentRead,
    DecisionRead,
    PolicyRead,
    SimulationRunRead,
)

router = APIRouter()

#: Default/max for the estate-wide list endpoints below — comfortably above
#: every real count today (16 seeded agents, a handful of policies), so
#: default behaviour for current data is unchanged. A real bound for
#: whichever of these grows first, not a UX feature yet.
DEFAULT_LIST_LIMIT = 200
MAX_LIST_LIMIT = 1000


# --- Agents -----------------------------------------------------------------


@router.get("/agents", response_model=list[AgentRead], tags=["agents"])
async def list_agents(
    response: Response,
    limit: int = Query(DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[Agent]:
    total = (await db.execute(select(func.count()).select_from(Agent))).scalar_one()
    set_total_count(response, total)

    result = await db.execute(
        select(Agent).order_by(Agent.trust_score.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.get("/agents/{agent_id}", response_model=AgentRead, tags=["agents"])
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


# --- Decisions --------------------------------------------------------------


@router.get("/decisions", response_model=list[DecisionRead], tags=["decisions"])
async def list_decisions(
    response: Response,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[Decision]:
    total = (await db.execute(select(func.count()).select_from(Decision))).scalar_one()
    set_total_count(response, total)

    result = await db.execute(
        select(Decision).order_by(Decision.decided_at.desc()).limit(limit).offset(offset)
    )
    return list(result.unique().scalars().all())


@router.get("/decisions/{decision_id}", response_model=DecisionRead, tags=["decisions"])
async def get_decision(decision_id: str, db: AsyncSession = Depends(get_db)) -> Decision:
    result = await db.execute(select(Decision).where(Decision.id == decision_id))
    decision = result.unique().scalar_one_or_none()
    if decision is None:
        raise HTTPException(status_code=404, detail=f"Decision '{decision_id}' not found")
    return decision


# --- Policies ---------------------------------------------------------------


@router.get("/policies", response_model=list[PolicyRead], tags=["policies"])
async def list_policies(
    response: Response,
    limit: int = Query(DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[Policy]:
    total = (await db.execute(select(func.count()).select_from(Policy))).scalar_one()
    set_total_count(response, total)

    result = await db.execute(
        select(Policy)
        .order_by(Policy.enabled.desc(), Policy.violations_24h.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


# --- Simulations ------------------------------------------------------------


@router.get("/simulations", response_model=list[SimulationRunRead], tags=["simulations"])
async def list_simulations(
    response: Response,
    limit: int = Query(DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[SimulationRun]:
    total = (await db.execute(select(func.count()).select_from(SimulationRun))).scalar_one()
    set_total_count(response, total)

    result = await db.execute(
        select(SimulationRun).order_by(SimulationRun.ran_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.get("/simulations/{simulation_id}", response_model=SimulationRunRead, tags=["simulations"])
async def get_simulation(simulation_id: str, db: AsyncSession = Depends(get_db)) -> SimulationRun:
    run = await db.get(SimulationRun, simulation_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found")
    return run


# --- Activity ---------------------------------------------------------------


@router.get("/activity", response_model=list[ActivityItemRead], tags=["activity"])
async def list_activity(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[ActivityItem]:
    result = await db.execute(select(ActivityItem).order_by(ActivityItem.at.desc()).limit(limit))
    return list(result.scalars().all())

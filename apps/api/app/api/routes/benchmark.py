from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.benchmark import (
    AgentScoreRead,
    BenchmarkRead,
    ChangeAttributionRead,
    CohortRead,
    ContributionRead,
    CriterionRead,
    GapRead,
)
from app.services import benchmark_service

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.get("/cohorts", response_model=list[CohortRead])
async def list_cohorts(db: AsyncSession = Depends(get_db)) -> list[CohortRead]:
    """Capabilities with agents in them — the groups that can be ranked.

    A cohort is a job, not a team. Agents are only comparable when they are
    doing the same work.
    """
    return [
        CohortRead(capability=c.capability, agents=c.agents)
        for c in await benchmark_service.list_cohorts(db)
    ]


@router.get("/cohorts/{capability}", response_model=BenchmarkRead)
async def benchmark_cohort(
    capability: str,
    days: int = Query(
        benchmark_service.DEFAULT_WINDOW_DAYS, ge=1, le=benchmark_service.MAX_WINDOW_DAYS
    ),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkRead:
    """Rank every agent doing this job, best first.

    Scores are absolute rather than normalised within the cohort, so a
    uniformly strong cohort looks strong instead of manufacturing a worst
    member at zero.
    """
    try:
        result = await benchmark_service.benchmark_cohort(db, capability, days=days)
    except benchmark_service.CohortNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    ranking = result.ranking

    return BenchmarkRead(
        capability=ranking.capability or capability,
        window_days=result.window_days,
        weights=ranking.weights,
        scored=[
            AgentScoreRead(
                agent_id=a.agent_id,
                agent_name=a.agent_name,
                capability=a.capability,
                composite=a.composite,
                decisions=a.decisions,
                thin_evidence=a.thin_evidence,
                criteria=[
                    CriterionRead(
                        key=c.key,
                        label=c.label,
                        score=c.score,
                        weight=c.weight,
                        basis=c.basis,
                        contribution=c.contribution,
                    )
                    for c in a.criteria
                ],
            )
            for a in ranking.scored
        ],
        leader_id=ranking.leader.agent_id if ranking.leader else None,
        comparable=ranking.comparable,
        gaps={
            agent_id: [
                GapRead(
                    key=g.key,
                    label=g.label,
                    agent_score=g.agent_score,
                    leader_score=g.leader_score,
                    points=g.points,
                    composite_cost=g.composite_cost,
                )
                for g in gaps
            ]
            for agent_id, gaps in result.gaps.items()
        },
    )


@router.get("/agents/{agent_id}/changes", response_model=ChangeAttributionRead)
async def agent_score_changes(
    agent_id: str,
    days: int = Query(
        benchmark_service.DEFAULT_WINDOW_DAYS, ge=1, le=benchmark_service.MAX_WINDOW_DAYS
    ),
    db: AsyncSession = Depends(get_db),
) -> ChangeAttributionRead:
    """What moved this agent's score, and by how much.

    The decomposition is exact: the base score is a weighted sum, so each
    factor's share is arithmetic rather than estimated, and the parts
    reconcile to the observed change. Anything left over is reported as a
    residual instead of being spread across the factors.
    """
    try:
        result = await benchmark_service.explain_score_change(db, agent_id, days=days)
    except benchmark_service.AgentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ChangeAttributionRead(
        agent_id=agent_id,
        window_days=days,
        before_score=result.before_score,
        after_score=result.after_score,
        delta=result.delta,
        contributions=[
            ContributionRead(
                key=c.key,
                label=c.label,
                before=c.before,
                after=c.after,
                contribution=c.contribution,
                from_value=c.from_value,
                from_weight=c.from_weight,
            )
            for c in result.contributions
        ],
        penalty_delta=result.penalty_delta,
        residual=result.residual,
        residual_share=result.residual_share,
        reconciles=result.reconciles,
    )

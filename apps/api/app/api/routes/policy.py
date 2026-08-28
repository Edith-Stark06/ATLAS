from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import domains
from app.api.deps import RequireAdmin
from app.core.database import get_db
from app.models import Agent, Policy
from app.schemas.policy import (
    ConditionResultRead,
    CreateVersionRequest,
    DomainRead,
    EvaluateRequest,
    EvaluateResponse,
    FieldSpecRead,
    PolicyDetailRead,
    PolicyEvaluationRead,
    PolicyVersionRead,
    RuleVocabularyRead,
    SimulatedDecisionRead,
    SimulateRuleRequest,
    SimulateRuleResponse,
)
from app.services import policy_engine, policy_service
from app.services.policy_engine import (
    Combinator,
    Effect,
    Operator,
    PolicyContext,
    RuleValidationError,
)

router = APIRouter(prefix="/policy", tags=["policy"])


def _summarise(rule_dict: dict | None) -> list[str]:
    """Render a stored rule as readable lines, or explain why it cannot be."""
    if rule_dict is None:
        return ["No active rule version."]
    try:
        rule = policy_engine.parse_rule(rule_dict)
    except RuleValidationError as exc:
        return [f"Rule is not evaluable: {exc}"]

    joiner = " AND " if rule.combinator is Combinator.ALL else " OR "
    scope = ", ".join(rule.applies_to) if rule.applies_to else "all agents"
    return [
        f"IF {joiner.join(c.describe() for c in rule.conditions)}",
        f"THEN {rule.effect.value.replace('_', ' ')}",
        f"Applies to: {scope}",
    ]


def _detail(policy: Policy, versions: list | None = None) -> PolicyDetailRead:
    rule = policy.active_version.rule if policy.active_version else None
    return PolicyDetailRead(
        id=policy.id,
        name=policy.name,
        version=policy.version,
        scope=policy.scope,
        enabled=policy.enabled,
        severity=policy.severity,
        updated_at=policy.updated_at,
        evaluations_24h=policy.evaluations_24h,
        violations_24h=policy.violations_24h,
        rule=rule,
        summary=_summarise(rule),
        versions=[PolicyVersionRead.model_validate(v) for v in (versions or [])],
    )


@router.get("/vocabulary", response_model=RuleVocabularyRead)
async def rule_vocabulary(db: AsyncSession = Depends(get_db)) -> RuleVocabularyRead:
    """The closed set of fields, operators and effects a rule may use.

    Served rather than hard-coded in the client so the authoring UI cannot
    drift from what the engine will actually accept.
    """
    capabilities = list(
        (await db.execute(select(Agent.capability).distinct().order_by(Agent.capability)))
        .scalars()
        .all()
    )

    packs = domains.all_packs()

    return RuleVocabularyRead(
        fields=[
            FieldSpecRead(
                key=key,
                label=spec.label,
                kind=spec.kind.__name__,
                description=spec.description,
                domain=(pack.key if (pack := domains.pack_for_field(key)) else None),
                # A core field applies everywhere; a domain field only where
                # its pack governs. Sent so the picker cannot offer a field
                # that would make the rule unevaluable.
                applies_to=(list(pack.capabilities) if pack else []),
            )
            for key, spec in policy_engine.evaluable_fields().items()
        ],
        operators=[o.value for o in Operator],
        combinators=[c.value for c in Combinator],
        effects=[e.value for e in Effect],
        capabilities=capabilities,
        domains=[
            DomainRead(
                key=pack.key,
                label=pack.label,
                description=pack.description,
                capabilities=list(pack.capabilities),
                fields=sorted(pack.fields),
            )
            for pack in packs
        ],
    )


@router.get("/policies", response_model=list[PolicyDetailRead])
async def list_policies(db: AsyncSession = Depends(get_db)) -> list[PolicyDetailRead]:
    """Every policy with its active rule — enabled first, then by name."""
    result = await db.execute(
        select(Policy)
        .options(selectinload(Policy.active_version))
        .order_by(Policy.enabled.desc(), Policy.name)
    )
    return [_detail(p) for p in result.scalars().all()]


@router.get("/policies/{policy_id}", response_model=PolicyDetailRead)
async def get_policy(policy_id: str, db: AsyncSession = Depends(get_db)) -> PolicyDetailRead:
    result = await db.execute(
        select(Policy).options(selectinload(Policy.active_version)).where(Policy.id == policy_id)
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")

    versions = await policy_service.load_versions(db, policy_id)
    return _detail(policy, versions)


@router.post(
    "/policies/{policy_id}/versions",
    response_model=PolicyVersionRead,
    status_code=201,
    # Authoring a rule changes what governs every future decision.
    dependencies=[RequireAdmin],
)
async def create_policy_version(
    policy_id: str, request: CreateVersionRequest, db: AsyncSession = Depends(get_db)
) -> PolicyVersionRead:
    """Append an immutable version and (by default) activate it.

    Editing a policy never mutates an existing version — a decision recorded
    months ago must still be explainable against the exact rule that produced it.
    """
    try:
        version = await policy_service.create_version(
            db,
            policy_id,
            rule=request.rule,
            version=request.version,
            note=request.note,
            created_by=request.created_by,
            activate=request.activate,
        )
    except RuleValidationError as exc:
        # 422, not 500: the rule is syntactically well-formed JSON but is not
        # a valid rule, which is the client's problem to fix.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if version is None:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")

    return PolicyVersionRead.model_validate(version)


@router.get("/policies/{policy_id}/versions", response_model=list[PolicyVersionRead])
async def list_policy_versions(
    policy_id: str, db: AsyncSession = Depends(get_db)
) -> list[PolicyVersionRead]:
    exists = (
        await db.execute(select(Policy.id).where(Policy.id == policy_id))
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")

    versions = await policy_service.load_versions(db, policy_id)
    return [PolicyVersionRead.model_validate(v) for v in versions]


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(
    request: EvaluateRequest, db: AsyncSession = Depends(get_db)
) -> EvaluateResponse:
    """Run the full active policy set against a hypothetical decision."""
    context = PolicyContext(
        trust_score=request.trust_score,
        risk_score=request.risk_score,
        amount_usd=request.amount_usd,
        authority_level=request.authority_level,
        agent_lifecycle=request.agent_lifecycle,
        capability=request.capability,
        hour_utc=request.hour_utc,
    )
    result = await policy_service.evaluate_context(db, context)

    return EvaluateResponse(
        effect=result.decision.effect,
        outcome=policy_service.EFFECT_TO_OUTCOME[result.decision.effect],
        explanation=result.decision.explanation,
        evaluations=[
            PolicyEvaluationRead(
                policy_id=detail.policy_id,
                policy_name=detail.policy_name,
                version=detail.version,
                matched=detail.evaluation.matched,
                in_scope=detail.evaluation.in_scope,
                effect=detail.evaluation.effect,
                conditions=[
                    ConditionResultRead(
                        description=r.describe(),
                        matched=r.matched,
                        skipped=r.skipped_reason is not None,
                    )
                    for r in detail.evaluation.results
                ],
            )
            for detail in result.details
        ],
        invalid=[f"{pid} ({name})" for pid, name in result.invalid],
    )


@router.post("/simulate", response_model=SimulateRuleResponse)
async def simulate(
    request: SimulateRuleRequest, db: AsyncSession = Depends(get_db)
) -> SimulateRuleResponse:
    """Replay a candidate rule over stored decisions before deploying it."""
    try:
        simulation = await policy_service.simulate_rule(db, request.rule)
    except RuleValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    def _read(s) -> SimulatedDecisionRead:
        return SimulatedDecisionRead(
            decision_id=s.decision_id,
            agent_name=s.agent_name,
            action=s.action,
            recorded_outcome=s.recorded_outcome,
            simulated_outcome=s.simulated_outcome,
            matched=s.matched,
            changed=s.changed,
        )

    return SimulateRuleResponse(
        evaluated=simulation.evaluated,
        matched=simulation.matched,
        would_block=simulation.would_block,
        would_escalate=simulation.would_escalate,
        would_allow=simulation.would_allow,
        changed=[_read(s) for s in simulation.changed],
        sample=[_read(s) for s in simulation.sample],
    )

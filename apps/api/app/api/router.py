from fastapi import APIRouter

from app.api.routes import dashboard, governance, health, ledger, policy, simulation, trust

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(dashboard.router)
# Registered before governance so POST /decisions/execute is matched by its
# literal path rather than reaching governance's /decisions/{decision_id}.
api_router.include_router(ledger.decisions_router)
api_router.include_router(ledger.router)
api_router.include_router(governance.router)
api_router.include_router(policy.router)
api_router.include_router(simulation.router)
api_router.include_router(trust.router)

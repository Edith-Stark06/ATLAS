from fastapi import APIRouter

from app.api.routes import dashboard, governance, health, policy, simulation, trust

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(dashboard.router)
api_router.include_router(governance.router)
api_router.include_router(policy.router)
api_router.include_router(simulation.router)
api_router.include_router(trust.router)

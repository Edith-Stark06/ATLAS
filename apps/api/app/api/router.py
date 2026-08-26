from fastapi import APIRouter

from app.api.deps import RequireOperator, RequireViewer
from app.api.routes import (
    analytics,
    auth,
    benchmark,
    dashboard,
    explain,
    governance,
    health,
    ledger,
    policy,
    simulation,
    trust,
)

api_router = APIRouter()

# Unauthenticated by design. Health is what a load balancer polls before it
# has any credential to present; auth is where credentials are obtained.
# Everything below carries at least RequireViewer, so a router added without a
# dependency stands out as an omission rather than blending in.
api_router.include_router(health.router)
api_router.include_router(auth.router)

# Committing a decision moves money, so this is the one router that needs
# operator rather than viewer. Registered before governance purely for
# readability — POST /decisions/execute and GET /decisions/{id} differ by
# method, so neither can shadow the other.
api_router.include_router(ledger.decisions_router, dependencies=[RequireOperator])

# Reads. Viewer is the floor for anything exposing governance data: trust
# scores, decision rationales and audit payloads are not public information.
# Individual write endpoints inside these routers raise the bar themselves.
api_router.include_router(governance.router, dependencies=[RequireViewer])
api_router.include_router(explain.router, dependencies=[RequireViewer])
api_router.include_router(analytics.router, dependencies=[RequireViewer])
api_router.include_router(benchmark.router, dependencies=[RequireViewer])
api_router.include_router(dashboard.router, dependencies=[RequireViewer])
api_router.include_router(ledger.router, dependencies=[RequireViewer])
api_router.include_router(policy.router, dependencies=[RequireViewer])
api_router.include_router(trust.router, dependencies=[RequireViewer])
api_router.include_router(simulation.router, dependencies=[RequireViewer])

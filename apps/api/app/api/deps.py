"""Request-scoped auth dependencies.

`require(role)` is the only thing routes should need. Anything reachable
without it is unauthenticated by omission, which is why the router keeps that
list short and explicit (see app/main.py).
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import API_KEY_PREFIX
from app.models import Role
from app.services import auth_service
from app.services.auth_service import Actor, AuthenticationError

#: Sent on 401 so a client knows *how* to authenticate, not just that it failed.
_AUTH_CHALLENGE = {"WWW-Authenticate": "Bearer"}


async def current_actor(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Actor:
    """Resolve the caller from an `Authorization: Bearer <credential>` header.

    One header carries both credential types. They are told apart by the API
    key's fixed prefix rather than by trying one and falling back to the
    other — a fallback would double the work on every request and blur which
    credential actually failed.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers=_AUTH_CHALLENGE,
        )

    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credential:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expected an 'Authorization: Bearer <token>' header",
            headers=_AUTH_CHALLENGE,
        )

    try:
        if credential.startswith(API_KEY_PREFIX):
            key = await auth_service.resolve_api_key(db, credential)
            return auth_service.actor_from_api_key(key)
        return await auth_service.actor_from_token(db, credential)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers=_AUTH_CHALLENGE,
        ) from exc


def require(role: Role) -> Callable[..., Awaitable[Actor]]:
    """Dependency factory enforcing a minimum privilege level.

    403, not 404: the caller is authenticated and the resource exists, they
    simply may not do this. Hiding that behind a 404 would make a permissions
    problem look like a bug and send someone debugging the wrong thing.
    """

    async def dependency(actor: Actor = Depends(current_actor)) -> Actor:
        if not actor.can(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires the '{role.value}' role or higher; you have '{actor.role.value}'",
            )
        return actor

    return dependency


#: Convenience aliases, so route signatures read as the permission they need.
RequireViewer = Depends(require(Role.VIEWER))
RequireOperator = Depends(require(Role.OPERATOR))
RequireAdmin = Depends(require(Role.ADMIN))

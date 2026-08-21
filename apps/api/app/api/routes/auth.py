from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireAdmin, current_actor
from app.core import security
from app.core.config import get_settings
from app.core.database import get_db
from app.models import ApiKey, User
from app.schemas.auth import (
    ActorRead,
    ApiKeyRead,
    CreateApiKeyRequest,
    CreatedApiKeyRead,
    CreateUserRequest,
    LoginRequest,
    TokenResponse,
    UserRead,
)
from app.services import auth_service
from app.services.auth_service import Actor, AuthenticationError

# This router is mounted without a role dependency (see app/api/router.py),
# so every route here declares its own. `/login` and `/me` are intentionally
# open and self-authenticating; the rest require admin.
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Exchange an email and password for a short-lived access token."""
    try:
        user = await auth_service.authenticate_user(db, request.email, request.password)
    except AuthenticationError as exc:
        # 401 with a deliberately generic message — see authenticate_user.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    settings = get_settings()
    token = security.create_access_token(user.email, role=user.role.value)
    await db.commit()

    return TokenResponse(
        access_token=token,
        expires_in_seconds=settings.access_token_minutes * 60,
        role=user.role,
        name=user.name,
        email=user.email,
    )


@router.get("/me", response_model=ActorRead)
async def me(actor: Actor = Depends(current_actor)) -> ActorRead:
    """Who the presented credential belongs to.

    Works for both credential types, so a service can confirm what role its
    key actually carries instead of assuming.
    """
    return ActorRead(
        kind=actor.kind,
        identifier=actor.identifier,
        display_name=actor.display_name,
        role=actor.role,
        agent_id=actor.agent_id,
    )


# --- users ------------------------------------------------------------------


@router.get("/users", response_model=list[UserRead], dependencies=[RequireAdmin])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[User]:
    result = await db.execute(select(User).order_by(User.email))
    return list(result.scalars().all())


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RequireAdmin],
)
async def create_user(request: CreateUserRequest, db: AsyncSession = Depends(get_db)) -> User:
    email = request.email.strip().lower()
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"User '{email}' already exists")

    user = User(
        email=email,
        name=request.name,
        password_hash=security.hash_password(request.password),
        role=request.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# --- API keys ---------------------------------------------------------------


@router.get("/api-keys", response_model=list[ApiKeyRead], dependencies=[RequireAdmin])
async def list_api_keys(db: AsyncSession = Depends(get_db)) -> list[ApiKey]:
    result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    return list(result.scalars().all())


@router.post(
    "/api-keys",
    response_model=CreatedApiKeyRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    request: CreateApiKeyRequest,
    db: AsyncSession = Depends(get_db),
    actor: Actor = RequireAdmin,
) -> CreatedApiKeyRead:
    """Mint a key for a service or agent.

    The secret is in the response and nowhere else: only its hash is stored,
    so it cannot be retrieved later. Losing it means issuing a new one.
    """
    generated = security.generate_api_key()
    expires_at = (
        datetime.now(UTC) + timedelta(days=request.expires_in_days)
        if request.expires_in_days is not None
        else None
    )

    key = ApiKey(
        name=request.name,
        token_hash=generated.token_hash,
        prefix=generated.prefix,
        role=request.role,
        agent_id=request.agent_id,
        expires_at=expires_at,
        created_by=actor.audit_label,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)

    return CreatedApiKeyRead(
        id=key.id,
        name=key.name,
        prefix=key.prefix,
        role=key.role,
        agent_id=key.agent_id,
        active=key.active,
        expires_at=key.expires_at,
        last_used_at=key.last_used_at,
        created_by=key.created_by,
        created_at=key.created_at,
        token=generated.token,
    )


@router.delete("/api-keys/{key_id}", response_model=ApiKeyRead, dependencies=[RequireAdmin])
async def revoke_api_key(key_id: int, db: AsyncSession = Depends(get_db)) -> ApiKey:
    """Deactivate a key.

    Deactivated rather than deleted: the key's prefix appears in audit records
    as the actor behind past decisions, and erasing it would leave those
    records naming a credential nobody can identify.
    """
    key = await db.get(ApiKey, key_id)
    if key is None:
        raise HTTPException(status_code=404, detail=f"API key {key_id} not found")

    key.active = False
    await db.commit()
    await db.refresh(key)
    return key

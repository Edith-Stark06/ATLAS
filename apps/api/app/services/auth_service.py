"""Authentication: who is calling, and what may they do.

Two credential types resolve to one `Actor`, so every downstream check and
every audit record treats a human operator and a service key the same way.
The distinction that matters to a reviewer is preserved *in* the actor (its
kind and identifier), not scattered through the call sites.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.models import ROLE_RANK, ApiKey, Role, User


@dataclass(frozen=True)
class Actor:
    """The authenticated caller, whatever kind of credential they used."""

    #: "user" or "api_key".
    kind: str
    #: Email for a user, key prefix for a service — stable, and safe to write
    #: into an audit record.
    identifier: str
    display_name: str
    role: Role
    #: Set when an API key is bound to a single agent.
    agent_id: str | None = None

    def can(self, required: Role) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[required]

    @property
    def audit_label(self) -> str:
        """How this actor appears in the governance ledger.

        Includes the kind because "admin@atlas.local" and a service key named
        "admin" must not be confusable when someone is reconstructing who did
        what.
        """
        return f"{self.kind}:{self.identifier}"


class AuthenticationError(Exception):
    """Credentials were absent, malformed, or did not match."""


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Verify an email/password pair.

    Every failure path raises the same error with the same message. Telling
    the caller whether the account exists, or is disabled, turns the login
    form into an account enumeration oracle.
    """
    user = (
        await db.execute(select(User).where(User.email == email.strip().lower()))
    ).scalar_one_or_none()

    if user is None:
        # Hash anyway so a missing account does not return measurably faster
        # than a wrong password.
        security.verify_password(password, security.hash_password("dummy"))
        raise AuthenticationError("Invalid email or password")

    if not security.verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password")

    if not user.active:
        raise AuthenticationError("Invalid email or password")

    # Opportunistic upgrade: lets the Argon2 cost be raised later and applied
    # to existing accounts on their next successful login.
    if security.needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(password)

    user.last_login_at = datetime.now(UTC)
    return user


async def resolve_api_key(db: AsyncSession, token: str) -> ApiKey:
    """Look a key up by hash and check it is still usable."""
    key = (
        await db.execute(select(ApiKey).where(ApiKey.token_hash == security.hash_api_key(token)))
    ).scalar_one_or_none()

    # The lookup is by hash, so this comparison is redundant against the
    # database — but it keeps the constant-time check on the path that decides
    # acceptance, rather than relying on an index lookup's timing.
    if key is None or not security.api_keys_match(token, key.token_hash):
        raise AuthenticationError("Invalid API key")

    if not key.active:
        raise AuthenticationError("Invalid API key")

    if key.expires_at is not None and key.expires_at <= datetime.now(UTC):
        raise AuthenticationError("Invalid API key")

    key.last_used_at = datetime.now(UTC)
    return key


async def actor_from_token(db: AsyncSession, token: str) -> Actor:
    """Resolve a bearer access token to an actor.

    The role is re-read from the database rather than trusted from the token
    claim: a token minted before a demotion must not keep working at the old
    level until it expires.
    """
    try:
        payload = security.decode_access_token(token)
    except security.InvalidToken as exc:
        raise AuthenticationError(str(exc)) from exc

    email = payload.get("sub", "")
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not user.active:
        raise AuthenticationError("Account is no longer active")

    return Actor(
        kind="user",
        identifier=user.email,
        display_name=user.name,
        role=user.role,
    )


def actor_from_api_key(key: ApiKey) -> Actor:
    return Actor(
        kind="api_key",
        identifier=key.prefix,
        display_name=key.name,
        role=key.role,
        agent_id=key.agent_id,
    )


async def count_users(db: AsyncSession) -> int:
    return len((await db.execute(select(User.id))).scalars().all())

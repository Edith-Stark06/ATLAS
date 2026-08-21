from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, Field

from app.models.enums import Role
from app.schemas.base import ApiModel


def _valid_email(value: str) -> str:
    """Light structural check, deliberately not `EmailStr`.

    Pydantic's `EmailStr` rejects special-use domains, which means it rejects
    `admin@atlas.local` — and `.local`, `.internal` and `.corp` are precisely
    what an internal governance console runs on. Strict RFC/deliverability
    validation buys nothing here either: the address is a lookup key for an
    account an admin has already created, not something we send mail to.
    """
    address = value.strip().lower()
    local, separator, domain = address.partition("@")
    if not separator or not local or not domain or " " in address:
        raise ValueError("must be an email address of the form name@domain")
    return address


Email = Annotated[str, AfterValidator(_valid_email)]


class LoginRequest(ApiModel):
    email: Email
    password: str = Field(min_length=1)


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    role: Role
    name: str
    email: str


class ActorRead(ApiModel):
    """Who the current credential belongs to."""

    kind: str
    identifier: str
    display_name: str
    role: Role
    agent_id: str | None = None


class CreateUserRequest(ApiModel):
    email: Email
    name: str = Field(min_length=1, max_length=120)
    # Long rather than complex: length is what actually resists guessing, and
    # composition rules mostly produce predictable substitutions.
    password: str = Field(min_length=12, max_length=256)
    role: Role = Role.VIEWER


class UserRead(ApiModel):
    id: int
    email: str
    name: str
    role: Role
    active: bool
    last_login_at: datetime | None
    created_at: datetime


class CreateApiKeyRequest(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    role: Role = Role.OPERATOR
    #: Restricts the key to acting for one agent.
    agent_id: str | None = None
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


class ApiKeyRead(ApiModel):
    id: int
    name: str
    prefix: str
    role: Role
    agent_id: str | None
    active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_by: str
    created_at: datetime


class CreatedApiKeyRead(ApiKeyRead):
    """Returned only at creation.

    `token` appears exactly once in the lifetime of the key — only its hash is
    stored, so it cannot be shown again.
    """

    token: str

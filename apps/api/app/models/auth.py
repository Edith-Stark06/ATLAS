from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import Role

_role_enum = Enum(Role, name="user_role", values_callable=lambda e: [m.value for m in e])


class User(Base):
    """A console operator.

    Distinct from `Agent`: an Agent is a governed subject, a User is a human
    who governs. Conflating them would make "who approved this?" ambiguous in
    exactly the situation where the answer matters.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))

    #: Argon2id. Never a plaintext or reversible form — see core/security.py.
    password_hash: Mapped[str] = mapped_column(String(255))

    role: Mapped[Role] = mapped_column(_role_enum, default=Role.VIEWER)

    #: Soft disable. Deleting the row would orphan the audit records that name
    #: this user as the actor, so access is withdrawn without erasing history.
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApiKey(Base):
    """A credential for a non-human caller — an agent or an upstream service.

    Agents are the primary consumer of `/decisions/execute`, and they cannot
    log in with a password. They get a key instead, with its own role, so a
    booking agent's credential cannot be used to rewrite policy.
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))

    #: SHA-256 of the token. The token itself is shown once at creation and is
    #: not recoverable — a leaked database must not yield working credentials.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    #: Leading characters in the clear, so a key is identifiable in a list
    #: without being reconstructable from it.
    prefix: Mapped[str] = mapped_column(String(32), index=True)

    role: Mapped[Role] = mapped_column(_role_enum, default=Role.OPERATOR)

    #: Optional binding to one agent. Set, and the key may only act for that
    #: agent — a compromised credential is then limited to the blast radius of
    #: the agent it belongs to rather than the whole estate.
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[str] = mapped_column(String(255), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

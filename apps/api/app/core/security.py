"""Password hashing, API key handling, and access tokens.

Two credential types with deliberately different hashing, for reasons worth
stating explicitly because getting this backwards is a common and expensive
mistake:

- **Passwords** are hashed with **Argon2id** — slow and memory-hard. A human
  password has little entropy, so a stolen table is only as safe as the cost
  of guessing each candidate.
- **API keys** are hashed with plain **SHA-256** — fast. The key is 256 bits
  of `secrets` randomness, so brute force is already impossible; a slow hash
  would buy nothing and would put a deliberate delay on every request an
  agent makes. Fast hashing is correct *because* the input is high-entropy,
  not despite it.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"

#: Shown to the user once, at creation, then never again — only the hash is
#: stored. The prefix is kept in the clear so a key can be identified in a
#: list ("which one am I about to revoke?") without being reversible.
API_KEY_PREFIX = "atlas_sk_"
API_KEY_PREFIX_LENGTH = len(API_KEY_PREFIX) + 8

_hasher = PasswordHasher()


class InvalidToken(Exception):
    """Token is missing, malformed, expired, or not signed by us."""


# --- passwords ---------------------------------------------------------------


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time as far as Argon2 allows; never raises on a bad hash.

    A malformed stored hash means a corrupt row, not a valid login — it must
    read as "wrong password", not as a 500 that tells an attacker the account
    exists and is in an unusual state.
    """
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    """True when the hash was made with weaker parameters than we now use.

    Lets the cost factor be raised over time and applied on next successful
    login, rather than leaving old accounts permanently on old parameters.
    """
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return False


# --- API keys ----------------------------------------------------------------


@dataclass(frozen=True)
class GeneratedApiKey:
    #: Full secret. Returned to the caller exactly once.
    token: str
    #: What gets stored.
    token_hash: str
    #: Leading characters, stored in the clear for identification.
    prefix: str


def generate_api_key() -> GeneratedApiKey:
    token = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return GeneratedApiKey(
        token=token,
        token_hash=hash_api_key(token),
        prefix=token[:API_KEY_PREFIX_LENGTH],
    )


def hash_api_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def api_keys_match(token: str, stored_hash: str) -> bool:
    """Compare with `compare_digest` so the check does not leak, through
    timing, how many leading characters were correct."""
    return hmac.compare_digest(hash_api_key(token), stored_hash)


# --- access tokens -----------------------------------------------------------


def create_access_token(subject: str, *, role: str, expires_in: timedelta | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expiry = now + (expires_in or timedelta(minutes=settings.access_token_minutes))

    payload: dict[str, Any] = {
        "sub": subject,
        # The role is a claim, but it is re-read from the database on every
        # request anyway — a token minted before a demotion must not keep
        # working at the old level until it expires.
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expiry.timestamp()),
        "iss": "atlas",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            # Pinned explicitly: accepting the token's own `alg` is how the
            # classic "alg: none" and HMAC-vs-RSA confusion attacks work.
            algorithms=[JWT_ALGORITHM],
            issuer="atlas",
            options={"require": ["exp", "sub", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc

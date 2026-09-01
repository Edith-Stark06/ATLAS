# Secrets

Everything here is a plain environment variable, read from `.env` at
process start (`apps/api/app/core/config.py`). No secrets manager is wired
up (no Vault, no AWS Secrets Manager) — if that changes, this doc and
`config.py`'s `Settings` class are the two places that need to agree.

## What's enforced automatically

`config.py`'s `_refuse_insecure_production` validator (lines 78-101) fails
startup — not a warning, a refusal to boot — outside `ENVIRONMENT=development`
if:

- `JWT_SECRET` is still the shipped development value, or shorter than 32
  characters
- `BOOTSTRAP_ADMIN_PASSWORD` is still the shipped development value

**What it does *not* check**: `DATABASE_URL` and `REDIS_URL` have no
equivalent guard against an insecure default. That's a real gap, left open
rather than silently patched — "insecure" for a connection string is a
product decision (does it mean the default host? a weak embedded password?
missing TLS?) that deserves a deliberate answer, not a guess baked in here.
`docker-compose.prod.yml` covers the Postgres side today, independently, by
requiring `POSTGRES_PASSWORD` via Compose's `${VAR:?...}` hard-fail syntax —
there's no equivalent requirement if you run `python -m app` directly
against a production database without Compose.

CI also runs a [gitleaks](https://github.com/gitleaks/gitleaks) scan
(`.github/workflows/ci.yml`) against every push and pull request, catching a
secret that made it into a commit before it reaches `main`.

## Generating and rotating each secret

### `JWT_SECRET`

```bash
openssl rand -hex 32
```

Signs every access token (`apps/api/app/core/security.py` via PyJWT,
HS256). **Rotating it invalidates every currently-issued JWT immediately** —
every signed-in user is signed out and has to log in again. It does **not**
affect API keys: `resolve_api_key` (`app/services/auth_service.py`) looks
keys up by their own stored hash (`security.hash_api_key`), entirely
independent of `JWT_SECRET`. Rotate this if the value has leaked (checked
into a commit, exposed in a log, shared over an insecure channel) —
otherwise there's no operational need to rotate it on a schedule the way
you would a password.

### `BOOTSTRAP_ADMIN_PASSWORD`

Only ever used once, by `python -m app.seed`, to create the very first
admin account when no users exist yet — see `docs/PROJECT_MEMORY.md` and
`config.py`. **Change it immediately after the first real login**, either
through the console (once a password-change flow exists — it doesn't yet;
today that means minting a new admin user via `POST /auth/users` and
retiring the bootstrap one) or by rotating `BOOTSTRAP_ADMIN_PASSWORD` and
re-seeding before any real account is created against it.

### `POSTGRES_PASSWORD`

Standard Postgres credential rotation: update it in `.env`, restart the
`postgres` container so it takes effect, then restart `api`/`migrate` with
the matching `DATABASE_URL`. Compose's `${POSTGRES_PASSWORD:?...}` syntax
means the stack refuses to start at all if this is unset — there's no
"forgot to set it and got a silent default" failure mode here, unlike
`JWT_SECRET`'s development fallback.

## API keys

Unlike the secrets above, API keys (`app/models/ApiKey`, minted via
`POST /auth/api-keys`) are per-integration credentials, not shared
deployment secrets. They're stored hashed (never in plaintext after
creation — the plaintext is returned exactly once, at mint time) and are
revoked individually by deleting the row, not by rotating a shared value.
`GET /auth/api-keys` (now paginated — see `docs/PROJECT_MEMORY.md`) is the
place to audit which keys exist and when they were created.

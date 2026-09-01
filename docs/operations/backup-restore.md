# Backup & restore

## What's backed up, and what deliberately isn't

**Postgres is the only durable source of truth**, and the only thing this
runbook covers. Everything ATLAS knows — agents, decisions, policies, the
governance ledger, trust snapshots — lives there.

Two things run alongside it and are **not** backed up, on purpose:

- **Redis** holds rate-limit counters (`app/services/rate_limiter.py`) —
  purely derived, short-lived state. Losing it on restore just means every
  client's rate-limit window resets; nothing is lost that matters.
- **ML artifacts** (`apps/api/app/ml/artifacts/`) are regenerable with
  `python -m app.ml.train` and are gitignored for exactly that reason — the
  trained model is a build output, not a record. If retraining is expensive
  or slow in your deployment target, snapshot this directory separately
  alongside a Postgres backup so a restore doesn't silently fall back to the
  heuristic scorer until the next training run.

## Taking a backup

```bash
# From the repo root, with the production stack running:
infra/scripts/backup.sh                 # writes to ./backups/
infra/scripts/backup.sh /path/to/dir    # or a directory of your choosing
```

This runs `pg_dump` inside the running `postgres` container (via
`docker compose -f infra/docker-compose.prod.yml`) and writes a
timestamped, gzip-compressed SQL dump — `atlas-<UTC timestamp>.sql.gz`.

### Suggested schedule

A daily cron entry calling `backup.sh` with a retention policy (e.g. keep 14
daily + 6 monthly) is a reasonable starting point for the data volumes this
system handles. Adjust to your actual write rate — a busier decision volume
warrants more frequent snapshots, since a restore loses everything decided
between the backup and the incident.

## Restoring

```bash
infra/scripts/restore.sh backups/atlas-20260901T120000Z.sql.gz
```

This is **destructive** — it drops and recreates every table in the target
database from the dump. The script pauses 5 seconds before running so a
wrong invocation can still be interrupted.

After restoring, confirm the API considers itself healthy:

```bash
curl -s http://localhost:8000/api/v1/health
```

Both `postgres` and `redis` should report `up` (Redis wasn't touched by the
restore — it never needed to be).

## An untested backup is not a backup

Run a restore drill periodically against a scratch environment, not just
the day something breaks. A dump that `pg_dump` produced without error can
still fail to `psql` back in cleanly — a schema drift, a corrupted file, a
permissions issue on the target — and the only way to know before it
matters is to have already tried it once when nothing was on fire.

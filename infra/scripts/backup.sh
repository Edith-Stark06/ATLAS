#!/usr/bin/env bash
# Dumps the production Postgres database to a timestamped, compressed file.
#
# Run from the repository root:
#   infra/scripts/backup.sh [output-dir]
#
# Backs up Postgres only — the one durable source of truth. See
# docs/operations/backup-restore.md for why Redis and the ML artifacts are
# deliberately not covered here.
set -euo pipefail

OUT_DIR="${1:-./backups}"
COMPOSE_FILE="infra/docker-compose.prod.yml"

if [ ! -f .env ]; then
  echo "No .env in the current directory — run this from the repo root." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .env

mkdir -p "$OUT_DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FILE="$OUT_DIR/atlas-${STAMP}.sql.gz"

docker compose -f "$COMPOSE_FILE" --env-file .env exec -T postgres \
  pg_dump -U "${POSTGRES_USER:?set POSTGRES_USER in .env}" -d "${POSTGRES_DB:-atlas}" \
  | gzip > "$FILE"

echo "Backup written to $FILE"

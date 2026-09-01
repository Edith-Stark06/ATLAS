#!/usr/bin/env bash
# Restores a backup produced by backup.sh into the running production
# Postgres container. DESTRUCTIVE — every table in the target database is
# dropped and recreated from the dump.
#
# Run from the repository root:
#   infra/scripts/restore.sh path/to/atlas-<timestamp>.sql.gz
set -euo pipefail

FILE="${1:?usage: infra/scripts/restore.sh <backup-file.sql.gz>}"
COMPOSE_FILE="infra/docker-compose.prod.yml"

if [ ! -f .env ]; then
  echo "No .env in the current directory — run this from the repo root." >&2
  exit 1
fi
if [ ! -f "$FILE" ]; then
  echo "No such backup file: $FILE" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .env

DB="${POSTGRES_DB:-atlas}"
echo "This will REPLACE every table in the '${DB}' database with the contents of ${FILE}."
echo "Ctrl+C now to abort. Continuing in 5 seconds..."
sleep 5

gunzip -c "$FILE" | docker compose -f "$COMPOSE_FILE" --env-file .env exec -T postgres \
  psql -U "${POSTGRES_USER:?set POSTGRES_USER in .env}" -d "$DB"

echo "Restore complete. Verify with: curl -s http://localhost:8000/api/v1/health"

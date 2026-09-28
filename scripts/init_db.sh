#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
ENV_FILE="$ROOT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

echo "Starting database container..."
docker compose -f "$COMPOSE_FILE" up -d db

echo -n "Waiting for Postgres to become ready"
until docker compose -f "$COMPOSE_FILE" exec -T db pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
  sleep 1
  echo -n "."
done
echo ""

# Idempotent schema apply: check for a known table
EXISTS=$(docker compose -f "$COMPOSE_FILE" exec -T db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT to_regclass('public.staff') IS NOT NULL;")

if [[ "$EXISTS" == "t" ]]; then
  echo "Schema already applied (table 'staff' exists). Skipping."
  echo "To reset: docker compose -f $COMPOSE_FILE down -v && rerun this script."
  exit 0
fi

echo "Applying schema from database/schema.sql ..."
docker compose -f "$COMPOSE_FILE" exec -T db \
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /schema/schema.sql

echo "Schema applied successfully."

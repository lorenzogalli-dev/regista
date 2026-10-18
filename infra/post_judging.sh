#!/usr/bin/env bash
# Run AFTER the judging period ends (10 Nov 2026), not before: removes PostgreSQL and lets the
# Container App scale to zero, so hosting costs drop to almost nothing. The app keeps working
# without a database (recorded runs are files); /health then reports the database as
# unreachable.
set -euo pipefail
RG=${RG:-rg-lgalli-1289}
PG=${PG:-gtf0893-pg}
APP=gtf-app

if [[ "$(date -u +%Y%m%d)" -le 20261110 && "${FORCE:-}" != "1" ]]; then
  echo "The judging period runs until 10 Nov 2026; refusing to run before then (FORCE=1 to override)." >&2
  exit 1
fi
az containerapp update -g "$RG" -n "$APP" --min-replicas 0 --remove-env-vars DATABASE_URL -o none
az containerapp secret remove -g "$RG" -n "$APP" --secret-names database-url -o none
az postgres flexible-server delete -g "$RG" -n "$PG" --yes
echo "PostgreSQL deleted; $APP scales to zero."

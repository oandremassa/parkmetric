#!/usr/bin/env sh
set -eu
: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL is required and must point to a verification database}"
IN="${1:?Usage: restore_postgres.sh <backup.dump>}"
pg_restore --clean --if-exists --no-owner --dbname="$RESTORE_DATABASE_URL" "$IN"
echo "Restore completed into the explicitly supplied verification database."

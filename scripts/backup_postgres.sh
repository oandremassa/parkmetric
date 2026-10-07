#!/usr/bin/env sh
set -eu
: "${DATABASE_URL:?DATABASE_URL is required}"
OUT="${1:-parkmetric-$(date +%Y%m%d-%H%M%S).dump}"
pg_dump --format=custom --no-owner --file="$OUT" "$DATABASE_URL"
echo "Backup written to $OUT"

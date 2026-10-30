#!/bin/sh
set -e

# Ensure instance directory exists
mkdir -p /app/instance

DB_PATH="${INFLATION_DB_PATH:-/app/instance/inflation_lens.sqlite3}"

# Auto-seed realistic data if database file does not exist
if [ "${AUTO_SEED:-1}" = "1" ] && [ ! -f "$DB_PATH" ]; then
    echo "==> [Inflation Lens] Seeding initial database at $DB_PATH..."
    python scripts/seed_perf_db.py "$DB_PATH"
    echo "==> [Inflation Lens] Database initialized successfully."
fi

exec "$@"

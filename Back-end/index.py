"""Vercel WSGI entrypoint for the Inflation Lens Flask API."""

from __future__ import annotations

import os
from pathlib import Path

# Vercel Serverless functions run on a read-only filesystem except /tmp.
# Seed a deterministic production-shaped SQLite snapshot into /tmp on
# cold start when no pre-existing database file is present.
if os.environ.get("VERCEL"):
    _db_path = Path(os.environ.setdefault("INFLATION_DB_PATH", "/tmp/inflation_lens.sqlite3"))
    if not _db_path.exists():
        from scripts.seed_perf_db import seed

        seed(_db_path)

from app import create_app

app = create_app()

__all__ = ["app"]

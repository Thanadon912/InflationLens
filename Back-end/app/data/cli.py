from __future__ import annotations

import json

import click
from flask import Flask

from app.data.service import IngestionService, load_local_env
from app.data.store import SnapshotStore


def register_data_cli(app: Flask) -> None:
    @app.cli.group("data")
    def data_group():
        """Fetch, verify, and inspect official inflation data snapshots."""

    @data_group.command("sync")
    @click.option("--geography", default="all", show_default=True)
    @click.option("--indicator", default="all", show_default=True)
    def sync(geography: str, indicator: str):
        load_local_env()
        result = IngestionService().sync(geography, indicator)
        click.echo(json.dumps(result, indent=2, sort_keys=True))
        if result["status"] == "partial":
            raise SystemExit(2)
        if result["status"] == "failed":
            raise SystemExit(1)

    @data_group.command("verify")
    @click.option("--geography", default="all", show_default=True)
    @click.option("--indicator", default="all", show_default=True)
    def verify(geography: str, indicator: str):
        load_local_env()
        result = IngestionService().verify(geography, indicator)
        click.echo(json.dumps(result, indent=2, sort_keys=True))
        if result["status"] != "ok":
            raise SystemExit(2)

    @data_group.command("status")
    def status():
        click.echo(json.dumps(SnapshotStore().status(), indent=2, sort_keys=True))

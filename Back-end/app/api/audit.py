"""Structured, secret-safe calculation audit events."""

from __future__ import annotations

import json
import logging
import os

from app.models.indicator_result import IndicatorResult

logger = logging.getLogger("inflation_engine.audit")


def log_calculation(result: IndicatorResult) -> None:
    logger.info(json.dumps({
        "event": "indicator_calculated",
        "indicator_id": result.indicator_id,
        "geography": result.geography,
        "period": result.period,
        "method": result.method,
        # Deliberately omit URLs, retrieval timestamps, values, and the raw
        # request.  Provider/series/vintage are sufficient to reproduce which
        # source revision participated without turning the audit log into a
        # sink for credentials or user-supplied payload data.
        "input_series": [
            {
                "provider": item.provider,
                "series_id": item.series_id,
                "data_vintage": item.data_vintage,
            }
            for item in result.input_series
        ],
        "config_version": result.config_version,
        "methodology_version": result.methodology_version,
        "warnings": list(result.warnings),
        "output": result.value,
        "calculated_at": result.calculated_at,
        "software_version": "0.2.0",
        "git_commit": os.environ.get("GIT_COMMIT", "unknown"),
    }, sort_keys=True))

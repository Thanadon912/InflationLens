from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.api.blueprint import _calculate_country
from app.api.country import HANDLERS
from app.config.loader import load_country_profile, load_source_registry
from app.data.store import SnapshotStore
from app.engines.shared.growth import year_over_year
from app.providers.base import ProviderError, ProviderSchemaError, ResilientClient, SourcePoint, utc_now
from app.providers import fetch_provider

logger = logging.getLogger("inflation_engine.ingestion")
SUPPORTED_INDICATORS = ("headline_consumer_inflation", "essential_cost_inflation", "broad_money_expansion", "economy_wide_inflation")


def load_local_env(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.is_file() and Path("../.env").is_file():
        env_path = Path("../.env")
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class IngestionService:
    def __init__(self, store: SnapshotStore | None = None, client: ResilientClient | None = None) -> None:
        self.store = store or SnapshotStore()
        self.client = client or ResilientClient()
        self.registry = load_source_registry()

    def sync(self, geography: str = "all", indicator: str = "all") -> dict[str, Any]:
        geography = geography.upper() if geography.lower() != "all" else "all"
        run_id = self.store.create_run(geography, indicator)
        mappings = [m for m in self.registry["sources"] if (geography == "all" or m["geography"] == geography) and (indicator == "all" or m["indicator_id"] == indicator)]
        successes = failures = 0
        groups: list[tuple[str, list[dict]]] = []
        bls = [m for m in mappings if m["provider"] == "bls"]
        if bls:
            groups.append(("bls", bls))
        groups.extend((m["provider"], [m]) for m in mappings if m["provider"] != "bls")
        start_year = datetime.now(UTC).year - 3
        for provider, provider_mappings in groups:
            try:
                bundles = fetch_provider(provider, provider_mappings, start_year=start_year, client=self.client)
                if not bundles:
                    raise ProviderSchemaError("Provider returned no bundles")
                for bundle in bundles:
                    raw_id = self.store.save_bundle(run_id, bundle)
                    for point in bundle.points:
                        point.mapping["source_url"] = bundle.request_url
                        self.store.save_point(run_id, raw_id, point)
                successes += 1
            except Exception as exc:  # isolate each source mapping/batch
                failures += 1
                self.store.add_issue(run_id, "PROVIDER_FETCH_FAILED", str(exc), provider=provider, geography=provider_mappings[0].get("geography"), indicator_id=provider_mappings[0].get("indicator_id"))
                logger.warning("provider sync failed provider=%s error=%s", provider, type(exc).__name__)
        for geo in sorted({m["geography"] for m in mappings}):
            self._derive_essential(run_id, geo)
            self._cross_source_checks(run_id, geo)
            for indicator_id in SUPPORTED_INDICATORS:
                if indicator != "all" and indicator_id != indicator:
                    continue
                try:
                    self.calculate_available(run_id, geo, indicator_id)
                except Exception as exc:
                    self.store.add_issue(run_id, "CALCULATION_FAILED", str(exc), geography=geo, indicator_id=indicator_id)
        self.store.finish_run(run_id, successes=successes, failures=failures)
        return {"run_id": run_id, "status": "success" if failures == 0 else "partial" if successes else "failed", "successes": successes, "failures": failures, "issues": self.store.issues(run_id)}

    def verify(self, geography: str = "all", indicator: str = "all") -> dict[str, Any]:
        geography = geography.upper() if geography.lower() != "all" else "all"
        mappings = [m for m in self.registry["sources"] if (geography == "all" or m["geography"] == geography) and (indicator == "all" or m["indicator_id"] == indicator)]
        checks = []
        for mapping in mappings:
            try:
                bundles = fetch_provider(mapping["provider"], [mapping], start_year=datetime.now(UTC).year - 1, client=self.client)
                count = sum(len(bundle.points) for bundle in bundles)
                checks.append({"provider": mapping["provider"], "series_id": mapping["series_id"], "status": "ok", "observations": count})
            except Exception as exc:
                checks.append({"provider": mapping["provider"], "series_id": mapping["series_id"], "status": "failed", "error": str(exc)})
        return {"status": "ok" if all(c["status"] == "ok" for c in checks) else "partial", "checks": checks}

    def _derive_essential(self, run_id: str, geography: str) -> None:
        rows = self.store.latest_observations(geography, "essential_cost_inflation", "category_index")
        by_component: dict[str, dict[str, dict]] = defaultdict(dict)
        for row in rows:
            by_component[row["component_id"]][row["observation_period"]] = row
        for component, periods in by_component.items():
            for period, current in periods.items():
                prior_period = _year_before(period)
                prior = periods.get(prior_period)
                if prior is None or current["value"] <= 0 or prior["value"] <= 0:
                    continue
                existing = [r for r in self.store.latest_observations(geography, "essential_cost_inflation", "category_rates") if r["component_id"] == component and r["observation_period"] == period and r["sync_run_id"] == run_id]
                if existing:
                    continue
                mapping = {"provider": "derived", "series_id": f"yoy:{current['source_series_id']}", "indicator_id": "essential_cost_inflation", "role": "category_rates", "geography": geography, "component_id": component, "frequency": "monthly", "unit": "percent_yoy", "seasonally_adjusted": bool(current["seasonally_adjusted"]), "source_url": current["source_url"]}
                point = SourcePoint(mapping, period, year_over_year(current["value"], prior["value"]), is_estimated=bool(current["is_estimated"] or prior["is_estimated"]), is_revised=bool(current["is_revised"] or prior["is_revised"]), data_vintage=current["data_vintage"])
                self.store.save_point(run_id, None, point, lineage=(current["id"], prior["id"]))

    def _cross_source_checks(self, run_id: str, geography: str) -> None:
        if geography != "USA":
            return
        primary = self.store.latest_observations("USA", "headline_consumer_inflation", "all_items_cpi_index")
        shadow = self.store.latest_observations("USA", "headline_consumer_inflation", "shadow_index")
        shadow_by_period = {row["observation_period"]: row for row in shadow}
        tolerance = self.registry["defaults"]["cross_source_index_tolerance"]
        for row in primary:
            other = shadow_by_period.get(row["observation_period"])
            if other and abs(row["value"] - other["value"]) > tolerance:
                self.store.add_issue(run_id, "CROSS_SOURCE_DIFFERENCE", "Primary BLS CPI and FRED shadow series differ beyond tolerance; primary was retained", severity="warning", provider="bls/fred", geography="USA", indicator_id="headline_consumer_inflation", details={"period": row["observation_period"], "primary": row["value"], "shadow": other["value"], "tolerance": tolerance})

    def calculate_available(self, run_id: str, geography: str, indicator_id: str) -> int:
        candidates = self._candidate_periods(geography, indicator_id)
        calculated = 0
        profile = load_country_profile(geography)
        for period in candidates:
            try:
                payload, used = self._payload(geography, indicator_id, period)
                result = _calculate_country(HANDLERS[indicator_id], geography, indicator_id, payload, profile).to_dict()
                vintages = [r["data_vintage"] or r["retrieved_at"] for r in used]
                self.store.save_result(run_id, geography, indicator_id, period, result, vintages)
                calculated += 1
            except Exception as exc:
                self.store.add_issue(run_id, "PERIOD_UNAVAILABLE", str(exc), severity="warning", geography=geography, indicator_id=indicator_id, details={"period": period})
        return calculated

    def _candidate_periods(self, geography: str, indicator_id: str) -> list[str]:
        role = {"headline_consumer_inflation": "all_items_cpi_index", "essential_cost_inflation": "category_rates", "broad_money_expansion": "money_level", "economy_wide_inflation": "nominal_gdp"}[indicator_id]
        rows = self.store.latest_observations(geography, indicator_id, role)
        limit = self.registry["defaults"]["quarterly_backfill_periods" if indicator_id == "economy_wide_inflation" else "monthly_backfill_periods"]
        periods = {r["observation_period"] for r in rows}
        if indicator_id == "essential_cost_inflation":
            # category_rates are already year-over-year derived observations;
            # requiring another prior-year rate would impose an accidental
            # two-year lookback and discard otherwise calculable periods.
            return sorted(periods, reverse=True)[:limit]
        # A published result always needs its documented YoY lag. Avoid
        # manufacturing noisy issues for the oldest backfill year, whose
        # prior-year observation was intentionally outside the fetch window.
        complete = {period for period in periods if _year_before(period) in periods}
        return sorted(complete, reverse=True)[:limit]

    def _payload(self, geography: str, indicator_id: str, period: str) -> tuple[dict, list[dict]]:
        used: list[dict] = []
        if indicator_id == "headline_consumer_inflation":
            rows = self.store.latest_observations(geography, indicator_id, "all_items_cpi_index")
            selected = [r for r in rows if r["observation_period"] <= period and r["observation_period"] >= _months_before(period, 15)]
            used.extend(selected)
            inputs = {"all_items_cpi_index": [_public_observation(r, indicator_id) for r in selected]}
        elif indicator_id == "essential_cost_inflation":
            rows = [r for r in self.store.latest_observations(geography, indicator_id, "category_rates") if r["observation_period"] == period]
            used.extend(rows)
            inputs = {"category_rates": [_public_observation(r, indicator_id) for r in rows]}
        elif indicator_id == "broad_money_expansion":
            rows = self.store.latest_observations(geography, indicator_id, "money_level")
            by_period = {r["observation_period"]: r for r in rows}
            current, prior = by_period[period], by_period[_year_before(period)]
            used.extend((current, prior))
            inputs = {"money_current": [_public_observation(current, indicator_id)], "money_prior_year": [_public_observation(prior, indicator_id)]}
        else:
            rows = self.store.latest_observations(geography, indicator_id)
            by_role_period = {(r["role"], r["observation_period"]): r for r in rows}
            prior_period = _year_before(period)
            nominal_current = by_role_period[("nominal_gdp", period)]
            real_current = by_role_period[("real_gdp", period)]
            nominal_prior = by_role_period[("nominal_gdp", prior_period)]
            real_prior = by_role_period[("real_gdp", prior_period)]
            used.extend((nominal_current, real_current, nominal_prior, real_prior))
            inputs = {
                "nominal_gdp_current": [_public_observation(nominal_current, indicator_id)],
                "real_gdp_current": [_public_observation(real_current, indicator_id)],
                "nominal_gdp_prior_year": [_public_observation(nominal_prior, indicator_id)],
                "real_gdp_prior_year": [_public_observation(real_prior, indicator_id)],
            }
        return {"period": period, "inputs": inputs}, used


def decorate_snapshot(row: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    result = dict(row["result"])
    frequency = "quarterly" if "Q" in row["period"] else "monthly"
    stale_days = defaults[f"{frequency}_stale_days"]
    calculated = datetime.fromisoformat(row["calculated_at"].replace("Z", "+00:00"))
    result["data_snapshot"] = {"snapshot_id": row["id"], "sync_run_id": row["sync_run_id"], "requested_period": row["period"], "actual_period": row["period"], "as_of": row["calculated_at"], "stale": datetime.now(UTC) - calculated > timedelta(days=stale_days), "source_vintages": row["source_vintages"]}
    return result


def _public_observation(row: dict, indicator_id: str) -> dict:
    return {key: value for key, value in {
        "provider": row["provider"], "source_series_id": row["source_series_id"], "indicator_id": indicator_id,
        "geography": row["geography"], "frequency": row["frequency"], "unit": row["unit"],
        "observation_period": row["observation_period"], "value": row["value"], "retrieved_at": row["retrieved_at"],
        "validation_status": "validated", "publication_date": row["publication_date"], "seasonally_adjusted": None if row["seasonally_adjusted"] is None else bool(row["seasonally_adjusted"]),
        "source_url": row["source_url"], "is_estimated": bool(row["is_estimated"]), "is_revised": bool(row["is_revised"]),
        "data_vintage": row["data_vintage"], "component_id": row["component_id"], "currency": row["currency"],
    }.items() if value is not None}


def _year_before(period: str) -> str:
    return f"{int(period[:4]) - 1}{period[4:]}"


def _months_before(period: str, months: int) -> str:
    year, month = map(int, period.split("-"))
    total = year * 12 + month - 1 - months
    return f"{total // 12:04d}-{total % 12 + 1:02d}"

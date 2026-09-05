"""Configuration loading.

CALCULATION_ENGINE_GUIDELINES.md section 11 lists everything that "must
remain outside calculation code": source priorities, basket weights, trim
percentages, mortgage assumptions, coverage thresholds, and more. This
module is the *only* place in the codebase that reads those YAML files
from disk. Engine modules (``app.engines.*``) never import this module —
they accept plain config values/dataclasses as function parameters. The
API layer is responsible for calling this loader and handing the resulting
values to the engines, which keeps every engine function testable without
touching the filesystem.

Nothing here performs network I/O; it only reads local, version-controlled
YAML files, which is why it is a separate concern from the (out-of-scope)
provider adapters that would fetch live data from external APIs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent


class ConfigError(Exception):
    """Raised when a configuration file is missing or malformed.

    This is a bootstrapping/deployment error, not a per-request domain
    error, so it is intentionally not one of the ``EngineError``
    subclasses in ``app.engines.shared.errors``.
    """


@lru_cache(maxsize=None)
def _load_yaml_cached(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"Configuration file not found: {p}")
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        raise ConfigError(f"Configuration file is empty: {p}")
    if not isinstance(data, dict):
        raise ConfigError(f"Configuration file must contain a mapping at the top level: {p}")
    return data


def load_yaml(path: Path | str) -> dict:
    """Load and cache a YAML file as a plain dict.

    Caching is safe because configuration is deployed as version-controlled
    files, not mutated at runtime; a process restart is required to pick up
    a configuration change, which is consistent with ENGINE guidelines
    section 21 treating configuration version as part of the cache key.
    """

    return dict(_load_yaml_cached(str(Path(path).resolve())))


def clear_cache() -> None:
    """Clear the YAML cache. Used by tests that swap in fixture config."""

    _load_yaml_cached.cache_clear()


def load_indicator_registry() -> dict:
    return load_yaml(CONFIG_DIR / "indicator_registry.yaml")


def load_methodology_versions() -> dict:
    return load_yaml(CONFIG_DIR / "methodology_versions.yaml")


def load_global_weights() -> dict:
    return load_yaml(CONFIG_DIR / "global_weights.yaml")


def load_source_registry() -> dict:
    return load_yaml(CONFIG_DIR / "source_registry.yaml")


def load_us_regions() -> dict:
    """Census-region assignment by 2-digit state FIPS (app/config/us_regions.yaml).

    Backs GET /api/v1/regions/us: every state inherits its census region's
    published regional CPI (source_registry.yaml), never a per-state estimate.
    """

    return load_yaml(CONFIG_DIR / "us_regions.yaml")


def load_iso_numeric() -> dict:
    """ISO 3166-1 alpha-3 -> numeric join table (app/config/iso_numeric.yaml).

    Backs GET /api/v1/world/cross-section: joins World Bank's ISO3 country
    codes onto world-atlas's numeric-keyed TopoJSON features.
    """

    return load_yaml(CONFIG_DIR / "iso_numeric.yaml")


def load_country_profile(geography: str) -> dict:
    path = CONFIG_DIR / "country_profiles" / f"{geography.upper()}.yaml"
    try:
        return load_yaml(path)
    except ConfigError as exc:
        raise ConfigError(
            f"No country profile configured for geography {geography!r} "
            f"(expected {path})"
        ) from exc


def available_country_profiles() -> list[str]:
    profiles_dir = CONFIG_DIR / "country_profiles"
    return sorted(p.stem for p in profiles_dir.glob("*.yaml"))

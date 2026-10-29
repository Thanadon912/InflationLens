import ast
from pathlib import Path
import re

from app.api import contracts, country, global_
from app.config import loader


ENGINE_ROOT = Path(__file__).parents[2] / "app" / "engines"
DOCS_ROOT = Path(__file__).parents[3] / "docs"
FORBIDDEN_IMPORTS = {"requests", "urllib", "httpx", "aiohttp", "socket", "sqlite3", "sqlalchemy", "yaml"}


def engine_files():
    return sorted(ENGINE_ROOT.rglob("*.py"))


def test_engines_do_not_import_network_database_or_config_io():
    violations = []
    for path in engine_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if name in FORBIDDEN_IMPORTS or (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.config")):
                    violations.append(f"{path.relative_to(ENGINE_ROOT)}:{node.lineno}:{name}")
    assert violations == []


def test_prohibited_product_labels_are_absent_from_runtime_literals():
    prohibited = "true" + " inflation"
    violations = []
    for path in engine_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and prohibited in node.value.lower():
                violations.append(f"{path.relative_to(ENGINE_ROOT)}:{node.lineno}")
    assert violations == []


def test_policy_weight_mappings_and_defaults_are_not_hard_coded_in_engines():
    """Policy weights belong in versioned configuration, not formulas.

    Mathematical constants such as the weighted-median 0.5 boundary are
    intentionally allowed; this gate targets policy-shaped mappings and
    function defaults whose names explicitly identify them as weights.
    """
    violations = []
    for path in engine_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Dict):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names = [target.id for target in targets if isinstance(target, ast.Name)]
                if any("weight" in name.lower() for name in names):
                    if any(isinstance(value, ast.Constant) and isinstance(value.value, float) for value in node.value.values):
                        violations.append(f"{path.relative_to(ENGINE_ROOT)}:{node.lineno}:weight mapping")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                positional = node.args.args[-len(node.args.defaults):] if node.args.defaults else []
                defaults = list(zip(positional, node.args.defaults)) + list(zip(node.args.kwonlyargs, node.args.kw_defaults))
                for argument, default in defaults:
                    if "weight" in argument.arg.lower() and isinstance(default, ast.Constant) and isinstance(default.value, (int, float)):
                        violations.append(f"{path.relative_to(ENGINE_ROOT)}:{node.lineno}:{argument.arg}")
    assert violations == []


def _parse_frontmatter_version(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    match = re.search(r"^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$", text, re.MULTILINE)
    assert match is not None, f"Missing version frontmatter in {md_path}"
    return match.group(1)


def test_architecture_registries_and_documentation_versions_are_synchronized():
    """Verify that the 10 Country + 8 Global engines, API contracts, config
    registries, and Markdown methodology documents stay in lockstep."""

    versions_cfg = loader.load_methodology_versions()
    country_versions = versions_cfg["country"]
    global_versions = versions_cfg["global"]

    assert len(country.HANDLERS) == 10
    assert len(global_.HANDLERS) == 8
    assert set(country.HANDLERS) == set(country_versions)
    assert set(global_.HANDLERS) == set(global_versions)
    assert set(country.HANDLERS) | set(global_.HANDLERS) == set(contracts.REQUIRED_ROLES)
    assert set(contracts.REQUIRED_ROLES) == set(contracts.ACCEPTED_FREQUENCIES)

    expected_version = _parse_frontmatter_version(DOCS_ROOT / "CALCULATION_ENGINE_GUIDELINES.md")
    assert _parse_frontmatter_version(DOCS_ROOT / "COUNTRY_INFLATION_METHODS.md") == expected_version
    assert _parse_frontmatter_version(DOCS_ROOT / "GLOBAL_INFLATION_METHODS.md") == expected_version

    for indicator_id, version in {**country_versions, **global_versions}.items():
        assert version == expected_version, f"{indicator_id} version mismatch in methodology_versions.yaml"

    for scope_dir in ("country", "global_"):
        for path in sorted((ENGINE_ROOT / scope_dir).glob("*.py")):
            if path.name == "__init__.py":
                continue
            text = path.read_text(encoding="utf-8")
            match = re.search(r'^METHODOLOGY_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
            assert match is not None, f"{path.name} missing METHODOLOGY_VERSION"
            assert match.group(1) == expected_version, f"{path.name} METHODOLOGY_VERSION != {expected_version}"

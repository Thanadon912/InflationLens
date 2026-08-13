import ast
from pathlib import Path


ENGINE_ROOT = Path(__file__).parents[2] / "app" / "engines"
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

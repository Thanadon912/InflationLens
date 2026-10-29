#!/usr/bin/env python3
"""Bootstrap and deploy the Git-connected Vercel projects for Inflation Lens.

Never uploads a dirty local working tree. Every deployment is created from the
exact GitHub commit SHA that passed CI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API = "https://api.vercel.com"
REPOSITORY = "Thanadon912/InflationLens"
PRODUCTION_BRANCH = "master"
FRONTEND_PROJECT = "inflation-lens-thanadon912"
BACKEND_PROJECT = "inflation-lens-api-thanadon912"
FRONTEND_URL = f"https://{FRONTEND_PROJECT}.vercel.app"
BACKEND_URL = f"https://{BACKEND_PROJECT}.vercel.app"

PROJECTS = {
    BACKEND_PROJECT: {"rootDirectory": "Back-end", "framework": "flask"},
    FRONTEND_PROJECT: {"rootDirectory": "Front-end", "framework": "vite"},
}

PUBLIC_ENV_KEYS = {
    "VITE_API_BASE_URL",
    "CORS_ALLOWED_ORIGINS",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_READ_PER_MINUTE",
    "RATE_LIMIT_CALC_PER_MINUTE",
}

BACKEND_SECRET_KEYS = {
    "FRED_API_KEY",
    "BEA_API_KEY",
    "EIA_API_KEY",
}


class VercelError(RuntimeError):
    pass


def read_env(path: Path | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if path is not None and path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if re.fullmatch(r"[A-Z][A-Z0-9_]*", key.strip()):
                values[key.strip()] = value.strip().strip('"').strip("'")
    for key in BACKEND_SECRET_KEYS | PUBLIC_ENV_KEYS:
        if os.environ.get(key):
            values.setdefault(key, os.environ[key].strip())
    return values


def api_request(
    token: str,
    method: str,
    path: str,
    payload: dict[str, Any] | list[Any] | None = None,
) -> Any:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{API}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # nosec B310 - HTTPS Vercel API endpoint
            content = response.read()
            return json.loads(content) if content else {}
    except HTTPError as exc:
        try:
            detail = json.load(exc).get("error", {}).get("message", "request failed")
        except Exception:
            detail = "request failed"
        raise VercelError(f"Vercel API {method} {path} failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise VercelError(f"Vercel API is unreachable: {exc.reason}") from exc


def get_project(token: str, name: str) -> dict[str, Any] | None:
    try:
        return api_request(token, "GET", f"/v9/projects/{quote(name)}")
    except VercelError as exc:
        if "(404)" in str(exc):
            return None
        raise


def upsert_project(token: str, name: str, spec: dict[str, Any]) -> dict[str, Any]:
    project = get_project(token, name)
    create_payload: dict[str, Any] = {
        "name": name,
        "rootDirectory": spec["rootDirectory"],
        "gitRepository": {"type": "github", "repo": REPOSITORY},
    }
    if spec["framework"] is not None:
        create_payload["framework"] = spec["framework"]
    if project is None:
        api_request(token, "POST", "/v10/projects", create_payload)
        print(f"Created Git-connected Vercel project {name}")
    updates: dict[str, Any] = {
        "rootDirectory": spec["rootDirectory"],
        "autoAssignCustomDomains": False,
    }
    if spec["framework"] is not None:
        updates["framework"] = spec["framework"]
    project = api_request(
        token,
        "PATCH",
        f"/v9/projects/{quote(name)}",
        updates,
    )
    if project is not None:
        print(f"Verified Vercel project {name}")
    link = project.get("link") or {}
    if link.get("type") != "github" or link.get("org") != "Thanadon912" or link.get("repo") != "InflationLens":
        raise VercelError(f"{name} is not linked to the approved GitHub repository {REPOSITORY}")
    if project.get("rootDirectory") != spec["rootDirectory"]:
        raise VercelError(f"{name} has an unexpected root directory")
    return project


def env_payload(key: str, value: str) -> dict[str, Any]:
    return {
        "key": key,
        "value": value,
        "type": "plain" if key in PUBLIC_ENV_KEYS or key.startswith("VITE_") else "sensitive",
        "target": ["production", "preview"],
    }


def replace_environment(token: str, project: str, values: dict[str, str]) -> None:
    non_empty = {k: v for k, v in values.items() if v}
    if not non_empty:
        return
    current = api_request(token, "GET", f"/v9/projects/{quote(project)}/env").get("envs", [])
    managed_keys = set(non_empty)
    for item in current:
        if item.get("key") in managed_keys:
            api_request(
                token,
                "DELETE",
                f"/v9/projects/{quote(project)}/env/{quote(item['id'])}",
            )
    payload = [env_payload(key, value) for key, value in sorted(non_empty.items())]
    api_request(token, "POST", f"/v10/projects/{quote(project)}/env", payload)
    print(f"Configured {len(payload)} managed environment variables for {project}")


def runtime_values(project: str, supplied: dict[str, str]) -> dict[str, str]:
    if project == FRONTEND_PROJECT:
        return {
            "VITE_API_BASE_URL": f"{BACKEND_URL}/api/v1",
        }
    values = {key: supplied.get(key, "") for key in BACKEND_SECRET_KEYS if supplied.get(key)}
    values.update(
        {
            "CORS_ALLOWED_ORIGINS": f"{FRONTEND_URL},http://localhost:3000,http://localhost:5173",
            "RATE_LIMIT_ENABLED": "1",
        }
    )
    return values


def bootstrap(token: str, env_file: Path | None = None) -> None:
    supplied = read_env(env_file)
    for name, spec in PROJECTS.items():
        upsert_project(token, name, spec)
        replace_environment(token, name, runtime_values(name, supplied))


def create_deployment(token: str, project: dict[str, Any], revision: str, ref: str = PRODUCTION_BRANCH) -> dict[str, Any]:
    link = project["link"]
    payload = {
        "name": project["name"],
        "target": "production",
        "gitSource": {
            "type": "github",
            "repoId": link["repoId"],
            "ref": ref,
            "sha": revision,
        },
        "meta": {"githubActionsGated": "true", "testedCommitSha": revision},
    }
    return api_request(
        token,
        "POST",
        "/v13/deployments?forceNew=1&skipAutoDetectionConfirmation=1",
        payload,
    )


def wait_ready(token: str, deployment_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        deployment = api_request(token, "GET", f"/v13/deployments/{quote(deployment_id)}")
        state = deployment.get("readyState")
        if state == "READY":
            return deployment
        if state in {"ERROR", "CANCELED"}:
            raise VercelError(f"Deployment {deployment_id} ended in state {state}")
        time.sleep(5)
    raise VercelError(f"Deployment {deployment_id} did not become ready within 10 minutes")


def http_json(url: str) -> Any:
    try:
        with urlopen(Request(url, headers={"User-Agent": "InflationLens-CD-Smoke/1.0"}), timeout=30) as response:  # nosec B310
            if response.status != 200:
                raise VercelError(f"Smoke endpoint returned HTTP {response.status}: {url}")
            return json.load(response)
    except (HTTPError, URLError, ValueError) as exc:
        raise VercelError(f"Smoke request failed for {url}") from exc


def wait_for_payload(url: str, predicate, description: str) -> Any:
    deadline = time.monotonic() + 120
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            payload = http_json(url)
            if predicate(payload):
                return payload
        except VercelError as exc:
            last_error = exc
        time.sleep(3)
    suffix = f": {last_error}" if last_error else ""
    raise VercelError(f"Timed out waiting for {description}{suffix}")


def deploy(token: str, revision: str, ref: str = PRODUCTION_BRANCH, env_file: Path | None = None) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise VercelError("REVISION must be a full 40-character Git SHA")
    supplied = read_env(env_file)
    projects = {}
    for name, spec in PROJECTS.items():
        projects[name] = upsert_project(token, name, spec)
        replace_environment(token, name, runtime_values(name, supplied))

    backend = wait_ready(token, create_deployment(token, projects[BACKEND_PROJECT], revision, ref=ref)["id"])
    frontend = wait_ready(token, create_deployment(token, projects[FRONTEND_PROJECT], revision, ref=ref)["id"])
    backend_preview = f"https://{backend['url']}"
    backend_sso = (projects[BACKEND_PROJECT].get("ssoProtection") or {}).get(
        "deploymentType"
    ) == "all_except_custom_domains"
    if backend_sso:
        print("Backend staged content smoke deferred because the deployment URL requires Vercel SSO")
    elif http_json(f"{backend_preview}/api/v1/health") != {"status": "ok"}:
        raise VercelError("Backend staged health payload is invalid")

    for name, deployment in ((BACKEND_PROJECT, backend), (FRONTEND_PROJECT, frontend)):
        project_id = projects[name].get("id")
        if not isinstance(project_id, str) or not project_id:
            raise VercelError(f"Vercel project {name} did not include an id")
        api_request(
            token,
            "POST",
            f"/v10/projects/{quote(project_id)}/promote/{quote(deployment['id'])}",
            {},
        )
        print(f"Promoted {name} deployment {deployment['id']}")

    wait_for_payload(
        f"{BACKEND_URL}/api/v1/health",
        lambda payload: payload == {"status": "ok"},
        "production backend health",
    )
    print(f"Production verified at {FRONTEND_URL} and {BACKEND_URL} (SHA {revision})")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("bootstrap", "deploy"))
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--revision", default=None)
    parser.add_argument("--ref", default=PRODUCTION_BRANCH)
    args = parser.parse_args()
    token = (
        os.environ.get("VERCEL_TOKEN")
        or os.environ.get("VERCEL_ACCESS_TOKEN")
        or os.environ.get("VERCEL_API_KEY")
        or ""
    ).strip()
    if not token:
        raise VercelError("VERCEL_ACCESS_TOKEN or VERCEL_TOKEN is required")
    if args.command == "bootstrap":
        bootstrap(token, args.env_file)
    else:
        if not args.revision:
            raise VercelError("--revision is required for deploy")
        deploy(token, args.revision, ref=args.ref, env_file=args.env_file)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VercelError as exc:
        print(f"vercel deployment error: {exc}", file=sys.stderr)
        raise SystemExit(1)

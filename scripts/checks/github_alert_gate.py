#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def run_command(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )


def detect_repo() -> str:
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]

    result = run_command(["git", "-C", str(REPO_ROOT), "remote", "get-url", "origin"])
    if result.returncode != 0:
        raise RuntimeError(f"unable to determine origin remote: {result.stderr.strip()}")

    remote = result.stdout.strip()
    for pattern in (
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
        r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
    ):
        match = re.search(pattern, remote)
        if match:
            return f"{match.group('owner')}/{match.group('repo')}"
    raise RuntimeError(f"unsupported origin remote format: {remote}")


def detect_code_ref() -> str | None:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    ref = os.environ.get("GITHUB_REF", "").strip()
    if event_name == "pull_request" and ref.startswith("refs/pull/"):
        return ref
    if ref.startswith("refs/heads/") or ref.startswith("refs/tags/"):
        return ref

    result = run_command(["git", "-C", str(REPO_ROOT), "rev-parse", "--abbrev-ref", "HEAD"])
    if result.returncode == 0:
        branch = result.stdout.strip()
        if branch and branch != "HEAD":
            return f"refs/heads/{branch}"
    return None


def gh_api_json(path: str) -> Any:
    result = run_command(["gh", "api", "--paginate", path], cwd=REPO_ROOT)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"gh api failed: {path}"
        raise RuntimeError(message)
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON from gh api {path}: {exc}") from exc


def list_open_code_alerts(repo: str, ref: str | None) -> list[dict[str, Any]]:
    path = f"repos/{repo}/code-scanning/alerts?state=open&per_page=100"
    if ref:
        path += f"&ref={ref}"
    try:
        data = gh_api_json(path)
    except RuntimeError as exc:
        message = str(exc).lower()
        # Local feature branches may not have a GitHub-side analysis result yet.
        if ref and ("no commit found for the ref" in message or "404" in message or "no analysis found" in message):
            return []
        if (
            os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
            and "resource not accessible by integration" in message
        ):
            print("code-scanning alerts unavailable to workflow integration token on pull_request; skipping remote code alert query")
            return []
        raise
    alerts = data if isinstance(data, list) else []
    filtered: list[dict[str, Any]] = []
    for alert in alerts:
        state = (alert.get("state") or "").lower()
        instance_state = ((alert.get("most_recent_instance") or {}).get("state") or "").lower()
        if state == "open" or instance_state == "open":
            filtered.append(alert)
    return filtered


def list_open_secret_alerts(repo: str) -> list[dict[str, Any]]:
    path = f"repos/{repo}/secret-scanning/alerts?state=open&per_page=100"
    try:
        data = gh_api_json(path)
    except RuntimeError as exc:
        message = str(exc).lower()
        if os.environ.get("GITHUB_ACTIONS") == "true" and "resource not accessible by integration" in message:
            print("secret-scanning alerts unavailable to workflow integration token; skipping remote secret alert query")
            return []
        raise
    return data if isinstance(data, list) else []


def main() -> int:
    try:
        repo = detect_repo()
        ref = detect_code_ref()
        code_alerts = list_open_code_alerts(repo, ref)
        secret_alerts = list_open_secret_alerts(repo)
    except RuntimeError as exc:
        print(f"github alert gate failed: {exc}", file=sys.stderr)
        return 1

    print(f"repo={repo}")
    print(f"code_ref={ref or 'default-branch'}")
    print(f"code-scanning: {len(code_alerts)} open")
    print(f"secret-scanning: {len(secret_alerts)} open")

    if code_alerts or secret_alerts:
        print("github alert gate failed: open GitHub security alerts remain", file=sys.stderr)
        return 1
    print("github alert gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

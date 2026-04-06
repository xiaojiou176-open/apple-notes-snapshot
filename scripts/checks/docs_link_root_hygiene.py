#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {
    ".git",
    ".venv",
    ".runtime-cache",
    ".agents",
    ".agent",
    ".codex",
    ".claude",
    ".serena",
    "vendor",
}
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HTML_LINK_RE = re.compile(r"""(?:href|src)=["']([^"']+)["']""")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

REQUIRED_ROOT_ENTRIES = (
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "AGENTS.md",
    "LICENSE",
    ".env.example",
    ".github",
    ".pre-commit-config.yaml",
    "pytest.ini",
    "requirements-dev.txt",
    "config",
    "scripts",
    "tests",
    "vendor",
    "web",
    "docs",
    "notesctl",
)

REQUIRED_TRACKED_PATHS = (
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "AGENTS.md",
    "LICENSE",
    ".env.example",
    ".pre-commit-config.yaml",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/trusted-ci.yml",
    ".github/ISSUE_TEMPLATE/security-contact-request.yml",
    "docs/index.html",
    "docs/quickstart/index.html",
    "docs/compare/index.html",
    "docs/faq/index.html",
    "docs/security/index.html",
    "docs/for-agents/public-skills/index.html",
    "docs/styles.css",
    "docs/media/30-second-overview/index.html",
    "docs/media/founder-note/index.html",
    "docs/.well-known/security.txt",
    "examples/public-skills/README.md",
    "examples/public-skills/repo-truthful-positioning.md",
    "examples/public-skills/agent-surfaces-contracts.md",
    "examples/public-skills/runtime-resource-hygiene.md",
)

FORBIDDEN_ROOT_ENTRIES = (
    "apps",
    "launchd",
    "README.zh-CN.md",
)

FORBIDDEN_TRACKED_PREFIXES = (
    ".agents/",
    ".agent/",
    ".codex/",
    ".claude/",
    ".serena/",
    ".runtime-cache/",
    "generated/launchd/",
    "logs/",
    "log/",
)

DOC_SURFACE_PATHS = (
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "AGENTS.md",
    ".env.example",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/security-contact-request.yml",
    "docs/index.html",
    "docs/quickstart/index.html",
    "docs/compare/index.html",
    "docs/faq/index.html",
    "docs/security/index.html",
    "docs/for-agents/public-skills/index.html",
    "docs/media/30-second-overview/index.html",
    "docs/media/founder-note/index.html",
    "examples/public-skills/README.md",
    "examples/public-skills/repo-truthful-positioning.md",
    "examples/public-skills/agent-surfaces-contracts.md",
    "examples/public-skills/runtime-resource-hygiene.md",
)

AGENTS_REQUIRED_PHRASES = (
    "## Execution hygiene",
    "Chrome / Chromium",
    "more than 6 Chrome/Chromium instances",
    "GitHub repo collaboration writes are allowed only",
    "Every non-GitHub external control plane stays read-only",
)


def iter_markdown_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*.md"):
        rel = path.relative_to(REPO_ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        files.append(path)
    return sorted(files)


def iter_html_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*.html"):
        rel = path.relative_to(REPO_ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        files.append(path)
    return sorted(files)


def extract_links(text: str) -> list[str]:
    links: list[str] = []
    for raw_target in MARKDOWN_LINK_RE.findall(text):
        target = raw_target.strip()
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        if " " in target and not target.startswith(("http://", "https://")):
            target = target.split(" ", 1)[0]
        links.append(target)
    return links


def is_external_link(target: str) -> bool:
    parsed = urlparse(target)
    return parsed.scheme in {"http", "https", "mailto", "tel"}


def validate_markdown_links() -> list[str]:
    failures: list[str] = []
    repo_root_real = REPO_ROOT.resolve()
    for path in iter_markdown_files():
        text = path.read_text(encoding="utf-8")
        for target in extract_links(text):
            if not target or target.startswith("#") or is_external_link(target):
                continue
            clean_target = unquote(target.split("#", 1)[0])
            candidate = (path.parent / clean_target).resolve(strict=False)
            try:
                candidate.relative_to(repo_root_real)
            except ValueError:
                failures.append(
                    f"{path.relative_to(REPO_ROOT)}: link escapes repo root -> {target}"
                )
                continue
            if not candidate.exists():
                failures.append(
                    f"{path.relative_to(REPO_ROOT)}: missing link target -> {target}"
                )
    return failures


def extract_html_links(text: str) -> list[str]:
    return [target.strip() for target in HTML_LINK_RE.findall(text)]


def validate_html_links() -> list[str]:
    failures: list[str] = []
    repo_root_real = REPO_ROOT.resolve()
    for path in iter_html_files():
        text = path.read_text(encoding="utf-8")
        for target in extract_html_links(text):
            if (
                not target
                or target.startswith("#")
                or target.startswith("data:")
                or is_external_link(target)
            ):
                continue
            clean_target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            candidate = (path.parent / clean_target).resolve(strict=False)
            try:
                candidate.relative_to(repo_root_real)
            except ValueError:
                failures.append(
                    f"{path.relative_to(REPO_ROOT)}: html link escapes repo root -> {target}"
                )
                continue
            if not candidate.exists():
                failures.append(
                    f"{path.relative_to(REPO_ROOT)}: missing html link target -> {target}"
                )
    return failures


def validate_root_hygiene() -> list[str]:
    failures: list[str] = []
    for entry in REQUIRED_ROOT_ENTRIES:
        if not (REPO_ROOT / entry).exists():
            failures.append(f"missing root entry: {entry}")
    for entry in FORBIDDEN_ROOT_ENTRIES:
        if (REPO_ROOT / entry).exists():
            failures.append(f"forbidden legacy root entry present: {entry}")
    return failures


def is_git_repo() -> bool:
    return (REPO_ROOT / ".git").exists()


def sanitized_git_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_PREFIX",
    ):
        env.pop(name, None)
    return env


def list_tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=False,
        env=sanitized_git_env(),
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def validate_tracked_public_surface() -> list[str]:
    if not is_git_repo():
        return []

    failures: list[str] = []
    for rel_path in REQUIRED_TRACKED_PATHS:
        target = REPO_ROOT / rel_path
        if not target.exists():
            failures.append(f"missing tracked public surface entry: {rel_path}")
            continue
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", rel_path],
            capture_output=True,
            text=True,
            check=False,
            env=sanitized_git_env(),
        )
        if result.returncode != 0:
            failures.append(f"public surface entry not tracked by git: {rel_path}")
    return failures


def validate_forbidden_tracked_paths() -> list[str]:
    if not is_git_repo():
        return []

    failures: list[str] = []
    for rel_path in list_tracked_paths():
        if rel_path.endswith(".log") or ".log." in rel_path:
            failures.append(f"forbidden tracked log artifact: {rel_path}")
            continue
        if any(rel_path.startswith(prefix) for prefix in FORBIDDEN_TRACKED_PREFIXES):
            failures.append(f"forbidden tracked runtime/ai surface: {rel_path}")
    return failures


def validate_english_doc_surface() -> list[str]:
    failures: list[str] = []
    for rel_path in DOC_SURFACE_PATHS:
        target = REPO_ROOT / rel_path
        if not target.exists():
            continue
        text = target.read_text(encoding="utf-8")
        if CJK_RE.search(text):
            failures.append(f"non-English text found in repo-owned doc surface: {rel_path}")
    return failures


def validate_agents_contract() -> list[str]:
    target = REPO_ROOT / "AGENTS.md"
    if not target.exists():
        return ["missing tracked public surface entry: AGENTS.md"]

    text = target.read_text(encoding="utf-8")
    failures: list[str] = []
    for phrase in AGENTS_REQUIRED_PHRASES:
        if phrase not in text:
            failures.append(f"AGENTS.md missing required contract phrase: {phrase}")
    return failures


def main() -> int:
    failures = validate_root_hygiene()
    failures.extend(validate_tracked_public_surface())
    failures.extend(validate_forbidden_tracked_paths())
    failures.extend(validate_english_doc_surface())
    failures.extend(validate_agents_contract())
    failures.extend(validate_markdown_links())
    failures.extend(validate_html_links())
    if failures:
        print("repo surface hygiene check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1
    print("repo surface hygiene check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = (
    REPO_ROOT / ".github",
    REPO_ROOT / "config",
    REPO_ROOT / "docs",
    REPO_ROOT / "examples",
    REPO_ROOT / "scripts",
    REPO_ROOT / "web",
)
SCAN_FILES = (
    REPO_ROOT / "notesctl",
    REPO_ROOT / "README.md",
    REPO_ROOT / "CHANGELOG.md",
    REPO_ROOT / "CONTRIBUTING.md",
    REPO_ROOT / "SECURITY.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / ".env.example",
    REPO_ROOT / "pytest.ini",
    REPO_ROOT / "requirements-dev.txt",
)

BANNED_SNIPPETS = tuple(
    "".join(parts)
    for parts in (
        ("/", "Users", "/"),
        ("Useful", "_", "Tools"),
        ("Notes", "Sync"),
    )
)

BANNED_PATTERNS = (
    re.compile(r"\bcom\.(?!yourname\b)[A-Za-z0-9_-]+\.apple-notes-snapshot(?:\.webui)?\b"),
)

TEXT_EXTENSIONS = {
    ".env",
    ".html",
    ".ini",
    ".json",
    ".jsonc",
    ".js",
    ".md",
    ".py",
    ".sh",
    ".txt",
    ".yaml",
    ".yml",
    ".zsh",
}


def should_scan(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT)
    if rel.parts[:2] == ("scripts", "checks"):
        return False
    if path.name.startswith(".") and path.suffix not in TEXT_EXTENSIONS:
        return False
    return path.is_file() and (path.suffix in TEXT_EXTENSIONS or not path.suffix)


def iter_scan_targets() -> list[Path]:
    targets: set[Path] = set()
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if should_scan(path):
                targets.add(path)
    for path in SCAN_FILES:
        if should_scan(path):
            targets.add(path)
    return sorted(targets)


def main() -> int:
    failures: list[str] = []
    for path in iter_scan_targets():
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            for banned in BANNED_SNIPPETS:
                if banned in line:
                    failures.append(
                        f"{path.relative_to(REPO_ROOT)}:{line_number}: banned legacy path snippet '{banned}'"
                    )
            for pattern in BANNED_PATTERNS:
                if pattern.search(line):
                    failures.append(
                        f"{path.relative_to(REPO_ROOT)}:{line_number}: banned personal namespace '{line.strip()}'"
                    )
    if failures:
        print("legacy path scan failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1
    print("legacy path scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

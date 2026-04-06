#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
USER_ROOT = "/".join(("", "Users", ""))
PRIVATE_VAR_FOLDERS = "/".join(("", "private", "var", "folders"))
CACHE_ROOT = "~/" + ".cache" + "/apple-notes-snapshot"
LEGACY_SUPPORT_ROOT = "~/Library/" + "Application Support" + "/AppleNotesSnapshot"
LEGACY_SUPPORT_ALT_ROOT = "~/Library/" + "ApplicationSupport" + "/AppleNotesSnapshot"
LEGACY_CACHE_ROOT = "~/Library/" + "Caches" + "/AppleNotesSnapshot"
DEFAULT_CHROME_ROOT = "~/Library/" + "Application Support" + "/Google/Chrome"
APPLE_NOTES_CONTAINER = ".".join(("group", "com", "apple", "notes"))
APPLE_NOTES_DB = "NoteStore" + ".sqlite"
LAUNCHD_NAMESPACE_SUFFIX = "." + "apple-notes-snapshot"
SCAN_DIRS = (
    REPO_ROOT / ".claude-plugin",
    REPO_ROOT / ".codex-plugin",
    REPO_ROOT / "docs",
    REPO_ROOT / "examples",
    REPO_ROOT / "plugins",
)
SCAN_FILES = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "CHANGELOG.md",
    REPO_ROOT / "CONTRIBUTING.md",
    REPO_ROOT / "SECURITY.md",
    REPO_ROOT / "SUPPORT.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / ".env.example",
    REPO_ROOT / "config" / "notes_snapshot.env",
    REPO_ROOT / "scripts" / "cmd" / "ops.zsh",
)

TEXT_EXTENSIONS = {
    ".env",
    ".example",
    ".html",
    ".json",
    ".jsonc",
    ".md",
    ".sh",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
    ".zsh",
}

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
RULES = (
    ("absolute user path", re.compile(re.escape(USER_ROOT) + r"[^\s`\"'<>]+")),
    (
        "private var folders path",
        re.compile(re.escape(PRIVATE_VAR_FOLDERS) + r"(?:/[^\s`\"'<>]+)?"),
    ),
    ("machine cache root", re.compile(re.escape(CACHE_ROOT) + r"(?:/[^\s`\"'<>]+)?")),
    (
        "legacy AppleNotesSnapshot support root",
        re.compile(re.escape(LEGACY_SUPPORT_ROOT) + r"(?:/[^\s`\"'<>]+)?"),
    ),
    (
        "legacy AppleNotesSnapshot alternate support root",
        re.compile(re.escape(LEGACY_SUPPORT_ALT_ROOT) + r"(?:/[^\s`\"'<>]+)?"),
    ),
    (
        "legacy AppleNotesSnapshot cache root",
        re.compile(re.escape(LEGACY_CACHE_ROOT) + r"(?:/[^\s`\"'<>]+)?"),
    ),
    (
        "default Chrome root",
        re.compile(re.escape(DEFAULT_CHROME_ROOT) + r"(?:/[^\s`\"'<>]+)?"),
    ),
    ("Apple Notes private container", re.compile(re.escape(APPLE_NOTES_CONTAINER))),
    ("Apple Notes private database", re.compile(re.escape(APPLE_NOTES_DB))),
    (
        "personal launchd namespace",
        re.compile(
            r"\bcom\.(?!yourname\b)[A-Za-z0-9_-]+"
            + re.escape(LAUNCHD_NAMESPACE_SUFFIX)
            + r"(?:\.webui)?\b"
        ),
    ),
)


def should_scan(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.name.startswith(".") and path.name not in {".env.example"}:
        return False
    return path.suffix in TEXT_EXTENSIONS or path.name.endswith(".env.example")


def iter_scan_targets() -> list[Path]:
    targets: set[Path] = set()
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if should_scan(path):
                targets.add(path)
    for path in SCAN_FILES:
        if path.exists() and should_scan(path):
            targets.add(path)
    return sorted(targets)


def email_allowed(value: str) -> bool:
    value = value.lower()
    return value.endswith("@example.com")


def main() -> int:
    failures: list[str] = []
    for path in iter_scan_targets():
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            for label, pattern in RULES:
                if pattern.search(line):
                    failures.append(
                        f"{path.relative_to(REPO_ROOT)}:{line_number}: banned {label} -> {line.strip()}"
                    )
            for match in EMAIL_RE.findall(line):
                if not email_allowed(match):
                    failures.append(
                        f"{path.relative_to(REPO_ROOT)}:{line_number}: banned public email -> {match}"
                    )
    if failures:
        print("public surface sensitive scan failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1
    print("public surface sensitive scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

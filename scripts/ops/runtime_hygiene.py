#!/usr/bin/env python3
from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path


DEFAULT_RETENTION_HOURS = 72
DEFAULT_BROWSER_RETENTION_HOURS = 24
DEFAULT_EXTERNAL_CACHE_MAX_BYTES = 2 * 1024 * 1024 * 1024


def path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def format_mtime(epoch: int | None) -> str:
    if epoch is None:
        return ""
    return datetime.fromtimestamp(epoch).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def size_bytes(path: Path) -> int:
    if not path_exists(path):
        return 0
    try:
        stat_result = path.lstat()
    except OSError:
        return 0

    if path.is_symlink():
        return stat_result.st_size
    if path.is_file():
        return stat_result.st_size

    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            children = list(current.iterdir())
        except OSError:
            continue
        for child in children:
            try:
                child_stat = child.lstat()
            except OSError:
                continue
            if child.is_symlink():
                total += child_stat.st_size
            elif child.is_file():
                total += child_stat.st_size
            elif child.is_dir():
                stack.append(child)
            else:
                total += child_stat.st_size
    return total


def current_labels(values: list[str]) -> list[str]:
    labels: list[str] = []
    seen = set()
    for value in values:
        if not value or value in seen:
            continue
        labels.append(value)
        seen.add(value)
    return labels


def repo_local_entries(repo_root: Path) -> list[dict]:
    surfaces = [
        ("repo-local-rebuildable-env", repo_root / ".runtime-cache" / "dev" / "venv"),
        ("repo-local-runtime-cache", repo_root / ".runtime-cache" / "cache" / "apple-notes-snapshot"),
        ("repo-local-scratch", repo_root / ".runtime-cache" / "temp"),
        ("repo-local-logs", repo_root / ".runtime-cache" / "logs"),
        ("repo-local-pytest-cache", repo_root / ".runtime-cache" / "pytest"),
        ("repo-local-coverage", repo_root / ".runtime-cache" / "coverage"),
        ("repo-local-pycache", repo_root / ".runtime-cache" / "pycache"),
        ("legacy-pytest-cache", repo_root / ".pytest_cache"),
        ("legacy-coverage", repo_root / ".coverage"),
        ("legacy-dot-venv", repo_root / ".venv"),
        ("legacy-tests-pycache", repo_root / "tests" / "__pycache__"),
        ("legacy-unit-pycache", repo_root / "tests" / "unit" / "__pycache__"),
        ("legacy-e2e-pycache", repo_root / "tests" / "e2e" / "__pycache__"),
        ("legacy-ops-pycache", repo_root / "scripts" / "ops" / "__pycache__"),
    ]
    entries = []
    for class_name, path in surfaces:
        exists = path_exists(path)
        mtime_epoch = None
        if exists:
            try:
                mtime_epoch = int(path.lstat().st_mtime)
            except OSError:
                mtime_epoch = None
        entries.append(
            {
                "class": class_name,
                "path": str(path),
                "exists": exists,
                "bytes": size_bytes(path),
                "mtime_epoch": mtime_epoch,
                "mtime": format_mtime(mtime_epoch),
            }
        )
    return entries


def build_missing_entry(kind: str, class_name: str, path: Path, root_set: str) -> dict:
    return {
        "class": class_name,
        "kind": kind,
        "label": "",
        "path": str(path),
        "bytes": 0,
        "mtime_epoch": None,
        "mtime": "",
        "is_current": False,
        "stale": False,
        "root_set": root_set,
        "action": "missing",
        "reason": "root_missing",
    }


def build_surface_entry(
    *,
    kind: str,
    class_name: str,
    path: Path,
    label: str,
    current: bool,
    cutoff_epoch: int,
    root_set: str,
    extra: dict | None = None,
) -> dict:
    mtime_epoch = None
    try:
        mtime_epoch = int(path.lstat().st_mtime)
    except OSError:
        mtime_epoch = None

    stale = False
    if not current and mtime_epoch is not None:
        stale = mtime_epoch <= cutoff_epoch

    if current:
        action = "skip_current"
        reason = "current_label_protected"
    elif stale:
        action = "would_remove"
        reason = "older_than_retention_window"
    else:
        action = "skip_recent"
        reason = "within_retention_window"

    entry = {
        "class": class_name,
        "kind": kind,
        "label": label,
        "path": str(path),
        "bytes": size_bytes(path),
        "mtime_epoch": mtime_epoch,
        "mtime": format_mtime(mtime_epoch),
        "is_current": current,
        "stale": stale,
        "root_set": root_set,
        "action": action,
        "reason": reason,
    }
    if extra:
        entry.update(extra)
    return entry


def build_protected_entry(
    *,
    kind: str,
    class_name: str,
    path: Path,
    root_set: str,
    reason: str,
) -> dict:
    mtime_epoch = None
    try:
        mtime_epoch = int(path.lstat().st_mtime)
    except OSError:
        mtime_epoch = None

    return {
        "class": class_name,
        "kind": kind,
        "label": path.name,
        "path": str(path),
        "bytes": 0,
        "mtime_epoch": mtime_epoch,
        "mtime": format_mtime(mtime_epoch),
        "is_current": False,
        "stale": False,
        "root_set": root_set,
        "action": "skip_protected",
        "reason": reason,
        "budget_eligible": False,
        "cleanup_excluded": True,
    }


def scan_root(
    *,
    kind: str,
    class_name: str,
    root: Path,
    active_labels: list[str],
    cutoff_epoch: int,
    root_set: str,
    extra_factory=None,
) -> list[dict]:
    if not path_exists(root):
        return [build_missing_entry(kind, class_name, root, root_set)]

    try:
        children = sorted(root.iterdir(), key=lambda item: item.name)
    except OSError:
        entry = build_missing_entry(kind, class_name, root, root_set)
        entry["reason"] = "root_unreadable"
        return [entry]

    entries = []
    for child in children:
        if not path_exists(child):
            continue
        extra = extra_factory(child) if extra_factory else None
        entries.append(
            build_surface_entry(
                kind=kind,
                class_name=class_name,
                path=child,
                label=child.name,
                current=child.name in active_labels,
                cutoff_epoch=cutoff_epoch,
                root_set=root_set,
                extra=extra,
            )
        )
    return entries


def conditional_vendor_entry(
    vendor_runtime_root: Path,
    *,
    cutoff_epoch: int,
    include_vendor_runtime: bool,
    root_set: str,
) -> dict:
    current_path = vendor_runtime_root / "current"
    if not path_exists(current_path):
        return {
            "class": "external-vendor-runtime",
            "kind": "vendor-runtime-current",
            "label": "current",
            "path": str(current_path),
            "bytes": 0,
            "mtime_epoch": None,
            "mtime": "",
            "is_current": False,
            "stale": False,
            "root_set": root_set,
            "action": "missing",
            "reason": "path_missing",
            "eligible_only_with_include_vendor_runtime": True,
        }

    try:
        mtime_epoch = int(current_path.lstat().st_mtime)
    except OSError:
        mtime_epoch = None

    stale = mtime_epoch is not None and mtime_epoch <= cutoff_epoch
    if mtime_epoch is None:
        action = "skip_recent"
        reason = "metadata_unreadable"
    elif include_vendor_runtime:
        action = "would_remove" if stale else "skip_recent"
        reason = "older_than_retention_window" if stale else "within_retention_window"
    else:
        action = "skip_recent"
        reason = "opt_in_required"

    return {
        "class": "external-vendor-runtime",
        "kind": "vendor-runtime-current",
        "label": "current",
        "path": str(current_path),
        "bytes": size_bytes(current_path),
        "mtime_epoch": mtime_epoch,
        "mtime": format_mtime(mtime_epoch),
        "is_current": False,
        "stale": stale,
        "root_set": root_set,
        "action": action,
        "reason": reason,
        "eligible_only_with_include_vendor_runtime": True,
        "budget_eligible": include_vendor_runtime,
    }


def mark_external_budget(entries: list[dict], max_external_bytes: int) -> tuple[list[dict], int]:
    total_bytes = sum(
        entry["bytes"]
        for entry in entries
        if entry["action"] != "missing"
    )
    if total_bytes <= max_external_bytes:
        return entries, total_bytes

    removable = [
        entry
        for entry in entries
        if entry["action"] == "skip_recent"
        and not entry.get("is_current", False)
        and entry.get("budget_eligible", True)
    ]
    removable.sort(key=lambda item: (item.get("mtime_epoch") or 0, item["bytes"]))

    current_total = total_bytes
    for entry in removable:
        if current_total <= max_external_bytes:
            break
        entry["action"] = "would_remove"
        entry["reason"] = "over_external_budget"
        current_total -= entry["bytes"]

    return entries, total_bytes


def build_report(
    *,
    repo_root: str,
    launchd_root: str,
    runtime_root: str,
    repos_root: str,
    legacy_launchd_root: str,
    legacy_runtime_root: str,
    legacy_repos_root: str,
    vendor_runtime_root: str,
    legacy_vendor_runtime_root: str,
    browser_root: str,
    browser_user_data_root: str,
    browser_temp_root: str,
    active_labels: list[str],
    retention_hours: int = DEFAULT_RETENTION_HOURS,
    browser_retention_hours: int = DEFAULT_BROWSER_RETENTION_HOURS,
    max_external_bytes: int = DEFAULT_EXTERNAL_CACHE_MAX_BYTES,
    include_vendor_runtime: bool = False,
    now_epoch: int | None = None,
) -> dict:
    now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
    cutoff_epoch = now_epoch - (int(retention_hours) * 3600)
    browser_cutoff_epoch = now_epoch - (int(browser_retention_hours) * 3600)
    labels = current_labels(active_labels)

    external_entries = []
    external_entries.extend(
        scan_root(
            kind="launchd",
            class_name="external-launchd",
            root=Path(launchd_root),
            active_labels=labels,
            cutoff_epoch=cutoff_epoch,
            root_set="current",
        )
    )
    external_entries.extend(
        scan_root(
            kind="runtime",
            class_name="external-runtime",
            root=Path(runtime_root),
            active_labels=labels,
            cutoff_epoch=cutoff_epoch,
            root_set="current",
        )
    )
    external_entries.extend(
        scan_root(
            kind="repos",
            class_name="external-repo-copy",
            root=Path(repos_root),
            active_labels=labels,
            cutoff_epoch=cutoff_epoch,
            root_set="current",
            extra_factory=lambda child: {
                "legacy_link_path": str(Path(legacy_launchd_root).parent / "repos" / child.name),
            },
        )
    )
    external_entries.extend(
        scan_root(
            kind="browser-temp",
            class_name="external-browser-temp",
            root=Path(browser_temp_root),
            active_labels=[],
            cutoff_epoch=browser_cutoff_epoch,
            root_set="current",
        )
    )
    persistent_browser_entries = []
    browser_user_data_path = Path(browser_user_data_root)
    if path_exists(browser_user_data_path):
        persistent_browser_entries.append(
            build_protected_entry(
                kind="browser-user-data",
                class_name="external-browser-user-data",
                path=browser_user_data_path,
                root_set="current",
                reason="persistent_browser_root_excluded",
            )
        )
    else:
        persistent_browser_entries.append(
            build_missing_entry(
                "browser-user-data",
                "external-browser-user-data",
                browser_user_data_path,
                "current",
            )
        )

    legacy_entries = []
    legacy_entries.extend(
        scan_root(
            kind="launchd",
            class_name="legacy-launchd",
            root=Path(legacy_launchd_root),
            active_labels=labels,
            cutoff_epoch=cutoff_epoch,
            root_set="legacy",
        )
    )
    legacy_entries.extend(
        scan_root(
            kind="runtime",
            class_name="legacy-runtime",
            root=Path(legacy_runtime_root),
            active_labels=labels,
            cutoff_epoch=cutoff_epoch,
            root_set="legacy",
        )
    )
    legacy_entries.extend(
        scan_root(
            kind="repos",
            class_name="legacy-repo-copy",
            root=Path(legacy_repos_root),
            active_labels=labels,
            cutoff_epoch=cutoff_epoch,
            root_set="legacy",
        )
    )

    conditional_paths = [
        conditional_vendor_entry(
            Path(vendor_runtime_root),
            cutoff_epoch=cutoff_epoch,
            include_vendor_runtime=include_vendor_runtime,
            root_set="current",
        ),
        conditional_vendor_entry(
            Path(legacy_vendor_runtime_root),
            cutoff_epoch=cutoff_epoch,
            include_vendor_runtime=include_vendor_runtime,
            root_set="legacy",
        ),
    ]

    budget_entries, total_external_bytes = mark_external_budget(
        external_entries
        + legacy_entries
        + ([entry for entry in conditional_paths if include_vendor_runtime and entry["action"] != "missing"]),
        max_external_bytes=max_external_bytes,
    )
    # mark_external_budget mutates in place; split back for readability.
    external_entries = [
        entry
        for entry in budget_entries
        if entry["root_set"] == "current" and entry["kind"] != "vendor-runtime-current"
    ]
    legacy_entries = [
        entry
        for entry in budget_entries
        if entry["root_set"] == "legacy" and entry["kind"] != "vendor-runtime-current"
    ]

    return {
        "repo_root": repo_root,
        "generated_at_epoch": now_epoch,
        "retention_hours": int(retention_hours),
        "browser_retention_hours": int(browser_retention_hours),
        "external_cache_max_bytes": int(max_external_bytes),
        "current_labels": labels,
        "repo_local": repo_local_entries(Path(repo_root)),
        "external_cache": {
            "roots": {
                "launchd_root": launchd_root,
                "runtime_root": runtime_root,
                "repos_root": repos_root,
                "browser_root": browser_root,
                "browser_user_data_root": browser_user_data_root,
                "browser_temp_root": browser_temp_root,
                "vendor_runtime_root": vendor_runtime_root,
            },
            "legacy_roots": {
                "launchd_root": legacy_launchd_root,
                "runtime_root": legacy_runtime_root,
                "repos_root": legacy_repos_root,
                "vendor_runtime_root": legacy_vendor_runtime_root,
            },
            "total_bytes_before_cleanup": total_external_bytes,
            "entries": external_entries,
            "legacy_entries": legacy_entries,
            "persistent_entries": persistent_browser_entries,
        },
        "conditional_paths": conditional_paths,
        "cleanup_contract": {
            "repo_local_cleanup_available": True,
            "external_cache_cleanup_available": True,
            "persistent_browser_root_cleanup_available": False,
            "docker_cleanup_available": False,
            "var_folders_cleanup_available": False,
            "shared_tool_cleanup_available": False,
        },
    }


def audit_lines(report: dict) -> list[str]:
    lines = [
        "Apple Notes Snapshot runtime-audit",
        f"repo_root={report['repo_root']}",
        f"retention_hours={report['retention_hours']}",
        f"browser_retention_hours={report['browser_retention_hours']}",
        f"external_cache_max_bytes={report['external_cache_max_bytes']}",
        f"current_labels={','.join(report['current_labels']) or '(none)'}",
        "",
        "repo_local:",
    ]
    for entry in report["repo_local"]:
        lines.append(
            "  - "
            + " ".join(
                [
                    f"class={entry['class']}",
                    f"path={entry['path']}",
                    f"exists={'true' if entry['exists'] else 'false'}",
                    f"bytes={entry['bytes']}",
                    f"mtime={entry['mtime'] or '(missing)'}",
                ]
            )
        )

    roots = report["external_cache"]["roots"]
    legacy_roots = report["external_cache"]["legacy_roots"]
    lines.extend(
        [
            "",
            "external_cache_roots:",
            f"  - launchd_root={roots['launchd_root']}",
            f"  - runtime_root={roots['runtime_root']}",
            f"  - repos_root={roots['repos_root']}",
            f"  - browser_root={roots['browser_root']}",
            f"  - browser_user_data_root={roots['browser_user_data_root']}",
            f"  - browser_temp_root={roots['browser_temp_root']}",
            f"  - vendor_runtime_root={roots['vendor_runtime_root']}",
            "legacy_external_roots:",
            f"  - launchd_root={legacy_roots['launchd_root']}",
            f"  - runtime_root={legacy_roots['runtime_root']}",
            f"  - repos_root={legacy_roots['repos_root']}",
            f"  - vendor_runtime_root={legacy_roots['vendor_runtime_root']}",
            f"external_cache_total_bytes_before_cleanup={report['external_cache']['total_bytes_before_cleanup']}",
            "",
            "external_entries:",
        ]
    )
    if report["external_cache"]["persistent_entries"]:
        lines.append("persistent_external_entries:")
        for entry in report["external_cache"]["persistent_entries"]:
            lines.append(
                "  - "
                + " ".join(
                    [
                        f"class={entry['class']}",
                        f"kind={entry['kind']}",
                        f"path={entry['path']}",
                        f"bytes={entry['bytes']}",
                        f"mtime={entry['mtime'] or '(missing)'}",
                        f"reason={entry['reason']}",
                        f"action={entry['action']}",
                    ]
                )
            )
    for bucket in ("entries", "legacy_entries"):
        if bucket == "legacy_entries":
            lines.append("legacy_external_entries:")
        for entry in report["external_cache"][bucket]:
            lines.append(
                "  - "
                + " ".join(
                    [
                        f"class={entry['class']}",
                        f"kind={entry['kind']}",
                        f"label={entry['label'] or '(root)'}",
                        f"path={entry['path']}",
                        f"bytes={entry['bytes']}",
                        f"mtime={entry['mtime'] or '(missing)'}",
                        f"is_current={'true' if entry['is_current'] else 'false'}",
                        f"stale={'true' if entry['stale'] else 'false'}",
                        f"reason={entry['reason']}",
                        f"action={entry['action']}",
                    ]
                )
            )

    lines.extend(["", "conditional_paths:"])
    for entry in report["conditional_paths"]:
        lines.append(
            "  - "
            + " ".join(
                [
                    f"class={entry['class']}",
                    f"path={entry['path']}",
                    f"bytes={entry['bytes']}",
                    f"mtime={entry['mtime'] or '(missing)'}",
                    f"root_set={entry['root_set']}",
                    f"reason={entry['reason']}",
                    f"action={entry['action']}",
                    "eligible_only_with_include_vendor_runtime=true",
                ]
            )
        )

    contract = report["cleanup_contract"]
    lines.extend(
        [
            "",
            "cleanup_contract:",
            f"  - repo_local_cleanup_available={'true' if contract['repo_local_cleanup_available'] else 'false'}",
            f"  - external_cache_cleanup_available={'true' if contract['external_cache_cleanup_available'] else 'false'}",
            f"  - persistent_browser_root_cleanup_available={'true' if contract['persistent_browser_root_cleanup_available'] else 'false'}",
            f"  - docker_cleanup_available={'true' if contract['docker_cleanup_available'] else 'false'}",
            f"  - var_folders_cleanup_available={'true' if contract['var_folders_cleanup_available'] else 'false'}",
            f"  - shared_tool_cleanup_available={'true' if contract['shared_tool_cleanup_available'] else 'false'}",
        ]
    )
    return lines


def cleanup_entries(report: dict, include_vendor_runtime: bool) -> list[dict]:
    entries = list(report["external_cache"]["entries"]) + list(report["external_cache"]["legacy_entries"])
    if include_vendor_runtime:
        entries.extend(report["conditional_paths"])
    return entries


def cleanup_line(entry: dict) -> str:
    return "[clean-runtime] " + " ".join(
        [
            f"class={entry['class']}",
            f"path={entry['path']}",
            f"label={entry['label'] or '(root)'}",
            f"bytes={entry['bytes']}",
            f"mtime={entry['mtime'] or '(missing)'}",
            f"reason={entry['reason']}",
            f"action={entry['action']}",
        ]
    )


def remove_path(path: Path) -> bool:
    if not path_exists(path):
        return False
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return True
    if path.is_dir():
        shutil.rmtree(path)
        return True
    path.unlink(missing_ok=True)
    return True


def apply_entry(entry: dict, legacy_repos_root: str) -> int:
    removed = 0
    target = Path(entry["path"])
    if remove_path(target):
        removed += 1

    if entry["kind"] == "repos" and entry.get("legacy_link_path"):
        legacy_path = Path(entry["legacy_link_path"])
        if remove_path(legacy_path):
            removed += 1
    elif entry["kind"] == "repos" and entry["root_set"] == "current" and entry["label"]:
        legacy_path = Path(legacy_repos_root) / entry["label"]
        if remove_path(legacy_path):
            removed += 1

    return removed

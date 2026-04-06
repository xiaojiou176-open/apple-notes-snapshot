#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime_hygiene import (
    DEFAULT_BROWSER_RETENTION_HOURS,
    DEFAULT_EXTERNAL_CACHE_MAX_BYTES,
    DEFAULT_RETENTION_HOURS,
    apply_entry,
    build_report,
    cleanup_entries,
    cleanup_line,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or remove stale external repo-owned runtime residue for Apple Notes Snapshot."
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", help="preview the cleanup set without deleting it")
    mode_group.add_argument("--apply", action="store_true", help="delete the current cleanup set (default)")
    parser.add_argument("--retention-hours", type=int, default=DEFAULT_RETENTION_HOURS)
    parser.add_argument("--browser-retention-hours", type=int, default=DEFAULT_BROWSER_RETENTION_HOURS)
    parser.add_argument("--max-external-bytes", type=int, default=DEFAULT_EXTERNAL_CACHE_MAX_BYTES)
    parser.add_argument("--include-vendor-runtime", action="store_true")
    parser.add_argument("--quiet-auto", action="store_true", help="suppress per-entry output for automatic cleanup hooks")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--launchd-root", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--repos-root", required=True)
    parser.add_argument("--legacy-launchd-root", required=True)
    parser.add_argument("--legacy-runtime-root", required=True)
    parser.add_argument("--legacy-repos-root", required=True)
    parser.add_argument("--vendor-runtime-root", required=True)
    parser.add_argument("--legacy-vendor-runtime-root", required=True)
    parser.add_argument("--browser-root", required=True)
    parser.add_argument("--browser-user-data-root", required=True)
    parser.add_argument("--browser-temp-root", required=True)
    parser.add_argument("--current-label", action="append", default=[])
    parser.add_argument("--now-epoch", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mode = "apply" if (args.apply or not args.dry_run) else "dry-run"
    report = build_report(
        repo_root=args.repo_root,
        launchd_root=args.launchd_root,
        runtime_root=args.runtime_root,
        repos_root=args.repos_root,
        legacy_launchd_root=args.legacy_launchd_root,
        legacy_runtime_root=args.legacy_runtime_root,
        legacy_repos_root=args.legacy_repos_root,
        vendor_runtime_root=args.vendor_runtime_root,
        legacy_vendor_runtime_root=args.legacy_vendor_runtime_root,
        browser_root=args.browser_root,
        browser_user_data_root=args.browser_user_data_root,
        browser_temp_root=args.browser_temp_root,
        active_labels=args.current_label,
        retention_hours=args.retention_hours,
        browser_retention_hours=args.browser_retention_hours,
        max_external_bytes=args.max_external_bytes,
        include_vendor_runtime=args.include_vendor_runtime,
        now_epoch=args.now_epoch,
    )

    if not args.quiet_auto:
        print("[clean-runtime] maintainer-only external cleanup lane; repo-local caches still use ./notesctl clean-cache")
        print(
            "[clean-runtime] "
            f"retention_hours={report['retention_hours']} "
            f"browser_retention_hours={report['browser_retention_hours']} "
            f"external_cache_max_bytes={report['external_cache_max_bytes']} "
            f"current_labels={','.join(report['current_labels']) or '(none)'}"
        )

    entries = cleanup_entries(report, include_vendor_runtime=args.include_vendor_runtime)
    missing = 0
    skipped = 0
    removed = 0

    for entry in entries:
        if not args.quiet_auto:
            print(cleanup_line(entry))
        if entry["action"] == "missing":
            missing += 1
        elif entry["action"] == "would_remove":
            if mode == "apply":
                removed += apply_entry(entry, report["external_cache"]["legacy_roots"]["repos_root"])
            else:
                skipped += 1
        else:
            skipped += 1

    if not args.quiet_auto:
        print(f"clean-runtime done (mode={mode}, removed={removed}, skipped={skipped}, missing={missing})")
        print("next: ./notesctl runtime-audit --json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

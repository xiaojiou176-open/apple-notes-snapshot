#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime_hygiene import (
    DEFAULT_BROWSER_RETENTION_HOURS,
    DEFAULT_EXTERNAL_CACHE_MAX_BYTES,
    DEFAULT_RETENTION_HOURS,
    audit_lines,
    build_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect repo-local and external repo-owned runtime residue for Apple Notes Snapshot."
    )
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument("--retention-hours", type=int, default=DEFAULT_RETENTION_HOURS)
    parser.add_argument("--browser-retention-hours", type=int, default=DEFAULT_BROWSER_RETENTION_HOURS)
    parser.add_argument("--max-external-bytes", type=int, default=DEFAULT_EXTERNAL_CACHE_MAX_BYTES)
    parser.add_argument("--include-vendor-runtime", action="store_true")
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
    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    for line in audit_lines(report):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

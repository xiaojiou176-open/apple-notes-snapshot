#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from browser_runtime import (
    LOCK_FILENAMES,
    default_settings_from_env,
    default_root_is_quiet,
    find_profile_dir_by_display_name,
    load_local_state,
    normalize_local_state_for_target,
    remove_lock_files,
    write_local_state,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap the isolated Apple Notes Snapshot Chrome root from the default Chrome user-data dir."
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = default_settings_from_env()
    errors: list[str] = []

    source_root = Path(settings["default_source_user_data_dir"]).expanduser()
    target_root = Path(settings["chrome_user_data_dir"]).expanduser()
    target_profile_dir = settings["chrome_profile_dir"]
    target_profile_path = target_root / target_profile_dir

    if settings["provider"] != "chrome":
        errors.append(f"Unsupported browser provider: {settings['provider']}. This repo only supports real Chrome.")
    if not source_root.exists():
        errors.append(f"Default Chrome user data dir was not found: {source_root}")

    quiet, foreign_processes = default_root_is_quiet(str(source_root))
    if not quiet:
        errors.append(
            "Default Chrome root is not quiet. Close the default-root Chrome instance before bootstrap. "
            + "Evidence: "
            + ", ".join(f"{proc['pid']}:{proc['args']}" for proc in foreign_processes[:10])
        )

    source_local_state_path = source_root / "Local State"
    source_local_state = load_local_state(source_local_state_path)
    if not source_local_state_path.exists():
        errors.append(f"Default Chrome Local State is missing: {source_local_state_path}")
    source_profile_dir = find_profile_dir_by_display_name(source_root, settings["chrome_profile_name"]) if source_root.exists() else None
    if not source_profile_dir:
        errors.append(
            f"Chrome profile named '{settings['chrome_profile_name']}' was not found in {source_root}"
        )

    if target_root.exists() and any(target_root.iterdir()):
        errors.append(f"Target isolated Chrome user data dir is not empty: {target_root}")

    payload = {
        "source_user_data_dir": str(source_root),
        "source_profile_dir": source_profile_dir or "",
        "target_user_data_dir": str(target_root),
        "target_profile_dir": target_profile_dir,
        "removed_lock_files": [],
        "ok": len(errors) == 0,
        "errors": errors,
        "next_launch_command": "./notesctl browser-open",
    }

    if errors:
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("Apple Notes Snapshot browser bootstrap")
            print(f"source_user_data_dir={payload['source_user_data_dir']}")
            print(f"source_profile_dir={payload['source_profile_dir'] or '(unresolved)'}")
            print(f"target_user_data_dir={payload['target_user_data_dir']}")
            print(f"target_profile_dir={payload['target_profile_dir']}")
            print("status=invalid")
            for err in errors:
                print(f"error={err}")
        return 1

    target_root.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source_local_state_path, target_root / "Local State")
    except OSError as exc:
        payload["ok"] = False
        payload["errors"] = [f"Failed to copy default Chrome Local State: {exc}"]
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("Apple Notes Snapshot browser bootstrap")
            print(f"source_user_data_dir={payload['source_user_data_dir']}")
            print(f"target_user_data_dir={payload['target_user_data_dir']}")
            print("status=invalid")
            print(f"error={payload['errors'][0]}")
        return 1
    try:
        shutil.copytree(source_root / source_profile_dir, target_profile_path, dirs_exist_ok=False)
    except OSError as exc:
        payload["ok"] = False
        payload["errors"] = [f"Failed to copy default Chrome Local State or profile: {exc}"]
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print("Apple Notes Snapshot browser bootstrap")
            print(f"source_user_data_dir={payload['source_user_data_dir']}")
            print(f"source_profile_dir={payload['source_profile_dir'] or '(unresolved)'}")
            print(f"target_user_data_dir={payload['target_user_data_dir']}")
            print(f"target_profile_dir={payload['target_profile_dir']}")
            print("status=invalid")
            print(f"error={payload['errors'][0]}")
        return 1

    normalized = normalize_local_state_for_target(
        source_local_state,
        source_profile_dir=source_profile_dir,
        target_profile_dir=target_profile_dir,
        target_profile_name=settings["chrome_profile_name"],
    )
    write_local_state(target_root / "Local State", normalized)
    payload["removed_lock_files"] = remove_lock_files(target_root)
    payload["ok"] = True

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Apple Notes Snapshot browser bootstrap")
        print(f"source_user_data_dir={payload['source_user_data_dir']}")
        print(f"source_profile_dir={payload['source_profile_dir']}")
        print(f"target_user_data_dir={payload['target_user_data_dir']}")
        print(f"target_profile_dir={payload['target_profile_dir']}")
        print(f"removed_lock_files={json.dumps(payload['removed_lock_files'], ensure_ascii=True)}")
        print(f"ignored_runtime_files={json.dumps(sorted(LOCK_FILENAMES), ensure_ascii=True)}")
        print(f"next_launch_command={payload['next_launch_command']}")
        print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

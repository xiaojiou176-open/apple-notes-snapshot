#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from browser_runtime import (
    build_attach_payload,
    cdp_url,
    chrome_binary_for_channel,
    default_settings_from_env,
    find_profile_dir_by_display_name,
    launch_command as browser_launch_command,
    list_chrome_processes,
    probe_cdp,
    process_uses_user_data_dir,
    tcp_listener_present,
)


def resolve_contract_from_env() -> dict:
    settings = default_settings_from_env()
    errors: list[str] = []

    if settings["provider"] != "chrome":
        errors.append(f"Unsupported browser provider: {settings['provider']}. This repo only supports real Chrome.")

    chrome_binary = chrome_binary_for_channel(settings["chrome_channel"])
    if not chrome_binary:
        errors.append(f"Chrome binary for channel '{settings['chrome_channel']}' was not found.")

    user_data_dir = Path(settings["chrome_user_data_dir"])
    if not user_data_dir.exists():
        errors.append(f"Chrome user data dir does not exist: {user_data_dir}")

    target_profile_dir = settings["chrome_profile_dir"]
    target_profile_path = user_data_dir / target_profile_dir
    local_state_path = user_data_dir / "Local State"
    target_profile_by_name = ""
    if user_data_dir.exists():
        target_profile_by_name = find_profile_dir_by_display_name(user_data_dir, settings["chrome_profile_name"]) or ""
        if not local_state_path.exists():
            errors.append(f"Chrome Local State is missing: {local_state_path}")
        if not target_profile_path.exists():
            errors.append(f"Chrome profile dir does not exist: {target_profile_path}")
        if target_profile_by_name and target_profile_by_name != target_profile_dir:
            errors.append(
                "Chrome profile display name resolves to "
                f"'{target_profile_by_name}', but NOTES_SNAPSHOT_CHROME_PROFILE_DIR is '{target_profile_dir}'."
            )

    processes = list_chrome_processes()
    repo_processes = [proc for proc in processes if process_uses_user_data_dir(proc["args"], str(user_data_dir))]
    cdp_payload = probe_cdp(settings["chrome_cdp_host"], settings["chrome_cdp_port"])
    cdp_live = cdp_payload is not None
    port_busy = tcp_listener_present(settings["chrome_cdp_host"], settings["chrome_cdp_port"])
    if cdp_live and not repo_processes:
        errors.append(
            "CDP endpoint is already live but no repo-owned Chrome process was detected for "
            f"{user_data_dir}. Port conflict: {cdp_url(settings['chrome_cdp_host'], settings['chrome_cdp_port'])}"
        )
    elif repo_processes and not cdp_live:
        errors.append(
            "Repo-owned Chrome processes were detected for "
            f"{user_data_dir}, but the configured CDP endpoint is unavailable: "
            f"{cdp_url(settings['chrome_cdp_host'], settings['chrome_cdp_port'])}"
        )
    elif port_busy and not cdp_live and not repo_processes:
        errors.append(
            "CDP port is already occupied by a non-Chrome or non-repo service at "
            f"{cdp_url(settings['chrome_cdp_host'], settings['chrome_cdp_port'])}"
        )

    launch_command = browser_launch_command(settings) if chrome_binary else []

    return {
        "provider": settings["provider"],
        "browser_root": settings["browser_root"],
        "browser_temp_root": settings["browser_temp_root"],
        "chrome_user_data_dir": settings["chrome_user_data_dir"],
        "chrome_profile_name": settings["chrome_profile_name"],
        "chrome_profile_dir": settings["chrome_profile_dir"],
        "chrome_profile_dir_by_name": target_profile_by_name,
        "chrome_channel": settings["chrome_channel"],
        "chrome_binary": chrome_binary or "",
        "cdp": {
            "host": settings["chrome_cdp_host"],
            "port": settings["chrome_cdp_port"],
            "url": cdp_url(settings["chrome_cdp_host"], settings["chrome_cdp_port"]),
            "running": cdp_live,
            "port_busy": port_busy,
            "version": cdp_payload or {},
        },
        "attach": build_attach_payload(settings),
        "launch": {
            "command": launch_command,
        },
        "processes": {
            "chrome_process_count": len(processes),
            "repo_process_count": len(repo_processes),
        },
        "ok": len(errors) == 0,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve and validate the Apple Notes Snapshot isolated Chrome browser contract."
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = resolve_contract_from_env()
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Apple Notes Snapshot browser contract")
        print(f"provider={payload['provider']}")
        print(f"browser_root={payload['browser_root']}")
        print(f"browser_temp_root={payload['browser_temp_root']}")
        print(f"chrome_user_data_dir={payload['chrome_user_data_dir']}")
        print(f"chrome_profile_name={payload['chrome_profile_name']}")
        print(f"chrome_profile_dir={payload['chrome_profile_dir']}")
        print(f"cdp_url={payload['cdp']['url']}")
        print(f"cdp_running={'true' if payload['cdp']['running'] else 'false'}")
        print(
            "launch_command="
            + json.dumps(payload["launch"]["command"], ensure_ascii=True)
        )
        print(
            "playwright_connect_over_cdp="
            + json.dumps(payload["attach"]["playwright"]["connectOverCDP"], ensure_ascii=True)
        )
        if payload["ok"]:
            print("status=ok")
        else:
            print("status=invalid")
            for err in payload["errors"]:
                print(f"error={err}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

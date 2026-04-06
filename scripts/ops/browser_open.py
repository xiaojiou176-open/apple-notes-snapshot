#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from browser_runtime import (
    build_attach_payload,
    chrome_binary_for_channel,
    cdp_url,
    default_settings_from_env,
    launch_command as browser_launch_command,
    list_chrome_processes,
    probe_cdp,
    process_uses_user_data_dir,
    tcp_listener_present,
    wait_for_cdp,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open or attach to the isolated Apple Notes Snapshot Chrome instance."
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = default_settings_from_env()
    errors: list[str] = []
    user_data_dir = Path(settings["chrome_user_data_dir"]).expanduser()
    profile_path = user_data_dir / settings["chrome_profile_dir"]
    chrome_binary = chrome_binary_for_channel(settings["chrome_channel"])
    processes = list_chrome_processes()
    repo_processes = [proc for proc in processes if process_uses_user_data_dir(proc["args"], settings["chrome_user_data_dir"])]
    live_cdp = probe_cdp(settings["chrome_cdp_host"], settings["chrome_cdp_port"])
    endpoint = cdp_url(settings["chrome_cdp_host"], settings["chrome_cdp_port"])
    port_busy = tcp_listener_present(settings["chrome_cdp_host"], settings["chrome_cdp_port"])

    if settings["provider"] != "chrome":
        errors.append(f"Unsupported browser provider: {settings['provider']}. This repo only supports real Chrome.")
    if not chrome_binary:
        errors.append(f"Chrome binary for channel '{settings['chrome_channel']}' was not found.")
    if not user_data_dir.exists():
        errors.append(f"Isolated Chrome user data dir does not exist: {user_data_dir}")
    if not profile_path.exists():
        errors.append(f"Isolated Chrome profile dir does not exist: {profile_path}")

    status = "attach"
    launched = False
    if live_cdp and not repo_processes:
        errors.append(f"CDP port conflict at {endpoint}; a non-repo Chrome instance appears to own this port.")
    elif repo_processes and not live_cdp:
        errors.append(
            f"Repo-owned Chrome processes exist for {user_data_dir}, but the configured CDP endpoint is unavailable: {endpoint}"
        )
    elif port_busy and not live_cdp and not repo_processes:
        errors.append(f"CDP port conflict at {endpoint}; another process is already listening there.")

    if not errors and not live_cdp:
        launch_command = browser_launch_command(settings)
        subprocess.Popen(
            launch_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        live_cdp = wait_for_cdp(settings["chrome_cdp_host"], settings["chrome_cdp_port"])
        if not live_cdp:
            errors.append(f"Chrome launched but CDP endpoint did not become ready: {endpoint}")
        else:
            processes = list_chrome_processes()
            repo_processes = [
                proc for proc in processes if process_uses_user_data_dir(proc["args"], settings["chrome_user_data_dir"])
            ]
            port_busy = tcp_listener_present(settings["chrome_cdp_host"], settings["chrome_cdp_port"])
            launched = True
            status = "launched"

    payload = {
        "status": "invalid" if errors else status,
        "launched": launched,
        "browser_root": settings["browser_root"],
        "chrome_user_data_dir": settings["chrome_user_data_dir"],
        "chrome_profile_dir": settings["chrome_profile_dir"],
        "cdp_url": endpoint,
        "cdp_port_busy": port_busy,
        "attach": build_attach_payload(settings),
        "repo_process_count": len(repo_processes),
        "chrome_process_count": len(processes),
        "errors": errors,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("Apple Notes Snapshot browser open")
        print(f"browser_root={payload['browser_root']}")
        print(f"chrome_user_data_dir={payload['chrome_user_data_dir']}")
        print(f"chrome_profile_dir={payload['chrome_profile_dir']}")
        print(f"cdp_url={payload['cdp_url']}")
        print(f"status={payload['status']}")
        print(f"launched={'true' if payload['launched'] else 'false'}")
        print(
            "playwright_connect_over_cdp="
            + json.dumps(payload["attach"]["playwright"]["connectOverCDP"], ensure_ascii=True)
        )
        for err in errors:
            print(f"error={err}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

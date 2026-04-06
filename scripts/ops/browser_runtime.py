#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import os
import socket
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


LOCK_FILENAMES = {
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
    "DevToolsActivePort",
}


def default_external_cache_root() -> str:
    return os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.join(Path.home(), ".cache")), "apple-notes-snapshot")


def default_browser_root(external_cache_root: str) -> str:
    return os.path.join(external_cache_root, "browser")


def default_default_chrome_user_data_dir() -> str:
    return str(Path.home() / "Library" / "Application Support" / "Google" / "Chrome")


def load_local_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_local_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def default_settings_from_env() -> dict:
    external_cache_root = os.environ.get("NOTES_SNAPSHOT_EXTERNAL_CACHE_ROOT", default_external_cache_root())
    browser_root = os.environ.get("NOTES_SNAPSHOT_BROWSER_ROOT", default_browser_root(external_cache_root))
    user_data_dir = os.environ.get(
        "NOTES_SNAPSHOT_CHROME_USER_DATA_DIR",
        os.path.join(browser_root, "chrome-user-data"),
    )
    temp_root = os.environ.get(
        "NOTES_SNAPSHOT_BROWSER_TEMP_ROOT",
        os.path.join(browser_root, "tmp"),
    )
    return {
        "provider": os.environ.get("NOTES_SNAPSHOT_BROWSER_PROVIDER", "chrome"),
        "browser_root": str(Path(browser_root).expanduser()),
        "chrome_user_data_dir": str(Path(user_data_dir).expanduser()),
        "chrome_profile_name": os.environ.get("NOTES_SNAPSHOT_CHROME_PROFILE_NAME", "apple-notes-snapshot"),
        "chrome_profile_dir": os.environ.get("NOTES_SNAPSHOT_CHROME_PROFILE_DIR", "Profile 1"),
        "chrome_channel": os.environ.get("NOTES_SNAPSHOT_CHROME_CHANNEL", "chrome"),
        "chrome_cdp_host": os.environ.get("NOTES_SNAPSHOT_CHROME_CDP_HOST", "127.0.0.1"),
        "chrome_cdp_port": int(os.environ.get("NOTES_SNAPSHOT_CHROME_CDP_PORT", "9337")),
        "browser_temp_root": str(Path(temp_root).expanduser()),
        "default_source_user_data_dir": default_default_chrome_user_data_dir(),
    }


def chrome_binary_for_channel(channel: str) -> str | None:
    if channel != "chrome":
        return None
    candidate = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if Path(candidate).exists():
        return candidate
    return None


def find_profile_dir_by_display_name(user_data_dir: Path, profile_name: str) -> str | None:
    info_cache = ((load_local_state(user_data_dir / "Local State").get("profile") or {}).get("info_cache") or {})
    for profile_dir, info in sorted(info_cache.items()):
        if (info or {}).get("name") == profile_name and (user_data_dir / profile_dir).exists():
            return profile_dir
    return None


def normalize_local_state_for_target(local_state: dict, source_profile_dir: str, target_profile_dir: str, target_profile_name: str) -> dict:
    payload = copy.deepcopy(local_state) if local_state else {}
    profile_section = payload.setdefault("profile", {})
    info_cache = copy.deepcopy(profile_section.get("info_cache") or {})
    source_entry = copy.deepcopy(info_cache.get(source_profile_dir) or {})
    source_entry["name"] = target_profile_name
    profile_section["info_cache"] = {target_profile_dir: source_entry}
    profile_section["last_used"] = target_profile_dir
    profile_section["last_active_profiles"] = [target_profile_dir]
    return payload


def remove_lock_files(root: Path) -> list[str]:
    removed: list[str] = []
    if not root.exists():
        return removed
    for path in root.rglob("*"):
        if path.name in LOCK_FILENAMES:
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
                removed.append(str(path))
            except OSError:
                continue
    return removed


def list_chrome_processes() -> list[dict]:
    result = subprocess.run(
        ["ps", "-ax", "-o", "pid=,args="],
        capture_output=True,
        text=True,
        check=False,
    )
    processes: list[dict] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "Google Chrome" not in line and "Chromium" not in line:
            continue
        parts = line.split(maxsplit=1)
        if not parts:
            continue
        pid = int(parts[0])
        args = parts[1] if len(parts) > 1 else ""
        processes.append({"pid": pid, "args": args})
    return processes


def process_uses_user_data_dir(process_args: str, user_data_dir: str) -> bool:
    token = f"--user-data-dir={user_data_dir}"
    return token in process_args


def default_root_is_quiet(source_user_data_dir: str) -> tuple[bool, list[dict]]:
    processes = list_chrome_processes()
    source_matches = [proc for proc in processes if process_uses_user_data_dir(proc["args"], source_user_data_dir)]
    return len(source_matches) == 0, source_matches


def cdp_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def probe_cdp(host: str, port: int, timeout: float = 1.0) -> dict | None:
    url = f"{cdp_url(host, port)}/json/version"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def tcp_listener_present(host: str, port: int, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def launch_command(settings: dict, url: str = "about:blank") -> list[str]:
    binary = chrome_binary_for_channel(settings["chrome_channel"])
    if not binary:
        return []
    return [
        binary,
        f"--user-data-dir={settings['chrome_user_data_dir']}",
        f"--profile-directory={settings['chrome_profile_dir']}",
        f"--remote-debugging-address={settings['chrome_cdp_host']}",
        f"--remote-debugging-port={settings['chrome_cdp_port']}",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]


def wait_for_cdp(host: str, port: int, timeout_sec: float = 15.0) -> dict | None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        payload = probe_cdp(host, port)
        if payload:
            return payload
        time.sleep(0.25)
    return None


def build_attach_payload(settings: dict) -> dict:
    endpoint = cdp_url(settings["chrome_cdp_host"], settings["chrome_cdp_port"])
    return {
        "cdp_url": endpoint,
        "playwright": {
            "connectOverCDP": {
                "endpointURL": endpoint,
            }
        },
    }


def profile_metadata_for_source_root(source_user_data_dir: Path, profile_name: str) -> dict:
    local_state = load_local_state(source_user_data_dir / "Local State")
    source_profile_dir = find_profile_dir_by_display_name(source_user_data_dir, profile_name)
    return {
        "source_user_data_dir": str(source_user_data_dir),
        "source_profile_dir": source_profile_dir or "",
        "source_local_state": local_state,
    }

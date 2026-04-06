import json
import os
import sys
import importlib.util
from pathlib import Path
from datetime import datetime, timezone

# ------------------------------
# Helpers
# ------------------------------
def env_default(name: str, default: str) -> str:
    return os.getenv(name, default)

def read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}

def parse_iso8601(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None

def compute_age_sec(iso_value: str) -> str:
    dt = parse_iso8601(iso_value)
    if not dt:
        return "unknown"
    return str(int((datetime.now(timezone.utc) - dt).total_seconds()))

def format_duration(seconds: int) -> str:
    if seconds is None:
        return "unknown"
    try:
        seconds = int(seconds)
    except Exception:
        return str(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    rem = seconds % 60
    return f"{minutes}m {rem}s"

def load_rich():
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.progress import Progress, BarColumn, TextColumn
        from rich.panel import Panel
        return Console, Table, Progress, BarColumn, TextColumn, Panel
    except Exception:
        return None


def load_aggregate_module():
    module_path = Path(__file__).with_name("aggregate_runs.py")
    try:
        spec = importlib.util.spec_from_file_location("aggregate_runs", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def build_recent_summary(state_dir: str, log_dir: str) -> dict:
    module = load_aggregate_module()
    if module is None:
        return {}
    metrics_path = Path(state_dir) / "metrics.jsonl"
    structured_path = Path(log_dir) / "structured.jsonl"
    metrics_entries, _ = module.read_jsonl(metrics_path, 50)
    structured_entries, _ = module.read_jsonl(structured_path, 50)
    runs = module.aggregate(metrics_entries, structured_entries)
    if not runs:
        runs = module.fallback_runs_from_state(Path(state_dir) / "state.json")
    return module.summarize_runs(runs)

def print_plain(summary: dict, phases: dict):
    print("Dashboard")
    for key, value in summary.items():
        print(f"{key}: {value}")
    if phases:
        print("")
        print("Phases")
        for name in sorted(phases.keys()):
            print(f"- {name}: {format_duration(phases[name])}")

def print_rich(summary: dict, phases: dict):
    Console, Table, Progress, BarColumn, TextColumn, Panel = load_rich()
    console = Console()

    table = Table(title="Apple Notes Snapshot Dashboard", show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    for key, value in summary.items():
        table.add_row(key, value)

    console.print(table)

    if not phases:
        return

    total = 0
    for value in phases.values():
        try:
            total += int(value)
        except Exception:
            continue
    if total <= 0:
        total = 1

    progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("{task.completed}/{task.total}s"),
        expand=True,
        transient=False,
    )
    with progress:
        for name in sorted(phases.keys()):
            try:
                duration = int(phases[name])
            except Exception:
                continue
            progress.add_task(name, total=total, completed=duration)

def main() -> int:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    default_log_dir = os.path.join(
        repo_root, ".runtime-cache", "logs", "apple-notes-snapshot"
    )
    default_state_dir = os.path.join(
        repo_root, ".runtime-cache", "cache", "apple-notes-snapshot", "state"
    )
    log_dir = env_default("NOTES_SNAPSHOT_LOG_DIR", default_log_dir)
    state_dir = env_default("NOTES_SNAPSHOT_STATE_DIR", default_state_dir)
    state_json = os.path.join(state_dir, "state.json")
    summary_txt = os.path.join(state_dir, "summary.txt")

    data = read_json(state_json)
    phases = data.get("phases") or {}
    status = data.get("status", "unknown")
    exit_code = data.get("exit_code", "unknown")
    duration_sec = data.get("duration_sec", "unknown")
    end_iso = data.get("end_iso", "unknown")
    last_success_iso = data.get("last_success_iso", "unknown")
    pipeline_exit_reason = data.get("pipeline_exit_reason", "none")

    age_sec = compute_age_sec(last_success_iso)
    stale_threshold = env_default("NOTES_SNAPSHOT_STALE_THRESHOLD_SEC", "7200")
    recent_summary = build_recent_summary(state_dir, log_dir)
    change_summary = recent_summary.get("change_summary") or {}
    current_streak = recent_summary.get("current_streak") or {}
    failure_clusters = recent_summary.get("failure_clusters") or []
    top_cluster = "none"
    if failure_clusters:
        first_cluster = failure_clusters[0]
        top_cluster = f"{first_cluster.get('reason', 'unknown')} x{first_cluster.get('count', 0)}"

    summary = {
        "status": str(status),
        "exit_code": str(exit_code),
        "duration": format_duration(duration_sec),
        "end_iso": str(end_iso),
        "last_success_iso": str(last_success_iso),
        "age_sec": str(age_sec),
        "stale_threshold_sec": str(stale_threshold),
        "pipeline_exit_reason": str(pipeline_exit_reason),
        "summary_file": summary_txt if os.path.isfile(summary_txt) else "(missing)",
        "state_json": state_json if os.path.isfile(state_json) else "(missing)",
        "recent_runs": str(recent_summary.get("recent_run_count", 0)),
        "recent_success": str(recent_summary.get("success_count", 0)),
        "recent_failed": str(recent_summary.get("failed_count", 0)),
        "recent_trend": str(change_summary.get("trend") or "unknown"),
        "change_summary": str(change_summary.get("summary") or "none"),
        "current_streak": f"{current_streak.get('status', 'unknown')}:{current_streak.get('count', 0)}",
        "status_window": json.dumps(recent_summary.get("status_window") or {}, ensure_ascii=True, sort_keys=True),
        "attention_state": str(recent_summary.get("attention_state") or "unknown"),
        "recoverability": str(recent_summary.get("recoverability") or "manual_review"),
        "workflow_hint": str(recent_summary.get("workflow_hint") or "none"),
        "latest_trigger_source": str(recent_summary.get("latest_trigger_source") or "unknown"),
        "latest_success_iso": str(recent_summary.get("latest_success_iso") or "unknown"),
        "top_failure_reason": str(recent_summary.get("top_failure_reason") or "none"),
        "top_failure_cluster": top_cluster,
    }

    if load_rich():
        print_rich(summary, phases)
    else:
        print_plain(summary, phases)
        print("")
        print("Tip: Install optional Rich UI with `pip install rich` for tables/bars.")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())

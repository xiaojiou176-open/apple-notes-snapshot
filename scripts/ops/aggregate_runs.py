#!/usr/bin/env python3
import argparse
import json
import os
from collections import Counter, defaultdict, deque
from pathlib import Path


def read_jsonl(path, tail):
    entries = deque(maxlen=tail) if tail else []
    errors = 0
    if not path or not path.is_file():
        return [], 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception:
                errors += 1
                continue
            if tail:
                entries.append(item)
            else:
                entries.append(item)  # type: ignore[arg-type]
    return list(entries), errors


def aggregate(metrics, structured):
    runs = defaultdict(lambda: {
        "run_id": "",
        "start_iso": "",
        "end_iso": "",
        "status": "",
        "exit_code": None,
        "trigger_source": "",
        "failure_reason": "",
        "root_dir": "",
        "events": [],
        "log_messages": [],
    })

    for item in metrics:
        run_id = item.get("run_id") or ""
        if not run_id:
            continue
        run = runs[run_id]
        run["run_id"] = run_id
        run["events"].append(item.get("event") or "")
        if item.get("event") == "run_start":
            run["start_iso"] = item.get("start_iso") or run["start_iso"]
            run["root_dir"] = item.get("root_dir") or run["root_dir"]
            run["trigger_source"] = item.get("trigger_source") or run["trigger_source"]
        if item.get("event") == "run_end":
            run["end_iso"] = item.get("end_iso") or run["end_iso"]
            run["status"] = item.get("status") or run["status"]
            run["exit_code"] = item.get("exit_code", run["exit_code"])
            run["failure_reason"] = item.get("failure_reason") or run["failure_reason"]
            run["trigger_source"] = item.get("trigger_source") or run["trigger_source"]

    for item in structured:
        run_id = item.get("run_id") or ""
        if not run_id:
            continue
        run = runs[run_id]
        run["run_id"] = run_id
        msg = item.get("message")
        if msg:
            run["log_messages"].append(msg)
        run["trigger_source"] = item.get("trigger_source") or run["trigger_source"]

    def sort_key(entry):
        return entry.get("end_iso") or entry.get("start_iso") or ""

    return sorted(runs.values(), key=sort_key, reverse=True)


def build_failure_clusters(runs, limit=3):
    clusters = {}
    for run in runs:
        if (run.get("status") or "") != "failed":
            continue
        reason = (run.get("failure_reason") or "").strip()
        if not reason:
            continue
        bucket = clusters.setdefault(
            reason,
            {
                "reason": reason,
                "count": 0,
                "latest_end_iso": "",
                "latest_run_id": "",
            },
        )
        bucket["count"] += 1
        end_iso = run.get("end_iso") or run.get("start_iso") or ""
        if end_iso and end_iso > bucket["latest_end_iso"]:
            bucket["latest_end_iso"] = end_iso
            bucket["latest_run_id"] = run.get("run_id") or ""

    ordered = sorted(clusters.values(), key=lambda item: item["reason"])
    ordered = sorted(ordered, key=lambda item: item["latest_end_iso"], reverse=True)
    ordered = sorted(ordered, key=lambda item: item["count"], reverse=True)
    return ordered[:limit]


def build_current_streak(runs):
    if not runs:
        return {"status": "unknown", "count": 0}

    latest_status = runs[0].get("status") or "unknown"
    streak = 0
    for run in runs:
        status = run.get("status") or "unknown"
        if status != latest_status:
            break
        streak += 1
    return {"status": latest_status, "count": streak}


def build_change_summary(runs):
    if not runs:
        return {
            "trend": "no_runs",
            "summary": "No recent runs were available in the current window.",
            "previous_distinct_status": "",
        }

    latest_status = runs[0].get("status") or "unknown"
    previous_distinct_status = ""
    for run in runs[1:]:
        status = run.get("status") or "unknown"
        if status != latest_status:
            previous_distinct_status = status
            break

    has_failures = any((run.get("status") or "") == "failed" for run in runs)
    has_successes = any((run.get("status") or "") == "success" for run in runs)
    streak = build_current_streak(runs)

    if len(runs) == 1:
        trend = f"single_{latest_status}"
        summary = f"Only one recent run is available, and it ended with {latest_status}."
    elif latest_status == "success" and has_failures:
        trend = "recovered"
        summary = "The most recent run succeeded after earlier failures in the recent window."
    elif latest_status == "failed" and has_successes:
        trend = "regressed"
        summary = "The most recent run failed after earlier successes in the recent window."
    elif latest_status == "success":
        trend = "steady_success"
        summary = f"The recent window is steady: the last {streak['count']} run(s) all succeeded."
    elif latest_status == "failed":
        trend = "steady_failure"
        summary = f"The recent window is unstable: the last {streak['count']} run(s) all failed."
    else:
        trend = "mixed"
        summary = "Recent runs show mixed or incomplete status signals."

    return {
        "trend": trend,
        "summary": summary,
        "previous_distinct_status": previous_distinct_status,
    }


def build_status_window(runs):
    statuses = Counter()
    for run in runs:
        status = run.get("status") or "unknown"
        statuses[status] += 1
    return dict(sorted(statuses.items()))


def build_attention_state(runs, change_summary):
    if not runs:
        return "no_runs"

    latest_status = runs[0].get("status") or "unknown"
    trend = change_summary.get("trend") or "unknown"

    if latest_status == "failed":
        return "failure_cluster"
    if latest_status == "success" and trend == "recovered":
        return "recovery_watch"
    if latest_status == "success" and trend in {"steady_success", "single_success"}:
        return "stable"
    return "mixed"


def build_recoverability(attention_state):
    if attention_state == "no_runs":
        return "bootstrap"
    if attention_state == "failure_cluster":
        return "recoverable"
    if attention_state == "recovery_watch":
        return "watch_window"
    if attention_state == "stable":
        return "stable_monitoring"
    return "manual_review"


def build_workflow_hint(attention_state):
    hints = {
        "no_runs": "Initialize the first successful snapshot baseline before treating the control room as a live incident board.",
        "failure_cluster": "Treat the latest failure cluster as the first stop, then inspect status, log-health, and doctor in that order.",
        "recovery_watch": "The latest run recovered; verify freshness and watch the next run before declaring the loop stable.",
        "stable": "Stay in watch mode; no immediate recovery action is required unless freshness or warnings change.",
        "mixed": "Use recent-run trend and state layers together before choosing the next operator action.",
    }
    return hints.get(attention_state, hints["mixed"])


def summarize_runs(runs):
    trigger_sources = Counter()
    failure_reasons = Counter()
    success_count = 0
    failed_count = 0
    latest_status = "unknown"
    latest_trigger_source = ""
    latest_failure_reason = ""
    latest_end_iso = ""
    latest_success_iso = ""

    for index, run in enumerate(runs):
        status = run.get("status") or "unknown"
        if index == 0:
            latest_status = status
            latest_trigger_source = run.get("trigger_source") or ""
            latest_failure_reason = run.get("failure_reason") or ""
            latest_end_iso = run.get("end_iso") or run.get("start_iso") or ""
        if status == "success":
            success_count += 1
            if not latest_success_iso:
                latest_success_iso = run.get("end_iso") or run.get("start_iso") or ""
        elif status == "failed":
            failed_count += 1

        trigger = run.get("trigger_source") or ""
        if trigger:
            trigger_sources[trigger] += 1

        failure_reason = run.get("failure_reason") or ""
        if failure_reason:
            failure_reasons[failure_reason] += 1

    top_failure_reason = ""
    if failure_reasons:
        top_failure_reason = failure_reasons.most_common(1)[0][0]

    current_streak = build_current_streak(runs)
    change_summary = build_change_summary(runs)
    failure_clusters = build_failure_clusters(runs)
    status_window = build_status_window(runs)
    attention_state = build_attention_state(runs, change_summary)
    recoverability = build_recoverability(attention_state)
    workflow_hint = build_workflow_hint(attention_state)
    top_failure_cluster = failure_clusters[0] if failure_clusters else {}

    return {
        "recent_run_count": len(runs),
        "success_count": success_count,
        "failed_count": failed_count,
        "latest_status": latest_status,
        "latest_trigger_source": latest_trigger_source,
        "latest_failure_reason": latest_failure_reason,
        "latest_end_iso": latest_end_iso,
        "latest_success_iso": latest_success_iso,
        "top_failure_reason": top_failure_reason,
        "trigger_sources": dict(sorted(trigger_sources.items())),
        "current_streak": current_streak,
        "change_summary": change_summary,
        "failure_clusters": failure_clusters,
        "status_window": status_window,
        "attention_state": attention_state,
        "recoverability": recoverability,
        "workflow_hint": workflow_hint,
        "top_failure_cluster": top_failure_cluster,
    }


def limit_recent_runs(runs, tail_runs):
    if not tail_runs or tail_runs <= 0:
        return runs
    return runs[:tail_runs]


def fallback_runs_from_state(state_path):
    if not state_path or not state_path.is_file():
        return []
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    run_id = payload.get("run_id") or ""
    if not run_id:
        return []

    status = payload.get("status") or "unknown"
    return [
        {
            "run_id": run_id,
            "start_iso": payload.get("start_iso") or "",
            "end_iso": payload.get("end_iso") or "",
            "status": status,
            "exit_code": payload.get("exit_code"),
            "trigger_source": payload.get("trigger_source") or "",
            "failure_reason": payload.get("failure_reason") or "",
            "root_dir": payload.get("root_dir") or "",
            "events": ["state_json_fallback"],
            "log_messages": [],
        }
    ]


def main():
    parser = argparse.ArgumentParser(description="Aggregate run metrics by run_id")
    parser.add_argument("--metrics", default="", help="metrics.jsonl path")
    parser.add_argument("--structured", default="", help="structured.jsonl path")
    parser.add_argument("--tail", type=int, default=500, help="max recent runs to include (0 = all)")
    parser.add_argument("--pretty", action="store_true", help="pretty JSON output")
    args = parser.parse_args()

    metrics_path = Path(args.metrics) if args.metrics else None
    structured_path = Path(args.structured) if args.structured else None
    repo_root = Path(__file__).resolve().parents[2]
    default_state_dir = (
        repo_root / ".runtime-cache" / "cache" / "apple-notes-snapshot" / "state"
    )
    default_log_dir = repo_root / ".runtime-cache" / "logs" / "apple-notes-snapshot"

    if metrics_path is None:
        state_dir = Path(
            os.getenv("NOTES_SNAPSHOT_STATE_DIR", str(default_state_dir))
        )
        metrics_path = state_dir / "metrics.jsonl"
        state_json_path = state_dir / "state.json"
    else:
        state_json_path = metrics_path.with_name("state.json")
    if structured_path is None:
        log_dir = Path(os.getenv("NOTES_SNAPSHOT_LOG_DIR", str(default_log_dir)))
        structured_path = log_dir / "structured.jsonl"

    tail = args.tail if args.tail and args.tail > 0 else 0
    metrics_entries, metrics_errors = read_jsonl(metrics_path, 0)
    structured_entries, structured_errors = read_jsonl(structured_path, 0)

    runs = aggregate(metrics_entries, structured_entries)
    if not runs:
        runs = fallback_runs_from_state(state_json_path)
    runs = limit_recent_runs(runs, tail)

    payload = {
        "metrics_file": str(metrics_path) if metrics_path else "",
        "structured_file": str(structured_path) if structured_path else "",
        "metrics_errors": metrics_errors,
        "structured_errors": structured_errors,
        "summary": summarize_runs(runs),
        "runs": runs,
    }

    if args.pretty:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

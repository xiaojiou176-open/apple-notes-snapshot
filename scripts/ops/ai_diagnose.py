#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NOTESCTL = REPO_ROOT / "notesctl"
DEFAULT_TAIL = 5
DEFAULT_TIMEOUT_SEC = 20
DEFAULT_MAX_OUTPUT_TOKENS = 2048
DEFAULT_SWITCHYARD_BASE_URL = "http://127.0.0.1:4010"


def env_default(name: str, default: str) -> str:
    return os.getenv(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def safe_int(raw: str, default: int) -> int:
    try:
        return int(raw)
    except Exception:
        return default


def resolve_tail_default() -> int:
    configured_tail = safe_int(
        env_default("NOTES_SNAPSHOT_AI_DIAGNOSE_TAIL", str(DEFAULT_TAIL)),
        DEFAULT_TAIL,
    )
    return configured_tail if configured_tail > 0 else DEFAULT_TAIL


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Advisory AI diagnosis for Apple Notes Snapshot",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument("--provider", default="", help="override configured provider")
    parser.add_argument("--model", default="", help="override configured model")
    parser.add_argument("--tail", type=int, default=None, help="recent runs to summarize")
    return parser.parse_args(argv)


def resolve_notesctl() -> Path:
    override = os.getenv("NOTES_SNAPSHOT_AI_NOTESCTL", "").strip()
    if override:
        return Path(override)
    return DEFAULT_NOTESCTL


def run_notesctl_json(command: list[str], timeout_sec: int) -> tuple[dict, str | None]:
    notesctl = resolve_notesctl()
    env = os.environ.copy()
    try:
        result = subprocess.run(
            [str(notesctl), *command],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            env=env,
        )
    except Exception as exc:
        return {}, f"subprocess_failed:{exc}"

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        return {}, f"command_failed:{' '.join(command)}:{result.returncode}:{stderr}"
    try:
        return json.loads(result.stdout), None
    except Exception as exc:
        return {}, f"invalid_json:{' '.join(command)}:{exc}"


def build_observed_facts(status: dict, doctor: dict, log_health: dict, aggregate: dict) -> list[str]:
    facts: list[str] = []

    health_level = status.get("health_level", "unknown")
    health_score = status.get("health_score", "unknown")
    facts.append(f"Status health is {health_level} with score {health_score}.")

    state_layers = status.get("state_layers") or {}
    ledger = state_layers.get("ledger") or {}
    launchd = state_layers.get("launchd") or {}
    config = state_layers.get("config") or {}
    if config:
        facts.append(f"Config layer is {config.get('status', 'unknown')}.")
    if launchd:
        facts.append(f"Launchd layer is {launchd.get('status', 'unknown')}.")
    if ledger:
        facts.append(f"Ledger layer is {ledger.get('status', 'unknown')}.")
        summary = ledger.get("summary")
        if summary:
            facts.append(f"Ledger summary: {summary}")

    last_success = status.get("last_success_iso", "unknown")
    facts.append(f"Last successful snapshot is {last_success}.")

    warnings = doctor.get("warnings") or []
    if warnings:
        facts.append(f"Doctor reported {len(warnings)} warning(s).")
        for warning in warnings[:3]:
            facts.append(f"Doctor warning: {warning}")
    else:
        facts.append("Doctor reported no warnings.")

    log_errors = ((log_health or {}).get("errors_total")) or 0
    facts.append(f"Log health reported {log_errors} matching error signal(s).")

    summary = aggregate.get("summary") or {}
    change_summary = summary.get("change_summary") or {}
    current_streak = summary.get("current_streak") or {}
    failure_clusters = summary.get("failure_clusters") or []
    status_window = summary.get("status_window") or {}
    workflow_hint = summary.get("workflow_hint") or ""
    recoverability = summary.get("recoverability") or ""
    attention_state = summary.get("attention_state") or ""
    facts.append(f"Recent run summary covers {summary.get('recent_run_count', 0)} run(s).")
    facts.append(f"Recent successes: {summary.get('success_count', 0)}.")
    facts.append(f"Recent failures: {summary.get('failed_count', 0)}.")
    if change_summary.get("summary"):
        facts.append(f"Recent change summary: {change_summary.get('summary')}")
    if current_streak.get("count", 0):
        facts.append(
            f"Current run streak is {current_streak.get('status', 'unknown')} x{current_streak.get('count', 0)}."
        )
    latest_trigger_source = summary.get("latest_trigger_source") or ""
    if latest_trigger_source:
        facts.append(f"Latest trigger source is {latest_trigger_source}.")
    top_failure = summary.get("top_failure_reason") or ""
    if top_failure:
        facts.append(f"Most recent repeated failure reason is {top_failure}.")
    if status_window:
        window_parts = [f"{name}={count}" for name, count in status_window.items()]
        facts.append(f"Recent status window: {', '.join(window_parts)}.")
    if failure_clusters:
        cluster_descriptions = [
            f"{cluster.get('reason', 'unknown')} x{cluster.get('count', 0)}"
            for cluster in failure_clusters[:3]
        ]
        facts.append(f"Failure clusters in the recent window: {', '.join(cluster_descriptions)}.")
    if attention_state:
        facts.append(f"Recent attention state is {attention_state}.")
    if recoverability:
        facts.append(f"Recoverability is currently {recoverability}.")
    if workflow_hint:
        facts.append(f"Workflow hint: {workflow_hint}")

    facts.append("AI Diagnose v1 did not inspect exported note content.")
    return facts


def build_run_change_summary(aggregate: dict) -> dict:
    summary = aggregate.get("summary") or {}
    change_summary = summary.get("change_summary") or {}
    current_streak = summary.get("current_streak") or {}
    recent_run_count = summary.get("recent_run_count", 0) or 0
    trend = change_summary.get("trend") or ("no_runs" if recent_run_count == 0 else "unknown")
    summary_text = change_summary.get("summary") or (
        "No recent runs were available in the current window." if recent_run_count == 0 else ""
    )
    return {
        "trend": trend,
        "summary": summary_text,
        "latest_status": summary.get("latest_status", "unknown"),
        "previous_distinct_status": change_summary.get("previous_distinct_status", ""),
        "latest_trigger_source": summary.get("latest_trigger_source", ""),
        "latest_success_iso": summary.get("latest_success_iso", ""),
        "current_streak": {
            "status": current_streak.get("status", "unknown"),
            "count": current_streak.get("count", 0),
        },
        "failure_clusters": summary.get("failure_clusters", []),
        "status_window": summary.get("status_window", {}),
        "attention_state": summary.get("attention_state", "unknown"),
        "recoverability": summary.get("recoverability", "manual_review"),
        "workflow_hint": summary.get("workflow_hint", ""),
    }


def build_deterministic_diagnosis(status: dict, doctor: dict, log_health: dict, aggregate: dict) -> dict:
    state_layers = status.get("state_layers") or {}
    ledger = state_layers.get("ledger") or {}
    launchd = state_layers.get("launchd") or {}
    warnings = doctor.get("warnings") or []
    summary = aggregate.get("summary") or {}
    change_summary = summary.get("change_summary") or {}
    health_level = status.get("health_level", "unknown")
    log_errors = (log_health or {}).get("errors_total", 0) or 0
    latest_status = summary.get("latest_status", "unknown")
    stale_warning = any("stale" in str(item).lower() for item in warnings)

    diagnosis: list[str] = []
    next_steps: list[str] = []
    confidence = "medium"

    if ledger.get("status") == "needs_first_run":
        diagnosis.append("This looks like an uninitialized first-run or cleaned-checkout state, not a confirmed runtime failure.")
        next_steps.extend(
            [
                "Run ./notesctl run --no-status to record the first successful snapshot baseline.",
                "Run ./notesctl verify to confirm the ledger now has a successful run.",
                "Run ./notesctl doctor if the state still looks empty afterward.",
            ]
        )
        confidence = "high"
    elif launchd.get("status") == "not_loaded":
        diagnosis.append("The local scheduler does not appear to be loaded right now.")
        next_steps.extend(
            [
                "Run ./notesctl install --minutes 30 --load.",
                "Run ./notesctl status --full to confirm the launchd layer changes.",
            ]
        )
        confidence = "high"
    elif latest_status == "success" and change_summary.get("trend") == "recovered":
        latest_cluster = summary.get("top_failure_reason") or "the earlier failure cluster"
        diagnosis.append(
            f"The latest run recovered, but recent history still shows earlier failures ({latest_cluster}) in the same observation window."
        )
        next_steps.extend(
            [
                "Run ./notesctl verify to confirm the recovery is stable, not just a one-off success.",
                "Run ./notesctl log-health --tail 200 to confirm the earlier failure cluster has stopped repeating.",
                "Keep the current recovery notes handy if the same failure reason returns.",
            ]
        )
        confidence = "medium"
    elif latest_status == "failed" or summary.get("failed_count", 0) > 0:
        top_failure = summary.get("top_failure_reason") or "the current failure pattern"
        diagnosis.append(
            f"Recent history shows an active failure pattern, and the dominant failure cluster looks like {top_failure}."
        )
        next_steps.extend(
            [
                "Run ./notesctl status --full to inspect the current state layers and recent failure reason.",
                "Run ./notesctl log-health --tail 200 for recent log signals.",
                "Run ./notesctl doctor to confirm dependency and path health.",
            ]
        )
        confidence = "high" if summary.get("failed_count", 0) > 1 else "medium"
    elif ledger.get("status") == "stale" and latest_status == "success" and summary.get("failed_count", 0) == 0:
        diagnosis.append(
            "The loop looks stale rather than broken: recent recorded runs are successful, but the latest success is now outside the freshness threshold."
        )
        next_steps.extend(
            [
                "Run ./notesctl run --no-status to refresh the snapshot baseline.",
                "Run ./notesctl verify to confirm the last successful snapshot is fresh again.",
                "If this should have run automatically, check ./notesctl status --full to confirm the scheduler still matches your expected cadence.",
            ]
        )
        confidence = "high"
    elif health_level == "OK" and not warnings and log_errors == 0:
        diagnosis.append("The deterministic control-room surfaces currently agree that the local backup loop looks healthy.")
        next_steps.extend(
            [
                "No immediate recovery action is required right now.",
                "Use ./notesctl status --full or ./notesctl doctor when you want a deterministic spot-check later.",
                "If a coding agent needs the same local facts, start ./notesctl mcp instead of screen-scraping the Web console.",
            ]
        )
        confidence = "high"
    elif warnings:
        if stale_warning and summary.get("failed_count", 0) == 0:
            diagnosis.append(
                "The deterministic checks point to a freshness issue, not a confirmed runtime failure, but the local loop still needs operator follow-up."
            )
            next_steps.extend(
                [
                    "Refresh the snapshot loop with ./notesctl run --no-status.",
                    "Run ./notesctl verify after the refresh to clear the stale warning.",
                    "If you expected the scheduler to keep this fresh, inspect ./notesctl status --full for the launchd cadence.",
                ]
            )
            confidence = "medium"
        else:
            diagnosis.append(
                "The deterministic checks do not show a confirmed AI diagnosis, but doctor warnings suggest the local runtime still needs attention."
            )
            next_steps.extend(
                [
                    "Review the first doctor warning and address the path or dependency gap it describes.",
                    "Run ./notesctl status --full after each fix to confirm the state layers move in the expected direction.",
                ]
            )
            confidence = "low"
    else:
        diagnosis.append("No single deterministic fault stands out, but the local state still deserves a manual review before calling it healthy.")
        next_steps.extend(
            [
                "Run ./notesctl status --full.",
                "Run ./notesctl doctor.",
                "If the state still looks ambiguous, compare with the quickstart and troubleshooting guides.",
            ]
        )
        confidence = "low"

    return {
        "likely_diagnosis": diagnosis,
        "recommended_next_steps": next_steps,
        "confidence": confidence,
    }


def build_operator_advisory(status: dict, doctor: dict, log_health: dict, aggregate: dict) -> dict:
    state_layers = status.get("state_layers") or {}
    ledger = state_layers.get("ledger") or {}
    launchd = state_layers.get("launchd") or {}
    warnings = doctor.get("warnings") or []
    summary = aggregate.get("summary") or {}
    change_summary = summary.get("change_summary") or {}
    failure_clusters = summary.get("failure_clusters") or []
    latest_status = summary.get("latest_status", "unknown")
    log_errors = (log_health or {}).get("errors_total", 0) or 0

    advisory = {
        "priority": "medium",
        "focus_area": "manual_review",
        "summary": "Keep using the deterministic control-room surfaces before escalating this state.",
        "anomaly_clusters": [],
        "recovery_path": [],
        "recoverability": "manual_review",
        "sequence_hint": "",
    }

    if failure_clusters:
        advisory["anomaly_clusters"] = [
            f"{cluster.get('reason', 'unknown')} x{cluster.get('count', 0)}"
            for cluster in failure_clusters[:3]
        ]

    if ledger.get("status") == "needs_first_run":
        advisory["priority"] = "high"
        advisory["focus_area"] = "first_run"
        advisory["summary"] = "Treat this as an initialization task, not as a broken export loop."
        advisory["recoverability"] = "bootstrap"
        advisory["sequence_hint"] = "Initialize first, verify second, then escalate only if the first successful snapshot still does not appear."
        advisory["recovery_path"] = [
            "Run ./notesctl run --no-status.",
            "Run ./notesctl verify.",
            "Only escalate if the first successful snapshot still does not appear afterward.",
        ]
    elif launchd.get("status") == "not_loaded":
        advisory["priority"] = "high"
        advisory["focus_area"] = "scheduler"
        advisory["summary"] = "The scheduler is not loaded, so the next operator action is to restore automation before debugging deeper."
        advisory["recoverability"] = "recoverable"
        advisory["sequence_hint"] = "Restore the scheduler first, then re-check freshness and warnings before doing deeper diagnosis."
        advisory["recovery_path"] = [
            "Run ./notesctl install --minutes 30 --load.",
            "Run ./notesctl status --full.",
            "Re-check freshness after launchd is loaded.",
        ]
    elif latest_status == "success" and change_summary.get("trend") == "recovered":
        advisory["priority"] = "medium"
        advisory["focus_area"] = "recovery_watch"
        advisory["summary"] = "The latest run recovered, but recent history still needs a watch window before you call the loop stable."
        advisory["recoverability"] = "watch_window"
        advisory["sequence_hint"] = "Verify the current state, then watch the next run before you downgrade this from incident to watch-only."
        advisory["recovery_path"] = [
            "Run ./notesctl verify.",
            "Watch the next scheduled/manual run.",
            "Keep the recent failure cluster in view if the same symptom returns.",
        ]
    elif latest_status == "failed" or summary.get("failed_count", 0) > 0:
        advisory["priority"] = "high"
        advisory["focus_area"] = "failure_cluster"
        advisory["summary"] = "Treat this as an active or recently active failure cluster and work from the deterministic run evidence outward."
        advisory["recoverability"] = "recoverable"
        advisory["sequence_hint"] = "Inspect current status first, then log-health, then doctor, so you confirm state, evidence, and dependency health in order."
        advisory["recovery_path"] = [
            "Run ./notesctl status --full.",
            "Run ./notesctl log-health --tail 200.",
            "Run ./notesctl doctor.",
        ]
    elif ledger.get("status") == "stale" and latest_status == "success" and summary.get("failed_count", 0) == 0:
        advisory["priority"] = "medium"
        advisory["focus_area"] = "freshness"
        advisory["summary"] = "The loop is stale rather than broken: refresh the snapshot cadence before treating this as a runtime incident."
        advisory["recoverability"] = "recoverable"
        advisory["sequence_hint"] = "Refresh the snapshot first, then verify freshness, then check the scheduler only if the freshness gap returns."
        advisory["recovery_path"] = [
            "Run ./notesctl run --no-status.",
            "Run ./notesctl verify.",
            "Check ./notesctl status --full if the scheduler should have kept this fresh automatically.",
        ]
    elif status.get("health_level") == "OK" and not warnings and log_errors == 0:
        advisory["priority"] = "low"
        advisory["focus_area"] = "healthy_watch"
        advisory["summary"] = "No immediate operator action is required. Treat this as a healthy control-room state with optional spot checks."
        advisory["recoverability"] = "stable_monitoring"
        advisory["sequence_hint"] = "No recovery sequence is needed right now; stay in watch mode and spot-check only when the state changes."
        advisory["recovery_path"] = [
            "No immediate recovery action is required.",
            "Use ./notesctl status --full or ./notesctl doctor when you want a deterministic spot-check later.",
        ]

    return advisory


REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "observed_facts": {"type": "array", "items": {"type": "string"}},
        "likely_diagnosis": {"type": "array", "items": {"type": "string"}},
        "recommended_next_steps": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string"},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "observed_facts",
        "likely_diagnosis",
        "recommended_next_steps",
        "confidence",
        "limitations",
    ],
    "additionalProperties": False,
}


def build_system_prompt() -> str:
    return (
        "You are the advisory AI Diagnose assistant for Apple Notes Snapshot. "
        "Only use the supplied diagnostic input. Never claim note content was inspected. "
        "Separate deterministic system facts from AI inferences. "
        "Return JSON only with observed_facts, likely_diagnosis, recommended_next_steps, confidence, limitations. "
        "Do not add markdown fences. "
        "Use arrays for observed_facts, likely_diagnosis, recommended_next_steps, and limitations. "
        "Keep every item concise."
    )


def build_user_prompt(normalized_input: dict) -> str:
    return (
        "Diagnose the current Apple Notes Snapshot state.\n"
        "Requirements:\n"
        "- observed_facts must only restate supplied evidence\n"
        "- likely_diagnosis may infer, but stay honest about uncertainty\n"
        "- recommended_next_steps should be concrete CLI actions when possible\n"
        "- limitations must mention that the result is advisory, not canonical system truth\n"
        "- return JSON only, with no markdown fences\n"
        "- keep the output compact and use short bullet-like strings inside the arrays\n\n"
        f"Diagnostic input JSON:\n{json.dumps(normalized_input, ensure_ascii=True, indent=2)}"
    )


def build_compact_user_prompt(normalized_input: dict) -> str:
    return (
        "Return minified JSON only with these exact keys:\n"
        '- observed_facts: array of at most 8 short strings\n'
        '- likely_diagnosis: array of at most 3 short strings\n'
        '- recommended_next_steps: array of at most 5 short strings\n'
        '- confidence: one of low, medium, high\n'
        '- limitations: array of at most 4 short strings\n'
        "Do not include markdown fences. Do not use paragraph values. Keep every string short and concrete.\n\n"
        f"Diagnostic input JSON:\n{json.dumps(normalized_input, ensure_ascii=True, separators=(',', ':'))}"
    )


def post_json(url: str, payload: dict, headers: dict, timeout_sec: int) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        return json.loads(response.read().decode("utf-8"))


def resolve_switchyard_invoke_url(raw_base_url: str) -> str:
    normalized = (raw_base_url or "").strip().rstrip("/")
    if not normalized:
        normalized = DEFAULT_SWITCHYARD_BASE_URL
    if normalized.endswith("/v1/runtime/invoke"):
        return normalized
    return f"{normalized}/v1/runtime/invoke"


def extract_switchyard_output_text(response: dict) -> str:
    if isinstance(response.get("text"), str):
        return response["text"].strip()
    if isinstance(response.get("outputText"), str):
        return response["outputText"].strip()
    return ""


def coerce_json_text(raw_text: str) -> str:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    if cleaned and not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
    return cleaned


def parse_model_report(raw_text: str) -> dict:
    data = json.loads(coerce_json_text(raw_text))
    if "likely_diagnosis" not in data and "ai_inference" in data:
        data["likely_diagnosis"] = data["ai_inference"]
    if isinstance(data.get("observed_facts"), str):
        data["observed_facts"] = [data["observed_facts"]]
    if isinstance(data.get("likely_diagnosis"), str):
        data["likely_diagnosis"] = [data["likely_diagnosis"]]
    if isinstance(data.get("recommended_next_steps"), str):
        data["recommended_next_steps"] = [data["recommended_next_steps"]]
    if isinstance(data.get("limitations"), str):
        data["limitations"] = [data["limitations"]]
    if isinstance(data.get("confidence"), str):
        data["confidence"] = data["confidence"].strip().lower()
    elif isinstance(data.get("confidence"), (int, float)):
        numeric_confidence = float(data["confidence"])
        if numeric_confidence >= 0.8:
            data["confidence"] = "high"
        elif numeric_confidence >= 0.5:
            data["confidence"] = "medium"
        else:
            data["confidence"] = "low"
    for key in REPORT_SCHEMA["required"]:
        if key not in data:
            raise ValueError(f"missing_key:{key}")
    if not isinstance(data.get("observed_facts"), list):
        raise ValueError("observed_facts_not_list")
    if not isinstance(data.get("likely_diagnosis"), list):
        raise ValueError("likely_diagnosis_not_list")
    if not isinstance(data.get("recommended_next_steps"), list):
        raise ValueError("recommended_next_steps_not_list")
    if not isinstance(data.get("limitations"), list):
        raise ValueError("limitations_not_list")
    return data


def call_switchyard_provider(normalized_input: dict, provider: str, model: str, base_url: str, timeout_sec: int, max_output_tokens: int) -> tuple[dict, str | None]:
    invoke_url = resolve_switchyard_invoke_url(base_url)
    headers = {"Content-Type": "application/json"}
    prompts = [
        build_user_prompt(normalized_input),
        build_compact_user_prompt(normalized_input),
    ]
    for attempt_index, prompt in enumerate(prompts):
        payload = {
            "lane": "byok",
            "provider": provider,
            "model": model,
            "input": prompt,
            "system": build_system_prompt(),
            "maxOutputTokens": max(max_output_tokens, 4096) if attempt_index > 0 else max_output_tokens,
            "temperature": 0,
            "stream": False,
        }
        try:
            response = post_json(invoke_url, payload, headers, timeout_sec)
            raw_text = extract_switchyard_output_text(response)
            if not raw_text:
                if attempt_index == len(prompts) - 1:
                    return {}, "switchyard_empty_output"
                continue
            return parse_model_report(raw_text), None
        except urllib.error.HTTPError as exc:
            return {}, f"switchyard_http_error:{exc.code}"
        except urllib.error.URLError as exc:
            return {}, f"switchyard_url_error:{exc.reason}"
        except Exception as exc:
            if attempt_index == len(prompts) - 1:
                return {}, f"switchyard_error:{exc}"
    return {}, "switchyard_empty_output"


def normalize_input(status: dict, doctor: dict, log_health: dict, aggregate: dict, tail: int) -> dict:
    summary = aggregate.get("summary") or {}
    runs = aggregate.get("runs") or []
    trimmed_runs = runs[:tail]

    return {
        "advisory_only": True,
        "note_content_included": False,
        "tail_runs_requested": tail,
        "status": {
            "health_level": status.get("health_level", "unknown"),
            "health_score": status.get("health_score", "unknown"),
            "health_reasons": status.get("health_reasons", []),
            "launchd": status.get("launchd", "unknown"),
            "last_success_iso": status.get("last_success_iso", "unknown"),
            "failure_reason": status.get("failure_reason", ""),
            "state_layers": status.get("state_layers", {}),
        },
        "doctor": {
            "warnings": doctor.get("warnings", []),
            "dependencies": doctor.get("dependencies", {}),
            "launchd_loaded": doctor.get("launchd_loaded"),
            "plist_exists": doctor.get("plist_exists"),
            "state_dir": doctor.get("state_dir", ""),
            "log_dir": doctor.get("log_dir", ""),
        },
        "log_health": {
            "health": log_health.get("health", "unknown"),
            "errors_total": log_health.get("errors_total", 0),
            "errors_stderr": log_health.get("errors_stderr", 0),
            "errors_launchd_err": log_health.get("errors_launchd_err", 0),
        },
        "recent_runs": {
            "summary": summary,
            "runs": trimmed_runs,
        },
    }


def build_report(status: dict, doctor: dict, log_health: dict, aggregate: dict, provider_name: str, provider_model: str, provider_error: str | None, ai_used: bool, tail: int) -> dict:
    normalized_input = normalize_input(status, doctor, log_health, aggregate, tail)
    observed_facts = build_observed_facts(status, doctor, log_health, aggregate)
    deterministic = build_deterministic_diagnosis(status, doctor, log_health, aggregate)
    run_change_summary = build_run_change_summary(aggregate)
    operator_advisory = build_operator_advisory(status, doctor, log_health, aggregate)

    limitations = [
        "AI Diagnose is advisory only. Existing status, doctor, verify, and log-health surfaces remain the canonical system truth.",
        "AI Diagnose v1 does not inspect exported note content.",
    ]
    if provider_error:
        limitations.append(f"AI provider was unavailable or misconfigured: {provider_error}. A deterministic fallback summary is shown instead.")
    elif not ai_used:
        limitations.append("AI provider is disabled or not configured, so this report is deterministic only.")

    report = {
        "advisory_only": True,
        "ai_used": ai_used,
        "execution_mode": "ai_augmented" if ai_used else ("deterministic_fallback" if provider_error else "deterministic_only"),
        "provider": {
            "enabled": ai_used,
            "name": provider_name or "",
            "model": provider_model or "",
            "status": "ok" if ai_used else ("misconfigured" if provider_error else "disabled"),
            "error": provider_error or "",
            "note_content_included": False,
        },
        "note_content_included": False,
        "observed_facts": observed_facts,
        "run_change_summary": run_change_summary,
        "operator_advisory": operator_advisory,
        "likely_diagnosis": {
            "deterministic": deterministic["likely_diagnosis"],
            "ai_inference": [],
        },
        "recommended_next_steps": [
            {"source": "deterministic", "text": item}
            for item in deterministic["recommended_next_steps"]
        ],
        "confidence": deterministic["confidence"],
        "limitations": limitations,
        "normalized_input": normalized_input,
    }
    return report


def merge_ai_report(base_report: dict, ai_report: dict) -> dict:
    merged = dict(base_report)
    merged["ai_used"] = True
    merged["execution_mode"] = "ai_augmented"
    merged["provider"]["enabled"] = True
    merged["provider"]["status"] = "ok"
    merged["observed_facts"] = base_report["observed_facts"]
    ai_inference = ai_report.get("likely_diagnosis")
    if not ai_inference:
        ai_inference = ai_report.get("ai_inference", [])
    merged["likely_diagnosis"] = {
        "deterministic": base_report["likely_diagnosis"]["deterministic"],
        "ai_inference": [str(item) for item in ai_inference if str(item).strip()],
    }
    merged["recommended_next_steps"] = list(base_report["recommended_next_steps"])
    for item in ai_report.get("recommended_next_steps", []):
        if str(item).strip():
            merged["recommended_next_steps"].append({"source": "ai", "text": str(item)})
    merged["confidence"] = ai_report.get("confidence", base_report["confidence"])
    merged["limitations"] = [
        item
        for item in base_report["limitations"]
        if "AI provider is disabled or not configured" not in str(item)
    ]
    merged["limitations"].extend(str(item) for item in ai_report.get("limitations", []) if str(item).strip())
    return merged


def render_plain(report: dict) -> str:
    lines = [
        "AI Diagnose",
        f"AI used: {'yes' if report.get('ai_used') else 'no'}",
        f"Execution mode: {report.get('execution_mode', 'deterministic_only')}",
        f"Provider status: {report.get('provider', {}).get('status', 'disabled')}",
        "Observed Facts",
    ]
    for item in report.get("observed_facts", []):
        lines.append(f"- {item}")

    run_change_summary = report.get("run_change_summary", {}) or {}
    lines.append("")
    lines.append("Run / Change Summary")
    lines.append(f"- Trend: {run_change_summary.get('trend', 'unknown')}")
    if run_change_summary.get("summary"):
        lines.append(f"- Summary: {run_change_summary.get('summary')}")
    current_streak = run_change_summary.get("current_streak", {}) or {}
    if current_streak.get("count", 0):
        lines.append(
            f"- Current streak: {current_streak.get('status', 'unknown')} x{current_streak.get('count', 0)}"
        )
    status_window = run_change_summary.get("status_window", {}) or {}
    if status_window:
        window_parts = [f"{name}={count}" for name, count in status_window.items()]
        lines.append(f"- Status window: {', '.join(window_parts)}")
    if run_change_summary.get("attention_state"):
        lines.append(f"- Attention state: {run_change_summary.get('attention_state')}")
    if run_change_summary.get("recoverability"):
        lines.append(f"- Recoverability: {run_change_summary.get('recoverability')}")
    if run_change_summary.get("workflow_hint"):
        lines.append(f"- Workflow hint: {run_change_summary.get('workflow_hint')}")
    if run_change_summary.get("latest_trigger_source"):
        lines.append(f"- Latest trigger source: {run_change_summary.get('latest_trigger_source')}")
    failure_clusters = run_change_summary.get("failure_clusters", []) or []
    for cluster in failure_clusters[:3]:
        lines.append(f"- Failure cluster: {cluster.get('reason', 'unknown')} x{cluster.get('count', 0)}")

    operator_advisory = report.get("operator_advisory", {}) or {}
    lines.append("")
    lines.append("Operator Advisory")
    lines.append(f"- Priority: {operator_advisory.get('priority', 'medium')}")
    lines.append(f"- Focus area: {operator_advisory.get('focus_area', 'manual_review')}")
    lines.append(f"- Recoverability: {operator_advisory.get('recoverability', 'manual_review')}")
    if operator_advisory.get("summary"):
        lines.append(f"- Summary: {operator_advisory.get('summary')}")
    if operator_advisory.get("sequence_hint"):
        lines.append(f"- Sequence hint: {operator_advisory.get('sequence_hint')}")
    for item in operator_advisory.get("recovery_path", []) or []:
        lines.append(f"- Recovery path: {item}")
    for item in operator_advisory.get("anomaly_clusters", []) or []:
        lines.append(f"- Anomaly cluster: {item}")

    lines.append("")
    lines.append("Likely Diagnosis")
    for item in report.get("likely_diagnosis", {}).get("deterministic", []):
        lines.append(f"- [FACT-BASED] {item}")
    for item in report.get("likely_diagnosis", {}).get("ai_inference", []):
        lines.append(f"- [AI] {item}")

    lines.append("")
    lines.append("Recommended Next Steps")
    for item in report.get("recommended_next_steps", []):
        lines.append(f"- [{item.get('source', 'deterministic')}] {item.get('text', '')}")

    lines.append("")
    lines.append("Confidence / Limitations")
    lines.append(f"- Confidence: {report.get('confidence', 'unknown')}")
    for item in report.get("limitations", []):
        lines.append(f"- {item}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    tail = args.tail if args.tail and args.tail > 0 else resolve_tail_default()
    timeout_sec = safe_int(env_default("NOTES_SNAPSHOT_AI_TIMEOUT_SEC", str(DEFAULT_TIMEOUT_SEC)), DEFAULT_TIMEOUT_SEC)
    max_output_tokens = safe_int(
        env_default("NOTES_SNAPSHOT_AI_MAX_OUTPUT_TOKENS", str(DEFAULT_MAX_OUTPUT_TOKENS)),
        DEFAULT_MAX_OUTPUT_TOKENS,
    )

    status, status_error = run_notesctl_json(["status", "--json"], timeout_sec)
    doctor, doctor_error = run_notesctl_json(["doctor", "--json"], timeout_sec)
    log_health, log_error = run_notesctl_json(["log-health", "--json", "--tail", "200"], timeout_sec)
    aggregate, aggregate_error = run_notesctl_json(["aggregate", "--tail", str(max(tail, 5))], timeout_sec)

    command_errors = [err for err in (status_error, doctor_error, log_error, aggregate_error) if err]
    if command_errors:
        payload = {
            "advisory_only": True,
            "ai_used": False,
            "execution_mode": "deterministic_input_error",
            "provider": {
                "enabled": False,
                "name": "",
                "model": "",
                "status": "disabled",
                "error": "",
                "note_content_included": False,
            },
            "note_content_included": False,
            "observed_facts": [],
            "run_change_summary": {
                "trend": "input_error",
                "summary": "AI Diagnose could not build a structured run/change summary because one or more deterministic inputs failed.",
                "latest_status": "unknown",
                "previous_distinct_status": "",
                "latest_trigger_source": "",
                "latest_success_iso": "",
                "current_streak": {"status": "unknown", "count": 0},
                "failure_clusters": [],
            },
            "operator_advisory": {
                "priority": "high",
                "focus_area": "input_surfaces",
                "summary": "Restore the deterministic inputs before trusting any advisory summary.",
                "anomaly_clusters": [],
                "recovery_path": [
                    "Run ./notesctl status --json",
                    "Run ./notesctl doctor --json",
                    "Run ./notesctl log-health --json",
                ],
            },
            "likely_diagnosis": {"deterministic": [], "ai_inference": []},
            "recommended_next_steps": [
                {"source": "deterministic", "text": "Run ./notesctl status --json"},
                {"source": "deterministic", "text": "Run ./notesctl doctor --json"},
                {"source": "deterministic", "text": "Run ./notesctl log-health --json"},
            ],
            "confidence": "low",
            "limitations": [
                "AI Diagnose could not gather the deterministic input surfaces it depends on.",
                *command_errors,
            ],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=True, indent=2))
        else:
            print(render_plain(payload))
        return 0

    provider_name = (args.provider or env_default("NOTES_SNAPSHOT_AI_PROVIDER", "")).strip().lower()
    provider_model = (args.model or env_default("NOTES_SNAPSHOT_AI_MODEL", "")).strip()
    ai_enabled = env_bool("NOTES_SNAPSHOT_AI_ENABLE", False)
    base_url = resolve_switchyard_invoke_url(
        env_default("NOTES_SNAPSHOT_AI_BASE_URL", DEFAULT_SWITCHYARD_BASE_URL)
    )

    note_content_allowed = env_bool("NOTES_SNAPSHOT_AI_ALLOW_NOTE_CONTENT", False)
    base_report = build_report(
        status,
        doctor,
        log_health,
        aggregate,
        provider_name,
        provider_model,
        None,
        False,
        tail,
    )
    if note_content_allowed:
        base_report["limitations"].append(
            "NOTES_SNAPSHOT_AI_ALLOW_NOTE_CONTENT is set, but AI Diagnose v1 still ignores note content and only reads diagnostic state surfaces."
        )
        base_report["provider"]["note_content_included"] = False

    provider_error: str | None = None
    ai_report: dict | None = None
    if ai_enabled:
        if not provider_name:
            provider_error = "provider_missing"
        elif not provider_model:
            provider_error = "model_missing"
        else:
            ai_report, provider_error = call_switchyard_provider(
                base_report["normalized_input"],
                provider_name,
                provider_model,
                base_url,
                timeout_sec,
                max_output_tokens,
            )

    if ai_report and not provider_error:
        report = merge_ai_report(base_report, ai_report)
    else:
        report = build_report(
            status,
            doctor,
            log_health,
            aggregate,
            provider_name,
            provider_model,
            provider_error,
            False,
            tail,
        )
        report["provider"]["enabled"] = ai_enabled
        report["provider"]["name"] = provider_name or ""
        report["provider"]["model"] = provider_model or ""
        if note_content_allowed:
            report["limitations"].append(
                "NOTES_SNAPSHOT_AI_ALLOW_NOTE_CONTENT is set, but AI Diagnose v1 still ignores note content and only reads diagnostic state surfaces."
            )

    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(render_plain(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

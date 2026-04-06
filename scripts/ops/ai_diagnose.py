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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ops.ai_diagnose_report import (  # noqa: E402
    build_deterministic_diagnosis,
    build_observed_facts,
    build_operator_advisory,
    build_report,
    build_run_change_summary,
    merge_ai_report,
    normalize_input,
    render_plain,
)


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

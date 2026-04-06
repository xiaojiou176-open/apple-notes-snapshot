import importlib.util
import io
import json
import os
import tempfile
import unittest
import unittest.mock
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path


def load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "ops" / "ai_diagnose.py"
    spec = importlib.util.spec_from_file_location("ai_diagnose", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AiDiagnoseUnitTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.status = {
            "health_level": "WARN",
            "health_score": 80,
            "health_reasons": ["unknown_last_success"],
            "launchd": "loaded",
            "last_success_iso": "unknown",
            "failure_reason": "",
            "state_layers": {
                "config": {"status": "configured", "summary": "Config ok."},
                "launchd": {"status": "loaded", "summary": "launchd loaded."},
                "ledger": {
                    "status": "needs_first_run",
                    "summary": "No successful snapshot is recorded yet.",
                },
            },
        }
        self.doctor = {
            "warnings": ["no last_success record; run wrapper once to initialize"],
            "dependencies": {"python_bin": "python3"},
            "launchd_loaded": True,
            "plist_exists": True,
            "state_dir": "/tmp/state",
            "log_dir": "/tmp/logs",
        }
        self.log_health = {
            "health": "FAIL",
            "errors_total": 0,
            "errors_stderr": 0,
            "errors_launchd_err": 0,
        }
        self.aggregate = {
            "summary": {
                "recent_run_count": 0,
                "success_count": 0,
                "failed_count": 0,
                "latest_status": "unknown",
                "top_failure_reason": "",
                "trigger_sources": {},
            },
            "runs": [],
        }

    def test_basic_helpers(self):
        self.assertTrue(self.mod.env_bool("NO_SUCH_BOOL", True))
        self.assertFalse(self.mod.env_bool("NO_SUCH_BOOL", False))
        self.assertEqual(self.mod.safe_int("5", 0), 5)
        self.assertEqual(self.mod.safe_int("bad", 7), 7)
        self.assertIsNone(self.mod.parse_args([]).tail)
        self.assertEqual(self.mod.resolve_tail_default(), 5)
        self.assertEqual(self.mod.parse_args(["--json", "--provider", "gemini", "--model", "gemini-2.5-flash", "--tail", "7"]).tail, 7)
        self.assertEqual(
            self.mod.resolve_switchyard_invoke_url("http://127.0.0.1:4010"),
            "http://127.0.0.1:4010/v1/runtime/invoke",
        )
        self.assertEqual(
            self.mod.resolve_switchyard_invoke_url("http://127.0.0.1:4010/v1/runtime/invoke"),
            "http://127.0.0.1:4010/v1/runtime/invoke",
        )
        with unittest.mock.patch.dict(os.environ, {"NOTES_SNAPSHOT_AI_DIAGNOSE_TAIL": "9"}, clear=False):
            self.assertEqual(self.mod.resolve_tail_default(), 9)
        with unittest.mock.patch.dict(os.environ, {"NOTES_SNAPSHOT_AI_DIAGNOSE_TAIL": "0"}, clear=False):
            self.assertEqual(self.mod.resolve_tail_default(), 5)
        with unittest.mock.patch.dict(os.environ, {"NOTES_SNAPSHOT_AI_DIAGNOSE_TAIL": "bad"}, clear=False):
            self.assertEqual(self.mod.resolve_tail_default(), 5)

    def test_resolve_notesctl_override(self):
        with unittest.mock.patch.dict(os.environ, {"NOTES_SNAPSHOT_AI_NOTESCTL": "/tmp/custom-notesctl"}, clear=False):
            self.assertEqual(str(self.mod.resolve_notesctl()), "/tmp/custom-notesctl")
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(str(self.mod.resolve_notesctl()).endswith("/notesctl"))

    def test_run_notesctl_json_success_failure_and_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stub = Path(tmpdir) / "notesctl"
            stub.write_text(
                """#!/usr/bin/env python3
import json
import sys
cmd = sys.argv[1:]
if cmd == ["status", "--json"]:
    print(json.dumps({"ok": True}))
elif cmd == ["doctor", "--json"]:
    print("not-json")
elif cmd == ["log-health", "--json", "--tail", "200"]:
    sys.stderr.write("boom\\n")
    sys.exit(2)
""",
                encoding="utf-8",
            )
            stub.chmod(0o755)
            with unittest.mock.patch.dict(os.environ, {"NOTES_SNAPSHOT_AI_NOTESCTL": str(stub)}, clear=False):
                payload, error = self.mod.run_notesctl_json(["status", "--json"], 5)
                self.assertIsNone(error)
                self.assertTrue(payload["ok"])

                payload, error = self.mod.run_notesctl_json(["doctor", "--json"], 5)
                self.assertEqual(payload, {})
                self.assertIn("invalid_json", error)

                payload, error = self.mod.run_notesctl_json(["log-health", "--json", "--tail", "200"], 5)
                self.assertEqual(payload, {})
                self.assertIn("command_failed", error)

    def test_build_observed_facts_and_deterministic_branches(self):
        facts = self.mod.build_observed_facts(self.status, self.doctor, self.log_health, self.aggregate)
        self.assertIn("Config layer is configured.", facts)
        self.assertTrue(any("Doctor warning" in item for item in facts))
        facts_with_top_failure = self.mod.build_observed_facts(
            self.status,
            {"warnings": []},
            {"errors_total": 1},
            {
                "summary": {
                    "recent_run_count": 2,
                    "success_count": 1,
                    "failed_count": 1,
                    "latest_status": "failed",
                    "top_failure_reason": "timeout",
                    "trigger_sources": {"launchd": 1},
                }
            },
        )
        self.assertIn("Most recent repeated failure reason is timeout.", facts_with_top_failure)

        first_run = self.mod.build_deterministic_diagnosis(self.status, self.doctor, self.log_health, self.aggregate)
        self.assertEqual(first_run["confidence"], "high")
        self.assertTrue(any("./notesctl run --no-status" in step for step in first_run["recommended_next_steps"]))

        launchd_case = self.mod.build_deterministic_diagnosis(
            {"state_layers": {"ledger": {"status": "fresh"}, "launchd": {"status": "not_loaded"}}},
            {"warnings": []},
            {},
            {"summary": {}},
        )
        self.assertIn("scheduler", launchd_case["likely_diagnosis"][0])

        failed_runs_case = self.mod.build_deterministic_diagnosis(
            {"state_layers": {"ledger": {"status": "fresh"}, "launchd": {"status": "loaded"}}},
            {"warnings": []},
            {},
            {"summary": {"failed_count": 2, "top_failure_reason": "timeout"}},
        )
        self.assertIn("timeout", failed_runs_case["likely_diagnosis"][0])

        warnings_case = self.mod.build_deterministic_diagnosis(
            {"state_layers": {"ledger": {"status": "fresh"}, "launchd": {"status": "loaded"}}},
            {"warnings": ["bad path"]},
            {},
            {"summary": {}},
        )
        self.assertIn("doctor warnings", warnings_case["likely_diagnosis"][0])

        healthy_case = self.mod.build_deterministic_diagnosis(
            {
                "health_level": "OK",
                "state_layers": {"ledger": {"status": "fresh"}, "launchd": {"status": "loaded"}},
            },
            {"warnings": []},
            {"errors_total": 0},
            {"summary": {}},
        )
        self.assertIn("looks healthy", healthy_case["likely_diagnosis"][0])
        self.assertEqual(healthy_case["confidence"], "high")
        self.assertTrue(any("./notesctl mcp" in step for step in healthy_case["recommended_next_steps"]))

        ambiguous_case = self.mod.build_deterministic_diagnosis(
            {
                "health_level": "WARN",
                "state_layers": {"ledger": {"status": "fresh"}, "launchd": {"status": "loaded"}},
            },
            {"warnings": []},
            {"errors_total": 0},
            {"summary": {}},
        )
        self.assertIn("manual review", ambiguous_case["likely_diagnosis"][0])
        self.assertEqual(ambiguous_case["confidence"], "low")

    def test_extract_and_parse_model_report(self):
        raw_text = self.mod.extract_switchyard_output_text(
            {
                "text": "```json\n{\"observed_facts\":[\"f\"],\"ai_inference\":[\"diag\"],\"recommended_next_steps\":[\"step\"],\"confidence\":\"medium\",\"limitations\":[\"limit\"]}\n```"
            }
        )
        parsed = self.mod.parse_model_report(raw_text)
        self.assertEqual(parsed["likely_diagnosis"], ["diag"])
        self.assertEqual(
            self.mod.extract_switchyard_output_text({"outputText": "hello"}),
            "hello",
        )
        self.assertEqual(
            self.mod.coerce_json_text("```json\n{\"a\":1}\n```"),
            "{\"a\":1}",
        )

        parsed_string_fields = self.mod.parse_model_report(
            json.dumps(
                {
                    "observed_facts": [],
                    "likely_diagnosis": "diag",
                    "recommended_next_steps": "step",
                    "confidence": "High",
                    "limitations": "limit",
                }
            )
        )
        self.assertEqual(parsed_string_fields["likely_diagnosis"], ["diag"])
        self.assertEqual(parsed_string_fields["recommended_next_steps"], ["step"])
        self.assertEqual(parsed_string_fields["limitations"], ["limit"])
        self.assertEqual(parsed_string_fields["confidence"], "high")

    def test_provider_success_and_error_paths(self):
        switchyard_payload = {
            "text": json.dumps(
                {
                    "observed_facts": ["fact"],
                    "likely_diagnosis": ["diag"],
                    "recommended_next_steps": ["step"],
                    "confidence": "medium",
                    "limitations": ["limit"],
                }
            )
        }
        with unittest.mock.patch.object(self.mod, "post_json", return_value=switchyard_payload):
            report, error = self.mod.call_switchyard_provider(
                normalized_input={"status": {}},
                provider="gemini",
                model="gpt-4.1-mini",
                base_url="http://127.0.0.1:4010",
                timeout_sec=5,
                max_output_tokens=100,
            )
            self.assertIsNone(error)
            self.assertEqual(report["confidence"], "medium")

        with unittest.mock.patch.object(self.mod, "post_json", side_effect=urllib.error.URLError("down")):
            report, error = self.mod.call_switchyard_provider(
                normalized_input={"status": {}},
                provider="gemini",
                model="gpt-4.1-mini",
                base_url="http://127.0.0.1:4010",
                timeout_sec=5,
                max_output_tokens=100,
            )
            self.assertEqual(report, {})
            self.assertIn("switchyard_url_error", error)

        with unittest.mock.patch.object(self.mod, "post_json", return_value={"response": ""}):
            report, error = self.mod.call_switchyard_provider(
                normalized_input={"status": {}},
                provider="gemini",
                model="gemini-2.5-flash",
                base_url="http://127.0.0.1:4010",
                timeout_sec=5,
                max_output_tokens=100,
            )
            self.assertEqual(report, {})
            self.assertEqual(error, "switchyard_empty_output")

    def test_build_report_and_merge_ai_report(self):
        base = self.mod.build_report(
            self.status,
            self.doctor,
            self.log_health,
            self.aggregate,
            provider_name="gemini",
            provider_model="gemini-2.5-flash",
            provider_error=None,
            ai_used=False,
            tail=5,
        )
        self.assertEqual(base["provider"]["status"], "disabled")
        self.assertEqual(base["execution_mode"], "deterministic_only")
        self.assertEqual(base["run_change_summary"]["trend"], "no_runs")
        self.assertEqual(base["run_change_summary"]["recoverability"], "manual_review")
        self.assertEqual(base["operator_advisory"]["focus_area"], "first_run")
        self.assertEqual(base["operator_advisory"]["recoverability"], "bootstrap")
        self.assertIn("canonical system truth", " ".join(base["limitations"]))

        merged = self.mod.merge_ai_report(
            base,
            {
                "likely_diagnosis": ["The scheduler is loaded, but the ledger still needs the first successful snapshot."],
                "recommended_next_steps": ["Run ./notesctl run --no-status"],
                "confidence": "high",
                "limitations": ["AI output can still be wrong."],
            },
        )
        self.assertTrue(merged["ai_used"])
        self.assertEqual(merged["provider"]["status"], "ok")
        self.assertTrue(merged["likely_diagnosis"]["ai_inference"])
        rendered = self.mod.render_plain(merged)
        self.assertIn("Run / Change Summary", rendered)
        self.assertIn("Operator Advisory", rendered)
        self.assertIn("[AI]", rendered)
        self.assertIn("Confidence / Limitations", rendered)

    def test_main_fallback_disabled_and_command_error_paths(self):
        def fake_run(command, timeout_sec):
            mapping = {
                ("status", "--json"): (self.status, None),
                ("doctor", "--json"): (self.doctor, None),
                ("log-health", "--json", "--tail", "200"): (self.log_health, None),
                ("aggregate", "--tail", "5"): (self.aggregate, None),
            }
            return mapping[tuple(command)]

        with unittest.mock.patch.object(self.mod, "run_notesctl_json", side_effect=fake_run):
            with unittest.mock.patch.dict(os.environ, {"NOTES_SNAPSHOT_AI_ENABLE": "0"}, clear=False):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = self.mod.main(["--json"])
                self.assertEqual(code, 0)
                payload = json.loads(buf.getvalue())
                self.assertFalse(payload["ai_used"])
                self.assertEqual(payload["execution_mode"], "deterministic_only")
            self.assertIn("disabled", payload["provider"]["status"])
            self.assertIn("run_change_summary", payload)
            self.assertIn("operator_advisory", payload)

        def fake_run_with_error(command, timeout_sec):
            mapping = {
                ("status", "--json"): ({}, "command_failed:status --json:1:boom"),
                ("doctor", "--json"): (self.doctor, None),
                ("log-health", "--json", "--tail", "200"): (self.log_health, None),
                ("aggregate", "--tail", "5"): (self.aggregate, None),
            }
            return mapping[tuple(command)]

        with unittest.mock.patch.object(self.mod, "run_notesctl_json", side_effect=fake_run_with_error):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = self.mod.main(["--json"])
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["execution_mode"], "deterministic_input_error")
            self.assertEqual(payload["confidence"], "low")
            self.assertTrue(any("could not gather" in item.lower() for item in payload["limitations"]))

    def test_main_provider_branches_and_note_content_flag(self):
        def fake_run(command, timeout_sec):
            mapping = {
                ("status", "--json"): (self.status, None),
                ("doctor", "--json"): (self.doctor, None),
                ("log-health", "--json", "--tail", "200"): (self.log_health, None),
                ("aggregate", "--tail", "5"): (self.aggregate, None),
            }
            return mapping[tuple(command)]

        ai_report = {
            "observed_facts": ["fact"],
            "likely_diagnosis": ["diag"],
            "recommended_next_steps": ["next"],
            "confidence": "medium",
            "limitations": ["limit"],
        }

        with unittest.mock.patch.object(self.mod, "run_notesctl_json", side_effect=fake_run):
            with unittest.mock.patch.object(self.mod, "call_switchyard_provider", return_value=(ai_report, None)):
                with unittest.mock.patch.dict(
                    os.environ,
                    {
                        "NOTES_SNAPSHOT_AI_ENABLE": "1",
                        "NOTES_SNAPSHOT_AI_PROVIDER": "gemini",
                        "NOTES_SNAPSHOT_AI_MODEL": "gemini-2.5-flash",
                        "NOTES_SNAPSHOT_AI_ALLOW_NOTE_CONTENT": "1",
                    },
                    clear=False,
                ):
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        code = self.mod.main(["--json"])
                    self.assertEqual(code, 0)
                    payload = json.loads(buf.getvalue())
                    self.assertTrue(payload["ai_used"])
                    self.assertEqual(payload["execution_mode"], "ai_augmented")
                    self.assertEqual(payload["provider"]["status"], "ok")
                    self.assertFalse(payload["provider"]["note_content_included"])

        with unittest.mock.patch.object(self.mod, "run_notesctl_json", side_effect=fake_run):
            with unittest.mock.patch.dict(
                os.environ,
                {
                    "NOTES_SNAPSHOT_AI_ENABLE": "1",
                    "NOTES_SNAPSHOT_AI_PROVIDER": "",
                    "NOTES_SNAPSHOT_AI_MODEL": "",
                },
                clear=False,
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = self.mod.main(["--json"])
                self.assertEqual(code, 0)
                payload = json.loads(buf.getvalue())
                self.assertFalse(payload["ai_used"])
                self.assertEqual(payload["execution_mode"], "deterministic_fallback")
                self.assertTrue(payload["provider"]["enabled"])
                self.assertEqual(payload["provider"]["status"], "misconfigured")
                self.assertEqual(payload["provider"]["error"], "provider_missing")

        with unittest.mock.patch.object(self.mod, "run_notesctl_json", side_effect=fake_run):
            with unittest.mock.patch.object(self.mod, "call_switchyard_provider", return_value=({}, "switchyard_http_error:503")):
                with unittest.mock.patch.dict(
                    os.environ,
                    {
                        "NOTES_SNAPSHOT_AI_ENABLE": "1",
                        "NOTES_SNAPSHOT_AI_PROVIDER": "gemini",
                        "NOTES_SNAPSHOT_AI_MODEL": "gemini-2.5-flash",
                    },
                    clear=False,
                ):
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        code = self.mod.main(["--json"])
                    self.assertEqual(code, 0)
                    payload = json.loads(buf.getvalue())
                    self.assertFalse(payload["ai_used"])
                    self.assertEqual(payload["execution_mode"], "deterministic_fallback")
                    self.assertEqual(payload["provider"]["status"], "misconfigured")
                    self.assertEqual(payload["provider"]["error"], "switchyard_http_error:503")

    def test_main_uses_env_tail_when_flag_is_omitted(self):
        seen_commands = []

        def fake_run(command, timeout_sec):
            seen_commands.append(tuple(command))
            mapping = {
                ("status", "--json"): (self.status, None),
                ("doctor", "--json"): (self.doctor, None),
                ("log-health", "--json", "--tail", "200"): (self.log_health, None),
                ("aggregate", "--tail", "9"): (self.aggregate, None),
            }
            return mapping[tuple(command)]

        with unittest.mock.patch.object(self.mod, "run_notesctl_json", side_effect=fake_run):
            with unittest.mock.patch.dict(
                os.environ,
                {
                    "NOTES_SNAPSHOT_AI_ENABLE": "0",
                    "NOTES_SNAPSHOT_AI_DIAGNOSE_TAIL": "9",
                },
                clear=False,
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = self.mod.main(["--json"])
                self.assertEqual(code, 0)

        self.assertIn(("aggregate", "--tail", "9"), seen_commands)

    def test_phase2_run_change_and_operator_advisory_branches(self):
        no_runs_summary = self.mod.build_run_change_summary({"summary": {"recent_run_count": 0}})
        self.assertEqual(no_runs_summary["trend"], "no_runs")

        stale_aggregate = {
            "summary": {
                "recent_run_count": 5,
                "success_count": 5,
                "failed_count": 0,
                "latest_status": "success",
                "latest_trigger_source": "manual",
                "latest_success_iso": "2024-01-01T00:00:00Z",
                "current_streak": {"status": "success", "count": 5},
                "change_summary": {
                    "trend": "steady_success",
                    "summary": "The recent window is steady: the last 5 run(s) all succeeded.",
                    "previous_distinct_status": "",
                },
                "attention_state": "stable",
                "recoverability": "stable_monitoring",
                "workflow_hint": "Stay in watch mode; no immediate recovery action is required unless freshness or warnings change.",
                "status_window": {"success": 5},
                "failure_clusters": [],
            }
        }
        stale_status = {
            "health_level": "DEGRADED",
            "state_layers": {
                "ledger": {"status": "stale"},
                "launchd": {"status": "loaded"},
            },
        }
        stale_doctor = {"warnings": ["last success is stale"], "dependencies": {}}
        stale_diag = self.mod.build_deterministic_diagnosis(
            stale_status,
            stale_doctor,
            {"errors_total": 0},
            stale_aggregate,
        )
        self.assertIn("stale rather than broken", stale_diag["likely_diagnosis"][0])
        stale_advisory = self.mod.build_operator_advisory(
            stale_status,
            stale_doctor,
            {"errors_total": 0},
            stale_aggregate,
        )
        self.assertEqual(stale_advisory["focus_area"], "freshness")
        self.assertEqual(stale_advisory["recoverability"], "recoverable")
        self.assertIn("Refresh the snapshot", stale_advisory["sequence_hint"])

        recovered_aggregate = {
            "summary": {
                "recent_run_count": 3,
                "success_count": 1,
                "failed_count": 2,
                "latest_status": "success",
                "top_failure_reason": "timeout",
                "current_streak": {"status": "success", "count": 1},
                "change_summary": {
                    "trend": "recovered",
                    "summary": "The most recent run succeeded after earlier failures in the recent window.",
                    "previous_distinct_status": "failed",
                },
                "attention_state": "recovery_watch",
                "recoverability": "watch_window",
                "workflow_hint": "The latest run recovered; verify freshness and watch the next run before declaring the loop stable.",
                "status_window": {"failed": 2, "success": 1},
                "failure_clusters": [{"reason": "timeout", "count": 2}],
            }
        }
        recovered_diag = self.mod.build_deterministic_diagnosis(
            {"state_layers": {"ledger": {"status": "fresh"}, "launchd": {"status": "loaded"}}},
            {"warnings": []},
            {"errors_total": 0},
            recovered_aggregate,
        )
        self.assertIn("recovered", recovered_diag["likely_diagnosis"][0])
        recovered_advisory = self.mod.build_operator_advisory(
            {"state_layers": {"ledger": {"status": "fresh"}, "launchd": {"status": "loaded"}}},
            {"warnings": []},
            {"errors_total": 0},
            recovered_aggregate,
        )
        self.assertEqual(recovered_advisory["focus_area"], "recovery_watch")
        self.assertIn("timeout x2", recovered_advisory["anomaly_clusters"])
        self.assertEqual(recovered_advisory["recoverability"], "watch_window")

        healthy_advisory = self.mod.build_operator_advisory(
            {
                "health_level": "OK",
                "state_layers": {"ledger": {"status": "fresh"}, "launchd": {"status": "loaded"}},
            },
            {"warnings": []},
            {"errors_total": 0},
            {"summary": {"latest_status": "success", "failed_count": 0, "change_summary": {"trend": "steady_success"}}},
        )
        self.assertEqual(healthy_advisory["priority"], "low")
        self.assertEqual(healthy_advisory["recoverability"], "stable_monitoring")

        rendered = self.mod.render_plain(
            {
                "ai_used": False,
                "execution_mode": "deterministic_only",
                "provider": {"status": "disabled"},
                "observed_facts": ["fact"],
                "run_change_summary": {
                    "trend": "recovered",
                    "summary": "Recovered after earlier failures.",
                    "current_streak": {"status": "success", "count": 1},
                    "status_window": {"failed": 2, "success": 1},
                    "attention_state": "recovery_watch",
                    "recoverability": "watch_window",
                    "workflow_hint": "The latest run recovered; verify freshness and watch the next run before declaring the loop stable.",
                    "latest_trigger_source": "manual",
                    "failure_clusters": [{"reason": "timeout", "count": 2}],
                },
                "operator_advisory": {
                    "priority": "medium",
                    "focus_area": "recovery_watch",
                    "recoverability": "watch_window",
                    "summary": "Watch the next run before calling it stable.",
                    "sequence_hint": "Verify the current state, then watch the next run before you downgrade this from incident to watch-only.",
                    "recovery_path": ["Run ./notesctl verify."],
                    "anomaly_clusters": ["timeout x2"],
                },
                "likely_diagnosis": {"deterministic": ["Recovered"], "ai_inference": []},
                "recommended_next_steps": [{"source": "deterministic", "text": "Run ./notesctl verify."}],
                "confidence": "medium",
                "limitations": ["limit"],
            }
        )
        self.assertIn("Failure cluster: timeout x2", rendered)
        self.assertIn("Anomaly cluster: timeout x2", rendered)
        self.assertIn("Status window: failed=2, success=1", rendered)
        self.assertIn("Recoverability: watch_window", rendered)


if __name__ == "__main__":
    unittest.main()

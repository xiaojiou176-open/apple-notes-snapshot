import json
import tempfile
import unittest
import importlib.util
import sys
import io
import contextlib
from pathlib import Path


class AggregateRunsTests(unittest.TestCase):
    def test_aggregate_outputs_runs(self):
        repo_root = Path(__file__).resolve().parents[2]
        module_path = repo_root / "scripts" / "ops" / "aggregate_runs.py"
        spec = importlib.util.spec_from_file_location("aggregate_runs", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            metrics = tmp / "metrics.jsonl"
            structured = tmp / "structured.jsonl"

            metrics.write_text(
                "\n".join(
                    [
                        '{"event":"run_start","run_id":"rid-1","start_iso":"2024-01-01T00:00:00Z","root_dir":"/tmp","trigger_source":"manual"}',
                        '{"event":"run_end","run_id":"rid-1","end_iso":"2024-01-01T00:01:00Z","status":"success","exit_code":0}',
                        '{"event":"run_start","run_id":"rid-2","start_iso":"2024-01-02T00:00:00Z","root_dir":"/tmp","trigger_source":"web:run"}',
                        '{"event":"run_end","run_id":"rid-2","end_iso":"2024-01-02T00:01:00Z","status":"failed","exit_code":1,"failure_reason":"timeout"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            structured.write_text(
                "\n".join(
                    [
                        '{"ts":"2024-01-02T00:00:10Z","message":"start export","run_id":"rid-2","trigger_source":"web:run"}',
                        '{"ts":"2024-01-01T00:00:10Z","message":"start export","run_id":"rid-1","trigger_source":"manual"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            metrics_entries, metrics_errors = module.read_jsonl(metrics, 100)
            structured_entries, structured_errors = module.read_jsonl(structured, 100)
            self.assertEqual(metrics_errors, 0)
            self.assertEqual(structured_errors, 0)
            runs = module.aggregate(metrics_entries, structured_entries)
            self.assertEqual(len(runs), 2)
            rid2 = runs[0]
            self.assertEqual(rid2.get("run_id"), "rid-2")
            self.assertEqual(rid2.get("status"), "failed")
            self.assertIn("start export", rid2.get("log_messages", []))
            summary = module.summarize_runs(runs)
            self.assertEqual(summary.get("recent_run_count"), 2)
            self.assertEqual(summary.get("success_count"), 1)
            self.assertEqual(summary.get("failed_count"), 1)
            self.assertEqual(summary.get("latest_status"), "failed")
            self.assertEqual(summary.get("latest_trigger_source"), "web:run")
            self.assertEqual(summary.get("top_failure_reason"), "timeout")
            self.assertEqual(summary.get("current_streak", {}).get("status"), "failed")
            self.assertEqual(summary.get("current_streak", {}).get("count"), 1)
            self.assertEqual(summary.get("change_summary", {}).get("trend"), "regressed")
            self.assertEqual(summary.get("failure_clusters", [])[0].get("reason"), "timeout")
            self.assertEqual(summary.get("trigger_sources", {}).get("manual"), 1)
            self.assertEqual(summary.get("trigger_sources", {}).get("web:run"), 1)
            self.assertEqual(summary.get("attention_state"), "failure_cluster")
            self.assertEqual(summary.get("recoverability"), "recoverable")
            self.assertIn("status", summary.get("workflow_hint", ""))
            self.assertEqual(summary.get("status_window", {}).get("failed"), 1)
            self.assertEqual(summary.get("status_window", {}).get("success"), 1)

            old_argv = sys.argv[:]
            try:
                sys.argv = [
                    "aggregate_runs.py",
                    "--metrics",
                    str(metrics),
                    "--structured",
                    str(structured),
                    "--pretty",
                ]
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    code = module.main()
                self.assertEqual(code, 0)
                payload = json.loads(buffer.getvalue())
                self.assertIn("summary", payload)
                self.assertEqual(payload["summary"]["recent_run_count"], 2)
                self.assertEqual(len(payload.get("runs", [])), 2)
            finally:
                sys.argv = old_argv

    def test_aggregate_falls_back_to_state_json_when_metrics_are_empty(self):
        repo_root = Path(__file__).resolve().parents[2]
        module_path = repo_root / "scripts" / "ops" / "aggregate_runs.py"
        spec = importlib.util.spec_from_file_location("aggregate_runs", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            metrics = tmp / "metrics.jsonl"
            structured = tmp / "structured.jsonl"
            state_json = tmp / "state.json"

            metrics.write_text("", encoding="utf-8")
            structured.write_text("", encoding="utf-8")
            state_json.write_text(
                json.dumps(
                    {
                        "run_id": "rid-fallback",
                        "start_iso": "2026-04-01T00:00:00Z",
                        "end_iso": "2026-04-01T00:00:01Z",
                        "status": "success",
                        "exit_code": 0,
                        "trigger_source": "manual",
                        "root_dir": "/tmp/export-root",
                    }
                ),
                encoding="utf-8",
            )

            old_argv = sys.argv[:]
            try:
                sys.argv = [
                    "aggregate_runs.py",
                    "--metrics",
                    str(metrics),
                    "--structured",
                    str(structured),
                    "--pretty",
                ]
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    code = module.main()
                self.assertEqual(code, 0)
                payload = json.loads(buffer.getvalue())
                self.assertEqual(payload["summary"]["recent_run_count"], 1)
                self.assertEqual(payload["runs"][0]["run_id"], "rid-fallback")
                self.assertEqual(payload["runs"][0]["events"], ["state_json_fallback"])
                self.assertEqual(payload["summary"]["change_summary"]["trend"], "single_success")
                self.assertEqual(payload["summary"]["attention_state"], "stable")
                self.assertEqual(payload["summary"]["recoverability"], "stable_monitoring")
            finally:
                sys.argv = old_argv

    def test_tail_argument_limits_recent_runs_not_raw_jsonl_lines(self):
        repo_root = Path(__file__).resolve().parents[2]
        module_path = repo_root / "scripts" / "ops" / "aggregate_runs.py"
        spec = importlib.util.spec_from_file_location("aggregate_runs", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            metrics = tmp / "metrics.jsonl"
            structured = tmp / "structured.jsonl"

            metrics.write_text(
                "\n".join(
                    [
                        '{"event":"run_start","run_id":"rid-1","start_iso":"2024-01-01T00:00:00Z","root_dir":"/tmp","trigger_source":"manual"}',
                        '{"event":"run_end","run_id":"rid-1","end_iso":"2024-01-01T00:00:10Z","status":"success","exit_code":0}',
                        '{"event":"run_start","run_id":"rid-2","start_iso":"2024-01-02T00:00:00Z","root_dir":"/tmp","trigger_source":"manual"}',
                        '{"event":"run_end","run_id":"rid-2","end_iso":"2024-01-02T00:00:10Z","status":"success","exit_code":0}',
                        '{"event":"run_start","run_id":"rid-3","start_iso":"2024-01-03T00:00:00Z","root_dir":"/tmp","trigger_source":"manual"}',
                        '{"event":"run_end","run_id":"rid-3","end_iso":"2024-01-03T00:00:10Z","status":"success","exit_code":0}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            structured.write_text("", encoding="utf-8")

            old_argv = sys.argv[:]
            try:
                sys.argv = [
                    "aggregate_runs.py",
                    "--metrics",
                    str(metrics),
                    "--structured",
                    str(structured),
                    "--tail",
                    "2",
                    "--pretty",
                ]
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    code = module.main()
                self.assertEqual(code, 0)
                payload = json.loads(buffer.getvalue())
                self.assertEqual(payload["summary"]["recent_run_count"], 2)
                self.assertEqual([run["run_id"] for run in payload["runs"]], ["rid-3", "rid-2"])
                self.assertEqual(payload["summary"]["change_summary"]["trend"], "steady_success")
                self.assertEqual(payload["summary"]["current_streak"]["count"], 2)
            finally:
                sys.argv = old_argv

    def test_fallback_runs_from_state_handles_invalid_or_partial_state(self):
        repo_root = Path(__file__).resolve().parents[2]
        module_path = repo_root / "scripts" / "ops" / "aggregate_runs.py"
        spec = importlib.util.spec_from_file_location("aggregate_runs", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bad_state = tmp / "bad-state.json"
            bad_state.write_text("{not-json", encoding="utf-8")
            self.assertEqual(module.fallback_runs_from_state(bad_state), [])

            partial_state = tmp / "partial-state.json"
            partial_state.write_text(json.dumps({"status": "success"}), encoding="utf-8")
            self.assertEqual(module.fallback_runs_from_state(partial_state), [])

    def test_helper_paths_cover_invalid_json_and_recovered_clusters(self):
        repo_root = Path(__file__).resolve().parents[2]
        module_path = repo_root / "scripts" / "ops" / "aggregate_runs.py"
        spec = importlib.util.spec_from_file_location("aggregate_runs", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            metrics = tmp / "metrics.jsonl"
            metrics.write_text(
                "\n".join(
                    [
                        "",
                        "{not-json",
                        json.dumps({"event": "run_start", "run_id": "rid-1", "start_iso": "2024-01-01T00:00:00Z"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            entries, errors = module.read_jsonl(metrics, 10)
            self.assertEqual(errors, 1)
            self.assertEqual(len(entries), 1)

        runs = [
            {
                "run_id": "rid-3",
                "status": "success",
                "end_iso": "2024-01-03T00:00:00Z",
                "trigger_source": "manual",
                "failure_reason": "",
            },
            {
                "run_id": "rid-2",
                "status": "failed",
                "end_iso": "2024-01-02T00:00:00Z",
                "trigger_source": "launchd",
                "failure_reason": "timeout",
            },
            {
                "run_id": "rid-1",
                "status": "failed",
                "end_iso": "2024-01-01T00:00:00Z",
                "trigger_source": "launchd",
                "failure_reason": "timeout",
            },
        ]
        self.assertEqual(module.build_current_streak(runs)["count"], 1)
        self.assertEqual(module.build_change_summary(runs)["trend"], "recovered")
        failure_clusters = module.build_failure_clusters(runs)
        self.assertEqual(failure_clusters[0]["reason"], "timeout")
        self.assertEqual(failure_clusters[0]["count"], 2)
        attention_state = module.build_attention_state(runs, module.build_change_summary(runs))
        self.assertEqual(attention_state, "recovery_watch")
        self.assertEqual(module.build_recoverability(attention_state), "watch_window")
        self.assertIn("watch", module.build_workflow_hint(attention_state))

        unknown_summary = module.build_change_summary(
            [
                {"status": "unknown", "run_id": "rid-4"},
                {"status": "success", "run_id": "rid-3"},
            ]
        )
        self.assertEqual(unknown_summary["trend"], "mixed")

        tied_clusters = module.build_failure_clusters(
            [
                {
                    "run_id": "rid-4",
                    "status": "failed",
                    "end_iso": "2024-01-04T00:00:00Z",
                    "trigger_source": "manual",
                    "failure_reason": "recent-timeout",
                },
                {
                    "run_id": "rid-3",
                    "status": "failed",
                    "end_iso": "2024-01-03T00:00:00Z",
                    "trigger_source": "manual",
                    "failure_reason": "recent-timeout",
                },
                {
                    "run_id": "rid-2",
                    "status": "failed",
                    "end_iso": "2024-01-02T00:00:00Z",
                    "trigger_source": "manual",
                    "failure_reason": "older-timeout",
                },
                {
                    "run_id": "rid-1",
                    "status": "failed",
                    "end_iso": "2024-01-01T00:00:00Z",
                    "trigger_source": "manual",
                    "failure_reason": "older-timeout",
                },
            ]
        )
        self.assertEqual(tied_clusters[0]["reason"], "recent-timeout")
        self.assertEqual(tied_clusters[1]["reason"], "older-timeout")


if __name__ == "__main__":
    unittest.main()

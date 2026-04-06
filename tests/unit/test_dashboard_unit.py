import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path


def load_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "ops" / "dashboard_notes_snapshot.py"
    spec = importlib.util.spec_from_file_location("dashboard_notes_snapshot", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DashboardUnitTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_format_duration(self):
        self.assertEqual(self.mod.format_duration(45), "45s")
        self.assertEqual(self.mod.format_duration(125), "2m 5s")
        self.assertEqual(self.mod.format_duration("bad"), "bad")
        self.assertEqual(self.mod.format_duration(None), "unknown")
        self.assertEqual(self.mod.format_duration(61), "1m 1s")

    def test_parse_iso(self):
        dt = self.mod.parse_iso8601("2024-01-01T00:00:00Z")
        self.assertIsNotNone(dt)
        self.assertIsNone(self.mod.parse_iso8601("bad"))

    def test_compute_age_sec(self):
        self.assertEqual(self.mod.compute_age_sec(""), "unknown")
        value = self.mod.compute_age_sec("2024-01-01T00:00:00Z")
        self.assertTrue(value.isdigit())

    def test_read_json(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write("{\"status\": \"ok\"}")
            path = tmp.name
        data = self.mod.read_json(path)
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(self.mod.read_json("/no/such/file"), {})

    def test_print_plain_and_rich(self):
        summary = {"status": "success", "duration": "5s"}
        phases = {"export": 2, "convert": 1}

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.mod.print_plain(summary, phases)
        output = buf.getvalue()
        self.assertIn("Dashboard", output)
        self.assertIn("export", output)

        class FakeConsole:
            def __init__(self):
                self.rows = []
            def print(self, _table):
                self.rows.append("printed")

        class FakeTable:
            def __init__(self, *args, **kwargs):
                self.columns = []
                self.rows = []
            def add_column(self, *args, **kwargs):
                self.columns.append(args)
            def add_row(self, *args, **kwargs):
                self.rows.append(args)

        class FakeProgress:
            def __init__(self, *args, **kwargs):
                self.tasks = []
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def add_task(self, name, total=0, completed=0):
                self.tasks.append((name, total, completed))

        class FakeBar:
            def __init__(self, *args, **kwargs):
                pass

        class FakeText:
            def __init__(self, *args, **kwargs):
                pass

        class FakePanel:
            pass

        self.mod.load_rich = lambda: (FakeConsole, FakeTable, FakeProgress, FakeBar, FakeText, FakePanel)
        self.mod.print_rich(summary, phases)
        self.assertTrue(self.mod.load_rich())

    def test_load_rich_failure(self):
        original_import = __import__

        def fake_import(name, *args, **kwargs):
            if name.startswith("rich"):
                raise ImportError("no rich")
            return original_import(name, *args, **kwargs)

        try:
            builtins = __import__("builtins")
            builtins.__import__ = fake_import
            self.assertIsNone(self.mod.load_rich())
        finally:
            builtins.__import__ = original_import

    def test_print_rich_no_phases(self):
        class FakeConsole:
            def __init__(self):
                self.rows = []
            def print(self, _table):
                self.rows.append("printed")

        class FakeTable:
            def __init__(self, *args, **kwargs):
                self.rows = []
            def add_column(self, *args, **kwargs):
                pass
            def add_row(self, *args, **kwargs):
                self.rows.append(args)

        class FakeProgress:
            def __init__(self, *args, **kwargs):
                self.tasks = []
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def add_task(self, name, total=0, completed=0):
                self.tasks.append((name, total, completed))

        class FakeBar:
            def __init__(self, *args, **kwargs):
                pass

        class FakeText:
            def __init__(self, *args, **kwargs):
                pass

        class FakePanel:
            pass

        self.mod.load_rich = lambda: (FakeConsole, FakeTable, FakeProgress, FakeBar, FakeText, FakePanel)
        self.mod.print_rich({"status": "ok"}, {})

    def test_main_rich_branch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            state_dir = log_dir / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            state_json = state_dir / "state.json"
            state_json.write_text("{\"status\": \"success\"}", encoding="utf-8")
            summary = state_dir / "summary.txt"
            summary.write_text("status=success", encoding="utf-8")

            class FakeConsole:
                def __init__(self):
                    pass
                def print(self, _table):
                    pass

            class FakeTable:
                def __init__(self, *args, **kwargs):
                    pass
                def add_column(self, *args, **kwargs):
                    pass
                def add_row(self, *args, **kwargs):
                    pass

            class FakeProgress:
                def __init__(self, *args, **kwargs):
                    pass
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc, tb):
                    return False
                def add_task(self, name, total=0, completed=0):
                    pass

            class FakeBar:
                def __init__(self, *args, **kwargs):
                    pass

            class FakeText:
                def __init__(self, *args, **kwargs):
                    pass

            class FakePanel:
                pass

            old_log = os.environ.get("NOTES_SNAPSHOT_LOG_DIR")
            old_state = os.environ.get("NOTES_SNAPSHOT_STATE_DIR")
            old_load = self.mod.load_rich
            try:
                os.environ["NOTES_SNAPSHOT_LOG_DIR"] = str(log_dir)
                os.environ["NOTES_SNAPSHOT_STATE_DIR"] = str(state_dir)
                self.mod.load_rich = lambda: (FakeConsole, FakeTable, FakeProgress, FakeBar, FakeText, FakePanel)
                code = self.mod.main()
                self.assertEqual(code, 0)
            finally:
                self.mod.load_rich = old_load
                if old_log is not None:
                    os.environ["NOTES_SNAPSHOT_LOG_DIR"] = old_log
                elif "NOTES_SNAPSHOT_LOG_DIR" in os.environ:
                    del os.environ["NOTES_SNAPSHOT_LOG_DIR"]
                if old_state is not None:
                    os.environ["NOTES_SNAPSHOT_STATE_DIR"] = old_state
                elif "NOTES_SNAPSHOT_STATE_DIR" in os.environ:
                    del os.environ["NOTES_SNAPSHOT_STATE_DIR"]

    def test_main_smoke(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            state_dir = log_dir / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            state_json = state_dir / "state.json"
            state_json.write_text(
                '{"status": "success", "exit_code": 0, "duration_sec": 5, "end_iso": "2024-01-01T00:00:00Z", "last_success_iso": "2024-01-01T00:00:00Z", "phases": {"export": 2}}',
                encoding="utf-8",
            )
            summary = state_dir / "summary.txt"
            summary.write_text("status=success", encoding="utf-8")
            metrics = state_dir / "metrics.jsonl"
            metrics.write_text(
                "\n".join(
                    [
                        '{"event":"run_start","run_id":"rid-1","start_iso":"2024-01-01T00:00:00Z","root_dir":"/tmp","trigger_source":"manual"}',
                        '{"event":"run_end","run_id":"rid-1","end_iso":"2024-01-01T00:01:00Z","status":"success","exit_code":0}'
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            old_log = os.environ.get("NOTES_SNAPSHOT_LOG_DIR")
            old_state = os.environ.get("NOTES_SNAPSHOT_STATE_DIR")
            try:
                os.environ["NOTES_SNAPSHOT_LOG_DIR"] = str(log_dir)
                os.environ["NOTES_SNAPSHOT_STATE_DIR"] = str(state_dir)
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = self.mod.main()
                self.assertEqual(code, 0)
                self.assertIn("Dashboard", buf.getvalue())
                self.assertIn("recent_runs", buf.getvalue())
                self.assertIn("recent_trend", buf.getvalue())
                self.assertIn("attention_state", buf.getvalue())
                self.assertIn("recoverability", buf.getvalue())
                self.assertIn("workflow_hint", buf.getvalue())
            finally:
                if old_log is not None:
                    os.environ["NOTES_SNAPSHOT_LOG_DIR"] = old_log
                elif "NOTES_SNAPSHOT_LOG_DIR" in os.environ:
                    del os.environ["NOTES_SNAPSHOT_LOG_DIR"]
                if old_state is not None:
                    os.environ["NOTES_SNAPSHOT_STATE_DIR"] = old_state
                elif "NOTES_SNAPSHOT_STATE_DIR" in os.environ:
                    del os.environ["NOTES_SNAPSHOT_STATE_DIR"]


if __name__ == "__main__":
    unittest.main()

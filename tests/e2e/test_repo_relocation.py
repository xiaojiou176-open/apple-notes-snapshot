import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RepoRelocationE2ETests(unittest.TestCase):
    def test_rebuild_dev_env_print_only_uses_current_repo_root(self):
        repo_root = Path(__file__).resolve().parents[2]

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir) / "repo"
            temp_root.mkdir(parents=True, exist_ok=True)

            for name in ("scripts", "vendor", "requirements-dev.txt"):
                src = repo_root / name
                dst = temp_root / name
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            script = temp_root / "scripts" / "ops" / "rebuild_dev_env.zsh"
            result = subprocess.run(
                ["/bin/zsh", str(script), "--print-only"],
                cwd=str(temp_root),
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            values = {}
            for line in result.stdout.splitlines():
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key] = value

            self.assertEqual(Path(values["repo_root"]).resolve(), temp_root.resolve())
            self.assertEqual(
                Path(values["venv_dir"]).resolve(),
                (temp_root / ".runtime-cache" / "dev" / "venv").resolve(),
            )
            legacy_name = "Notes" + "Sync"
            self.assertNotIn(legacy_name, result.stdout)
            self.assertNotIn(str(repo_root), result.stdout)

    def test_rebuild_dev_env_recreates_a_clean_venv(self):
        repo_root = Path(__file__).resolve().parents[2]

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir) / "repo"
            temp_root.mkdir(parents=True, exist_ok=True)

            for name in ("scripts", "vendor", "requirements-dev.txt"):
                src = repo_root / name
                dst = temp_root / name
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            script = temp_root / "scripts" / "ops" / "rebuild_dev_env.zsh"
            python_bin = str(Path(sys.executable).resolve())
            first = subprocess.run(
                ["/bin/zsh", str(script), "--python", python_bin],
                cwd=str(temp_root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            stale_marker = temp_root / ".runtime-cache" / "dev" / "venv" / "stale.txt"
            stale_marker.write_text("stale\n", encoding="utf-8")

            second = subprocess.run(
                ["/bin/zsh", str(script), "--python", python_bin],
                cwd=str(temp_root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertFalse(stale_marker.exists(), "rebuild should replace the existing venv")

            cfg = (temp_root / ".runtime-cache" / "dev" / "venv" / "pyvenv.cfg").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                f"version = {sys.version_info.major}.{sys.version_info.minor}",
                cfg,
            )

    def test_rebuild_dev_env_print_only_prefers_versioned_homebrew_python(self):
        repo_root = Path(__file__).resolve().parents[2]
        python_313 = Path("/opt/homebrew/bin/python3.13")
        python_314 = Path("/opt/homebrew/bin/python3.14")

        if not python_313.exists() or not python_314.exists():
            self.skipTest("requires Homebrew Python 3.13 and 3.14 to be installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir) / "repo"
            temp_root.mkdir(parents=True, exist_ok=True)

            for name in ("scripts", "vendor", "requirements-dev.txt"):
                src = repo_root / name
                dst = temp_root / name
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            temp_brew = Path(tmpdir) / "homebrew"
            temp_bin = temp_brew / "bin"
            temp_bin.mkdir(parents=True, exist_ok=True)
            (temp_bin / "python3").symlink_to(python_314)
            (temp_bin / "python3.13").symlink_to(python_313)

            script = temp_root / "scripts" / "ops" / "rebuild_dev_env.zsh"
            result = subprocess.run(
                ["/bin/zsh", str(script), "--print-only"],
                cwd=str(temp_root),
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "HOMEBREW_PREFIX": str(temp_brew)},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            values = {}
            for line in result.stdout.splitlines():
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key] = value

            self.assertEqual(values["python_bin"], str(temp_bin / "python3.13"))


if __name__ == "__main__":
    unittest.main()

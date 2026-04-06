import subprocess
import unittest
from pathlib import Path


class NotesctlHelpSurfaceUnitTests(unittest.TestCase):
    def test_top_level_help_splits_user_optional_and_maintainer_lanes(self):
        repo_root = Path(__file__).resolve().parents[2]

        result = subprocess.run(
            [str(repo_root / "notesctl"), "--help"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Primary user lane:", result.stdout)
        self.assertIn("Optional AI and agent-facing surfaces:", result.stdout)
        self.assertIn("Maintainer lane:", result.stdout)
        self.assertIn("clean-cache             preview/remove local caches", result.stdout)
        self.assertIn("runtime-audit           inspect repo-local and external repo-owned runtime/cache residue", result.stdout)
        self.assertIn("clean-runtime           preview/remove external repo-owned runtime/cache residue", result.stdout)
        self.assertIn("browser-bootstrap       bootstrap the isolated Chrome root from the default Chrome root", result.stdout)
        self.assertIn("browser-open            launch or attach to the single repo-owned Chrome instance", result.stdout)
        self.assertIn("browser-contract        validate the isolated root + single instance + CDP attach-first contract", result.stdout)
        self.assertIn("ai-diagnose             operator next-step assistant", result.stdout)
        self.assertIn("mcp                     start the stdio-first MCP provider for MCP-aware hosts", result.stdout)
        self.assertIn("web                     start the local Web UI + token-gated Local Web API", result.stdout)

    def test_web_help_explains_local_web_api_contract(self):
        repo_root = Path(__file__).resolve().parents[2]

        result = subprocess.run(
            [str(repo_root / "notesctl"), "help", "web"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("token-gated local browser control room plus same-machine Local Web API", result.stdout)
        self.assertIn("/api/status", result.stdout)
        self.assertIn("does not become a public OpenAPI", result.stdout)

    def test_audit_help_explains_local_web_security_contract(self):
        repo_root = Path(__file__).resolve().parents[2]

        result = subprocess.run(
            [str(repo_root / "notesctl"), "help", "audit"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("inspect the local Web surface security contract", result.stdout)
        self.assertIn("token, scope, allowlist, readonly, and rate-limit settings", result.stdout)
        self.assertIn("./notesctl audit --json", result.stdout)

    def test_runtime_and_browser_help_surface_explains_new_contracts(self):
        repo_root = Path(__file__).resolve().parents[2]

        runtime_result = subprocess.run(
            [str(repo_root / "notesctl"), "help", "runtime-audit"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(runtime_result.returncode, 0, runtime_result.stderr)
        self.assertIn("repo-local and external repo-owned runtime residue", runtime_result.stdout)
        self.assertIn("current machine-cache entries for launchd, runtime, repo copies, and disposable browser temp state", runtime_result.stdout)
        self.assertIn("repo-managed isolated Chrome root", runtime_result.stdout)
        self.assertIn("does not scan system temp roots, Docker, or shared tool caches", runtime_result.stdout)

        browser_result = subprocess.run(
            [str(repo_root / "notesctl"), "help", "browser-contract"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(browser_result.returncode, 0, browser_result.stderr)
        self.assertIn('NOTES_SNAPSHOT_BROWSER_PROVIDER must stay "chrome"', browser_result.stdout)
        self.assertIn("single repo-owned Chrome instance", browser_result.stdout)
        self.assertIn("NOTES_SNAPSHOT_CHROME_CDP_HOST/PORT define the attach endpoint", browser_result.stdout)
        self.assertIn("./notesctl browser-contract --json", browser_result.stdout)

        clean_result = subprocess.run(
            [str(repo_root / "notesctl"), "help", "clean-runtime"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(clean_result.returncode, 0, clean_result.stderr)
        self.assertIn("repo-managed machine cache root for launchd, runtime, repo copies, and disposable browser temp state", clean_result.stdout)
        self.assertIn("repo-managed isolated browser root is always protected", clean_result.stdout)
        self.assertIn("repo-local caches (.runtime-cache/*) -> use ./notesctl clean-cache", clean_result.stdout)

        bootstrap_result = subprocess.run(
            [str(repo_root / "notesctl"), "help", "browser-bootstrap"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(bootstrap_result.returncode, 0, bootstrap_result.stderr)
        self.assertIn("create the isolated repo-owned Chrome root", bootstrap_result.stdout)
        self.assertIn("Profile 1", bootstrap_result.stdout)

        open_result = subprocess.run(
            [str(repo_root / "notesctl"), "help", "browser-open"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(open_result.returncode, 0, open_result.stderr)
        self.assertIn("single repo-owned Chrome instance", open_result.stdout)
        self.assertIn("CDP", open_result.stdout)


if __name__ == "__main__":
    unittest.main()

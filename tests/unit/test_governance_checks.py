import importlib.util
import os
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path


def load_module(module_name: str, relative_path: str):
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sanitized_git_env():
    env = os.environ.copy()
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_PREFIX",
    ):
        env.pop(name, None)
    return env


def git_run(repo_root: Path, *args: str):
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        env=sanitized_git_env(),
    )


class GovernanceCheckTests(unittest.TestCase):
    def test_workflows_do_not_reintroduce_self_hosted_runner_lane(self):
        repo_root = Path(__file__).resolve().parents[2]
        for workflow in (repo_root / ".github" / "workflows").glob("*.yml"):
            content = workflow.read_text(encoding="utf-8")
            self.assertNotIn("self-hosted", content, f"unexpected self-hosted runner in {workflow.name}")

    def test_agents_contract_requires_execution_hygiene_phrases(self):
        mod = load_module(
            "docs_link_root_hygiene",
            "scripts/checks/docs_link_root_hygiene.py",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            agents = repo_root / "AGENTS.md"
            agents.write_text(
                "# Agent Guide\n\n## Execution hygiene\n- Chrome / Chromium\n",
                encoding="utf-8",
            )

            original_root = mod.REPO_ROOT
            try:
                mod.REPO_ROOT = repo_root
                failures = mod.validate_agents_contract()
                self.assertIn(
                    "AGENTS.md missing required contract phrase: more than 6 Chrome/Chromium instances",
                    failures,
                )
                self.assertIn(
                    "AGENTS.md missing required contract phrase: GitHub repo collaboration writes are allowed only",
                    failures,
                )
                self.assertIn(
                    "AGENTS.md missing required contract phrase: Every non-GitHub external control plane stays read-only",
                    failures,
                )

                agents.write_text(
                    "\n".join(
                        [
                            "# Agent Guide",
                            "",
                            "## Execution hygiene",
                            "- Chrome / Chromium",
                            "- If the machine already has more than 6 Chrome/Chromium instances in play, do not open another one.",
                            "- GitHub repo collaboration writes are allowed only when the current task explicitly includes repo branch / PR / review / merge / release closeout.",
                            "- Every non-GitHub external control plane stays read-only by default.",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                failures = mod.validate_agents_contract()
                self.assertEqual(failures, [])
            finally:
                mod.REPO_ROOT = original_root
    def test_repo_surface_hygiene_requires_tracked_public_surface(self):
        mod = load_module(
            "docs_link_root_hygiene",
            "scripts/checks/docs_link_root_hygiene.py",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            for name in (
                "README.md",
                "CHANGELOG.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "AGENTS.md",
                "LICENSE",
                ".env.example",
                "pytest.ini",
                "requirements-dev.txt",
                "notesctl",
            ):
                (repo_root / name).write_text("ok\n", encoding="utf-8")
            for dirname in (
                "config",
                "scripts",
                "tests",
                "vendor",
                "web",
                "docs/quickstart",
                "docs/compare",
                "docs/faq",
                "docs/security",
                "docs/for-agents/public-skills",
                "docs/media/30-second-overview",
                "docs/media/founder-note",
                "docs/.well-known",
                "examples/public-skills",
                ".github/workflows",
                ".github/ISSUE_TEMPLATE",
            ):
                (repo_root / dirname).mkdir(parents=True, exist_ok=True)
            (repo_root / "docs/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/quickstart/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/compare/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/faq/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/security/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/for-agents/public-skills/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/media/30-second-overview/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/media/founder-note/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/.well-known/security.txt").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/styles.css").write_text("ok\n", encoding="utf-8")
            (repo_root / "examples/public-skills/README.md").write_text("ok\n", encoding="utf-8")
            (repo_root / "examples/public-skills/repo-truthful-positioning.md").write_text("ok\n", encoding="utf-8")
            (repo_root / "examples/public-skills/agent-surfaces-contracts.md").write_text("ok\n", encoding="utf-8")
            (repo_root / "examples/public-skills/runtime-resource-hygiene.md").write_text("ok\n", encoding="utf-8")
            (repo_root / ".github/workflows/trusted-ci.yml").write_text("name: trusted\n", encoding="utf-8")
            (repo_root / ".github/ISSUE_TEMPLATE/security-contact-request.yml").write_text(
                "name: security\n",
                encoding="utf-8",
            )
            (repo_root / ".github/CODEOWNERS").write_text("* @example\n", encoding="utf-8")
            (repo_root / ".github/PULL_REQUEST_TEMPLATE.md").write_text(
                "## Summary\n",
                encoding="utf-8",
            )

            git_run(repo_root, "init")
            tracked = [
                "README.md",
                "CHANGELOG.md",
                "CONTRIBUTING.md",
                "LICENSE",
                ".env.example",
                "pytest.ini",
                "requirements-dev.txt",
                "notesctl",
                "docs/index.html",
                "docs/quickstart/index.html",
                "docs/compare/index.html",
                "docs/faq/index.html",
                "docs/security/index.html",
                "docs/media/30-second-overview/index.html",
                "docs/media/founder-note/index.html",
                "docs/.well-known/security.txt",
                "docs/styles.css",
                ".github/ISSUE_TEMPLATE/security-contact-request.yml",
                ".github/workflows/trusted-ci.yml",
            ]
            git_run(repo_root, "add", "--", *tracked)

            original_root = mod.REPO_ROOT
            try:
                mod.REPO_ROOT = repo_root
                self.assertIn(
                    "docs/for-agents/public-skills/index.html",
                    mod.REQUIRED_TRACKED_PATHS,
                )
                self.assertIn(
                    "examples/public-skills/runtime-resource-hygiene.md",
                    mod.REQUIRED_TRACKED_PATHS,
                )
                self.assertIn(
                    "docs/for-agents/public-skills/index.html",
                    mod.DOC_SURFACE_PATHS,
                )
                self.assertIn(
                    "examples/public-skills/runtime-resource-hygiene.md",
                    mod.DOC_SURFACE_PATHS,
                )
                failures = mod.validate_tracked_public_surface()
                self.assertIn(
                    "public surface entry not tracked by git: SECURITY.md",
                    failures,
                )
                self.assertIn(
                    "public surface entry not tracked by git: AGENTS.md",
                    failures,
                )
                self.assertIn(
                    "public surface entry not tracked by git: .github/CODEOWNERS",
                    failures,
                )
                self.assertIn(
                    "public surface entry not tracked by git: .github/PULL_REQUEST_TEMPLATE.md",
                    failures,
                )
                git_run(
                    repo_root,
                    "add",
                    "--",
                    "SECURITY.md",
                    "AGENTS.md",
                    ".github/CODEOWNERS",
                    ".github/PULL_REQUEST_TEMPLATE.md",
                    "docs/for-agents/public-skills/index.html",
                    "examples/public-skills/README.md",
                    "examples/public-skills/repo-truthful-positioning.md",
                    "examples/public-skills/agent-surfaces-contracts.md",
                    "examples/public-skills/runtime-resource-hygiene.md",
                )
                failures = mod.validate_tracked_public_surface()
                self.assertNotIn(
                    "public surface entry not tracked by git: SECURITY.md",
                    failures,
                )
                self.assertNotIn(
                    "public surface entry not tracked by git: AGENTS.md",
                    failures,
                )
                self.assertNotIn(
                    "public surface entry not tracked by git: .github/CODEOWNERS",
                    failures,
                )
                self.assertNotIn(
                    "public surface entry not tracked by git: .github/PULL_REQUEST_TEMPLATE.md",
                    failures,
                )
            finally:
                mod.REPO_ROOT = original_root

    def test_root_hygiene_allows_docs_and_rejects_legacy_localized_surface(self):
        mod = load_module(
            "docs_link_root_hygiene",
            "scripts/checks/docs_link_root_hygiene.py",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "docs").mkdir()
            (repo_root / "README.zh-CN.md").write_text("legacy\n", encoding="utf-8")

            original_root = mod.REPO_ROOT
            try:
                mod.REPO_ROOT = repo_root
                failures = mod.validate_root_hygiene()
                self.assertNotIn("forbidden legacy root entry present: docs", failures)
                self.assertIn(
                    "forbidden legacy root entry present: README.zh-CN.md",
                    failures,
                )
            finally:
                mod.REPO_ROOT = original_root

    def test_legacy_path_scan_checks_root_docs(self):
        mod = load_module("legacy_path_scan", "scripts/checks/legacy_path_scan.py")

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            readme = repo_root / "README.md"
            legacy_path = "/".join(["", "Users", "example", "Notes" + "Sync"])
            readme.write_text(f"legacy {legacy_path}\n", encoding="utf-8")

            original_root = mod.REPO_ROOT
            original_dirs = mod.SCAN_DIRS
            original_files = mod.SCAN_FILES
            try:
                mod.REPO_ROOT = repo_root
                mod.SCAN_DIRS = ()
                mod.SCAN_FILES = (readme,)
                self.assertEqual(mod.main(), 1)
            finally:
                mod.REPO_ROOT = original_root
                mod.SCAN_DIRS = original_dirs
                mod.SCAN_FILES = original_files

    def test_legacy_path_scan_checks_html_docs(self):
        mod = load_module("legacy_path_scan", "scripts/checks/legacy_path_scan.py")

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            doc = repo_root / "docs" / "index.html"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text(
                "<p>" + "/".join(("", "Users", "example", "private")) + "</p>\n",
                encoding="utf-8",
            )

            original_root = mod.REPO_ROOT
            original_dirs = mod.SCAN_DIRS
            original_files = mod.SCAN_FILES
            try:
                mod.REPO_ROOT = repo_root
                mod.SCAN_DIRS = (repo_root / "docs",)
                mod.SCAN_FILES = ()
                self.assertEqual(mod.main(), 1)
            finally:
                mod.REPO_ROOT = original_root
                mod.SCAN_DIRS = original_dirs
                mod.SCAN_FILES = original_files

    def test_legacy_path_scan_rejects_personal_launchd_namespace(self):
        mod = load_module("legacy_path_scan", "scripts/checks/legacy_path_scan.py")

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            config = repo_root / "config" / "notes_snapshot.env"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                'NOTES_SNAPSHOT_LAUNCHD_LABEL="' + ".".join(("com", "realperson", "apple-notes-snapshot")) + '"\n',
                encoding="utf-8",
            )

            original_root = mod.REPO_ROOT
            original_dirs = mod.SCAN_DIRS
            original_files = mod.SCAN_FILES
            try:
                mod.REPO_ROOT = repo_root
                mod.SCAN_DIRS = (repo_root / "config",)
                mod.SCAN_FILES = ()
                self.assertEqual(mod.main(), 1)
            finally:
                mod.REPO_ROOT = original_root
                mod.SCAN_DIRS = original_dirs
                mod.SCAN_FILES = original_files

    def test_legacy_path_scan_allows_placeholder_launchd_namespace(self):
        mod = load_module("legacy_path_scan", "scripts/checks/legacy_path_scan.py")

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            config = repo_root / "config" / "notes_snapshot.env"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(
                'NOTES_SNAPSHOT_LAUNCHD_LABEL="local.apple-notes-snapshot.custom"\n',
                encoding="utf-8",
            )

            original_root = mod.REPO_ROOT
            original_dirs = mod.SCAN_DIRS
            original_files = mod.SCAN_FILES
            try:
                mod.REPO_ROOT = repo_root
                mod.SCAN_DIRS = (repo_root / "config",)
                mod.SCAN_FILES = ()
                self.assertEqual(mod.main(), 0)
            finally:
                mod.REPO_ROOT = original_root
                mod.SCAN_DIRS = original_dirs
                mod.SCAN_FILES = original_files

    def test_public_surface_sensitive_scan_rejects_machine_cache_root(self):
        mod = load_module(
            "public_surface_sensitive_scan",
            "scripts/checks/public_surface_sensitive_scan.py",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            readme = repo_root / "README.md"
            readme.write_text(
                "cache root lives under " + "~/" + ".cache" + "/apple-notes-snapshot/browser\n",
                encoding="utf-8",
            )

            original_root = mod.REPO_ROOT
            original_dirs = mod.SCAN_DIRS
            original_files = mod.SCAN_FILES
            try:
                mod.REPO_ROOT = repo_root
                mod.SCAN_DIRS = ()
                mod.SCAN_FILES = (readme,)
                self.assertEqual(mod.main(), 1)
            finally:
                mod.REPO_ROOT = original_root
                mod.SCAN_DIRS = original_dirs
                mod.SCAN_FILES = original_files

    def test_public_surface_sensitive_scan_rejects_public_email(self):
        mod = load_module(
            "public_surface_sensitive_scan",
            "scripts/checks/public_surface_sensitive_scan.py",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            doc = repo_root / "docs" / "index.html"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text("contact me at " + "person@" + "mail.test\n", encoding="utf-8")

            original_root = mod.REPO_ROOT
            original_dirs = mod.SCAN_DIRS
            original_files = mod.SCAN_FILES
            try:
                mod.REPO_ROOT = repo_root
                mod.SCAN_DIRS = (repo_root / "docs",)
                mod.SCAN_FILES = ()
                self.assertEqual(mod.main(), 1)
            finally:
                mod.REPO_ROOT = original_root
                mod.SCAN_DIRS = original_dirs
                mod.SCAN_FILES = original_files

    def test_public_surface_sensitive_scan_allows_repo_relative_runtime_path(self):
        mod = load_module(
            "public_surface_sensitive_scan",
            "scripts/checks/public_surface_sensitive_scan.py",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            readme = repo_root / "README.md"
            readme.write_text(
                "run ./.runtime-cache/dev/venv/bin/python -m pre_commit run --all-files\n",
                encoding="utf-8",
            )

            original_root = mod.REPO_ROOT
            original_dirs = mod.SCAN_DIRS
            original_files = mod.SCAN_FILES
            try:
                mod.REPO_ROOT = repo_root
                mod.SCAN_DIRS = ()
                mod.SCAN_FILES = (readme,)
                self.assertEqual(mod.main(), 0)
            finally:
                mod.REPO_ROOT = original_root
                mod.SCAN_DIRS = original_dirs
                mod.SCAN_FILES = original_files

    def test_repo_surface_hygiene_rejects_forbidden_tracked_runtime_surfaces(self):
        mod = load_module(
            "docs_link_root_hygiene",
            "scripts/checks/docs_link_root_hygiene.py",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            for name in (
                "README.md",
                "CHANGELOG.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "AGENTS.md",
                "LICENSE",
                ".env.example",
                "pytest.ini",
                "requirements-dev.txt",
                "notesctl",
            ):
                (repo_root / name).write_text("ok\n", encoding="utf-8")
            for dirname in (
                "config",
                "scripts",
                "tests",
                "vendor",
                "web",
                ".github/workflows",
                ".github/ISSUE_TEMPLATE",
                ".runtime-cache/logs",
                "log",
            ):
                (repo_root / dirname).mkdir(parents=True, exist_ok=True)
            (repo_root / ".github/workflows/trusted-ci.yml").write_text("name: trusted\n", encoding="utf-8")
            (repo_root / ".github/ISSUE_TEMPLATE/security-contact-request.yml").write_text(
                "name: security\n",
                encoding="utf-8",
            )
            (repo_root / ".github/CODEOWNERS").write_text("* @example\n", encoding="utf-8")
            (repo_root / ".github/PULL_REQUEST_TEMPLATE.md").write_text(
                "## Summary\n",
                encoding="utf-8",
            )
            (repo_root / ".runtime-cache/logs/runtime.log").write_text("noise\n", encoding="utf-8")
            (repo_root / "log/runtime.log").write_text("noise\n", encoding="utf-8")

            git_run(repo_root, "init")
            tracked = [
                "README.md",
                "CHANGELOG.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "AGENTS.md",
                "LICENSE",
                ".env.example",
                "pytest.ini",
                "requirements-dev.txt",
                "notesctl",
                ".github/CODEOWNERS",
                ".github/PULL_REQUEST_TEMPLATE.md",
                ".github/ISSUE_TEMPLATE/security-contact-request.yml",
                ".github/workflows/trusted-ci.yml",
                ".runtime-cache/logs/runtime.log",
                "log/runtime.log",
            ]
            git_run(repo_root, "add", "--", *tracked)

            original_root = mod.REPO_ROOT
            try:
                mod.REPO_ROOT = repo_root
                failures = mod.validate_forbidden_tracked_paths()
                self.assertIn(
                    "forbidden tracked log artifact: .runtime-cache/logs/runtime.log",
                    failures,
                )
                self.assertIn(
                    "forbidden tracked log artifact: log/runtime.log",
                    failures,
                )
            finally:
                mod.REPO_ROOT = original_root

    def test_repo_surface_hygiene_ignores_outer_git_env_pollution(self):
        mod = load_module(
            "docs_link_root_hygiene",
            "scripts/checks/docs_link_root_hygiene.py",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            for name in (
                "README.md",
                "CHANGELOG.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "AGENTS.md",
                "LICENSE",
                ".env.example",
                "pytest.ini",
                "requirements-dev.txt",
                "notesctl",
            ):
                (repo_root / name).write_text("ok\n", encoding="utf-8")
            for dirname in (
                "config",
                "scripts",
                "tests",
                "vendor",
                "web",
                "docs/quickstart",
                "docs/compare",
                "docs/faq",
                "docs/security",
                "docs/media/30-second-overview",
                "docs/media/founder-note",
                "docs/.well-known",
                ".github/workflows",
                ".github/ISSUE_TEMPLATE",
            ):
                (repo_root / dirname).mkdir(parents=True, exist_ok=True)
            (repo_root / "docs/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/quickstart/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/compare/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/faq/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/security/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/media/30-second-overview/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/media/founder-note/index.html").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/.well-known/security.txt").write_text("ok\n", encoding="utf-8")
            (repo_root / "docs/styles.css").write_text("ok\n", encoding="utf-8")
            (repo_root / ".github/workflows/trusted-ci.yml").write_text("name: trusted\n", encoding="utf-8")
            (repo_root / ".github/ISSUE_TEMPLATE/security-contact-request.yml").write_text(
                "name: security\n",
                encoding="utf-8",
            )
            (repo_root / ".github/CODEOWNERS").write_text("* @example\n", encoding="utf-8")
            (repo_root / ".github/PULL_REQUEST_TEMPLATE.md").write_text(
                "## Summary\n",
                encoding="utf-8",
            )

            git_run(repo_root, "init")
            tracked = [
                "README.md",
                "CHANGELOG.md",
                "CONTRIBUTING.md",
                "LICENSE",
                ".env.example",
                "pytest.ini",
                "requirements-dev.txt",
                "notesctl",
                "docs/index.html",
                "docs/quickstart/index.html",
                "docs/compare/index.html",
                "docs/faq/index.html",
                "docs/security/index.html",
                "docs/media/30-second-overview/index.html",
                "docs/media/founder-note/index.html",
                "docs/.well-known/security.txt",
                "docs/styles.css",
                ".github/ISSUE_TEMPLATE/security-contact-request.yml",
                ".github/workflows/trusted-ci.yml",
            ]
            git_run(repo_root, "add", "--", *tracked)

            original_root = mod.REPO_ROOT
            try:
                mod.REPO_ROOT = repo_root
                with unittest.mock.patch.dict(
                    os.environ,
                    {
                        "GIT_DIR": str(Path(__file__).resolve().parents[2] / ".git"),
                        "GIT_WORK_TREE": str(Path(__file__).resolve().parents[2]),
                    },
                    clear=False,
                ):
                    failures = mod.validate_tracked_public_surface()
                self.assertIn(
                    "public surface entry not tracked by git: SECURITY.md",
                    failures,
                )
                self.assertIn(
                    "public surface entry not tracked by git: AGENTS.md",
                    failures,
                )
            finally:
                mod.REPO_ROOT = original_root

    def test_repo_surface_hygiene_rejects_non_english_doc_surface(self):
        mod = load_module(
            "docs_link_root_hygiene",
            "scripts/checks/docs_link_root_hygiene.py",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            readme = repo_root / "README.md"
            readme.write_text(
                "English only\n" + chr(0x4E2D) + chr(0x6587) + "\n",
                encoding="utf-8",
            )

            original_root = mod.REPO_ROOT
            try:
                mod.REPO_ROOT = repo_root
                failures = mod.validate_english_doc_surface()
                self.assertIn(
                    "non-English text found in repo-owned doc surface: README.md",
                    failures,
                )
            finally:
                mod.REPO_ROOT = original_root

    def test_html_link_validation_rejects_missing_local_targets(self):
        mod = load_module(
            "docs_link_root_hygiene",
            "scripts/checks/docs_link_root_hygiene.py",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            html = repo_root / "docs" / "index.html"
            html.parent.mkdir(parents=True, exist_ok=True)
            html.write_text(
                '<a href="./quickstart/index.html">Quickstart</a><img src="./assets/hero.png" />',
                encoding="utf-8",
            )
            (repo_root / "docs" / "quickstart").mkdir(parents=True, exist_ok=True)
            (repo_root / "docs" / "quickstart" / "index.html").write_text("ok\n", encoding="utf-8")

            original_root = mod.REPO_ROOT
            try:
                mod.REPO_ROOT = repo_root
                failures = mod.validate_html_links()
                self.assertIn(
                    "docs/index.html: missing html link target -> ./assets/hero.png",
                    failures,
                )
                (repo_root / "docs" / "assets").mkdir(parents=True, exist_ok=True)
                (repo_root / "docs" / "assets" / "hero.png").write_text("ok\n", encoding="utf-8")
                failures = mod.validate_html_links()
                self.assertEqual(failures, [])
            finally:
                mod.REPO_ROOT = original_root

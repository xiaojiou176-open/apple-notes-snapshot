import json
import os
import subprocess
import unittest
from pathlib import Path


class PluginBundleManifestUnitTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[2]
        self.claude_marketplace = self.repo_root / ".claude-plugin" / "marketplace.json"
        self.codex_marketplace = self.repo_root / ".codex-plugin" / "marketplace.json"
        self.plugin_root = self.repo_root / "plugins" / "apple-notes-snapshot-control-room"

    def test_marketplace_manifests_reference_the_bundle(self):
        for manifest_path in (self.claude_marketplace, self.codex_marketplace):
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["plugins"][0]["name"], "apple-notes-snapshot-control-room")
            source = payload["plugins"][0]["source"]
            self.assertTrue((self.repo_root / source).exists(), source)

        claude_payload = json.loads(self.claude_marketplace.read_text(encoding="utf-8"))
        self.assertEqual(
            claude_payload["metadata"]["description"],
            "Repo-owned local marketplace for the Apple Notes Snapshot control-room plugin bundle.",
        )

    def test_bundle_contains_plugin_contract_files(self):
        required_paths = [
            self.plugin_root / ".claude-plugin" / "plugin.json",
            self.plugin_root / ".codex-plugin" / "plugin.json",
            self.plugin_root / ".mcp.json",
            self.plugin_root / "commands" / "notes-snapshot-preflight.md",
            self.plugin_root / "skills" / "notes-snapshot-control-room" / "SKILL.md",
            self.plugin_root / "scripts" / "notes_snapshot_mcp.sh",
            self.plugin_root / "README.md",
        ]
        for path in required_paths:
            self.assertTrue(path.exists(), str(path))

    def test_resolver_script_finds_repo_owned_notesctl(self):
        resolver = self.plugin_root / "scripts" / "notes_snapshot_mcp.sh"
        env = os.environ.copy()
        env["APPLE_NOTES_SNAPSHOT_REPO_ROOT"] = str(self.repo_root)
        result = subprocess.run(
            [str(resolver), "--print-path"],
            cwd=str(self.repo_root),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.repo_root / "notesctl"))


if __name__ == "__main__":
    unittest.main()

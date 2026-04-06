import json
import subprocess
import unittest
from pathlib import Path


class BuilderContractManifestUnitTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[2]
        self.manifest_path = self.repo_root / "examples" / "integration-pack" / "builder-contract.manifest.json"
        self.payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def test_manifest_has_expected_identity_and_surface_ids(self):
        self.assertEqual(self.payload["schema_version"], 1)
        self.assertEqual(self.payload["artifact"], "builder-contract-manifest")
        self.assertEqual(
            self.payload["product"]["identity"],
            "Apple Notes local-first backup control room for macOS",
        )
        surface_ids = {surface["id"] for surface in self.payload["builder_surfaces"]}
        self.assertEqual(surface_ids, {"cli", "local-web-api", "ai-diagnose", "mcp"})

    def test_manifest_host_proof_levels_and_assets_are_truthful(self):
        hosts = {host["id"]: host for host in self.payload["hosts"]}
        self.assertEqual(hosts["generic-mcp-aware-host"]["proof_level"], "repo-side proven")
        self.assertEqual(hosts["codex"]["proof_level"], "host-side verify required")
        self.assertEqual(hosts["claude-code"]["proof_level"], "attach-proven")
        self.assertEqual(hosts["opencode"]["proof_level"], "template-only")
        self.assertEqual(hosts["openhands"]["proof_level"], "comparison-only")
        self.assertEqual(hosts["openclaw"]["proof_level"], "host-side verify required")
        self.assertIn(".claude-plugin/marketplace.json", hosts["claude-code"]["copyable_assets"])
        self.assertIn(".codex-plugin/marketplace.json", hosts["codex"]["copyable_assets"])
        self.assertIn("attach-proven", self.payload["proof_legend"])

        paths = set(self.payload["docs_entrypoints"])
        for surface in self.payload["builder_surfaces"]:
            paths.update(surface.get("docs", []))
        for host in self.payload["hosts"]:
            paths.update(host.get("copyable_assets", []))

        for rel_path in sorted(paths):
            self.assertTrue((self.repo_root / rel_path).exists(), rel_path)

    def test_manifest_help_entrypoints_resolve(self):
        for command in self.payload["help_entrypoints"]:
            args = command.split()
            result = subprocess.run(
                args,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, f"{command}\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()

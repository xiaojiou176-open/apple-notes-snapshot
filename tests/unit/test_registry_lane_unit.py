import json
import re
import unittest
from pathlib import Path


class RegistryLaneUnitTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[2]

    def test_server_json_uses_mcpb_release_lane(self):
        payload = json.loads((self.repo_root / "server.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["name"], "io.github.xiaojiou176-open/apple-notes-snapshot")
        self.assertEqual(payload["version"], "0.1.12")
        self.assertEqual(payload["packages"][0]["registryType"], "mcpb")
        self.assertEqual(
            payload["packages"][0]["identifier"],
            "https://github.com/xiaojiou176-open/apple-notes-snapshot/releases/download/v0.1.12/apple-notes-snapshot-control-room-v0.1.12.mcpb",
        )
        self.assertRegex(payload["packages"][0]["fileSha256"], r"^[a-f0-9]{64}$")

    def test_public_skill_packet_has_required_frontmatter(self):
        skill_text = (
            self.repo_root
            / "examples"
            / "public-skills"
            / "notes-snapshot-control-room"
            / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("name: notes-snapshot-control-room", skill_text)
        self.assertIn("description:", skill_text)
        self.assertIn("version: 1.0.2", skill_text)

    def test_public_skill_listing_manifest_is_present_and_truthful(self):
        manifest_text = (
            self.repo_root
            / "examples"
            / "public-skills"
            / "notes-snapshot-control-room"
            / "manifest.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("artifact: public-skill-listing-manifest", manifest_text)
        self.assertIn("name: notes-snapshot-control-room", manifest_text)
        self.assertIn('display_name: Apple Notes Snapshot Control-Room', manifest_text)
        self.assertIn("version: 1.0.2", manifest_text)
        self.assertIn("status: ready-but-not-listed", manifest_text)
        self.assertIn("No live ClawHub listing exists yet", manifest_text)
        self.assertRegex(
            manifest_text,
            re.compile(
                r"submit_via: clawhub publish <repo-root>/examples/public-skills/notes-snapshot-control-room "
                r"--slug notes-snapshot-control-room --name \"Apple Notes Snapshot Control-Room\" "
                r"--version 1.0.2 --tags apple-notes,local-first,backup,mcp"
            ),
        )
        self.assertIn("references/install-and-attach.md", manifest_text)
        self.assertIn("references/usage-and-proof.md", manifest_text)

    def test_glama_claim_metadata_exists_without_docker_runtime_claim(self):
        payload = json.loads((self.repo_root / "glama.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["$schema"], "https://glama.ai/mcp/schemas/server.json")
        self.assertEqual(payload["maintainers"], ["xiaojiou176"])


if __name__ == "__main__":
    unittest.main()

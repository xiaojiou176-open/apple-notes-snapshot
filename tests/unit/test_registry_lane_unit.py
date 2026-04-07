import json
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
        self.assertIn("version: 1.0.0", skill_text)


if __name__ == "__main__":
    unittest.main()

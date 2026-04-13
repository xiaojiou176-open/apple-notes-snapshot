import json
import re
import unittest
from pathlib import Path


class RegistryLaneUnitTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[2]

    def test_server_json_uses_mcpb_companion_release_lane(self):
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
        self.assertIn("status: listed-live", manifest_text)
        self.assertIn("status: submission-done-platform-not-accepted-yet", manifest_text)
        self.assertIn("review_state: changes-requested", manifest_text)
        self.assertIn("official_listing_state: mixed-live-and-submission-done", manifest_text)
        self.assertIn("ClawHub listing is live today for notes-snapshot-control-room.", manifest_text)
        self.assertIn(
            "OpenHands/extensions #150 is submitted with changes requested and is not accepted or listed live.",
            manifest_text,
        )
        self.assertNotIn("status: ready-but-not-listed", manifest_text)
        self.assertNotIn("No live ClawHub listing exists yet", manifest_text)
        self.assertRegex(
            manifest_text,
            re.compile(
                r"submit_via: clawhub publish <repo-root>/examples/public-skills/notes-snapshot-control-room "
                r"--slug notes-snapshot-control-room --name \"Apple Notes Snapshot Control-Room\" "
                r"--version 1.0.2 --tags apple-notes,local-first,backup,mcp"
            ),
        )
        self.assertIn("references/README.md", manifest_text)
        self.assertIn("references/INSTALL.md", manifest_text)
        self.assertIn("references/DEMO.md", manifest_text)
        self.assertIn("references/TROUBLESHOOTING.md", manifest_text)

    def test_root_distribution_surface_converges_descriptor_package_and_skill_lanes(self):
        distribution_text = (self.repo_root / "DISTRIBUTION.md").read_text(encoding="utf-8")
        self.assertIn("Run -> Install -> Verify", distribution_text)
        self.assertIn("server.json", distribution_text)
        self.assertIn("packaging/mcpb/manifest.json", distribution_text)
        self.assertIn(
            "examples/public-skills/notes-snapshot-control-room/manifest.yaml",
            distribution_text,
        )
        self.assertIn("ClawHub is live today", distribution_text)
        self.assertIn(
            "Goose Skills Marketplace submission is review-pending on `block/Agent-Skills#27`",
            distribution_text,
        )
        self.assertIn(
            "the community index submission is review-pending on `heilcheng/awesome-agent-skills#183`",
            distribution_text,
        )
        self.assertIn(
            "OpenHands/extensions `#150` remains submitted with changes requested",
            distribution_text,
        )
        self.assertIn("external-only / review-pending", distribution_text)
        self.assertNotIn("the `.mcpb` package proves a hosted runtime", distribution_text.split("## Allowed Claims", 1)[0])
        self.assertNotIn("Goose Skills Marketplace is listed live", distribution_text.split("## Allowed Claims", 1)[0])
        self.assertNotIn("agent-skill.co is live", distribution_text.split("## Allowed Claims", 1)[0])

    def test_public_skill_packet_drops_legacy_reference_filenames(self):
        references_dir = (
            self.repo_root
            / "examples"
            / "public-skills"
            / "notes-snapshot-control-room"
            / "references"
        )
        self.assertFalse((references_dir / "install-and-attach.md").exists())
        self.assertFalse((references_dir / "usage-and-proof.md").exists())

    def test_glama_claim_metadata_exists_without_docker_runtime_claim(self):
        payload = json.loads((self.repo_root / "glama.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["$schema"], "https://glama.ai/mcp/schemas/server.json")
        self.assertEqual(payload["maintainers"], ["xiaojiou176"])


if __name__ == "__main__":
    unittest.main()

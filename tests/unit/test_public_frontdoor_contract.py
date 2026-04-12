import unittest
from pathlib import Path


class PublicFrontDoorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.readme = (cls.repo_root / "README.md").read_text(encoding="utf-8")
        cls.docs_index = (cls.repo_root / "docs" / "index.html").read_text(encoding="utf-8")
        cls.public_skills_index = (
            cls.repo_root / "docs" / "for-agents" / "public-skills" / "index.html"
        ).read_text(encoding="utf-8")
        cls.web_index = (cls.repo_root / "web" / "index.html").read_text(encoding="utf-8")

    def assert_order(self, content, earlier, later):
        earlier_index = content.find(earlier)
        later_index = content.find(later)
        self.assertNotEqual(earlier_index, -1, f"missing expected marker: {earlier}")
        self.assertNotEqual(later_index, -1, f"missing expected marker: {later}")
        self.assertLess(
            earlier_index,
            later_index,
            f"expected {earlier!r} to appear before {later!r}",
        )

    def test_readme_keeps_run_install_verify_before_builder_lane(self):
        self.assertIn("## Start with Run -> Install -> Verify", self.readme)
        self.assertIn("[Start the 3-step quickstart]", self.readme)
        self.assertIn("[Open the proof page]", self.readme)
        self.assertIn("[Get support or routing help]", self.readme)
        self.assertIn("## Builder and maintainer lanes after the operator path", self.readme)
        self.assertIn("Secondary builder reads after the first healthy loop:", self.readme)
        self.assertIn("[Distribution and listing boundaries](./DISTRIBUTION.md)", self.readme)
        self.assertIn("[For Codex / Claude Code builders]", self.readme)

        self.assert_order(
            self.readme,
            "## Start with Run -> Install -> Verify",
            "## Builder and maintainer lanes after the operator path",
        )
        self.assert_order(
            self.readme,
            "[Get support or routing help]",
            "Secondary builder reads after the first healthy loop:",
        )
        self.assert_order(
            self.readme,
            "Secondary builder reads after the first healthy loop:",
            "[For Codex / Claude Code builders]",
        )

    def test_docs_front_door_keeps_first_success_ctas_ahead_of_builder_lane(self):
        self.assertIn("Operator first. Builder-ready only after the loop feels obvious.", self.docs_index)
        self.assertIn("Start the 3-step quickstart", self.docs_index)
        self.assertIn("First-run troubleshooting", self.docs_index)
        self.assertIn("Open the proof page", self.docs_index)
        self.assertIn(">Run one snapshot and let macOS show the real permission prompts.<", self.docs_index)
        self.assertIn(">Install the loop so backups stop depending on your memory.<", self.docs_index)
        self.assertIn(">Verify the loop, then open proof and diagnostics with context.<", self.docs_index)
        self.assertIn(">For Agents<", self.docs_index)
        self.assertIn("Open the builder lane", self.docs_index)
        self.assertIn("Open the builder shelf last", self.docs_index)
        self.assertIn("Distribution boundary", self.docs_index)
        self.assertIn("Open the distribution ledger", self.docs_index)
        self.assertIn(
            "https://github.com/xiaojiou176-open/apple-notes-snapshot/blob/main/DISTRIBUTION.md",
            self.docs_index,
        )

        self.assert_order(
            self.docs_index,
            "Start the 3-step quickstart",
            "Open the builder lane",
        )
        self.assert_order(
            self.docs_index,
            "Open the proof page",
            "Open the builder lane",
        )
        self.assert_order(
            self.docs_index,
            "Step 1",
            "Step 2",
        )
        self.assert_order(
            self.docs_index,
            "Step 2",
            "Step 3",
        )

    def test_web_console_preserves_the_same_first_success_spine(self):
        self.assertIn('data-i18n="ui.operatorLane">Run -> Install -> Verify</h2>', self.web_index)
        self.assertIn(
            'Run one snapshot, install launchd, then verify the loop before you read deeper diagnostics or builder lanes.',
            self.web_index,
        )
        self.assertIn("Open the <a href=\"https://xiaojiou176-open.github.io/apple-notes-snapshot/quickstart/\">quickstart</a>", self.web_index)
        self.assertIn("troubleshooting guide", self.web_index)
        self.assertIn("proof page</a> for after the first verified loop", self.web_index)
        self.assertIn("Run ./notesctl run --no-status", self.web_index)
        self.assertIn("Run ./notesctl install --minutes 30 --load", self.web_index)
        self.assertIn("Run ./notesctl verify", self.web_index)

        self.assert_order(self.web_index, "quickstart", "troubleshooting guide")
        self.assert_order(self.web_index, "troubleshooting guide", "proof page")
        self.assert_order(self.web_index, "Run ./notesctl run --no-status", "Run ./notesctl install --minutes 30 --load")
        self.assert_order(self.web_index, "Run ./notesctl install --minutes 30 --load", "Run ./notesctl verify")

    def test_public_skills_page_points_back_to_root_distribution_ledger(self):
        self.assertIn("DISTRIBUTION.md", self.public_skills_index)
        self.assertIn("root-level convergence ledger", self.public_skills_index)
        self.assertIn("companion <code>.mcpb</code> package", self.public_skills_index)
        self.assertIn(
            "https://github.com/xiaojiou176-open/apple-notes-snapshot/blob/main/DISTRIBUTION.md",
            self.public_skills_index,
        )


if __name__ == "__main__":
    unittest.main()

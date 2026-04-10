import unittest
from pathlib import Path


class WebI18nContractTests(unittest.TestCase):
    def test_deep_merge_guards_recursive_merge_on_own_properties(self):
        repo_root = Path(__file__).resolve().parents[2]
        content = (repo_root / "web" / "i18n.js").read_text(encoding="utf-8")
        self.assertIn("Object.prototype.hasOwnProperty.call(base, key)", content)
        self.assertIn('key === "__proto__" || key === "constructor" || key === "prototype"', content)
        self.assertIn("Object.create(null)", content)
        self.assertIn('Object.freeze(["__proto__", "constructor", "prototype"])', content)

    def test_operator_focus_nodes_are_wired_into_bilingual_contract(self):
        repo_root = Path(__file__).resolve().parents[2]
        html = (repo_root / "web" / "index.html").read_text(encoding="utf-8")
        i18n = (repo_root / "web" / "i18n.js").read_text(encoding="utf-8")

        self.assertIn('data-i18n="ui.operatorFocusDeck"', html)
        self.assertIn('data-i18n="ui.currentNextMove"', html)
        self.assertIn('data-i18n="ui.readOrder"', html)
        self.assertIn('data-i18n="ui.controlRoomSignals"', html)
        self.assertIn('data-i18n="ui.latestActionTranscript"', html)
        self.assertIn('data-i18n="message.operatorFocusDeckSummary"', html)
        self.assertIn('data-i18n="message.outputGuidanceSummary"', html)
        self.assertIn('data-i18n="message.outputMetaHint"', html)

        self.assertIn('operatorFocusDeck: "Operator Focus Deck"', i18n)
        self.assertIn('operatorFocusDeck: "操作员聚焦甲板"', i18n)
        self.assertIn('outputGuidanceSummary:', i18n)
        self.assertIn('focusWaitingSignals:', i18n)


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

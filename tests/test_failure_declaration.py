import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "actions" / "failure-declaration" / "validate.py"
spec = importlib.util.spec_from_file_location("failure_declaration", PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class FailureDeclarationTests(unittest.TestCase):
    def block(self, classification="implementation defect", root="state transition occurs before commit"):
        return f"""{module.START}
- [ ] {module.NOT_REMEDIATION}
- [x] {module.REMEDIATION}
Observed:
required CI failed on exact revision abc
Classification:
{classification}
Basis:
reproduction isolates the owning responsibility layer
Root cause:
{root}
Remediation:
move the state transition into the owning transaction
Proof:
rerun regression and exact-head CI
{module.END}
"""

    def test_valid_remediation(self):
        self.assertEqual(module.validate(self.block(), "User", "owner"), "remediation:implementation defect")

    def test_non_remediation(self):
        body = f"""{module.START}
- [x] {module.NOT_REMEDIATION}
- [ ] {module.REMEDIATION}
{module.END}
"""
        self.assertEqual(module.validate(body, "User", "owner"), "not-remediation")

    def test_unknown_classification_fails_closed(self):
        with self.assertRaises(module.TriageError):
            module.validate(self.block(classification="UNKNOWN"), "User", "owner")

    def test_unknown_root_fails_closed(self):
        with self.assertRaises(module.TriageError):
            module.validate(self.block(root="The cause remains UNKNOWN pending reproduction"), "User", "owner")

    def test_trusted_dependabot_exemption(self):
        self.assertEqual(module.validate("", "Bot", "dependabot[bot]"), "bot-exempt")

    def test_untrusted_bot_not_exempt(self):
        with self.assertRaises(module.TriageError):
            module.validate("", "Bot", "other[bot]")


if __name__ == "__main__":
    unittest.main()

import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "actions" / "failure-classifier" / "classify.py"
spec = importlib.util.spec_from_file_location("failure_classifier", PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FailureClassifierTests(unittest.TestCase):
    def test_failure_declaration_is_auto_proven_evidence_defect(self):
        finding = module.classify_failure(
            "Failure triage",
            "failure-triage",
            "Validate failure-remediation declaration",
            "failure triage: FAIL: missing or duplicated failure-triage v1 block",
        )
        self.assertEqual(finding.classification, "evidence defect")
        self.assertEqual(finding.decision, module.AUTO_PROVEN)
        self.assertEqual(finding.rule, "FC-EVIDENCE-001")

    def test_test_failure_remains_unknown(self):
        finding = module.classify_failure(
            "Build",
            "test",
            "Run unit tests",
            "AssertionError: expected 4 actual 5",
        )
        self.assertEqual(finding.classification, "UNKNOWN")
        self.assertEqual(finding.decision, module.CANDIDATE)
        self.assertEqual(set(finding.candidates), {"implementation defect", "test defect"})

    def test_unrecognized_failure_remains_unknown(self):
        finding = module.classify_failure("CI", "mystery", "opaque step", "exit status 1")
        self.assertEqual(finding.classification, "UNKNOWN")
        self.assertEqual(finding.decision, module.UNKNOWN)

    def test_startup_failure_remains_fail_closed_candidate(self):
        finding = module.classify_startup_failure()
        self.assertIn("startup_failure", module.FAILURE_CONCLUSIONS)
        self.assertEqual(finding.classification, "UNKNOWN")
        self.assertEqual(finding.decision, module.CANDIDATE)
        self.assertEqual(set(finding.candidates), {"workflow-policy drift", "environment failure"})

    def test_latest_run_wins_for_same_workflow(self):
        runs = [
            {"workflow_id": 1, "name": "Build", "run_number": 10, "run_attempt": 1, "event": "pull_request"},
            {"workflow_id": 1, "name": "Build", "run_number": 11, "run_attempt": 1, "event": "pull_request"},
        ]
        latest = module._latest_runs(runs, {"Build"})
        self.assertEqual([item["run_number"] for item in latest], [11])

    def test_classifier_workflow_is_never_self_observed(self):
        runs = [
            {"workflow_id": 1, "name": "Failure classification", "run_number": 1, "run_attempt": 1, "event": "workflow_run"},
        ]
        self.assertEqual(module._latest_runs(runs, set()), [])

    def test_safe_text_strips_multiline_markup_and_bounds_length(self):
        value = module.safe_text("evil|name\n<script>" + "x" * 300)
        self.assertNotIn("\n", value)
        self.assertNotIn("<", value)
        self.assertIn("\\|", value)
        self.assertLessEqual(len(value), 160)

    def test_report_states_fail_closed(self):
        finding = module.classify_failure("Build", "test", "unit tests", "AssertionError")
        record = module.FailureRecord("Build", 1, "https://example.invalid", "failure", "test", "unit tests", finding)
        report = module.render_report("abc", [record], [])
        self.assertIn("**State:** **BLOCKED**", report)
        self.assertIn("`UNKNOWN`", report)
        self.assertIn("do not authorize remediation", report)


if __name__ == "__main__":
    unittest.main()

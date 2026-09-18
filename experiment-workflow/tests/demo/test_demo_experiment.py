import importlib
import sys
import unittest
from pathlib import Path


DEMO_DIR = Path(__file__).resolve().parent
if str(DEMO_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_DIR))


class DemoExperimentTests(unittest.TestCase):
    def _load_demo(self):
        try:
            return importlib.import_module("demo_experiment")
        except ModuleNotFoundError as error:
            self.fail(f"demo_experiment implementation is missing: {error}")

    def test_success_rate_counts_fixed_boolean_outcomes(self):
        demo = self._load_demo()

        metric = demo.success_rate([True, False, True, False, True, False])

        self.assertEqual(metric["correct"], 3)
        self.assertEqual(metric["total"], 6)
        self.assertEqual(metric["success_rate"], 0.5)

    def test_driver_preserves_paired_rows_and_failure_details(self):
        demo = self._load_demo()

        report = demo.run_experiment()

        self.assertEqual(report["sample_count"], 6)
        self.assertEqual(report["baseline"]["correct"], 2)
        self.assertEqual(report["candidate"]["correct"], 5)
        self.assertEqual(len(report["samples"]), 6)

        failed_candidate = [
            sample for sample in report["samples"] if not sample["candidate"]["success"]
        ]
        self.assertEqual(len(failed_candidate), 1)
        self.assertEqual(failed_candidate[0]["query"], "bye!")
        self.assertEqual(failed_candidate[0]["candidate"]["prediction"], "bye!")
        self.assertEqual(failed_candidate[0]["candidate"]["label"], "bye")

    def test_baseline_and_candidate_use_distinct_prediction_rules(self):
        demo = self._load_demo()

        self.assertEqual(demo.baseline_predict("  HELLO "), "  HELLO ")
        self.assertEqual(demo.candidate_predict("  HELLO "), "hello")


if __name__ == "__main__":
    unittest.main()

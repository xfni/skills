from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ExperimentSkillContractTests(unittest.TestCase):
    def test_exp_run_forecasts_authority_and_preflights_before_unattended_execution(self):
        skill = (ROOT / "skills" / "exp-run" / "SKILL.md").read_text()
        contract = (ROOT / "skills" / "exp-run" / "references" / "experiment.md").read_text()
        for value in (
            "Pre-authorization Forecast",
            "production read sources and data classes",
            "exact receiver, endpoint, and model",
            "bounded calls, retries, cost, and time",
            "non-destructive authorization preflight",
            "before unattended execution",
            "delta authorization",
            "reserve and deduct",
        ):
            self.assertIn(value, skill)
        for value in (
            "预授权包",
            "不能替代宿主沙箱、网络、凭证",
            "预检本身计入已确认配额",
            "不通过试探性生产写入验证权限",
        ):
            self.assertIn(value, contract)


if __name__ == "__main__":
    unittest.main()

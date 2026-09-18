"""Small, local-only replay for EXP-DEMO-001."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Iterable


EXPERIMENT = "EXP-DEMO-001"
ISSUE = "issues/3"
DATASET_VERSION = "fixed-inline-v1"
PARAMETERS = {
    "baseline": "original query string",
    "candidate": "lower+strip",
    "pairing": "same fixed sample for baseline and candidate",
}

SAMPLES = (
    {"sample_id": "case-01", "query": "  HELLO ", "label": "hello"},
    {"sample_id": "case-02", "query": "bye", "label": "bye"},
    {"sample_id": "case-03", "query": "HELLO", "label": "hello"},
    {"sample_id": "case-04", "query": "bye!", "label": "bye"},
    {"sample_id": "case-05", "query": "hello", "label": "hello"},
    {"sample_id": "case-06", "query": "  bye", "label": "bye"},
)


def baseline_predict(query: str) -> str:
    """Return the baseline prediction without transforming the input."""

    return query


def candidate_predict(query: str) -> str:
    """Return the candidate prediction using the agreed lower+strip rule."""

    return query.lower().strip()


def success_rate(outcomes: Iterable[bool]) -> dict[str, float | int]:
    """Calculate correct count, denominator, and success rate from outcomes."""

    outcome_list = list(outcomes)
    correct = sum(1 for outcome in outcome_list if outcome)
    total = len(outcome_list)
    return {
        "correct": correct,
        "total": total,
        "success_rate": correct / total if total else 0.0,
    }


def _run_strategy(
    strategy: str,
    predictor: Callable[[str], str],
) -> list[dict[str, object]]:
    rows = []
    for sample in SAMPLES:
        prediction = predictor(sample["query"])
        rows.append(
            {
                "sample_id": sample["sample_id"],
                "strategy": strategy,
                "prediction": prediction,
                "label": sample["label"],
                "success": prediction == sample["label"],
            }
        )
    return rows


def run_experiment() -> dict[str, object]:
    """Replay both independent prediction rules over the same six samples."""

    baseline_rows = _run_strategy("baseline", baseline_predict)
    candidate_rows = _run_strategy("candidate", candidate_predict)
    paired_samples = []
    for sample, baseline_row, candidate_row in zip(
        SAMPLES, baseline_rows, candidate_rows
    ):
        paired_samples.append(
            {
                "sample_id": sample["sample_id"],
                "query": sample["query"],
                "label": sample["label"],
                "baseline": baseline_row,
                "candidate": candidate_row,
            }
        )

    return {
        "experiment": EXPERIMENT,
        "issue": ISSUE,
        "dataset_version": DATASET_VERSION,
        "parameters": PARAMETERS,
        "sample_count": len(SAMPLES),
        "baseline": success_rate(row["success"] for row in baseline_rows),
        "candidate": success_rate(row["success"] for row in candidate_rows),
        "samples": paired_samples,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    report = run_experiment()
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

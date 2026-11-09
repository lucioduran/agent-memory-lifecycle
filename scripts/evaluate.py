"""Run or verify the small, author-known deterministic lifecycle fixture suite."""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from memory_lifecycle import Ledger
from memory_lifecycle.ledger import tokens

FIXTURE = Path("examples/scenarios.json")


def evaluate() -> list[dict[str, Any]]:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    outcomes = []
    for case in cases:
        ledger = Ledger.replay(case["events"])
        selection = ledger.select(case["session"], case["query"], case["at"], 1)
        actual = [e["id"] for e in selection["selected"]]
        # Append-only lexical baseline: session-scoped, no temporal lifecycle policy.
        candidates = [
            e for e in case["events"] if e["kind"] != "delete" and e["session"] == case["session"]
        ]
        query = tokens(case["query"])
        ranked = sorted(
            enumerate(candidates),
            key=lambda pair: (
                -sum((tokens(pair[1]["key"] + " " + pair[1]["value"]) & query).values()),
                pair[0],
            ),
        )
        baseline = (
            [ranked[0][1]["id"]]
            if ranked
            and sum((tokens(ranked[0][1]["key"] + " " + ranked[0][1]["value"]) & query).values())
            else []
        )
        replay = Ledger.replay(ledger.export())
        if replay.select(case["session"], case["query"], case["at"], 1) != selection:
            raise ValueError("sanitized replay diverged")
        outcomes.append(
            {
                "case": case["name"],
                "category": case["category"],
                "expected": case["expected"],
                "actual": actual,
                "pass": actual == case["expected"],
                "baseline": baseline,
                "baseline_pass": baseline == case["expected"],
                "selection": selection,
            }
        )
    return outcomes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    start = time.perf_counter()
    outcomes = evaluate()
    elapsed = time.perf_counter() - start
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    summary = {
        "cases": len(outcomes),
        "policy_pass": sum(x["pass"] for x in outcomes),
        "baseline_pass": sum(x["baseline_pass"] for x in outcomes),
    }
    if args.verify:
        report = json.loads(args.output.read_text(encoding="utf-8"))
        if (
            report["fixture_sha256"] != digest
            or report["outcomes"] != outcomes
            or report["summary"] != summary
        ):
            raise ValueError("evidence mismatch")
    else:
        cpu = platform.processor()
        if sys.platform == "darwin":
            cpu = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
            ).strip()
        report = {
            "fixture_sha256": digest,
            "summary": summary,
            "outcomes": outcomes,
            "environment": {
                "python": sys.version,
                "platform": platform.platform(),
                "cpu": cpu,
                "threads": 1,
                "runtime_dependencies": [],
                "git_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], text=True
                ).strip(),
            },
            "elapsed_seconds": elapsed,
        }
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, allow_nan=False)
            handle.write("\n")
    print(json.dumps(summary))
    if summary["policy_pass"] != summary["cases"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

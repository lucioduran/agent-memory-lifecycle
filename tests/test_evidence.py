import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory_lifecycle import Ledger
from scripts.evaluate import evaluate, main


class EvidenceTests(unittest.TestCase):
    def test_all_expected_selections(self):
        outcomes = evaluate()
        self.assertEqual(len(outcomes), 18)
        self.assertTrue(all(item["pass"] for item in outcomes))

    def test_report_verification_detects_changes(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            output = Path(tmp) / "report.json"
            with patch("sys.argv", ["evaluate", str(output)]):
                main()
                with self.assertRaises(FileExistsError):
                    main()
            with patch("sys.argv", ["evaluate", str(output), "--verify"]):
                main()
                report = json.loads(output.read_text())
                report["outcomes"][0]["actual"] = []
                output.write_text(json.dumps(report))
                with self.assertRaises(ValueError):
                    main()

    def test_malformed_replay(self):
        for data in ({}, [1], [{}], [{"id": []}]):
            with self.assertRaises(ValueError):
                Ledger.replay(data)

    def test_repository_conventions(self):
        headings = [
            line[3:]
            for line in Path("README.md").read_text().splitlines()
            if line.startswith("## ")
        ]
        self.assertEqual(
            headings,
            [
                "Problem",
                "Scope",
                "Quick start",
                "Usage",
                "Architecture",
                "Reproduction",
                "Results",
                "Testing",
                "Limitations",
                "Contributing",
                "License",
            ],
        )
        for root in (Path("memory_lifecycle"), Path("docs"), Path("examples"), Path("scripts")):
            for path in root.rglob("*"):
                if path.suffix in {".py", ".md", ".json"}:
                    self.assertNotIn(chr(0x2014), path.read_text())

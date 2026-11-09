import contextlib
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from memory_lifecycle import Ledger
from memory_lifecycle.__main__ import main


def event(id="a", **changes):
    return (
        dict(
            id=id,
            session="one",
            kind="assert",
            recorded_at="2026-01-01T00:00:00Z",
            valid_from="2026-01-01T00:00:00Z",
            key="office",
            value="North",
            source="original fictional fixture",
            **{},
        )
        | changes
    )


def delete(target, id="d", **changes):
    return event(id, **(dict(kind="delete", key="", value="", source="", target=target) | changes))


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.ledger.append(event())

    def select(self, **changes):
        return self.ledger.select(
            **(dict(session="one", query="office", at="2026-02-01T00:00:00Z") | changes)
        )

    def test_cosine_and_provenance(self):
        result = self.select()
        self.assertEqual(result["selected"][0]["source"], "original fictional fixture")
        self.assertAlmostEqual(result["selected"][0]["score"], 1 / math.sqrt(2))
        self.assertEqual(result["trace"][0]["reason"], "selected")

    def test_newer_fact_conflict(self):
        self.ledger.append(event("b", value="South", valid_from="2026-01-02T00:00:00Z"))
        result = self.select()
        self.assertEqual([e["id"] for e in result["selected"]], ["b"])
        self.assertEqual(result["conflicts"], [{"key": "office", "ids": ["a", "b"], "chosen": "b"}])
        self.assertEqual(result["trace"][0]["reason"], "older_fact")

    def test_ties_and_identical_values(self):
        self.ledger.append(event("z"))
        self.assertEqual(self.select()["selected"][0]["id"], "z")
        self.assertEqual(self.select()["conflicts"], [])
        self.ledger.append(event("b", recorded_at="2026-01-02T00:00:00Z"))
        self.assertEqual(self.select()["selected"][0]["id"], "b")

    def test_correction_boundary_and_no_resurrection(self):
        self.ledger.append(
            event(
                "b",
                kind="correct",
                target="a",
                value="South",
                valid_from="2026-01-02T00:00:00Z",
                valid_until="2026-01-03T00:00:00Z",
            )
        )
        self.assertEqual(self.select(at="2026-01-01T23:59:59Z")["selected"][0]["id"], "a")
        self.assertEqual(self.select(at="2026-01-02T00:00:00Z")["selected"][0]["id"], "b")
        self.assertEqual(self.select(at="2026-01-03T00:00:00Z")["selected"], [])
        self.ledger.append(delete("b", valid_from="2026-01-03T00:00:00Z"))
        self.assertEqual(self.select()["selected"], [])
        self.assertEqual(Ledger.replay(self.ledger.export()).export(), self.ledger.export())

    def test_expiration_and_independent_fallback(self):
        self.ledger.append(
            event(
                "b",
                value="South",
                valid_from="2026-01-02T00:00:00Z",
                valid_until="2026-02-01T00:00:00Z",
            )
        )
        self.assertEqual(self.select()["selected"][0]["id"], "a")
        self.assertEqual(self.select(at="2025-01-01T00:00:00Z")["selected"], [])

    def test_session_isolation_including_statistics(self):
        before = self.select()
        self.ledger.append(event("secret-id", session="two", value="office office secret"))
        self.assertEqual(self.select(), before)
        self.assertEqual(self.select(session="unknown")["trace"], [])

    def test_no_overlap_and_limit(self):
        self.assertEqual(self.select(query="unrelated")["selected"], [])
        self.assertEqual(self.select(query="")["trace"][0]["reason"], "no_overlap")
        self.ledger.append(event("b", key="office location", value="South"))
        result = self.select(limit=1)
        self.assertEqual(len(result["selected"]), 1)
        self.assertIn("below_limit", [e["reason"] for e in result["trace"]])

    def test_delete_erases_payload_and_is_replayable(self):
        self.ledger.append(delete("a"))
        exported = self.ledger.export()
        self.assertNotIn("North", json.dumps(exported))
        self.assertNotIn("original fictional fixture", json.dumps(exported))
        self.assertEqual(self.select()["trace"], [{"id": "a", "reason": "deleted"}])
        self.assertEqual(self.select(at="2025-01-01T00:00:00Z")["selected"], [])
        self.assertEqual(Ledger.replay(exported).export(), exported)
        exported[0]["id"] = "changed"
        self.assertEqual(self.ledger.export()[0]["id"], "a")

    def test_replay_deleted_correction_chain(self):
        self.ledger.append(event("b", kind="correct", target="a", value="South"))
        self.ledger.append(event("c", kind="correct", target="b", value="West"))
        self.ledger.append(delete("a"))
        self.ledger.append(delete("b", id="e"))
        self.assertEqual(Ledger.replay(self.ledger.export()).export(), self.ledger.export())

    def test_invalid_events_are_atomic(self):
        invalid = [
            event("a"),
            event("b", kind="unknown"),
            event("b", id2="extra"),
            event("b", session=""),
            event("b", key=" "),
            event("b", value=2),
            event("b", redacted=1),
            event("b", redacted=True, key="", value="", source=""),
            event("b", recorded_at="2025-01-01T00:00:00Z"),
            event("b", valid_from="2026-01-01"),
            event("b", valid_from="bad"),
            event("b", valid_until="2026-01-01T00:00:00Z"),
            event("b", target="a"),
            event("b", kind="correct", target="missing"),
            event("b", kind="correct", target="a", session="two"),
            event("b", kind="correct", target="a", key="different"),
            delete("a", valid_from="2025-01-01T00:00:00Z"),
            delete("a", value="payload"),
        ]
        original = self.ledger.export()
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.ledger.append(item)
            self.assertEqual(self.ledger.export(), original)
        self.ledger.append(delete("a"))
        for item in (delete("a", id="e"), delete("d", id="f")):
            with self.assertRaises(ValueError):
                self.ledger.append(item)

    def test_invalid_selection(self):
        for changes in ({"session": ""}, {"limit": 0}, {"limit": True}, {"at": "bad"}):
            with self.assertRaises(ValueError):
                self.select(**changes)

    def test_replay_rejects_forged_redaction_and_raw_key_mismatch(self):
        for data in (
            [event(redacted=True)],
            [event(redacted=True, key="", value="", source="")],
            [event(), event("b", kind="correct", target="a", key="wrong"), delete("a")],
        ):
            with self.assertRaises(ValueError):
                Ledger.replay(data)

    def test_timezone_equivalence(self):
        self.assertEqual(self.select(at="2026-01-01T01:00:00+01:00")["selected"][0]["id"], "a")


class CLITests(unittest.TestCase):
    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.json"
            for data, command, expected in [
                ([event()], ["redact"], 0),
                (
                    [event()],
                    [
                        "select",
                        "--session",
                        "one",
                        "--query",
                        "office",
                        "--at",
                        "2026-02-01T00:00:00Z",
                    ],
                    0,
                ),
                ({}, ["redact"], 2),
                ([2], ["redact"], 2),
                ([event(value=3)], ["redact"], 2),
            ]:
                path.write_text(json.dumps(data), encoding="utf-8")
                run = subprocess.run(
                    [sys.executable, "-m", "memory_lifecycle", str(path), *command],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(run.returncode, expected, run.stderr)
                with (
                    patch.object(sys, "argv", ["memory_lifecycle", str(path), *command]),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    self.assertEqual(main(), expected)
            path.unlink()
            run = subprocess.run(
                [sys.executable, "-m", "memory_lifecycle", str(path), "redact"], capture_output=True
            )
            self.assertEqual(run.returncode, 2)

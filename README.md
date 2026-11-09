# Agent Memory Lifecycle

Auditable memory events, temporal policies and local lexical retrieval. No runtime dependencies.

## Problem

An append-only memory can retrieve an obsolete fact after a correction, expiry or deletion. A plausible retrieval score does not explain whether a fact should still be usable.

## Scope

A Python library and JSON CLI for session-scoped assertions, explicit corrections, deletion and conflicting values. Original fictional fixtures exercise deterministic policies using real local TF-IDF cosine retrieval. No language model is used and no model-quality claim is made.

## Quick start

```sh
git clone https://github.com/lucioduran/agent-memory-lifecycle.git
cd agent-memory-lifecycle
python -m memory_lifecycle examples/ledger.json select --session one --query office --at 2026-02-01T00:00:00Z
```

Requires Python 3.11 or newer. The result selects the newer South office fact, lists its conflict with North, and explains both decisions.

## Usage

```python
from memory_lifecycle import Ledger

ledger = Ledger()
ledger.append({
    "id": "fact-1", "session": "session-1", "kind": "assert",
    "recorded_at": "2026-01-01T00:00:00Z",
    "valid_from": "2026-01-01T00:00:00Z",
    "key": "office", "value": "North", "source": "user declaration"
})
trace = ledger.select("session-1", "office", "2026-02-01T00:00:00Z")
replayed = Ledger.replay(ledger.export())
```

Use `kind: correct` with `target` for a permanent correction, or `kind: delete` with `target` and no payload for immediate erasure. Optional `valid_until` is exclusive. `python -m memory_lifecycle INPUT.json redact` writes a sanitized export to stdout; the original file is untouched. Errors exit with code 2; successful commands exit with 0. JSON inputs are arrays of events. See the [full contract](docs/semantics.md).

## Architecture

Validated events form an ordered in-memory ledger. Session filtering and validity rules run before conflict resolution. One winner per key enters a TF-IDF cosine ranker. Results include source provenance, explicit conflicts, scores and exclusion reasons. Serialized exports support deterministic replay, including redacted events backed by tombstones. This is a library for trusted callers, not an authenticated service.

## Reproduction

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m scripts.evaluate results/new-run.json
python -m scripts.evaluate results/evaluation.json --verify
```

The evaluator refuses to overwrite an existing report. On Windows activate `.venv\Scripts\Activate.ps1`. Reference execution uses one thread and the shared benchmark lock required by the parent project. See [methodology](docs/evaluation.md) for the exact command and measurement boundaries. Verification recomputes selections, traces, fixture hash and counts; it does not authenticate hardware metadata or timing.

## Results

The recorded [local evaluation](results/evaluation.json) passed 18/18 policy scenarios; the session-scoped append-only lexical baseline passed 8/18. All 18 scenario traces are included. Results and hardware details are documented in [evaluation methodology](docs/evaluation.md). Counts describe these fixed, author-known cases only.

## Testing

```sh
python -m ruff check .
python -m ruff format --check .
python -m mypy memory_lifecycle scripts
python -m coverage run -m unittest discover -v
python -m coverage report
python -m scripts.evaluate results/evaluation.json --verify
```

CI runs these checks on Linux, macOS and Windows with Python 3.11.9 and a 90% statement/branch coverage floor. Tests cover precedence, timezone boundaries, correction chains, expiry fallback, deletion payload removal, sanitized replay, malformed inputs, session isolation, CLI behavior and modified evidence.

## Limitations

All data is in memory and trusted files have no size limits. No concurrency, crash durability, authentication, encryption or secure erasure is provided. Deletion cannot erase external copies or prior traces. Audit identifiers and timestamps remain. Erased correction keys cannot be revalidated during sanitized replay. Newer facts are preferred by policy, not verified as true. Historical queries use current knowledge, not knowledge available at that past time. The lexical ranker uses ASCII tokens and has no semantic understanding. Small synthetic fixtures, one machine and a single timed pass cannot establish production accuracy, throughput or security. There has been no independent human review.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Keep policy changes explicit, add boundary tests, and version fixture changes with new evidence. Never turn deterministic retrieval results into model claims.

## License

Code, documentation, original fictional fixtures and recorded results use the [MIT license](LICENSE). Development dependencies retain their respective licenses.

# Evaluation methodology and evidence

The 18 original fictional scenarios are author-known policy regression fixtures,
not a held-out statistical sample. The evaluator runs actual local lexical
retrieval and records every selection, exclusion, conflict and score.
Expected IDs are explicit fixture labels and never enter the retrieval policy.

## Reference result

| Method | Exact top-one ID set matches |
| --- | ---: |
| Session-scoped append-only lexical baseline | 8 / 18 |
| Temporal policy followed by TF-IDF cosine | 18 / 18 |

The baseline ranks raw assertions and corrections by query-token overlap and
insertion order, filtering by session but ignoring corrections, expiry and
deletion. It is intentionally a simple lifecycle-unaware baseline, not a
competitive retrieval system. Because rankers differ as well as lifecycle
policies, this comparison does not isolate a causal retrieval-quality gain.
No-overlap returns an empty result in both methods. Empty expected sets are
included in the counts. The baseline also passes isolation controls because
session filtering is shared. No confidence intervals are justified for these
fixed author-written checks. No inference or human evaluation was performed.

Reference host: Intel Xeon W-3223 CPU at 3.50 GHz, x86_64 macOS 26.7.1,
CPython 3.11.13, one execution thread, no runtime packages. The full fixture
pass took 0.004563411 seconds, including JSON input, ledger replay, selection,
baseline scoring and sanitized replay checks. This is a single elapsed-time
observation, not a latency benchmark or load test. Startup, hardware metadata
collection and report writing are excluded. Electricity use was not measured.

## Exact local command

Run from the repository with a fresh destination path:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 /Users/luchoduran/Sites/open-source-projects/.coordination/benchmark_lock.py .venv/bin/python -m scripts.evaluate results/evaluation.json
```

The shared wrapper serialized this run with other projects. External contributors
can run `python -m scripts.evaluate results/new-run.json` directly when they do
not share that parent workspace. Keep experiments in the foreground and use one
thread. No paid services or downloads are involved.

The report records implementation commit
`7b9a6b77399c38e461544c7897f812bab6e96ebd`, environment and fixture SHA-256.
Later publication commits add evidence and documentation without changing the
measured implementation. Verification recomputes the complete deterministic
outcomes and summary from the current implementation. Metadata and elapsed time
are observations, not authenticated claims. Tests mutate evidence to exercise
verification failure. All result traces use fictional data, so no real personal
memory payload is published.

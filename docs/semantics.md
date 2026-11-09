# Memory contract

The ledger is an in-memory, single-writer policy library. Event IDs are globally
unique opaque strings. Session IDs and keys use exact case-sensitive matching.
Callers supply provenance in `source`; this declaration is not source verification.
All timestamps require timezone offsets. Intervals are [valid_from, valid_until).
An empty valid_until means no expiry. recorded_at must be nondecreasing in append
order. Backdated and future effective facts are supported.

## Selection

Selection uses all events currently in the ledger, evaluated at a valid-time
instant. It is not a historical transaction-time query: recorded_at does not hide
facts learned later. A correction permanently suppresses its specific target
from the correction's valid_from onward, even after the replacement expires or
is deleted. Before that boundary the target remains eligible unless deleted.
Corrections require an earlier fact in the same session and the same key.
Concurrent corrections are allowed and become explicit conflicts.

For each key, eligible assertions with different values produce a conflict
listing all IDs and the chosen ID. The greatest tuple (valid_from, recorded_at,
ID) wins. ID breaks exact timestamp ties lexicographically. Repeated identical
values are deduplicated by the same rule without reporting a contradiction.
Independent assertions are not permanent corrections: an older assertion can
become visible again if a newer independent assertion expires. Use correct to
prevent this fallback. Newness is a policy preference, not a truth guarantee.

Only winners enter lexical retrieval. Lowercase ASCII alphanumeric tokens and
raw term frequencies are weighted by smoothed IDF, log((1+N)/(1+df))+1.
Cosine scores greater than zero are ranked descending, with ID ascending as the
tie break. No stemming, embeddings or model inference is involved. Session
filtering occurs before IDF calculation. Traces expose every same-session fact's
reason, and scores for retrieval candidates, but no other session's metadata.
Conflicts are returned even when their key does not match the query.

## Deletion and audit

Delete targets exactly one fact, immediately at ingestion, regardless of its
valid_from or query time. valid_from is retained audit metadata and must not
precede the target's validity. Deletion cannot be scheduled. To remove a concept,
delete every assertion and correction carrying it individually. A deletion never
reactivates a corrected predecessor. A deleted target cannot be corrected or
deleted again. Deletion events cannot themselves be deleted.

The target's key, value and provenance source are replaced with empty strings.
ID, session, kind, times, target links and a redacted flag remain for audit.
Use opaque identifiers: identifiers and times may themselves be sensitive.
No content digest is retained. export returns a detached sanitized representation.
Replay accepts either raw events or sanitized exports backed by deletion events;
replay applies the same policy and deletion again. Erased key equality cannot be
revalidated, so sanitized replay checks structural links but cannot attest to the
original correction's key equality. This is a documented loss of validation, not
cryptographic audit integrity. No signatures or tamper-proof storage are claimed.

Deleting from this object cannot erase caller-owned inputs, previous exports,
files, backups, prior traces or Python allocator memory. The CLI redact command
emits a sanitized copy; it does not overwrite the input. Operators must handle
these copies. Session filtering is logical isolation, not authentication or a
multi-tenant security boundary. Trusted callers can export all sessions.

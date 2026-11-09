"""Validated event replay and explainable memory selection."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Any


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed


@dataclass(frozen=True)
class Event:
    id: str
    session: str
    kind: str
    recorded_at: str
    valid_from: str
    key: str = ""
    value: str = ""
    source: str = ""
    valid_until: str = ""
    target: str = ""
    redacted: bool = False


def tokens(text: str) -> Counter[str]:
    return Counter(re.findall(r"[a-z0-9]+", text.lower()))


class Ledger:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def append(self, data: dict[str, Any]) -> None:
        try:
            event = Event(**data)
        except TypeError as exc:
            raise ValueError("invalid event fields") from exc
        for name, value in asdict(event).items():
            if name == "redacted":
                if type(value) is not bool:
                    raise ValueError("redacted must be boolean")
            elif not isinstance(value, str):
                raise ValueError("event fields must be strings")
        if not all((event.id.strip(), event.session.strip(), event.recorded_at, event.valid_from)):
            raise ValueError("missing event identity or time")
        recorded, effective = instant(event.recorded_at), instant(event.valid_from)
        if self._events and recorded < instant(self._events[-1].recorded_at):
            raise ValueError("recorded_at must be monotonic")
        if any(e.id == event.id for e in self._events):
            raise ValueError("duplicate event ID")
        if event.kind not in {"assert", "correct", "delete"}:
            raise ValueError("unknown event kind")
        if event.valid_until and instant(event.valid_until) <= effective:
            raise ValueError("valid_until must follow valid_from")
        if event.kind == "assert" and event.target:
            raise ValueError("assert cannot have a target")
        if event.kind != "assert":
            target = next((e for e in self._events if e.id == event.target), None)
            if target is None or target.kind == "delete" or target.session != event.session:
                raise ValueError("target must be an earlier fact in this session")
            if target.redacted:
                raise ValueError("target has been deleted")
            if effective < instant(target.valid_from):
                raise ValueError("target cannot be changed before its validity starts")
            if event.kind == "correct" and event.key != target.key:
                raise ValueError("correction must preserve key")
        if event.kind == "delete":
            if any((event.key, event.value, event.source, event.valid_until, event.redacted)):
                raise ValueError("delete carries no payload or expiration")
        elif event.redacted:
            raise ValueError("redacted facts are accepted only through replay")
        elif not all((event.key.strip(), event.value.strip(), event.source.strip())):
            raise ValueError("facts require key, value and provenance source")
        self._events.append(event)
        if event.kind == "delete":
            self._events = [
                replace(e, key="", value="", source="", redacted=True)
                if e.id == event.target
                else e
                for e in self._events
            ]

    def export(self) -> list[dict[str, Any]]:
        return [asdict(e) for e in self._events]

    @classmethod
    def replay(cls, data: list[dict[str, Any]]) -> Ledger:
        # Validate redacted exports with their structural links before applying erasure.
        ledger = cls()
        deleted = {e.get("target") for e in data if e.get("kind") == "delete"}
        erased = {e.get("id") for e in data if e.get("redacted") is True}
        keys: dict[str, str] = {}
        for raw in data:
            item = dict(raw)
            if item.get("redacted") is True:
                if item.get("id") not in deleted or any(
                    item.get(k) for k in ("key", "value", "source")
                ):
                    raise ValueError("unbacked or payload-bearing redaction")
                item.update(
                    key=keys.get(str(item.get("target")), "[erased]"),
                    value="[erased]",
                    source="[erased]",
                    redacted=False,
                )
            if item.get("kind") == "correct" and item.get("target") in erased:
                # Erased keys cannot be compared; validate the remaining structural contract.
                target = next((e for e in ledger._events if e.id == item["target"]), None)
                if target is not None:
                    ledger._events[ledger._events.index(target)] = replace(target, key=item["key"])
            ledger.append(item)
            keys[str(item.get("id"))] = str(item.get("key", ""))
        return ledger

    def select(self, session: str, query: str, at: str, limit: int = 5) -> dict[str, Any]:
        if not session.strip() or type(limit) is not int or limit < 1:
            raise ValueError("session and positive integer limit required")
        now = instant(at)
        facts = [e for e in self._events if e.session == session and e.kind != "delete"]
        superseded = {
            e.target
            for e in self._events
            if e.session == session and e.kind == "correct" and instant(e.valid_from) <= now
        }
        trace: list[dict[str, Any]] = []
        eligible: list[Event] = []
        for fact in facts:
            reason = "eligible"
            if fact.redacted:
                reason = "deleted"
            elif instant(fact.valid_from) > now:
                reason = "not_yet_valid"
            elif fact.id in superseded:
                reason = "corrected"
            elif fact.valid_until and now >= instant(fact.valid_until):
                reason = "expired"
            trace.append({"id": fact.id, "reason": reason})
            if reason == "eligible":
                eligible.append(fact)
        groups: dict[str, list[Event]] = {}
        for fact in eligible:
            groups.setdefault(fact.key, []).append(fact)
        conflicts = []
        winners = []
        for key, group in sorted(groups.items()):
            winner = max(group, key=lambda e: (instant(e.valid_from), instant(e.recorded_at), e.id))
            winners.append(winner)
            if len({e.value for e in group}) > 1:
                conflicts.append(
                    {"key": key, "ids": sorted(e.id for e in group), "chosen": winner.id}
                )
            for entry in trace:
                if entry["id"] in {e.id for e in group if e != winner}:
                    entry["reason"] = "older_fact"
        docs = [tokens(f"{e.key} {e.value}") for e in winners]
        query_tokens = tokens(query)
        vocabulary = set(query_tokens).union(*(set(d) for d in docs))
        idf = {
            t: math.log((1 + len(docs)) / (1 + sum(t in d for d in docs))) + 1 for t in vocabulary
        }

        def cosine(doc: Counter[str]) -> float:
            numerator = sum(doc[t] * query_tokens[t] * idf[t] ** 2 for t in query_tokens)
            norm = math.sqrt(sum((n * idf[t]) ** 2 for t, n in doc.items()))
            qnorm = math.sqrt(sum((n * idf[t]) ** 2 for t, n in query_tokens.items()))
            return numerator / (norm * qnorm) if norm and qnorm else 0.0

        ranked = sorted(
            zip(winners, map(cosine, docs), strict=True), key=lambda p: (-p[1], p[0].id)
        )
        selected = [
            {"id": e.id, "key": e.key, "value": e.value, "source": e.source, "score": score}
            for e, score in ranked
            if score > 0
        ][:limit]
        scores = {e.id: score for e, score in ranked}
        selected_ids = {e["id"] for e in selected}
        for entry in trace:
            if entry["reason"] == "eligible":
                entry["score"] = scores[entry["id"]]
                entry["reason"] = (
                    "selected"
                    if entry["id"] in selected_ids
                    else "no_overlap"
                    if not scores[entry["id"]]
                    else "below_limit"
                )
        return {
            "session": session,
            "at": at,
            "query": query,
            "selected": selected,
            "conflicts": conflicts,
            "trace": trace,
        }

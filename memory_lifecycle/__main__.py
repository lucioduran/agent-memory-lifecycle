"""JSON command line interface."""

import argparse
import json
import sys
from pathlib import Path

from .ledger import Ledger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    select = sub.add_parser("select")
    select.add_argument("--session", required=True)
    select.add_argument("--query", required=True)
    select.add_argument("--at", required=True)
    select.add_argument("--limit", type=int, default=5)
    sub.add_parser("redact", help="emit sanitized ledger to stdout")
    args = parser.parse_args()
    try:
        data = json.loads(args.ledger.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(isinstance(e, dict) for e in data):
            raise ValueError("ledger must be a JSON array of event objects")
        ledger = Ledger.replay(data)
        result = (
            ledger.export()
            if args.command == "redact"
            else ledger.select(args.session, args.query, args.at, args.limit)
        )
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, OSError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

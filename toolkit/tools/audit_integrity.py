#!/usr/bin/env python3
"""
audit_integrity.py — Tamper-evident audit log with chained SHA-256 hashes.

Each entry in audit.jsonl includes a SHA-256 hash of the previous entry,
forming a hash chain. Any modification to a past entry breaks the chain.

Usage:
    from tools.audit_integrity import verify_audit_chain, append_with_hash
    result = verify_audit_chain("audit.jsonl")
    print(result)

    entry = {"action": "scan", "target": "example.com"}
    append_with_hash(entry, last_hash, "audit.jsonl")

    # CLI
    python3 tools/audit_integrity.py audit.jsonl
    python3 tools/audit_integrity.py audit.jsonl --append '{"action":"test"}'
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


# ── Hashing helpers ─────────────────────────────────────────────────────────

GENESIS_HASH = "0" * 64  # SHA-256 of nothing — used for the first entry


def _hash_entry(entry: dict[str, Any]) -> str:
    """Compute SHA-256 hex digest of a JSON-serialised audit entry.

    The hash is computed over the canonical JSON (sorted keys, no
    whitespace) excluding the ``_hash`` field itself to avoid
    circular dependency.
    """
    clean = {k: v for k, v in entry.items() if k != "_hash"}
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def append_with_hash(
    entry: dict[str, Any],
    prev_hash: str | None,
    log_path: str | Path,
) -> str:
    """Append a tamper-evident entry to the audit log.

    Adds ``_hash`` (hash of this entry) and ``_prev_hash`` fields to the
    entry before writing.

    Args:
        entry: The audit event dict (will be copied, not mutated).
        prev_hash: Hash of the previous entry (use ``GENESIS_HASH`` for
            the first entry).
        log_path: Path to the JSONL audit log file.

    Returns:
        The SHA-256 hash of the newly appended entry.
    """
    enriched = dict(entry)
    if prev_hash is None:
        prev_hash = GENESIS_HASH
    enriched["_prev_hash"] = prev_hash

    entry_hash = _hash_entry(enriched)
    enriched["_hash"] = entry_hash

    log_file = Path(log_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(enriched, sort_keys=True) + "\n")

    return entry_hash


# ── Chain verification ──────────────────────────────────────────────────────


def verify_audit_chain(
    audit_log_path: str | Path,
) -> dict[str, Any]:
    """Read audit.jsonl and verify the hash chain is intact.

    Returns:
        Dict with:
            ``valid`` (bool): True if the entire chain is intact.
            ``total_entries`` (int): Number of entries read.
            ``tampered_at`` (int|None): 0-indexed position of first
                tampered entry, or None if clean.
            ``errors`` (list[str]): Human-readable error messages.
    """
    log_file = Path(audit_log_path)
    result: dict[str, Any] = {
        "valid": True,
        "total_entries": 0,
        "tampered_at": None,
        "errors": [],
    }

    if not log_file.is_file():
        result["valid"] = False
        result["errors"].append(f"Log file not found: {log_file}")
        return result

    prev_expected = GENESIS_HASH

    with log_file.open(encoding="utf-8") as f:
        for line_num, raw_line in enumerate(f):
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            result["total_entries"] += 1

            try:
                entry = json.loads(raw_line)
            except json.JSONDecodeError as e:
                result["valid"] = False
                result["tampered_at"] = line_num
                result["errors"].append(
                    f"Entry {line_num}: invalid JSON — {e}"
                )
                break

            # Check previous hash links to our expected predecessor
            actual_prev = entry.get("_prev_hash")
            if actual_prev != prev_expected:
                result["valid"] = False
                result["tampered_at"] = line_num
                result["errors"].append(
                    f"Entry {line_num}: _prev_hash mismatch "
                    f"(expected {prev_expected}, got {actual_prev})"
                )
                break

            # Recompute this entry's hash
            recomputed = _hash_entry(entry)
            stored_hash = entry.get("_hash")
            if recomputed != stored_hash:
                result["valid"] = False
                result["tampered_at"] = line_num
                result["errors"].append(
                    f"Entry {line_num}: hash mismatch "
                    f"(expected {recomputed}, got {stored_hash})"
                )
                break

            prev_expected = stored_hash

    return result


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit log integrity verification"
    )
    parser.add_argument(
        "log_file",
        type=Path,
        help="Path to audit.jsonl",
    )
    parser.add_argument(
        "--append",
        type=str,
        default=None,
        metavar="JSON",
        help="Append a new entry (JSON string) with chained hash",
    )
    args = parser.parse_args()

    if args.append:
        # Read the last hash from the existing log
        prev_hash = GENESIS_HASH
        log_file = args.log_file
        if log_file.is_file():
            with log_file.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        prev_hash = entry.get("_hash", GENESIS_HASH)
                    except json.JSONDecodeError:
                        continue

        new_entry = json.loads(args.append)
        new_hash = append_with_hash(new_entry, prev_hash, args.log_file)
        print(f"Appended entry. Hash: {new_hash}")
        return 0

    # Verify chain
    result = verify_audit_chain(args.log_file)

    print(f"Entries verified: {result['total_entries']}")
    if result["valid"]:
        print("Status: VALID — chain intact")
    else:
        print(f"Status: TAMPERED at entry {result['tampered_at']}")
        for err in result["errors"]:
            print(f"  Error: {err}")

    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())

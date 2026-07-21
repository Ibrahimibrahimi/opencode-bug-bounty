#!/usr/bin/env python3
"""
llm_cache.py — LLM response caching with SHA-256 hashing and JSON file storage.

Caches LLM responses keyed by SHA-256 hash of the prompt to avoid redundant
API calls. Entries expire after a configurable TTL.

Usage:
    from tools.llm_cache import LLMCache

    cache = LLMCache(cache_dir="/tmp/llm-cache")
    prompt_hash = cache.hash_prompt("What is XSS?")
    cached = cache.get(prompt_hash)
    if cached is None:
        response = call_llm("What is XSS?")
        cache.set(prompt_hash, response, ttl_seconds=3600)
    cache.clear_expired()
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


# ── Constants ───────────────────────────────────────────────────────────────

DEFAULT_TTL = 3600  # 1 hour
MAX_PROMPT_LEN = 10_000  # Truncate prompts before hashing for consistency


class LLMCache:
    """File-based LLM response cache using SHA-256 prompt hashes as keys.

    Storage layout::

        <cache_dir>/
            <hash_prefix>/<hash>.json   # one file per cached entry

    Each JSON file contains:
        {"prompt_hash": "...", "response": "...", "created_at": ..., "ttl": ...}
    """

    def __init__(self, cache_dir: str | Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Hashing ──────────────────────────────────────────────────────────────

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        """Return SHA-256 hex digest of the prompt text.

        Prompts longer than ``MAX_PROMPT_LEN`` are truncated before
        hashing to avoid issues with extremely large inputs.
        """
        truncated = prompt[:MAX_PROMPT_LEN]
        return hashlib.sha256(truncated.encode("utf-8")).hexdigest()

    # ── Path helpers ─────────────────────────────────────────────────────────

    def _path_for(self, prompt_hash: str) -> Path:
        """Map a full hex hash to a sharded path: first 2 chars / full hash."""
        prefix = prompt_hash[:2]
        return self.cache_dir / prefix / f"{prompt_hash}.json"

    # ── Core API ─────────────────────────────────────────────────────────────

    def get(self, prompt_hash: str) -> str | None:
        """Look up a cached response by prompt hash.

        Returns:
            The cached response string, or ``None`` if not found or expired.
        """
        path = self._path_for(prompt_hash)
        if not path.exists():
            return None

        try:
            with path.open(encoding="utf-8") as f:
                entry = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        ttl = entry.get("ttl", DEFAULT_TTL)
        created = entry.get("created_at", 0)
        if time.time() - created > ttl:
            return None

        return entry.get("response")

    def set(
        self,
        prompt_hash: str,
        response: str,
        ttl_seconds: int = DEFAULT_TTL,
    ) -> None:
        """Store an LLM response keyed by prompt hash.

        Args:
            prompt_hash: SHA-256 hex digest of the prompt.
            response: The LLM response text to cache.
            ttl_seconds: Time-to-live in seconds (default: 3600).
        """
        path = self._path_for(prompt_hash)
        path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "prompt_hash": prompt_hash,
            "response": response,
            "created_at": time.time(),
            "ttl": ttl_seconds,
        }

        with path.open("w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)

    def clear_expired(self) -> int:
        """Remove all expired cache entries.

        Returns:
            Number of entries removed.
        """
        removed = 0
        now = time.time()

        for subdir in self.cache_dir.iterdir():
            if not subdir.is_dir():
                continue
            for entry_path in subdir.glob("*.json"):
                try:
                    with entry_path.open(encoding="utf-8") as f:
                        entry = json.load(f)
                    ttl = entry.get("ttl", DEFAULT_TTL)
                    created = entry.get("created_at", 0)
                    if now - created > ttl:
                        entry_path.unlink()
                        removed += 1
                except (json.JSONDecodeError, OSError):
                    # Corrupt file — remove it
                    entry_path.unlink(missing_ok=True)
                    removed += 1

        return removed

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        total = 0
        expired = 0
        now = time.time()

        for subdir in self.cache_dir.iterdir():
            if not subdir.is_dir():
                continue
            for entry_path in subdir.glob("*.json"):
                total += 1
                try:
                    with entry_path.open(encoding="utf-8") as f:
                        entry = json.load(f)
                    ttl = entry.get("ttl", DEFAULT_TTL)
                    created = entry.get("created_at", 0)
                    if now - created > ttl:
                        expired += 1
                except (json.JSONDecodeError, OSError):
                    expired += 1

        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
        }


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LLM response cache management"
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("/tmp/llm-cache"),
        help="Cache directory (default: /tmp/llm-cache)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("stats", help="Show cache statistics")
    sub.add_parser("clear", help="Remove expired entries")

    hash_cmd = sub.add_parser("hash", help="Hash a prompt string")
    hash_cmd.add_argument("prompt", help="Prompt text to hash")

    get_cmd = sub.add_parser("get", help="Get cached response by hash")
    get_cmd.add_argument("prompt_hash", help="SHA-256 prompt hash")

    args = parser.parse_args()

    cache = LLMCache(args.cache_dir)

    if args.command == "stats":
        s = cache.stats()
        print(f"Total entries:   {s['total_entries']}")
        print(f"Active entries:  {s['active_entries']}")
        print(f"Expired entries: {s['expired_entries']}")

    elif args.command == "clear":
        removed = cache.clear_expired()
        print(f"Removed {removed} expired entries.")

    elif args.command == "hash":
        print(cache.hash_prompt(args.prompt))

    elif args.command == "get":
        result = cache.get(args.prompt_hash)
        if result is None:
            print("Cache miss or expired.", file=sys.stderr)
            return 1
        print(result)

    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    exit(main())

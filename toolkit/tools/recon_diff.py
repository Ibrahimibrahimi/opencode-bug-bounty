#!/usr/bin/env python3
"""
recon_diff.py — Diff two recon snapshots and surface changes.

Compares two ReconData objects and returns structured deltas:
new/removed subdomains, new/removed endpoints, and technology changes.

Usage:
    from tools.recon_adapter import load_recon
    from tools.recon_diff import recon_diff

    old = load_recon("example.com", recon_dir="recon/old")
    new = load_recon("example.com", recon_dir="recon/new")
    delta = recon_diff(old, new)

    if delta["new_subdomains"]:
        print(f"New subdomains: {delta['new_subdomains']}")
"""

from __future__ import annotations

from typing import Any

from tools.recon_adapter import ReconData


def recon_diff(old: ReconData, new: ReconData) -> dict[str, Any]:
    """Compare two ReconData snapshots and return the diff.

    Args:
        old: Previous recon snapshot.
        new: Current recon snapshot.

    Returns:
        Dict with keys:
            ``new_subdomains``: Subdomains present in new but not old.
            ``removed_subdomains``: Subdomains present in old but not new.
            ``new_endpoints``: URLs present in new but not old.
            ``removed_endpoints``: URLs present in old but not new.
            ``technology_changes``: Dict with ``added`` and ``removed`` lists.
    """
    old_subs = set(old.subdomains)
    new_subs = set(new.subdomains)

    old_urls = set(old.urls)
    new_urls = set(new.urls)

    old_tech = set(old.technologies)
    new_tech = set(new.technologies)

    return {
        "new_subdomains": sorted(new_subs - old_subs),
        "removed_subdomains": sorted(old_subs - new_subs),
        "new_endpoints": sorted(new_urls - old_urls),
        "removed_endpoints": sorted(old_urls - new_urls),
        "technology_changes": {
            "added": sorted(new_tech - old_tech),
            "removed": sorted(old_tech - new_tech),
        },
    }


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    import argparse
    import json
    import sys

    from tools.recon_adapter import load_recon

    parser = argparse.ArgumentParser(
        description="Diff two recon snapshots"
    )
    parser.add_argument(
        "target",
        help="Target domain (used to locate recon dirs)",
    )
    parser.add_argument(
        "--old-dir",
        type=str,
        required=True,
        help="Path to old recon directory",
    )
    parser.add_argument(
        "--new-dir",
        type=str,
        required=True,
        help="Path to new recon directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )
    args = parser.parse_args()

    old = load_recon(args.target, args.old_dir)
    new = load_recon(args.target, args.new_dir)

    delta = recon_diff(old, new)

    if args.json_output:
        print(json.dumps(delta, indent=2))
    else:
        ns = delta["new_subdomains"]
        rs = delta["removed_subdomains"]
        ne = delta["new_endpoints"]
        re_ = delta["removed_endpoints"]
        tc = delta["technology_changes"]

        if not any([ns, rs, ne, re_, tc["added"], tc["removed"]]):
            print("No differences found.")
            return 0

        if ns:
            print(f"New subdomains ({len(ns)}):")
            for s in ns:
                print(f"  + {s}")
            print()

        if rs:
            print(f"Removed subdomains ({len(rs)}):")
            for s in rs:
                print(f"  - {s}")
            print()

        if ne:
            print(f"New endpoints ({len(ne)}):")
            for u in ne:
                print(f"  + {u}")
            print()

        if re_:
            print(f"Removed endpoints ({len(re_)}):")
            for u in re_:
                print(f"  - {u}")
            print()

        if tc["added"]:
            print(f"Technologies added ({len(tc['added'])}):")
            for t in tc["added"]:
                print(f"  + {t}")
            print()

        if tc["removed"]:
            print(f"Technologies removed ({len(tc['removed'])}):")
            for t in tc["removed"]:
                print(f"  - {t}")
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())

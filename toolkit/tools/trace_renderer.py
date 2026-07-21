#!/usr/bin/env python3
"""
trace_renderer.py — Chain-of-thought trace visualization.

Converts raw JSON trace events into readable Markdown, showing timestamps,
agent names, actions, and observations in a human-friendly format.

Usage:
    from tools.trace_renderer import trace_to_markdown
    md = trace_to_markdown(trace_data)
    print(md)

    # CLI
    python3 tools/trace_renderer.py trace.json
    python3 tools/trace_renderer.py trace.json -o trace.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Trace event schema ─────────────────────────────────────────────────────
# Expected trace_data structure:
# {
#   "trace_id": "...",
#   "events": [
#     {
#       "timestamp": "2025-01-15T12:00:00Z",
#       "agent": "recon-agent",
#       "action": "subdomain_enum",
#       "input": "...",
#       "observation": "...",
#       "status": "success" | "error",
#       "metadata": {}
#     }
#   ]
# }


def _format_timestamp(ts: str) -> str:
    """Normalize and format an ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        return str(ts)


def _format_status(status: str | None) -> str:
    """Return a markdown badge for the event status."""
    if status is None:
        return "`unknown`"
    s = status.lower()
    if s in ("success", "ok", "complete"):
        return "`success`"
    if s in ("error", "fail", "failed"):
        return "`error`"
    if s in ("skipped", "skip"):
        return "`skipped`"
    return f"`{s}`"


def _truncate(text: Any, max_len: int = 200) -> str:
    """Truncate a value to max_len characters for display."""
    s = str(text) if text is not None else ""
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def _format_event(idx: int, event: dict[str, Any]) -> str:
    """Render a single trace event as a Markdown block."""
    lines = []

    ts = _format_timestamp(event.get("timestamp", "unknown"))
    agent = event.get("agent", "unknown")
    action = event.get("action", "unknown")
    status = _format_status(event.get("status"))
    obs = event.get("observation", "")
    meta = event.get("metadata")

    lines.append(f"### Step {idx + 1}: {action}")
    lines.append("")
    lines.append(f"- **Time:** {ts}")
    lines.append(f"- **Agent:** {agent}")
    lines.append(f"- **Status:** {status}")
    lines.append("")

    inp = event.get("input")
    if inp:
        lines.append("**Input:**")
        lines.append("")
        lines.append(f"```")
        lines.append(_truncate(inp, 500))
        lines.append("```")
        lines.append("")

    if obs:
        lines.append("**Observation:**")
        lines.append("")
        lines.append(_truncate(obs, 500))
        lines.append("")

    if meta:
        lines.append("**Metadata:**")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(meta, indent=2)[:500])
        lines.append("```")
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def trace_to_markdown(trace_data: dict[str, Any]) -> str:
    """Convert a raw JSON trace dict into readable Markdown.

    Args:
        trace_data: Dictionary with optional ``trace_id`` and required
            ``events`` list.  Each event is a dict with keys:
            ``timestamp``, ``agent``, ``action``, ``input``,
            ``observation``, ``status``, ``metadata``.

    Returns:
        Markdown string with a header and formatted event blocks.
    """
    lines = []

    trace_id = trace_data.get("trace_id", "N/A")
    events = trace_data.get("events", [])

    lines.append(f"# Trace: {trace_id}")
    lines.append("")
    lines.append(f"- **Total events:** {len(events)}")
    if events:
        first_ts = _format_timestamp(events[0].get("timestamp", ""))
        last_ts = _format_timestamp(events[-1].get("timestamp", ""))
        lines.append(f"- **First event:** {first_ts}")
        lines.append(f"- **Last event:** {last_ts}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for idx, event in enumerate(events):
        lines.append(_format_event(idx, event))

    lines.append(f"*End of trace {trace_id}*")
    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert raw JSON trace to readable Markdown"
    )
    parser.add_argument(
        "trace_file",
        type=Path,
        help="Path to trace JSON file",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Write Markdown to file (default: stdout)",
    )
    args = parser.parse_args()

    if not args.trace_file.is_file():
        print(f"Error: {args.trace_file} not found", file=sys.stderr)
        return 1

    with args.trace_file.open() as f:
        trace_data = json.load(f)

    md = trace_to_markdown(trace_data)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(md, encoding="utf-8")
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(md)

    return 0


if __name__ == "__main__":
    sys.exit(main())

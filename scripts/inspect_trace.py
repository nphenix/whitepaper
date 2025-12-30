"""
Inspect a Playwright trace zip and extract network info for a target URL substring.

Usage (Windows/PowerShell recommended):
  conda run -n lumoscribe2025 python scripts/inspect_trace.py --trace-zip "test-results\\e2e\\xxx.trace.zip" --contains "/api/outline"
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Hit:
    source: str
    line_no: int
    raw: str


def _find_trace_entries(names: list[str]) -> dict[str, str]:
    """
    Return trace.* entries inside the zip (trace.network/trace.trace/trace.stacks) if present.
    They usually live under a folder like: "<test>_TIMESTAMP.trace/trace.network"
    """
    out: dict[str, str] = {}
    for n in names:
        if n.endswith("/trace.network"):
            out["trace.network"] = n
        elif n.endswith("/trace.trace"):
            out["trace.trace"] = n
        elif n.endswith("/trace.stacks"):
            out["trace.stacks"] = n
    return out


def _iter_text_lines(z: zipfile.ZipFile, member: str) -> list[str]:
    data = z.read(member)
    # trace.network can be large; decode with replacement
    text = data.decode("utf-8", errors="replace")
    return text.splitlines()


def _extract_json_like(line: str) -> Any | None:
    line = line.strip()
    if not line:
        return None
    if not (line.startswith("{") and line.endswith("}")):
        return None
    try:
        return json.loads(line)
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace-zip", required=True, help="Path to Playwright trace.zip")
    ap.add_argument("--contains", default="/api/outline", help="URL substring to search for")
    ap.add_argument("--context", type=int, default=3, help="Context lines around hits")
    args = ap.parse_args()

    zpath = Path(args.trace_zip)
    if not zpath.exists():
        print(f"[inspect_trace] trace zip not found: {zpath}", file=sys.stderr)
        return 2

    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        entries = _find_trace_entries(names)
        print(f"[inspect_trace] zip={zpath} entries={len(names)}")
        if not entries:
            print("[inspect_trace] no trace.* entries found in zip; members head:", names[:20])
            return 3

        for k, v in entries.items():
            print(f"[inspect_trace] found {k}: {v}")

        member = entries.get("trace.network") or entries.get("trace.trace")
        if not member:
            print("[inspect_trace] no trace.network or trace.trace found")
            return 4

        lines = _iter_text_lines(z, member)
        contains = args.contains

        hits: list[Hit] = []
        for i, line in enumerate(lines, start=1):
            if contains in line:
                hits.append(Hit(source=member, line_no=i, raw=line))

        print(f"[inspect_trace] search='{contains}' hits={len(hits)} in {member}")
        if not hits:
            # Some traces store URLs URL-encoded or in binary-ish chunks; fall back to scanning all trace.* files
            for k, m in entries.items():
                if m == member:
                    continue
                try:
                    text = z.read(m).decode("utf-8", errors="replace")
                except Exception:
                    continue
                if contains in text:
                    print(f"[inspect_trace] also found '{contains}' in {m}")
            return 0

        # Print context around first few hits
        for idx, h in enumerate(hits[:5], start=1):
            print(f"\n[inspect_trace] hit {idx} at {h.source}:{h.line_no}")
            start = max(1, h.line_no - args.context)
            end = min(len(lines), h.line_no + args.context)
            for ln in range(start, end + 1):
                prefix = ">>" if ln == h.line_no else "  "
                print(f"{prefix} {ln}: {lines[ln-1][:500]}")

        # Try extracting status/method info from JSON lines (if trace.network is JSONL)
        extracted: list[dict[str, Any]] = []
        for h in hits:
            obj = _extract_json_like(h.raw)
            if not isinstance(obj, dict):
                continue

            url = obj.get("url") or obj.get("request", {}).get("url")
            if isinstance(url, str) and contains in url:
                extracted.append(obj)

        if extracted:
            print(f"\n[inspect_trace] parsed_json_hits={len(extracted)} (showing up to 5)")
            for obj in extracted[:5]:
                # best-effort: different playwright versions store different shapes
                url = obj.get("url") or obj.get("request", {}).get("url")
                method = obj.get("method") or obj.get("request", {}).get("method")
                status = obj.get("status") or obj.get("response", {}).get("status")
                print(f"- url={url} method={method} status={status}")

        return 0


if __name__ == "__main__":
    raise SystemExit(main())



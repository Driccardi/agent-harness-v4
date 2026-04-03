#!/usr/bin/env python3
"""
mc — Memory-Core CLI
The universal command-line interface for the memory-core container.
Replaces 'python -m atlas ...' from the v1 design.

Usage:
  mc search 'JWT authentication'
  mc inject --hook PreToolUse --session sess-123
  mc soul
  mc topics
  mc health
  mc export > backup.json
  mc import < backup.json
"""

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../client"))
from mc_client import MemoryCoreClient, UniversalEvent, EventType, client_from_env


def get_client() -> MemoryCoreClient:
    c = client_from_env()
    if not c._headers.get("X-MC-Key"):
        print("ERROR: MC_SESSION_KEY not set.", file=sys.stderr)
        sys.exit(1)
    return c


async def cmd_search(args):
    client = get_client()
    results = await client.recall(
        query=args.query,
        limit=args.limit,
        confidence_min=args.confidence,
        recency_days=args.days,
    )
    print(f"\n── Memory search: '{args.query}' ({len(results)} results) ─────")
    for i, r in enumerate(results, 1):
        sim = r.get("similarity", 0)
        conf = r.get("confidence", 0)
        topics = ", ".join(r.get("topic_labels") or [])
        content = (r.get("content") or "")[:200].replace("\n", " ")
        print(f"\n  [{i}] sim={sim:.2f} conf={conf:.2f} type={r.get('chunk_type','?')}"
              + (f" [{topics}]" if topics else ""))
        print(f"      {content}")
    print()


async def cmd_inject(args):
    client = get_client()
    injection = await client.get_injection(
        hook_type=args.hook,
        session_id=args.session,
        tool_name=args.tool or "",
    )
    if injection.inject:
        print(injection.system_message or "(empty injection)")
    else:
        print("(no injection — gate blocked)")


async def cmd_soul(args):
    client = get_client()
    soul = await client.get_soul()
    print(soul if soul else "(soul.md is empty)")


async def cmd_health(args):
    client = get_client()
    status = await client.health()
    print(json.dumps(status, indent=2))


async def cmd_topics(args):
    import httpx
    client = get_client()
    resp = await client._client.get("/v1/session/topics")
    data = resp.json()
    topics = data.get("topics", [])
    print(f"\n── Topics ({len(topics)}) ──────────────────────────")
    for t in topics:
        print(f"  [{str(t.get('node_id',''))[:8]}] {t.get('label','?')} "
              f"({t.get('topic_type','?')}) chunks={t.get('chunk_count',0)}")
    print()


async def cmd_export(args):
    """Export all memory state for this human. Pipe to file: mc export > backup.json"""
    client = get_client()
    resp = await client._client.get(
        f"/v1/export/{client.human_id}",
        headers={"X-MC-Key": os.environ.get("MC_ADMIN_KEY", "")}
    )
    if resp.status_code == 401:
        print("ERROR: MC_ADMIN_KEY required for export", file=sys.stderr)
        sys.exit(1)
    print(resp.text)


async def cmd_ingest(args):
    """Ingest a single event from JSON file or stdin."""
    client = get_client()
    data = json.loads(sys.stdin.read() if args.file == "-" else open(args.file).read())
    event = UniversalEvent(
        event_type=EventType(data.get("event_type", "HUMAN_TURN")),
        content=data.get("content"),
        session_id=data.get("session_id", os.environ.get("MC_SESSION_ID", "cli")),
        framework=data.get("framework", "cli"),
    )
    chunk_id = await client.ingest(event)
    print(f"Ingested: {chunk_id}")


# ── Parser ────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(prog="mc", description="Memory-Core CLI")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("search", help="Semantic search")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--confidence", type=float, default=0.60)
    s.add_argument("--days", type=int, default=90)

    inj = sub.add_parser("inject", help="Get injection for a hook point")
    inj.add_argument("--hook", default="PreToolUse")
    inj.add_argument("--session", default=os.environ.get("MC_SESSION_ID", ""))
    inj.add_argument("--tool", default="")

    sub.add_parser("soul", help="Read soul.md")
    sub.add_parser("health", help="Container health check")
    sub.add_parser("topics", help="List topic nodes")
    sub.add_parser("export", help="Export all memory state (requires MC_ADMIN_KEY)")

    ing = sub.add_parser("ingest", help="Ingest a raw event from JSON")
    ing.add_argument("--file", default="-")

    args = p.parse_args()
    commands = {
        "search": cmd_search,
        "inject": cmd_inject,
        "soul": cmd_soul,
        "health": cmd_health,
        "topics": cmd_topics,
        "export": cmd_export,
        "ingest": cmd_ingest,
    }
    fn = commands.get(args.cmd)
    if not fn:
        p.print_help()
        sys.exit(1)
    asyncio.run(fn(args))


if __name__ == "__main__":
    main()

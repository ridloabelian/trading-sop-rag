"""CLI for trading-sop-rag: search, pre-trade audit, and portal generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sop_rag.auditor import audit_trade_plan, audit_with_gemini
from sop_rag.indexer import CorpusBM25Index
from sop_rag.portal import build_portal


def cmd_search(args: argparse.Namespace) -> int:
    idx = CorpusBM25Index(args.corpus)
    hits = idx.search(args.query, top_k=args.top_k, speaker_filter=args.speaker)
    if args.json:
        print(json.dumps(hits, indent=2, ensure_ascii=False))
        return 0
    for i, h in enumerate(hits, 1):
        ts = ", ".join(h["timestamps"]) or "N/A"
        print(f"[{i}] ({h['score']}) {h['video_id']} | {h['speaker_layer']} | {ts}")
        print(f"    Title: {h['title']}")
        if h["youtube_url"]:
            print(f"    URL:   {h['youtube_url']}")
        print(f"    Note:  {h['excerpt']}\n")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    idx = CorpusBM25Index(args.corpus)
    structured = json.loads(Path(args.plan_json).read_text(encoding="utf-8")) if args.plan_json else None
    result = audit_trade_plan(args.plan, index=idx, structured=structured, top_k=args.top_k)

    if args.gemini:
        result["gemini_review"] = audit_with_gemini(args.plan, result["supporting_evidence"])

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print(f"VERDICT: {result['verdict']} ({result['violation_count']} rule triggers)")
    for v in result["violations"]:
        print(f"  - [{v['severity']}] {v['rule_id']} {v['title']}: {v['reason']}")
        print(f"    Citation: {v['citation']} -> {v['youtube_url']}")
    if result["supporting_evidence"]:
        print("\nTop Supporting Evidence:")
        for e in result["supporting_evidence"]:
            print(f"  * {e['video_id']} ({e['speaker_layer']}): {e['youtube_url'] or e['doc_id']}")
    return 0


def cmd_portal(args: argparse.Namespace) -> int:
    out = build_portal(corpus_dir=args.corpus, out_html=args.out)
    print(f"Built searchable portal at {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sop-rag", description="Arist MD 199-Video BM25 RAG & 18-Rule Pre-Trade Auditor")
    p.add_argument("--corpus", default=None, help="Path to corpus directory (defaults to bundled corpus/)")
    sub = p.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("search", help="BM25 search across all 199 video extractions & Playbook")
    ps.add_argument("query")
    ps.add_argument("--top-k", type=int, default=5)
    ps.add_argument("--speaker", default=None, help="Filter by speaker layer (e.g. Arist, Ragnaray, Franz)")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_search)

    pa = sub.add_parser("audit", help="Audit a trade plan against 18 SOP rules + retrieve citations")
    pa.add_argument("plan", help="Free-form Indonesian/English trade plan text")
    pa.add_argument("--plan-json", default=None, help="Optional JSON file with structured risk flags")
    pa.add_argument("--top-k", type=int, default=4)
    pa.add_argument("--gemini", action="store_true", help="Optionally invoke Gemini synthesis (requires GEMINI_API_KEY)")
    pa.add_argument("--json", action="store_true")
    pa.set_defaults(func=cmd_audit)

    pp = sub.add_parser("build-portal", help="Generate searchable static HTML Evidence Portal")
    pp.add_argument("--out", default="docs/index.html")
    pp.set_defaults(func=cmd_portal)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

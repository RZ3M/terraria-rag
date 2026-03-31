"""
TESTS/eval_retrieval.py — Automated retrieval quality evaluation.

Runs every case in eval_queries.py through the retriever (no LLM),
scores recall and content-hit rate, and saves results to DATA/.

Usage:
    python TESTS/eval_retrieval.py
    python TESTS/eval_retrieval.py --k 5 --save-as my_run
    python TESTS/eval_retrieval.py --category crafting
    python TESTS/eval_retrieval.py --compare DATA/eval_baseline.json
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from COMMON.config import DATA_DIR, RETRIEVAL_SCORE_THRESHOLD
from QUERY.retriever import retrieve
from TESTS.eval_queries import EVAL_CASES, EvalCase, get_cases_by_category


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _title_hit(case: EvalCase, results: list) -> tuple[bool, int]:
    """
    Check if any expected title appears in top-K results.
    Returns (hit, rank) — rank is 1-indexed, 0 if no hit.
    """
    result_titles = [r.chunk.wiki_title.lower() for r in results]
    for rank, title in enumerate(result_titles, start=1):
        for expected in case.expected_titles:
            if expected.lower() in title or title in expected.lower():
                return True, rank
    return False, 0


def _section_hit(case: EvalCase, results: list) -> bool:
    """Check if any expected section appears in top-K results."""
    if not case.expected_sections:
        return True  # no section expectation = auto-pass
    for r in results:
        section = r.chunk.section_path.lower()
        for expected in case.expected_sections:
            if expected.lower() in section:
                return True
    return False


def _content_hit(case: EvalCase, results: list) -> bool:
    """Check if expected content substrings appear in any top-K chunk."""
    if not case.expected_content_contains:
        return True  # no content expectation = auto-pass
    all_content = " ".join(r.chunk.content.lower() for r in results)
    return all(kw.lower() in all_content for kw in case.expected_content_contains)


def score_case(case: EvalCase, k: int = 5) -> dict:
    """Run retrieval for a single case and compute scores."""
    t0 = time.time()
    try:
        results = retrieve(query_text=case.query, top_k=k)
    except Exception as e:
        return {
            "query": case.query,
            "category": case.category,
            "error": str(e),
            "title_hit": False,
            "title_rank": 0,
            "section_hit": False,
            "content_hit": False,
            "rr": 0.0,
            "latency_ms": (time.time() - t0) * 1000,
            "num_results": 0,
            "top_titles": [],
        }

    title_hit, title_rank = _title_hit(case, results)
    section_hit = _section_hit(case, results)
    content_hit = _content_hit(case, results)
    rr = 1.0 / title_rank if title_rank > 0 else 0.0

    return {
        "query": case.query,
        "category": case.category,
        "notes": case.notes,
        "title_hit": title_hit,
        "title_rank": title_rank,
        "section_hit": section_hit,
        "content_hit": content_hit,
        "rr": rr,
        "latency_ms": round((time.time() - t0) * 1000, 1),
        "num_results": len(results),
        "top_titles": [r.chunk.wiki_title for r in results[:5]],
        "top_scores": [round(r.score, 3) for r in results[:5]],
        "expected_titles": case.expected_titles,
        "expected_sections": case.expected_sections,
        "expected_content_contains": case.expected_content_contains,
    }


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------

def compute_metrics(scores: list[dict]) -> dict:
    """Aggregate per-case scores into summary metrics."""
    valid = [s for s in scores if "error" not in s]
    if not valid:
        return {}

    n = len(valid)
    title_hits = sum(1 for s in valid if s["title_hit"])
    section_hits = sum(1 for s in valid if s["section_hit"])
    content_hits = sum(1 for s in valid if s["content_hit"])
    mrr = sum(s["rr"] for s in valid) / n
    avg_latency = sum(s["latency_ms"] for s in valid) / n

    # Per-category breakdown
    categories = sorted(set(s["category"] for s in valid))
    per_category = {}
    for cat in categories:
        cat_scores = [s for s in valid if s["category"] == cat]
        cn = len(cat_scores)
        per_category[cat] = {
            "n": cn,
            "recall_title": round(sum(1 for s in cat_scores if s["title_hit"]) / cn, 3),
            "recall_content": round(sum(1 for s in cat_scores if s["content_hit"]) / cn, 3),
            "mrr": round(sum(s["rr"] for s in cat_scores) / cn, 3),
        }

    return {
        "n": n,
        "recall_title_at_k": round(title_hits / n, 3),
        "recall_section_at_k": round(section_hits / n, 3),
        "recall_content_at_k": round(content_hits / n, 3),
        "mrr": round(mrr, 3),
        "avg_latency_ms": round(avg_latency, 1),
        "errors": len(scores) - len(valid),
        "per_category": per_category,
    }


# ---------------------------------------------------------------------------
# Comparison helper
# ---------------------------------------------------------------------------

def compare_runs(baseline_path: Path, current_metrics: dict) -> None:
    """Print diff between a saved baseline and current metrics."""
    with open(baseline_path) as f:
        baseline = json.load(f)
    bm = baseline.get("metrics", {})

    print("\n=== Comparison vs baseline ===")
    key_metrics = ["recall_title_at_k", "recall_section_at_k", "recall_content_at_k", "mrr"]
    for k in key_metrics:
        old = bm.get(k, 0)
        new = current_metrics.get(k, 0)
        delta = new - old
        arrow = "▲" if delta > 0.005 else ("▼" if delta < -0.005 else "–")
        print(f"  {k:30s} {old:.3f} → {new:.3f}  {arrow} {delta:+.3f}")


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_results(scores: list[dict], metrics: dict) -> None:
    """Pretty-print per-case results and summary."""
    print("\n" + "=" * 80)
    print("RETRIEVAL EVALUATION RESULTS")
    print("=" * 80)

    # Per-case table
    col_w = 45
    print(f"\n{'Query':<{col_w}} {'Title':^5} {'Sect':^5} {'Cont':^5} {'RR':^5} {'Rank':^5} {'ms':^6}")
    print("-" * (col_w + 35))
    for s in scores:
        if "error" in s:
            print(f"{s['query']:<{col_w}} ERROR: {s['error']}")
            continue
        title = "✓" if s["title_hit"] else "✗"
        sect = "✓" if s["section_hit"] else "✗"
        cont = "✓" if s["content_hit"] else "✗"
        rr = f"{s['rr']:.2f}"
        rank = str(s["title_rank"]) if s["title_rank"] else "-"
        ms = f"{s['latency_ms']:.0f}"
        q = s["query"][:col_w - 1]
        print(f"{q:<{col_w}} {title:^5} {sect:^5} {cont:^5} {rr:^5} {rank:^5} {ms:^6}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Cases evaluated  : {metrics.get('n', 0)}")
    print(f"  Recall@K (title) : {metrics.get('recall_title_at_k', 0):.1%}")
    print(f"  Recall@K (sect)  : {metrics.get('recall_section_at_k', 0):.1%}")
    print(f"  Recall@K (content): {metrics.get('recall_content_at_k', 0):.1%}")
    print(f"  MRR              : {metrics.get('mrr', 0):.3f}")
    print(f"  Avg latency      : {metrics.get('avg_latency_ms', 0):.0f} ms")
    if metrics.get("errors"):
        print(f"  Errors           : {metrics['errors']}")

    print("\n  Per-category breakdown:")
    for cat, cm in metrics.get("per_category", {}).items():
        print(f"    {cat:<15} n={cm['n']}  recall_title={cm['recall_title']:.1%}  "
              f"recall_content={cm['recall_content']:.1%}  mrr={cm['mrr']:.3f}")

    # Failures
    failures = [s for s in scores if not s.get("title_hit") and "error" not in s]
    if failures:
        print(f"\n  FAILED title recall ({len(failures)} cases):")
        for s in failures:
            print(f"    ✗ {s['query']}")
            print(f"      Expected: {s['expected_titles']}")
            print(f"      Got:      {s['top_titles'][:3]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality")
    parser.add_argument("--k", type=int, default=5, help="Top-K results to evaluate (default: 5)")
    parser.add_argument("--category", type=str, default=None, help="Only run cases in this category")
    parser.add_argument("--save-as", type=str, default=None, help="Name for the saved results file")
    parser.add_argument("--compare", type=str, default=None, help="Path to baseline JSON to compare against")
    parser.add_argument("--no-save", action="store_true", help="Skip saving results to disk")
    args = parser.parse_args()

    cases = EVAL_CASES
    if args.category:
        cases = get_cases_by_category(args.category)
        if not cases:
            print(f"No cases found for category: {args.category}")
            sys.exit(1)

    print(f"Running {len(cases)} eval cases (top_k={args.k})...")
    scores = []
    for i, case in enumerate(cases, start=1):
        print(f"  [{i:2d}/{len(cases)}] {case.query[:60]}...", end="", flush=True)
        result = score_case(case, k=args.k)
        scores.append(result)
        status = "✓" if result.get("title_hit") else ("ERR" if "error" in result else "✗")
        print(f" {status}")

    metrics = compute_metrics(scores)
    print_results(scores, metrics)

    # Compare to baseline if requested
    if args.compare:
        compare_runs(Path(args.compare), metrics)

    # Save results
    if not args.no_save:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = args.save_as or f"eval_{timestamp}"
        if not name.endswith(".json"):
            name = f"{name}.json"
        out_path = DATA_DIR / name
        payload = {
            "timestamp": timestamp,
            "k": args.k,
            "category_filter": args.category,
            "metrics": metrics,
            "cases": scores,
        }
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"\n  Results saved to: {out_path}")


if __name__ == "__main__":
    main()

"""Optional manual smoke-test script for live OpenAlex and Crossref discovery queries.

This script is intentionally separate from the automated pytest suite so that
unit tests never depend on external network or live API availability.

Usage (from backend directory in PowerShell):
    .\.venv\Scripts\python.exe -m scripts.smoke_test_discovery --query "transformer attention" --limit 5
"""

import argparse
import asyncio
import json
import sys

from app.services.cache import SearchCache
from app.services.discovery import PaperDiscoveryService


async def _run_smoke_test(query: str, limit: int) -> int:
    service = PaperDiscoveryService(cache=SearchCache(cache_file_path=None))
    print(f"Running live discovery smoke test for query={query!r}, limit={limit}...")
    try:
        response = await service.search_papers(query=query, limit=limit)
    except Exception as exc:
        print(f"[ERROR] Live smoke test failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(response.model_dump(), indent=2))
    print(
        f"\n[OK] Retrieved {response.count} deduplicated paper(s). "
        f"Warnings: {response.warnings or 'None'}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an optional live smoke test against OpenAlex and Crossref."
    )
    parser.add_argument(
        "--query",
        default="retrieval augmented generation",
        help="Search query to send to OpenAlex and Crossref.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of deduplicated papers to return (1-50).",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run_smoke_test(query=args.query, limit=args.limit)))


if __name__ == "__main__":
    main()

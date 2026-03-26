from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Sequence

from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services import content_generator_service


logger = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate site-level content assets from the active crawl snapshot.")
    parser.add_argument("--site-id", type=int, required=True, help="Site ID for which content assets should be generated.")
    parser.add_argument("--active-crawl-id", type=int, default=None, help="Optional crawl snapshot override.")
    parser.add_argument("--output-language", default="en", help="Output language for generated text, e.g. en or pl.")
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only the serialized asset payload without the long text sections.",
    )
    return parser.parse_args(argv)


def run_generate_command(
    *,
    site_id: int,
    active_crawl_id: int | None = None,
    output_language: str = "en",
) -> dict[str, Any]:
    with SessionLocal() as session:
        return content_generator_service.generate_site_content_assets(
            session,
            site_id=site_id,
            active_crawl_id=active_crawl_id,
            output_language=output_language,
        )


def main(argv: Sequence[str] | None = None) -> None:
    configure_logging()
    args = parse_args(argv)
    try:
        payload = run_generate_command(
            site_id=args.site_id,
            active_crawl_id=args.active_crawl_id,
            output_language=args.output_language,
        )
    except content_generator_service.ContentGeneratorServiceError as exc:
        logger.error("Content asset generation failed: %s", exc)
        raise SystemExit(1) from exc

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))
    if args.json_only:
        return

    print("\n[Surfer Custom Instructions]\n")
    print(payload.get("surfer_custom_instructions") or "")
    print("\n[SEO Writing.ai - Details to Include]\n")
    print(payload.get("seowriting_details_to_include") or "")
    print("\n[Introductory Hook Brief]\n")
    print(payload.get("introductory_hook_brief") or "")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


if __name__ == "__main__":
    main()

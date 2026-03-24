from __future__ import annotations

import json
from dataclasses import dataclass

from scrapy.http import Response


@dataclass(slots=True)
class SchemaSummary:
    present: bool
    count: int
    types: list[str]


def extract_schema_summary(response: Response) -> SchemaSummary:
    collected_types: set[str] = set()
    item_count = 0

    for raw_value in response.xpath(
        "//script[translate(@type, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='application/ld+json']/text()"
    ).getall():
        if raw_value is None:
            continue

        candidate = raw_value.strip()
        if not candidate:
            continue

        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        nodes = _flatten_schema_nodes(parsed)
        if not nodes:
            continue

        item_count += len(nodes)
        for node in nodes:
            for schema_type in _extract_schema_types(node):
                collected_types.add(schema_type)

    return SchemaSummary(
        present=item_count > 0,
        count=item_count,
        types=sorted(collected_types, key=str.lower),
    )


def _flatten_schema_nodes(value) -> list[object]:
    if isinstance(value, list):
        nodes: list[object] = []
        for item in value:
            nodes.extend(_flatten_schema_nodes(item))
        return nodes

    if isinstance(value, dict):
        if "@graph" in value and isinstance(value["@graph"], list):
            nodes = [value]
            nodes.extend(_flatten_schema_nodes(value["@graph"]))
            return nodes
        return [value]

    return []


def _extract_schema_types(value) -> list[str]:
    if not isinstance(value, dict):
        return []

    raw_types = value.get("@type")
    if isinstance(raw_types, list):
        items = raw_types
    elif raw_types is None:
        items = []
    else:
        items = [raw_types]

    types: list[str] = []
    for item in items:
        normalized = _normalize_schema_type(item)
        if normalized:
            types.append(normalized)
    return types


def _normalize_schema_type(value) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split())
    return normalized or None

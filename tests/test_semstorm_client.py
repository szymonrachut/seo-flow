from __future__ import annotations

import httpx

from app.integrations.semstorm.client import _unwrap_payload


def test_unwrap_payload_returns_results_list() -> None:
    response = httpx.Response(
        200,
        json={
            "params": {"domains": ["example.com"]},
            "results": [
                {"competitor": "competitor-a.com", "common_keywords": "12"},
                {"competitor": "competitor-b.com", "common_keywords": "8"},
            ],
            "results_count": 2,
            "access": "free",
        },
    )

    payload = _unwrap_payload(response)

    assert payload == [
        {"competitor": "competitor-a.com", "common_keywords": "12"},
        {"competitor": "competitor-b.com", "common_keywords": "8"},
    ]


def test_unwrap_payload_returns_results_dict() -> None:
    response = httpx.Response(
        200,
        json={
            "params": {"domains": ["example.com"]},
            "results": {
                "example.com": {
                    "keywords": 120,
                    "traffic": 480,
                }
            },
            "access": "free",
        },
    )

    payload = _unwrap_payload(response)

    assert payload == {
        "example.com": {
            "keywords": 120,
            "traffic": 480,
        }
    }

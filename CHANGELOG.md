# Changelog

## Unreleased
- Competitive Gap competitor extraction no longer sends outbound body excerpts to the LLM; the extraction prompt is now metadata-only and segment-level text chunking is intentionally disabled while that policy holds.
- `CompetitorExtractionResult` scalar-to-`semantic_card_json` compatibility shim is now deprecated and scheduled for removal after `stage-12a4 stabilization phase 1`, once all call sites pass `semantic_card_json` explicitly.

## stage-2-1-postgres-validated - 2026-03-13
- Domkniety backend ETAPU 2.1: paginacja, sortowanie i filtry dla `pages` i `links`.
- Dodane `summary_counts`, `progress` i `stop` dla crawl jobow.
- Utwardzony flow PostgreSQL i smoke test, w tym poprawka health check dla `psycopg`.
- Uporzadkowane eksporty CSV oraz testy ETAPU 1, 2 i 2.1.

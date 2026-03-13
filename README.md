# SEO Crawler (ETAP 2.1)

Lokalny crawler SEO dla jednej domeny z:
- crawl jobami,
- zapisem pages/links w PostgreSQL,
- audytem technicznym SEO,
- eksportem CSV,
- lokalnym API FastAPI.

## Zakres i ograniczenia
- Crawl tylko jednej domeny startowej.
- Linki zewnetrzne sa zapisywane, ale nie sa crawlowane.
- Brak GUI, Playwright, Search Console API, Celery/Redis, auth i WebSocket.
- ETAP 2.1 skupia sie na hardeningu API: paginacja, sortowanie, filtry, summary/progress, stop joba.

## Wymagania
- Python `3.12+`
- Docker Desktop (`docker compose`)
- PowerShell

## Szybki start
1. Skopiuj env:
```bash
copy .env.example .env
```
2. Bootstrap:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command bootstrap
```
3. Start PostgreSQL:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-up
```
4. Migracje:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command migrate
```

## Crawl i eksport przez CLI
Uruchomienie crawl:
```bash
python -m app.cli.run_crawl https://example.com --max-urls 300 --max-depth 4 --delay 0.5
```

Eksport:
```bash
python -m app.cli.run_crawl export-pages --job-id 1 --output exports/pages_job_1.csv
python -m app.cli.run_crawl export-links --job-id 1 --output exports/links_job_1.csv
python -m app.cli.run_crawl export-audit --job-id 1 --output exports/audit_job_1.csv
```

## API FastAPI
Start API:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command api
```

Health:
```bash
curl http://127.0.0.1:8000/health
```

### Endpointy
- `POST /crawl-jobs`
- `GET /crawl-jobs/{job_id}`
- `POST /crawl-jobs/{job_id}/stop`
- `GET /crawl-jobs/{job_id}/pages`
- `GET /crawl-jobs/{job_id}/links`
- `GET /crawl-jobs/{job_id}/audit`
- `GET /crawl-jobs/{job_id}/export/pages.csv`
- `GET /crawl-jobs/{job_id}/export/links.csv`
- `GET /crawl-jobs/{job_id}/export/audit.csv`

## Pages API (paginacja, sortowanie, filtry)
Query params:
- `page` (>= 1)
- `page_size` (1..200)
- `sort_by`: `url|status_code|depth|title|fetched_at|response_time_ms`
- `sort_order`: `asc|desc`
- `missing_title`, `missing_meta_description`, `missing_h1`
- `has_title`, `has_meta_description`, `has_h1`
- `status_code`, `status_code_min`, `status_code_max`
- `canonical_missing`
- `robots_meta_contains`
- `non_indexable_like`

Przyklad:
```bash
curl "http://127.0.0.1:8000/crawl-jobs/1/pages?page=1&page_size=50&sort_by=depth&sort_order=desc&has_title=true&non_indexable_like=false"
```

## Links API (paginacja, sortowanie, filtry)
Query params:
- `page` (>= 1)
- `page_size` (1..200)
- `sort_by`: `source_url|target_url|target_domain|is_internal|is_nofollow`
- `sort_order`: `asc|desc`
- `is_internal`
- `is_nofollow`
- `target_domain`
- `has_anchor`

Przyklad:
```bash
curl "http://127.0.0.1:8000/crawl-jobs/1/links?page=1&page_size=50&sort_by=target_url&sort_order=asc&is_internal=true&has_anchor=true"
```

## Job detail: summary + progress
`GET /crawl-jobs/{job_id}` zwraca:
- metadane joba (`status`, timestamps, settings/stats),
- `summary_counts`:
  - `total_pages`, `total_links`, `total_internal_links`, `total_external_links`
  - `pages_missing_title`, `pages_missing_meta_description`, `pages_missing_h1`
  - `pages_non_indexable_like`
  - `broken_internal_links`, `redirecting_internal_links`
- `progress`:
  - `visited_pages`, `queued_urls`, `discovered_links`,
  - `internal_links`, `external_links`, `errors_count`

## Zatrzymanie joba
Stop endpoint:
```bash
curl -X POST "http://127.0.0.1:8000/crawl-jobs/1/stop"
```

Mechanizm jest cooperative:
- API oznacza job jako `stopped`,
- spider sprawdza status i konczy prace przy najblizszej okazji,
- to nie jest hard kill procesu; niewielka liczba in-flight requestow moze jeszcze sie domknac.

## Audit API
`GET /crawl-jobs/{job_id}/audit` zwraca summary + listy:
- missing title/meta/h1,
- duplicate title/meta description,
- broken/unresolved/redirecting internal links,
- non-indexable-like signals.

## CSV eksport
- Eksport przez CLI i API uzywa tej samej warstwy `export_service`.
- Kolumny maja stabilna kolejnosc.
- CSV jest kodowane jako UTF-8 z BOM (lepsza wspolpraca z Excel na Windows).

## Testy
Pelny zestaw:
```bash
python -m pytest
```

Smoke PostgreSQL:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command smoke-postgres
```

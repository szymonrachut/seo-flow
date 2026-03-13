# SEO Crawler (ETAP 3)

Lokalny crawler SEO dla jednej domeny z:
- backendem FastAPI,
- crawlerem Scrapy,
- PostgreSQL jako docelowa baza,
- audytem technicznym SEO,
- eksportem CSV,
- frontendem React + Vite do codziennej pracy lokalnej.

## Zakres i ograniczenia
- Crawl tylko jednej domeny startowej.
- Linki zewnetrzne sa zapisywane, ale nie sa crawlowane jako pages.
- Anchory sa zapisywane dla linkow wewnetrznych i zewnetrznych.
- Brak GUI desktopowego, Playwright, Search Console API, auth, WebSocket i Celery/Redis.
- ETAP 3 dodaje lokalny panel webowy nad istniejacym API. Logika audytu pozostaje po stronie backendu.

## Wymagania
- Python `3.12+`
- Node.js `20+`
- Docker Desktop (`docker compose`)
- PowerShell

## Backend quick start
1. Skopiuj env:
```bash
copy .env.example .env
```
2. Bootstrap Pythona i zaleznosci:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command bootstrap
```
3. Uruchom PostgreSQL:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-up
```
4. Uruchom migracje:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command migrate
```
5. Uruchom API:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command api
```

API domyslnie nasluchuje na `http://127.0.0.1:8000`.

## Frontend quick start
1. Przejdz do katalogu:
```bash
cd frontend
```
2. Skopiuj env:
```bash
copy .env.example .env.local
```
3. Zainstaluj zaleznosci:
```bash
npm install
```
4. Uruchom dev server:
```bash
npm run dev
```

Frontend domyslnie dziala na `http://127.0.0.1:5173` i laczy sie z API przez:
```env
VITE_API_BASE_URL=http://localhost:8000
```

Backend ma wlaczone CORS dla lokalnego frontendu:
- `http://localhost:5173`
- `http://127.0.0.1:5173`

## Pelny flow lokalny
Terminal 1:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-up
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command api
```

Terminal 2:
```bash
cd frontend
npm install
npm run dev
```

Potem otworz:
```text
http://127.0.0.1:5173
```

## Frontend routes
- `/` -> redirect do `/jobs`
- `/jobs` -> lista jobow + formularz nowego joba
- `/jobs/:jobId` -> szczegoly joba, summary counts, progress, eksporty, stop
- `/jobs/:jobId/pages` -> tabela pages z filtrami, sortowaniem i paginacja
- `/jobs/:jobId/links` -> tabela links z filtrami, sortowaniem i paginacja
- `/jobs/:jobId/audit` -> raport audytowy z countami i sekcjami problemow

## Widoki frontendowe

### Lista jobow
Widok `/jobs` pokazuje:
- `id`
- `status`
- `started_at`
- `finished_at`
- `total_pages`
- `total_internal_links`
- `total_external_links`
- `total_errors`

Mozna:
- sortowac po `id` lub `created_at`,
- utworzyc nowy crawl job,
- przejsc do szczegolow joba.

### Nowy job
Formularz korzysta z `POST /crawl-jobs` i przyjmuje:
- `root_url`
- `max_urls`
- `max_depth`
- `delay`

Po sukcesie frontend przekierowuje do szczegolow nowego joba.

### Szczegoly joba
Widok `/jobs/:jobId` pokazuje:
- status,
- timestamps,
- `settings_json`,
- `stats_json`,
- `summary_counts`,
- `progress`,
- linki do pages, links, audit i eksportow CSV.

Dla jobow `pending` i `running` frontend robi polling. Po przejsciu do `finished`, `failed` albo `stopped` polling zatrzymuje sie.

### Pages
Widok `/jobs/:jobId/pages` korzysta z:
```text
GET /crawl-jobs/{job_id}/pages
```

Obsluguje:
- paginacje,
- sortowanie,
- filtry backendowe,
- loading, empty i error states.

Stan paginacji, filtrow i sortowania jest synchronizowany z query stringiem URL.

Filtry:
- `has_title`
- `has_meta_description`
- `has_h1`
- `canonical_missing`
- `robots_meta_contains`
- `non_indexable_like`
- `status_code_min`
- `status_code_max`

Sortowanie:
- `url`
- `status_code`
- `depth`
- `title`
- `fetched_at`
- `response_time_ms`

### Links
Widok `/jobs/:jobId/links` korzysta z:
```text
GET /crawl-jobs/{job_id}/links
```

Obsluguje:
- paginacje,
- sortowanie,
- filtry backendowe,
- loading, empty i error states.

Stan rowniez jest synchronizowany z query stringiem URL.

Filtry:
- `is_internal`
- `is_nofollow`
- `target_domain`
- `has_anchor`

Sortowanie:
- `source_url`
- `target_url`
- `target_domain`
- `is_internal`
- `is_nofollow`

### Audit
Widok `/jobs/:jobId/audit` korzysta z:
```text
GET /crawl-jobs/{job_id}/audit
```

Pokazuje:
- summary counts,
- sekcje problemow:
  - `pages_missing_title`
  - `pages_missing_meta_description`
  - `pages_missing_h1`
  - `pages_duplicate_title`
  - `pages_duplicate_meta_description`
  - `broken_internal_links`
  - `unresolved_internal_targets`
  - `redirecting_internal_links`
  - `non_indexable_like_signals`

Jest tez przycisk eksportu `audit.csv`.

## API FastAPI
Najwazniejsze endpointy:
- `GET /health`
- `GET /crawl-jobs`
- `POST /crawl-jobs`
- `GET /crawl-jobs/{job_id}`
- `POST /crawl-jobs/{job_id}/stop`
- `GET /crawl-jobs/{job_id}/pages`
- `GET /crawl-jobs/{job_id}/links`
- `GET /crawl-jobs/{job_id}/audit`
- `GET /crawl-jobs/{job_id}/export/pages.csv`
- `GET /crawl-jobs/{job_id}/export/links.csv`
- `GET /crawl-jobs/{job_id}/export/audit.csv`

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

## Stop i progress
Job mozna zatrzymac przez:
- UI (`Stop job` w szczegolach joba),
- API:
```bash
curl -X POST "http://127.0.0.1:8000/crawl-jobs/1/stop"
```

Mechanizm stop jest cooperative:
- API oznacza job do zatrzymania,
- spider konczy prace przy najblizszej bezpiecznej okazji,
- to nie jest hard kill procesu, wiec pojedyncze in-flight requesty moga jeszcze sie domknac.

Progress w `GET /crawl-jobs/{job_id}` zawiera:
- `visited_pages`
- `queued_urls`
- `discovered_links`
- `internal_links`
- `external_links`
- `errors_count`

## CSV eksport
Eksport przez UI, API i CLI korzysta z tej samej warstwy backendowej.

Wlasciwosci:
- stabilna kolejnosc kolumn,
- czytelne naglowki,
- UTF-8 z BOM dla lepszej wspolpracy z Excel na Windows.

## Testy
Backend:
```bash
python -m pytest
```

Smoke PostgreSQL:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command smoke-postgres
```

Frontend:
```bash
cd frontend
npm test
npm run build
```

## Znane ograniczenia
- Brak autoryzacji uzytkownikow.
- Brak WebSocketow; aktywne joby odswiezane sa pollingiem.
- Brak GUI desktopowego.
- Brak Playwright i renderowania JS po stronie przegladarki.
- Brak Search Console API.
- Brak crawlowania domen zewnetrznych.

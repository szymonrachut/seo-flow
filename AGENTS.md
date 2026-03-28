# AGENTS.md

## Cel
Krotki przewodnik dla agenta pracujacego w tym repo po ETAPIE 12A.4.

Najwazniejszy model mentalny:
- `Site` jest trwala przestrzenia robocza witryny.
- `CrawlJob` jest snapshotem tej witryny w czasie.
- `pages`, `links`, audit, opportunities, internal linking, cannibalization i zaimportowane dane GSC nadal sa logicznie liczone dla jednego konkretnego `crawl_job`.
- `pages` maja tez trwala warstwe page taxonomy (`page_type`, `page_bucket`, confidence, version) liczona per snapshot.
- `AI Review Editor` jest osobna warstwa site-level dla dokumentow redakcyjnych; kanoniczny current state dokumentu pochodzi z aktywnych `editor_document_blocks`.
- `source_content` i `normalized_content` AI Review Editor sa reprezentacjami pochodnymi synchronizowanymi z aktywnych blokow.
- `content recommendations` sa warstwa site-level liczona dynamicznie nad aktywnym snapshotem i own data only.
- `competitive gap` jest warstwa site-level nad aktywnym snapshotem i manual competitors, ale ma juz snapshot-aware persisted warstwy Content Gap Review.
- competitor sync zapisuje strony i extraction do osobnego store site-level, a po udanym syncu zapisuje tez raw candidates do `site_content_gap_candidates`.
- explicit review run zapisuje snapshot-aware review state w `site_content_gap_review_runs` i reviewed items w `site_content_gap_items`.
- backendowy read model Competitive Gap dziala teraz w kolejnosci:
  - reviewed items dla aktywnego snapshotu,
  - raw candidates dla aktywnego snapshotu,
  - legacy dynamic fallback.
- semantic foundation i semantic arbiter pozostaja warstwa competitorowego enrichmentu / cache / legacy fallbacku, ale nie sa juz auto-triggerowanym primary path dla Content Gap Review.
- lifecycle Content Recommendations (`mark done`, implemented, outcome tracking, filters, summary bar i outcome windows) jest cienka warstwa stanu na poziomie `site`.
- konfiguracja GSC nalezy do `site`, ale import danych GSC nadal trafia do konkretnego snapshotu `crawl_job`.

## Od czego zaczac
Czytaj w tej kolejnosci:
1. `README.md`
2. `REPO_MAP.md`
3. `ARCHITECTURE.md`
4. `CHANGELOG.md`
5. `TESTING.md`
6. `app/api/main.py`, `app/cli/run_crawl.py`
7. odpowiedni obszar w `app/services/`, `app/api/routes/`, `frontend/src/features/`
8. testy powiazane z obszarem zmiany
9. `app/db/models.py` i `alembic/versions/`

## Faktyczne komendy
Backend:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command bootstrap
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command init-worktree-env
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command clone-worktree-db
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command start-worktree
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command stop-worktree
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command info-worktree
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-up
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-reset
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command migrate
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command api
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command test-quick
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command test-crawler
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command test-backend-full
python -m pytest -q
```

Crawl / eksport:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command crawl -StartUrl https://example.com
python -m app.cli.run_crawl https://example.com --max-urls 300 --max-depth 4 --delay 0.5
python -m app.cli.run_crawl export-pages --job-id 1 --output exports/pages.csv
```

Frontend:
```bash
cd frontend
npm install
npm run dev
npm test
npm test -- src/features/pages/PagesPage.test.tsx
npm run build
```

Playwright:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command playwright-install
```

Smoke PostgreSQL:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command smoke-postgres
```

## Workflow testowy agenta
- `TESTING.md` jest source of truth dla doboru zakresu testow i mapy `feature -> testy`.
- Zawsze zaczynaj od najmniejszego sensownego zakresu testow dla obszaru zmiany.
- Domyslny backendowy smoke po wiekszosci lokalnych zmian to `powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command test-quick`.
- Dla zmian w crawlerze najpierw uzyj `powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command test-crawler`; `tests/test_spider_scheduling.py` i `tests/test_e2e_local_cli.py` uruchamiaj tylko wtedy, gdy zmiana dotyka scheduler, stop flow, CLI albo pelnej orkiestracji crawl.
- Dla zmian endpointu backendowego uruchom test warstwy serwisowej i test API tego samego obszaru; nie odpalaj pelnego `pytest`, jesli zmiana jest lokalna.
- Dla zmian AI Review Editor lacz test API z testem serwisowym tej samej warstwy (`review`, `rewrite`, `block ops`, `versions`) i frontendowym `AIReviewEditorPage.test.tsx`; build dolacz przy zmianie routingu, shared kontraktu albo wiekszym UI hardeningu.
- Dla zmian frontendowych uruchamiaj test tylko dotknietego feature'a; `npm run build` dolacz dopiero przy zmianie routingu, kontraktu API, shared UI albo wiekszym refaktorze.
- `powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command test-backend-full` uruchamiaj dopiero przy zmianach przekrojowych: DB/migrations, `tests/conftest.py`, crawler core, shared helpers, shared read models, kontrakty API obejmujace wiele feature'ow i checkpoint przed merge.
- `powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command smoke-postgres` uruchamiaj tylko przy zmianach migracji, local DB flow, guardow Postgresa albo gdy prosisz o realny smoke.
- Jesli pelny `pytest` przekroczy timeout, nie zakladaj automatycznie bledu aplikacji. Najpierw sprawdz `TESTING.md`, uruchom wezszy zakres albo `python -m pytest -q --durations=20`.

## Jak repo jest zorganizowane
- `app/api/`: cienkie route handlery FastAPI
- `app/services/`: glowna logika aplikacji, read model, orkiestracja crawl, site workspace, GSC, eksporty
- `app/services/site_service.py`: site-centric workspace detail, crawl history, active/baseline context
- `app/services/gsc_service.py`: site-level property selection + per-crawl import i summary
- `app/services/ai_review_editor_service.py`: create/list/get/update dokumentu, parse i sync pochodnych reprezentacji dokumentu
- `app/services/editor_document_block_service.py`: inline edit, insert/delete block, reindex i current-state sync
- `app/services/editor_document_version_service.py`: version snapshots, diff preview, rollback / restore
- `app/services/editor_review_run_service.py`: review runs, summary, current vs stale governance
- `app/services/editor_review_engine_service.py`: deterministiczny/mock review engine i wspolny draft issue dla review workflow
- `app/services/editor_rewrite_service.py`: dismiss/resolved_manual, rewrite runs, apply rewrite, stale/actionability guards
- `app/services/content_recommendation_service.py`: site-centric own-data recommendations reuse'ujace taxonomy, GSC, internal linking, lifecycle state, `implemented_summary`, shared status order dla summary/sortowania, outcome windows, `too_early` i backendowe implemented filters
- `app/services/competitive_gap_service.py`: finalny site-centric Competitive Gap read model nad aktywnym snapshotem, z source selection `reviewed -> raw_candidates -> legacy`, readiness diagnostics i legacy fallback
- `app/services/competitive_gap_sync_service.py`: manual competitor sync, lightweight diagnostics, persistence do tabel competitorowych i zapis raw candidates po syncu
- `app/services/competitive_gap_sync_run_service.py`: operational sync run store, lease/heartbeat, stale recovery i retry/reset runtime
- `app/services/competitive_gap_semantic_rules.py`: deterministic exclusion rules i semantic eligibility dla competitor pages
- `app/services/competitive_gap_semantic_service.py`: semantic foundation, raw candidate store i top-K candidate generation
- `app/services/competitive_gap_semantic_run_service.py`: operational semantic run store, stale recovery i summary payload
- `app/services/competitive_gap_semantic_arbiter_service.py`: legacy/auxiliary semantic arbiter, cache decyzji merge/match/canonical naming i manual rerun
- `app/services/content_gap_candidate_service.py`: deterministiczny zapis raw content gap candidates z append/supersede/invalidate
- `app/services/content_gap_review_run_service.py`: jawne review runy Content Gap, snapshot-aware context freeze, lease/heartbeat, retry/stale
- `app/services/content_gap_review_llm_service.py`: realny LLM execution dla review runu, batch review i normalizacja do sanitized decisions
- `app/services/content_gap_item_materialization_service.py`: deterministiczna materializacja reviewed items i supersede starszych itemow
- `app/services/content_recommendation_rules.py`: centralne progi, wagi i typy rekomendacji dla ETAPU 11.2
- `app/services/content_recommendation_keys.py`: centralny helper dla deterministycznego `recommendation_key`
- `app/services/page_taxonomy_service.py`: regułowa klasyfikacja typow stron i summary per `crawl_job`
- `app/crawler/`: Scrapy spider, ekstraktory, JS-heavy detection, Playwright fallback
- `app/db/`: modele SQLAlchemy, sesja, metadata
- `frontend/src/features/sites/`: site workspace shell, overview, crawl history
- `frontend/src/features/content-recommendations/`: site-level widok Content Recommendations
- `frontend/src/features/competitive-gap/`: site-level widok Competitive Gap z readiness panel, semantic debug/status panel, empty states, competitor sync summary, operator UI dla runow i lazy explanation
- `frontend/src/features/ai-review-editor/`: site-level AI Review Editor z lista dokumentow, ekranem dokumentu, issue panel, rewrite preview, version history i diff preview
- `app/services/site_compare_service.py`: compare layer dla site workspace nad `active_crawl_id` i `baseline_crawl_id`
- `app/api/routes/site_compare.py`: site-centric compare endpointy dla pages / audit / opportunities / internal linking
- `frontend/src/features/gsc/`: site-level GSC workspace i legacy snapshot GSC view
- `frontend/src/features/pages/`, `frontend/src/features/audit/`, `frontend/src/features/opportunities/`, `frontend/src/features/internal-linking/`: snapshot views + site current-state views + site compare views
- `frontend/src/features/jobs/`: lista jobow, create flow, detail snapshotu
- `tests/`: backend unit/API/smoke
- `alembic/versions/`: historia schematu bazy

## Gdzie zagladac przy typowych taskach
- Site workspace / routing:
  `app/api/routes/sites.py`, `app/services/site_service.py`, `frontend/src/features/sites/`, `frontend/src/routes/AppRoutes.tsx`
- Site compare / compare context:
  `app/services/site_compare_service.py`, `app/api/routes/site_compare.py`, `frontend/src/features/pages/SitePagesComparePage.tsx`, `frontend/src/features/audit/SiteAuditComparePage.tsx`, `frontend/src/features/opportunities/SiteOpportunitiesComparePage.tsx`, `frontend/src/features/internal-linking/SiteInternalLinkingComparePage.tsx`
- Tworzenie nowego crawla:
  `app/services/crawl_job_service.py`, `app/api/routes/crawl_jobs.py`, `app/api/routes/sites.py`, `frontend/src/features/jobs/`, `frontend/src/features/sites/`
- GSC site-level:
  `app/integrations/gsc/*`, `app/services/gsc_service.py`, `app/api/routes/gsc.py`, `frontend/src/features/gsc/`, `frontend/src/features/sites/`
- Snapshotowe tabele i read model:
  `app/db/models.py`, `app/services/seo_analysis.py`, `app/services/crawl_job_service.py`
- Page taxonomy / classification:
  `app/services/page_taxonomy_service.py`, `app/api/routes/pages.py`, `frontend/src/features/pages/`
- Content Recommendations:
  `app/services/content_recommendation_service.py`, `app/services/content_recommendation_rules.py`, `app/api/routes/site_content_recommendations.py`, `frontend/src/features/content-recommendations/`
- AI Review Editor:
  `app/api/routes/site_ai_review_editor.py`, `app/schemas/ai_review_editor.py`, `app/services/ai_review_editor_service.py`, `app/services/editor_document_block_service.py`, `app/services/editor_document_version_service.py`, `app/services/editor_review_run_service.py`, `app/services/editor_review_engine_service.py`, `app/services/editor_review_llm_service.py`, `app/services/editor_rewrite_service.py`, `app/services/editor_rewrite_llm_service.py`, `frontend/src/features/ai-review-editor/`
- Competitive Gap:
  `app/services/competitive_gap_service.py`, `app/services/competitive_gap_sync_service.py`, `app/services/competitive_gap_sync_run_service.py`, `app/services/competitive_gap_semantic_rules.py`, `app/services/competitive_gap_semantic_service.py`, `app/services/competitive_gap_semantic_run_service.py`, `app/services/competitive_gap_semantic_arbiter_service.py`, `app/services/competitive_gap_extraction_service.py`, `app/api/routes/site_competitive_gap.py`, `frontend/src/features/competitive-gap/`
- Audit:
  `app/services/seo_analysis.py`, `app/services/audit_service.py`, `frontend/src/features/audit/`
- Opportunities / priority:
  `app/services/priority_rules.py`, `app/services/priority_service.py`, `app/api/routes/opportunities.py`, `frontend/src/features/opportunities/`
- Internal linking:
  `app/services/internal_linking_service.py`, `app/api/routes/internal_linking.py`, `frontend/src/features/internal-linking/`
- Cannibalization:
  `app/services/cannibalization_service.py`, `app/api/routes/cannibalization.py`, `frontend/src/features/cannibalization/`
- Trends / compare:
  `app/services/trend_rules.py`, `app/services/trends_service.py`, `app/api/routes/trends.py`, `frontend/src/features/trends/`

## Typowe checklisty zmian

### 1. Zmiana modelu `Site` / `CrawlJob`
- Zacznij od `app/db/models.py` i migracji, jesli zmienia sie schema.
- Dla tworzenia nowych crawl snapshotow sprawdz `app/services/crawl_job_service.py`.
- Dla workspace detail / active/baseline context sprawdz `app/services/site_service.py`.
- Zaktualizuj `app/schemas/site.py`, `frontend/src/types/api.ts` i `frontend/src/features/sites/`.
- Doloz test API w `tests/test_api_sites.py` oraz test frontendu obok `frontend/src/features/sites/`.

### 2. Nowy endpoint backendowy
- Dodaj schema request/response w `app/schemas/`.
- Dodaj cienki route w `app/api/routes/`.
- Logike trzymaj w `app/services/`.
- Jesli endpoint dotyczy UI, dopnij klienta w `frontend/src/features/*/api.ts`.
- Zaktualizuj `frontend/src/types/api.ts`.
- Dodaj test API i, jesli trzeba, test warstwy serwisowej.

### 3. Zmiana GSC
- Rozdziel:
  - OAuth / API client: `app/integrations/gsc/`
  - site-level konfiguracja i import snapshotu: `app/services/gsc_service.py`
  - HTTP: `app/api/routes/gsc.py`
  - UI: `frontend/src/features/gsc/` i `frontend/src/features/sites/`
- Pamietaj:
  - property selection jest trwale na `site_id`
  - import danych pozostaje per `crawl_job_id`
  - nie mieszaj wielu crawl snapshotow w podstawowych tabelach GSC
- Przy zmianie kontraktu dopnij test w `tests/test_gsc_integration.py` i test frontendowy obok `frontend/src/features/gsc/`.

### 4. Zmiana read modelu `pages`
- Persistent field: `app/db/models.py` + migracja.
- Page taxonomy rules / version / rationale: `app/services/page_taxonomy_service.py`.
- Read model: `app/services/seo_analysis.py`.
- Filtry / sortowanie / paginacja: `app/services/crawl_job_service.py` i odpowiedni route.
- Eksport: `app/services/export_service.py`.
- Frontend: `frontend/src/types/api.ts` + odpowiedni feature page.
- Testy backendowe i frontendowe.

### 4a. Zmiana Content Recommendations
- Rules / scoring: `app/services/content_recommendation_rules.py`.
- Recommendation key: `app/services/content_recommendation_keys.py`.
- Site-level skladanie payloadu + lifecycle + outcome: `app/services/content_recommendation_service.py`.
- HTTP: `app/api/routes/site_content_recommendations.py`.
- Eksport: `app/services/export_service.py`.
- Frontend: `frontend/src/features/content-recommendations/`, `frontend/src/types/api.ts`, `frontend/src/features/sites/`.
- Pamietaj:
  - modul ma zostac own-data only
  - reuse'uje page taxonomy z ETAPU 11.1, GSC, internal linking, opportunities i cannibalization jako sygnal pomocniczy
  - `mark done` chowa rekomendacje tylko dla tego samego `active_crawl_id`
  - jesli ten sam problem wraca po przyszlym crawl snapshot, rekomendacja moze znowu pojawic sie jako active
  - implemented filters / outcome windows / `too_early` maja zostac cienka warstwa read-modelowa; bez nowej tabeli, migracji i event history
  - `implemented_summary` ma liczyc scope po outcome window / mode / search, ale przed status drilldown
  - summary bar w UI jest tylko klikanym drilldownem po statusie; frontend nie przelicza tych countow sam
  - przy cleanupie status order trzymaj jedno zrodlo prawdy na backendzie i jedno na froncie; nie duplikuj recznie list w kilku miejscach
  - nie dodawaj competitor gap ani external keyword integrations "przy okazji"

### 4b. Zmiana AI Review Editor
- Backend:
  - `app/api/routes/site_ai_review_editor.py`
  - `app/schemas/ai_review_editor.py`
  - `app/services/ai_review_editor_service.py`
  - `app/services/editor_document_block_service.py`
  - `app/services/editor_document_version_service.py`
  - `app/services/editor_review_run_service.py`
  - `app/services/editor_review_llm_service.py`
  - `app/services/editor_rewrite_service.py`
  - `app/services/editor_rewrite_llm_service.py`
- Frontend:
  - `frontend/src/features/ai-review-editor/`
  - `frontend/src/types/api.ts`
- Testy backendowe:
  - `tests/test_api_ai_review_editor.py`
  - `tests/test_ai_review_editor_block_service.py`
  - `tests/test_ai_review_editor_review_service.py`
  - `tests/test_ai_review_editor_rewrite_service.py`
  - `tests/test_ai_review_editor_version_service.py`
- Testy frontendowe:
  - `frontend/src/features/ai-review-editor/AIReviewEditorPage.test.tsx`
- Pamietaj:
  - kanoniczny current state dokumentu = aktywne `editor_document_blocks`
  - `source_content` i `normalized_content` sa pochodne i musza pozostac zsynchronizowane z blokami
  - stale review pozostaje historycznym kontekstem; nie remapuj issue automatycznie do nowego current state
  - rewrite apply ma byc blokowany, gdy rewrite input nie pasuje juz do aktualnego stanu dokumentu

### 5. Zmiana w crawlerze
- Scheduler i request flow: `app/crawler/scrapy_project/spiders/site_spider.py`
- Parsowanie: `app/crawler/extraction/*`
- Rendering: `app/crawler/rendering/*`, `scrapy_project/settings.py`
- Zapis do DB: `app/crawler/scrapy_project/pipelines.py`
- Jesli zmienia sie payload trwaly, wracaj do checklisty dla pola persistentnego.

### 6. Zmiana compare / trends / analytics
- Progi i heurystyki: `app/services/trend_rules.py`
- Skladanie compare rows i summary: `app/services/trends_service.py`
- Site compare layer nad workspace: `app/services/site_compare_service.py`, `app/api/routes/site_compare.py`
- UI:
  - `frontend/src/features/trends/` dla job-centric compare
  - `frontend/src/features/pages/`, `frontend/src/features/audit/`, `frontend/src/features/opportunities/`, `frontend/src/features/internal-linking/` dla site-centric compare
- Pamietaj, ze compare reuse'uje istniejace snapshoty `crawl_jobs` i dane GSC zapisane per crawl.

## Zasady ostroznych zmian
- Nie przenos logiki biznesowej do route handlerow.
- Nie mieszaj danych wielu crawl snapshotow w podstawowych tabelach `pages`, `links`, audit ani `gsc_*`.
- Nie zmieniaj lokalnego hasla roli Postgresa w skryptach, testach ani dokumentacji "pomocniczo".
- Jesli lokalny PostgreSQL zwraca `password authentication failed`, traktuj to najpierw jako rozjazd starego Docker volume i `.env`, a nie jako powod do rotacji hasla.
- `main` worktree ma zostac podpiety do kanonicznej lokalnej bazy `seo-crawler-db` na `127.0.0.1:5432`, z baza `seo_crawler`.
- Dla `main` nie przepinaj `.env`, `DATABASE_URL`, `POSTGRES_PORT` ani `start-local.cmd` / `start-local.ps1` na izolowana baze worktree; `main` ma korzystac z kontenera `seo-crawler-db` na porcie `5432`, chyba ze uzytkownik wprost poprosi o inny target.
- Traktuj `frontend/src/types/api.ts` jako czesc kontraktu.
- Eksport ma reuse'owac read modele, nie osobna logike CSV.
- Frontend ma wyswietlac i orkiestracyjnie spinac API, nie liczyc audytu sam.
- Przy zmianie modelu aktualizuj jednoczesnie migracje, response schemas i testy.

## Ograniczenia, ktorych nie obchodz bez potrzeby
- Brak auth uzytkownikow koncowych
- Brak wielokontowego GSC
- Brak worker queue, websocketow i Celery/Redis
- Crawl jednej domeny startowej
- Linki zewnetrzne sa zapisywane, ale nie sa crawlowane jako `pages`

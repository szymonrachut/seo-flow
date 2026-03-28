# TESTING.md

## Cel
Praktyczny workflow testowy dla tego repo. Ten plik jest source of truth dla doboru zakresu testow, markerow i gotowych komend, tak aby agent i czlowiek nie zgadywali, kiedy odpalac lokalny test, kiedy szerszy backend i kiedy pelny run.

## Zasada wyboru zakresu
1. Zawsze zacznij od najmniejszego sensownego zestawu testow dla zmienionego obszaru.
2. Jesli zmiana dotyka kontraktu API, uruchom test warstwy serwisowej i test API tego samego obszaru.
3. Jesli zmiana dotyka shared helpers, modeli DB, `tests/conftest.py`, crawler core albo eksportow reuse'owanych przez wiele modulow, przejdz do szerszego backendowego runu.
4. Pelny backendowy `pytest` jest potrzebny dopiero przy zmianach przekrojowych albo przed checkpointem / merge.
5. Timeout pelnego `pytest` nie oznacza automatycznie bledu aplikacji; najpierw sprawdz najwolniejsze testy i to, czy odpaliles wlasciwy zakres.

## Gotowe komendy

### Backend
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command test-quick
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command test-crawler
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command test-backend-full
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command smoke-postgres
```

### Co robi kazda komenda
- `test-quick`: szybki backendowy run do codziennej pracy; pomija `slow`, `integration`, `e2e` i `postgres_smoke`.
- `test-crawler`: szybki rdzen crawlera dla typowych zmian w extractorach, renderingu, normalizacji i pipeline; celowo nie odpala `tests/test_spider_scheduling.py` ani `tests/test_e2e_local_cli.py`.
- `test-backend-full`: pelny backendowy run bez `postgres_smoke`, z `--durations=20`.
- `smoke-postgres`: realny smoke z PostgreSQL; tylko dla zmian w DB flow, migracjach i guardach.

### Frontend
```bash
cd frontend
npm test -- src/features/pages/PagesPage.test.tsx
npm test -- src/features/ai-review-editor/AIReviewEditorPage.test.tsx
npm run build
```

## Markery pytest
- `slow`: testy wyraznie dluzsze, pomijane przez `test-quick`.
- `integration`: testy przekraczajace granice procesu, srodowiska albo narzedzia zewnetrznego.
- `e2e`: end-to-end flow przez realny entrypoint aplikacji.
- `postgres_smoke`: smoke testy wymagajace dzialajacego PostgreSQL.

## Mapa feature -> testy -> kiedy rozszerzyc

### Site workspace / jobs / routing
- Backend:
  - `tests/test_api_sites.py`
  - `tests/test_api_jobs_list.py`
  - `tests/test_api_site_compare.py` gdy zmiana dotyka active / baseline context
- Frontend:
  - `frontend/src/features/sites/SiteWorkspaceLayout.test.tsx`
  - `frontend/src/features/sites/SitesPage.test.tsx`
  - `frontend/src/features/jobs/JobsPage.test.tsx`
  - `frontend/src/features/jobs/JobDetailPage.test.tsx`
- Wystarczy lokalny zakres:
  - zmiana w `app/services/site_service.py`
  - zmiana w `app/api/routes/sites.py`
  - zmiana w `frontend/src/features/sites/` lub `frontend/src/features/jobs/`
- Rozszerz do szerszego backendu:
  - gdy zmiana dotyka `Site`, `CrawlJob`, compare context albo shared schemas site / job
- Przejdz do full backend:
  - gdy zmienia sie model DB lub migracje dla `Site` / `CrawlJob`

### Site compare / trends
- Backend:
  - `tests/test_api_site_compare.py`
  - `tests/test_trends_compare.py`
- Frontend:
  - `frontend/src/features/pages/SitePagesComparePage.test.tsx`
  - `frontend/src/features/trends/TrendsPage.test.tsx`
  - testy obok compare views w `audit/`, `opportunities/`, `internal-linking/`, jesli sa dodawane
- Wystarczy lokalny zakres:
  - zmiana w `app/services/site_compare_service.py`
  - zmiana w `app/services/trends_service.py`
  - zmiana w jednej compare sekcji UI
- Rozszerz do szerszego backendu:
  - gdy zmiana dotyka shared filters compare, eksportow albo logiki GSC compare
- Przejdz do full backend:
  - gdy compare reuse'uje kilka modulow naraz i zmienia shared helpers / read models

### Pages / links / page taxonomy
- Backend:
  - `tests/test_api_stage2.py`
  - `tests/test_api_stage2_1.py`
  - `tests/test_page_taxonomy.py`
- Frontend:
  - `frontend/src/features/pages/PagesPage.test.tsx`
  - `frontend/src/features/links/LinksPage.test.tsx`
- Wystarczy lokalny zakres:
  - zmiana w `app/services/page_taxonomy_service.py`
  - zmiana w `app/services/seo_analysis.py` ograniczona do pages / links
  - zmiana w `frontend/src/features/pages/` lub `frontend/src/features/links/`
- Rozszerz do szerszego backendu:
  - gdy zmiana dotyka filtrowania, sortowania, paginacji lub eksportu pages / links
- Przejdz do full backend:
  - gdy zmienia sie persistent field strony, schema albo migracja

### Audit
- Backend:
  - `tests/test_audit_service.py`
  - `tests/test_api_stage5.py`
- Frontend:
  - `frontend/src/features/audit/AuditPage.test.tsx`
- Wystarczy lokalny zakres:
  - zmiana w `app/services/audit_service.py`
  - zmiana w `app/services/seo_analysis.py` ograniczona do audit
  - zmiana w `frontend/src/features/audit/`
- Rozszerz do szerszego backendu:
  - gdy audit reuse'uje pages, export albo compare
- Przejdz do full backend:
  - gdy zmienia sie shared read model strony lub pola audit zapisane w DB

### Opportunities / priority
- Backend:
  - `tests/test_priority_opportunities.py`
- Frontend:
  - `frontend/src/features/opportunities/OpportunitiesPage.test.tsx`
- Wystarczy lokalny zakres:
  - zmiana w `app/services/priority_rules.py`
  - zmiana w `app/services/priority_service.py`
  - zmiana w `frontend/src/features/opportunities/`
- Rozszerz do szerszego backendu:
  - gdy zmiana dotyka shared signals z audit / pages / GSC
- Przejdz do full backend:
  - gdy zmieniaja sie shared reguly scoringu lub eksporty wspoldzielone z innymi modulami

### Internal linking
- Backend:
  - `tests/test_internal_linking.py`
- Frontend:
  - `frontend/src/features/internal-linking/InternalLinkingPage.test.tsx`
- Wystarczy lokalny zakres:
  - zmiana w `app/services/internal_linking_service.py`
  - zmiana w `app/api/routes/internal_linking.py`
  - zmiana w `frontend/src/features/internal-linking/`
- Rozszerz do szerszego backendu:
  - gdy zmiana dotyka pages / links read model albo compare
- Przejdz do full backend:
  - gdy zmienia sie zapis linkow lub crawler payload

### Cannibalization
- Backend:
  - `tests/test_cannibalization.py`
- Frontend:
  - `frontend/src/features/cannibalization/CannibalizationPage.test.tsx`
- Wystarczy lokalny zakres:
  - zmiana w `app/services/cannibalization_service.py`
  - zmiana w `app/api/routes/cannibalization.py`
  - zmiana w `frontend/src/features/cannibalization/`
- Rozszerz do szerszego backendu:
  - gdy zmiana dotyka GSC signals, pages albo eksportow
- Przejdz do full backend:
  - gdy zmienia sie shared model danych uzywany tez przez opportunities / recommendations

### GSC
- Backend:
  - `tests/test_gsc_integration.py`
- Frontend:
  - `frontend/src/features/gsc/GscPage.test.tsx`
  - `frontend/src/features/gsc/SiteGscPage.test.tsx`
- Wystarczy lokalny zakres:
  - zmiana w `app/services/gsc_service.py`
  - zmiana w `app/api/routes/gsc.py`
  - zmiana w `frontend/src/features/gsc/`
- Rozszerz do szerszego backendu:
  - gdy zmiana dotyka site-level config i job-level import jednoczesnie
- Przejdz do full backend:
  - gdy zmienia sie kontrakt importu GSC albo modele DB `gsc_*`

### Content Recommendations
- Backend:
  - `tests/test_content_recommendations.py`
- Frontend:
  - `frontend/src/features/content-recommendations/SiteContentRecommendationsPage.test.tsx`
- Wystarczy lokalny zakres:
  - zmiana w `app/services/content_recommendation_service.py`
  - zmiana w `app/services/content_recommendation_rules.py`
  - zmiana w `app/services/content_recommendation_keys.py`
  - zmiana w `frontend/src/features/content-recommendations/`
- Rozszerz do szerszego backendu:
  - gdy zmiana dotyka lifecycle, `implemented_summary`, outcome windows albo eksportu
- Przejdz do full backend:
  - gdy zmiana dotyka shared signals z pages / GSC / internal linking / opportunities / cannibalization naraz

### AI Review Editor
- Backend:
  - `tests/test_ai_review_editor_block_service.py`
  - `tests/test_ai_review_editor_review_service.py`
  - `tests/test_ai_review_editor_rewrite_service.py`
  - `tests/test_ai_review_editor_version_service.py`
  - `tests/test_api_ai_review_editor.py`
  - `tests/test_ai_review_editor_migration.py`
  - `tests/test_editor_block_parser_service.py`
  - `tests/test_editor_review_engine_service.py`
  - `tests/test_editor_review_llm_service.py`
  - `tests/test_editor_rewrite_llm_service.py`
- Frontend:
  - `frontend/src/features/ai-review-editor/AIReviewEditorPage.test.tsx`
- Wystarczy lokalny zakres:
  - zmiana w `app/services/ai_review_editor_service.py`
  - zmiana w `app/services/editor_document_block_service.py`
  - zmiana w `app/services/editor_document_version_service.py`
  - zmiana w `app/services/editor_review_run_service.py`
  - zmiana w `app/services/editor_rewrite_service.py`
  - zmiana w `frontend/src/features/ai-review-editor/`
- Rozszerz do szerszego backendu:
  - gdy zmiana dotyka kontraktu API AI Review Editor, stale/current governance albo shared prompt normalization
- Przejdz do full backend:
  - gdy zmienia sie `app/db/models.py`, migracje `0023-0028`, shared DB fixtures albo kilka warstw AI Review Editor naraz

### Competitive Gap
- Backend:
  - `tests/test_api_competitive_gap.py`
  - `tests/test_competitive_gap_service.py`
  - `tests/test_competitor_sync_service.py`
  - `tests/test_competitive_gap_extraction_service.py`
- Frontend:
  - `frontend/src/features/competitive-gap/SiteCompetitiveGapPage.test.tsx`
- Wystarczy lokalny zakres:
  - zmiana w `app/services/competitive_gap_service.py`
  - zmiana w `app/services/competitive_gap_sync_service.py`
  - zmiana w `app/services/competitive_gap_sync_run_service.py`
  - zmiana w `frontend/src/features/competitive-gap/`
- Rozszerz do szerszego backendu:
  - gdy zmiana dotyka sync run store, retry / reset runtime albo ekstrakcji
- Przejdz do full backend:
  - gdy zmienia sie kilka warstw naraz: API, sync, extraction i read model

### Crawler / extraction / rendering
- Domyslny szybki run:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command test-crawler`
- Backend szybkie testy:
  - `tests/test_api_stage5.py`
  - `tests/test_links_extraction.py`
  - `tests/test_meta_extraction_stage2.py`
  - `tests/test_pipeline_and_stats.py`
  - `tests/test_rendering_stage5.py`
  - `tests/test_url_normalization.py`
- Dodatkowe wolniejsze testy tylko przy konkretnym zakresie:
  - `tests/test_spider_scheduling.py` dla zmian w scheduler, `stop_requested`, request dedupe, queue flow
  - `tests/test_e2e_local_cli.py` dla zmian w `app/cli/run_crawl.py`, entrypointach i pelnej orkiestracji local crawl
- Wystarczy lokalny zakres:
  - zmiana w extractorach, normalizacji URL, parserach, heurystykach renderingu
- Rozszerz do szerszego backendu:
  - gdy zmiana dotyka spider flow, pipeline zapisu, stats albo request scheduling
- Przejdz do full backend:
  - gdy zmiana dotyka crawler core i read modeli downstream

### Export / shared read models
- Backend:
  - `tests/test_export_service.py`
  - odpowiedni test modulu zrodlowego, np. pages / trends / recommendations
- Wystarczy lokalny zakres:
  - zmiana tylko w formacie eksportu jednego modulu
- Rozszerz do szerszego backendu:
  - gdy eksport reuse'uje shared read model albo kilka wspoldzielonych filtrow
- Przejdz do full backend:
  - gdy zmiana dotyka eksportow i modeli danych jednoczesnie

### Dev scripts / Postgres smoke / migracje
- Backend:
  - `tests/test_dev_scripts_postgres_guard.py`
  - `tests/test_postgres_smoke.py`
  - `tests/test_alembic_revision_ids.py`
- Wystarczy lokalny zakres:
  - zmiana w `scripts/dev.ps1`
  - zmiana w guardach srodowiskowych
- Rozszerz do szerszego backendu:
  - gdy zmiana dotyka migracji i bootstrap flow
- Przejdz do full backend:
  - gdy zmienia sie sposob inicjalizacji DB, migracje albo shared setup testowy

## Kiedy przejsc do `test-backend-full`
- zmiana w `app/db/models.py`
- nowa migracja albo zmiana istniejacej
- zmiana w `tests/conftest.py`
- zmiana w crawler core
- zmiana w shared services / shared rules uzywanych przez wiele modulow
- zmiana kontraktu API albo eksportow obejmujaca kilka feature'ow
- checkpoint przed merge

## Kiedy timeout pelnego pytest nie oznacza od razu problemu aplikacji
- gdy pojedyncze testy `integration`, crawler albo CLI sa wolne
- gdy lokalny Postgres nie odpowiada i test przypadkiem probuje go dotknac
- gdy pelny run zostal odpalony zamiast lokalnego testu jednego feature'a
- gdy trzeba po prostu uzyc `python -m pytest -q --durations=20` i zobaczyc, co naprawde jest najwolniejsze

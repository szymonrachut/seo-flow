# REPO_MAP.md

## Root
- `README.md`: aktualny opis produktu, setup lokalny, routing, API, AI Review Editor, page taxonomy, Content Recommendations lifecycle z implemented filters / outcome windows / summary barem, Competitive Gap z dual-read `reviewed/raw/legacy` i GSC flow
- `UI_MAP.md`: mapa glownych ekranow i glownych blokow UI
- `AGENTS.md`: szybki przewodnik dla agenta
- `ARCHITECTURE.md`: model architektury i invariants
- `CHANGELOG.md`: historyczne checkpointy
- `pyproject.toml`: backend dependencies, pytest config
- `docker-compose.yml`: lokalny PostgreSQL
- `.env.example`: backend env, crawl defaults, GSC paths i OAuth redirect
- `scripts/dev.ps1`: glowny wrapper developerski
- `alembic.ini`: konfiguracja Alembic

## Top-level katalogi
```text
app/        backend FastAPI + crawler + services + models
alembic/    migracje schematu
frontend/   React + Vite + Vitest
scripts/    pomocnicze komendy developerskie
tests/      testy backendowe i smoke
```

## Backend: `app/`
- `api/`
  - `main.py`: FastAPI app, CORS, router registration
  - `deps.py`: DB dependency
  - `routes/`
    - `crawl_jobs.py`: create/list/detail/stop job snapshots
    - `sites.py`: site workspace list/detail/crawl history/new crawl for existing site
    - `site_content_recommendations.py`: site-centric Content Recommendations, `mark-done`, backendowy `implemented_summary`, implemented filters / outcome windows + CSV export
    - `site_competitive_gap.py`: site-centric Competitive Gap, strategy CRUD, manual competitors, sync, sync runs, review runs, semantic rerun endpoint, readiness diagnostics, explanation i CSV export
    - `site_ai_review_editor.py`: site-centric AI Review Editor documents, blocks, review runs, issues, rewrites, versions, diff i restore
    - `pages.py`: snapshot-scoped pages list
    - `pages.py`: snapshot-scoped pages list + taxonomy summary endpoint
    - `links.py`: snapshot-scoped links list
    - `audit.py`: snapshot-scoped audit report
    - `gsc.py`: site-level GSC config + legacy job-centric snapshot endpoints
    - `site_compare.py`: site-centric compare endpoints dla pages / audit / opportunities / internal linking
    - `opportunities.py`: snapshot-scoped opportunities
    - `internal_linking.py`: snapshot-scoped internal linking
    - `cannibalization.py`: snapshot-scoped cannibalization/query overlap
    - `trends.py`: compare i snapshot delty
    - `exports.py`: CSV eksporty
- `cli/`
  - `run_crawl.py`: entry point dla crawl i eksportow CLI
- `core/`
  - `config.py`: centralny odczyt env
  - `logging.py`: konfiguracja logowania
- `crawler/`
  - `scrapy_project/spiders/site_spider.py`: glowny spider
  - `scrapy_project/pipelines.py`: zapis `Page` i `Link`
  - `scrapy_project/settings.py`: settings Scrapy + Playwright wiring
  - `extraction/`: parsery meta, headings, links, content, schema, media
  - `rendering/detection.py`: heurystyka `js_heavy_like`
  - `normalization/urls.py`: normalizacja URL-i
- `db/`
- `models.py`: modele `Site`, `CrawlJob`, `Page`, `Link`, `EditorDocument`, `EditorDocumentBlock`, `EditorDocumentVersion`, `EditorReviewRun`, `EditorReviewIssue`, `EditorRewriteRun`, `GscProperty`, `GscUrlMetric`, `GscTopQuery`, `SiteContentRecommendationState`, `SiteContentStrategy`, `SiteCompetitor`, `SiteCompetitorPage`, `SiteCompetitorSemanticCandidate`, `SiteCompetitorSemanticRun`, `SiteCompetitorSemanticDecision`, `SiteCompetitorPageExtraction`, `SiteCompetitorSyncRun`, `SiteContentGapCandidate`, `SiteContentGapReviewRun`, `SiteContentGapItem`
  - `session.py`: engine i `SessionLocal`
  - `base.py`: SQLAlchemy base
- `integrations/gsc/`
  - `auth.py`: lokalny OAuth token/state store
  - `client.py`: klient Google Search Console API
- `schemas/`
  - kontrakty request/response dla API
  - `services/`
    - `crawl_job_service.py`: create/reuse `Site`, create crawl snapshots, job detail, pages/links summary
    - `site_service.py`: site workspace detail, active/baseline context, crawl history
    - `site_compare_service.py`: compare layer nad aktywnym snapshotem i baseline snapshotem w site workspace; compare filters akceptuja tez CSV multi-select dla quick filters
    - `seo_analysis.py`: pochodne sygnaly SEO i laczenie snapshotu z GSC
    - `content_recommendation_rules.py`: centralne recommendation types, wagi i progi ETAPU 11.2
    - `content_recommendation_keys.py`: deterministyczny `recommendation_key`
    - `content_recommendation_service.py`: dynamiczne own-data Content Recommendations, implemented lifecycle, `implemented_summary`, shared status order dla summary/sortowania, outcome windows, `too_early` i backendowe filtrowanie implemented dla site workspace
    - `competitive_gap_service.py`: finalny Competitive Gap read model z source selection `reviewed -> raw_candidates -> legacy`, readiness / empty-state diagnostics i latency-safe fallback dla ciezkiej semantic sciezki
    - `competitive_gap_sync_service.py`: manual competitor sync, lightweight diagnostics i persistence do competitor store; po syncu zapisuje raw candidates, ale nie odpala juz automatycznie review LLM
    - `competitive_gap_sync_run_service.py`: operational sync run store, lease/heartbeat, stale detection, retry/reset runtime
    - `competitive_gap_semantic_rules.py`: deterministic exclusion rules / semantic eligibility dla competitor pages
    - `competitive_gap_semantic_service.py`: semantic foundation, raw candidates, reusable own-site match index i top-K candidate generation bez all-to-all
    - `competitive_gap_semantic_run_service.py`: operational semantic run store, lease/heartbeat, stale detection i summary payload; backend preferuje tez ostatni displayable run summary po pustym stale retry
    - `competitive_gap_semantic_arbiter_service.py`: legacy/auxiliary semantic arbiter, cache decyzji merge/match/canonical naming i manual rerun orchestration
    - `content_gap_candidate_service.py`: persisted raw content gap candidate generation po competitor sync
    - `content_gap_review_run_service.py`: explicit review run lifecycle, snapshot-aware context freeze, retry/stale
    - `content_gap_review_llm_service.py`: LLM review execution dla review runow, maly batching i normalizacja do sanitized decisions
    - `content_gap_item_materialization_service.py`: reviewed item materialization i supersede starszych itemow
    - `competitive_gap_extraction_service.py`: LLM extraction/labeling competitor pages
    - `competitive_gap_explanation_service.py`: on-demand explanation dla pojedynczego gap row
    - `page_taxonomy_service.py`: regułowa, trwała klasyfikacja `page_type` / `page_bucket` + summary per crawl
    - `ai_review_editor_service.py`: create/list/get/update dokumentu i parse do blokow
    - `editor_document_block_service.py`: inline edit, insert before/after/end, delete block, reindex i sync reprezentacji dokumentu
    - `editor_document_version_service.py`: snapshot wersji dokumentu, diff preview, restore/rollback, hash current-state
    - `editor_review_run_service.py`: review runs, summary, latest/current vs stale governance
    - `editor_review_engine_service.py`: deterministic/mock review engine i wspolny draft issue dla review workflow
    - `editor_review_llm_service.py`: structured LLM review + normalizacja issue
    - `editor_rewrite_service.py`: dismiss/resolved_manual, rewrite runs, apply rewrite, stale/actionability guards
    - `editor_rewrite_llm_service.py`: structured single-block rewrite + input hash dla bezpiecznego apply
  - `audit_service.py`: raport audytowy
  - `gsc_service.py`: site-level property selection, OAuth redirect validation, per-crawl import, top queries, summary
  - `priority_rules.py` / `priority_service.py`: priority score i opportunities
  - `internal_linking_service.py`: snapshot-scoped internal linking read model
  - `cannibalization_service.py`: query overlap i cannibalization per snapshot
  - `trend_rules.py` / `trends_service.py`: compare i delty
  - `export_service.py`: CSV

## Frontend: `frontend/src/`
- `main.tsx`: React root + router + providers
- `app/`: `App.tsx`, providers React Query + i18n
- `routes/AppRoutes.tsx`: routing aplikacji; root redirect do `/sites`, site shell routes, `/sites/new`, realny dashboard `/sites/:siteId/progress`, current-state views `/sites/:siteId/pages` i `/sites/:siteId/audit`, hub `/sites/:siteId/changes` oraz kanoniczne compare entry pointy `/sites/:siteId/changes/*`
- `layouts/AppLayout.tsx`: glowny shell UI z sticky headerem, sidebarem, site switcherem i globalna nawigacja
- `layouts/AppHeader.tsx`, `layouts/AppSidebar.tsx`, `layouts/appShell.ts`: logika naglowka, sidebara i route-aware menu / titles dla shellu
- `api/client.ts`: wspolny fetch wrapper
- `api/queryKeys.ts`: React Query keys
- `types/api.ts`: lustrzane typy kontraktow backendowych
  - `features/`
  - `sites/`
    - `SitesPage.tsx`: lista witryn, glowne miejsce zarzadzania workspace'ami i wejscie do add-site flow
    - `NewSitePage.tsx`: osobne wejscie do dodania witryny / pierwszego crawla
    - `SiteWorkspaceLayout.tsx`: site workspace context bar z `active_crawl_id` i `baseline_crawl_id`; bez compare-first bannera
    - `SiteOverviewPage.tsx`: current-first site overview z KPI aktywnego snapshotu, sygnalami do dzialania, shortcutami workspace, baseline helperem, historia i create new crawl
    - `SiteProgressPage.tsx`: site-level dashboard postepu z trend KPI, poprawami/regresjami, postepem wdrozen i lekkim timeline reuse'ujacym istniejace payloady compare / GSC / recommendations
    - `SiteChangesHubPage.tsx`: realny hub compare dla witryny pod sekcja `Zmiany`, z readiness, kontekstem active/baseline i linkami do kanonicznych compare entry pointow `/changes/*`
    - `SiteCompareLegacyRedirect.tsx`: helper dla cienkich redirectow kompatybilnosci ze starych compare route'ow do `/changes/*`, gdy sa jeszcze potrzebne
    - `SiteCrawlsPage.tsx`: historia crawl snapshotow dla witryny
    - `SiteNewCrawlPage.tsx`: dedykowany create-flow nowego snapshotu dla istniejacej witryny
    - `api.ts`, `routes.ts`, `context.ts`
  - `ai-review-editor/`: site-level AI Review Editor z lista dokumentow, ekranem dokumentu, version history, diff preview i helperami governance/stale state
  - `content-recommendations/`: site-level own-data Recommendations workspace z podwidokami `overview` / `active` / `implemented`, API client i testami
  - `competitive-gap/`: site-level Competitive Gap workspace z podwidokami `overview` / `strategy` / `competitors` / `sync` / `results`, reuse'ujacy ten sam backendowy sync, semantic, review i results flow
  - `jobs/`: lista snapshotow, create flow, detail snapshotu, legacy entry point
  - `pages/`: snapshotowa tabela pages, page taxonomy badges/summary, filtry, eksport + site current-state views (`SitePagesOverviewPage.tsx`, `SitePagesRecordsPage.tsx`) i `SitePagesComparePage.tsx`
  - `links/`: tabela links
  - `audit/`: snapshotowy raport audytowy + site current-state views (`SiteAuditOverviewPage`, `SiteAuditSectionsPage`) i `SiteAuditComparePage.tsx`
  - `gsc/`
    - `SiteGscPage.tsx`: site-level GSC overview/settings/import
    - `GscPage.tsx`: legacy snapshot GSC view z mostkiem do site workspace
    - `api.ts`
  - `opportunities/`: snapshot route, `SiteOpportunitiesCurrentPage.tsx` i `SiteOpportunitiesComparePage.tsx`
  - `internal-linking/`: snapshot route, `SiteInternalLinkingCurrentPage.tsx` i `SiteInternalLinkingComparePage.tsx`
  - `cannibalization/`: route cannibalization
  - `trends/`: route compare crawl + GSC
- `components/`: wspolne UI (`DataTable`, `DataViewHeader`, `ActionMenu`, `QuickFilterBar`, `FilterPanel`, `PaginationControls`, `SummaryCards`, ...)
- `i18n/`: `en.json`, `pl.json`, init i storage language
- `utils/`: formatowanie, query string, clipboard, error mapping
- `test/`: setup i helpery renderowania

## Testy: `tests/`
- `conftest.py`: fixtures SQLite i `TestClient`
- API / services:
  - `test_api_ai_review_editor.py`
  - `test_ai_review_editor_block_service.py`
  - `test_ai_review_editor_review_service.py`
  - `test_ai_review_editor_rewrite_service.py`
  - `test_ai_review_editor_version_service.py`
  - `test_ai_review_editor_migration.py`
  - `test_editor_block_parser_service.py`
  - `test_editor_review_engine_service.py`
  - `test_editor_review_llm_service.py`
  - `test_editor_rewrite_llm_service.py`
  - `test_api_competitive_gap.py`
  - `test_api_jobs_list.py`
  - `test_api_sites.py`
  - `test_api_site_compare.py`
  - `test_api_stage2.py`
  - `test_api_stage2_1.py`
  - `test_api_stage5.py`
  - `test_audit_service.py`
  - `test_export_service.py`
  - `test_gsc_integration.py`
  - `test_internal_linking.py`
  - `test_page_taxonomy.py`
  - `test_content_recommendations.py`
  - `test_competitive_gap_semantic_service.py`
  - `test_competitive_gap_semantic_arbiter_service.py`
  - `test_competitor_sync_service.py`
  - `test_cannibalization.py`
  - `test_priority_opportunities.py`
  - `test_trends_compare.py`
  - `test_alembic_revision_ids.py`
- crawler / extraction:
  - `test_links_extraction.py`
  - `test_meta_extraction_stage2.py`
  - `test_pipeline_and_stats.py`
  - `test_rendering_stage5.py`
  - `test_spider_scheduling.py`
  - `test_url_normalization.py`
- CLI / smoke:
  - `test_e2e_local_cli.py`
  - `test_postgres_smoke.py`

Frontend testy siedza obok feature'ow w `frontend/src/**/*.test.tsx`.

## Migracje: `alembic/versions/`
- `0001_initial.py`: schema bazowa `sites`, `crawl_jobs`, `pages`, `links`
- `0002_page_seo_fields.py`: wczesne pola SEO dla pages
- `0003_add_stopped_status.py`: status `stopped`
- `0004_stage4_page_metrics.py`: metryki on-page
- `0005_stage5_rendering_and_schema.py`: rendering/schema/robots
- `0006_stage6_gsc_integration.py`: `gsc_properties`, `gsc_url_metrics`, `gsc_top_queries`
- `0008_stage12a_competitive_gap_core.py`: core tabele Competitive Gap i strategii
- `0009_stage12a_competitor_sync_and_strategy_debug.py`: debug/status strategii i sync competitorow
- `0010_reco_lifecycle_state.py`: cienka tabela `site_content_recommendation_states` dla `mark done` i implemented outcome
- `0011_stage12a_sync_progress_and_reset.py`: progress syncu competitorow i reset runtime state
- `0012_stage12a_competitive_gap_hardening.py`: sync summary i diagnostics hardening
- `0013_stage12a_competitive_gap_sync_runs.py`: operational sync run store, retry/reset/stale recovery
- `0014_stage12a4_semantic_foundation.py`: semantic eligibility metadata, raw semantic candidate store i deterministic top-K foundation
- `0015_stage12a4_semantic_arbiter.py`: semantic decision cache, semantic run store i rerun/status support
- `0019_content_gap_candidates_v1.py`: persisted raw content gap candidates
- `0020_content_gap_review_runs_v1.py`: explicit review run lifecycle
- `0021_content_gap_items_v1.py`: persisted reviewed items
- `0023_ai_review_editor_stage1.py`: core tabele AI Review Editor
- `0024_ai_review_editor_stage4_workflow.py`: workflow issue / rewrite run state
- `0025_ai_review_editor_v6.py`: versioning i governance doprecyzowania
- `0026_ai_review_editor_stage7_inline_block_edit.py`: inline block edit
- `0027_ai_review_editor_stage8_block_ops.py`: insert/delete block
- `0028_ai_review_editor_stage9_status_cleanup.py`: cleanup legacy statusu `resolved` w `editor_review_issues`
- `0007_stage11_page_taxonomy.py`: trwałe pola page taxonomy w `pages`

ETAP 7, ETAP 8, ETAP 10.1, ETAP 10.2 i ETAP 10.3 nie dodaja nowej migracji:
- priority/opportunities, compare, site workspace, site-level GSC i site compare UX reuse'uja istniejace `sites`, `crawl_jobs`, `pages`, `links`, `gsc_properties`, `gsc_url_metrics`, `gsc_top_queries`

ETAP 11.2 tez nie dodaje nowej migracji:
- Content Recommendations sa liczone dynamicznie nad aktywnym snapshotem i own data only

ETAP 11.3 dodaje jedna cienka migracje:
- `site_content_recommendation_states` przechowuje site-level lifecycle rekomendacji
- nie miesza wielu snapshotow w `pages`, `links`, audit ani `gsc_*`
- rekord `mark done` nie oznacza wiecznego ukrycia rekomendacji; ten sam `recommendation_key` moze wrocic do active po przyszlym crawl snapshot

ETAP 11.3B nie dodaje nowej migracji:
- implemented filters, outcome windows i `too_early` reuse'uja ten sam lifecycle state oraz aktywny snapshot
- `implemented_summary` liczy scope po outcome window / mode / search, a status drilldown jest juz cienka warstwa UI/API nad tym samym payloadem
- frontend utrzymuje ten sam render order badge'y/statusow w jednym miejscu kontraktowym (`frontend/src/types/api.ts`)

## Gdzie zagladac przy taskach
- Site workspace foundation:
  `app/services/site_service.py`, `app/api/routes/sites.py`, `frontend/src/features/sites/`
- Create or reuse `Site` for new crawl:
  `app/services/crawl_job_service.py`
- GSC site-level config:
  `app/services/gsc_service.py`, `app/api/routes/gsc.py`, `frontend/src/features/gsc/`
- Snapshot-scoped pages/audit/links:
  `app/services/seo_analysis.py`, `app/services/crawl_job_service.py`, odpowiedni route i feature frontendu
- Page taxonomy:
  `app/services/page_taxonomy_service.py`, `app/api/routes/pages.py`, `frontend/src/features/pages/PagesPage.tsx`
- Content Recommendations:
  `app/services/content_recommendation_service.py`, `app/services/content_recommendation_rules.py`, `app/services/content_recommendation_keys.py`, `app/api/routes/site_content_recommendations.py`, `frontend/src/features/content-recommendations/`
- AI Review Editor:
  `app/api/routes/site_ai_review_editor.py`, `app/schemas/ai_review_editor.py`, `app/services/ai_review_editor_service.py`, `app/services/editor_document_block_service.py`, `app/services/editor_document_version_service.py`, `app/services/editor_review_run_service.py`, `app/services/editor_review_engine_service.py`, `app/services/editor_review_llm_service.py`, `app/services/editor_rewrite_service.py`, `app/services/editor_rewrite_llm_service.py`, `frontend/src/features/ai-review-editor/`, `tests/test_api_ai_review_editor.py`
- Competitive Gap:
  `app/services/competitive_gap_service.py`, `app/services/competitive_gap_sync_service.py`, `app/services/competitive_gap_sync_run_service.py`, `app/services/competitive_gap_semantic_rules.py`, `app/services/competitive_gap_semantic_service.py`, `app/services/competitive_gap_semantic_run_service.py`, `app/services/competitive_gap_semantic_arbiter_service.py`, `app/services/competitive_gap_extraction_service.py`, `app/services/competitive_gap_explanation_service.py`, `app/api/routes/site_competitive_gap.py`, `frontend/src/features/competitive-gap/`
- CSV eksport:
  `app/services/export_service.py`, `app/api/routes/exports.py`
- Priority/opportunities:
  `app/services/priority_rules.py`, `app/services/priority_service.py`, `frontend/src/features/opportunities/`
- Internal linking:
  `app/services/internal_linking_service.py`, `frontend/src/features/internal-linking/`
- Cannibalization:
  `app/services/cannibalization_service.py`, `frontend/src/features/cannibalization/`
- Trends:
  `app/services/trends_service.py`, `frontend/src/features/trends/`
- Site compare views:
  `app/services/site_compare_service.py`, `app/api/routes/site_compare.py`, `frontend/src/features/pages/`, `frontend/src/features/audit/`, `frontend/src/features/opportunities/`, `frontend/src/features/internal-linking/`

## Typowe checklisty zmian

### Zmiana modelu `Site` / `CrawlJob`
```text
app/db/models.py
-> alembic/versions/*
-> app/services/crawl_job_service.py
-> app/services/site_service.py
-> app/schemas/site.py lub crawl_job.py
-> app/api/routes/sites.py lub crawl_jobs.py
-> frontend/src/types/api.ts
-> frontend/src/features/sites/* lub jobs/*
-> tests/test_api_sites.py + frontend/src/features/sites/*.test.tsx
```

### Nowy endpoint
```text
app/schemas/*
-> app/services/*
-> app/api/routes/*
-> frontend/src/features/*/api.ts
-> frontend/src/types/api.ts
-> tests/test_api_*.py lub test dedykowany
```

### Zmiana GSC
```text
app/integrations/gsc/*
-> app/services/gsc_service.py
-> app/api/routes/gsc.py
-> frontend/src/features/gsc/*
-> frontend/src/features/sites/*
-> frontend/src/types/api.ts
-> tests/test_gsc_integration.py
-> frontend/src/features/gsc/*.test.tsx
```

### Zmiana read modelu `pages`
```text
app/db/models.py
-> alembic/versions/*
-> app/services/page_taxonomy_service.py
-> app/services/seo_analysis.py
-> app/services/crawl_job_service.py
-> app/api/routes/pages.py
-> app/services/export_service.py
-> frontend/src/types/api.ts
-> frontend/src/features/pages/PagesPage.tsx
-> tests/* + frontend/src/**/*.test.tsx
```

### Zmiana AI Review Editor
```text
app/schemas/ai_review_editor.py
-> app/api/routes/site_ai_review_editor.py
-> app/services/ai_review_editor_service.py
-> app/services/editor_document_block_service.py
-> app/services/editor_document_version_service.py
-> app/services/editor_review_run_service.py
-> app/services/editor_review_llm_service.py
-> app/services/editor_rewrite_service.py
-> app/services/editor_rewrite_llm_service.py
-> frontend/src/features/ai-review-editor/*
-> frontend/src/types/api.ts
-> tests/test_api_ai_review_editor.py
-> tests/test_ai_review_editor_*.py
-> frontend/src/features/ai-review-editor/AIReviewEditorPage.test.tsx
```

## Rzeczy, ktorych tu nie ma
- osobnego katalogu `docs/`
- auth uzytkownikow koncowych
- wielokontowego GSC
- worker queue i websocketow

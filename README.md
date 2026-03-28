# SEO Crawler (ETAP 12A.4)

Lokalny crawler SEO dla jednej domeny z:
- backendem FastAPI,
- crawlerem Scrapy + opcjonalnym Playwright fallback,
- PostgreSQL jako docelowa baza,
- frontendem React + Vite do codziennej pracy lokalnej,
- site-centric workspace nad snapshotami crawl,
- site-centric compare UX nad `active_crawl_id` i `baseline_crawl_id`,
- site-level AI Review Editor dla dokumentow blokowych z review/rewrite workflow, version history i rollbackiem,
- site-centric Content Recommendations (own data only),
- site-centric Competitive Gap z manual competitors,
- cienka warstwa lifecycle dla Content Recommendations (`mark done`, implemented, dynamic outcome, filters i outcome windows),
- manual competitor sync z lightweight diagnostics summary i on-demand explanation dla Competitive Gap,
- cienkim operational store dla competitor sync runow, retry/reset/recovery po restarcie API i lekkim UI operatorskim w Competitive Gap,
- semantic foundation + semantic arbiter/cache/run store dla Competitive Gap jako warstwa enrichmentu / legacy fallbacku,
- snapshot-aware Content Gap Review flow:
  - raw candidates w `site_content_gap_candidates`,
  - explicit review runs w `site_content_gap_review_runs`,
  - reviewed items w `site_content_gap_items`,
  - backendowy source selection `reviewed -> raw_candidates -> legacy`,
- czytelnymi empty states, readiness panel i competitor sync summary w UI Competitive Gap,
- site-level integracja Google Search Console,
- trwala taksonomia stron w `pages` (`page_type`, `page_bucket`, confidence, version),
- snapshotowymi widokami `pages`, `links`, `audit`, `opportunities`, `internal linking`, `cannibalization`, `trends`,
- eksportami CSV reuse'ujacymi te same read modele co API.

## Aktualny model mentalny
- `Site` jest trwala przestrzenia robocza witryny.
- `CrawlJob` jest snapshotem tej witryny w czasie.
- pierwszy crawl tworzy albo odnajduje `Site`,
- kolejne crawle tej samej witryny reuse'uja ten sam `site_id`,
- `pages`, `links`, audit i wszystkie podstawowe read modele nadal dzialaja dla jednego konkretnego `crawl_job`,
- klasyfikacja page taxonomy jest trwale zapisana per rekord `pages` i reuse'owana przez API, eksport i UI,
- Content Recommendations sa dynamiczna warstwa site-level nad aktywnym snapshotem i danymi wlasnymi witryny,
- Competitive Gap ma teraz snapshot-aware persisted warstwy Content Gap Review:
  - raw candidates po competitor sync,
  - explicit review runs uruchamiane jawnie,
  - reviewed items przypiete do konkretnego `basis_crawl_job_id`,
- backendowy read model Competitive Gap czyta dane w kolejnosci:
  - reviewed items dla aktywnego snapshotu,
  - raw candidates dla aktywnego snapshotu,
  - legacy dynamic fallback,
- semantic foundation i semantic arbiter pozostaja competitorowa warstwa cache/statusow i legacy fallbackiem; nie sa juz auto-triggerowanym primary path dla review layer,
- lifecycle rekomendacji jest cienka, trwala warstwa site-level; nie zmienia snapshotowego modelu `pages`, `links` ani `gsc_*`,
- AI Review Editor jest osobna warstwa site-level dla dokumentow redakcyjnych; biezacy stan dokumentu pochodzi z aktywnych `editor_document_blocks`,
- `source_content` i `normalized_content` dokumentu AI Review Editor sa reprezentacjami pochodnymi synchronizowanymi z aktywnego zestawu blokow,
- `mark done` chowa rekomendacje tylko dla tego samego `active_crawl_id`; jesli ten sam problem wraca w przyszlym crawl snapshot, rekomendacja moze znowu pojawic sie jako aktywna,
- compare w site workspace jest dodatkowa warstwa nad aktywnym i baseline crawl, a nie osobnym snapshot store,
- konfiguracja GSC nalezy do `site`,
- import danych GSC nadal jest wykonywany do konkretnego snapshotu `crawl_job`.

To jest najwazniejszy invariant repo:
- site-centric UX i routing nie oznaczaja mieszania wielu crawl snapshotow w podstawowych tabelach.

## Najwazniejsze funkcje

### Crawl i snapshoty
- create crawl z poziomu `/sites` albo `/jobs`
- create nowego snapshotu dla istniejacego `site`
- detail joba, stop joba, rerun z tymi samymi ustawieniami
- aktywny i opcjonalny baseline crawl w site workspace

### Snapshotowe widoki analityczne
- `pages` z page taxonomy, filtrami po typie/buckecie i summary per crawl
- `links`
- `audit`
- `opportunities`
- `internal linking`
- `cannibalization`
- `trends`

### Site compare UX
- compare-ready routing dla `pages`, `audit`, `opportunities`, `internal linking`
- baseline fallback do poprzedniego crawla tej samej witryny, jesli istnieje
- summary cards, badge i filtry zmian bez mieszania wielu snapshotow w jednej bazowej tabeli

### AI Review Editor
- site-level routing:
  - `/sites/:siteId/ai-review-editor/documents`
  - `/sites/:siteId/ai-review-editor/documents/:documentId`
- kanoniczny current source of truth dokumentu to aktywne `editor_document_blocks`
- parse HTML do blokow, inline manual edit pojedynczego bloku, insert before / insert after / delete block z guardem ostatniego bloku
- explicit review runs zapisujace issue dla konkretnego `document_version_hash`
- governance stale state:
  - review z poprzedniego stanu dokumentu jest oznaczany jako stale po pozniejszej zmianie blokow,
  - read model review summary / issue list zwraca flagi `latest_review_matches_current_document` i `review_matches_current_document`,
  - akcje issue (`dismiss`, `resolved_manual`, `rewrite`) sa blokowane dla stale review,
  - rewrite preview ma read flags `matches_current_document`, `matches_current_block`, `is_stale`
- AI rewrite pozostaje single-block preview:
  - request rewrite tworzy persisted rewrite run,
  - apply rewrite podmienia tylko docelowy blok i capture'uje nowa wersje dokumentu
- version history:
  - `document_parse`, `document_update`, `manual_block_edit`, `block_insert`, `block_delete`, `rewrite_apply`, `rollback`
  - diff preview porownuje snapshoty blokow i metadanych
  - restore / rollback tworzy nowa aktualna wersje bez nadpisywania historii
- ograniczenia:
  - brak drag & drop reorder, split/merge blokow, collaborative editing, rich-text editora, auto-review on save i automatycznego remapowania issue

### Site Intelligence
- ETAP 11.1: trwaĹ‚a page taxonomy zapisana w `pages`
- ETAP 11.2: site-centric Content Recommendations liczone dynamicznie z own data only
- ETAP 12A: site-centric Competitive Gap liczone nad manual competitors i aktywnym snapshotem witryny
- ETAP 12A.4+: semantic foundation / arbiter / cache / statusy pozostaja competitorowym enrichmentem i fallbackiem
- Semstorm ma osobny site-level discovery store:
  - preview `POST /sites/{site_id}/competitive-content-gap/semstorm/discovery-preview` zostaje lekkim debug/manual payloadem bez persistencji
  - persisted discovery runs `POST/GET /sites/{site_id}/competitive-content-gap/semstorm/discovery-runs*` zapisuje historie runow, competitorow i top queries
  - `GET /sites/{site_id}/competitive-content-gap/semstorm/opportunities` sklada cienki Semstorm opportunity layer nad persisted discovery, aktywnym crawlem i opcjonalnym GSC; ocenia `coverage_status`, `decision_type` i `opportunity_score_v2`, ale nadal nie wpina sie do finalnego read modelu `reviewed -> raw_candidates -> legacy`
  - Semstorm ma tez osobny lifecycle state i promoted backlog: `site_semstorm_opportunity_states` trzyma `new/accepted/dismissed/promoted`, a `site_semstorm_promoted_items` zapisuje wypromowane seed backlog items do dalszej pracy SEO
  - promoted backlog moze byc dalej materializowany do cienkiego planning store `site_semstorm_plan_items`, a nastepnie do osobnych brief scaffoldow w `site_semstorm_brief_items`; to nadal nie jest Content Recommendation ani finalny Competitive Gap result
  - brief scaffold moze dostac opcjonalny AI enrichment run store `site_semstorm_brief_enrichment_runs`; enrich/apply pozostaja jawna, synchroniczna warstwa nad istniejacym briefem, a nie osobnym content flow
  - brief scaffold ma tez cienki execution lifecycle nad tym samym brief itemem: `draft -> ready -> in_execution -> completed -> archived`, z prostym `assignee`, `execution_note` i osobnym read modelem `GET /sites/{site_id}/competitive-content-gap/semstorm/execution`
  - po zakonczeniu execution ten sam brief artifact moze wejsc do lekkiego feedback loopu `implemented / evaluated`: `POST /sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/implementation-status` ustawia stan wdrozenia, a `GET /sites/{site_id}/competitive-content-gap/semstorm/implemented` liczy dynamiczny outcome summary nad aktywnym snapshotem i dostepnym GSC bez mieszania Semstorm z Content Recommendations ani finalnym `competitive-gap/results`
- Content Gap Review flow:
  - competitor sync zapisuje raw candidates,
  - review run uruchamiany jawnie zamraza snapshot-aware context,
  - LLM review materializuje reviewed items,
  - UI i CSV reuse'uja ten sam backendowy source selection `reviewed -> raw_candidates -> legacy`
- reuse page taxonomy, internal linking, opportunities, cannibalization i GSC bez osobnej warstwy AI ani external keyword gap

### Google Search Console
- lokalny OAuth 2.0 dla developmentu
- jedna wybrana property na `site`
- reuse property przy kolejnych crawl snapshotach tej samej witryny
- import danych GSC do aktywnego snapshotu
- legacy job-centric GSC view nadal dziala jako snapshot detail / bridge

### ETAP 11.1 - Page Taxonomy / Classification
- `pages` dostaja trwałe pola:
  - `page_type`
  - `page_bucket`
  - `page_type_confidence`
  - `page_type_version`
  - `page_type_rationale`
- klasyfikacja jest regułowa, deterministyczna i centralnie trzymana w `app/services/page_taxonomy_service.py`
- sygnaly bazuja na:
  - `schema_types_json`
  - wzorcach URL / slugow / segmentow sciezki
  - `title`
  - `h1`
  - lekkim site-wide wykrywaniu powtarzalnych prefiksow typu `/blog/`, `/kategoria/`, `/produkt/`
- wynik jest reuse'owany przez:
  - `GET /crawl-jobs/{job_id}/pages`
  - `GET /crawl-jobs/{job_id}/page-taxonomy/summary`
  - `GET /crawl-jobs/{job_id}/export/pages.csv`
  - frontend `PagesPage.tsx`
- ETAP 11.1 pozostaje fundamentem pod kolejne moduly Site Intelligence

Ograniczenia heurystyk:
- brak NLP, embeddings i LLM
- brak recznych override'ow per site w UI
- przy nietypowych URL-ach lub bardzo ubogich sygnalach klasyfikacja moze wpasc do `other`
- `page_type_version` sluzy do jawnego backfillu i przyszlego strojenia reguł

### ETAP 11.2 / 11.3 - Content Recommendations (own data only + lifecycle)
- nowy modul site-centric dziala pod:
  - `GET /sites/{site_id}/content-recommendations`
  - `POST /sites/{site_id}/content-recommendations/mark-done`
  - `GET /sites/{site_id}/export/content-recommendations.csv`
- modul liczy rekomendacje dynamicznie nad:
  - aktywnym `crawl_job`
  - page taxonomy z ETAPU 11.1
  - sygnalami internal linking
  - priority / opportunities
  - snapshotowymi metrykami GSC i top queries
  - cannibalization jako sygnalem pomocniczym
- recommendation types:
  - `MISSING_SUPPORTING_CONTENT`
  - `THIN_CLUSTER`
  - `EXPAND_EXISTING_PAGE`
  - `MISSING_STRUCTURAL_PAGE_TYPE`
  - `INTERNAL_LINKING_SUPPORT`
- scoring pozostaje heurystyczny i explainable:
  - `priority_score`
  - `confidence`
  - `impact`
  - `effort`
  - `cluster_strength`
  - `coverage_gap_score`
  - `internal_support_score`
- kazda rekomendacja ma:
  - `rationale`
  - `signals`
  - `reasons`
  - `prerequisites`
  - `target_url` lub `suggested_page_type`
- frontend route:
  - `/sites/:siteId/content-recommendations`
  - filtry po `recommendation_type`, `segment`, `page_type`, `cluster`, `confidence`, `priority`
  - quick filters typu create new page / expand existing / strengthen cluster / improve internal support
  - aktywne rekomendacje z przyciskiem `Mark done`
  - backendowe filtry sekcji implemented po `outcome_status`, `primary_outcome_kind`, search i sortowaniu
  - outcome windows dla implemented: `7d`, `30d`, `90d`, `all`
  - summary bar sekcji implemented jest klikanym status drilldown
  - summary bar opiera sie o backendowy `implemented_summary`
  - `implemented_summary` liczy `total_count`, `status_counts` i `mode_counts` po `outcome_window` / mode / search, ale przed status drilldown
  - backend trzyma jedna wspolna kolejnosc implemented outcome statusow dla summary i sortowania, a frontend renderuje badge'e w tej samej kolejnosci z jednego stalego zrodla w warstwie UI
  - status `too_early`, gdy od `implemented_at` minelo za malo czasu dla wybranego okna
  - sekcja wdrozonych rekomendacji zwinięta do jednego wiersza z outcome summary i detalem before/after po rozwinieciu
  - eksport reuse'uje ten sam payload i te same filtry

ETAP 11.3 doklada:
- nowa tabele `site_content_recommendation_states`
- deterministyczny `recommendation_key`
- `implemented_at`, `implemented_crawl_job_id` i opcjonalny baseline z chwili klikniecia
- dynamiczny outcome tracking liczony nad:
  - snapshotem z chwili wdrozenia
  - aktualnym aktywnym snapshotem workspace
- outcome dla:
  - URL / GSC cases (`impressions`, `clicks`, `avg position`, opcjonalnie CTR)
  - issue-driven cases (`internal linking`, `cannibalization`, `issue flags`)

ETAP 11.3B nie dodaje nowej migracji ani nowego store:
- implemented filters, outcome windows i `too_early` sa cienka warstwa read-modelowa nad istniejacym lifecycle state i aktywnym snapshotem
- backend zwraca tez `implemented_summary`, aby UI moglo pokazac summary bar i status drilldown bez osobnego liczenia po stronie frontendu
- aktywny status drilldown nie zmienia scope `implemented_summary`; lista moze byc pusta, gdy summary nadal pokazuje scope po window / mode / search
- outcome nadal jest liczony dynamicznie nad tym samym `site_content_recommendation_states`, aktywnym crawlem i dostepnymi sygnalami own-data only

Ograniczenia heurystyk:
- to nie jest competitor gap ani external keyword gap
- brak external keyword APIs, embeddings, NLP, LLM i generatora tresci
- brak content briefs, editorial calendar i publishing workflow
- baseline compare moze byc obecny w kontekscie workspace, ale nie jest wymagany do dzialania modulu

## Wymagania
- Python `3.12+`
- Node.js `20+`
- Docker Desktop (`docker compose`)
- PowerShell
- Chromium zainstalowany przez Playwright, jesli chcesz korzystac z `render_mode=auto` albo `render_mode=always`

## Dokumenty pomocnicze
- `AGENTS.md`: szybki przewodnik dla agenta
- `REPO_MAP.md`: mapa katalogow i entry pointow
- `ARCHITECTURE.md`: architektura i invariants

## First run
Terminal 1:
```bash
copy .env.example .env
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command bootstrap
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command playwright-install
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-up
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-reset
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command migrate
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command api
```

Terminal 2:
```bash
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Frontend domyslnie:
```text
http://127.0.0.1:5173
```

API domyslnie:
```text
http://127.0.0.1:8000
```

## Izolowany worktree local flow
Ten repo moze dzialac rownolegle w kilku `git worktree`, ale kazdy worktree powinien miec wlasny lokalny runtime.

Nowe komendy developerskie:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command init-worktree-env
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command clone-worktree-db
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command start-worktree
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command stop-worktree
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command info-worktree
```

Co robi `init-worktree-env`:
- wylicza deterministyczny `WORKTREE_INSTANCE_ID` z katalogu worktree,
- ustawia izolowany `COMPOSE_PROJECT_NAME`,
- ustawia osobne porty dla PostgreSQL / API / frontendu,
- aktualizuje tylko lokalne, gitignore'owane pliki `.env`, `frontend/.env.local` i `.local/worktree/*`,
- ustawia osobne sciezki dla lokalnych plikow GSC (`.local/worktree/gsc/*`).

Typowy flow dla nowego worktree:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command init-worktree-env
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command clone-worktree-db
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command start-worktree
```

`clone-worktree-db`:
- wykrywa domyslny source worktree przez `git worktree list` albo przyjmuje `-SourceWorktreePath`,
- robi logiczna kopie PostgreSQL `pg_dump | pg_restore` do izolowanej instancji tego worktree,
- po restore uruchamia `alembic upgrade head` na bazie worktree.

Przyklad z jawnym zrodlem:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command init-worktree-env -SourceWorktreePath ..\seo_crawler
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command clone-worktree-db -SourceWorktreePath ..\seo_crawler
```

`start-worktree` uruchamia:
- bootstrap `.venv`,
- izolowany PostgreSQL tego worktree,
- migracje,
- backend w osobnym oknie PowerShell,
- frontend Vite w osobnym oknie PowerShell.

`stop-worktree` zatrzymuje lokalne procesy backend/frontend zapisane w `.local/worktree/runtime.env` oraz wykonuje `docker compose down` tylko dla tego worktree.

## Daily run
Terminal 1:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-up
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command api
```

Terminal 2:
```bash
cd frontend
npm run dev
```

Jesli byly zmiany w modelu bazy lub migracjach:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command migrate
```

## Backend quick start
```bash
copy .env.example .env
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command bootstrap
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command playwright-install
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-up
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-reset
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command migrate
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command api
```

## Frontend quick start
```bash
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

## Konfiguracja GSC

Minimalna konfiguracja `.env`:
```env
FRONTEND_APP_URL=http://127.0.0.1:5173
GSC_CLIENT_SECRETS_PATH=.local/worktree/gsc/credentials.json
GSC_TOKEN_PATH=.local/worktree/gsc/token.json
GSC_OAUTH_STATE_PATH=.local/worktree/gsc/oauth_state.json
GSC_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/gsc/oauth/callback
GSC_DEFAULT_TOP_QUERIES_LIMIT=20
GSC_METRICS_ROW_LIMIT=25000
```

Domyslne pliki lokalne:
- `.local/worktree/gsc/credentials.json`
- `.local/worktree/gsc/token.json`
- `.local/worktree/gsc/oauth_state.json`

Pliki w `.local/worktree/gsc/` sa ignorowane przez git i sa przeznaczone tylko do lokalnego developmentu konkretnego worktree.

### Jak przygotowac Google credentials
1. W Google Cloud utworz lub wybierz projekt.
2. Wlacz `Google Search Console API`.
3. Utworz OAuth client credentials typu `Web application`.
4. Dodaj redirect URI:
   - `http://127.0.0.1:8000/gsc/oauth/callback`
5. Pobierz JSON i zapisz go jako:
   - `.local/worktree/gsc/credentials.json`

## GSC local flow po ETAPIE 11.2
1. Otworz `/sites` i wejdz do workspace witryny.
2. Przejdz do `/sites/:siteId/gsc/settings`.
3. Kliknij `Connect GSC`.
4. Zakoncz lokalny OAuth i wroc do konfiguracji site workspace.
5. Wybierz property zgodna z domena witryny.
6. Ustaw aktywny crawl w workspace witryny.
7. Przejdz do `/sites/:siteId/gsc/import` i uruchom import do aktywnego snapshotu:
   - jednego zakresu, albo
   - `28d + 90d`
8. Analizuj dane w kontekscie konkretnego snapshotu:
   - site-level GSC workspace pokazuje status integracji i importu
   - `/jobs/:jobId/gsc` pozostaje snapshotowym detailed view

Wazne:
- property jest trwale przypiete do `site`,
- nowe crawle tej samej witryny reuse'uja te sama konfiguracje,
- dane GSC nadal trafiaja do konkretnego `crawl_job`.

### AI Review Editor
- route'y site-level:
  - `/sites/:siteId/ai-review-editor/documents`
  - `/sites/:siteId/ai-review-editor/documents/:documentId`
- source of truth:
  - kanoniczny aktualny stan dokumentu to aktywne `editor_document_blocks`
  - `source_content` i `normalized_content` sa pochodnymi reprezentacjami synchronizowanymi z aktywnych blokow
- glowny workflow:
  - create / load dokumentu
  - parse HTML do blokow
  - review run nad aktualnym snapshotem aktywnych blokow
  - issue workflow: `dismiss`, `resolved_manual`, `AI rewrite`, `apply rewrite`
  - inline manual edit pojedynczego bloku
  - insert before / insert after / delete block
  - version history, diff preview, rollback / restore
- governance po ETAPIE 9:
  - latest review moze byc `current` albo `stale`
  - stale review pozostaje tylko historycznym kontekstem; workflow issue jest wtedy blokowany do czasu nowego review
  - rewrite preview jest uznawany za bezpieczny do apply tylko wtedy, gdy nadal pasuje do aktualnego stanu dokumentu
  - backend i UI jawnie sygnalizuja failed review/rewrite runy oraz stany nieaktualne
- glowne warstwy backendowe:
  - `app/services/ai_review_editor_service.py`
  - `app/services/editor_document_block_service.py`
  - `app/services/editor_document_version_service.py`
  - `app/services/editor_review_run_service.py`
  - `app/services/editor_review_engine_service.py`
  - `app/services/editor_review_llm_service.py`
  - `app/services/editor_rewrite_service.py`
  - `app/services/editor_rewrite_llm_service.py`
- frontend:
  - `frontend/src/features/ai-review-editor/AIReviewEditorDocumentsPage.tsx`
  - `frontend/src/features/ai-review-editor/AIReviewEditorDocumentPage.tsx`
  - `frontend/src/features/ai-review-editor/AIReviewEditorVersionHistorySection.tsx`
  - `frontend/src/features/ai-review-editor/AIReviewEditorDiffPreviewSection.tsx`
- ograniczenia modulu:
  - brak drag & drop reorder
  - brak split/merge blokow
  - brak collaborative editing i live sync
  - brak rich-text editora
  - brak auto-review on save
  - brak automatycznego remapowania issue do nowego stanu dokumentu bez twardej reguly

## Frontend routing

### Glowny site-centric routing
- `/` -> redirect do `/sites`
- `/sites` -> lista witryn + zarzadzanie workspace'ami + create nowego crawla
- `/sites/new` -> dodanie witryny / pierwszy crawl
- `/sites/:siteId` -> site overview
- `/sites/:siteId/progress` -> site-level dashboard postepu oparty o aktywny crawl, pomocniczy baseline, trend KPI, poprawy/regresje, postep wdrozen i timeline
- `/sites/:siteId/ai-review-editor` -> redirect do listy dokumentow AI Review Editor
- `/sites/:siteId/ai-review-editor/documents` -> lista dokumentow AI Review Editor dla witryny
- `/sites/:siteId/ai-review-editor/documents/:documentId` -> current-state ekran dokumentu AI Review Editor z issue panelem, rewrite preview i historia wersji
- `/sites/:siteId/pages` -> current-state pages overview dla aktywnego crawla
- `/sites/:siteId/pages/records` -> current-state records list dla aktywnego crawla
- `/sites/:siteId/audit` -> current-state audit overview dla aktywnego crawla
- `/sites/:siteId/audit/sections` -> current-state audit sections dla aktywnego crawla
- `/sites/:siteId/opportunities` -> current-state SEO opportunities overview dla aktywnego crawla
- `/sites/:siteId/opportunities/records` -> current-state opportunity records dla aktywnego crawla
- `/sites/:siteId/internal-linking` -> current-state internal linking overview dla aktywnego crawla
- `/sites/:siteId/internal-linking/issues` -> current-state internal linking issues dla aktywnego crawla
- `/sites/:siteId/changes` -> hub compare dla witryny
- `/sites/:siteId/changes/pages` -> compare pages nad aktywnym snapshotem; kanoniczny entry point sekcji `Zmiany`
- `/sites/:siteId/changes/audit` -> compare audit nad aktywnym snapshotem; kanoniczny entry point sekcji `Zmiany`
- `/sites/:siteId/changes/opportunities` -> compare opportunities nad aktywnym snapshotem; kanoniczny entry point sekcji `Zmiany`
- `/sites/:siteId/changes/internal-linking` -> compare internal linking nad aktywnym snapshotem; kanoniczny entry point sekcji `Zmiany`
- `/sites/:siteId/crawls` -> historia crawl snapshotow witryny
- `/sites/:siteId/crawls/new` -> nowy crawl dla istniejacej witryny
- `/sites/:siteId/content-recommendations` -> site-centric overview Content Recommendations
- `/sites/:siteId/content-recommendations/active` -> aktywne own-data Content Recommendations
- `/sites/:siteId/content-recommendations/implemented` -> wdrozone / evaluated Content Recommendations
- `/sites/:siteId/competitive-gap` -> site-centric Competitive Gap overview
- `/sites/:siteId/competitive-gap/strategy` -> strategia Competitive Gap
- `/sites/:siteId/competitive-gap/competitors` -> zarzadzanie lista konkurentow
- `/sites/:siteId/competitive-gap/sync` -> operacyjny widok synchronizacji i runtime
- `/sites/:siteId/competitive-gap/results` -> glowny widok wynikow Competitive Gap
- `/sites/:siteId/competitive-gap/semstorm/discovery` -> operatorski widok Semstorm discovery runow
- `/sites/:siteId/competitive-gap/semstorm/opportunities` -> osobny frontendowy widok Semstorm opportunities
- `/sites/:siteId/competitive-gap/semstorm/promoted` -> cienki backlog wypromowanych Semstorm seeds
- `/sites/:siteId/competitive-gap/semstorm/plans` -> cienki planning workspace dla wypromowanych Semstorm items
- `/sites/:siteId/competitive-gap/semstorm/briefs` -> cienki execution workspace dla deterministicznych brief scaffoldow
- `/sites/:siteId/competitive-gap/semstorm/execution` -> cienki board realizacji / handoffu dla briefow Semstorm
- `/sites/:siteId/competitive-gap/semstorm/implemented` -> cienki outcome / feedback workspace dla wdrozonych briefow Semstorm
- `/sites/:siteId/gsc` -> site-level GSC overview
- `/sites/:siteId/gsc/settings` -> site-level konfiguracja property GSC
- `/sites/:siteId/gsc/import` -> import GSC do aktywnego crawla

Compare entry points sa skanalizowane do sekcji `Zmiany`:
- `/sites/:siteId/changes/pages`
- `/sites/:siteId/changes/audit`
- `/sites/:siteId/changes/opportunities`
- `/sites/:siteId/changes/internal-linking`

Kontekst workspace jest trzymany w URL:
- `active_crawl_id`
- `baseline_crawl_id`

### Legacy / snapshot-centric routing
- `/jobs` -> lista snapshotow crawl job
- `/jobs/:jobId` -> detail snapshotu
- `/jobs/:jobId/pages`
- `/jobs/:jobId/links`
- `/jobs/:jobId/audit`
- `/jobs/:jobId/opportunities`
- `/jobs/:jobId/internal-linking`
- `/jobs/:jobId/cannibalization`
- `/jobs/:jobId/gsc`
- `/jobs/:jobId/trends`

Snapshotowe route'y nadal dzialaja:
- jako kompatybilnosc wsteczna,
- jako detal pojedynczego crawl snapshotu,
- z mostkiem do odpowiedniego site workspace.

## Glowny UX po ETAPIE 12A.4
- shell aplikacji ma sticky header + sidebar + main content,
- header pokazuje branding `SEO Flow`, logiczny tytul aktualnej sekcji, theme/language toggle i placeholdery settings/account,
- sidebar jest glowna nawigacja aplikacji:
  - site switcher + szybkie wyszukiwanie witryny + `Dodaj witryne`
  - status aktualnie wybranej witryny
  - site menu dla overview / progress / pages / audit / opportunities / internal linking / intelligence / GSC / crawls / changes
  - sekcja globalna dla `Wszystkie witryny` i `Operacje`
- nowy crawl tworzony z `/sites` albo `/jobs` konczy w workspace witryny,
- `/sites/new` daje osobne, lekkie wejscie do zalozenia nowej witryny i pierwszego crawla,
- create nowego crawla z poziomu witryny tworzy kolejny snapshot w tym samym `site`,
- site overview jest current-first: pokazuje aktywny crawl, KPI aktywnego snapshotu, sygnaly do dzialania, skroty workspace, historie i create flow, a baseline zostawia jako pomocniczy kontekst,
- `/sites/:siteId/progress` odpowiada na pytanie `czy idziemy do przodu?`: pokazuje status aktywnego crawla, trend KPI, poprawy/regresje, postep wdrozen i timeline bez przepinania compare route'ow na nowe semantyki,
- `/sites/:siteId/opportunities` i `/sites/:siteId/internal-linking` sa current-state views nad aktywnym crawlem, a compare dla tych obszarow pozostaje pod `/sites/:siteId/changes/opportunities` i `/sites/:siteId/changes/internal-linking`,
- site workspace shell pokazuje kompaktowy current-first context bar z nazwa witryny, root URL, aktywnym crawlem, statusem GSC, CTA `Nowy crawl` i lekkim wejsciem do `Zmian`,
- compare-first feeling zostal ograniczony w shellu; compare pozostaje dostepny przez sekcje `Zmiany`, dedykowany hub `/sites/:siteId/changes` i kanoniczne entry pointy `/sites/:siteId/changes/*`,
- `/jobs/:jobId/pages` pokazuje taxonomy badges, summary i filtry po `page_type` / `page_bucket`,
- `Rekomendacje tresci` sa rozdzielone na `Przeglad`, `Aktywne` i `Wdrozone`,
- `/sites/:siteId/content-recommendations/active` pozostaje glownym widokiem roboczym z `Mark done`, filtrami i explainable rationale,
- `/sites/:siteId/content-recommendations/implemented` pozostaje widokiem lifecycle / outcome tracking opartym tylko o dane wlasne witryny,
- `Braki wzgledem konkurencji` sa rozdzielone na `Przeglad`, `Strategie`, `Konkurentow`, `Synchronizacje` i `Wyniki`,
- `/sites/:siteId/competitive-gap/sync` skupia operacyjne flow sync / retry / semantic / review runs bez zmiany semantyki backendu,
- `/sites/:siteId/competitive-gap/results` pozostaje glownym ekranem roboczym dla wynikow i filtrow Competitive Gap, z tym samym source mode `reviewed/raw/legacy`,
- Semstorm ma osobny frontendowy slice w Competitive Gap workspace:
  - `/sites/:siteId/competitive-gap/semstorm/discovery` dla persisted discovery runow,
  - `/sites/:siteId/competitive-gap/semstorm/opportunities` dla cienkiego coverage/opportunity layer nad persisted discovery,
  - `/sites/:siteId/competitive-gap/semstorm/promoted` dla trwalego backlogu wypromowanych seeds,
  - `/sites/:siteId/competitive-gap/semstorm/plans` dla cienkiego persisted planning layer nad promoted backlogiem,
  - `/sites/:siteId/competitive-gap/semstorm/briefs` dla osobnych execution packets / brief scaffoldow nad plan items,
  - `/sites/:siteId/competitive-gap/semstorm/execution` dla lekkiego execution workflow nad briefami z `assignee`, `execution_note` i statusem handoffu,
  - `/sites/:siteId/competitive-gap/semstorm/implemented` dla lekkiego feedback loopu nad wdrozonymi briefami, z dynamicznym outcome summary liczonym nad aktywnym snapshotem i dostepnym GSC,
  - selection Semstorm (`run_id`, `plan_id`, `brief_id`, `enrichment_run_id`) pozostaje odtwarzalna z query stringa, z korekta stalego ID do aktualnie widocznej listy,
  - opportunities wspiera selection, bulk actions `Accept / Dismiss / Promote` i persisted `state_status`,
  - promoted backlog wspiera bulk action `Create plan`, plan items wspieraja bulk `Create brief`, a briefs maja osobny lekki CRUD statusu i zawartosci execution packetu, jawne akcje execution lifecycle oraz outcome lifecycle `implemented / evaluated / archived`,
  - ten frontend nie miesza Semstorm z glownym `/competitive-gap/results`,
- `/sites/:siteId/changes/pages`, `/changes/audit`, `/changes/opportunities`, `/changes/internal-linking` nadal dokladaja delty nad aktywnym snapshotem zamiast budowac jedna historyczna tabele; compare pozostaje osobna warstwa nawigacyjna,
- top-level `/sites/:siteId/pages`, `/audit`, `/opportunities`, `/internal-linking` odpowiadaja juz za current-state views aktywnego crawla,
- site GSC jest rozdzielone na `Przeglad`, `Konfiguracja` i `Import`,
- konfiguracja property nadal nalezy do witryny, a import nadal trafia do aktywnego crawla,
- snapshotowe widoki `pages`, `audit`, `opportunities`, `internal linking`, `cannibalization`, `trends` nadal pracuja na `job_id`.

## API FastAPI

### Site workspace
- `GET /sites`
- `GET /sites/{site_id}`
- `GET /sites/{site_id}/crawls`
- `POST /sites/{site_id}/crawls`
- `GET /sites/{site_id}/ai-review-editor/documents`
- `POST /sites/{site_id}/ai-review-editor/documents`
- `GET /sites/{site_id}/ai-review-editor/documents/{document_id}`
- `PUT /sites/{site_id}/ai-review-editor/documents/{document_id}`
- `POST /sites/{site_id}/ai-review-editor/documents/{document_id}/parse`
- `GET /sites/{site_id}/ai-review-editor/documents/{document_id}/blocks`
- `POST /sites/{site_id}/ai-review-editor/documents/{document_id}/blocks`
- `PUT /sites/{site_id}/ai-review-editor/documents/{document_id}/blocks/{block_key}`
- `DELETE /sites/{site_id}/ai-review-editor/documents/{document_id}/blocks/{block_key}`
- `GET /sites/{site_id}/ai-review-editor/documents/{document_id}/review-summary`
- `GET /sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs`
- `POST /sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs`
- `GET /sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs/{review_run_id}`
- `GET /sites/{site_id}/ai-review-editor/documents/{document_id}/issues`
- `GET /sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs/{review_run_id}/issues`
- `POST /sites/{site_id}/ai-review-editor/documents/{document_id}/issues/{issue_id}/dismiss`
- `POST /sites/{site_id}/ai-review-editor/documents/{document_id}/issues/{issue_id}/resolve-manual`
- `GET /sites/{site_id}/ai-review-editor/documents/{document_id}/issues/{issue_id}/rewrite-runs`
- `POST /sites/{site_id}/ai-review-editor/documents/{document_id}/issues/{issue_id}/rewrite-runs`
- `GET /sites/{site_id}/ai-review-editor/documents/{document_id}/rewrite-runs/{rewrite_run_id}`
- `POST /sites/{site_id}/ai-review-editor/documents/{document_id}/rewrite-runs/{rewrite_run_id}/apply`
- `GET /sites/{site_id}/ai-review-editor/documents/{document_id}/versions`
- `GET /sites/{site_id}/ai-review-editor/documents/{document_id}/versions/{version_id}`
- `GET /sites/{site_id}/ai-review-editor/documents/{document_id}/versions/{version_id}/diff`
- `POST /sites/{site_id}/ai-review-editor/documents/{document_id}/versions/{version_id}/restore`
- `GET /sites/{site_id}/content-recommendations`
- `POST /sites/{site_id}/content-recommendations/mark-done`
- `GET /sites/{site_id}/competitive-content-gap`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/discovery-preview`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/discovery-runs`
- `GET /sites/{site_id}/competitive-content-gap/semstorm/discovery-runs`
- `GET /sites/{site_id}/competitive-content-gap/semstorm/discovery-runs/{run_id}`
- `GET /sites/{site_id}/competitive-content-gap/semstorm/opportunities`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/accept`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/dismiss`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/promote`
- `GET /sites/{site_id}/competitive-content-gap/semstorm/promoted`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/promoted/actions/create-plan`
- `GET /sites/{site_id}/competitive-content-gap/semstorm/plans`
- `GET /sites/{site_id}/competitive-content-gap/semstorm/plans/{plan_id}`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/plans/{plan_id}/status`
- `PUT /sites/{site_id}/competitive-content-gap/semstorm/plans/{plan_id}`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/plans/actions/create-brief`
- `GET /sites/{site_id}/competitive-content-gap/semstorm/briefs`
- `GET /sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/status`
- `PUT /sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}`
- `GET /sites/{site_id}/competitive-content-gap/semstorm/execution`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/execution-status`
- `PUT /sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/execution`
- `GET /sites/{site_id}/competitive-content-gap/semstorm/implemented`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/implementation-status`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/enrich`
- `GET /sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/enrichment-runs`
- `POST /sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/enrichment-runs/{run_id}/apply`
- `GET /sites/{site_id}/competitive-content-gap/strategy`
- `PUT /sites/{site_id}/competitive-content-gap/strategy`
- `GET /sites/{site_id}/competitive-content-gap/competitors`
- `GET /sites/{site_id}/competitive-content-gap/review-runs`
- `POST /sites/{site_id}/competitive-content-gap/review-runs/{run_id}/retry`
- `POST /sites/{site_id}/competitive-content-gap/semantic/re-run`
- `POST /sites/{site_id}/competitive-content-gap/competitors/{competitor_id}/sync`

### Site compare
- `GET /sites/{site_id}/pages`
- `GET /sites/{site_id}/audit`
- `GET /sites/{site_id}/opportunities`
- `GET /sites/{site_id}/internal-linking`

### Site-level GSC
- `GET /sites/{site_id}/gsc/oauth/start`
- `GET /sites/{site_id}/gsc/summary`
- `GET /sites/{site_id}/gsc/properties`
- `PUT /sites/{site_id}/gsc/property`
- `POST /sites/{site_id}/gsc/import`
- `GET /gsc/oauth/callback`

### Crawl snapshots
- `GET /health`
- `GET /crawl-jobs`
- `POST /crawl-jobs`
- `GET /crawl-jobs/{job_id}`
- `POST /crawl-jobs/{job_id}/stop`
- `GET /crawl-jobs/{job_id}/pages`
- `GET /crawl-jobs/{job_id}/page-taxonomy/summary`
- `GET /crawl-jobs/{job_id}/links`
- `GET /crawl-jobs/{job_id}/audit`
- `GET /crawl-jobs/{job_id}/opportunities`
- `GET /crawl-jobs/{job_id}/internal-linking/overview`
- `GET /crawl-jobs/{job_id}/internal-linking/issues`
- `GET /crawl-jobs/{job_id}/cannibalization`
- `GET /crawl-jobs/{job_id}/cannibalization/pages/{page_id}`
- `GET /crawl-jobs/{job_id}/trends/overview`
- `GET /crawl-jobs/{job_id}/trends/crawl`
- `GET /crawl-jobs/{job_id}/trends/gsc`

### Legacy snapshot GSC endpoints
- `GET /crawl-jobs/{job_id}/gsc/oauth/start`
- `GET /crawl-jobs/{job_id}/gsc/summary`
- `GET /crawl-jobs/{job_id}/gsc/properties`
- `PUT /crawl-jobs/{job_id}/gsc/property`
- `POST /crawl-jobs/{job_id}/gsc/import`
- `GET /crawl-jobs/{job_id}/gsc/top-queries`
- `GET /crawl-jobs/{job_id}/pages/{page_id}/gsc/top-queries`

### Eksporty CSV
- `GET /sites/{site_id}/export/content-recommendations.csv`
- `GET /crawl-jobs/{job_id}/export/pages.csv`
- `GET /crawl-jobs/{job_id}/export/links.csv`
- `GET /crawl-jobs/{job_id}/export/audit.csv`
- `GET /crawl-jobs/{job_id}/export/opportunities.csv`
- `GET /crawl-jobs/{job_id}/export/gsc-top-queries.csv`
- `GET /crawl-jobs/{job_id}/export/cannibalization.csv`
- `GET /crawl-jobs/{job_id}/export/crawl-compare.csv`
- `GET /crawl-jobs/{job_id}/export/gsc-compare.csv`

## Snapshotowe obszary funkcjonalne

### Pages
- filtrowanie, sortowanie, paginacja
- sygnaly on-page, rendering, schema, robots
- metryki GSC dla `28d` i `90d`
- priority score i opportunities metadata
- deep-linki do snapshotowych analiz

### Links
- linki wewnetrzne i zewnetrzne
- filtry link health
- eksport aktualnego widoku

### Audit
- raport sekcyjny liczony z read modelu
- deep-linki do `pages` i `links`

### Opportunities
- snapshotowe grupy opportunities
- priority score, impact, effort, rationale

### Internal linking
- snapshotowa ocena orphan-like, weakly linked, anchor diversity i equity

### Cannibalization
- snapshotowy query overlap i klastry konfliktow URL-i

### Trends
- compare crawl snapshotow dla tego samego `site`
- compare zakresow GSC dla jednego snapshotu

### Site compare views
- `pages`: flagi `new`, `missing`, `changed`, `improved`, `worsened` plus filtry zmian title/H1/canonical/noindex/priority/internal linking/content length
- `pages`: trwałe page taxonomy (`page_type`, `page_bucket`, confidence, version) + filtry i eksport reuse'ujace ten sam kontrakt
- `audit`: resolved vs new vs improved vs worsened sekcje audytu
- `opportunities`: nowe / rozwiazane opportunity, zmiany priorytetu i wejscie / wyjscie z grupy actionable
- `internal linking`: orphan-like, weak important, link equity, linking pages, anchor diversity i boilerplate delty

## CSV eksport
Eksport przez UI, API i CLI korzysta z tej samej warstwy backendowej.

Wlasciwosci:
- stabilna kolejnosc kolumn
- UTF-8 z BOM dla lepszej wspolpracy z Excel na Windows
- eksport calego joba albo aktualnego widoku, tam gdzie endpoint to wspiera
- reuse tego samego filtrowania i tych samych read modeli co API
- Competitive Gap CSV reuse'uje ten sam source selection co endpoint:
  - reviewed items dla aktywnego snapshotu,
  - raw candidates fallback,
  - legacy fallback koncowy

## Crawl przez CLI
Uruchomienie crawl:
```bash
python -m app.cli.run_crawl https://example.com --max-urls 300 --max-depth 4 --delay 0.5
```

Z render fallbackiem:
```bash
python -m app.cli.run_crawl https://example.com --max-urls 300 --max-depth 4 --delay 0.5 --render-mode auto --render-timeout-ms 8000 --max-rendered-pages 25
```

To samo przez PowerShell:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command crawl -StartUrl https://example.com -MaxUrls 300 -MaxDepth 4 -Delay 0.5 -RenderMode auto -RenderTimeoutMs 8000 -MaxRenderedPages 25
```

## Testy i build
Backend:
```bash
python -m pytest
python -m pytest tests/test_api_ai_review_editor.py tests/test_ai_review_editor_block_service.py tests/test_ai_review_editor_review_service.py tests/test_ai_review_editor_rewrite_service.py tests/test_ai_review_editor_version_service.py tests/test_ai_review_editor_migration.py tests/test_editor_block_parser_service.py tests/test_editor_review_engine_service.py tests/test_editor_review_llm_service.py tests/test_editor_rewrite_llm_service.py -q
```

Frontend:
```bash
cd frontend
npm test
npm test -- src/features/ai-review-editor/AIReviewEditorPage.test.tsx
npm run build
```

Smoke PostgreSQL:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command smoke-postgres
```

## PostgreSQL auth mismatch
Normal local startup commands now keep a trusted credential lock in `.local/postgres/credentials.env` after a successful PostgreSQL connection. That lock is the source of truth for the local password and it does not change during normal startup. It is updated only when the lock is first created or when you run `db-refresh-lock` deliberately. If `.env` drifts away from the stored password, `db-up`, `db-wait`, `migrate`, `api` and `start-local.cmd` sync `.env` back to the locked credentials automatically. If the PostgreSQL role password itself drifts locally, `db-wait` restores PostgreSQL back to the trusted stored password before continuing. Legacy lock files are also probed once against the running DB before they are ignored.

If local PostgreSQL suddenly starts returning `password authentication failed for user "postgres"` while `.env` still points at `postgres/postgres`, treat it first as an old Docker volume problem, not as a migration or test changing the password.

If you do not need the current local DB data:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-reset
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command migrate
```

If you need to keep the data, do not reset the volume. Update `.env` to the real password already stored in PostgreSQL, then refresh the local credential lock:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-refresh-lock
```

If you want to keep the data and deliberately set the running PostgreSQL role password to the value from `.env`:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-align-password
```

If you want to inspect or recreate `.env` from the current lock without touching Docker:
```bash
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-sync-env
```

## Ograniczenia
- crawl jednej domeny startowej
- linki zewnetrzne sa zapisywane, ale nie sa crawlowane jako `pages`
- brak auth uzytkownikow koncowych
- brak wielokontowego GSC
- brak worker queue, websocketow, Celery i Redis
- brak zaawansowanego site-level compare engine ponad wieloma crawl snapshotami dla GSC
- brak competitor compare, external keyword gap, AI content generation, content briefs i publication planning

## Co jest celowo rozdzielone
- site-level:
  - `Site`
  - wybrana property GSC
  - historia crawl snapshotow
  - active/baseline context
- crawl-level:
  - `CrawlJob`
  - `pages`
  - `links`
  - audit
  - opportunities
  - internal linking
  - cannibalization
  - imported `gsc_url_metrics`
  - imported `gsc_top_queries`

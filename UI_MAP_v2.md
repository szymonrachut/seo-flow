# UI_MAP_v2.md

Docelowa mapa UI frontendu dla SEO Flow.

Cel:
- uporzadkowac UI wokol site workspace,
- pokazac pelna strukture w sidebarze,
- ustawic current-first jako domyslny tryb pracy,
- schowac compare pod sekcja `Zmiany`,
- rozdzielic tam, gdzie ma to sens:
  - przeglad,
  - konfiguracje,
  - rekordy / wyniki,
  - operacje.

Dokument opisuje target state.
Nie zastepuje:
- `README.md`
- `REPO_MAP.md`
- `ARCHITECTURE.md`
- `UI_MAP.md`

---

## 1. Zasady nadrzedne

- `Site` = glowna przestrzen robocza witryny.
- `CrawlJob` = snapshot witryny w czasie.
- Domyslny tryb pracy jest current-first:
  - po wejsciu do witryny user widzi stan aktywnego crawla.
- Compare jest funkcja dodatkowa:
  - siedzi pod sekcja `Zmiany`.
- Kontekst workspace pozostaje w URL:
  - `active_crawl_id`
  - `baseline_crawl_id`
- Sticky header zostaje.
- Sidebar jest glowna nawigacja systemu.
- Rozwiniete jest tylko submenu sekcji, w ktorej aktualnie jest user.

---

## 2. App shell v2

### 2.1. Uklad
- Sticky header
- Sidebar
- Main content

### 2.2. Sticky header
Header jest zawsze widoczny.

Zawartosc:
- Branding:
  - `SEO Flow`
  - w przyszlosci logo
- Logiczny tytul aktualnej sekcji
  - zawsze moze zawierac URL witryny, np.:
    - `Przeglad — example.com`
    - `Audyt — example.com`
    - `Braki wzgledem konkurencji — example.com`
- Przelacznik motywu
- Przelacznik jezyka
- Ikona ustawien systemu
- Ikona / menu uzytkownika

Header nie zawiera site switchera.
Header nie zawiera glownej nawigacji.

---

## 3. Sidebar v2

Sidebar jest glowna pionowa nawigacja.

### 3.1. Gora sidebara
- Site switcher
  - lista witryn
  - search
  - szybkie przelaczenie workspace
  - akcja `Dodaj witryne`

### 3.2. Dodawanie nowych witryn
Nowa witryna moze byc dodana w dwoch miejscach:
- `/sites`
  - lista witryn
  - formularz dodania witryny / uruchomienia pierwszego crawla
- site switcher
  - szybka akcja `Dodaj witryne`, ktora prowadzi do `/sites/new` albo otwiera modal

`/sites` jest glownym miejscem zarzadzania lista witryn.
Site switcher daje szybki skrot.

### 3.3. Sekcja aktualnej witryny
Pod site switcherem:
- nazwa witryny
- root URL
- status aktywnego crawla
- opcjonalnie:
  - data ostatniego crawla
  - status GSC

### 3.4. Menu witryny
Glowne pozycje sidebara dla wybranej witryny:
- Przeglad
- Postep
- Strony
- AI Review Editor
- Audyt
- Szanse SEO
- Linkowanie wewnetrzne
- Rekomendacje tresci
- Braki wzgledem konkurencji
- GSC
- Crawle
- Zmiany

### 3.5. Submenu sekcji
Rozwiniete jest tylko submenu aktywnej sekcji.

#### Przeglad
- Przeglad

#### Postep
- Postep

#### Strony
- Przeglad
- Rekordy

#### AI Review Editor
- Dokumenty
- Dokument
  - jeden dokument otwierany bez osobnego submenu dla issue albo wersji; workflow pozostaje na jednym ekranie

#### Audyt
- Przeglad
- Sekcje

#### Szanse SEO
- Przeglad
- Rekordy

#### Linkowanie wewnetrzne
- Przeglad
- Problemy

#### Rekomendacje tresci
- Przeglad
- Aktywne
- Wdrożone

#### Braki wzgledem konkurencji
- Przeglad
- Strategia
- Konkurenci
- Synchronizacja
- Wyniki
  - backend preferuje `reviewed`, potem `raw candidates`, a na koncu `legacy`
  - lekki operator/debug flow review runow pozostaje w tym samym module, bez osobnego dashboardu

#### GSC
- Przeglad
- Konfiguracja
- Import

#### Crawle
- Historia
- Nowy crawl

#### Zmiany
- Przeglad
- Strony
- Audyt
- Szanse SEO
- Linkowanie wewnetrzne

### 3.6. Sekcja globalna
Na dole sidebara:
- Wszystkie witryny
- Operacje
- Ustawienia systemu
- Konto

---

## 4. Routing v2

### 4.1. Global
- `/` -> redirect do `/sites`
- `/sites` -> lista witryn
- `/sites/new` -> dodanie witryny / pierwszy crawl
- `/jobs` albo docelowo `/runs` -> operacje / legacy snapshot layer
- `*` -> not found

### 4.2. Site workspace
- `/sites/:siteId` -> Przeglad
- `/sites/:siteId/progress` -> Postep

- `/sites/:siteId/pages` -> Strony / Przeglad
- `/sites/:siteId/pages/records` -> Strony / Rekordy

- `/sites/:siteId/ai-review-editor` -> redirect do Dokumentow
- `/sites/:siteId/ai-review-editor/documents` -> AI Review Editor / Dokumenty
- `/sites/:siteId/ai-review-editor/documents/:documentId` -> AI Review Editor / Dokument
  - dokument renderowany z aktywnych blokow
  - issue/rewrite actions respektuja stale/current governance
  - version history, diff preview i restore pozostaja w tym samym ekranie

- `/sites/:siteId/audit` -> Audyt / Przeglad
- `/sites/:siteId/audit/sections` -> Audyt / Sekcje

- `/sites/:siteId/opportunities` -> Szanse SEO / Przeglad
- `/sites/:siteId/opportunities/records` -> Szanse SEO / Rekordy

- `/sites/:siteId/internal-linking` -> Linkowanie wewnetrzne / Przeglad
- `/sites/:siteId/internal-linking/issues` -> Linkowanie wewnetrzne / Problemy

- `/sites/:siteId/content-recommendations` -> Rekomendacje tresci / Przeglad
- `/sites/:siteId/content-recommendations/active` -> Aktywne
- `/sites/:siteId/content-recommendations/implemented` -> Wdrożone

- `/sites/:siteId/competitive-gap` -> Braki wzgledem konkurencji / Przeglad
- `/sites/:siteId/competitive-gap/strategy` -> Strategia
- `/sites/:siteId/competitive-gap/competitors` -> Konkurenci
- `/sites/:siteId/competitive-gap/sync` -> Synchronizacja
- `/sites/:siteId/competitive-gap/results` -> Wyniki

- `/sites/:siteId/gsc` -> GSC / Przeglad
- `/sites/:siteId/gsc/settings` -> GSC / Konfiguracja
- `/sites/:siteId/gsc/import` -> GSC / Import

- `/sites/:siteId/crawls` -> Crawle / Historia
- `/sites/:siteId/crawls/new` -> Crawle / Nowy crawl

- `/sites/:siteId/changes` -> Zmiany / Przeglad
- `/sites/:siteId/changes/pages` -> Zmiany stron
- `/sites/:siteId/changes/audit` -> Zmiany audytu
- `/sites/:siteId/changes/opportunities` -> Zmiany szans SEO
- `/sites/:siteId/changes/internal-linking` -> Zmiany linkowania

### 4.3. Legacy / operacyjne
- `/jobs`
- `/jobs/:jobId`
- `/jobs/:jobId/pages`
- `/jobs/:jobId/links`
- `/jobs/:jobId/audit`
- `/jobs/:jobId/opportunities`
- `/jobs/:jobId/internal-linking`
- `/jobs/:jobId/cannibalization`
- `/jobs/:jobId/gsc`
- `/jobs/:jobId/trends`

Legacy routes zostaja jako warstwa techniczna i operacyjna.

---

## 5. Site workspace shell v2

Kazdy widok witryny korzysta ze wspolnego shellu.

### 5.1. Context bar
Pod sticky headerem:
- nazwa witryny
- root URL
- aktywny crawl
- baseline crawl, jesli ustawiony
- status GSC
- glowne CTA:
  - `Nowy crawl`

### 5.2. Snapshot context
Kontekst pozostaje w query params:
- `active_crawl_id`
- `baseline_crawl_id`

Zasady:
- aktywny crawl = glowny snapshot roboczy
- baseline = kontekst porownawczy
- baseline nie dominuje UI

---

## 6. Wzorzec akcji

Tam, gdzie ma to sens, widoki maja ten sam uklad akcji w prawym gornym rogu:
- Primary action
- `Operacje`
- `Eksport`

### 6.1. Primary action
Najwazniejsza akcja w danym widoku, np.:
- `Nowy crawl`
- `Import GSC`
- `Zapisz strategie`
- `Dodaj konkurenta`

### 6.2. Operacje
Jedno miejsce na akcje procesowe:
- odswiez
- uruchom ponownie
- synchronizuj
- reset runtime
- trigger LLM
- trigger semantic matching
- inne procesy backendowe

### 6.3. Eksport
Jedno miejsce na eksporty:
- `Eksport CSV`
- tylko tam, gdzie eksport ma sens

Zasada:
- eksport zawsze siedzi w `Eksport`
- procesy zawsze siedza w `Operacje`
- nie rozrzucac tych akcji po ekranie

---

## 7. Wzorzec filtrow

### 7.1. Quick filters
Quick filters zawsze dzialaja jako:
- klik = wlacz
- klik ponownie = wylacz
- mozna zaznaczyc dowolna liczbe naraz
- mozna odznaczyc dowolne pojedynczo
- zawsze jest `Reset`

Quick filters sa stanem UI i query stringu.

### 7.2. Advanced filters
Dodatkowe filtry siedza w jednym panelu filtrow.
Nie dublowac logiki quick filters i panelu.

### 7.3. Standard list views
Preferowany uklad:
- compact header
- summary cards
- quick filters
- panel filtrow
- tabela / lista
- details drawer lub panel szczegolow
- pagination

---

## 8. Widoki site-level

### 8.1. `/sites`
Bloki:
- compact header
- akcja `Dodaj witryne`
- formularz pierwszego crawla
- tabela witryn

### 8.2. `Przeglad`
Pytanie:
- jak jest teraz?

Bloki:
- KPI aktywnego snapshotu
- status crawla
- status GSC
- najwazniejsze problemy
- top szanse SEO
- skroty do kluczowych modulow
- ostatnie crawle

### 8.3. `Postep`
Pytanie:
- czy idziemy do przodu?

Bloki:
- trendy KPI
- co sie poprawilo
- co sie pogorszylo
- postep wdrozen
- timeline

### 8.4. `Strony`
Widoki:
- Przeglad
- Rekordy

### 8.5. `Audyt`
Widoki:
- Przeglad
- Sekcje

### 8.6. `Szanse SEO`
Widoki:
- Przeglad
- Rekordy

### 8.7. `Linkowanie wewnetrzne`
Widoki:
- Przeglad
- Problemy

### 8.8. `AI Review Editor`
Widoki:
- Dokumenty
- Dokument

Wazne bloki:
- current document renderowany z aktywnych blokow
- issue pane z governance stale/current
- rewrite preview ze stanem bezpiecznego apply
- version history + diff preview + restore

### 8.9. `Rekomendacje tresci`
Widoki:
- Przeglad
- Aktywne
- Wdrożone

### 8.10. `Braki wzgledem konkurencji`
Widoki:
- Przeglad
- Strategia
- Konkurenci
- Synchronizacja
- Wyniki

### 8.11. `GSC`
Widoki:
- Przeglad
- Konfiguracja
- Import

### 8.12. `Crawle`
Widoki:
- Historia
- Nowy crawl

### 8.13. `Zmiany`
Widoki:
- Przeglad
- Strony
- Audyt
- Szanse SEO
- Linkowanie wewnetrzne

---

## 9. Widoki z osobna konfiguracja

Na teraz osobne widoki konfiguracji maja:
- GSC
- Braki wzgledem konkurencji

Sekcje, ktore moga dostac osobna konfiguracje w przyszlosci:
- Crawle
- Rekomendacje tresci
- Zmiany

Na teraz nie ma potrzeby robic osobnej konfiguracji dla:
- Strony
- Audyt
- Szanse SEO
- Linkowanie wewnetrzne

---

## 10. Invarianty techniczne

- `Site` pozostaje glownym workspace.
- `CrawlJob` pozostaje snapshotem.
- Dane snapshotowe nie moga mieszac wielu crawl snapshotow w podstawowych tabelach.
- Compare pozostaje warstwa nad `active_crawl_id` i `baseline_crawl_id`.
- GSC config pozostaje site-level.
- GSC import pozostaje per crawl.
- Legacy `/jobs/*` pozostaje kompatybilna warstwa techniczna.

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import (
    CrawlJob,
    CrawlJobStatus,
    GscProperty,
    GscTopQuery,
    Page,
    Site,
    SiteContentGeneratorAsset,
)
from app.services import content_generator_service, content_generator_source_service
from app.services.content_generator_prompt_service import CONTENT_GENERATOR_PROMPT_VERSION


FIXED_TIME = datetime(2026, 3, 20, 12, 0, tzinfo=timezone.utc)


class FakeContentGeneratorClient:
    provider_name = "openai-test"

    def __init__(
        self,
        payload: dict[str, object],
        *,
        session=None,
        site_id: int | None = None,
    ) -> None:
        self.payload = payload
        self.session = session
        self.site_id = site_id
        self.calls: list[dict[str, object]] = []

    def is_available(self) -> bool:
        return True

    def parse_chat_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_format,
        max_completion_tokens: int,
        reasoning_effort: str | None = None,
        verbosity: str = "low",
    ):
        if self.session is not None and self.site_id is not None:
            asset = self.session.scalar(
                select(SiteContentGeneratorAsset).where(SiteContentGeneratorAsset.site_id == self.site_id)
            )
            assert asset is not None
            assert asset.status == "running"
            assert asset.source_urls_json
            assert asset.prompt_version == CONTENT_GENERATOR_PROMPT_VERSION
        self.calls.append(
            {
                "model": model,
                "system_prompt": system_prompt,
                "payload": json.loads(user_prompt),
                "max_completion_tokens": max_completion_tokens,
                "reasoning_effort": reasoning_effort,
                "verbosity": verbosity,
            }
        )
        return response_format.model_validate(self.payload)


def _make_page(crawl_job_id: int, path: str, **overrides) -> Page:
    url = f"https://example.com{path}"
    defaults = {
        "crawl_job_id": crawl_job_id,
        "url": url,
        "normalized_url": url,
        "final_url": url,
        "status_code": 200,
        "title": f"Title for {path}",
        "meta_description": f"Meta description for {path}",
        "h1": f"H1 for {path}",
        "canonical_url": url,
        "content_type": "text/html; charset=utf-8",
        "is_internal": True,
        "depth": len([segment for segment in path.split("/") if segment]),
        "schema_present": False,
        "schema_types_json": None,
        "fetched_at": FIXED_TIME,
        "created_at": FIXED_TIME,
    }
    defaults.update(overrides)
    return Page(**defaults)


def _add_gsc_query(
    session,
    *,
    gsc_property_id: int,
    crawl_job_id: int,
    page_id: int,
    path: str,
    query: str,
    clicks: int,
    impressions: int,
    position: float,
) -> None:
    url = f"https://example.com{path}"
    session.add(
        GscTopQuery(
            gsc_property_id=gsc_property_id,
            crawl_job_id=crawl_job_id,
            page_id=page_id,
            url=url,
            normalized_url=url,
            date_range_label="last_28_days",
            query=query,
            clicks=clicks,
            impressions=impressions,
            ctr=0.1,
            position=position,
            fetched_at=FIXED_TIME,
            created_at=FIXED_TIME,
        )
    )


def _seed_content_generator_site(sqlite_session_factory) -> dict[str, int]:
    with sqlite_session_factory() as session:
        site = Site(root_url="https://example.com/", domain="example.com", created_at=FIXED_TIME)
        session.add(site)
        session.flush()

        old_crawl = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=FIXED_TIME,
            started_at=FIXED_TIME,
            finished_at=FIXED_TIME,
            settings_json={"start_url": "https://example.com"},
            stats_json={},
        )
        active_crawl = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=FIXED_TIME + timedelta(days=1),
            started_at=FIXED_TIME + timedelta(days=1),
            finished_at=FIXED_TIME + timedelta(days=1),
            settings_json={"start_url": "https://example.com"},
            stats_json={},
        )
        session.add_all([old_crawl, active_crawl])
        session.flush()

        session.add_all(
            [
                _make_page(
                    old_crawl.id,
                    "/legacy-service",
                    title="Legacy service page",
                    h1="Legacy service page",
                    meta_description="Legacy service page from an older crawl.",
                    schema_types_json=["Service"],
                ),
                _make_page(
                    active_crawl.id,
                    "/",
                    title="Example home",
                    h1="Example home",
                    meta_description="SEO and content services for growing websites.",
                    schema_types_json=["Organization"],
                ),
                _make_page(
                    active_crawl.id,
                    "/kontakt",
                    title="Kontakt",
                    h1="Kontakt",
                    meta_description="Skontaktuj sie w sprawie wspolpracy SEO.",
                    schema_types_json=["ContactPage"],
                ),
                _make_page(
                    active_crawl.id,
                    "/o-nas",
                    title="O nas",
                    h1="O nas",
                    meta_description="Poznaj zespol i podejscie do strategii contentowej.",
                    schema_types_json=["AboutPage"],
                ),
                _make_page(
                    active_crawl.id,
                    "/uslugi/audyt-seo",
                    title="Audyt SEO",
                    h1="Audyt SEO",
                    meta_description="Audyty SEO dla firm, ktore chca uporzadkowac wzrost organiczny.",
                    schema_types_json=["Service"],
                    word_count=650,
                ),
                _make_page(
                    active_crawl.id,
                    "/uslugi/local-seo",
                    title="Local SEO",
                    h1="Local SEO",
                    meta_description="Wsparcie lokalnej widocznosci i stron lokalnych.",
                    schema_types_json=["Service"],
                    word_count=520,
                ),
                _make_page(
                    active_crawl.id,
                    "/kategoria/pozycjonowanie",
                    title="Pozycjonowanie stron",
                    h1="Pozycjonowanie stron",
                    meta_description="Oferta pozycjonowania stron i planowania tresci.",
                    schema_types_json=["CollectionPage"],
                    word_count=430,
                ),
                _make_page(
                    active_crawl.id,
                    "/blog/seo-poradnik",
                    title="SEO poradnik",
                    h1="SEO poradnik",
                    meta_description="Artykul blogowy o SEO.",
                    schema_types_json=["Article"],
                    word_count=900,
                ),
                _make_page(
                    active_crawl.id,
                    "/oferta/noindex",
                    title="Strona noindex",
                    h1="Strona noindex",
                    meta_description="Ta strona nie powinna trafic do selekcji.",
                    robots_meta="noindex",
                    schema_types_json=["Service"],
                ),
                _make_page(
                    active_crawl.id,
                    "/cennik.pdf",
                    title="Cennik PDF",
                    h1="Cennik PDF",
                    meta_description="Plik PDF, nie strona HTML.",
                    content_type="application/pdf",
                ),
            ]
        )
        session.flush()

        gsc_property = GscProperty(
            site_id=site.id,
            property_uri="sc-domain:example.com",
            permission_level="siteOwner",
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        session.add(gsc_property)
        session.flush()

        pages = session.scalars(select(Page).where(Page.crawl_job_id == active_crawl.id).order_by(Page.id.asc())).all()
        page_by_path = {
            page.normalized_url.removeprefix("https://example.com"): page
            for page in pages
        }
        _add_gsc_query(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=active_crawl.id,
            page_id=page_by_path["/uslugi/audyt-seo"].id,
            path="/uslugi/audyt-seo",
            query="audyt seo",
            clicks=18,
            impressions=220,
            position=6.5,
        )
        _add_gsc_query(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=active_crawl.id,
            page_id=page_by_path["/uslugi/local-seo"].id,
            path="/uslugi/local-seo",
            query="local seo",
            clicks=12,
            impressions=180,
            position=7.2,
        )
        _add_gsc_query(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=active_crawl.id,
            page_id=page_by_path["/kategoria/pozycjonowanie"].id,
            path="/kategoria/pozycjonowanie",
            query="pozycjonowanie stron",
            clicks=10,
            impressions=150,
            position=8.4,
        )
        _add_gsc_query(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=active_crawl.id,
            page_id=page_by_path["/o-nas"].id,
            path="/o-nas",
            query="o nas",
            clicks=3,
            impressions=40,
            position=12.0,
        )
        session.commit()
        return {
            "site_id": site.id,
            "old_crawl_id": old_crawl.id,
            "active_crawl_id": active_crawl.id,
        }


def _valid_surfer_instructions() -> str:
    return (
        "Marka powinna byc opisywana jako praktyczny partner SEO i contentowy dla firm, ktore chca uporzadkowac "
        "widocznosc organiczna. Pisz do zespolow marketingu i wlascicieli stron, ktorzy szukaja konkretow, a nie "
        "ogolnikow. Utrzymuj rzeczowy, spokojny ton, bez napompowanych obietnic i bez deklarowania przewag, ktorych "
        "nie ma w zrodlach. Prezentuj oferte przez realne obszary widoczne na stronach uslugowych, pokazuj zakres "
        "prac i problemy, ktore rozwiazuje dana usluga. CTA powinny byc lekkie: zapraszaj do kontaktu lub rozmowy "
        "o zakresie wspolpracy tylko wtedy, gdy wynika to z kontekstu. Linkowanie wewnetrzne kieruj do najblizszych "
        "stron uslugowych, kategorii albo kontaktu, bez wciskania przypadkowych linkow. Twardo zabronione jest "
        "dopisywanie certyfikatow, lokalizacji, lat doswiadczenia, procesow, skladu zespolu, wynikow i obietnic, "
        "jesli nie pojawiaja sie w zrodlach. Gdy dane sa skape, zaznaczaj, ze nalezy opierac sie tylko na jawnie "
        "potwierdzonych informacjach z aktualnego snapshotu witryny."
    )


def _valid_details_to_include() -> str:
    return (
        "Uwzglednij, ze marka komunikuje SEO, audyt SEO, local SEO i pozycjonowanie stron. Pisz do firm, ktore "
        "potrzebuja praktycznego wsparcia wzrostu organicznego. Ton ma byc rzeczowy, konkretny i ostrozny. "
        "Eksponuj tylko te obszary oferty, ktore wynikaja z homepage, stron uslugowych, kategorii i kontaktu. "
        "Nie dopisuj przewag ani claimow bez potwierdzenia w zrodlach."
    )


def _valid_hook_brief() -> str:
    return (
        "Otwieraj tekst od konkretnego napiecia zwiazanego z widocznoscia organiczna albo uporzadkowaniem dzialan SEO, "
        "nawiazujac do realnych uslug marki. Buduj ciekawosc przez problem, decyzje lub koszt zaniechania, a nie przez "
        "szablonowe zapowiedzi tresci. Bez obietnic i bez wymyslonych claimow."
    )


def test_select_site_content_generator_sources_uses_active_snapshot_and_prefers_core_pages(sqlite_session_factory) -> None:
    ids = _seed_content_generator_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        selection = content_generator_source_service.select_site_content_generator_sources(
            session,
            site_id=ids["site_id"],
        )

    assert selection.basis_crawl_job_id == ids["active_crawl_id"]
    assert len(selection.source_pages) >= 5
    assert selection.source_urls[:3] == [
        "https://example.com/",
        "https://example.com/kontakt",
        "https://example.com/o-nas",
    ]
    assert "https://example.com/legacy-service" not in selection.source_urls
    assert "https://example.com/oferta/noindex" not in selection.source_urls
    assert "https://example.com/cennik.pdf" not in selection.source_urls
    commercial_urls = {
        "https://example.com/uslugi/audyt-seo",
        "https://example.com/uslugi/local-seo",
        "https://example.com/kategoria/pozycjonowanie",
    }
    assert len(commercial_urls.intersection(selection.source_urls)) >= 2
    service_page = next(page for page in selection.source_pages if page.url == "https://example.com/uslugi/audyt-seo")
    assert service_page.top_queries == ["audyt seo"]


def test_generate_site_content_assets_marks_running_then_persists_ready_asset(sqlite_session_factory) -> None:
    ids = _seed_content_generator_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        fake_client = FakeContentGeneratorClient(
            {
                "surfer_custom_instructions": _valid_surfer_instructions(),
                "seowriting_details_to_include": _valid_details_to_include(),
                "introductory_hook_brief": _valid_hook_brief(),
            },
            session=session,
            site_id=ids["site_id"],
        )

        payload = content_generator_service.generate_site_content_assets(
            session,
            site_id=ids["site_id"],
            output_language="pl",
            client=fake_client,
        )

        asset = session.scalar(
            select(SiteContentGeneratorAsset).where(SiteContentGeneratorAsset.site_id == ids["site_id"])
        )

    assert payload["status"] == "ready"
    assert payload["basis_crawl_job_id"] == ids["active_crawl_id"]
    assert payload["generated_at"] is not None
    assert payload["prompt_version"] == CONTENT_GENERATOR_PROMPT_VERSION
    assert payload["llm_provider"] == "openai-test"
    assert payload["llm_model"] == get_settings().openai_model_content_generator
    assert payload["source_urls_json"]
    assert payload["source_pages_hash"]
    assert asset is not None
    assert asset.status == "ready"
    assert asset.surfer_custom_instructions == _valid_surfer_instructions()
    assert asset.seowriting_details_to_include == _valid_details_to_include()
    assert asset.introductory_hook_brief == _valid_hook_brief()
    assert "Polish" in str(fake_client.calls[0]["system_prompt"])
    assert fake_client.calls[0]["payload"]["context"]["site"]["basis_crawl_job_id"] == ids["active_crawl_id"]
    assert fake_client.calls[0]["payload"]["context"]["source_selection"]["source_urls"] == payload["source_urls_json"]


def test_generate_site_content_assets_marks_failed_when_hook_is_generic(sqlite_session_factory) -> None:
    ids = _seed_content_generator_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        session.add(
            SiteContentGeneratorAsset(
                site_id=ids["site_id"],
                basis_crawl_job_id=ids["old_crawl_id"],
                status="ready",
                surfer_custom_instructions="Old instructions",
                seowriting_details_to_include="Old details",
                introductory_hook_brief="Old hook",
                source_urls_json=["https://example.com/legacy-service"],
                source_pages_hash="old-hash",
                prompt_version="old-version",
                llm_provider="openai",
                llm_model="old-model",
                generated_at=FIXED_TIME,
                created_at=FIXED_TIME,
                updated_at=FIXED_TIME,
            )
        )
        session.commit()

    with sqlite_session_factory() as session:
        fake_client = FakeContentGeneratorClient(
            {
                "surfer_custom_instructions": _valid_surfer_instructions(),
                "seowriting_details_to_include": _valid_details_to_include(),
                "introductory_hook_brief": "W tym artykule omowimy, jak podejsc do SEO i co warto wiedziec na start.",
            },
            session=session,
            site_id=ids["site_id"],
        )

        with pytest.raises(content_generator_service.ContentGeneratorServiceError) as exc_info:
            content_generator_service.generate_site_content_assets(
                session,
                site_id=ids["site_id"],
                output_language="pl",
                client=fake_client,
            )

        asset = session.scalar(
            select(SiteContentGeneratorAsset).where(SiteContentGeneratorAsset.site_id == ids["site_id"])
        )

    assert exc_info.value.code == "generic_hook_brief"
    assert asset is not None
    assert asset.status == "failed"
    assert asset.basis_crawl_job_id == ids["active_crawl_id"]
    assert asset.generated_at is None
    assert asset.last_error_code == "generic_hook_brief"
    assert asset.surfer_custom_instructions is None
    assert asset.seowriting_details_to_include is None
    assert asset.introductory_hook_brief is None
    assert asset.source_urls_json
    assert "legacy-service" not in json.dumps(asset.source_urls_json)

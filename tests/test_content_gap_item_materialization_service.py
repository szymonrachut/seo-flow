from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import SiteContentGapItem, SiteContentGapReviewRun
from app.services import content_gap_item_materialization_service, content_gap_review_run_service
from tests.test_content_gap_review_run_service import _add_candidate, _seed_site_with_two_crawls


def test_materialize_review_items_persists_keep_remove_merge_and_rewrite(sqlite_session_factory) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    with sqlite_session_factory() as session:
        candidate_a = _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-a",
            candidate_input_hash="hash-a",
            topic_key="local-seo",
            topic_label="Local SEO",
        )
        candidate_b = _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-b",
            candidate_input_hash="hash-b",
            topic_key="seo-audit",
            topic_label="SEO Audit",
        )
        candidate_c = _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-c",
            candidate_input_hash="hash-c",
            topic_key="technical-seo",
            topic_label="Technical SEO",
        )
        candidate_d = _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-d",
            candidate_input_hash="hash-d",
            topic_key="content-gap",
            topic_label="Content Gap Review",
        )
        queued_run = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
        )
        session.commit()

    decisions = [
        content_gap_item_materialization_service.SanitizedContentGapDecision(
            source_candidate_id=candidate_a.id,
            decision_action="keep",
            decision_reason_text="Strong fit for the site.",
            fit_score=91.0,
            confidence=0.88,
            reviewed_phrase="Local SEO",
            reviewed_topic_label="Local SEO",
            reviewed_normalized_topic_key="local-seo",
            reviewed_gap_type="NEW_TOPIC",
            sort_score=91.0,
        ),
        content_gap_item_materialization_service.SanitizedContentGapDecision(
            source_candidate_id=candidate_b.id,
            decision_action="remove",
            decision_reason_text="Out of scope for the site.",
            fit_score=12.0,
            confidence=0.82,
            remove_reason_code="site_mismatch",
            remove_reason_text="This topic does not fit the business offer.",
        ),
        content_gap_item_materialization_service.SanitizedContentGapDecision(
            source_candidate_id=candidate_c.id,
            decision_action="merge",
            decision_reason_text="Merge into the Local SEO parent topic.",
            fit_score=67.0,
            confidence=0.79,
            review_group_key="merge:local-seo",
            group_primary=False,
            merge_target_candidate_key="merge:local-seo",
            merge_target_phrase="Local SEO",
        ),
        content_gap_item_materialization_service.SanitizedContentGapDecision(
            source_candidate_id=candidate_d.id,
            decision_action="rewrite",
            decision_reason_text="The topic fits better after narrowing the phrasing.",
            fit_score=78.0,
            confidence=0.83,
            reviewed_phrase="Content gap analysis process",
            reviewed_topic_label="Content Gap Analysis Process",
            reviewed_normalized_topic_key="content-gap-analysis-process",
            reviewed_gap_type="EXPAND_TOPIC",
            rewrite_reason_text="Narrowed to a more specific phrase.",
            own_site_alignment_json={"matched_urls": ["https://example.com/local-seo"]},
            gsc_support_json={"queries": ["content gap"]},
            competitor_evidence_json={"competitor_count": 2},
        ),
    ]

    with sqlite_session_factory() as session:
        summary = content_gap_item_materialization_service.materialize_review_items(
            session,
            site_id=ids["site_id"],
            review_run_id=queued_run["id"],
            decisions=decisions,
        )
        session.commit()

        items = session.scalars(
            select(SiteContentGapItem)
            .where(SiteContentGapItem.review_run_id == queued_run["id"])
            .order_by(SiteContentGapItem.source_candidate_id.asc())
        ).all()
        run_row = session.scalar(
            select(SiteContentGapReviewRun).where(SiteContentGapReviewRun.id == queued_run["id"])
        )

    assert summary.created_count == 4
    assert summary.visible_count == 2
    assert summary.hidden_removed_count == 1
    assert summary.hidden_merged_child_count == 1
    assert all(item.basis_crawl_job_id == ids["crawl_a_id"] for item in items)
    assert len(items) == 4
    by_candidate_id = {item.source_candidate_id: item for item in items}
    assert by_candidate_id[candidate_a.id].decision_action == "keep"
    assert by_candidate_id[candidate_a.id].display_state == "visible"
    assert by_candidate_id[candidate_b.id].decision_action == "remove"
    assert by_candidate_id[candidate_b.id].display_state == "hidden_removed"
    assert by_candidate_id[candidate_c.id].decision_action == "merge"
    assert by_candidate_id[candidate_c.id].display_state == "hidden_merged_child"
    assert by_candidate_id[candidate_c.id].group_primary is False
    assert by_candidate_id[candidate_d.id].decision_action == "rewrite"
    assert by_candidate_id[candidate_d.id].display_state == "visible"
    assert run_row is not None
    assert run_row.basis_crawl_job_id == ids["crawl_a_id"]


def test_materialize_review_items_supersedes_older_active_items_for_same_snapshot(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    monkeypatch.setattr(content_gap_review_run_service, "SessionLocal", sqlite_session_factory)
    with sqlite_session_factory() as session:
        candidate_a = _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-a",
            candidate_input_hash="hash-a",
            topic_key="local-seo",
            topic_label="Local SEO",
        )
        candidate_b = _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-b",
            candidate_input_hash="hash-b",
            topic_key="seo-audit",
            topic_label="SEO Audit",
        )
        run_one = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
        )
        session.commit()

    with sqlite_session_factory() as session:
        content_gap_item_materialization_service.materialize_review_items(
            session,
            site_id=ids["site_id"],
            review_run_id=run_one["id"],
            decisions=[
                content_gap_item_materialization_service.SanitizedContentGapDecision(
                    source_candidate_id=candidate_a.id,
                    decision_action="keep",
                    decision_reason_text="Keep.",
                    fit_score=88.0,
                    confidence=0.8,
                ),
                content_gap_item_materialization_service.SanitizedContentGapDecision(
                    source_candidate_id=candidate_b.id,
                    decision_action="keep",
                    decision_reason_text="Keep.",
                    fit_score=82.0,
                    confidence=0.78,
                ),
            ],
        )
        session.commit()
        content_gap_review_run_service.complete_review_run(
            ids["site_id"],
            run_one["run_id"],
        )

        run_two = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
        )
        session.commit()

    with sqlite_session_factory() as session:
        summary = content_gap_item_materialization_service.materialize_review_items(
            session,
            site_id=ids["site_id"],
            review_run_id=run_two["id"],
            decisions=[
                content_gap_item_materialization_service.SanitizedContentGapDecision(
                    source_candidate_id=candidate_a.id,
                    decision_action="rewrite",
                    decision_reason_text="Rewrite.",
                    fit_score=90.0,
                    confidence=0.84,
                    reviewed_phrase="Local SEO services",
                ),
                content_gap_item_materialization_service.SanitizedContentGapDecision(
                    source_candidate_id=candidate_b.id,
                    decision_action="remove",
                    decision_reason_text="Remove.",
                    fit_score=20.0,
                    confidence=0.7,
                    remove_reason_text="Too weak for the site.",
                ),
            ],
        )
        session.commit()

        items = session.scalars(
            select(SiteContentGapItem)
            .where(SiteContentGapItem.site_id == ids["site_id"])
            .order_by(SiteContentGapItem.id.asc())
        ).all()

    assert summary.superseded_count == 2
    active_items = [item for item in items if item.item_status == "active"]
    superseded_items = [item for item in items if item.item_status == "superseded"]
    assert len(active_items) == 2
    assert len(superseded_items) == 2
    assert all(item.review_run_id == run_two["id"] for item in active_items)


def test_materialize_review_items_rejects_inconsistent_decisions_without_partial_write(sqlite_session_factory) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    with sqlite_session_factory() as session:
        candidate_a = _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-a",
            candidate_input_hash="hash-a",
            topic_key="local-seo",
            topic_label="Local SEO",
        )
        _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-b",
            candidate_input_hash="hash-b",
            topic_key="seo-audit",
            topic_label="SEO Audit",
        )
        run = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
        )
        session.commit()

    with sqlite_session_factory() as session:
        with pytest.raises(
            content_gap_item_materialization_service.ContentGapItemMaterializationServiceError
        ) as exc_info:
            content_gap_item_materialization_service.materialize_review_items(
                session,
                site_id=ids["site_id"],
                review_run_id=run["id"],
                decisions=[
                    content_gap_item_materialization_service.SanitizedContentGapDecision(
                        source_candidate_id=candidate_a.id,
                        decision_action="keep",
                        decision_reason_text="Only one decision for two-candidate run.",
                        fit_score=70.0,
                        confidence=0.7,
                    )
                ],
            )
        session.rollback()
        items = session.scalars(
            select(SiteContentGapItem).where(SiteContentGapItem.site_id == ids["site_id"])
        ).all()

    assert exc_info.value.code == "decision_scope_mismatch"
    assert items == []


def test_materialize_review_items_rejects_multiple_group_primaries(sqlite_session_factory) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    with sqlite_session_factory() as session:
        candidate_a = _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-a",
            candidate_input_hash="hash-a",
            topic_key="local-seo",
            topic_label="Local SEO",
        )
        candidate_b = _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-b",
            candidate_input_hash="hash-b",
            topic_key="seo-audit",
            topic_label="SEO Audit",
        )
        run = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
        )
        session.commit()

    with sqlite_session_factory() as session:
        with pytest.raises(
            content_gap_item_materialization_service.ContentGapItemMaterializationServiceError
        ) as exc_info:
            content_gap_item_materialization_service.materialize_review_items(
                session,
                site_id=ids["site_id"],
                review_run_id=run["id"],
                decisions=[
                    content_gap_item_materialization_service.SanitizedContentGapDecision(
                        source_candidate_id=candidate_a.id,
                        decision_action="merge",
                        decision_reason_text="Merge.",
                        fit_score=75.0,
                        confidence=0.8,
                        review_group_key="merge:shared",
                        group_primary=True,
                    ),
                    content_gap_item_materialization_service.SanitizedContentGapDecision(
                        source_candidate_id=candidate_b.id,
                        decision_action="merge",
                        decision_reason_text="Merge.",
                        fit_score=74.0,
                        confidence=0.79,
                        review_group_key="merge:shared",
                        group_primary=True,
                    ),
                ],
            )
        session.rollback()

    assert exc_info.value.code == "multiple_group_primaries"

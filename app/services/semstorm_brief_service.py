from __future__ import annotations

from datetime import datetime, timedelta
import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.text_processing import dedupe_preserve_order, normalize_ascii, normalize_text_for_hash, tokenize_topic_text
from app.db.models import Site, SiteSemstormBriefItem, SiteSemstormPlanItem, utcnow
from app.services import semstorm_coverage_service


SemstormBriefStateStatus = Literal["draft", "ready", "in_execution", "completed", "archived"]
SemstormBriefType = Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"]
SemstormBriefSearchIntent = Literal["informational", "commercial", "transactional", "navigational", "mixed"]
SemstormBriefImplementationStatus = Literal["too_early", "implemented", "evaluated", "archived"]
SemstormBriefOutcomeStatus = Literal["too_early", "no_signal", "weak_signal", "positive_signal"]

_BRIEF_STATE_VALUES = {"draft", "ready", "in_execution", "completed", "archived"}
_BRIEF_TYPE_VALUES = {"new_page", "expand_existing", "refresh_existing", "cluster_support"}
_SEARCH_INTENT_VALUES = {"informational", "commercial", "transactional", "navigational", "mixed"}
_IMPLEMENTATION_STATUS_VALUES = {"too_early", "implemented", "evaluated", "archived"}
_OUTCOME_STATUS_VALUES = {"too_early", "no_signal", "weak_signal", "positive_signal"}
_BRIEF_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"ready", "archived"},
    "ready": {"in_execution", "archived"},
    "in_execution": {"ready", "completed", "archived"},
    "completed": {"archived"},
    "archived": set(),
}
_INFORMATIONAL_TOKENS = {
    "guide",
    "checklist",
    "template",
    "tips",
    "examples",
    "example",
    "how",
    "what",
    "why",
}
_TRANSACTIONAL_TOKENS = {"buy", "price", "pricing", "cost", "quote", "hire", "package", "packages"}
_COMMERCIAL_TOKENS = {"service", "services", "agency", "consulting", "consultant", "software", "tool", "tools"}
_NAVIGATIONAL_TOKENS = {"login", "contact", "about", "support", "docs", "documentation"}
_TITLE_UPPERCASE_TOKENS = {"seo", "gsc", "faq", "url", "urls", "cpc", "ai", "ui"}
_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
_OUTCOME_WINDOW_DEFAULT_DAYS = 30
_OUTCOME_WINDOW_MAX_DAYS = 365


class SemstormBriefServiceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "semstorm_brief_error",
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def create_semstorm_brief_items(
    session: Session,
    site_id: int,
    *,
    plan_item_ids: Sequence[int],
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    requested_ids = _normalize_plan_item_ids(plan_item_ids)
    if not requested_ids:
        raise SemstormBriefServiceError(
            "At least one plan item id is required.",
            code="invalid_plan_ids",
            status_code=400,
        )

    plan_items = list(
        session.scalars(
            select(SiteSemstormPlanItem)
            .where(SiteSemstormPlanItem.id.in_(requested_ids))
            .options(selectinload(SiteSemstormPlanItem.promoted_item))
            .order_by(SiteSemstormPlanItem.id.asc())
        )
    )
    plan_by_id = {int(item.id): item for item in plan_items}
    existing_brief_by_plan_id = load_brief_items_by_plan_ids(session, site_id, requested_ids)
    coverage_context = semstorm_coverage_service.build_site_coverage_context(session, site_id)

    created_items: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for plan_item_id in requested_ids:
        plan_item = plan_by_id.get(plan_item_id)
        if plan_item is None:
            skipped.append(
                {
                    "plan_item_id": plan_item_id,
                    "brief_title": None,
                    "reason": "plan_not_found",
                }
            )
            continue
        if int(plan_item.site_id) != site_id:
            skipped.append(
                {
                    "plan_item_id": plan_item_id,
                    "brief_title": None,
                    "reason": "wrong_site",
                }
            )
            continue
        if existing_brief_by_plan_id.get(plan_item_id) is not None:
            skipped.append(
                {
                    "plan_item_id": plan_item_id,
                    "brief_title": _default_brief_title(
                        _resolve_primary_keyword(plan_item),
                        _normalize_brief_type(plan_item.target_page_type),
                    ),
                    "reason": "already_exists",
                }
            )
            continue

        now = utcnow()
        scaffold = _build_brief_scaffold(
            session,
            site_id=site_id,
            plan_item=plan_item,
            coverage_context=coverage_context,
        )
        brief_item = SiteSemstormBriefItem(
            site_id=site_id,
            plan_item_id=plan_item.id,
            state_status="draft",
            brief_title=scaffold["brief_title"],
            brief_type=scaffold["brief_type"],
            primary_keyword=scaffold["primary_keyword"],
            secondary_keywords_json=scaffold["secondary_keywords"],
            search_intent=scaffold["search_intent"],
            target_url_existing=scaffold["target_url_existing"],
            proposed_url_slug=scaffold["proposed_url_slug"],
            recommended_page_title=scaffold["recommended_page_title"],
            recommended_h1=scaffold["recommended_h1"],
            content_goal=scaffold["content_goal"],
            angle_summary=scaffold["angle_summary"],
            sections_json=scaffold["sections"],
            internal_link_targets_json=scaffold["internal_link_targets"],
            source_notes_json=scaffold["source_notes"],
            created_at=now,
            updated_at=now,
        )
        session.add(brief_item)
        session.flush()
        session.refresh(brief_item)
        created_items.append(serialize_brief_item(brief_item))
        existing_brief_by_plan_id[plan_item_id] = brief_item

    return {
        "site_id": site_id,
        "requested_count": len(requested_ids),
        "created_count": len(created_items),
        "updated_count": 0,
        "skipped_count": len(skipped),
        "items": created_items,
        "skipped": skipped,
    }


def list_semstorm_brief_items(
    session: Session,
    site_id: int,
    *,
    state_status: SemstormBriefStateStatus | None = None,
    brief_type: SemstormBriefType | None = None,
    search_intent: SemstormBriefSearchIntent | None = None,
    search: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    items = _load_brief_items(session, site_id)
    filtered = _apply_brief_filters(
        items,
        state_status=state_status,
        brief_type=brief_type,
        search_intent=search_intent,
        search=search,
    )
    normalized_limit = max(1, min(int(limit or 1), 500))
    return {
        "site_id": site_id,
        "summary": {
            "total_count": len(filtered),
            "state_counts": _build_brief_state_counts(filtered),
            "brief_type_counts": _build_brief_type_counts(filtered),
            "intent_counts": _build_intent_counts(filtered),
        },
        "items": [serialize_brief_list_item(item) for item in filtered[:normalized_limit]],
    }


def list_semstorm_execution_items(
    session: Session,
    site_id: int,
    *,
    execution_status: SemstormBriefStateStatus | None = None,
    assignee: str | None = None,
    brief_type: SemstormBriefType | None = None,
    search: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    items = _load_brief_items(session, site_id)
    filtered = _apply_execution_filters(
        items,
        execution_status=execution_status,
        assignee=assignee,
        brief_type=brief_type,
        search=search,
    )
    normalized_limit = max(1, min(int(limit or 1), 500))
    execution_status_counts = _build_brief_state_counts(filtered)
    return {
        "site_id": site_id,
        "summary": {
            "total_count": len(filtered),
            "execution_status_counts": execution_status_counts,
            "ready_count": execution_status_counts["ready"],
            "in_execution_count": execution_status_counts["in_execution"],
            "completed_count": execution_status_counts["completed"],
        },
        "items": [serialize_execution_list_item(item) for item in filtered[:normalized_limit]],
    }


def list_semstorm_implemented_items(
    session: Session,
    site_id: int,
    *,
    implementation_status: SemstormBriefImplementationStatus | None = None,
    outcome_status: SemstormBriefOutcomeStatus | None = None,
    brief_type: SemstormBriefType | None = None,
    search: str | None = None,
    window_days: int = _OUTCOME_WINDOW_DEFAULT_DAYS,
    limit: int = 100,
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    normalized_window_days = _normalize_window_days(window_days)
    coverage_context = semstorm_coverage_service.build_site_coverage_context(session, site_id)
    items = [item for item in _load_brief_items(session, site_id) if _has_implementation_state(item)]
    evaluated_items = [
        _build_implemented_item_payload(
            item,
            coverage_context=coverage_context,
            window_days=normalized_window_days,
        )
        for item in items
    ]
    filtered = _apply_implemented_filters(
        evaluated_items,
        implementation_status=implementation_status,
        outcome_status=outcome_status,
        brief_type=brief_type,
        search=search,
    )
    normalized_limit = max(1, min(int(limit or 1), 500))
    session.flush()
    implementation_status_counts = _build_implemented_status_counts(filtered)
    outcome_status_counts = _build_outcome_status_counts(filtered)
    return {
        "site_id": site_id,
        "active_crawl_id": coverage_context.active_crawl_id,
        "window_days": normalized_window_days,
        "summary": {
            "total_count": len(filtered),
            "implementation_status_counts": implementation_status_counts,
            "outcome_status_counts": outcome_status_counts,
            "too_early_count": outcome_status_counts["too_early"],
            "positive_signal_count": outcome_status_counts["positive_signal"],
        },
        "items": filtered[:normalized_limit],
    }


def get_semstorm_brief_item(session: Session, site_id: int, brief_id: int) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    brief_item = _get_brief_item_or_raise(session, site_id, brief_id)
    return serialize_brief_item(brief_item)


def update_semstorm_brief_item_status(
    session: Session,
    site_id: int,
    brief_id: int,
    *,
    state_status: SemstormBriefStateStatus,
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    brief_item = _get_brief_item_or_raise(session, site_id, brief_id)
    _apply_brief_execution_transition(brief_item, state_status)
    session.flush()
    session.refresh(brief_item)
    return serialize_brief_item(brief_item)


def update_semstorm_brief_execution_status(
    session: Session,
    site_id: int,
    brief_id: int,
    *,
    execution_status: SemstormBriefStateStatus,
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    brief_item = _get_brief_item_or_raise(session, site_id, brief_id)
    _apply_brief_execution_transition(brief_item, execution_status)
    session.flush()
    session.refresh(brief_item)
    return serialize_brief_item(brief_item)


def update_semstorm_brief_implementation_status(
    session: Session,
    site_id: int,
    brief_id: int,
    *,
    implementation_status: Literal["implemented", "archived"],
    evaluation_note: str | None = None,
    implementation_url_override: str | None = None,
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    brief_item = _get_brief_item_or_raise(session, site_id, brief_id)
    normalized_status = _normalize_implementation_action_status(implementation_status)
    current_status = _normalize_existing_implementation_status(brief_item.implementation_status)
    if normalized_status == "implemented":
        if str(brief_item.state_status or "draft") != "completed":
            raise SemstormBriefServiceError(
                "Only completed Semstorm briefs can be marked as implemented.",
                code="invalid_implementation_transition",
                status_code=409,
            )
        now = utcnow()
        if current_status not in {"implemented", "too_early"} or brief_item.implemented_at is None:
            brief_item.implemented_at = now
        brief_item.implementation_status = "implemented"
        brief_item.last_outcome_checked_at = None
    else:
        if current_status is None and str(brief_item.state_status or "draft") != "completed":
            raise SemstormBriefServiceError(
                "Only completed or already implemented Semstorm briefs can be archived.",
                code="invalid_implementation_transition",
                status_code=409,
            )
        brief_item.implementation_status = "archived"
    if evaluation_note is not None:
        brief_item.evaluation_note = _normalize_optional_text(evaluation_note)
    if implementation_url_override is not None:
        brief_item.implementation_url_override = _normalize_optional_text(
            implementation_url_override,
            max_length=2048,
        )
    brief_item.updated_at = utcnow()
    session.flush()
    session.refresh(brief_item)
    return serialize_brief_item(brief_item)


def update_semstorm_brief_execution(
    session: Session,
    site_id: int,
    brief_id: int,
    *,
    updates: Mapping[str, Any],
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    brief_item = _get_brief_item_or_raise(session, site_id, brief_id)
    if "assignee" in updates:
        brief_item.assignee = _normalize_optional_text(updates.get("assignee"), max_length=255)
    if "execution_note" in updates:
        brief_item.execution_note = _normalize_optional_text(updates.get("execution_note"))
    brief_item.updated_at = utcnow()
    session.flush()
    session.refresh(brief_item)
    return serialize_brief_item(brief_item)


def update_semstorm_brief_item(
    session: Session,
    site_id: int,
    brief_id: int,
    *,
    updates: Mapping[str, Any],
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    brief_item = _get_brief_item_or_raise(session, site_id, brief_id)
    if "state_status" in updates and updates["state_status"] is not None:
        _apply_brief_execution_transition(brief_item, updates["state_status"])
    if "brief_title" in updates:
        brief_item.brief_title = _normalize_optional_text(updates.get("brief_title"))
    if "brief_type" in updates and updates["brief_type"] is not None:
        brief_item.brief_type = _normalize_brief_type(updates["brief_type"])
    if "primary_keyword" in updates:
        brief_item.primary_keyword = _normalize_required_text(
            updates.get("primary_keyword"),
            field_name="primary_keyword",
            max_length=512,
        )
    if "secondary_keywords" in updates:
        brief_item.secondary_keywords_json = _normalize_string_list(
            updates.get("secondary_keywords"),
            field_name="secondary_keywords",
        )
    if "search_intent" in updates and updates["search_intent"] is not None:
        brief_item.search_intent = _normalize_search_intent(updates["search_intent"])
    if "target_url_existing" in updates:
        brief_item.target_url_existing = _normalize_optional_text(updates.get("target_url_existing"), max_length=2048)
    if "proposed_url_slug" in updates:
        brief_item.proposed_url_slug = _normalize_optional_text(updates.get("proposed_url_slug"), max_length=512)
    if "recommended_page_title" in updates:
        brief_item.recommended_page_title = _normalize_optional_text(updates.get("recommended_page_title"))
    if "recommended_h1" in updates:
        brief_item.recommended_h1 = _normalize_optional_text(updates.get("recommended_h1"))
    if "content_goal" in updates:
        brief_item.content_goal = _normalize_optional_text(updates.get("content_goal"))
    if "angle_summary" in updates:
        brief_item.angle_summary = _normalize_optional_text(updates.get("angle_summary"))
    if "sections" in updates:
        brief_item.sections_json = _normalize_string_list(updates.get("sections"), field_name="sections")
    if "internal_link_targets" in updates:
        brief_item.internal_link_targets_json = _normalize_string_list(
            updates.get("internal_link_targets"),
            field_name="internal_link_targets",
            max_length=2048,
        )
    if "source_notes" in updates:
        brief_item.source_notes_json = _normalize_string_list(updates.get("source_notes"), field_name="source_notes")
    if "assignee" in updates:
        brief_item.assignee = _normalize_optional_text(updates.get("assignee"), max_length=255)
    if "execution_note" in updates:
        brief_item.execution_note = _normalize_optional_text(updates.get("execution_note"))

    brief_item.updated_at = utcnow()
    session.flush()
    session.refresh(brief_item)
    return serialize_brief_item(brief_item)


def load_brief_items_by_plan_ids(
    session: Session,
    site_id: int,
    plan_item_ids: Sequence[int],
) -> dict[int, SiteSemstormBriefItem]:
    normalized_ids = _normalize_plan_item_ids(plan_item_ids)
    if not normalized_ids:
        return {}
    rows = list(
        session.scalars(
            select(SiteSemstormBriefItem).where(
                SiteSemstormBriefItem.site_id == site_id,
                SiteSemstormBriefItem.plan_item_id.in_(normalized_ids),
            )
        )
    )
    return {int(row.plan_item_id): row for row in rows}


def serialize_brief_list_item(brief_item: SiteSemstormBriefItem) -> dict[str, Any]:
    source_context = _serialize_brief_source_context(brief_item)
    return {
        "id": brief_item.id,
        "site_id": brief_item.site_id,
        "plan_item_id": brief_item.plan_item_id,
        "brief_title": brief_item.brief_title,
        "primary_keyword": brief_item.primary_keyword,
        "brief_type": brief_item.brief_type,
        "search_intent": brief_item.search_intent,
        "state_status": brief_item.state_status,
        "execution_status": brief_item.state_status,
        "assignee": brief_item.assignee,
        "execution_note": brief_item.execution_note,
        "ready_at": brief_item.ready_at,
        "started_at": brief_item.started_at,
        "completed_at": brief_item.completed_at,
        "archived_at": brief_item.archived_at,
        "implementation_status": _serialize_brief_implementation_status(brief_item),
        "implemented_at": brief_item.implemented_at,
        "last_outcome_checked_at": brief_item.last_outcome_checked_at,
        "recommended_page_title": brief_item.recommended_page_title,
        "proposed_url_slug": brief_item.proposed_url_slug,
        **source_context,
        "created_at": brief_item.created_at,
        "updated_at": brief_item.updated_at,
    }


def serialize_brief_item(brief_item: SiteSemstormBriefItem) -> dict[str, Any]:
    return {
        **serialize_brief_list_item(brief_item),
        "secondary_keywords": list(brief_item.secondary_keywords_json or []),
        "target_url_existing": brief_item.target_url_existing,
        "implementation_url_override": brief_item.implementation_url_override,
        "evaluation_note": brief_item.evaluation_note,
        "recommended_h1": brief_item.recommended_h1,
        "content_goal": brief_item.content_goal,
        "angle_summary": brief_item.angle_summary,
        "sections": list(brief_item.sections_json or []),
        "internal_link_targets": list(brief_item.internal_link_targets_json or []),
        "source_notes": list(brief_item.source_notes_json or []),
    }


def serialize_execution_list_item(brief_item: SiteSemstormBriefItem) -> dict[str, Any]:
    source_context = _serialize_brief_source_context(brief_item)
    return {
        "brief_id": brief_item.id,
        "plan_item_id": brief_item.plan_item_id,
        "brief_title": brief_item.brief_title,
        "primary_keyword": brief_item.primary_keyword,
        "brief_type": brief_item.brief_type,
        "search_intent": brief_item.search_intent,
        "execution_status": brief_item.state_status,
        "assignee": brief_item.assignee,
        "execution_note": brief_item.execution_note,
        "implementation_status": _serialize_brief_implementation_status(brief_item),
        "implemented_at": brief_item.implemented_at,
        "recommended_page_title": brief_item.recommended_page_title,
        "proposed_url_slug": brief_item.proposed_url_slug,
        "ready_at": brief_item.ready_at,
        "started_at": brief_item.started_at,
        "completed_at": brief_item.completed_at,
        "archived_at": brief_item.archived_at,
        **source_context,
        "updated_at": brief_item.updated_at,
    }


def _ensure_site_exists(session: Session, site_id: int) -> None:
    exists = session.scalar(select(Site.id).where(Site.id == site_id))
    if exists is None:
        raise SemstormBriefServiceError(
            f"Site {site_id} not found.",
            code="not_found",
            status_code=404,
        )


def _load_brief_items(session: Session, site_id: int) -> list[SiteSemstormBriefItem]:
    return list(
        session.scalars(
            select(SiteSemstormBriefItem)
            .where(SiteSemstormBriefItem.site_id == site_id)
            .options(
                selectinload(SiteSemstormBriefItem.plan_item).selectinload(SiteSemstormPlanItem.promoted_item)
            )
            .order_by(SiteSemstormBriefItem.updated_at.desc(), SiteSemstormBriefItem.id.desc())
        )
    )


def _apply_brief_filters(
    items: Sequence[SiteSemstormBriefItem],
    *,
    state_status: SemstormBriefStateStatus | None,
    brief_type: SemstormBriefType | None,
    search_intent: SemstormBriefSearchIntent | None,
    search: str | None,
) -> list[SiteSemstormBriefItem]:
    search_term = _normalize_search(search)
    filtered: list[SiteSemstormBriefItem] = []
    for item in items:
        if state_status is not None and str(item.state_status) != state_status:
            continue
        if brief_type is not None and str(item.brief_type) != brief_type:
            continue
        if search_intent is not None and str(item.search_intent) != search_intent:
            continue
        if search_term and not _brief_matches_search(item, search_term):
            continue
        filtered.append(item)
    return filtered


def _apply_execution_filters(
    items: Sequence[SiteSemstormBriefItem],
    *,
    execution_status: SemstormBriefStateStatus | None,
    assignee: str | None,
    brief_type: SemstormBriefType | None,
    search: str | None,
) -> list[SiteSemstormBriefItem]:
    assignee_term = _normalize_search(assignee)
    search_term = _normalize_search(search)
    filtered: list[SiteSemstormBriefItem] = []
    for item in items:
        if execution_status is not None and str(item.state_status) != execution_status:
            continue
        if brief_type is not None and str(item.brief_type) != brief_type:
            continue
        if assignee_term and assignee_term not in str(item.assignee or "").strip().lower():
            continue
        if search_term and not _brief_matches_search(item, search_term):
            continue
        filtered.append(item)
    return filtered


def _apply_implemented_filters(
    items: Sequence[dict[str, Any]],
    *,
    implementation_status: SemstormBriefImplementationStatus | None,
    outcome_status: SemstormBriefOutcomeStatus | None,
    brief_type: SemstormBriefType | None,
    search: str | None,
) -> list[dict[str, Any]]:
    search_term = _normalize_search(search)
    filtered: list[dict[str, Any]] = []
    for item in items:
        if implementation_status is not None and str(item.get("implementation_status") or "") != implementation_status:
            continue
        if outcome_status is not None and str(item.get("outcome_status") or "") != outcome_status:
            continue
        if brief_type is not None and str(item.get("brief_type") or "") != brief_type:
            continue
        if search_term and not _implemented_item_matches_search(item, search_term):
            continue
        filtered.append(item)
    return filtered


def _brief_matches_search(item: SiteSemstormBriefItem, search_term: str) -> bool:
    haystacks = [
        item.brief_title,
        item.primary_keyword,
        item.recommended_page_title,
        item.proposed_url_slug,
        item.assignee,
    ]
    return any(search_term in str(value or "").strip().lower() for value in haystacks)


def _implemented_item_matches_search(item: Mapping[str, Any], search_term: str) -> bool:
    matched_page = item.get("matched_page") if isinstance(item.get("matched_page"), Mapping) else {}
    haystacks = [
        item.get("brief_title"),
        item.get("primary_keyword"),
        item.get("recommended_page_title"),
        item.get("proposed_url_slug"),
        item.get("assignee"),
        item.get("evaluation_note"),
        matched_page.get("url"),
        matched_page.get("title"),
    ]
    return any(search_term in str(value or "").strip().lower() for value in haystacks)


def _build_brief_state_counts(items: Sequence[SiteSemstormBriefItem]) -> dict[str, int]:
    counts = {"draft": 0, "ready": 0, "in_execution": 0, "completed": 0, "archived": 0}
    for item in items:
        state_status = str(item.state_status or "draft")
        if state_status in counts:
            counts[state_status] += 1
    return counts


def _build_brief_type_counts(items: Sequence[SiteSemstormBriefItem]) -> dict[str, int]:
    counts = {"new_page": 0, "expand_existing": 0, "refresh_existing": 0, "cluster_support": 0}
    for item in items:
        brief_type = str(item.brief_type or "new_page")
        if brief_type in counts:
            counts[brief_type] += 1
    return counts


def _build_intent_counts(items: Sequence[SiteSemstormBriefItem]) -> dict[str, int]:
    counts = {"informational": 0, "commercial": 0, "transactional": 0, "navigational": 0, "mixed": 0}
    for item in items:
        search_intent = str(item.search_intent or "mixed")
        if search_intent in counts:
            counts[search_intent] += 1
    return counts


def _build_implemented_status_counts(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"too_early": 0, "implemented": 0, "evaluated": 0, "archived": 0}
    for item in items:
        state_value = str(item.get("implementation_status") or "")
        if state_value in counts:
            counts[state_value] += 1
    return counts


def _build_outcome_status_counts(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"too_early": 0, "no_signal": 0, "weak_signal": 0, "positive_signal": 0}
    for item in items:
        state_value = str(item.get("outcome_status") or "")
        if state_value in counts:
            counts[state_value] += 1
    return counts


def _get_brief_item_or_raise(session: Session, site_id: int, brief_id: int) -> SiteSemstormBriefItem:
    brief_item = session.scalar(
        select(SiteSemstormBriefItem)
        .where(
            SiteSemstormBriefItem.site_id == site_id,
            SiteSemstormBriefItem.id == brief_id,
        )
        .options(
            selectinload(SiteSemstormBriefItem.plan_item).selectinload(SiteSemstormPlanItem.promoted_item)
        )
    )
    if brief_item is None:
        raise SemstormBriefServiceError(
            f"Semstorm brief item {brief_id} not found.",
            code="not_found",
            status_code=404,
        )
    return brief_item


def _serialize_brief_source_context(brief_item: SiteSemstormBriefItem) -> dict[str, Any]:
    plan_item = brief_item.plan_item
    if plan_item is None:
        return {
            "decision_type_snapshot": None,
            "bucket_snapshot": None,
            "coverage_status_snapshot": None,
            "gsc_signal_status_snapshot": None,
            "opportunity_score_v2_snapshot": 0,
        }
    return {
        "decision_type_snapshot": plan_item.decision_type_snapshot,
        "bucket_snapshot": plan_item.bucket_snapshot,
        "coverage_status_snapshot": plan_item.coverage_status_snapshot,
        "gsc_signal_status_snapshot": plan_item.gsc_signal_status_snapshot,
        "opportunity_score_v2_snapshot": int(plan_item.opportunity_score_v2_snapshot or 0),
    }


def _serialize_brief_implementation_status(brief_item: SiteSemstormBriefItem) -> str | None:
    return _normalize_existing_implementation_status(brief_item.implementation_status)


def _build_implemented_item_payload(
    brief_item: SiteSemstormBriefItem,
    *,
    coverage_context: semstorm_coverage_service.SiteCoverageContext,
    window_days: int,
) -> dict[str, Any]:
    now = utcnow()
    stored_status = _normalize_existing_implementation_status(brief_item.implementation_status)
    effective_status = "implemented" if stored_status in {"implemented", "too_early"} else (stored_status or "implemented")
    implemented_at = _ensure_utc_datetime(brief_item.implemented_at)
    is_too_early = _implemented_item_is_too_early(implemented_at, reference_at=now, window_days=window_days)
    matched_page, match_notes = _resolve_implemented_page_match(brief_item, coverage_context)
    gsc_signal = _build_implemented_gsc_signal(
        coverage_context,
        brief_item=brief_item,
        matched_page=matched_page,
    )
    page_present_in_active_crawl = matched_page is not None
    notes = list(match_notes)
    if coverage_context.active_crawl_id is None:
        notes.append("No active crawl is available for outcome checks.")
    elif not coverage_context.pages:
        notes.append("Active crawl has no internal pages to match against this brief.")
    if not coverage_context.url_metrics_by_page_id and not coverage_context.top_queries:
        notes.append("No GSC metrics are available for the active crawl.")
    if not page_present_in_active_crawl:
        notes.append("No matching page is currently present in the active crawl.")
    if gsc_signal["query_match_count"] <= 0:
        notes.append("No matching GSC queries were found for the current brief keywords.")
    if brief_item.evaluation_note:
        notes.append(f"Evaluation note: {brief_item.evaluation_note}")

    if stored_status in {"implemented", "too_early"} and not is_too_early:
        brief_item.implementation_status = "evaluated"
        stored_status = "evaluated"
        effective_status = "evaluated"
    elif stored_status == "archived":
        effective_status = "archived"
    elif is_too_early:
        effective_status = "too_early"
    elif stored_status == "evaluated":
        effective_status = "evaluated"

    brief_item.last_outcome_checked_at = now

    outcome_status = _resolve_implemented_outcome_status(
        is_too_early=is_too_early,
        page_present_in_active_crawl=page_present_in_active_crawl,
        gsc_signal_status=str(gsc_signal["gsc_signal_status"]),
        query_match_count=int(gsc_signal["query_match_count"]),
    )
    if outcome_status == "too_early":
        notes.append(f"Too early to evaluate against the {window_days}-day outcome window.")

    source_context = _serialize_brief_source_context(brief_item)
    return {
        "brief_id": brief_item.id,
        "plan_item_id": brief_item.plan_item_id,
        "brief_title": brief_item.brief_title,
        "primary_keyword": brief_item.primary_keyword,
        "brief_type": brief_item.brief_type,
        "execution_status": brief_item.state_status,
        "implementation_status": effective_status,
        "implemented_at": implemented_at,
        "evaluation_note": brief_item.evaluation_note,
        "implementation_url_override": brief_item.implementation_url_override,
        "outcome_status": outcome_status,
        "page_present_in_active_crawl": page_present_in_active_crawl,
        "matched_page": matched_page,
        "gsc_signal_status": gsc_signal["gsc_signal_status"],
        "gsc_summary": gsc_signal["gsc_summary"],
        "query_match_count": int(gsc_signal["query_match_count"]),
        "notes": dedupe_preserve_order(note for note in notes if str(note or "").strip()),
        **source_context,
        "updated_at": brief_item.updated_at,
        "last_outcome_checked_at": brief_item.last_outcome_checked_at,
    }


def _apply_brief_execution_transition(
    brief_item: SiteSemstormBriefItem,
    state_status: Any,
) -> None:
    normalized_state = _normalize_state_status(state_status)
    current_state = str(brief_item.state_status or "draft")
    if normalized_state == current_state:
        brief_item.updated_at = utcnow()
        return

    allowed_transitions = _BRIEF_ALLOWED_TRANSITIONS.get(current_state, set())
    if normalized_state not in allowed_transitions:
        raise SemstormBriefServiceError(
            f"Invalid Semstorm brief execution transition '{current_state}' -> '{normalized_state}'.",
            code="invalid_execution_transition",
            status_code=409,
        )

    now = utcnow()
    brief_item.state_status = normalized_state
    brief_item.updated_at = now
    if normalized_state == "ready":
        brief_item.ready_at = now
    elif normalized_state == "in_execution":
        brief_item.started_at = now
    elif normalized_state == "completed":
        brief_item.completed_at = now
    elif normalized_state == "archived":
        brief_item.archived_at = now


def _build_brief_scaffold(
    session: Session,
    *,
    site_id: int,
    plan_item: SiteSemstormPlanItem,
    coverage_context: semstorm_coverage_service.SiteCoverageContext,
) -> dict[str, Any]:
    promoted_item = plan_item.promoted_item
    source_payload = (
        dict(promoted_item.source_payload_json or {})
        if promoted_item is not None and isinstance(promoted_item.source_payload_json, dict)
        else {}
    )
    brief_type = _normalize_brief_type(plan_item.target_page_type)
    primary_keyword = _resolve_primary_keyword(plan_item)
    secondary_keywords = _resolve_secondary_keywords(plan_item, primary_keyword=primary_keyword)
    search_intent = _infer_search_intent(
        primary_keyword,
        brief_type=brief_type,
        decision_type=str(plan_item.decision_type_snapshot or ""),
        coverage_status=str(plan_item.coverage_status_snapshot or ""),
    )
    existing_page = source_payload.get("best_match_page") if isinstance(source_payload.get("best_match_page"), dict) else {}
    existing_url = _normalize_optional_text(plan_item.best_match_page_url_snapshot, max_length=2048) or _normalize_optional_text(
        existing_page.get("url"),
        max_length=2048,
    )
    existing_title = _normalize_optional_text(existing_page.get("title"))
    proposed_url_slug = _normalize_optional_text(plan_item.proposed_slug, max_length=512)
    if proposed_url_slug is None and brief_type in {"new_page", "cluster_support"}:
        proposed_url_slug = _slugify(primary_keyword) or None

    brief_title = _default_brief_title(primary_keyword, brief_type)
    recommended_page_title = _build_recommended_page_title(
        primary_keyword,
        brief_type=brief_type,
        search_intent=search_intent,
        existing_title=existing_title,
    )
    recommended_h1 = _build_recommended_h1(primary_keyword)
    target_url_existing = existing_url if brief_type != "new_page" else None
    content_goal = _build_content_goal(
        primary_keyword,
        brief_type=brief_type,
        coverage_status=str(plan_item.coverage_status_snapshot or "missing"),
        competitor_count=_int_or_zero(source_payload.get("competitor_count")),
        gsc_signal_status=str(plan_item.gsc_signal_status_snapshot or "none"),
    )
    angle_summary = _build_angle_summary(
        brief_type=brief_type,
        bucket=str(plan_item.bucket_snapshot or "watchlist"),
        decision_type=str(plan_item.decision_type_snapshot or "monitor_only"),
        coverage_status=str(plan_item.coverage_status_snapshot or "missing"),
        gsc_signal_status=str(plan_item.gsc_signal_status_snapshot or "none"),
        existing_url=existing_url,
    )
    sections = _build_sections(primary_keyword, brief_type=brief_type)
    internal_link_targets = _build_internal_link_targets(
        coverage_context,
        primary_keyword=primary_keyword,
        existing_url=existing_url,
    )
    source_notes = _build_source_notes(plan_item, source_payload)
    return {
        "brief_title": brief_title,
        "brief_type": brief_type,
        "primary_keyword": primary_keyword,
        "secondary_keywords": secondary_keywords,
        "search_intent": search_intent,
        "target_url_existing": target_url_existing,
        "proposed_url_slug": proposed_url_slug,
        "recommended_page_title": recommended_page_title,
        "recommended_h1": recommended_h1,
        "content_goal": content_goal,
        "angle_summary": angle_summary,
        "sections": sections,
        "internal_link_targets": internal_link_targets,
        "source_notes": source_notes,
    }


def _resolve_primary_keyword(plan_item: SiteSemstormPlanItem) -> str:
    primary = _normalize_optional_text(plan_item.proposed_primary_keyword, max_length=512)
    if primary is not None:
        return primary
    return _normalize_required_text(plan_item.keyword, field_name="keyword", max_length=512)


def _resolve_secondary_keywords(
    plan_item: SiteSemstormPlanItem,
    *,
    primary_keyword: str,
) -> list[str]:
    configured = _normalize_string_list(
        list(plan_item.proposed_secondary_keywords_json or []),
        field_name="proposed_secondary_keywords",
        max_length=512,
    )
    if configured:
        return configured
    candidates = [plan_item.keyword]
    return [
        value
        for value in dedupe_preserve_order(candidates)
        if normalize_text_for_hash(value) and normalize_text_for_hash(value) != normalize_text_for_hash(primary_keyword)
    ]


def _default_brief_title(primary_keyword: str, brief_type: SemstormBriefType) -> str:
    keyword_label = _title_case_keyword(primary_keyword)
    if brief_type == "new_page":
        return f"New page brief: {keyword_label}"
    if brief_type == "expand_existing":
        return f"Expansion brief: {keyword_label}"
    if brief_type == "refresh_existing":
        return f"Refresh brief: {keyword_label}"
    return f"Cluster support brief: {keyword_label}"


def _infer_search_intent(
    primary_keyword: str,
    *,
    brief_type: SemstormBriefType,
    decision_type: str,
    coverage_status: str,
) -> SemstormBriefSearchIntent:
    tokens = set(_tokenize_keyword(primary_keyword))
    if tokens & _NAVIGATIONAL_TOKENS:
        return "navigational"
    if tokens & _TRANSACTIONAL_TOKENS:
        return "transactional"
    if tokens & _INFORMATIONAL_TOKENS:
        return "informational"
    if tokens & _COMMERCIAL_TOKENS:
        return "commercial"
    if decision_type == "create_new_page" and coverage_status == "missing":
        return "commercial" if brief_type == "new_page" else "mixed"
    if decision_type == "expand_existing_page":
        return "mixed"
    return "mixed"


def _build_recommended_page_title(
    primary_keyword: str,
    *,
    brief_type: SemstormBriefType,
    search_intent: SemstormBriefSearchIntent,
    existing_title: str | None,
) -> str:
    keyword_label = _title_case_keyword(primary_keyword)
    if existing_title and brief_type in {"expand_existing", "refresh_existing"}:
        return f"{existing_title} | {keyword_label}"
    if brief_type == "cluster_support":
        return f"{keyword_label} | Supporting Topic"
    if search_intent == "informational":
        return f"{keyword_label} | Guide and Checklist"
    if search_intent == "transactional":
        return f"{keyword_label} | Pricing and Options"
    if search_intent == "commercial":
        return f"{keyword_label} | Services and Next Steps"
    return f"{keyword_label} | Overview and Next Steps"


def _build_recommended_h1(primary_keyword: str) -> str:
    return _title_case_keyword(primary_keyword)


def _build_content_goal(
    primary_keyword: str,
    *,
    brief_type: SemstormBriefType,
    coverage_status: str,
    competitor_count: int,
    gsc_signal_status: str,
) -> str:
    if brief_type == "new_page":
        goal = (
            f"Create a new page targeting '{primary_keyword}' because the current site coverage is {coverage_status.replace('_', ' ')} "
            f"and competitors are already visible on this topic."
        )
    elif brief_type == "expand_existing":
        goal = (
            f"Expand the existing page coverage for '{primary_keyword}' because the current match is still {coverage_status.replace('_', ' ')} "
            f"and the topic shows live competitive demand."
        )
    elif brief_type == "refresh_existing":
        goal = (
            f"Refresh the existing page for '{primary_keyword}' to improve competitiveness and close the current coverage gap."
        )
    else:
        goal = (
            f"Create a supporting cluster brief for '{primary_keyword}' to deepen topical coverage around the current site page set."
        )
    signal_tail = f" Competitive signal currently comes from {competitor_count} competitors."
    if gsc_signal_status != "none":
        signal_tail += f" There is also a {gsc_signal_status.replace('_', ' ')} GSC signal on the current site."
    return f"{goal}{signal_tail}"


def _build_angle_summary(
    *,
    brief_type: SemstormBriefType,
    bucket: str,
    decision_type: str,
    coverage_status: str,
    gsc_signal_status: str,
    existing_url: str | None,
) -> str:
    bucket_label = bucket.replace("_", " ")
    decision_label = decision_type.replace("_", " ")
    coverage_label = coverage_status.replace("_", " ")
    gsc_label = gsc_signal_status.replace("_", " ")
    first_sentence = f"This scaffold comes from a {bucket_label} opportunity with the decision to {decision_label}."
    second_sentence = f"Current site coverage is {coverage_label} and the current GSC signal is {gsc_label}."
    if existing_url:
        third_sentence = f"The closest current page is {existing_url}, so the brief should stay anchored to that context."
    elif brief_type == "new_page":
        third_sentence = "There is no strong existing page context, so the brief is framed as a new standalone asset."
    else:
        third_sentence = "Existing page context is limited, so the brief keeps the execution packet intentionally lightweight."
    return " ".join([first_sentence, second_sentence, third_sentence])


def _build_sections(primary_keyword: str, *, brief_type: SemstormBriefType) -> list[str]:
    keyword_label = _title_case_keyword(primary_keyword)
    if brief_type == "new_page":
        return [
            f"Introduction to {keyword_label}",
            f"When {keyword_label} matters",
            f"Process or checklist for {keyword_label}",
            "Examples and practical scenarios",
            "Common mistakes and FAQs",
            "Next steps",
        ]
    if brief_type == "expand_existing":
        return [
            "Current gap to close",
            f"Expanded coverage of {keyword_label}",
            "Examples, proof points and supporting detail",
            "Decision criteria or comparison points",
            "FAQs and objections",
            "Internal links and related resources",
        ]
    if brief_type == "refresh_existing":
        return [
            "What needs updating",
            f"Refreshed scope of {keyword_label}",
            "Current examples and proof points",
            "Best practices and pitfalls",
            "FAQ refresh",
        ]
    return [
        "How this topic supports the main page",
        f"Subtopic overview for {keyword_label}",
        "Detailed steps or checklist",
        "Examples and implementation notes",
        "Related questions",
        "Links back to the core page",
    ]


def _build_internal_link_targets(
    coverage_context: semstorm_coverage_service.SiteCoverageContext,
    *,
    primary_keyword: str,
    existing_url: str | None,
) -> list[str]:
    targets: list[str] = []
    if existing_url:
        targets.append(existing_url)

    keyword_tokens = set(_tokenize_keyword(primary_keyword))
    if not coverage_context.pages or not keyword_tokens:
        return dedupe_preserve_order(targets)[:3]

    scored_candidates: list[tuple[int, int, str]] = []
    existing_normalized = normalize_text_for_hash(existing_url)
    for page in coverage_context.pages:
        if existing_normalized and normalize_text_for_hash(page.url) == existing_normalized:
            continue
        page_tokens = set(_tokenize_keyword(f"{page.title or ''} {page.url}"))
        overlap = len(keyword_tokens & page_tokens)
        if overlap <= 0:
            continue
        scored_candidates.append((-overlap, int(page.page_id), page.url))

    scored_candidates.sort()
    for _score, _page_id, url in scored_candidates:
        targets.append(url)
        if len(dedupe_preserve_order(targets)) >= 3:
            break
    return dedupe_preserve_order(targets)[:3]


def _build_source_notes(plan_item: SiteSemstormPlanItem, source_payload: Mapping[str, Any]) -> list[str]:
    notes = [
        f"Source run: #{int(plan_item.source_run_id)}",
        f"Opportunity score v2: {int(plan_item.opportunity_score_v2_snapshot or 0)}",
        f"Decision type: {str(plan_item.decision_type_snapshot or '').replace('_', ' ')}",
        f"Bucket: {str(plan_item.bucket_snapshot or '').replace('_', ' ')}",
        f"Coverage status: {str(plan_item.coverage_status_snapshot or '').replace('_', ' ')}",
        f"GSC signal: {str(plan_item.gsc_signal_status_snapshot or '').replace('_', ' ')}",
    ]
    if plan_item.best_match_page_url_snapshot:
        notes.append(f"Best match page: {plan_item.best_match_page_url_snapshot}")
    competitor_count = _int_or_zero(source_payload.get("competitor_count"))
    if competitor_count > 0:
        notes.append(f"Competitor count: {competitor_count}")
    gsc_summary = source_payload.get("gsc_summary")
    if isinstance(gsc_summary, Mapping):
        clicks = _int_or_zero(gsc_summary.get("clicks"))
        impressions = _int_or_zero(gsc_summary.get("impressions"))
        ctr = gsc_summary.get("ctr")
        avg_position = gsc_summary.get("avg_position")
        ctr_text = f"{round(float(ctr) * 100, 1)}%" if isinstance(ctr, (int, float)) else "-"
        position_text = f"{round(float(avg_position), 1)}" if isinstance(avg_position, (int, float)) else "-"
        notes.append(
            f"GSC summary: {clicks} clicks, {impressions} impressions, CTR {ctr_text}, avg position {position_text}"
        )
    sample_competitors = [
        str(value).strip()
        for value in (source_payload.get("sample_competitors") or [])
        if str(value).strip()
    ]
    if sample_competitors:
        notes.append(f"Sample competitors: {', '.join(sample_competitors[:3])}")
    return notes


def _normalize_plan_item_ids(values: Sequence[int]) -> list[int]:
    deduped: list[int] = []
    seen: set[int] = set()
    for value in values:
        item_id = int(value or 0)
        if item_id <= 0 or item_id in seen:
            continue
        seen.add(item_id)
        deduped.append(item_id)
    return deduped


def _normalize_implementation_action_status(value: Any) -> Literal["implemented", "archived"]:
    normalized = str(value or "").strip()
    if normalized not in {"implemented", "archived"}:
        raise SemstormBriefServiceError(
            f"Unsupported implementation_status '{value}'.",
            code="invalid_implementation_status",
            status_code=400,
        )
    return normalized  # type: ignore[return-value]


def _normalize_existing_implementation_status(value: Any) -> SemstormBriefImplementationStatus | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized not in _IMPLEMENTATION_STATUS_VALUES:
        return None
    return normalized  # type: ignore[return-value]


def _normalize_window_days(value: Any) -> int:
    try:
        parsed = int(value or _OUTCOME_WINDOW_DEFAULT_DAYS)
    except (TypeError, ValueError):
        parsed = _OUTCOME_WINDOW_DEFAULT_DAYS
    return max(1, min(parsed, _OUTCOME_WINDOW_MAX_DAYS))


def _has_implementation_state(brief_item: SiteSemstormBriefItem) -> bool:
    return _normalize_existing_implementation_status(brief_item.implementation_status) is not None


def _ensure_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=utcnow().tzinfo)
    return value


def _implemented_item_is_too_early(
    implemented_at: datetime | None,
    *,
    reference_at: datetime,
    window_days: int,
) -> bool:
    if not isinstance(implemented_at, datetime):
        return False
    return reference_at < implemented_at + timedelta(days=window_days)


def _resolve_implemented_page_match(
    brief_item: SiteSemstormBriefItem,
    coverage_context: semstorm_coverage_service.SiteCoverageContext,
) -> tuple[dict[str, Any] | None, list[str]]:
    notes: list[str] = []
    if not coverage_context.pages:
        return None, notes

    override_url = _normalize_optional_text(brief_item.implementation_url_override, max_length=2048)
    if override_url:
        page = _find_page_by_exact_url(coverage_context, override_url)
        if page is not None:
            notes.append("Matched active crawl page via implementation URL override.")
            return _serialize_matched_coverage_page(page, match_signals=["implementation_url_override"]), notes
        notes.append("Implementation URL override is not present in the active crawl.")
        return None, notes

    existing_url = _normalize_optional_text(brief_item.target_url_existing, max_length=2048)
    if existing_url:
        page = _find_page_by_exact_url(coverage_context, existing_url)
        if page is not None:
            notes.append("Matched active crawl page via existing target URL.")
            return _serialize_matched_coverage_page(page, match_signals=["target_url_existing"]), notes

    proposed_slug = _normalize_optional_text(brief_item.proposed_url_slug, max_length=512)
    if proposed_slug:
        page = _find_page_by_slug(coverage_context, proposed_slug)
        if page is not None:
            notes.append("Matched active crawl page via proposed slug.")
            return _serialize_matched_coverage_page(page, match_signals=["proposed_url_slug"]), notes

    coverage_match = semstorm_coverage_service.evaluate_keyword_coverage(coverage_context, brief_item.primary_keyword)
    best_match = coverage_match.get("best_match_page") if isinstance(coverage_match, Mapping) else None
    if isinstance(best_match, Mapping):
        notes.append("Matched active crawl page via keyword coverage fallback.")
        return {
            "page_id": int(best_match.get("page_id") or 0),
            "url": str(best_match.get("url") or ""),
            "title": _normalize_optional_text(best_match.get("title")),
            "match_signals": list(best_match.get("match_signals") or []),
        }, notes
    return None, notes


def _serialize_matched_coverage_page(
    page: semstorm_coverage_service.CoveragePageCandidate,
    *,
    match_signals: list[str],
) -> dict[str, Any]:
    return {
        "page_id": int(page.page_id),
        "url": page.url,
        "title": page.title,
        "match_signals": list(match_signals),
    }


def _find_page_by_exact_url(
    coverage_context: semstorm_coverage_service.SiteCoverageContext,
    url: str,
) -> semstorm_coverage_service.CoveragePageCandidate | None:
    normalized_target = normalize_text_for_hash(url)
    if not normalized_target:
        return None
    for page in coverage_context.pages:
        if normalize_text_for_hash(page.url) == normalized_target:
            return page
    return None


def _find_page_by_slug(
    coverage_context: semstorm_coverage_service.SiteCoverageContext,
    slug: str,
) -> semstorm_coverage_service.CoveragePageCandidate | None:
    normalized_slug = _normalize_outcome_text(slug)
    if not normalized_slug:
        return None
    slug_tokens = set(_tokenize_outcome_text(normalized_slug))
    best_candidate: tuple[int, int, semstorm_coverage_service.CoveragePageCandidate] | None = None
    for page in coverage_context.pages:
        normalized_url = _normalize_outcome_text(page.url)
        if not normalized_url:
            continue
        score = 0
        if normalized_slug in normalized_url:
            score = 100
        else:
            page_tokens = set(_tokenize_outcome_text(normalized_url))
            overlap = len(slug_tokens & page_tokens)
            if overlap <= 0:
                continue
            score = overlap * 10
        candidate_key = (-score, int(page.page_id))
        if best_candidate is None or candidate_key < (best_candidate[0], best_candidate[1]):
            best_candidate = (candidate_key[0], candidate_key[1], page)
    return best_candidate[2] if best_candidate is not None else None


def _build_implemented_gsc_signal(
    coverage_context: semstorm_coverage_service.SiteCoverageContext,
    *,
    brief_item: SiteSemstormBriefItem,
    matched_page: Mapping[str, Any] | None,
) -> dict[str, Any]:
    keyword_targets = _build_brief_keyword_targets(brief_item)
    matched_page_id = int(matched_page.get("page_id") or 0) if isinstance(matched_page, Mapping) else None
    preferred_queries = [
        row
        for row in coverage_context.top_queries
        if matched_page_id is not None and row.page_id == matched_page_id and _query_matches_keyword_targets(row.normalized_query, keyword_targets)
    ]
    fallback_queries = [
        row
        for row in coverage_context.top_queries
        if _query_matches_keyword_targets(row.normalized_query, keyword_targets)
    ]
    query_rows = preferred_queries or fallback_queries
    query_match_count = len(query_rows)
    gsc_summary = _aggregate_gsc_rows(query_rows) if query_rows else None

    url_metric = (
        coverage_context.url_metrics_by_page_id.get(matched_page_id)
        if matched_page_id is not None
        else None
    )
    if gsc_summary is None and url_metric is not None:
        gsc_summary = {
            "clicks": int(url_metric.clicks),
            "impressions": int(url_metric.impressions),
            "ctr": url_metric.ctr,
            "avg_position": url_metric.avg_position,
        }

    if query_rows and (int(gsc_summary.get("clicks") or 0) > 0 or int(gsc_summary.get("impressions") or 0) >= 20):
        gsc_signal_status = "present"
    elif query_rows or (url_metric is not None and (int(url_metric.impressions) > 0 or int(url_metric.clicks) > 0)):
        gsc_signal_status = "weak"
    else:
        gsc_signal_status = "none"

    return {
        "gsc_signal_status": gsc_signal_status,
        "gsc_summary": gsc_summary,
        "query_match_count": query_match_count,
    }


def _build_brief_keyword_targets(brief_item: SiteSemstormBriefItem) -> list[str]:
    return [
        normalized
        for normalized in (
            _normalize_outcome_text(value)
            for value in [brief_item.primary_keyword, *(brief_item.secondary_keywords_json or [])]
        )
        if normalized
    ]


def _query_matches_keyword_targets(normalized_query: str, keyword_targets: Sequence[str]) -> bool:
    if not normalized_query:
        return False
    for keyword in keyword_targets:
        if normalized_query == keyword:
            return True
        if _contains_outcome_phrase(normalized_query, keyword) or _contains_outcome_phrase(keyword, normalized_query):
            return True
        query_tokens = set(_tokenize_outcome_text(normalized_query))
        keyword_tokens = set(_tokenize_outcome_text(keyword))
        if keyword_tokens and len(query_tokens & keyword_tokens) >= max(1, min(len(keyword_tokens), 2)):
            return True
    return False


def _aggregate_gsc_rows(rows: Sequence[semstorm_coverage_service.GscQuerySignal]) -> dict[str, Any]:
    clicks = sum(int(row.clicks) for row in rows)
    impressions = sum(int(row.impressions) for row in rows)
    weighted_position = 0.0
    weighted_impressions = 0
    for row in rows:
        if row.position is None:
            continue
        row_weight = max(1, int(row.impressions))
        weighted_position += float(row.position) * row_weight
        weighted_impressions += row_weight
    avg_position = round(weighted_position / weighted_impressions, 2) if weighted_impressions > 0 else None
    ctr = round(clicks / impressions, 4) if impressions > 0 else None
    return {
        "clicks": clicks,
        "impressions": impressions,
        "ctr": ctr,
        "avg_position": avg_position,
    }


def _resolve_implemented_outcome_status(
    *,
    is_too_early: bool,
    page_present_in_active_crawl: bool,
    gsc_signal_status: str,
    query_match_count: int,
) -> SemstormBriefOutcomeStatus:
    if is_too_early:
        return "too_early"
    if gsc_signal_status == "present" and page_present_in_active_crawl:
        return "positive_signal"
    if gsc_signal_status == "weak" and (page_present_in_active_crawl or query_match_count > 0):
        return "weak_signal"
    if page_present_in_active_crawl and query_match_count > 0:
        return "weak_signal"
    return "no_signal"


def _normalize_state_status(value: Any) -> SemstormBriefStateStatus:
    normalized = str(value or "").strip()
    if normalized not in _BRIEF_STATE_VALUES:
        raise SemstormBriefServiceError(
            f"Unsupported brief state_status '{value}'.",
            code="invalid_state_status",
            status_code=400,
        )
    return normalized  # type: ignore[return-value]


def _normalize_brief_type(value: Any) -> SemstormBriefType:
    normalized = str(value or "").strip()
    if normalized not in _BRIEF_TYPE_VALUES:
        raise SemstormBriefServiceError(
            f"Unsupported brief_type '{value}'.",
            code="invalid_brief_type",
            status_code=400,
        )
    return normalized  # type: ignore[return-value]


def _normalize_search_intent(value: Any) -> SemstormBriefSearchIntent:
    normalized = str(value or "").strip()
    if normalized not in _SEARCH_INTENT_VALUES:
        raise SemstormBriefServiceError(
            f"Unsupported search_intent '{value}'.",
            code="invalid_search_intent",
            status_code=400,
        )
    return normalized  # type: ignore[return-value]


def _normalize_optional_text(value: Any, *, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length] if max_length is not None else text


def _normalize_required_text(value: Any, *, field_name: str, max_length: int | None = None) -> str:
    text = _normalize_optional_text(value, max_length=max_length)
    if text is None:
        raise SemstormBriefServiceError(
            f"{field_name} is required.",
            code=f"invalid_{field_name}",
            status_code=400,
        )
    return text


def _normalize_string_list(
    value: Any,
    *,
    field_name: str,
    max_length: int | None = None,
) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SemstormBriefServiceError(
            f"{field_name} must be a list of strings.",
            code=f"invalid_{field_name}",
            status_code=400,
        )
    items: list[str] = []
    seen: set[str] = set()
    for raw_item in value:
        normalized_item = _normalize_optional_text(raw_item, max_length=max_length)
        if normalized_item is None:
            continue
        dedupe_key = normalize_text_for_hash(normalized_item)
        if not dedupe_key or dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        items.append(normalized_item)
    return items


def _normalize_search(value: str | None) -> str:
    return str(value or "").strip().lower()


def _normalize_outcome_text(value: Any) -> str:
    ascii_text = normalize_ascii(str(value or "").strip().lower())
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()


def _tokenize_outcome_text(value: Any) -> list[str]:
    return [token for token in _normalize_outcome_text(value).split() if len(token) >= 2]


def _contains_outcome_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    return f" {phrase} " in f" {text} "


def _title_case_keyword(value: str) -> str:
    parts = re.split(r"(\s+|-)", str(value or "").strip())
    transformed: list[str] = []
    for part in parts:
        if not part or part.isspace() or part == "-":
            transformed.append(part)
            continue
        lower_part = part.lower()
        if lower_part in _TITLE_UPPERCASE_TOKENS:
            transformed.append(lower_part.upper())
        else:
            transformed.append(lower_part.capitalize())
    return "".join(transformed) or value


def _slugify(value: str) -> str:
    tokens = _TOKEN_SPLIT_RE.split(normalize_text_for_hash(value))
    return "-".join(token for token in tokens if token)[:512]


def _tokenize_keyword(value: str) -> list[str]:
    return tokenize_topic_text(value, min_length=2)


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

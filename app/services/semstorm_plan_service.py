from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Site, SiteSemstormPlanItem, SiteSemstormPromotedItem, utcnow
from app.services import semstorm_opportunity_state_service


SemstormPlanStateStatus = Literal["planned", "in_progress", "done", "archived"]
SemstormPlanTargetPageType = Literal["new_page", "expand_existing", "refresh_existing", "cluster_support"]

_PLAN_STATE_VALUES = {"planned", "in_progress", "done", "archived"}
_PLAN_TARGET_PAGE_TYPE_VALUES = {"new_page", "expand_existing", "refresh_existing", "cluster_support"}
_SLUG_TOKEN_RE = re.compile(r"[^a-z0-9]+")


class SemstormPlanServiceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "semstorm_plan_error",
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def create_semstorm_plan_items(
    session: Session,
    site_id: int,
    *,
    promoted_item_ids: Sequence[int],
    target_page_type: SemstormPlanTargetPageType | None = None,
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    requested_ids = _normalize_promoted_item_ids(promoted_item_ids)
    promoted_items = list(
        session.scalars(
            select(SiteSemstormPromotedItem)
            .where(
                SiteSemstormPromotedItem.site_id == site_id,
                SiteSemstormPromotedItem.id.in_(requested_ids),
            )
            .order_by(SiteSemstormPromotedItem.id.asc())
        )
    )
    promoted_by_id = {int(item.id): item for item in promoted_items}
    existing_plan_by_promoted_id = load_plan_items_by_promoted_ids(session, site_id, requested_ids)

    created_items: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for promoted_item_id in requested_ids:
        promoted_item = promoted_by_id.get(promoted_item_id)
        if promoted_item is None:
            skipped.append(
                {
                    "promoted_item_id": promoted_item_id,
                    "keyword": None,
                    "reason": "promoted_item_not_found",
                }
            )
            continue
        if str(promoted_item.promotion_status or "active") != "active":
            skipped.append(
                {
                    "promoted_item_id": promoted_item_id,
                    "keyword": promoted_item.keyword,
                    "reason": "promotion_not_active",
                }
            )
            continue
        if existing_plan_by_promoted_id.get(promoted_item_id) is not None:
            skipped.append(
                {
                    "promoted_item_id": promoted_item_id,
                    "keyword": promoted_item.keyword,
                    "reason": "already_exists",
                }
            )
            continue

        resolved_target_page_type = target_page_type or _default_target_page_type(promoted_item)
        now = utcnow()
        plan_item = SiteSemstormPlanItem(
            site_id=site_id,
            promoted_item_id=promoted_item.id,
            keyword=promoted_item.keyword[:512],
            normalized_keyword=promoted_item.normalized_keyword[:512],
            source_run_id=promoted_item.source_run_id,
            state_status="planned",
            decision_type_snapshot=promoted_item.decision_type[:32],
            bucket_snapshot=promoted_item.bucket[:32],
            coverage_status_snapshot=promoted_item.coverage_status[:32],
            opportunity_score_v2_snapshot=int(promoted_item.opportunity_score_v2 or 0),
            best_match_page_url_snapshot=_normalize_optional_text(promoted_item.best_match_page_url, max_length=2048),
            gsc_signal_status_snapshot=(promoted_item.gsc_signal_status or "none")[:32],
            plan_title=_default_plan_title(promoted_item.keyword, resolved_target_page_type),
            plan_note=None,
            target_page_type=resolved_target_page_type,
            proposed_slug=_default_proposed_slug(promoted_item.keyword, resolved_target_page_type),
            proposed_primary_keyword=promoted_item.keyword[:512],
            proposed_secondary_keywords_json=[],
            created_at=now,
            updated_at=now,
        )
        session.add(plan_item)
        session.flush()
        session.refresh(plan_item)
        created_items.append(serialize_plan_item(plan_item))
        existing_plan_by_promoted_id[promoted_item_id] = plan_item

    return {
        "site_id": site_id,
        "requested_count": len(requested_ids),
        "created_count": len(created_items),
        "updated_count": 0,
        "skipped_count": len(skipped),
        "items": created_items,
        "skipped": skipped,
    }


def list_semstorm_plan_items(
    session: Session,
    site_id: int,
    *,
    state_status: SemstormPlanStateStatus | None = None,
    target_page_type: SemstormPlanTargetPageType | None = None,
    search: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    items = _load_plan_items(session, site_id)
    filtered = _apply_plan_filters(
        items,
        state_status=state_status,
        target_page_type=target_page_type,
        search=search,
    )
    normalized_limit = max(1, min(int(limit or 1), 500))
    serialized_items = [serialize_plan_item(item) for item in filtered[:normalized_limit]]
    return {
        "site_id": site_id,
        "summary": {
            "total_count": len(filtered),
            "state_counts": _build_plan_state_counts(filtered),
            "target_page_type_counts": _build_target_page_type_counts(filtered),
        },
        "items": serialized_items,
    }


def get_semstorm_plan_item(session: Session, site_id: int, plan_id: int) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    plan_item = _get_plan_item_or_raise(session, site_id, plan_id)
    return serialize_plan_item(plan_item)


def update_semstorm_plan_item_status(
    session: Session,
    site_id: int,
    plan_id: int,
    *,
    state_status: SemstormPlanStateStatus,
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    plan_item = _get_plan_item_or_raise(session, site_id, plan_id)
    _apply_plan_state(plan_item, state_status)
    session.flush()
    session.refresh(plan_item)
    return serialize_plan_item(plan_item)


def update_semstorm_plan_item(
    session: Session,
    site_id: int,
    plan_id: int,
    *,
    updates: Mapping[str, Any],
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    plan_item = _get_plan_item_or_raise(session, site_id, plan_id)
    if "state_status" in updates and updates["state_status"] is not None:
        _apply_plan_state(plan_item, str(updates["state_status"]))
    if "plan_title" in updates:
        plan_item.plan_title = _normalize_optional_text(updates.get("plan_title"))
    if "plan_note" in updates:
        plan_item.plan_note = _normalize_optional_text(updates.get("plan_note"))
    if "target_page_type" in updates and updates["target_page_type"] is not None:
        plan_item.target_page_type = _normalize_target_page_type(updates["target_page_type"])
    if "proposed_slug" in updates:
        plan_item.proposed_slug = _normalize_optional_text(updates.get("proposed_slug"), max_length=512)
    if "proposed_primary_keyword" in updates:
        plan_item.proposed_primary_keyword = _normalize_optional_text(
            updates.get("proposed_primary_keyword"),
            max_length=512,
        )
    if "proposed_secondary_keywords" in updates:
        plan_item.proposed_secondary_keywords_json = _normalize_secondary_keywords(
            updates.get("proposed_secondary_keywords")
        )

    plan_item.updated_at = utcnow()
    session.flush()
    session.refresh(plan_item)
    return serialize_plan_item(plan_item)


def load_plan_items_by_promoted_ids(
    session: Session,
    site_id: int,
    promoted_item_ids: Sequence[int],
) -> dict[int, SiteSemstormPlanItem]:
    normalized_ids = sorted({int(item_id) for item_id in promoted_item_ids if int(item_id) > 0})
    if not normalized_ids:
        return {}
    rows = list(
        session.scalars(
            select(SiteSemstormPlanItem).where(
                SiteSemstormPlanItem.site_id == site_id,
                SiteSemstormPlanItem.promoted_item_id.in_(normalized_ids),
            )
        )
    )
    return {int(row.promoted_item_id): row for row in rows}


def serialize_plan_item(plan_item: SiteSemstormPlanItem) -> dict[str, Any]:
    brief_item = plan_item.brief_item
    return {
        "id": plan_item.id,
        "site_id": plan_item.site_id,
        "promoted_item_id": plan_item.promoted_item_id,
        "keyword": plan_item.keyword,
        "normalized_keyword": plan_item.normalized_keyword,
        "source_run_id": plan_item.source_run_id,
        "state_status": plan_item.state_status,
        "decision_type_snapshot": plan_item.decision_type_snapshot,
        "bucket_snapshot": plan_item.bucket_snapshot,
        "coverage_status_snapshot": plan_item.coverage_status_snapshot,
        "opportunity_score_v2_snapshot": int(plan_item.opportunity_score_v2_snapshot or 0),
        "best_match_page_url_snapshot": plan_item.best_match_page_url_snapshot,
        "gsc_signal_status_snapshot": plan_item.gsc_signal_status_snapshot,
        "plan_title": plan_item.plan_title,
        "plan_note": plan_item.plan_note,
        "target_page_type": plan_item.target_page_type,
        "proposed_slug": plan_item.proposed_slug,
        "proposed_primary_keyword": plan_item.proposed_primary_keyword,
        "proposed_secondary_keywords": list(plan_item.proposed_secondary_keywords_json or []),
        "has_brief": brief_item is not None,
        "brief_id": int(brief_item.id) if brief_item is not None else None,
        "brief_state_status": str(brief_item.state_status) if brief_item is not None else None,
        "created_at": plan_item.created_at,
        "updated_at": plan_item.updated_at,
    }


def _ensure_site_exists(session: Session, site_id: int) -> None:
    exists = session.scalar(select(Site.id).where(Site.id == site_id))
    if exists is None:
        raise SemstormPlanServiceError(
            f"Site {site_id} not found.",
            code="not_found",
            status_code=404,
        )


def _load_plan_items(session: Session, site_id: int) -> list[SiteSemstormPlanItem]:
    return list(
        session.scalars(
            select(SiteSemstormPlanItem)
            .where(SiteSemstormPlanItem.site_id == site_id)
            .options(
                selectinload(SiteSemstormPlanItem.promoted_item),
                selectinload(SiteSemstormPlanItem.brief_item),
            )
            .order_by(SiteSemstormPlanItem.updated_at.desc(), SiteSemstormPlanItem.id.desc())
        )
    )


def _apply_plan_filters(
    items: Sequence[SiteSemstormPlanItem],
    *,
    state_status: SemstormPlanStateStatus | None,
    target_page_type: SemstormPlanTargetPageType | None,
    search: str | None,
) -> list[SiteSemstormPlanItem]:
    search_term = _normalize_search(search)
    filtered: list[SiteSemstormPlanItem] = []
    for item in items:
        if state_status is not None and str(item.state_status) != state_status:
            continue
        if target_page_type is not None and str(item.target_page_type) != target_page_type:
            continue
        if search_term and not _plan_matches_search(item, search_term):
            continue
        filtered.append(item)
    return filtered


def _plan_matches_search(item: SiteSemstormPlanItem, search_term: str) -> bool:
    haystacks = [
        item.keyword,
        item.plan_title,
        item.proposed_primary_keyword,
        item.proposed_slug,
    ]
    return any(search_term in str(value or "").strip().lower() for value in haystacks)


def _build_plan_state_counts(items: Sequence[SiteSemstormPlanItem]) -> dict[str, int]:
    counts = {"planned": 0, "in_progress": 0, "done": 0, "archived": 0}
    for item in items:
        state_status = str(item.state_status or "planned")
        if state_status in counts:
            counts[state_status] += 1
    return counts


def _build_target_page_type_counts(items: Sequence[SiteSemstormPlanItem]) -> dict[str, int]:
    counts = {"new_page": 0, "expand_existing": 0, "refresh_existing": 0, "cluster_support": 0}
    for item in items:
        target_page_type = str(item.target_page_type or "new_page")
        if target_page_type in counts:
            counts[target_page_type] += 1
    return counts


def _get_plan_item_or_raise(session: Session, site_id: int, plan_id: int) -> SiteSemstormPlanItem:
    plan_item = session.scalar(
        select(SiteSemstormPlanItem)
        .where(
            SiteSemstormPlanItem.site_id == site_id,
            SiteSemstormPlanItem.id == plan_id,
        )
        .options(
            selectinload(SiteSemstormPlanItem.promoted_item),
            selectinload(SiteSemstormPlanItem.brief_item),
        )
    )
    if plan_item is None:
        raise SemstormPlanServiceError(
            f"Semstorm plan item {plan_id} not found.",
            code="not_found",
            status_code=404,
        )
    return plan_item


def _apply_plan_state(plan_item: SiteSemstormPlanItem, state_status: str) -> None:
    normalized_state = _normalize_state_status(state_status)
    plan_item.state_status = normalized_state
    plan_item.updated_at = utcnow()


def _default_target_page_type(promoted_item: SiteSemstormPromotedItem) -> SemstormPlanTargetPageType:
    decision_type = str(promoted_item.decision_type or "monitor_only")
    if decision_type == "create_new_page":
        return "new_page"
    if decision_type == "expand_existing_page":
        return "expand_existing"
    return "refresh_existing"


def _default_plan_title(keyword: str, target_page_type: SemstormPlanTargetPageType) -> str:
    clean_keyword = str(keyword or "").strip() or "keyword"
    if target_page_type == "new_page":
        return f"Create page for {clean_keyword}"
    if target_page_type == "expand_existing":
        return f"Expand existing page for {clean_keyword}"
    if target_page_type == "cluster_support":
        return f"Add supporting content for {clean_keyword}"
    return f"Refresh coverage for {clean_keyword}"


def _default_proposed_slug(keyword: str, target_page_type: SemstormPlanTargetPageType) -> str | None:
    if target_page_type != "new_page":
        return None
    slug = _slugify(keyword)
    return slug or None


def _slugify(value: str | None) -> str:
    normalized = semstorm_opportunity_state_service.normalize_semstorm_keyword(value or "")
    slug = _SLUG_TOKEN_RE.sub("-", normalized).strip("-")
    return slug[:512]


def _normalize_promoted_item_ids(values: Sequence[int]) -> list[int]:
    deduped: list[int] = []
    seen: set[int] = set()
    for value in values:
        item_id = int(value or 0)
        if item_id <= 0 or item_id in seen:
            continue
        seen.add(item_id)
        deduped.append(item_id)
    return deduped


def _normalize_optional_text(value: Any, *, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if max_length is not None:
        return text[:max_length]
    return text


def _normalize_secondary_keywords(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SemstormPlanServiceError(
            "proposed_secondary_keywords must be a list of strings.",
            code="invalid_secondary_keywords",
            status_code=400,
        )
    deduped: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = _normalize_optional_text(item, max_length=512)
        if normalized is None:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _normalize_state_status(value: Any) -> SemstormPlanStateStatus:
    normalized = str(value or "").strip()
    if normalized not in _PLAN_STATE_VALUES:
        raise SemstormPlanServiceError(
            f"Unsupported Semstorm plan state_status '{value}'.",
            code="invalid_state_status",
            status_code=400,
        )
    return normalized  # type: ignore[return-value]


def _normalize_target_page_type(value: Any) -> SemstormPlanTargetPageType:
    normalized = str(value or "").strip()
    if normalized not in _PLAN_TARGET_PAGE_TYPE_VALUES:
        raise SemstormPlanServiceError(
            f"Unsupported Semstorm target_page_type '{value}'.",
            code="invalid_target_page_type",
            status_code=400,
        )
    return normalized  # type: ignore[return-value]


def _normalize_search(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    return normalized.lower()

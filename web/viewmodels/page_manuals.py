from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .page_manuals_common import (
    SHARED_FRAGMENTS,
    _clean_related_ids,
    build_manual_payload_from_topic,
    build_page_fallback_text_from_bundle,
)
from .page_manuals_equipment import EQUIPMENT_TOPICS
from .page_manuals_excel_demo import EXCEL_DEMO_TOPICS
from .page_manuals_material import MATERIAL_TOPICS
from .page_manuals_personnel import PERSONNEL_TOPICS
from .page_manuals_process import PROCESS_TOPICS
from .page_manuals_registry import ENDPOINT_OVERRIDES, ENDPOINT_TO_MANUAL_ID, MANUAL_ENTRY_ENDPOINTS
from .page_manuals_reports import REPORTS_TOPICS
from .page_manuals_scheduler import SCHEDULER_TOPICS
from .page_manuals_system import SYSTEM_TOPICS

MANUAL_TOPICS: Dict[str, Dict[str, Any]] = {}
for topic_group in (
    EXCEL_DEMO_TOPICS,
    PERSONNEL_TOPICS,
    EQUIPMENT_TOPICS,
    PROCESS_TOPICS,
    SCHEDULER_TOPICS,
    MATERIAL_TOPICS,
    REPORTS_TOPICS,
    SYSTEM_TOPICS,
):
    MANUAL_TOPICS.update(topic_group)


def resolve_manual_id(endpoint: Optional[str]) -> Optional[str]:
    key = str(endpoint or "").strip()
    if not key:
        return None
    return ENDPOINT_TO_MANUAL_ID.get(key)


def build_manual_payload(
    manual_id: str,
    overrides: Optional[Mapping[str, Any]] = None,
    include_sections: bool = True,
) -> Optional[Dict[str, Any]]:
    key = str(manual_id or "").strip()
    topic = MANUAL_TOPICS.get(key)
    if not topic:
        return None
    return build_manual_payload_from_topic(
        key,
        topic,
        overrides=overrides,
        include_sections=include_sections,
    )


def build_manual_for_endpoint(endpoint: Optional[str], include_sections: bool = True) -> Optional[Dict[str, Any]]:
    key = str(endpoint or "").strip()
    manual_id = resolve_manual_id(key)
    if not manual_id:
        return None
    payload = build_manual_payload(manual_id, overrides=ENDPOINT_OVERRIDES.get(key), include_sections=include_sections)
    if not payload:
        return None
    payload["endpoint"] = key
    return payload


def get_related_manual_ids(manual_id: Optional[str]) -> List[str]:
    topic = MANUAL_TOPICS.get(str(manual_id or "").strip())
    if not topic:
        return []
    return _clean_related_ids(list(topic.get("related_manual_ids") or []))


def build_related_manuals(manual_id: Optional[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for related_id in get_related_manual_ids(manual_id):
        related = build_manual_payload(related_id, include_sections=True)
        if related:
            related["preview_sections"] = list(related.get("sections") or [])[:2]
            related.pop("sections", None)
            out.append(related)
    return out


def build_page_manual_bundle(endpoint: Optional[str]) -> Optional[Dict[str, Any]]:
    current_manual = build_manual_for_endpoint(endpoint, include_sections=True)
    if not current_manual:
        return None
    return {
        "current_manual": current_manual,
        "related_manuals": build_related_manuals(current_manual.get("manual_id")),
    }


def build_page_fallback_text(endpoint: Optional[str], bundle: Optional[Dict[str, Any]] = None) -> str:
    if bundle is None:
        bundle = build_page_manual_bundle(endpoint)
    return build_page_fallback_text_from_bundle(bundle)

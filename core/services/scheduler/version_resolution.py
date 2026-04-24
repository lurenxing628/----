from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError

VERSION_ERROR_MESSAGE = "版本参数不合法，请填写正整数版本号，或使用 latest 表示最新版本。"


@dataclass(frozen=True)
class VersionResolution:
    has_history: bool
    selected_version: Optional[int]
    requested_version: Optional[int]
    status: str
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_history": bool(self.has_history),
            "selected_version": self.selected_version,
            "requested_version": self.requested_version,
            "status": self.status,
            "source": self.source,
        }


def _parse_explicit_version(value: Any, *, field: str) -> int:
    try:
        version = int(str(value).strip())
    except Exception as exc:
        raise ValidationError(VERSION_ERROR_MESSAGE, field=field) from exc
    if version <= 0:
        raise ValidationError(VERSION_ERROR_MESSAGE, field=field)
    return int(version)


def resolve_version_or_latest(
    value: Any,
    *,
    latest_version: int,
    version_exists: Optional[Callable[[int], bool]] = None,
    field: str = "version",
) -> VersionResolution:
    latest = int(latest_version or 0)
    raw_missing = value is None or str(value).strip() == ""
    raw_text = "" if raw_missing else str(value).strip()
    is_latest = raw_text.lower() == "latest"

    if raw_missing or is_latest:
        source = "default" if raw_missing else "latest"
        if latest <= 0:
            return VersionResolution(
                has_history=False,
                selected_version=None,
                requested_version=None,
                status="no_history",
                source=source,
            )
        return VersionResolution(
            has_history=True,
            selected_version=latest,
            requested_version=None,
            status="ok",
            source=source,
        )

    requested = _parse_explicit_version(raw_text, field=field)
    exists = bool(version_exists(requested)) if version_exists is not None else latest > 0
    if not exists:
        return VersionResolution(
            has_history=latest > 0,
            selected_version=None,
            requested_version=requested,
            status="missing_history",
            source="explicit",
        )
    return VersionResolution(
        has_history=True,
        selected_version=requested,
        requested_version=requested,
        status="ok",
        source="explicit",
    )


def require_selected_version(resolution: VersionResolution, *, message: str = "排产版本不存在，请先选择已有版本。") -> int:
    if resolution.selected_version is not None:
        return int(resolution.selected_version)
    raise BusinessError(
        ErrorCode.NOT_FOUND,
        message,
        details={
            "field": "version",
            "requested_version": resolution.requested_version,
            "status": resolution.status,
        },
    )

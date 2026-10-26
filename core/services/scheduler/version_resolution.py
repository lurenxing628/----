from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from core.errors import ValidationError

VERSION_ERROR_MESSAGE = "版本号不对。请填写大于 0 的数字版本号；如果想看最新版本，可以不填版本。"


@dataclass(frozen=True)
class VersionResolution:
    selected_version: Optional[int]


def _parse_explicit_version(value: str) -> int:
    try:
        version = int(value)
    except Exception as exc:
        raise ValidationError(VERSION_ERROR_MESSAGE, field="version") from exc
    if version <= 0:
        raise ValidationError(VERSION_ERROR_MESSAGE, field="version")
    return version


def resolve_version_or_latest(
    value: Any,
    *,
    latest_version: int,
    version_exists: Callable[[int], bool],
) -> VersionResolution:
    latest = latest_version
    raw_text = "" if value is None else str(value).strip()
    if not raw_text or raw_text.lower() == "latest":
        return VersionResolution(selected_version=latest if latest > 0 else None)

    requested = _parse_explicit_version(raw_text)
    return VersionResolution(selected_version=requested if version_exists(requested) else None)

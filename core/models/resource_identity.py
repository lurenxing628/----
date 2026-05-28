from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


def _text(value: Any) -> str:
    return str(value or "").strip()


def _clean_repeated_id_prefix(rid: str, name: str) -> str:
    if not rid or not name or not name.startswith(rid):
        return name
    remainder = name[len(rid) :]
    if remainder and remainder[0].isspace():
        return remainder.strip()
    return name


@dataclass(frozen=True)
class ResourceIdentity:
    id: str = ""
    name: str = ""
    display_label: str = ""
    identity_label: str = ""
    label: str = ""

    def to_dict(self, prefix: str = "") -> Dict[str, str]:
        return {
            f"{prefix}id": self.id,
            f"{prefix}name": self.name,
            f"{prefix}display_label": self.display_label,
            f"{prefix}identity_label": self.identity_label,
            f"{prefix}label": self.label,
        }


def build_resource_identity(
    resource_id: Any = None,
    resource_name: Any = None,
    *,
    display_label: Any = None,
    identity_label: Any = None,
) -> ResourceIdentity:
    rid = _text(resource_id)
    name = _clean_repeated_id_prefix(rid, _text(resource_name))
    display = _text(display_label) or name or rid
    identity = _text(identity_label)
    if not identity:
        if rid and name and name != rid:
            identity = f"{rid} {name}"
        else:
            identity = display
    label = identity
    return ResourceIdentity(
        id=rid,
        name=name,
        display_label=display,
        identity_label=identity,
        label=label,
    )


__all__ = ["ResourceIdentity", "build_resource_identity"]

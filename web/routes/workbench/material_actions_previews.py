"""Original material previews and bytes, separate from opaque token bindings.

Entries share the existing short-token expiry. There is no new row/file/count
limit here; upload limits and the 2000-row import contract remain authoritative.
Expired entries are reclaimed on access. App restart loses unconfirmed previews,
never the committed command receipts. The single-process host is threaded.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock
from typing import Dict, Optional, Tuple

from flask import current_app

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_material_file import MaterialPreview

_EXTENSION = "workbench_material_previews_v1"
_LOCK = RLock()


@dataclass(frozen=True)
class _RetainedPreview:
    preview: MaterialPreview
    content: Optional[bytes]
    expires_at: float


def _live_store() -> Dict[str, _RetainedPreview]:
    store = current_app.extensions.setdefault(_EXTENSION, {})
    now = time.time()
    for key in list(store):
        if store[key].expires_at <= now:
            del store[key]
    return store


def retain_preview(preview: MaterialPreview, content: Optional[bytes], expires_at: float) -> None:
    with _LOCK:
        store = _live_store()
        key = preview.digest
        previous = store.get(key)
        if previous is not None:
            if previous.preview != preview or previous.content != content:
                raise RuntimeError("物料预览引用对应了不同内容，未替换原预览。")
            expires_at = max(expires_at, previous.expires_at)
        store[key] = _RetainedPreview(preview, content, expires_at)


def stored_preview(key: str) -> Tuple[MaterialPreview, Optional[bytes]]:
    with _LOCK:
        entry = _live_store().get(key)
        if entry is None:
            raise WorkbenchCommandRejected("stale_write", "原始物料预览已失效，请重新预检；未使用浏览器内容重建。")
        return entry.preview, entry.content

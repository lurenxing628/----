"""Bounded discovery of existing trial identities, independent of browser state."""

from dataclasses import dataclass
from typing import Optional

from core.models.workbench_trial import reference, reject

MAX_CATALOG_ROWS = 100000
MAX_CATALOG_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class TrialCatalogScope:
    collection: str
    status: str = "all"
    base_kind: Optional[str] = None
    base_ref: Optional[str] = None
    page: int = 1
    size: int = 20

    def __post_init__(self):
        if self.collection not in ("drafts", "scenarios"):
            reject("invalid_input", "试调目录类型无效。", 400)
        allowed = ("all", "editing", "saved", "discarded") if self.collection == "drafts" else ("all", "saved")
        if self.status not in allowed:
            reject("invalid_input", "目录状态筛选无效，未忽略条件。", 400)
        if type(self.page) is not int or not 1 <= self.page <= MAX_CATALOG_ROWS:
            reject("invalid_input", "目录页码必须为1至100000的整数。", 400)
        if type(self.size) is not int or not 1 <= self.size <= 50:
            reject("invalid_input", "目录每页数量必须为1至50的整数。", 400)
        if (self.base_kind is None) != (self.base_ref is None):
            reject("invalid_input", "筛选基础方案时必须同时提供来源类型和永久引用。", 400)
        if self.base_kind is not None:
            if self.base_kind not in ("plan_ref", "candidate_ref"):
                reject("invalid_input", "基础来源类型必须为plan_ref或candidate_ref。", 400)
            reference(self.base_ref)

    def scope(self):
        return {"source": "production", "kind": "trial_catalog", "collection": self.collection,
                "status": self.status, "base_kind": self.base_kind, "base_ref": self.base_ref, "size": self.size}

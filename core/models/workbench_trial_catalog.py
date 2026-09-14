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
            reject("invalid_input", "试调列表类型无效。", 400)
        allowed = ("all", "editing", "saved", "discarded") if self.collection == "drafts" else ("all", "saved")
        if self.status not in allowed:
            reject("invalid_input", "列表的状态筛选不对，请重新选择。", 400)
        if type(self.page) is not int or not 1 <= self.page <= MAX_CATALOG_ROWS:
            reject("invalid_input", "页码必须是 1 至 100000 的整数。", 400)
        if type(self.size) is not int or not 1 <= self.size <= 50:
            reject("invalid_input", "每页条数必须是 1 至 50 的整数。", 400)
        if (self.base_kind is None) != (self.base_ref is None):
            reject("invalid_input", "按来源筛选时，来源类型和来源编号要一起选。", 400)
        if self.base_kind is not None:
            if self.base_kind not in ("plan_ref", "candidate_ref"):
                reject("invalid_input", "基础来源类型必须为plan_ref或candidate_ref。", 400)
            reference(self.base_ref)

    def scope(self):
        return {"source": "production", "kind": "trial_catalog", "collection": self.collection,
                "status": self.status, "base_kind": self.base_kind, "base_ref": self.base_ref, "size": self.size}

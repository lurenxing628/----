"""Inputs and evidence for adopting one real D05 template recommendation."""

from dataclasses import dataclass
from typing import Any, Dict

from core.models.workbench_command import WorkbenchCommandRejected

ADOPT_ACTION = "calibration.adopt"
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024


def preview_input(value):
    if type(value) is not dict or set(value) != {"reason", "declared_operator"}:
        raise WorkbenchCommandRejected("invalid_input", "预览须提供原因和声明人；建议值、样本及本机操作者由服务读取。", 400)
    result = {}
    for key, limit in (("reason", 2000), ("declared_operator", 100)):
        text = value[key]
        if type(text) is not str or not text.strip() or len(text) > limit or "\x00" in text:
            raise WorkbenchCommandRejected("invalid_input", "请填写有效的采纳原因和声明人；原因最多2000字，声明人最多100字，不能含空字符。", 422)
        result[key] = text.strip()
    return result


def adoption_input(value):
    if type(value) is not dict or set(value) != {"reason", "declared_operator", "confirm"}:
        raise WorkbenchCommandRejected("invalid_input", "采纳须提供确认、原因和声明人，不能缺失或夹带其他字段。", 400)
    if value["confirm"] is not True:
        raise WorkbenchCommandRejected("confirmation_required", "请复核预览并明确确认采纳。", 422)
    return {**preview_input({key: value[key] for key in ("reason", "declared_operator")}), "confirm": True}


@dataclass(frozen=True)
class CalibrationAdoptionEvidence:
    template: Dict[str, Any]
    suggestion: Dict[str, Any]
    samples: list
    snapshot: Dict[str, Any]
    generated_at: str
    blockers: list

    def require_adoptable(self):
        if self.blockers:
            first = self.blockers[0]
            raise WorkbenchCommandRejected(first["code"], first["message"])


def closed_context(reasons):
    return {"write_token": None, "expires_at": None, "capabilities": {ADOPT_ACTION: False}, "blocked_reasons": reasons}

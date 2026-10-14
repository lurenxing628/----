from __future__ import annotations

from typing import Any, Optional

from core.errors import ValidationError
from core.models.content import content_text

from .actual_records import TaskPlan


def idempotency_key(import_token: Optional[str], task_code: Any, action: str, row_number: int) -> str:
    """Real task identity, submission origin and event slot; no payload copies."""
    return "resource-dispatch-actual-v2:" + content_text({
        "submission": import_token or "manual", "task": task_code, "event": action, "row": row_number})


def manual_plan_token(plan: TaskPlan) -> str:
    """The original state revision identifies the first event of a submission."""
    revision = plan.task.expected_state_revision
    if type(revision) is not str or not revision:
        raise ValidationError("缺少原现场状态版本，请刷新任务后再提交。", field="state_revision")
    return "manual:" + revision

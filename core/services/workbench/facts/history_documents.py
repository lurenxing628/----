"""ScheduleHistory 的四份 JSON 文档：在线计划头行和捕获归档行共用的唯一解码与准入。

写侧只有正式计划落库一处（``plan/official_persistence.py``，经 ``canonical_json``）。每份文档在第一次
被读到时解码并准入一次，之后复用；读者用不到的文档不解码——工时账随工序数增长（上万道工序时有数 MB），
看板和交付只读延后清单，计划来源只读算法摘要。同一读作用域里几个读者共读的在线版本经
``PlanReadContext.history_documents(version)`` 共用同一个对象；只有一个读者的行由它直接构造。
"""

from functools import cached_property
from typing import Any, Dict, FrozenSet, Mapping, NoReturn, Optional

from core.models.content import StoredJsonCorrupt, read_stored_json
from core.shared.strict_parse import is_exact_positive_int

from .operation_effort_evidence import saved_operation_efforts


def _corrupt() -> NoReturn:
    raise StoredJsonCorrupt()


class HistoryDocuments:
    def __init__(self, row: Mapping[str, Any]) -> None:
        self._row = row

    @cached_property
    def deferred_operation_ids(self) -> FrozenSet[int]:
        """这一版因等料延后、没有排进计划的工序 id。"""
        ids = read_stored_json(self._row["deferred_operation_ids_json"], list)
        if not all(is_exact_positive_int(op_id) for op_id in ids):
            _corrupt()
        return frozenset(ids)

    @cached_property
    def operation_effort(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """这一版的实际需求账，按工序永久编号取已准入的条目；来源没有需求账时存 NULL，读出 None。

        条目损坏与文档读不出是同一种存储损坏。
        """
        raw = self._row["operation_effort_json"]
        return None if raw is None else saved_operation_efforts(read_stored_json(raw, dict), on_corrupt=_corrupt)

    @cached_property
    def material_policy(self) -> Dict[str, Any]:
        return read_stored_json(self._row["material_policy_json"], dict)

    @cached_property
    def algorithm(self) -> Optional[Dict[str, Any]]:
        """候选采用时的算法摘要；试调采用没有算法，存 NULL，读出 None。"""
        raw = self._row["algorithm_json"]
        return None if raw is None else read_stored_json(raw, dict)

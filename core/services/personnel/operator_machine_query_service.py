from __future__ import annotations

from typing import Any, Dict, List, Sequence

from core.models.enums import YesNo
from core.services.common.enum_normalizers import normalize_skill_level, normalize_yes_no_wide
from data.repositories import OperatorMachineRepository


class OperatorMachineQueryService:
    """
    人员-设备关联查询服务（只读 façade）。

    目的：
    - 让 Route 层避免直接依赖 Repository
    - 不引入/改变写入语义（写入仍由 OperatorMachineService 负责）
    """

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.repo = OperatorMachineRepository(conn, logger=logger)

    @staticmethod
    def _normalize_row(r: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(r or {})
        dirty_fields: List[str] = []
        dirty_reasons: Dict[str, str] = {}

        def _mark_dirty(field: str, reason: str) -> None:
            field_name = str(field or "").strip()
            message = str(reason or "").strip()
            if not field_name or not message:
                return
            if field_name not in dirty_fields:
                dirty_fields.append(field_name)
            dirty_reasons[field_name] = message

        if "skill_level" in out:
            raw_skill = out.get("skill_level")
            raw_skill_text = "" if raw_skill is None else str(raw_skill).strip()
            try:
                out["skill_level"] = normalize_skill_level(out.get("skill_level"), default="normal", allow_none=False)
            except ValueError:
                out["skill_level"] = "normal"
                if raw_skill is None or raw_skill_text == "":
                    _mark_dirty("skill_level", "历史技能等级为空，已兼容归一为 normal。")
                else:
                    _mark_dirty("skill_level", f"历史技能等级 {raw_skill_text!r} 无效，已兼容归一为 normal。")
            else:
                if raw_skill is None or raw_skill_text == "":
                    _mark_dirty("skill_level", "历史技能等级为空，已兼容归一为 normal。")
                elif raw_skill_text.lower() != str(out.get("skill_level") or "").strip().lower():
                    _mark_dirty("skill_level", f"历史技能等级 {raw_skill_text!r} 已兼容归一为 {out.get('skill_level')}。")
        if "is_primary" in out:
            raw_primary = out.get("is_primary")
            raw_primary_text = "" if raw_primary is None else str(raw_primary).strip()
            out["is_primary"] = normalize_yes_no_wide(out.get("is_primary"), default=YesNo.NO.value, unknown_policy="no")
            if raw_primary is None or raw_primary_text == "":
                _mark_dirty("is_primary", "历史主操标记为空，已兼容归一为 no。")
            elif raw_primary_text.lower() != str(out.get("is_primary") or "").strip().lower():
                _mark_dirty("is_primary", f"历史主操标记 {raw_primary_text!r} 已兼容归一为 {out.get('is_primary')}。")
        if dirty_fields:
            out["dirty_fields"] = list(dirty_fields)
            out["dirty_reasons"] = dict(dirty_reasons)
        return out

    @classmethod
    def _normalize_rows(cls, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [cls._normalize_row(r) for r in (rows or [])]

    def list_simple_rows(self) -> List[Dict[str, Any]]:
        return self._normalize_rows(self.repo.list_simple_rows())

    def list_with_names_by_machine(self) -> List[Dict[str, Any]]:
        return self._normalize_rows(self.repo.list_with_names_by_machine())

    def list_with_names_by_operator(self) -> List[Dict[str, Any]]:
        return self._normalize_rows(self.repo.list_with_names_by_operator())

    def list_links_with_operator_info(self) -> List[Dict[str, Any]]:
        return self._normalize_rows(self.repo.list_links_with_operator_info())

    def list_simple_rows_for_machine_operator_sets(
        self,
        machine_ids: Sequence[str],
        operator_ids: Sequence[str],
    ) -> List[Dict[str, Any]]:
        return self._normalize_rows(self.repo.list_simple_rows_for_machine_operator_sets(machine_ids, operator_ids))


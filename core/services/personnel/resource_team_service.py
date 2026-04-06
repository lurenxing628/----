from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models import ResourceTeam
from core.models.enums import RESOURCE_TEAM_STATUS_VALUES, ResourceTeamStatus
from core.services.common.normalize import normalize_text
from data.repositories import ResourceTeamRepository


class ResourceTeamService:
    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.repo = ResourceTeamRepository(conn, logger=logger)

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    def _validate_fields(
        self,
        team_id: Any,
        name: Any,
        status: Any,
        allow_partial: bool = False,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        tid = self._normalize_text(team_id)
        tname = self._normalize_text(name)
        tstatus = self._normalize_text(status)
        if tstatus is not None:
            tstatus = tstatus.lower()

        if not allow_partial:
            if not tid:
                raise ValidationError("班组ID不能为空", field="班组ID")
            if not tname:
                raise ValidationError("班组名称不能为空", field="班组名称")
            if not tstatus:
                tstatus = ResourceTeamStatus.ACTIVE.value

        if tstatus is not None and tstatus not in RESOURCE_TEAM_STATUS_VALUES:
            raise ValidationError("状态不正确，请选择：启用 / 停用。", field="状态")

        return tid, tname, tstatus

    def _get_or_raise(self, team_id: str) -> ResourceTeam:
        team = self.repo.get(team_id)
        if not team:
            raise BusinessError(ErrorCode.TEAM_NOT_FOUND, f"班组{team_id}不存在")
        return team

    def list(self, status: Optional[str] = None) -> List[ResourceTeam]:
        filter_status = None
        if status:
            _, _, filter_status = self._validate_fields(None, None, status, allow_partial=True)
            if filter_status is None:
                raise ValidationError("缺少状态参数", field="状态")
        return self.repo.list(status=filter_status)

    def list_with_counts(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        filter_status = None
        if status:
            _, _, filter_status = self._validate_fields(None, None, status, allow_partial=True)
            if filter_status is None:
                raise ValidationError("缺少状态参数", field="状态")
        return self.repo.list_with_counts(status=filter_status)

    def list_options(self, status: Optional[str] = ResourceTeamStatus.ACTIVE.value) -> List[Dict[str, Any]]:
        return [team.to_dict() for team in self.list(status=status)]

    def get(self, team_id: str) -> ResourceTeam:
        tid, _, _ = self._validate_fields(team_id, None, None, allow_partial=True)
        if not tid:
            raise ValidationError("班组ID不能为空", field="班组ID")
        return self._get_or_raise(tid)

    def get_optional(self, team_id: Any) -> Optional[ResourceTeam]:
        tid, _, _ = self._validate_fields(team_id, None, None, allow_partial=True)
        if not tid:
            return None
        return self.repo.get(tid)

    def get_by_name_optional(self, name: Any) -> Optional[ResourceTeam]:
        tname = self._normalize_text(name)
        if not tname:
            return None
        return self.repo.get_by_name(tname)

    def resolve_team_id_optional(self, value: Any) -> Optional[str]:
        v = self._normalize_text(value)
        if not v:
            return None
        team = self.get_optional(v)
        if not team:
            team = self.get_by_name_optional(v)
        if not team:
            raise ValidationError(f"班组{v}不存在，请先在人员管理-班组管理中维护。", field="班组")
        return team.team_id

    def resolve_team_name_optional(self, value: Any) -> Optional[str]:
        team_id = self.resolve_team_id_optional(value)
        if not team_id:
            return None
        team = self.get_optional(team_id)
        return team.name if team else None

    def get_usage_counts(self, team_id: Any) -> Dict[str, int]:
        tid, _, _ = self._validate_fields(team_id, None, None, allow_partial=True)
        if not tid:
            raise ValidationError("班组ID不能为空", field="班组ID")
        return {
            "operator_count": self.repo.count_operator_refs(tid),
            "machine_count": self.repo.count_machine_refs(tid),
        }

    def create(
        self,
        team_id: Any,
        name: Any,
        status: Any = ResourceTeamStatus.ACTIVE.value,
        remark: Any = None,
    ) -> ResourceTeam:
        tid, tname, tstatus = self._validate_fields(team_id, name, status)
        tremark = self._normalize_text(remark)

        if self.repo.exists(tid):
            raise BusinessError(ErrorCode.TEAM_ALREADY_EXISTS, f"班组ID{tid}已存在，不能重复添加。")
        existing = self.repo.get_by_name(tname)
        if existing:
            raise BusinessError(ErrorCode.TEAM_ALREADY_EXISTS, f"班组名称{tname}已存在，不能重复添加。")

        with self.tx_manager.transaction():
            self.repo.create(
                {
                    "team_id": tid,
                    "name": tname,
                    "status": tstatus or ResourceTeamStatus.ACTIVE.value,
                    "remark": tremark,
                }
            )
        return self._get_or_raise(tid)

    def update(
        self,
        team_id: Any,
        name: Any = None,
        status: Any = None,
        remark: Any = None,
    ) -> ResourceTeam:
        tid, tname, tstatus = self._validate_fields(team_id, name, status, allow_partial=True)
        if not tid:
            raise ValidationError("班组ID不能为空", field="班组ID")
        self._get_or_raise(tid)

        updates: Dict[str, Any] = {}
        if tname is not None:
            if not tname:
                raise ValidationError("班组名称不能为空", field="班组名称")
            existing = self.repo.get_by_name(tname)
            if existing and existing.team_id != tid:
                raise BusinessError(ErrorCode.TEAM_ALREADY_EXISTS, f"班组名称{tname}已存在，不能重复。")
            updates["name"] = tname
        if status is not None:
            updates["status"] = tstatus
        if remark is not None:
            updates["remark"] = self._normalize_text(remark)

        with self.tx_manager.transaction():
            self.repo.update(tid, updates)
        return self._get_or_raise(tid)

    def delete(self, team_id: Any) -> None:
        tid, _, _ = self._validate_fields(team_id, None, None, allow_partial=True)
        if not tid:
            raise ValidationError("班组ID不能为空", field="班组ID")
        self._get_or_raise(tid)

        counts = self.get_usage_counts(tid)
        operator_count = int(counts.get("operator_count", 0) or 0)
        machine_count = int(counts.get("machine_count", 0) or 0)
        if operator_count > 0 or machine_count > 0:
            raise BusinessError(
                ErrorCode.TEAM_IN_USE,
                f"该班组仍被引用：人员 {operator_count} 个，设备 {machine_count} 台，不能删除。",
            )

        with self.tx_manager.transaction():
            self.repo.delete(tid)

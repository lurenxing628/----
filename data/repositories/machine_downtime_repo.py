from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from core.models import MachineDowntime

from .base_repo import BaseRepository
from .schedule_time_sql import overlap_or_bad_time_sql, require_dt_for_sql, time_dt


class MachineDowntimeRepository(BaseRepository):
    """设备停机时间段仓库（MachineDowntimes）。"""

    def get(self, downtime_id: int) -> Optional[MachineDowntime]:
        row = self.fetchone(
            """
            SELECT id, machine_id, scope_type, scope_value, start_time, end_time, reason_code, reason_detail,
                   status, created_at, updated_at
            FROM MachineDowntimes
            WHERE id = ?
            """,
            (int(downtime_id),),
        )
        return MachineDowntime.from_row(row) if row else None

    def list_by_machine(self, machine_id: str, include_cancelled: bool = False) -> List[MachineDowntime]:
        sql = """
            SELECT id, machine_id, scope_type, scope_value, start_time, end_time, reason_code, reason_detail,
                   status, created_at, updated_at
            FROM MachineDowntimes
            WHERE machine_id = ?
        """
        params: List[Any] = [machine_id]
        if not include_cancelled:
            sql += " AND status = 'active'"
        sql += " ORDER BY start_time DESC, id DESC"
        rows = self.fetchall(sql, tuple(params))
        return [MachineDowntime.from_row(r) for r in rows]

    def list_active_after(self, machine_id: str, start_time: str) -> List[MachineDowntime]:
        """
        列出某设备在 start_time 之后仍可能影响排产的有效停机区间（end_time > start_time）。

        口径：坏时间行经 aps_parse_dt 解析为 NULL、比较为假后**有意从结果剔除**，不做坏行兜底。
        本方法供排产资源占用/延误诊断当“约束区间”用，坏行没有可比较边界，纳入会污染判定；
        与 list_active_overlaps_with_machine_names（明细展示，兜底坏行做降级提示）口径相反但各有其所。
        写入层（MachineDowntimeService.create/create_by_scope）已强制归一，坏行仅可能来自外部直写/导入。
        """
        parsed_start_time = require_dt_for_sql(start_time, "停机查询开始时间写法不对，无法读取停机线索")
        rows = self.fetchall(
            f"""
            SELECT id, machine_id, scope_type, scope_value, start_time, end_time, reason_code, reason_detail,
                   status, created_at, updated_at
            FROM MachineDowntimes
            WHERE machine_id = ?
              AND status = 'active'
              AND {time_dt(None, "end_time")} > ?
            ORDER BY start_time ASC, id ASC
            """,
            (machine_id, parsed_start_time),
        )
        return [MachineDowntime.from_row(r) for r in rows]

    def list_active_overlaps_with_machine_names(self, start_time: str, end_time: str) -> List[Dict[str, Any]]:
        parsed_start_time = require_dt_for_sql(start_time, "停机重叠查询时间写法不对，无法读取停机线索")
        parsed_end_time = require_dt_for_sql(end_time, "停机重叠查询时间写法不对，无法读取停机线索")
        rows = self.fetchall(
            f"""
            SELECT md.machine_id, m.name AS machine_name, md.start_time, md.end_time, md.reason_code, md.reason_detail
            FROM MachineDowntimes md
            LEFT JOIN Machines m ON m.machine_id = md.machine_id
            WHERE md.status = 'active'
              AND {overlap_or_bad_time_sql("md")}
            ORDER BY md.machine_id, md.start_time, md.id
            """,
            (parsed_end_time, parsed_start_time),
        )
        return [dict(row) for row in rows]

    def has_overlap(
        self,
        machine_id: str,
        start_time: str,
        end_time: str,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """
        判断是否与已有“有效(active)”停机区间重叠。
        重叠条件：NOT(end<=existing_start OR start>=existing_end)

        口径：坏时间行经 aps_parse_dt 解析为 NULL、比较为假后**有意不计入重叠**，不做坏行兜底。
        本方法是“冲突/blocker”判定（创建停机查重、甘特调整 machine_downtime blocker），
        坏行对任意窗口都满足兜底条件，若计入会误报封锁任何新停机/调整；故与
        list_active_overlaps_with_machine_names 的明细兜底口径相反。
        """
        parsed_start_time = require_dt_for_sql(start_time, "停机重叠检查开始时间写法不对，无法判断停机冲突")
        parsed_end_time = require_dt_for_sql(end_time, "停机重叠检查结束时间写法不对，无法判断停机冲突")
        sql = f"""
            SELECT 1
            FROM MachineDowntimes
            WHERE machine_id = ?
              AND status = 'active'
              AND {time_dt(None, "end_time")} > ?
              AND {time_dt(None, "start_time")} < ?
        """
        params: List[Any] = [machine_id, parsed_start_time, parsed_end_time]
        if exclude_id is not None:
            sql += " AND id <> ?"
            params.append(int(exclude_id))
        sql += " LIMIT 1"
        return bool(self.fetchvalue(sql, tuple(params)))

    def list_active_machine_ids_at(self, now_str: str) -> Set[str]:
        """返回此刻处于有效停机的设备集合（可用性判定）。

        口径：坏时间行解析为 NULL、比较为假后**有意排除**，不做坏行兜底。坏行对任意 now 恒满足
        兜底条件，若计入会把该设备永久误标为停机不可用；故与明细查询的坏行兜底口径相反。
        """
        parsed_now = require_dt_for_sql(now_str, "停机状态查询时间写法不对，无法读取停机状态")
        rows = self.fetchall(
            f"""
            SELECT DISTINCT machine_id
            FROM MachineDowntimes
            WHERE status='active'
              AND {time_dt(None, "start_time")} <= ?
              AND {time_dt(None, "end_time")} > ?
            """,
            (parsed_now, parsed_now),
        )
        out: Set[str] = set()
        for r in rows:
            mid = str((r or {}).get("machine_id") or "").strip()
            if mid:
                out.add(mid)
        return out

    def create(self, payload: Dict[str, Any]) -> MachineDowntime:
        d = payload if isinstance(payload, MachineDowntime) else MachineDowntime.from_row(payload)
        cur = self.execute(
            """
            INSERT INTO MachineDowntimes
            (machine_id, scope_type, scope_value, start_time, end_time, reason_code, reason_detail, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d.machine_id,
                d.scope_type,
                d.scope_value,
                d.start_time,
                d.end_time,
                d.reason_code,
                d.reason_detail,
                d.status or "active",
            ),
        )
        lastrowid = getattr(cur, "lastrowid", None)
        d.id = int(lastrowid) if lastrowid is not None else None
        return d

    def update(self, downtime_id: int, updates: Dict[str, Any]) -> None:
        if not updates:
            return
        allowed = {"start_time", "end_time", "reason_code", "reason_detail", "status"}
        set_parts: List[str] = []
        params: List[Any] = []
        for key in ("start_time", "end_time", "reason_code", "reason_detail", "status"):
            if key in updates and key in allowed:
                set_parts.append(f"{key} = ?")
                params.append(updates.get(key))
        if not set_parts:
            return
        set_parts.append("updated_at = CURRENT_TIMESTAMP")
        params.append(int(downtime_id))
        sql = f"UPDATE MachineDowntimes SET {', '.join(set_parts)} WHERE id = ?"
        self.execute(sql, tuple(params))

    def cancel(self, downtime_id: int) -> None:
        self.execute(
            "UPDATE MachineDowntimes SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(downtime_id),),
        )

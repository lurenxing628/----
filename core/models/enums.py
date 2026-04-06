from __future__ import annotations

from enum import Enum


class YesNo(str, Enum):
    YES = "yes"
    NO = "no"


class OperatorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MachineStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTAIN = "maintain"


class ResourceTeamStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MaterialStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class SourceType(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class BatchStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BatchOperationStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class BatchPriority(str, Enum):
    NORMAL = "normal"
    URGENT = "urgent"
    CRITICAL = "critical"


class ReadyStatus(str, Enum):
    YES = "yes"
    NO = "no"
    PARTIAL = "partial"


class CalendarDayType(str, Enum):
    WORKDAY = "workday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


class MergeMode(str, Enum):
    SEPARATE = "separate"
    MERGED = "merged"


class PartOperationStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"


class MachineDowntimeStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class LockStatus(str, Enum):
    UNLOCKED = "unlocked"
    LOCKED = "locked"


class DowntimeScopeType(str, Enum):
    MACHINE = "machine"
    CATEGORY = "category"
    ALL = "all"


class SkillLevel(str, Enum):
    BEGINNER = "beginner"
    NORMAL = "normal"
    # 历史兼容别名：新写入与对外展示均不再使用该值。
    SKILLED = "skilled"
    EXPERT = "expert"


# ============================================================
# Allowed enum value tuples (DRY, anti-drift)
# ============================================================

YESNO_VALUES = tuple(m.value for m in YesNo)

OPERATOR_STATUS_VALUES = tuple(m.value for m in OperatorStatus)
MACHINE_STATUS_VALUES = tuple(m.value for m in MachineStatus)
RESOURCE_TEAM_STATUS_VALUES = tuple(m.value for m in ResourceTeamStatus)

SUPPLIER_STATUS_VALUES = tuple(m.value for m in SupplierStatus)
MATERIAL_STATUS_VALUES = tuple(m.value for m in MaterialStatus)
SOURCE_TYPE_VALUES = tuple(m.value for m in SourceType)

BATCH_STATUS_VALUES = tuple(m.value for m in BatchStatus)
BATCH_OPERATION_STATUS_VALUES = tuple(m.value for m in BatchOperationStatus)
BATCH_PRIORITY_VALUES = tuple(m.value for m in BatchPriority)
READY_STATUS_VALUES = tuple(m.value for m in ReadyStatus)

CALENDAR_DAY_TYPE_VALUES = tuple(m.value for m in CalendarDayType)
# 存储口径：CalendarAdmin/导入落库层统一将 weekend 归一为 holiday，因此落库值域只需 workday/holiday
CALENDAR_DAY_TYPE_STORED_VALUES = (CalendarDayType.WORKDAY.value, CalendarDayType.HOLIDAY.value)
MERGE_MODE_VALUES = tuple(m.value for m in MergeMode)

PART_OPERATION_STATUS_VALUES = tuple(m.value for m in PartOperationStatus)
MACHINE_DOWNTIME_STATUS_VALUES = tuple(m.value for m in MachineDowntimeStatus)

LOCK_STATUS_VALUES = tuple(m.value for m in LockStatus)
DOWNTIME_SCOPE_TYPE_VALUES = tuple(m.value for m in DowntimeScopeType)
# 正式合同只保留 canonical3；skilled 作为历史别名在归一化矩阵中折叠到 expert。
SKILL_LEVEL_VALUES = (SkillLevel.BEGINNER.value, SkillLevel.NORMAL.value, SkillLevel.EXPERT.value)

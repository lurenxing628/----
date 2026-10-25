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


class SupplierStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MaterialStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class SourceType(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class OperationSetupState(str, Enum):
    PENDING = "pending"
    RETAINED_IN_EXECUTION = "retained_in_execution"
    ALREADY_COMPLETED = "already_completed"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class OperationRequirementRole(str, Enum):
    NEW_SCHEDULE = "new_schedule"
    RETAINED = "retained"
    EXECUTION = "execution"
    COMPLETED = "completed"
    NOT_SCHEDULED = "not_scheduled"


class OperationQuantityBasis(str, Enum):
    PIECE = "piece"
    BATCH = "batch"
    UNKNOWN = "unknown"


class OpTypeCategory(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    BOTH = "both"


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


class DueState(str, Enum):
    SPECIFIED = "specified"
    UNSPECIFIED = "unspecified"
    INVALID = "invalid"


class DeliveryRisk(str, Enum):
    OVERDUE = "overdue"
    ON_TIME = "on_time"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class DeliveryCompletionState(str, Enum):
    COMPLETE = "complete"
    DEFERRED = "deferred"
    INCOMPLETE = "incomplete"
    UNKNOWN = "unknown"


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


class BatchExternalContextOrigin(str, Enum):
    CREATION = "creation"
    TEMPLATE_COPY = "template_copy"
    INSTANCE_COPY = "instance_copy"
    MIGRATION_V33 = "migration_v33"
    ARCHIVE_PRE_V33 = "archive_pre_v33"  # In-memory interpretation of an authenticated pre-v33 run capture only.


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

SUPPLIER_STATUS_VALUES = tuple(m.value for m in SupplierStatus)
MATERIAL_STATUS_VALUES = tuple(m.value for m in MaterialStatus)
SOURCE_TYPE_VALUES = tuple(m.value for m in SourceType)

BATCH_STATUS_VALUES = tuple(m.value for m in BatchStatus)
BATCH_OPERATION_STATUS_VALUES = tuple(m.value for m in BatchOperationStatus)
BATCH_PRIORITY_VALUES = tuple(m.value for m in BatchPriority)
READY_STATUS_VALUES = tuple(m.value for m in ReadyStatus)

# 存储口径：CalendarAdmin/导入落库层统一将 weekend 归一为 holiday，因此落库值域只需 workday/holiday
CALENDAR_DAY_TYPE_STORED_VALUES = (CalendarDayType.WORKDAY.value, CalendarDayType.HOLIDAY.value)
MERGE_MODE_VALUES = tuple(m.value for m in MergeMode)

PART_OPERATION_STATUS_VALUES = tuple(m.value for m in PartOperationStatus)
MACHINE_DOWNTIME_STATUS_VALUES = tuple(m.value for m in MachineDowntimeStatus)

LOCK_STATUS_VALUES = tuple(m.value for m in LockStatus)
DOWNTIME_SCOPE_TYPE_VALUES = tuple(m.value for m in DowntimeScopeType)


def read_source_type(value):
    """Read legacy source text; unrecognized storage values remain unknown."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in SOURCE_TYPE_VALUES:
            return normalized
    return value

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


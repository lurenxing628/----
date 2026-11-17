"""存储枚举的唯一事实源：值域、中文叫法、业务顺序，以及 DDL 引用的 CHECK 片段。

DDL 模块用 ``enum_check`` / ``nullable_enum_check`` 生成值域约束，写入口准入、排序和显示都从这里取值，
不在别处另写一份值域元组或标签表。导入文件的表头和填写叫法由各文件模块定义（多数直接取这里的叫法），这里不收别名。
存储微秒与存储计数这两类整数列的 CHECK 片段（``time_us_check`` / ``nullable_time_us_check`` / ``count_check``）
也在这里生成。
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from core.shared.strict_parse import EXTERNAL_DAYS_MAX, JS_SAFE_INT_MAX, TIME_US_MAX, TIME_US_MIN


class YesNo(str, Enum):
    YES = "yes"
    NO = "no"


class SortStrategy(Enum):
    """排产配置 ``sort_strategy`` 的取值。不混入 str：公开出口必须显式写 ``.value``，漏写时序列化直接报错。"""

    PRIORITY_FIRST = "priority_first"
    DUE_DATE_FIRST = "due_date_first"
    WEIGHTED = "weighted"
    FIFO = "fifo"


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


class MachineGroupStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ShiftProfileStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class OperatorInactiveReason(str, Enum):
    LEAVE = "leave"
    DISABLED = "disabled"


class SupplierInactiveReason(str, Enum):
    PENDING_REVIEW = "pending_review"
    DISABLED = "disabled"


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


class PartOperationStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"


class MachineDowntimeStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class MachineDowntimeReason(str, Enum):
    MAINTENANCE = "maintenance"
    BREAKDOWN = "breakdown"
    POWER = "power"
    TOOLING = "tooling"
    OTHER = "other"


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
    EXPERT = "expert"


# ============================================================
# 存储值域：DDL 的 CHECK 片段与写入口准入共用这一份
# ============================================================

YESNO_VALUES = tuple(m.value for m in YesNo)

OPERATOR_STATUS_VALUES = tuple(m.value for m in OperatorStatus)
MACHINE_STATUS_VALUES = tuple(m.value for m in MachineStatus)

SUPPLIER_STATUS_VALUES = tuple(m.value for m in SupplierStatus)
MATERIAL_STATUS_VALUES = tuple(m.value for m in MaterialStatus)
MACHINE_GROUP_STATUS_VALUES = tuple(m.value for m in MachineGroupStatus)
SHIFT_PROFILE_STATUS_VALUES = tuple(m.value for m in ShiftProfileStatus)
OPERATOR_INACTIVE_REASON_VALUES = tuple(m.value for m in OperatorInactiveReason)
SUPPLIER_INACTIVE_REASON_VALUES = tuple(m.value for m in SupplierInactiveReason)
SOURCE_TYPE_VALUES = tuple(m.value for m in SourceType)
OP_TYPE_CATEGORY_VALUES = tuple(m.value for m in OpTypeCategory)
SKILL_LEVEL_VALUES = tuple(m.value for m in SkillLevel)

BATCH_STATUS_VALUES = tuple(m.value for m in BatchStatus)
BATCH_OPERATION_STATUS_VALUES = tuple(m.value for m in BatchOperationStatus)
BATCH_PRIORITY_VALUES = tuple(m.value for m in BatchPriority)
READY_STATUS_VALUES = tuple(m.value for m in ReadyStatus)

#: 日历只存工作日和假期；周末按假期存。
CALENDAR_DAY_TYPE_STORED_VALUES = (CalendarDayType.WORKDAY.value, CalendarDayType.HOLIDAY.value)
MERGE_MODE_VALUES = tuple(m.value for m in MergeMode)
BATCH_EXTERNAL_CONTEXT_ORIGIN_VALUES = tuple(m.value for m in BatchExternalContextOrigin)

PART_OPERATION_STATUS_VALUES = tuple(m.value for m in PartOperationStatus)
MACHINE_DOWNTIME_STATUS_VALUES = tuple(m.value for m in MachineDowntimeStatus)
MACHINE_DOWNTIME_REASON_VALUES = tuple(m.value for m in MachineDowntimeReason)

LOCK_STATUS_VALUES = tuple(m.value for m in LockStatus)
DOWNTIME_SCOPE_TYPE_VALUES = tuple(m.value for m in DowntimeScopeType)


# ============================================================
# 中文叫法：后端出口与导出文件只用这一份
# ============================================================

#: 资源公开状态（存储 status 加停用原因推出）的叫法；“可用”在各页另有叫法，见 RESOURCE_ACTIVE_LABELS。
RESOURCE_STATUS_LABELS = {
    "active": "可用", "maintain": "停机", "leave": "请假", "pending_review": "待复核", "inactive": "停用",
}
RESOURCE_ACTIVE_LABELS = {
    "machine": "可用", "operator": "在岗", "supplier": "启用", "material": "启用", "machine_group": "启用", "shift_profile": "启用",
}
SOURCE_TYPE_LABELS = {SourceType.INTERNAL.value: "自制", SourceType.EXTERNAL.value: "外协"}
OP_TYPE_CATEGORY_LABELS = {
    OpTypeCategory.INTERNAL.value: "自制", OpTypeCategory.EXTERNAL.value: "外协", OpTypeCategory.BOTH.value: "自制和外协都可",
}
MERGE_MODE_LABELS = {MergeMode.SEPARATE.value: "分别设置", MergeMode.MERGED.value: "合并设置"}
BATCH_PRIORITY_LABELS = {BatchPriority.NORMAL.value: "普通", BatchPriority.URGENT.value: "急件", BatchPriority.CRITICAL.value: "特急"}
READY_STATUS_LABELS = {ReadyStatus.YES.value: "齐套", ReadyStatus.PARTIAL.value: "部分齐套", ReadyStatus.NO.value: "未齐套"}
BATCH_STATUS_LABELS = {
    BatchStatus.PENDING.value: "待排", BatchStatus.SCHEDULED.value: "已排", BatchStatus.PROCESSING.value: "加工中",
    BatchStatus.COMPLETED.value: "已完成", BatchStatus.CANCELLED.value: "已取消",
}
SKILL_LEVEL_LABELS = {SkillLevel.BEGINNER.value: "初级", SkillLevel.NORMAL.value: "普通", SkillLevel.EXPERT.value: "熟练"}
YES_NO_LABELS = {YesNo.YES.value: "是", YesNo.NO.value: "否"}
MACHINE_DOWNTIME_REASON_LABELS = {
    MachineDowntimeReason.MAINTENANCE.value: "计划维护", MachineDowntimeReason.BREAKDOWN.value: "故障停机",
    MachineDowntimeReason.POWER.value: "停电/能耗", MachineDowntimeReason.TOOLING.value: "换刀/工装",
    MachineDowntimeReason.OTHER.value: "其他",
}


# ============================================================
# 业务顺序：SQL 排序与 Python 排序都按同一份序号，序号小的在前
# ============================================================

#: 能用的在前，停机、请假、待复核这类暂时用不了的并列居中，停用在后。
RESOURCE_STATUS_RANKS = {"active": 0, "maintain": 1, "leave": 1, "pending_review": 1, "inactive": 2}
#: 越急越靠前；排产规则与列表排序共用。
BATCH_PRIORITY_RANKS = {BatchPriority.CRITICAL.value: 0, BatchPriority.URGENT.value: 1, BatchPriority.NORMAL.value: 2}
#: 齐套的在前，未齐套在后。
READY_STATUS_RANKS = {ReadyStatus.YES.value: 0, ReadyStatus.PARTIAL.value: 1, ReadyStatus.NO.value: 2}
#: 按批次流程先后：待排、已排、加工中、已完成，已取消在最后。
BATCH_STATUS_RANKS = {status.value: rank for rank, status in enumerate(BatchStatus)}
#: 熟练的在前；排产挑人与列表排序共用。
SKILL_LEVEL_RANKS = {SkillLevel.EXPERT.value: 0, SkillLevel.NORMAL.value: 1, SkillLevel.BEGINNER.value: 2}


# ============================================================
# DDL 值域约束片段
# ============================================================


def _sql_literals(values: Iterable[str]) -> str:
    return ", ".join("'" + value + "'" for value in values)


def enum_check(column: str, values: Iterable[str]) -> str:
    """必填枚举列的约束：``CHECK(column IN (...))``，列本身另写 ``NOT NULL``。"""
    return "CHECK(" + column + " IN (" + _sql_literals(values) + "))"


def nullable_enum_check(column: str, values: Iterable[str]) -> str:
    """合法可空枚举列的约束：``CHECK(column IS NULL OR column IN (...))``。"""
    return "CHECK(" + column + " IS NULL OR " + column + " IN (" + _sql_literals(values) + "))"


# 存储整数列的值域：INTEGER 亲和存得下 REAL、非数字文本和超出 int64 的数，只有 typeof 加范围才把列定型。
# 范围取 strict_parse 的同一规则：时间微秒（local_datetime.datetime_to_us 写入）是 datetime 能表示的范围，
# 负数、零、超过 2**53-1 都是正常时刻；单条计数是 0..2**53-1。读侧因此直接用库里的值。


def _integer_between(column: str, low: int, high: int) -> str:
    return "typeof(" + column + ") = 'integer' AND " + column + " BETWEEN " + str(low) + " AND " + str(high)


def time_us_check(column: str) -> str:
    """必填时间微秒列的约束，列本身另写 ``NOT NULL``。"""
    return "CHECK(" + _integer_between(column, TIME_US_MIN, TIME_US_MAX) + ")"


def nullable_time_us_check(column: str) -> str:
    """合法可空时间微秒列的约束：``NULL`` 或同一值域。"""
    return "CHECK(" + column + " IS NULL OR (" + _integer_between(column, TIME_US_MIN, TIME_US_MAX) + "))"


def count_check(column: str) -> str:
    """必填单条计数列的约束，列本身另写 ``NOT NULL``。"""
    return "CHECK(" + _integer_between(column, 0, JS_SAFE_INT_MAX) + ")"


# 外协周期列（自然日，REAL 亲和）的值域取 strict_parse.is_external_days 的同一规则 (0, EXTERNAL_DAYS_MAX]：
# REAL 亲和存得下文本、±Inf 和超过百年的数，typeof 加区间才把列定型。NaN 绑定进库就成了 NULL，只能由写入方
# 按同一原语先拒收。


def _external_days_between(column: str) -> str:
    return ("typeof(" + column + ") IN ('integer', 'real') AND " + column + " > 0 AND "
            + column + " <= " + str(EXTERNAL_DAYS_MAX))


def external_days_check(column: str) -> str:
    """必填外协周期列的约束，列本身另写 ``NOT NULL``。"""
    return "CHECK(" + _external_days_between(column) + ")"


def nullable_external_days_check(column: str) -> str:
    """可空外协周期列的约束：``NULL``（还没设周期）或同一值域。"""
    return "CHECK(" + column + " IS NULL OR (" + _external_days_between(column) + "))"


# ============================================================
# 0/1 标志、单值来源种类、班次轮换区间与正数量：DDL 片段与归档准入共用这一份
# ============================================================

#: 存储 0/1 标志（是否有效、是否休息日、是否已登记技能这类）的值域。
FLAG_VALUES = (0, 1)


class PlanSourceKind(str, Enum):
    OPERATION = "operation"


#: 计划来源永久编号登记的来源种类，目前只有工序。
PLAN_SOURCE_KIND_VALUES = tuple(m.value for m in PlanSourceKind)

#: 班次轮换周期 1..SHIFT_CYCLE_DAYS_MAX 天；轮换日偏移是周期内第几天，从 0 起。
SHIFT_CYCLE_DAYS_MAX = 366
SHIFT_DAY_OFFSET_MAX = SHIFT_CYCLE_DAYS_MAX - 1


def flag_check(column: str) -> str:
    """必填 0/1 标志列的约束：``CHECK(column IN (0, 1))``，列本身另写 ``NOT NULL``。"""
    return "CHECK(" + column + " IN (" + ", ".join(str(value) for value in FLAG_VALUES) + "))"


def integer_range_check(column: str, low: int, high: int) -> str:
    """必填整数区间列（班次周期、轮换日偏移）的约束：typeof 加区间把列定型，列本身另写 ``NOT NULL``。"""
    return "CHECK(" + _integer_between(column, low, high) + ")"


def positive_amount_check(column: str) -> str:
    """必填正数量列（到料量）的约束，取 ``strict_parse.is_stored_number(positive=True)`` 同一规则：
    整数或实数、大于 0、不超过 2**53-1。REAL 亲和存得下文本和 +Inf，只有 typeof 加区间才把列定型。"""
    return ("CHECK(typeof(" + column + ") IN ('integer', 'real') AND " + column + " > 0 AND "
            + column + " <= " + str(JS_SAFE_INT_MAX) + ")")


# ============================================================
# 工艺来源、正式版本采纳来源、排程数量依据、报工来源与修订动作，以及可空单条计数
# ============================================================


class WorkflowOrigin(str, Enum):
    LEGACY = "legacy"
    MANAGED = "managed"


class AdoptionSourceKind(str, Enum):
    CANDIDATE_ADOPTION = "candidate_adoption"
    TRIAL_ADOPTION = "trial_adoption"


class ScheduleQuantityBasis(str, Enum):
    RUN_ADMISSION = "run_admission"
    TRIAL_CREATION = "trial_creation"


class ReportSource(str, Enum):
    MANUAL = "manual"
    EXCEL = "excel"


class ReportRevisionAction(str, Enum):
    CREATE = "create"
    SUPPLEMENT = "supplement"
    CORRECT = "correct"


#: 零件工艺来自旧数据（legacy）还是在工作台逐级确认（managed）。
WORKFLOW_ORIGIN_VALUES = tuple(m.value for m in WorkflowOrigin)
#: 正式计划版本由候选采纳还是试调采纳写入。
ADOPTION_SOURCE_KIND_VALUES = tuple(m.value for m in AdoptionSourceKind)
#: 正式排程行的数量取自运行受理时还是试调创建时。
SCHEDULE_QUANTITY_BASIS_VALUES = tuple(m.value for m in ScheduleQuantityBasis)
#: 报工来源与报工修订动作。
REPORT_SOURCE_VALUES = tuple(m.value for m in ReportSource)
REPORT_REVISION_ACTION_VALUES = tuple(m.value for m in ReportRevisionAction)


def nullable_count_check(column: str) -> str:
    """可空单条计数列（报工完成数量）的约束：``NULL`` 或 ``count_check`` 的同一值域，
    取 ``strict_parse.is_stored_number(integer=True)`` 同一规则。"""
    return "CHECK(" + column + " IS NULL OR (" + _integer_between(column, 0, JS_SAFE_INT_MAX) + "))"


# ============================================================
# 值班台条目、外协登记、排产运行与读模型、试调草稿的存储值域，以及正整数计数与整数合计
# ============================================================


class DashboardItemCategory(str, Enum):
    DELIVERY = "delivery"
    ACTUAL = "actual"
    EXTERNAL = "external"
    DOWNTIME = "downtime"
    MATERIAL = "material"


class DashboardHandlingAction(str, Enum):
    TRANSITION = "transition"
    REOPEN = "reopen"


class OutsourcingTargetKind(str, Enum):
    SINGLE = "single"
    MERGED = "merged"


class OutsourcingConfirmedState(str, Enum):
    IN_TRANSIT = "in_transit"
    RETURNED = "returned"
    AWAITING_CONFIRMATION = "awaiting_confirmation"


class RunState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class RunStage(str, Enum):
    QUEUED = "queued"
    COMPUTING = "computing"
    FINISHED = "finished"
    AWAITING_RECONCILIATION = "awaiting_reconciliation"


class RunResourceView(str, Enum):
    SELECTED_BATCHES = "selected_batches"
    FULL_CANDIDATE = "full_candidate"


class TrialBaseKind(str, Enum):
    PLAN_REF = "plan_ref"
    CANDIDATE_REF = "candidate_ref"


class TrialDraftStatus(str, Enum):
    EDITING = "editing"
    SAVED = "saved"
    DISCARDED = "discarded"


#: 值班台处置条目的种类（库里登记的那些）与处置动作。
DASHBOARD_ITEM_CATEGORY_VALUES = tuple(m.value for m in DashboardItemCategory)
DASHBOARD_HANDLING_ACTION_VALUES = tuple(m.value for m in DashboardHandlingAction)
#: 外协单发出方式（单工序或合并）与确认状态。
OUTSOURCING_TARGET_KIND_VALUES = tuple(m.value for m in OutsourcingTargetKind)
OUTSOURCING_CONFIRMED_STATE_VALUES = tuple(m.value for m in OutsourcingConfirmedState)
#: 排产运行的状态与阶段；后四种状态是终态，运行结束后不再变。
RUN_STATE_VALUES = tuple(m.value for m in RunState)
RUN_TERMINAL_STATE_VALUES = tuple(m.value for m in (RunState.COMPLETE, RunState.PARTIAL, RunState.FAILED, RunState.INTERRUPTED))
RUN_TERMINAL_STATES = frozenset(RUN_TERMINAL_STATE_VALUES)
RUN_STAGE_VALUES = tuple(m.value for m in RunStage)
#: 决策读模型的资源视角：本次所选批次，或方案全部安排。
RUN_RESOURCE_VIEW_VALUES = tuple(m.value for m in RunResourceView)
#: 试调草稿的来源种类与状态。
TRIAL_BASE_KIND_VALUES = tuple(m.value for m in TrialBaseKind)
TRIAL_DRAFT_STATUS_VALUES = tuple(m.value for m in TrialDraftStatus)


def enum_predicate(column: str, values: Iterable[str]) -> str:
    """``column IN (...)`` 的 SQL 判断（不带 CHECK），给跨列约束与触发器引用同一份值域。"""
    return column + " IN (" + _sql_literals(values) + ")"


def positive_count_check(column: str) -> str:
    """必填正整数计数列（批次数量与物料核对时记下的批次数量、修订次数与序号）的约束，取 ``strict_parse.is_stored_number(integer=True,
    positive=True)`` 同一规则：整数、1..2**53-1。列本身另写 ``NOT NULL``。"""
    return "CHECK(" + _integer_between(column, 1, JS_SAFE_INT_MAX) + ")"


def integer_sum_check(column: str) -> str:
    """必填非负整数合计列（已知完成数量这类按条累加的量）的约束：整数且不小于 0。单条计数才有 2**53-1 的上限，
    合计只要求精确非负（见 ``strict_parse.is_stored_number``）。列本身另写 ``NOT NULL``。"""
    return "CHECK(typeof(" + column + ") = 'integer' AND " + column + " >= 0)"


#: 还没结束的运行状态（排队中、计算中），与终态互补。
RUN_UNFINISHED_STATE_VALUES = (RunState.QUEUED.value, RunState.RUNNING.value)
#: 运行结束并留下了候选结果的状态（完成、部分完成）。
RUN_RESULT_STATE_VALUES = (RunState.COMPLETE.value, RunState.PARTIAL.value)

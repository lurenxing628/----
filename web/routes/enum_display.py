from __future__ import annotations

from core.models.enums import BatchStatus, OperatorStatus
from core.services.common.enum_normalizers import (
    batch_priority_label,
    calendar_day_type_label,
    machine_status_label,
    normalize_operator_status,
    operator_status_label,
    ready_status_label,
)

# R41/O26 收口（选项 C）：本文件原是 enum_normalizers 标准标签的第二套私有实现（口径已漂移），
# 现 5 族（machine/operator/day_type/priority/ready）收口为标准版薄包装；其中 operator 与 ready
# 两处按 O26 配套裁定在本包装层打补丁（标准版语义不满足业务），batch_status 无 canonical 收口点
# 保留私有（强建 batch_status_label = 新 P5，禁）。补丁只许打在本 web 包装层——enum_normalizers
# 是 LB04 承重毗邻区，R41 只调用不修改。


def machine_status_zh(status: str) -> str:
    return machine_status_label(status)


def operator_status_zh(status: str) -> str:
    # O26 打补丁：inactive 在本系统业务上含「休假」语义，标准版 operator_status_label 只给「停用」，
    # 此处保留「停用/休假」双标签——HR 需要区分停用与休假的可能性，禁收窄成「停用」。
    if normalize_operator_status(status) == OperatorStatus.INACTIVE.value:
        return "停用/休假"
    return operator_status_label(status)


def day_type_zh(day_type: str) -> str:
    return calendar_day_type_label(day_type)


def batch_status_zh(v: str) -> str:
    # O26 裁定保留私有：enum_normalizers 无 canonical 的 batch_status 标签函数（同名
    # batch_status_label 仅是 viewmodel 注入参数名），强行新建收口点 = 制造新的第二模块。
    s = (v or "").strip()
    if s == BatchStatus.PENDING.value:
        return "待排"
    if s == BatchStatus.SCHEDULED.value:
        return "已排"
    if s == BatchStatus.PROCESSING.value:
        return "加工中"
    if s == BatchStatus.COMPLETED.value:
        return "已完成"
    if s == BatchStatus.CANCELLED.value:
        return "已取消"
    return s or "-"


def priority_zh(v: str) -> str:
    return batch_priority_label(v)


def ready_zh(v: str) -> str:
    # O26/RK20 打补丁：空值绝不让标准版默认「齐套」放行——ready_status_label 的空值默认是
    # ReadyStatus.YES（齐套），调度场景下「未齐套冒充齐套」会让调度员误放行，空值必须钉「未齐套」。
    # 未知坏值走标准版 passthrough 原样暴露（loud），禁改回静默贴「未齐套」确定态。
    if v is None or str(v).strip() == "":
        return "未齐套"
    return ready_status_label(v)

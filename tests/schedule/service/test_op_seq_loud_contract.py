"""回归测试：_op_seq 单源收口与 loud 契约（R69/O24 收口）——persistence_guard 与 runtime_support 两份逐字节相同的副本已合一到 schedule_input_contracts，is 断言钉单源、hasattr 反断言防本地副本回潮；seq=None/0/空串走 `or 0` 合法短路返回 0 绝不 raise（下游靠 completed_seq<=0 短路过滤，爆点 #15：卷入报错会放大双热路径不可用），坏类型（seq="abc"）必须 loud raise ValueError，禁改回 except 静默归 0。"""

from __future__ import annotations

import pytest

from core.services.scheduler.run.schedule_input_contracts import _op_seq


class _Op:
    def __init__(self, seq):
        self.seq = seq


def test_op_seq_legal_or_zero_paths_never_raise() -> None:
    # `or 0` 兜的「无 seq」合法形态：None/0/空串/False → 0，绝不卷入 loud。
    assert _op_seq(_Op(None)) == 0
    assert _op_seq(_Op(0)) == 0
    assert _op_seq(_Op("")) == 0
    assert _op_seq(object()) == 0, "无 seq 属性走 getattr 默认 0，同属合法短路"
    assert _op_seq(_Op(7)) == 7
    assert _op_seq(_Op("12")) == 12, "可转 int 的字符串照常转换"


def test_op_seq_bad_type_raises_loud() -> None:
    with pytest.raises(ValueError, match="seq 值无效"):
        _op_seq(_Op("abc"))
    with pytest.raises(ValueError, match="seq 值无效"):
        _op_seq(_Op(object()))


def test_op_seq_single_source_no_local_copies() -> None:
    from core.services.scheduler.run import (
        schedule_execution_persistence_guard as guard_mod,
    )
    from core.services.scheduler.run import (
        schedule_input_contracts as contracts_mod,
    )
    from core.services.scheduler.run import (
        schedule_input_runtime_support as runtime_mod,
    )

    assert guard_mod._op_seq is contracts_mod._op_seq, "guard 必须共享契约文件单源，不得回潮本地副本"
    assert runtime_mod._op_seq is contracts_mod._op_seq, "runtime_support 必须共享契约文件单源"

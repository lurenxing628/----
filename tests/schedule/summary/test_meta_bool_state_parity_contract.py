"""回归测试：_meta_bool_state 全矩阵 parity 与单源收口（R68 收口）——resource_pool 路径（schedule_summary_degradation）与 downtime 路径（schedule_summary_downtime_degradation）对同一 (meta, key, default) 必须逐格等价，且收口后两模块共享 summary_count_parse 单源（is 断言防回潮分叉）；(bool, parse_failed) 二元组绝不许压扁——坏 meta（int 非 0/1、垃圾字符串、list/dict 等）必须 parse_failed=True loud 标记（断言完整二元组，禁只断第一位），否则前端「降级因 meta 异常」提示静默丢失。"""

from __future__ import annotations

import pytest

from core.services.scheduler.summary import schedule_summary_degradation as pool_mod
from core.services.scheduler.summary import schedule_summary_downtime_degradation as downtime_mod

_IMPLS = [
    pytest.param(pool_mod._meta_bool_state, id="resource_pool_path"),
    pytest.param(downtime_mod._meta_bool_state, id="downtime_path"),
]

# (meta, key, default) -> 期望完整二元组 (bool, parse_failed)
_MATRIX = [
    pytest.param({}, "k", False, (False, False), id="key缺失-default-False"),
    pytest.param({}, "k", True, (True, False), id="key缺失-default-True"),
    pytest.param({"k": None}, "k", True, (True, False), id="None视同缺失"),
    pytest.param({"k": True}, "k", False, (True, False), id="bool-True"),
    pytest.param({"k": False}, "k", True, (False, False), id="bool-False"),
    pytest.param({"k": 1}, "k", False, (True, False), id="int-1"),
    pytest.param({"k": 0}, "k", True, (False, False), id="int-0"),
    pytest.param({"k": 5}, "k", True, (True, True), id="int非01-loud-default-True"),
    pytest.param({"k": 5}, "k", False, (False, True), id="int非01-loud-default-False"),
    pytest.param({"k": "yes"}, "k", False, (True, False), id="str-yes"),
    pytest.param({"k": " ON "}, "k", False, (True, False), id="str-on-带空白大写"),
    pytest.param({"k": "off"}, "k", True, (False, False), id="str-off"),
    pytest.param({"k": "0"}, "k", True, (False, False), id="str-0"),
    pytest.param({"k": "garbage"}, "k", True, (True, True), id="str垃圾-loud"),
    pytest.param({"k": []}, "k", False, (False, True), id="list-loud"),
    pytest.param({"k": {}}, "k", True, (True, True), id="dict-loud"),
]


@pytest.mark.parametrize("impl", _IMPLS)
@pytest.mark.parametrize("meta, key, default, expected", _MATRIX)
def test_meta_bool_state_full_matrix_parity(impl, meta, key, default, expected) -> None:
    assert impl(meta, key, default=default) == expected, (
        "必须断言完整 (bool, parse_failed) 二元组：坏 meta 的 parse_failed=True 是 loud 降级标记，禁压扁"
    )


def test_meta_bool_state_single_source_no_local_copies() -> None:
    from core.services.scheduler.summary import summary_count_parse as parse_mod

    assert pool_mod._meta_bool_state is parse_mod._meta_bool_state, (
        "resource_pool 路径必须共享 summary_count_parse 单源，不得回潮本地副本"
    )
    assert downtime_mod._meta_bool_state is parse_mod._meta_bool_state, (
        "downtime 路径必须共享 summary_count_parse 单源"
    )

"""回归测试:候选择优比较的 runtime tie-break 合同。

锁住"runtime_ms 缺失或为 None 表示耗时未知,不能被当成 0ms 最快候选"这一合同,
避免同分、同指纹状态下未知耗时候选错误抢占 best。
"""

from __future__ import annotations

from core.services.scheduler.run.optimizer_candidate_comparison import (
    candidate_is_preferred,
    candidate_runtime_ms,
)


def test_candidate_runtime_ms_treats_none_as_unknown_not_zero() -> None:
    # None 与缺失同义:耗时未知,按最不被偏好(大惩罚值)处理,不能折成 0ms。
    assert candidate_runtime_ms({"score": [1], "runtime_ms": None}) == 1_000_000_000
    assert candidate_runtime_ms({"score": [1]}) == 1_000_000_000
    # 合法值原样保留,真实的 0ms 仍是 0(最快),不被惩罚。
    assert candidate_runtime_ms({"score": [1], "runtime_ms": 1000}) == 1000
    assert candidate_runtime_ms({"score": [1], "runtime_ms": 0}) == 0


def test_candidate_with_unknown_runtime_does_not_win_tiebreak() -> None:
    # 同分、同指纹状态下,runtime_ms=None 的候选不能被当成"最快"而抢占 best。
    preferred = candidate_is_preferred(
        candidate={"score": [1], "runtime_ms": None},
        incumbent={"score": [1], "runtime_ms": 1000},
        candidate_origin="local_search",
        incumbent_origin="local_search",
        candidate_fingerprint=None,
        incumbent_fingerprint_changed=False,
    )
    assert preferred is False


def test_candidate_with_faster_known_runtime_still_wins_tiebreak() -> None:
    # 真实更快(已知更小 runtime)的候选仍应在 tie-break 胜出,确认修复没误伤正常择优。
    preferred = candidate_is_preferred(
        candidate={"score": [1], "runtime_ms": 500},
        incumbent={"score": [1], "runtime_ms": 1000},
        candidate_origin="local_search",
        incumbent_origin="local_search",
        candidate_fingerprint=None,
        incumbent_fingerprint_changed=False,
    )
    assert preferred is True

"""实现一致性对标进门禁。

这个脚本以前只能人工敲命令跑，所以它红了很久没人知道：2026-09-21 第一次跑出 1 个 BLOCKER
加 6 个 MAJOR，其中 5 条是检查在看已经删掉的东西（旧甘特静态资源、旧路由层、旧模板目录、
和债务台账重复的行数检查、和行为测试重复的排产落库 AST 检查），2 条是实现搬了家而检查没跟
（退出备份执行体搬去 launcher_shutdown.py、排产默认值常量搬去 config_constants.py）。

剪裁 + 改指之后接进日常门禁，从此它再红就是实现真的偏了。
"""

from __future__ import annotations

from typing import List

from tests._support.paths import REPO_ROOT_STR
from tests.gate_meta.generate_conformance_report import CheckResult, generate_report


def _failures(checks: List[CheckResult], severity: str) -> List[str]:
    return [f"{check.name}：{check.details or '详见报告证据'}"
            for check in checks if not check.ok and check.severity == severity]


def test_implementation_matches_documented_conformance_checks() -> None:
    _, checks = generate_report(REPO_ROOT_STR)
    assert checks, "一致性检查一项都没跑，说明登记表被清空了"
    blocking = _failures(checks, "BLOCKER") + _failures(checks, "MAJOR")
    assert not blocking, "实现和开发文档对不上：\n" + "\n".join("- " + item for item in blocking)


def test_minor_conformance_gaps_are_reported_without_blocking() -> None:
    """MINOR 不拦门禁，但必须还能被报出来——否则这一档形同虚设。"""
    _, checks = generate_report(REPO_ROOT_STR)
    assert {check.severity for check in checks} <= {"BLOCKER", "MAJOR", "MINOR", "INFO"}
    for check in checks:
        assert check.ok == (check.severity == "INFO"), (
            f"{check.name}：通过的检查严重性应记 INFO，不通过的必须保留原始档位")

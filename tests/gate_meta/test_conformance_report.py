"""实现一致性对标进门禁。

这个脚本以前只能人工敲命令跑，所以它红了很久没人知道：2026-09-21 第一次跑出 1 个 BLOCKER
加 6 个 MAJOR，其中 5 条是检查在看已经删掉的东西（旧甘特静态资源、旧路由层、旧模板目录、
和债务台账重复的行数检查、和行为测试重复的排产落库 AST 检查），2 条是实现搬了家而检查没跟
（退出备份执行体搬去 launcher_shutdown.py、排产默认值常量搬去 config_constants.py）。

剪裁 + 改指之后接进日常门禁。2026-10-06 默认值统一到模型注册表后，默认值检查改为比较
共同注册表、实际服务常量与文档表格，保持四个字段的政策核对，避免依赖旧源码布局。
"""

from __future__ import annotations

from typing import List

import pytest

from tests._support.paths import REPO_ROOT_STR
from tests.gate_meta import generate_conformance_report as conformance
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


@pytest.mark.parametrize("changed_source", ("registry", "service", "document"))
def test_scheduler_default_conformance_rejects_each_source_drift(
    monkeypatch: pytest.MonkeyPatch, changed_source: str,
) -> None:
    from core.models import schedule_config_runtime_fields
    from core.services.scheduler.config import config_constants

    if changed_source == "registry":
        original_default_for = schedule_config_runtime_fields.default_for

        def changed_default_for(key: str):
            return 0.8 if key == "priority_weight" else original_default_for(key)

        monkeypatch.setattr(schedule_config_runtime_fields, "default_for", changed_default_for)
    elif changed_source == "service":
        monkeypatch.setattr(config_constants, "DEFAULT_PRIORITY_WEIGHT", 0.8)
    else:
        original_read_text = conformance._read_text

        def changed_read_text(path: str) -> str:
            text = original_read_text(path)
            return text.replace("│ priority_weight      │ 0.4", "│ priority_weight      │ 0.8")

        monkeypatch.setattr(conformance, "_read_text", changed_read_text)

    result = conformance._check_scheduler_config_defaults(REPO_ROOT_STR)

    assert not result.ok, f"未发现 {changed_source} 默认值与其他事实来源不一致"
    assert result.severity == "MAJOR"

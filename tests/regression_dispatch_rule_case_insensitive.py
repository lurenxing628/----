"""回归测试：parse_dispatch_rule 对 CR/ATC/SLACK 等派工规则做大小写与首尾空白容错，未知值回退到 default 参数。"""


def test_dispatch_rule_case_insensitive() -> None:

    from core.algorithms.dispatch_rules import DispatchRule, parse_dispatch_rule

    assert parse_dispatch_rule("CR") == DispatchRule.CR, "CR 大小写容错失败"
    assert parse_dispatch_rule(" atc ") == DispatchRule.ATC, "ATC 空白/大小写容错失败"
    assert parse_dispatch_rule("Slack") == DispatchRule.SLACK, "SLACK 大小写容错失败"

    # 未知值回退 default
    assert parse_dispatch_rule("unknown", default=DispatchRule.CR) == DispatchRule.CR, "未知值 default 回退失败"



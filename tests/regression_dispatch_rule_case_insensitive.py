import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms.dispatch_rules import DispatchRule, parse_dispatch_rule

    assert parse_dispatch_rule("CR") == DispatchRule.CR, "CR 大小写容错失败"
    assert parse_dispatch_rule(" atc ") == DispatchRule.ATC, "ATC 空白/大小写容错失败"
    assert parse_dispatch_rule("Slack") == DispatchRule.SLACK, "SLACK 大小写容错失败"

    # 未知值回退 default
    assert parse_dispatch_rule("unknown", default=DispatchRule.CR) == DispatchRule.CR, "未知值 default 回退失败"

    print("OK")


if __name__ == "__main__":
    main()


"""Host-only contracts for tools.scan_constant_arguments; these tests do not enter the product gate.

夹具是临时仓库里的真实写法：正例锁住“该报的报出来、依据写对”，反例锁住“引用表不完整或有一处不同就不报”。
"""

from __future__ import annotations

import json
import textwrap

from tools import scan_constant_arguments as scanner


def _p(*parts):
    # 夹具文件只在临时仓库里存在，拼出路径，不写成会被失效路径扫描器当成仓库路径的字面量。
    return "/".join(parts)


M = _p("core", "m.py")
T = _p("tests", "test_m.py")


def _scan(root, files):
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
    return scanner.scan(str(root))


def _arguments(result):
    return {
        (item["function"].split("::", 1)[1], item["parameter"]): item
        for item in result["findings"]
        if item["kind"] == scanner.CONSTANT_ARGUMENT
    }


def _empties(result):
    return {item["name"]: item for item in result["findings"] if item["kind"] == scanner.CONSTANT_EMPTY}


def test_constant_arguments_report_omitted_shared_and_always_passed_literals(tmp_path):
    result = _scan(tmp_path, {
        M: """
            def fetch(key, *, strict=False, limit=10, mode="fast", label=None):
                return key, strict, limit, mode, label

            def load(path, required=False):
                return path, required

            def read_all():
                fetch("a", label="x")
                fetch("b", limit=10, mode="fast", label="y")
                return load("p", required=True), load("q", required=True)
        """,
        T: """
            from core.m import fetch, load

            def test_strict_fetch():
                assert fetch("t", strict=True)
                assert load("t")
        """,
    })
    found = _arguments(result)
    assert set(found) == {("fetch", "strict"), ("fetch", "limit"), ("fetch", "mode"), ("load", "required")}
    strict = found[("fetch", "strict")]
    assert (strict["value"], strict["value_source"], strict["calls"]) == ("False", "default", [f"{M}:8", f"{M}:9"])
    assert strict["test_deviations"] == [{"site": f"{T}:4", "value": "传 True"}]
    assert (found[("fetch", "limit")]["value"], found[("fetch", "limit")]["value_source"]) == ("10", "default_and_literal")
    assert found[("fetch", "mode")]["value"] == "'fast'"
    required = found[("load", "required")]
    assert (required["value"], required["value_source"], required["default"]) == ("True", "literal", "False")
    assert required["test_deviations"] == [{"site": f"{T}:5", "value": "没传（用默认值）"}]


def test_constant_arguments_skip_escapes_unresolved_names_star_calls_and_differing_values(tmp_path):
    result = _scan(tmp_path, {M: """
        def escaped(value, flag=False):
            return value

        def mirrored(value, flag=False):
            return value

        def starred(value, flag=False):
            return value

        def spread(value, flag=False):
            return value

        def varied(value, flag=False):
            return value

        HANDLERS = {"escaped": escaped}

        def caller(row, args, options, plugin):
            escaped(row)
            mirrored(row)
            plugin.mirrored(row, flag=True)
            starred(row)
            starred(*args)
            spread(row)
            spread(row, **options)
            varied(row)
            return varied(row, flag=True)
    """})
    assert _arguments(result) == {}


def test_constant_arguments_need_a_production_call_and_skip_dispatch_that_the_index_cannot_see(tmp_path):
    result = _scan(tmp_path, {
        M: """
            import queue

            JOBS = queue.Queue()
            FACTORIES = queue.Queue()

            def tested_only(value, flag=False):
                return value

            class Job:
                def run(self, fast=False):
                    return fast

            class RetryJob(Job):
                def run(self, fast=False):
                    return not fast

            class Widget:
                def __init__(self, size=1):
                    self.size = size

            def submit():
                JOBS.put(RetryJob())
                FACTORIES.put(Widget)
                return RetryJob().run(), Widget()

            def drive():
                job: Job = JOBS.get()
                job.run(fast=True)
                return FACTORIES.get()(size=2)

            def scaled(values):
                scale = lambda value, factor=2: value * factor
                return scale(1), list(map(scale, values))
        """,
        T: """
            from core.m import tested_only

            def test_tested_only():
                assert tested_only(1, flag=True) == 1
        """,
    })
    # RetryJob.run 真实会经 Job 注解的接收者收到 fast=True，Widget 会经队列里的类对象收到 size=2，
    # lambda 经 map 被外部调用：索引对这三处都不留标记，所以都不判定。
    assert _arguments(result) == {}


def test_constant_arguments_skip_call_sites_whose_binding_depends_on_the_path(tmp_path):
    # 经实例调用时 True 对到 x，经类调用时 True 对到 self、x 用默认值：同一调用点两种绑定，不判定。
    result = _scan(tmp_path, {M: """
        class C:
            def f(self, x=False, y=False):
                return x, y

        def main(choose):
            c = C()
            return (c.f if choose else C.f)(True)
    """})
    assert _arguments(result) == {}


def test_constant_empty_reports_read_only_module_containers_and_lists_test_writes(tmp_path):
    result = _scan(tmp_path, {
        M: """
            from typing import Dict, Tuple

            EXTRA_RULES = []
            ALIASES: Dict[str, str] = {}
            IGNORED_ERRORS: Tuple[type, ...] = ()
            SEEN = frozenset()

            def rules():
                for rule in EXTRA_RULES:
                    yield rule

            def alias(key):
                return ALIASES.get(key, key)

            def check(name, action):
                if name in SEEN or IGNORED_ERRORS:
                    return [rule for rule in EXTRA_RULES if rule]
                try:
                    return action()
                except IGNORED_ERRORS:
                    return None
        """,
        T: """
            from core import m

            def test_rules():
                m.EXTRA_RULES.append("x")
                assert list(m.rules()) == ["x"]
        """,
    })
    found = _empties(result)
    assert set(found) == {"EXTRA_RULES", "ALIASES", "IGNORED_ERRORS", "SEEN"}
    assert [read["use"] for read in found["EXTRA_RULES"]["reads"]] == ["迭代", "迭代"]
    assert found["ALIASES"]["reads"] == [{"site": f"{M}:13", "use": "调用 .get()"}]
    assert {read["use"] for read in found["IGNORED_ERRORS"]["reads"]} == {"真值", "异常匹配"}
    assert (found["SEEN"]["value"], found["SEEN"]["reads"][0]["use"]) == ("frozenset()", "比较")
    assert found["EXTRA_RULES"]["test_deviations"] == [{"site": f"{T}:4", "value": "调用 .append()"}]


def test_constant_empty_skips_written_escaping_aliased_rebound_and_unresolved_containers(tmp_path):
    result = _scan(tmp_path, {M: """
        CACHE = {}
        REGISTRY = {}
        PENDING = []
        DEFAULTS = ()
        STATE = []
        OPTIONS = []
        LEFT = RIGHT = []

        def remember(key, value, sink, module):
            CACHE.update({key: value})
            REGISTRY[key] = value
            sink(PENDING)
            for item in OPTIONS:
                module.OPTIONS.append(item)
            return key in LEFT or key in RIGHT

        def defaults():
            return DEFAULTS

        def reset():
            global STATE
            for item in STATE:
                print(item)
            STATE = [1]
    """})
    assert _empties(result) == {}


def test_constant_empty_needs_the_real_builtin_constructor(tmp_path):
    # 模块里自定义的同名工厂不是内置构造器，它返回的容器不空。
    result = _scan(tmp_path, {
        M: """
            def dict():
                return {"hot": 1}

            REGISTRY = dict()

            def lookup(key):
                return REGISTRY.get(key)
        """,
        _p("core", "n.py"): """
            CACHE = dict()

            def read(key):
                return CACHE.get(key)
        """,
    })
    assert set(_empties(result)) == {"CACHE"}


def test_constant_empty_counts_operands_the_other_side_may_take_as_escapes(tmp_path):
    # 作比较、运算、增量赋值的操作数或下标（含切片分量、扩展切片 grid[x:, 0] 的各维）时，接收它的另一方不是字面量，
    # 就可能经协议方法把它当实参拿走：仓库对象的 __eq__ / __getitem__，列表里元素的 __eq__（in），类型未知的队列
    # 取出物、累加目标都算传出。另一方是字面量、或它自己作 in 右边的容器时只读。
    result = _scan(tmp_path, {M: """
        from queue import Queue

        EMPTY = []
        WINDOW = []
        ROWS = []
        COLUMN = []
        NEEDLE = []
        PENDING = []
        TAIL = ()
        NESTED = ()
        PLAIN = ()
        TAGS = ()

        class Consumer:
            def __eq__(self, other):
                other.append(1)
                return True

            def __getitem__(self, key):
                key.start.append(1)
                return 0

        def make_consumer():
            queue = Queue()
            queue.put(Consumer())
            return queue.get()

        def check(consumer: Consumer, total, first, second):
            total += TAIL
            return (consumer == EMPTY, Consumer()[WINDOW:], Consumer()[ROWS:, 0], Consumer()[1:, COLUMN],
                    NEEDLE in [Consumer()], make_consumer() == PENDING, first + second == NESTED, total, PLAIN == (),
                    "x" in TAGS, TAGS + ("y",))
    """})
    assert set(_empties(result)) == {"PLAIN", "TAGS"}


def test_constant_empty_counts_import_def_and_class_rebinding_as_writes(tmp_path):
    # import / def / class 重新绑定同名模块变量也是写入：BACKEND 在运行时是 json 模块，真值为真。
    result = _scan(tmp_path, {M: """
        BACKEND = {}
        try:
            import json as BACKEND
        except ImportError:
            pass

        HANDLERS = []

        def HANDLERS():
            return []

        TIMEOUTS = {}

        def enabled():
            if BACKEND or HANDLERS:
                return True
            return bool(TIMEOUTS.get("default"))
    """})
    assert set(_empties(result)) == {"TIMEOUTS"}


def test_module_alias_cycles_do_not_stop_the_scan(tmp_path):
    # os.path.os 就是 os：沿模块别名环取属性的写法照常求解收敛，同一份代码里的恒定实参照常报出。
    result = _scan(tmp_path, {M: """
        import os

        root = os

        def step():
            global root
            root = root.path.os

        def fetch(key, strict=False):
            return key, strict

        def main():
            step()
            return fetch("a")
    """})
    assert set(_arguments(result)) == {("fetch", "strict")}


def test_cli_prints_json_and_text_grouped_by_file(tmp_path, capsys):
    _scan(tmp_path, {M: """
        IGNORED = ()

        def fetch(key, strict=False):
            return key

        def read(key):
            if key in IGNORED:
                return None
            return fetch(key)
    """})
    assert scanner.main(["--json", "--repo-root", str(tmp_path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["totals"] == {scanner.CONSTANT_ARGUMENT: 1, scanner.CONSTANT_EMPTY: 1}
    assert scanner.main(["--repo-root", str(tmp_path)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1:] == [
        M,
        f"  :1 恒空常量 IGNORED = ()：1 处生产/工具读取都只读（{M}:7 比较）",
        f"  :3 恒定实参 fetch(strict) 恒用默认值 False：1 处生产/工具调用都没传（{M}:9）",
    ]

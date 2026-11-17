"""Host-only contracts for tools.scan_dead_code_islands; these tests do not enter the product gate.

规则测试都走公开入口（``build_reference_index`` / ``scan``），夹具是生产里真实出现的写法：
每条规则一个“该有证据”的正例和一个“不该有证据”的反例，锁住的是扫描器对合法代码的判定，不是给哪条防御续命。
"""

from __future__ import annotations

import ast
import importlib
import json
import sys
import textwrap

import pytest

from tools import scan_dead_code_islands as scanner
from tools.dead_code_usage.binder import bind, signature_of
from tools.dead_code_usage.model import CALL, CALLBACK, DECORATOR, LOAD, PROTOCOL, REFERENCE, STORE, CodeRoles
from tools.dead_code_usage.reference_index import build_reference_index
from tools.dead_code_usage.scip_usage import ScipUsageError
from tools.path_roles import PRODUCTION, TEST, role_of


def _write(root, rel_path, text):
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")


def _p(*parts):
    # 夹具文件只在临时仓库里存在，拼出路径，不写成会被失效路径扫描器当成仓库路径的字面量。
    return "/".join(parts)


M = _p("core", "m.py")


def _index(root, files):
    for rel, text in files.items():
        _write(root, rel, text)
    return build_reference_index(str(root), {}, sorted(files), CodeRoles(role_of, TEST))


def _uses(index, name, rel=M):
    """目标的引用：(种类, 引用所在函数)。"""
    return sorted({(ref.kind, ref.source_qual) for ref in index.references.get(f"{rel}::{name}", ())})


def _mini_repo(root):
    _write(root, _p("core", "__init__.py"), "")
    _write(root, _p("core", "sample.py"), """
        def zz_wired_callee():
            return 1


        def zz_wired_caller():
            return zz_wired_callee()


        def zz_never_used():
            return 2


        def zz_tool_used():
            return 3


        def zz_host_tested():
            return 4


        def zz_product_tested():
            return 5
    """)
    _write(root, _p("tools", "__init__.py"), "")
    _write(root, _p("tools", "report.py"), """
        from core.sample import zz_tool_used

        print(zz_tool_used())
    """)
    _write(root, _p("tools", "host_tests", "__init__.py"), "")
    _write(root, _p("tools", "host_tests", "test_sample.py"), """
        def test_host():
            from core.sample import zz_host_tested
            assert zz_host_tested() == 4


        def zz_host_helper_never_used():
            return 6
    """)
    _write(root, _p("tests", "test_sample.py"), """
        from core.sample import zz_product_tested


        def test_product():
            assert zz_product_tested() == 5
    """)


def test_scan_drops_test_role_nodes_and_splits_evidence_by_role(tmp_path):
    _mini_repo(tmp_path)
    result = scanner.scan(str(tmp_path))

    # 宿主测试里的调用边不再让被测函数退出候选；测试角色自己的函数不当候选；
    # 宿主工具的引用算在用，只有测试引用的归 test_only。
    assert result["entries"] == [
        {
            "path": "core/sample.py::zz_host_tested",
            "kind": "test_only",
            "count": 1,
            "test_refs": ["tools/host_tests/test_sample.py:3"],
        },
        {"path": "core/sample.py::zz_never_used", "kind": "suspect_dead", "count": 1},
        {
            "path": "core/sample.py::zz_product_tested",
            "kind": "test_only",
            "count": 1,
            "test_refs": ["tests/test_sample.py:5"],
        },
    ]
    assert result["kind_totals"] == {"suspect_dead": 1, "test_only": 2}
    assert result["live_count"] == 1


def test_cli_uses_shared_ratchet_and_precise_mode_never_touches_baseline(tmp_path, capsys):
    _mini_repo(tmp_path)
    root = ["--repo-root", str(tmp_path)]

    assert scanner.main(root + ["--fail-on-new"]) == 2
    assert "基线缺失" in capsys.readouterr().err

    assert scanner.main(root + ["--refresh"]) == 0
    baseline_path = tmp_path / ".codestable" / "checkup" / "dead_code_islands_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline["rule"] == "dead_code_islands"
    assert [(entry["path"], entry["kind"], entry["count"]) for entry in baseline["entries"]] == [
        ("core/sample.py::zz_host_tested", "test_only", 1),
        ("core/sample.py::zz_never_used", "suspect_dead", 1),
        ("core/sample.py::zz_product_tested", "test_only", 1),
    ]
    capsys.readouterr()

    assert scanner.main(root + ["--fail-on-new", "--quiet-when-clean"]) == 0
    assert capsys.readouterr().out == ""

    _write(tmp_path, _p("core", "extra.py"), "def zz_new_dead():\n    return 7\n")
    assert scanner.main(root + ["--fail-on-new"]) == 1
    assert "新增债务：core/extra.py::zz_new_dead kind=suspect_dead count=1" in capsys.readouterr().out
    assert scanner.main(root + ["--refresh"]) == 1
    assert "刷新被拒绝" in capsys.readouterr().err

    with pytest.raises(SystemExit):
        scanner.main(root + ["--mode", "precise", "--refresh"])
    assert "precise 模式只出报告" in capsys.readouterr().err


def test_precise_mode_checks_scip_before_running_callgraph(tmp_path, monkeypatch):
    _mini_repo(tmp_path)

    def callgraph_reached(_repo_root):
        raise scanner.CallgraphError("调用图已运行")

    monkeypatch.setattr(scanner, "_callgraph", callgraph_reached)
    # 临时目录不是干净的 git 工作区：前置检查先失败，调用图根本没跑。
    with pytest.raises(ScipUsageError) as caught:
        scanner.scan(str(tmp_path), mode="precise")
    assert caught.value.code == "dirty_worktree"
    # quick 模式不做 SCIP 前置检查，直接进调用图。
    with pytest.raises(scanner.CallgraphError):
        scanner.scan(str(tmp_path), mode="quick")


def test_test_files_get_their_own_scope_index(tmp_path):
    # DC-25 的形状：测试函数体内局部 import、闭包里构造、经列表元素取回再调用；调用图不索引测试文件。
    _write(tmp_path, _p("core", "__init__.py"), "")
    _write(tmp_path, _p("core", "cache.py"), """
        class Cache:
            @classmethod
            def build(cls):
                return cls()

            def stats(self):
                return {}

            def reset(self):
                return None
    """)
    _write(tmp_path, _p("tests", "test_cache.py"), """
        def test_stats():
            from core.cache import Cache
            created = []

            def capture():
                cache = Cache.build()
                created.append(cache)
                return cache

            capture()
            assert created[-1].stats() == {}


        def test_untyped(fake):
            fake.reset()
    """)
    result = scanner.scan(str(tmp_path))
    by_path = {entry["path"].split("::")[1]: entry for entry in result["entries"]}
    assert by_path["Cache.stats"] == {
        "path": _p("core", "cache.py") + "::Cache.stats", "kind": "test_only", "count": 1,
        "test_refs": [_p("tests", "test_cache.py") + ":11"],
    }
    assert by_path["Cache.build"]["kind"] == "test_only"
    # 接收者类型不明的同名调用不算证据。
    assert by_path["Cache.reset"]["kind"] == "suspect_dead"


def test_mro_dispatch_reaches_inherited_method_only(tmp_path):
    index = _index(tmp_path, {M: """
        class Base:
            def run(self):
                return 1

        class Child(Base):
            pass

        class Other:
            def run(self):
                return 2

        def main():
            return Child().run()
    """})
    assert _uses(index, "Base.run") == [(CALL, f"{M}::main")]
    assert _uses(index, "Other.run") == []


def test_super_and_explicit_base_call_reach_parent_but_plain_override_does_not(tmp_path):
    index = _index(tmp_path, {M: """
        class Base:
            def run(self):
                return 1

            def stop(self):
                return 2

            def pause(self):
                return 3

        class Child(Base):
            def run(self):
                return super().run()

            def stop(self):
                return Base.stop(self)

            def pause(self):
                return 0

        def main():
            child = Child()
            return child.run(), child.stop(), child.pause()
    """})
    assert _uses(index, "Base.run") == [(CALL, f"{M}::Child.run")]
    assert _uses(index, "Base.stop") == [(CALL, f"{M}::Child.stop")]
    assert _uses(index, "Base.pause") == []
    assert _uses(index, "Child.pause") == [(CALL, f"{M}::main")]


def test_assignment_overrides_type_set_and_branches_merge(tmp_path):
    index = _index(tmp_path, {M: """
        class A:
            def go(self):
                return 1

            def stay(self):
                return 1

        class B:
            def go(self):
                return 2

            def stay(self):
                return 2

        def override():
            x = A()
            x = B()
            return x.go()

        def branches(flag):
            if flag:
                y = A()
            else:
                y = B()
            return y.stay()
    """})
    assert _uses(index, "B.go") == [(CALL, f"{M}::override")]
    assert _uses(index, "A.go") == []
    assert _uses(index, "A.stay") == _uses(index, "B.stay") == [(CALL, f"{M}::branches")]


def test_tuple_unpacking_follows_position_annotation_and_return_branches(tmp_path):
    index = _index(tmp_path, {M: """
        from typing import Tuple

        class A:
            def ping(self):
                return 1

            def pong(self):
                return 1

            def close(self):
                return 1

        class B:
            def ping(self):
                return 2

            def pong(self):
                return 2

            def close(self):
                return 2

        def annotated(source) -> Tuple[A, B]:
            return source()

        def branched(flag):
            if flag:
                return A(), B()
            return B(), A()

        def main(source, flag):
            _first, second = annotated(source)
            second.ping()
            annotated(source)[0].pong()
            left, _right = branched(flag)
            return left.close()
    """})
    assert _uses(index, "B.ping") == _uses(index, "A.pong") == [(CALL, f"{M}::main")]
    assert _uses(index, "A.ping") == _uses(index, "B.pong") == []
    assert _uses(index, "A.close") == _uses(index, "B.close") == [(CALL, f"{M}::main")]


def test_attribute_receivers_follow_instance_and_dataclass_field_types(tmp_path):
    index = _index(tmp_path, {M: """
        from dataclasses import dataclass

        class Repo:
            def load(self):
                return 1

        class Cache:
            def fetch(self):
                return 2

        class Spare:
            def load(self):
                return 3

        class Service:
            def __init__(self, repo: Repo):
                self.repo = repo

            def run(self):
                return self.repo.load()

        @dataclass
        class Holder:
            cache: Cache

        def main():
            Service(Repo()).run()
            return Holder(Cache()).cache.fetch()
    """})
    assert _uses(index, "Repo.load") == [(CALL, f"{M}::Service.run")]
    assert _uses(index, "Cache.fetch") == [(CALL, f"{M}::main")]
    assert _uses(index, "Spare.load") == []


def test_module_level_instance_import_carries_its_type(tmp_path):
    store = _p("core", "store.py")
    index = _index(tmp_path, {
        store: """
            class Store:
                def get(self):
                    return 1

                def put(self):
                    return 2

            CACHE = Store()
        """,
        _p("core", "user.py"): """
            from core.store import CACHE

            def main():
                return CACHE.get()
        """,
    })
    assert _uses(index, "Store.get", store) == [(CALL, _p("core", "user.py") + "::main")]
    assert _uses(index, "Store.put", store) == []


def test_protocol_parameter_only_reaches_types_that_flow_in(tmp_path):
    index = _index(tmp_path, {M: """
        from typing import Protocol

        class Runner(Protocol):
            def go(self) -> int: ...

        class Real:
            def go(self):
                return 1

        class Lookalike:
            def go(self):
                return 2

        def drive(runner: Runner):
            return runner.go()

        def main():
            return drive(Real())
    """})
    assert _uses(index, "Real.go") == [(CALL, f"{M}::drive")]
    # 结构上满足协议但没有流入的类不算被调用。
    assert _uses(index, "Lookalike.go") == []


def test_generated_init_runs_post_init_only_for_dataclasses(tmp_path):
    index = _index(tmp_path, {M: """
        from dataclasses import dataclass

        @dataclass
        class Item:
            size: int

            def __post_init__(self):
                self.area = self.size * 2

        class Plain:
            def __init__(self, size):
                self.size = size

            def __post_init__(self):
                self.area = self.size * 2

        def main():
            return Item(1), Plain(2)
    """})
    assert _uses(index, "Item.__post_init__") == [(PROTOCOL, f"{M}::main")]
    assert _uses(index, "Plain.__post_init__") == []


def test_post_init_follows_the_decorated_class_at_decoration_time_for_construction_and_replace(tmp_path):
    # CPython 只在装饰那一刻检查 __post_init__：生成初始化的类当时 MRO 上有它，生成的 __init__ 才经 self 调用它。
    index = _index(tmp_path, {M: """
        from dataclasses import dataclass, replace

        class Checked:
            def __post_init__(self):
                self.checked = True

        @dataclass
        class Window(Checked):
            start: int

        class StrictWindow(Window):
            def __post_init__(self):
                self.strict = True

        @dataclass
        class Plain:
            size: int

        class Later(Plain):
            def __post_init__(self):
                self.area = self.size * 2

        class Renewed(Plain):
            def __post_init__(self):
                self.area = 0

        def main(renewed: Renewed):
            return Window(1), StrictWindow(2), Later(3), replace(renewed, size=4)
    """})
    # 继承来的 __post_init__ 在装饰时可见；子类覆写后按实例派发到子类。
    assert _uses(index, "Checked.__post_init__") == [(PROTOCOL, f"{M}::main")]
    assert _uses(index, "StrictWindow.__post_init__") == [(PROTOCOL, f"{M}::main")]
    # Plain 装饰时没有 __post_init__：子类后加的不会被调用，构造与 replace 一样。
    assert _uses(index, "Later.__post_init__") == []
    assert _uses(index, "Renewed.__post_init__") == []


def test_operations_and_external_api_reach_protocol_members_of_typed_operands(tmp_path):
    index = _index(tmp_path, {M: """
        import bisect

        class Rows:
            def __len__(self):
                return 0

            def __getitem__(self, index):
                return index

            def insert(self, index, value):
                return None

            def __add__(self, other):
                return self

            def __neg__(self):
                return self

        class Loose:
            def __len__(self):
                return 0

        def main(unknown):
            rows = Rows()
            bisect.insort(rows, 3)
            len(unknown)
            return rows + rows
    """})
    for member in ("Rows.__len__", "Rows.__getitem__", "Rows.insert", "Rows.__add__"):
        assert _uses(index, member) == [(PROTOCOL, f"{M}::main")], member
    # 接收者类型不明的 len 不给任何同名成员记证据；没被运算用到的协议成员也没有证据。
    assert _uses(index, "Loose.__len__") == []
    assert _uses(index, "Rows.__neg__") == []


def test_iteration_apis_separate_getting_advancing_and_consuming_an_iterator(tmp_path):
    # iter(x) 只取迭代器；推进（next、for、sum/any 等消费型 API）才调用 __next__；
    # iter(callable, sentinel) 由库以零实参反复调用 callable（读子进程输出的 iter(stream.readline, "") 写法）。
    index = _index(tmp_path, {M: """
        class Cursor:
            def __next__(self):
                raise StopIteration

        class Probe:
            def __iter__(self):
                return Cursor()

        class Lines:
            def __iter__(self):
                return LineCursor()

        class LineCursor:
            def __next__(self):
                raise StopIteration

        class Totals:
            def __iter__(self):
                return TotalCursor()

        class TotalCursor:
            def __next__(self):
                raise StopIteration

        class Ticker:
            def __call__(self):
                return 1

            def __iter__(self):
                return iter(())

        class Reader:
            def readline(self):
                return ""

        def peek(probe: Probe):
            return iter(probe)

        def main(lines: Lines, totals: Totals, ticker: Ticker, reader: Reader):
            first = next(iter(lines))
            for chunk in iter(reader.readline, ""):
                print(chunk)
            return first, sum(totals), any(totals), list(iter(ticker, None))
    """})
    assert _uses(index, "Probe.__iter__") == [(PROTOCOL, f"{M}::peek")]
    assert _uses(index, "Cursor.__next__") == []
    assert _uses(index, "LineCursor.__next__") == [(PROTOCOL, f"{M}::main")]
    assert _uses(index, "TotalCursor.__next__") == [(PROTOCOL, f"{M}::main")]
    assert _uses(index, "Ticker.__call__") == [(CALL, f"{M}::main")]
    assert _uses(index, "Ticker.__iter__") == []
    assert _uses(index, "Reader.readline") == [(CALL, f"{M}::main"), (REFERENCE, f"{M}::main")]


def test_reversed_uses_reversed_or_the_sequence_protocol_and_never_iterates_the_original(tmp_path):
    index = _index(tmp_path, {M: """
        class History:
            def __iter__(self):
                return iter(())

            def __reversed__(self):
                return Rewind()

        class Rewind:
            def __iter__(self):
                return self

            def __next__(self):
                raise StopIteration

        class Segments:
            def __len__(self):
                return 0

            def __getitem__(self, index):
                return index

            def __iter__(self):
                return iter(())

        def main(history: History, segments: Segments):
            for entry in reversed(history):
                print(entry)
            return list(reversed(segments))
    """})
    for member in ("History.__reversed__", "Rewind.__iter__", "Rewind.__next__", "Segments.__len__", "Segments.__getitem__"):
        assert _uses(index, member) == [(PROTOCOL, f"{M}::main")], member
    assert _uses(index, "History.__iter__") == []
    assert _uses(index, "Segments.__iter__") == []


def test_reflected_operators_need_unknown_or_different_left_operand(tmp_path):
    # 同类型运算 Python 不试反射；增量赋值先 __iadd__，同样不试反射；左值未知时右操作数的反射方法可能被调用。
    index = _index(tmp_path, {M: """
        class Vector:
            def __add__(self, other):
                return self

            def __radd__(self, other):
                return self

        class Tally:
            def __iadd__(self, other):
                return self

            def __radd__(self, other):
                return self

        class Amount:
            def __radd__(self, other):
                return self

        def main(vector: Vector, tally: Tally, amount: Amount, total):
            doubled = vector + vector
            tally += Tally()
            return doubled, tally, total + amount
    """})
    assert _uses(index, "Vector.__add__") == [(PROTOCOL, f"{M}::main")]
    assert _uses(index, "Tally.__iadd__") == [(PROTOCOL, f"{M}::main")]
    assert _uses(index, "Amount.__radd__") == [(PROTOCOL, f"{M}::main")]
    assert _uses(index, "Vector.__radd__") == []
    assert _uses(index, "Tally.__radd__") == []


def test_external_api_operands_are_bound_by_parameter_name(tmp_path):
    # Python 3.8 的 bisect.insort(a, x, ...) 接受关键字实参：操作数按形参名取，不按位置猜。
    index = _index(tmp_path, {M: """
        import bisect

        class Rows:
            def __len__(self):
                return 0

            def __getitem__(self, index):
                return index

            def insert(self, index, value):
                return None

        class Marker:
            def __len__(self):
                return 0

            def insert(self, index, value):
                return None

        def main(rows: Rows, plain):
            bisect.insort(x=3, a=rows)
            bisect.insort(plain, x=Marker())
    """})
    for member in ("Rows.__len__", "Rows.__getitem__", "Rows.insert"):
        assert _uses(index, member) == [(PROTOCOL, f"{M}::main")], member
    assert _uses(index, "Marker.__len__") == _uses(index, "Marker.insert") == []


def test_starred_arguments_spread_elements_into_every_parameter_they_can_reach(tmp_path):
    # *x 展开成个数不定的位置实参：取值是 x 的元素；排在全部具名形参之后时进 *args，前面还有具名形参时它与其后的
    # 实参可能落在任一剩余形参上，排在它前面的实参落点不变（starts, ends = zip(*segs) 是 downtime 里的写法）。
    index = _index(tmp_path, {M: """
        from typing import List, Tuple

        class Row:
            def __str__(self):
                return ""

            def draw(self):
                return None

        class Footer:
            def draw(self):
                return None

        class Start:
            def shift(self):
                return None

        class End:
            def close(self):
                return None

        class Head:
            def lead(self):
                return None

        class Middle:
            def lead(self):
                return None

            def finish(self):
                return None

        class Tail:
            def lead(self):
                return None

            def finish(self):
                return None

        def render(*parts):
            for part in parts:
                part.draw()

        def arrange(head, body, tail):
            head.lead()
            return tail.finish()

        def main(rows: List[Row], segments: List[Tuple[Start, End]], middles: List[Middle]):
            print(*rows)
            render(*rows, Footer())
            starts, ends = zip(*segments)
            for start in starts:
                start.shift()
            for end in ends:
                end.close()
            return arrange(Head(), *middles, Tail())
    """})
    assert _uses(index, "Row.__str__") == [(PROTOCOL, f"{M}::main")]
    assert _uses(index, "Row.draw") == _uses(index, "Footer.draw") == [(CALL, f"{M}::render")]
    assert _uses(index, "Start.shift") == _uses(index, "End.close") == [(CALL, f"{M}::main")]
    assert _uses(index, "Middle.finish") == _uses(index, "Tail.finish") == [(CALL, f"{M}::arrange")]
    assert _uses(index, "Head.lead") == [(CALL, f"{M}::arrange")]
    assert _uses(index, "Middle.lead") == _uses(index, "Tail.lead") == []


def test_external_calls_return_every_value_python_may_hand_back(tmp_path):
    # getattr / next / min / max 取不到时原样返回 default；min / max 收到多个位置实参时返回其中之一。
    index = _index(tmp_path, {M: """
        from typing import List

        class Item:
            pass

        class Missing:
            def label(self):
                return ""

        class Exhausted:
            def label(self):
                return ""

        class Lowest:
            def label(self):
                return ""

        class First:
            def rank(self):
                return 1

        class Second:
            def rank(self):
                return 2

        def main(items: List[Item], target: Item):
            getattr(target, "label", Missing()).label()
            next(iter(items), Exhausted()).label()
            min(items, default=Lowest()).label()
            return max(First(), Second()).rank()
    """})
    for member in ("Missing.label", "Exhausted.label", "Lowest.label", "First.rank", "Second.rank"):
        assert _uses(index, member) == [(CALL, f"{M}::main")], member


def test_external_callbacks_follow_real_base_chain_and_exact_names(tmp_path):
    index = _index(tmp_path, {M: """
        from html.parser import HTMLParser
        from http.server import HTTPServer
        from socketserver import BaseServer
        from typing import Dict

        import pytest

        class Table(Dict[str, str]):
            def __str__(self):
                return ""

        class Parser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                return None

            def handle_banana(self):
                return None

        class Server(HTTPServer):
            def handle_error(self, request, client_address):
                return None

            def server_bind(self):
                return None

        class Loop(BaseServer):
            def server_bind(self):
                return None

            def service_actions(self):
                return None

        class NotAParser:
            def handle_starttag(self, tag, attrs):
                return None

        class Plugin:
            def pytest_collection_modifyitems(self, items):
                return None

            def pytest_not_a_hook(self):
                return None

        def run():
            return pytest.main(["-q"], plugins=[Plugin()])
    """})
    assert _uses(index, "Parser.handle_starttag") == [(CALLBACK, "<module>")]
    # HTTPServer -> TCPServer -> BaseServer：继承链从已安装的库读取。
    assert _uses(index, "Server.handle_error") == [(CALLBACK, "<module>")]
    # 绑定由 TCPServer.__init__ 调用：HTTPServer 的子类有，直接继承 BaseServer 的没有。
    assert _uses(index, "Server.server_bind") == _uses(index, "Loop.service_actions") == [(CALLBACK, "<module>")]
    assert _uses(index, "Loop.server_bind") == []
    assert _uses(index, "Plugin.pytest_collection_modifyitems") == [(PROTOCOL, f"{M}::run")]
    assert _uses(index, "Parser.handle_banana") == []
    # typing 的泛型别名作基类时按它代表的类（dict）读继承链，不是 BaseException，__str__ 不是回调。
    assert _uses(index, "Table.__str__") == []
    assert _uses(index, "NotAParser.handle_starttag") == []
    assert _uses(index, "Plugin.pytest_not_a_hook") == []


def test_wsgi_app_assigned_on_flask_instances_is_called_iterated_and_closed(tmp_path):
    # 三种真实接入：闭包、带 __call__ 的实例、工厂函数返回的实例；接收者经构造、注解或仓库子类得到 Flask 身份。
    index = _index(tmp_path, {M: """
        import types
        from typing import Any

        from flask import Flask

        class Body:
            def __iter__(self):
                return self

            def __next__(self):
                raise StopIteration

            def close(self):
                return None

        class Transport:
            def __init__(self, application):
                self.application = application

            def __call__(self, environ, start_response):
                return self.application(environ, start_response)

        class Never:
            def __iter__(self):
                return iter(())

        class Holder:
            wsgi_app = None

        class App(Flask):
            pass

        def wrap(app):
            def wsgi(environ, start_response):
                return Body()
            app.wsgi_app = wsgi

        def install(app: Flask):
            app.wsgi_app = Transport(app.wsgi_app)

        def recovery_app():
            return Transport(None)

        def subclassed():
            App(__name__).wsgi_app = recovery_app()

        def stray(environ, start_response):
            return Never()

        def elsewhere(app: Flask, holder: Holder, loose: Any):
            app.json_handler = stray
            holder.wsgi_app = stray
            types.SimpleNamespace().wsgi_app = stray
            loose.wsgi_app = stray

        def main():
            app = Flask(__name__)
            wrap(app)
            install(app)
    """})
    assert _uses(index, "wrap.<locals>.wsgi") == [(CALL, f"{M}::wrap"), (REFERENCE, f"{M}::wrap")]
    (binding,) = [ref.binding for ref in index.references[f"{M}::wrap.<locals>.wsgi"] if ref.kind == CALL]
    assert binding is not None and binding.decidable
    assert [name for name, _ in binding.arguments] == ["environ", "start_response"]
    for member in ("Body.__iter__", "Body.__next__", "Body.close"):
        assert _uses(index, member) == [(PROTOCOL, f"{M}::wrap")], member
    assert _uses(index, "Transport.__call__") == [(CALL, f"{M}::install"), (CALL, f"{M}::subclassed")]
    # 别的外部属性、仓库对象的同名属性、不是 Flask 的外部对象、类型未知（Any）的接收者都不调用存进去的值；
    # 没有接入的可迭代类仍无证据。
    assert _uses(index, "stray") == [(REFERENCE, f"{M}::elsewhere")]
    assert _uses(index, "Never.__iter__") == []


def test_external_class_instances_flow_through_fields_and_other_external_values_stay_unknown(tmp_path):
    # 外部类的实例（注解给出，或调用外部类得到，含模块级 __getattr__ 惰性给出的 ThreadPoolExecutor）存进字段后，
    # 字段照常解析、身份随值流动：经 self.app 接入 wsgi_app 同样被库调用（RequestFrame 把 app 存进字段的写法）。
    # 外部函数与途经类成员的名字（json.loads、datetime.now）返回值类型未知，存进字段后读取记为未解析；
    # 外部实例的成员一律不跟踪。
    index = _index(tmp_path, {M: """
        import json
        from concurrent.futures import ThreadPoolExecutor
        from datetime import datetime

        from flask import Flask

        class Body:
            def __iter__(self):
                return self

            def __next__(self):
                raise StopIteration

        def handler(environ, start_response):
            return Body()

        class Frame:
            def __init__(self, app: Flask, raw):
                self.app = app
                self.pool = ThreadPoolExecutor(max_workers=1)
                self.payload = json.loads(raw)
                self.started = datetime.now()

            def install(self):
                self.app.wsgi_app = handler

            def report(self):
                return self.pool, self.payload, self.started, self.pool.submit

        def main():
            Frame(Flask(__name__), "{}").install()
    """})
    assert _uses(index, "handler") == [(CALL, f"{M}::Frame.install"), (REFERENCE, f"{M}::Frame.install")]
    assert _uses(index, "Body.__iter__") == [(PROTOCOL, f"{M}::Frame.install")]
    unresolved = index.unresolved_attributes
    assert "app" not in unresolved and "pool" not in unresolved
    for name in ("payload", "started", "submit"):
        assert [site.line for site in unresolved[name]], name


def test_nested_functions_resolve_through_lexical_scope(tmp_path):
    index = _index(tmp_path, {M: """
        class Tool:
            def use(self):
                return 1

        def helper():
            return 0

        def outer():
            tool = Tool()

            def helper():
                return tool.use()

            return helper()
    """})
    assert _uses(index, "outer.<locals>.helper") == [(CALL, f"{M}::outer")]
    assert _uses(index, "Tool.use") == [(CALL, f"{M}::outer.<locals>.helper")]
    assert _uses(index, "helper") == []


def test_decorators_count_only_when_they_take_the_function(tmp_path):
    index = _index(tmp_path, {M: """
        import atexit

        def register(fn):
            fn()
            return fn

        @atexit.register
        def on_exit():
            return None

        @register
        def repo_decorated():
            return None

        class Holder:
            @staticmethod
            def quiet():
                return None
    """})
    assert _uses(index, "on_exit") == [(DECORATOR, "<module>")]
    # 仓库装饰器按真实调用展开：在 register 里被调用一次，又作为返回值逃逸一次。
    assert _uses(index, "repo_decorated") == [(CALL, f"{M}::register"), (REFERENCE, f"{M}::register")]
    assert _uses(index, "Holder.quiet") == []


def test_binder_binds_receiver_keywords_and_defaults_and_rejects_unknowable_calls():
    function = ast.parse("def f(self, a, b=1, *, key, opt=2):\n    pass").body[0]
    assert isinstance(function, ast.FunctionDef)
    signature = signature_of(function.args, exact=True)

    def call(source, bound=True):
        node = ast.parse(source, mode="eval").body
        assert isinstance(node, ast.Call)
        return bind(signature, node.args, node.keywords, bound=bound)

    binding = call("obj.f(10, key=20)")
    assert binding.decidable and binding.receiver == "self"
    assert [name for name, _ in binding.arguments] == ["a", "key"]
    assert binding.defaulted == ("b", "opt")
    # 调用处 *args / **kwargs、缺必填关键字、重复赋值都不可判定。
    assert not call("obj.f(*values, key=1)").decidable
    assert not call("obj.f(1, **options)").decidable
    assert not call("obj.f(1)").decidable
    assert not call("obj.f(1, a=2, key=3)").decidable
    # 不经实例调用时 self 是普通位置形参。
    unbound = call("Cls.f(obj, 1, key=2)", bound=False)
    assert unbound.decidable and unbound.receiver is None
    assert [name for name, _ in unbound.arguments] == ["self", "a", "key"]
    # *values 之后的位置实参落点不定：每个可能落到的形参都记一项，整个绑定不可判定。
    spread = call("obj.f(*values, 5, key=1)")
    assert not spread.decidable
    assert [(name, type(expr).__name__) for name, expr in spread.arguments] == [
        ("a", "Starred"), ("a", "Constant"), ("b", "Starred"), ("b", "Constant"), ("key", "Constant"),
    ]


def test_reference_index_reports_bindings_escapes_unresolved_attributes_and_variable_context(tmp_path):
    index = _index(tmp_path, {M: """
        LIMIT = 3

        def handler(value, *, scale=1):
            return value * scale

        def setup(item):
            global LIMIT
            callbacks = [handler]
            item.zz_mystery()
            LIMIT = 4
            return callbacks, handler(LIMIT)

        def untouched():
            return None
    """})
    refs = {ref.kind: ref for ref in index.references[f"{M}::handler"]}
    assert set(refs) == {CALL, REFERENCE}
    binding = refs[CALL].binding
    assert binding is not None and binding.decidable and binding.defaulted == ("scale",)
    assert refs[REFERENCE].binding is None
    assert [(site.name, site.line) for site in index.unresolved_attributes["zz_mystery"]] == [("zz_mystery", 9)]
    variable = sorted((ref.kind, ref.line, type(ref.context[0]).__name__) for ref in index.references[f"{M}::LIMIT"])
    assert variable == [(LOAD, 11, "Call"), (STORE, 1, "Assign"), (STORE, 10, "Assign")]
    assert index.functions[f"{M}::handler"].signature.kwonly == ("scale",)
    # 没有引用的函数不出现在引用表里。
    assert f"{M}::untouched" not in index.references


def test_reference_index_keeps_every_binding_variant_of_one_call_site(tmp_path):
    # 同一调用点经实例与经类取到同一方法：实参对到的形参不同，两种绑定都留在索引里。
    index = _index(tmp_path, {M: """
        class C:
            def f(self, x=False, y=False):
                return x, y

        def main(choose):
            c = C()
            return (c.f if choose else C.f)(True)
    """})
    shapes = []
    for ref in index.references[f"{M}::C.f"]:
        assert ref.kind == CALL and ref.binding is not None
        shapes.append((ref.binding.receiver, tuple(name for name, _ in ref.binding.arguments)))
    assert len(shapes) == 2 and set(shapes) == {(None, ("self",)), ("self", ("x",))}


def _origins(index, name, rel=M):
    """目标的引用：(种类, 引用所在函数, 证据来源)。"""
    return sorted({(ref.kind, ref.source_qual, ref.origin) for ref in index.references.get(f"{rel}::{name}", ())})


T = _p("tests", "test_m.py")


def test_types_only_tests_pass_in_give_test_evidence_even_inside_production_code(tmp_path):
    # 生产 helper 只拿到生产传入的 Rows；Pages 只有测试传进来，它经 helper 形成的协议引用是测试证据。
    files = {
        M: """
            class Rows:
                def __len__(self):
                    return 0

            class Pages:
                def __len__(self):
                    return 1

            def count(items):
                return len(items)

            def total():
                return count(Rows())
        """,
        T: """
            from core.m import Pages, count

            def test_count():
                assert count(Pages()) == 1
        """,
    }
    index = _index(tmp_path, files)
    assert _origins(index, "Rows.__len__") == [(PROTOCOL, f"{M}::count", PRODUCTION)]
    assert _origins(index, "Pages.__len__") == [(PROTOCOL, f"{M}::count", TEST)]
    assert _origins(index, "count") == [(CALL, f"{M}::total", PRODUCTION), (CALL, f"{T}::test_count", TEST)]
    # 扫描器只认生产证据：Pages.__len__ 只靠测试续命，列为 test_only，证据位置在生产 helper 里。
    assert scanner.scan(str(tmp_path))["entries"] == [
        {"path": f"{M}::Pages.__len__", "kind": "test_only", "count": 1, "test_refs": [f"{M}:10"]},
    ]


def test_default_factories_and_container_constructors_build_containers_production_fills(tmp_path):
    # dataclass 的 field(default_factory=list/dict) 每个实例一个新容器，与不带实参的 list()/dict() 一样之后可被改写；
    # 生产代码 append 进去的阶段经同一字段被消费（schedule_shared_optimizer 的 view.stages 写法）。
    index = _index(tmp_path, {M: """
        from dataclasses import dataclass, field
        from typing import Dict, List

        class Stage:
            def unavailable_reason(self):
                return None

        class WarmStage(Stage):
            def unavailable_reason(self):
                return "finished"

        class Charge:
            def seconds(self):
                return 0.0

        class Note:
            def text(self):
                return ""

        @dataclass
        class View:
            stages: List[Stage] = field(default_factory=list)
            charged: Dict[int, Charge] = field(default_factory=dict)

        def prepare(view: View):
            view.stages.append(WarmStage())
            view.charged[0] = Charge()

        def reasons(view: View):
            return [stage.unavailable_reason() for stage in view.stages], [c.seconds() for c in view.charged.values()]

        class Tag:
            def text(self):
                return ""

        def notes():
            found = list()
            found.append(Note())
            by_name = dict()
            by_name["first"] = Tag()
            return [note.text() for note in found], [tag.text() for tag in by_name.values()]
    """})
    assert _uses(index, "WarmStage.unavailable_reason") == [(CALL, f"{M}::reasons")]
    assert _uses(index, "Charge.seconds") == [(CALL, f"{M}::reasons")]
    assert _uses(index, "Note.text") == _uses(index, "Tag.text") == [(CALL, f"{M}::notes")]


def test_consuming_apis_apply_their_element_operations(tmp_path):
    # any/all 对元素做真值测试，sum 从 0 起累加（先 __radd__，之后上一次的和 + 元素），min/max/sorted 两两比较
    # （给了 key 时比较 key 的返回值，元素本身不比），in 逐个元素与被测值做 ==。
    index = _index(tmp_path, {M: """
        from typing import List

        class Flag:
            def __bool__(self):
                return True

        class Cost:
            def __radd__(self, other):
                return self

            def __add__(self, other):
                return self

        class Rank:
            def __lt__(self, other):
                return True

            def __gt__(self, other):
                return False

        class Task:
            def __lt__(self, other):
                return True

        class Member:
            def __eq__(self, other):
                return True

        def rank_of(task: Task) -> Rank:
            return Rank()

        def main(flags: List[Flag], costs: List[Cost], ranks: List[Rank], tasks: List[Task], members: List[Member], wanted):
            ready = any(flags) and all(flags)
            total = sum(costs)
            lowest = min(ranks)
            ordered = sorted(tasks, key=rank_of)
            return ready, total, lowest, ordered, wanted in members
    """})
    for member in ("Flag.__bool__", "Cost.__radd__", "Cost.__add__", "Rank.__lt__", "Rank.__gt__", "Member.__eq__"):
        assert _uses(index, member) == [(PROTOCOL, f"{M}::main")], member
    assert _uses(index, "rank_of") == [(CALL, f"{M}::main"), (REFERENCE, f"{M}::main")]
    assert _uses(index, "Task.__lt__") == []


def test_list_sort_compares_like_sorted(tmp_path):
    # list.sort 与 sorted 同一规则：新建列表与序列副本的元素两两用 < 比较；给了 key 时库以每个元素调用 key、
    # 比较 key 的返回值，元素本身不比。
    index = _index(tmp_path, {M: """
        from typing import List

        class Slot:
            def __lt__(self, other):
                return True

        class Rank:
            def __lt__(self, other):
                return True

        class Job:
            def __lt__(self, other):
                return True

        def rank_of(job: Job) -> Rank:
            return Rank()

        def main(jobs: List[Job]):
            slots = []
            slots.append(Slot())
            slots.sort()
            queue = list(jobs)
            queue.sort(key=rank_of, reverse=True)
            return slots, queue
    """})
    assert _uses(index, "Slot.__lt__") == _uses(index, "Rank.__lt__") == [(PROTOCOL, f"{M}::main")]
    assert _uses(index, "rank_of") == [(CALL, f"{M}::main"), (REFERENCE, f"{M}::main")]
    assert _uses(index, "Job.__lt__") == []


def test_protocol_calls_pass_their_operands_into_parameters(tmp_path):
    # 解释器调用协议方法时把另一操作数、下标、被测值作实参交给它：方法体里对实参的调用由此得到证据。
    index = _index(tmp_path, {M: """
        class Result:
            def finish(self):
                return 1

        class Key:
            def result(self):
                return Result()

        class Table:
            def __getitem__(self, key):
                return key.result()

        class Right:
            def work(self):
                return 1

        class Left:
            def __add__(self, other):
                return other.work()

        class Item:
            def check(self):
                return True

        class Bag:
            def __contains__(self, item):
                return item.check()

        def main():
            return Table()[Key()].finish(), Left() + Right(), Item() in Bag()
    """})
    assert _uses(index, "Key.result") == [(CALL, f"{M}::Table.__getitem__")]
    assert _uses(index, "Result.finish") == [(CALL, f"{M}::main")]
    assert _uses(index, "Right.work") == [(CALL, f"{M}::Left.__add__")]
    assert _uses(index, "Item.check") == [(CALL, f"{M}::Bag.__contains__")]


def test_operator_values_are_what_the_protocol_methods_return(tmp_path):
    # 一元运算、abs/round/copy.copy 与增量赋值的值是被调方法的返回值；__iadd__ 换了类型后旧类的方法不再被调用；
    # 内置列表原地 += 仍是同一个列表。
    index = _index(tmp_path, {M: """
        import copy

        class Result:
            def live(self):
                return 1

        class Operand:
            def __neg__(self):
                return Result()

            def __abs__(self):
                return Result()

            def __round__(self, ndigits=None):
                return Result()

            def __copy__(self):
                return Result()

        class Draft:
            def __iadd__(self, other):
                return Final()

            def finish(self):
                return "draft"

        class Final:
            def finish(self):
                return "final"

        class Entry:
            def run(self):
                return None

        def main():
            values = [(-Operand()).live(), abs(Operand()).live(), round(Operand(), 2).live(), copy.copy(Operand()).live()]
            document = Draft()
            document += "tail"
            entries = []
            entries += [Entry()]
            return values, document.finish(), [entry.run() for entry in entries]
    """})
    assert _uses(index, "Result.live") == [(CALL, f"{M}::main")]
    assert _uses(index, "Final.finish") == [(CALL, f"{M}::main")]
    assert _uses(index, "Draft.finish") == []
    assert _uses(index, "Entry.run") == [(CALL, f"{M}::main")]


def test_in_place_set_operators_add_the_right_side_elements(tmp_path):
    # 新建集合的 |= 与 ^= 和列表 += 同一规则：原地把右边的元素加进去，集合仍是同一个；-= 只去掉元素。
    index = _index(tmp_path, {M: """
        class Plan:
            def publish(self):
                return 1

        class Flip:
            def apply(self):
                return 1

        class Gone:
            def cleanup(self):
                return 1

        def pending():
            return [Plan()]

        def main():
            seen = set()
            seen |= set(pending())
            toggled = set()
            toggled ^= {Flip()}
            kept = set()
            kept -= {Gone()}
            return [plan.publish() for plan in seen], [flip.apply() for flip in toggled], [gone.cleanup() for gone in kept]
    """})
    assert _uses(index, "Plan.publish") == _uses(index, "Flip.apply") == [(CALL, f"{M}::main")]
    assert _uses(index, "Gone.cleanup") == []


def test_percent_formatting_calls_what_each_conversion_needs(tmp_path):
    # %r 只调 __repr__，%d/%f 走数值转换，映射形式按键经 __getitem__ 取值；格式串不是常量时各种转换都可能。
    index = _index(tmp_path, {M: """
        class Shown:
            def __str__(self):
                return "s"

            def __repr__(self):
                return "r"

        class Count:
            def __int__(self):
                return 1

            def __float__(self):
                return 1.0

            def __str__(self):
                return "1"

        class Shelf:
            def __getitem__(self, key):
                return Shown()

        class Loose:
            def __str__(self):
                return "s"

            def __repr__(self):
                return "r"

        def render(shown: Shown, count: Count, shelf: Shelf, loose: Loose, template):
            return "%r" % shown, "%d items, %.1f%%" % (count, count), "%(name)s" % shelf, template % loose
    """})
    assert _uses(index, "Shown.__repr__") == [(PROTOCOL, f"{M}::render")]
    assert _uses(index, "Count.__int__") == _uses(index, "Count.__float__") == [(PROTOCOL, f"{M}::render")]
    assert _uses(index, "Count.__str__") == []
    assert _uses(index, "Shelf.__getitem__") == [(PROTOCOL, f"{M}::render")]
    # Shelf 交出的 Shown 按 %s 取 __str__。
    assert _uses(index, "Shown.__str__") == [(PROTOCOL, f"{M}::render")]
    assert _uses(index, "Loose.__str__") == _uses(index, "Loose.__repr__") == [(PROTOCOL, f"{M}::render")]


def _protocol_lines(index, name):
    """协议证据所在的行：一个夹具里每行一种写法，按行锁住每条路径各自给出了证据。"""
    return sorted({ref.line for ref in index.references.get(f"{M}::{name}", ()) if ref.kind == PROTOCOL})


def test_sets_and_dicts_hash_what_they_store_or_look_up(tmp_path):
    # 新建的集合与字典插入元素或键（字面量、add、下标写入、update、set(x)、推导式）以及按键查找（discard、in、get、
    # 下标读取与删除、字典注解值的下标）时，解释器对元素或键调用 __hash__；元组键逐个元素取哈希。列表的插入与 in 不取哈希。
    index = _index(tmp_path, {M: """
        from typing import Dict, List

        class Key:
            def __init__(self, name):
                self.name = name

            def __hash__(self):
                return hash(self.name)

        class Listed:
            def __hash__(self):
                return 0

        def main(table: Dict[Key, int], collected: List[Key], wanted: Key):
            members = {Key("a")}
            members.add(Key("b"))
            members.discard(wanted)
            by_key = {}
            by_key[Key("d")] = 1
            by_key.update(zip(collected, range(3)))
            unique = set(collected)
            probed = wanted in members
            fetched = by_key.get(wanted)
            paired = by_key[(wanted, 1)]
            annotated = table[wanted]
            del by_key[wanted]
            positions = {key: 1 for key in collected}
            listed = [Listed()]
            return members, unique, probed, fetched, paired, annotated, positions, Listed() in listed
    """})
    assert _protocol_lines(index, "Key.__hash__") == [15, 16, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27]
    assert _uses(index, "Listed.__hash__") == []


def test_text_of_builtin_containers_takes_the_repr_of_every_element(tmp_path):
    # print、f-string、str、repr、% 格式化作用在内置容器上时，容器对每个元素取 repr（字典的键与值都取，嵌套容器
    # 逐层展开），不调元素的 __str__；直接格式化实例本身才走 __str__。
    index = _index(tmp_path, {M: """
        from typing import Dict, List

        class Step:
            def __str__(self):
                return "step"

            def __repr__(self):
                return "Step()"

        def render(steps: List[Step], by_name: Dict[str, Step], step: Step):
            print(steps)
            shown = f"{[step]}"
            text = str(by_name)
            nested = repr(((step,), {"k": [step]}))
            keyed = "%s" % ({step: 1},)
            return shown, text, nested, keyed, f"{step}"
    """})
    assert _protocol_lines(index, "Step.__repr__") == [11, 12, 13, 14, 15]
    assert _protocol_lines(index, "Step.__str__") == [16]


def test_attributes_of_external_objects_are_values_not_new_symbols(tmp_path):
    # logging.root 是实例：它的属性不再拼成新的外部符号，反复向上取 parent 的字段因此收敛，访问记为未解析。
    index = _index(tmp_path, {M: """
        import logging

        class Chain:
            def __init__(self):
                self.logger = logging.root

            def climb(self):
                self.logger = self.logger.parent
                return self.logger
    """})
    assert [(site.name, site.line) for site in index.unresolved_attributes["parent"]] == [("parent", 8)]


def test_attribute_chains_around_module_alias_cycles_converge(tmp_path):
    # os.path.os 就是 os：沿别名环反复取属性只在这两个真实模块的符号之间转，传播收敛，每次访问都已解析。
    # 读不到的模块（本机没装的库）是叶子，它的属性不再拼成新符号，访问记为未解析。
    index = _index(tmp_path, {M: """
        import os
        import zz_not_installed

        root = os
        missing = zz_not_installed

        def step():
            global root, missing
            root = root.path.os
            missing = missing.child

        step()
    """})
    unresolved = index.unresolved_attributes
    assert "path" not in unresolved and "os" not in unresolved
    assert [site.line for site in unresolved["child"]] == [10]
    assert _uses(index, "step") == [(CALL, "<module>")]


def test_aliases_of_one_real_module_or_class_share_its_symbol(tmp_path):
    # 同一个真实模块或类只有一个外部符号：经变量别名到达、经别的模块转出（dataclasses 导入的 builtins 就是 builtins
    # 模块，typing.Text 就是 str），都按它自己的身份对上外部 API 表，协议成员照常得到证据。
    index = _index(tmp_path, {M: """
        import builtins
        import dataclasses
        from typing import Text

        class Rows:
            def __len__(self):
                return 0

        class Pages:
            def __len__(self):
                return 0

        class Label:
            def __str__(self):
                return "label"

        def size(rows: Rows, pages: Pages):
            native = builtins
            return native.len(rows) + dataclasses.builtins.len(pages)

        def render(label: Label):
            return Text(label)
    """})
    assert _uses(index, "Rows.__len__") == [(PROTOCOL, f"{M}::size")]
    assert _uses(index, "Pages.__len__") == [(PROTOCOL, f"{M}::size")]
    assert _uses(index, "Label.__str__") == [(PROTOCOL, f"{M}::render")]


def test_imports_under_repository_packages_are_never_read_as_installed_libraries(tmp_path, monkeypatch):
    # 首段是仓库包的导入目标属于仓库：没有索引到的（被忽略的本机文件导入已删除的模块）不知道指向什么，
    # 也不会被当成已安装的库去导入执行。
    imported = []
    import_module = importlib.import_module

    def spy(name, package=None):
        imported.append(name)
        return import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", spy)
    index = _index(tmp_path, {
        _p("tools", "__init__.py"): "",
        M: """
            from core.gone import helper
            import tools.gone as gone_tools

            def main():
                helper()
                return gone_tools.run()
        """,
    })
    assert not [name for name in imported if name.partition(".")[0] in ("core", "tools")]
    assert [site.line for site in index.unresolved_attributes["run"]] == [6]


@pytest.fixture
def library(tmp_path, monkeypatch):
    """仓库外的库：写进被扫描仓库（tmp_path/repo）以外的 site 目录并放上 sys.path；结束时移除它们登记的模块。"""
    registered = []

    def install(files, modules):
        for rel, text in files.items():
            _write(tmp_path / "site", rel, text)
        monkeypatch.syspath_prepend(str(tmp_path / "site"))
        registered.extend(modules)

    yield install
    for name in registered:
        sys.modules.pop(name, None)


def test_classes_of_dynamic_modules_without_spec_keep_their_identity(tmp_path, library):
    # 外部库新建 ModuleType 登记进 sys.modules（没有 __spec__），在里面定义类再导出：读回声明全名时直接用已加载的模块，
    # 类仍是命名空间，仓库子类经它的真实继承链得到库的回调。
    library({"zz_generated_lib.py": """
        import sys
        from types import ModuleType

        generated = ModuleType("zz_generated_namespace")
        exec("from html.parser import HTMLParser\\nclass Public(HTMLParser):\\n    pass", generated.__dict__)
        sys.modules[generated.__name__] = generated
        Public = generated.Public
    """}, ["zz_generated_lib", "zz_generated_namespace"])
    index = _index(tmp_path / "repo", {M: """
        from zz_generated_lib import Public

        class Child(Public):
            def handle_data(self, data):
                return data
    """})
    assert _uses(index, "Child.handle_data") == [(CALLBACK, "<module>")]


def test_repository_scripts_put_on_sys_path_are_never_imported(tmp_path, monkeypatch):
    # 测试把仓库里的脚本目录加进 sys.path 再导入（.codestable/tools 的写法）：模块来源在仓库里，不是已安装的库，
    # 扫描器不导入它，名字没有外部符号，访问记为未解析。
    repo = tmp_path / "repo"
    _write(repo, _p(".codestable", "tools", "zz_frontmatter.py"), 'raise RuntimeError("仓库脚本被扫描器执行")\n')
    monkeypatch.syspath_prepend(str(repo / ".codestable" / "tools"))
    index = _index(repo, {T: """
        import zz_frontmatter as frontmatter

        def test_parse():
            assert frontmatter.parse("x")
    """})
    assert [site.line for site in index.unresolved_attributes["parse"]] == [4]


def test_declared_names_inside_the_repository_are_never_imported(tmp_path, monkeypatch, library):
    # 外部库的类可以把声明模块写成仓库里的模块（namedtuple 的 module=）：读回声明全名要先判归属，
    # 仓库模块不导入，类按读到它的名字作叶子。
    library({"zz_widgets.py": """
        from collections import namedtuple

        Widget = namedtuple("Widget", "value", module="zz_bridge")
    """}, ["zz_widgets"])
    repo = tmp_path / "repo"
    monkeypatch.syspath_prepend(str(repo))
    index = _index(repo, {
        "zz_bridge.py": 'raise RuntimeError("仓库模块被扫描器执行")\n',
        M: """
            from zz_widgets import Widget

            def build():
                return Widget(1).value
        """,
    })
    assert [site.line for site in index.unresolved_attributes["value"]] == [4]


def test_long_dotted_imports_stop_at_the_first_leaf(tmp_path):
    # 合法的长点分导入（首段就读不到）逐段解析，遇到叶子即结束，不随段数加深调用栈。
    dotted = ".".join(["zz_missing"] * 1100)
    index = _index(tmp_path, {M: f"if False:\n    import {dotted} as deep\n\ndef main():\n    return deep.run()\n"})
    assert [site.line for site in index.unresolved_attributes["run"]] == [5]

---
doc_type: audit-index
audit: 2026-06-30-test-suite-redundancy
scope: tests/ 测试套件"冗余 / 低价值测试"专项审计(maintainability 维度)
created: 2026-06-30
status: active
total_findings: 4
---

# test-suite-redundancy 审计报告

## 范围

- 对象:`tests/` 下全部真实测试文件 **614 个 / 3837 个测试函数 / 约 15.5 万行**(已排除 `_support/`、`_scripts_e2e/`、`_data/`、`__pycache__/` 等辅助目录;`.venv*` 第三方依赖自带测试不计)。
- 维度:只扫 **maintainability — 冗余 / 低价值测试**(重合测试、无意义测试、本该参数化却复制成多个函数)。不扫产品 bug / 安全 / 性能。
- 触发:用户"测试太冗杂,想去掉一些",选定"出完整精简清单、口径适中、先不改代码"。

## 方法(可复现)

1. **唯一真相源**:写了一个零依赖 AST 扫描器(Python 3.8,只读不运行测试),量化每个测试函数的断言数、`raise`/`pytest.raises`、`monkeypatch` 打桩数、空体/平凡断言,并做"完全重复(AST 等价)"与"结构近似重复(变量名/常量归一后骨架等价)"聚类。脚本与数据归档在本目录 `scripts/`(`scan_tests.py`、`group_report.py`、`findings.json`、`groups_by_module.json`),可重跑复核。
   - 关键纠偏:初版把"`def test_x(): main()` 双层委托结构"和"用 `if cond: raise` 代替 `assert` 的风格"误判为无断言,假阳性 42 个;加入**文件内调用闭包** + **`raise` 语句识别**后降到 3 个,确认真相源干净后才进入人工核实。
2. **逐组实读核实**:5 个 subagent(均走 OPUS)分模块打开每组成员的真实函数体对比,按适中口径判定 **MERGE(参数化合并)/ DELETE(可删)/ KEEP(假阳性保留)**,每条带 `file:line`、风险与置信度。

## 总评

**这是一个测试质量很高、几乎没有"垃圾测试"可删的套件;真正的冗余集中在"该用 `@pytest.mark.parametrize` 却复制成了多个独立函数"。**

- **无意义测试 ≈ 0**:空测试体 **0**、永真断言(`assert True` / `assert x==x`)**0**、无任何断言的仅 **3** 个且逐一核实均为 by-design 的"调用不抛异常即通过"契约测试(见 finding-03)。
- **完全重复(AST 一字不差)4 组,无一可直接删**:其中 3 组是"被测对象 / parametrize 契约确实不同"的误导性重复(删了会丢覆盖),1 组并入参数化即可(见 finding-02)。
- **结构近似重复约 40 组可参数化合并**,合并后**覆盖零损失**、预计可减少 **约 600 行**重复测试代码。这属于"行为不变的重构"(走 `cs-refactor`),不是"删测试"(见 finding-01)。
- **跨模块同型断言**(如 `models_domain` 的 `normalize_text` 与另一模块的 Flask 取参器)均为骨架巧合,已核实为独立测试,保留(见 finding-04)。

一句话:**想"砍掉一批测试"基本没有空间;想"瘦身"——把 ~40 组复制粘贴的测试合并成参数化——空间很大且安全。**

## 发现清单

| # | 性质 | 严重度 | 置信度 | 标题 | 文件 |
|---|---|---|---|---|---|
| 1 | maintainability | P2 | high | 约 40 组同文件结构重复,应参数化合并(可省约 600 行,零覆盖损失) | [finding-01.md](finding-01.md) |
| 2 | maintainability | P2 | high | 完全重复(AST 等价)4 组核实:无一可删,3 组是误导性重复 | [finding-02.md](finding-02.md) |
| 3 | maintainability | P2 | medium | 3 个无显式断言测试均为 by-design 契约,可选增强断言 | [finding-03.md](finding-03.md) |
| 4 | maintainability | P2 | high | 已核实的"假阳性"清单(跨文件同型 / 新旧 UI 并存),存档防误删 | [finding-04.md](finding-04.md) |

## 按维度分布

| 性质 | P0 | P1 | P2 | 合计 |
|---|---|---|---|---|
| bug | 0 | 0 | 0 | 0 |
| security | 0 | 0 | 0 | 0 |
| performance | 0 | 0 | 0 | 0 |
| maintainability | 0 | 0 | 4 | 4 |
| arch-drift | 0 | 0 | 0 | 0 |
| **合计** | **0** | **0** | **4** | **4** |

> 全部定为 **P2**:测试冗余是可维护性债务,不影响产品正确性;且 finding-01 的合并是"覆盖零损失"的低风险重构。没有 P0/P1,因为核实中**未发现任何漏测 bug 或名不副实的复制漏改**。

## 下一步建议

- **P2 有空再做(推荐分批,走 `cs-refactor`)**:finding-01 的 ~40 组参数化合并。建议从收益高、风险最低的几组起步:
  1. `web_pages` — `test_page_manual_registry.py` 的 9 个 manual 壳(省 ~48 行,纯委托,最干净)
  2. `gate_meta` — `test_long_gate_cache.py:740/867/1088/1192/1204`(5 组缓存失效,省 ~35 行)
  3. `schedule` — `test_scheduler_batches_page_viewmodel.py:516/556`(函数体逐字相同,拼数据即可)
  4. `migration_db`/`calendar_maintenance`/`gantt` 各 1 组高置信、同文件、docstring 已枚举分支的
- **finding-03**(3 个低断言测试):可选,优先级最低,增强时只加显式断言、不改被测行为。
- **finding-04**:无需动作,仅存档——提醒后续任何人**不要**按"AST 相同 / 结构相似"盲删这些组。
- **时机提醒**:`tests/algorithm/test_optimizer_compare_algorithms_contract.py`、`test_optimizer_benchmark_ratchet_gate.py` 本轮工作区有未提交改动;涉及它们的组结论都是 KEEP、不影响,但若将来要动 finding-01 的合并,务必在工作区干净、合并范围与他人改动不重叠时再做,逐组合并后跑对应测试自证行为不变。

> 合并不减覆盖,但仍属改测试代码:每合并一组,应在该组涉及的测试文件上跑一次(`pytest <file>`)确认通过,再进下一组。本审计只发现、不改代码。

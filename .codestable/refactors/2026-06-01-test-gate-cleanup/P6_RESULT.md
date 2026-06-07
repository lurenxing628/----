# P6 结果 — 测试目录重组 + 命名规范(测试/门禁去冗 A 阶段收尾)

> 状态:**已收官并 push**。分支 `cleanup/p3-main-style-to-pytest`,P6 提交链自 `ff5f305b` 起:14 个实现/迁移 commit(`ff5f305b..017c1920`)+ Phase C 文档 commit(`19ed8c7a` 起,含本报告)。每次 push 后 remote==local 已验。

## 一、做了什么

把 **562 个扁平 `tests/*.py`** 测试文件按模块迁入 `tests/<模块>/` 子目录(参照既有 `tests/scheduler_graph/`),去前缀(`regression_`→`test_`)、收敛后缀。`tests/` 顶层迁后**只余 `conftest.py`**。

### Phase A — 仓库根解析加固(根因前置,文件仍平铺,行为等价)
- 新增 `tests/_support/paths.py`(`REPO_ROOT` marker-walk 到 `pyproject.toml`,depth-independent)+ `tests/_support/__init__.py`。
- 185 个收集型文件:`Path(__file__).resolve().parents[1]` → `from tests._support.paths import REPO_ROOT`(任意子目录深度安全)。
- 21 个 `_scripts_e2e` main-style 脚本:保留自举 sys.path,固定跳数换内联 marker-walk(避免 chicken-and-egg)。
- commit:`d89b462c`(A1)/`d738b103`(A2)/`326f0d27`(A3,对抗审查 4 处 BLOCKING 收口)。

### Phase B — 分模块波次迁移(git mv = 移动 + 去前缀 + 后缀收敛)
14 个一级模块 + `schedule/{service,summary,route_view}` 二级 + `scheduler_graph/` 并入 + `_scripts_e2e/`,共 8 波:

| 波 | 模块 | 文件 | commit |
|----|------|------|--------|
| B1 | migration_db | 17 | `46355e1b` |
| B2 | calendar_maintenance/config/candidate/models_domain | 91 | `b3683673` |
| B3 | algorithm/excel_data_io | 138 | `9ca50d99` |
| B4 | operation_execution/resource_dispatch/scheduler_analysis | 60 | `7cc286e0` |
| B5 | schedule/{service,summary,route_view} | 70 | `89ee6e3c` |
| B6 | web_pages | 47 | `fc103e02` |
| B7 | app_runtime/gantt | 66 | `13728100` |
| B8 | gate_meta/scheduler_graph/_scripts_e2e + 清跨波路径串漂移 | 72 | `a997e4e3` |
| B8-fix | 同步技术债务治理台账 5 个 fixed-debt nodeid | — | `017c1920` |

机器基建(先于 B1):`ca982c8d` 放开 `test_registry` 单层校验(`count("/")==1`→`startswith("tests/")`),允许 helper/target 落子目录;`65687fb2` 落地 `p6_path_map.csv`。

**命名铁律**:去前缀后必须仍匹配 `python_files=["test_*.py","*_test.py","regression_*.py"]`。`kind=script/scaffold/tool`(36 文件)本就 0 test 函数、不被收集,原名迁入不加 `test_` 前缀。

## 二、不变量(每波后校验,终态)

| 指标 | 基线(ff5f305b) | 终态(017c1920) | 说明 |
|------|------|------|------|
| collect | 3745 | **3745** | 0 静默丢测试;实跑 `--collect-only` rc=0、0 collect error |
| required nodeid | 1790 | **1790** | registry 路径全更新、0 断链 |
| serial | 881 | **770** | 纯合法 false-serial shedding(去 `regression_` 前缀后不再匹配 `tests/regression_*port*.py` 等失效 glob;0 个真串行被误判 parallel,-n4 实证) |
| perf 文件 | 3 | 3 | 不变 |

**B7 根因修复**:`full_test_debt_shards.classify_nodeid` 改按「文件名::测试名」匹配(`tail = name + nodeid[len(path):]`),剥目录段,防 `app_runtime` 含 "runtime" 污染 NODEID glob 误判整目录 serial。

**B8 跨波机器面收尾**:早期波次 machinery 用 curated PY_TARGETS,漏覆盖 pyright config / quality_gate_shared / 散落写死 nodeid 串 → 累积漂移(两边同步陈旧,契约相等性检查未暴露,Phase B 全门禁此前 deferred 才未触发)。B8 改全树扫 `tests/+tools/+scripts/(.py/.json)+2 LIVE 文本`,全 CSV 替换清零(quality_gate_shared 21 + pyright 7 + test_debt_registry/long_gate cache 等 35 + scripts 3)。

## 三、验证与对抗审核

- **全门禁端到端绿**:`run_quality_gate.py --require-clean-worktree --long-gate-cache` → **GATE_EXIT=0**,16/16 步全过(含第 16 步实跑迁移后 `tests/gate_meta/check_quickref_vs_routes.py`),long gate 9 executed 0 failed。
- **holistic 对抗审核 #1**(7 维 finder→对抗验证→完整性批判,28 agent):**0 阻塞**。硬证据:基线与终态都是 542 个 `python_files` 文件 / 3050 个 test 顶层函数,**差额 0**;561 git rename 0 删除(历史保全);跨子目录 basename 全局唯一 0 碰撞;registry/helper 0 断链。
- **修复后再审核 #2**(补 LIVE 强制源漂移维度,25 agent):**0 阻塞**。铁证:**契约三角(`quality_gate_shared.FULL_TEST_DEBT_ALLOWED_ACTIVE_XFAIL_NODEIDS` == `test_debt_registry` seed-meta 键 == 台账 nodeid)逐字一致、全 fixed 模式、零旧路径残留**;`git grep` 全 tools/scripts flat test 路径命中=0。

## 四、交接物(A→B)

- **权威映射**:`p6_path_map.csv`(561 行 `old_path,new_path,module,kind`),覆盖 B 的 dossier 锚点 + A 的 required/startup 两套。
- **B 锚点审计**(只读核查):dossier 全树引用 106 条去重扁平旧路径,**纯 P6 迁移漂移 CSV 100% 覆盖**。106 核销:97 精确命中 + 4 合并改名/命名漂移(近名在 CSV)+ 2 B 待新建 parity/黄金基线(本就无映射)+ 2 真悬空(下条)+ 1 占位示例。详见 ANCHOR-DRIFT SOP §六。
- **2 条真悬空锚点(非 P6 所致,提示 B 单独裁定)**:
  1. `tests/regression_sp06_no_duplicate_defs.py` —— 已在 `7ca42ca4`(P1.1 删 35 个 DROP 死代码测试,**早于 P6**)删除,CSV/磁盘均无。
  2. `tests/regression_scheduler_candidate_py38_contract.py` —— 已废弃,无改名链;现存 py38 扫描器是 `tests/gate_meta/test_scan_py38plus_syntax.py`。
- ANCHOR-DRIFT SOP(`.codestable/audits/2026-06-02-underwater-debt-census/fix-plan/phase4-dep-safety/ANCHOR-DRIFT-2026-06-05-POSTCOMMIT.md` §五)已标注「P6 已落地待 B 执行」。

## 五、已知 minor(非阻塞,留待将来,不在 P6 内修)

- **`tests/regression/` 僵尸空包**:仅含 `"""专项回归测试目录。"""` 的 `__init__.py`、零测试文件,**基线 ff5f305b 既存**(P6 未用未清)。它是 tests/ 树唯一 `__init__.py`(regular package),其余子目录靠 namespace(PEP 420)+ conftest 注入 sys.path 解析——两套 import 机制并存。当前 233 import 0 断链已证可跑通;若日后清理可整目录删。
- **`test_scheduler_wrapper_import_order_contract.py` 归桶**:CSV 归 `excel_data_io`,语义偏 import-order/架构(近 gate_meta)。纯归类瑕疵,不影响 collect/运行;移动=再一次 rename+重锚,无功能收益,故不动。
- **94 文件残留 unused `from pathlib import Path`(F401)**:加固把 `parents[N]` 换成 `REPO_ROOT` 后旧 import 未清;ruff 全局 `ignore=["F401"]` 兜底,不红 gate,无害代码异味。

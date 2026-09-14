---
doc_type: issue-fix
slug: main-merge-pyright-contracts
status: fixed
created: 2026-09-14
summary: 修复 main 合入前门禁发现的七处可选值和进度回调类型错误，保留既有业务边界。
tags: [pyright, scheduler, workbench, quality-gate]
---

# main 合入前的类型合同修复

## 失败现场

- 待合入提交：`fabd2dc42ac266ab4f99738be3b367e7199854df`。
- GitHub 运行：[34795976614](https://github.com/lurenxing628/----/actions/runs/34795976614)。Windows / Python 3.8 上前 11/19 步通过，第 12 步 `python -m pyright -p pyrightconfig.gate.json` 报 7 个错误而结束，未合并 `main`。
- 本地 `.venv/bin/python`（Python 3.8.10）与 Pyright 1.1.406 重现相同的 7 个错误。

## 根因与修复

1. `core/algorithms/greedy/dispatch/sgs.py`：原缓存闭包的定义脱离非空分支，闭包内部无法证明 `cache` 存在。现在只在缓存非空时构造闭包并绑定该对象，保留原评分和复用路径。
2. `core/services/scheduler/run/schedule_candidate_runner.py`：已完成兄弟与准备输入必然成对的约束跨越两个方法，`prepared()` 的返回类型仍可能是 `None`。复用前明确验证准备输入存在，缺失时抛出内部合同错误，不重新搜索掩盖该问题。
3. `core/services/workbench/run_compute.py`：进度回调在三个传递层没有类型声明，经 `callable()` 收窄后返回值仍是 `object`。三个入口统一声明 `Optional[Callable[[int, int], None]]`。
4. `core/models/workbench_system.py`：日志级别归一化没有区分字符串和缺失值的返回合同，查询参数的整体校验也未建立逐项字符串类型。增加 `str -> str`、`None -> None` 重载，展示层明确处理缺失值，查询层逐项验证后写入 `Dict[str, str]`。保留 `WARN -> WARNING`、缺失展示“未读取”、未知展示值原样保留以及非法查询值拒绝的行为。
5. `web/routes/workbench/legacy_presentation.py`：引文循环两次调用正则匹配，第二次结果不能沿用第一次判定。现在保存每轮匹配结果，判空后读取分组。

未修改类型检查配置、门禁要求、运行依赖、数据库结构或静态资源。

## 验证

运行环境为仓库 `.venv/bin/python`，Python 3.8.10。

- `.venv/bin/python -m pyright -p pyrightconfig.gate.json`：**0 errors, 0 warnings**。
- `.venv/bin/python -m pyright -p pyrightconfig.tools.json`：**0 errors, 0 warnings**。
- SGS 缓存等价、候选去重、进度账本三个测试文件：**47 passed / 5.31s**。文件为 `tests/algorithm/test_sgs_score_cache_equivalence.py`、`tests/candidate/test_scheduler_candidate_dedup_contract.py`、`tests/workbench/test_run_progress_ledger.py`。新增故障注入证明：复用输入缺失时明确失败，优化器调用保持 `[0, 250]`，没有额外搜索。
- `.venv/bin/python -m pytest -q tests/workbench/test_round1_host_boundaries.py -k 'query or log_level'`：**25 passed, 6 deselected**，覆盖缺失值、日志别名、未知展示值和非法查询值。
- `.venv/bin/python -m pytest -q tests/web_pages/test_manual_entry_scope.py`：**2 passed**，覆盖真实手册路由、连续引文、下一段边界、空引文和转义。
- `.venv/bin/python -m pytest -q tests/workbench/test_system_maintenance_api.py -k 'operation_log_summary or windows_filter or invalid_log_query'`：**11 passed, 13 deselected**，覆盖日志 API、筛选与导出。
- 合计 **85 个定向测试通过**；8 个修改的 Python 文件 Ruff、`git diff --check` 和 Python 3.8 兼容语法扫描通过。

上述检查基于本地修复工作区，不代表完整门禁通过。按用户要求，本地没有重跑全量门禁；本次提交推送后重新触发 GitHub 必需门禁，待远端检查成功再执行合并。

## 工作区边界

本轮起步工作区干净。按项目要求运行 `symbol_locator` 时自动更新了 6 份已跟踪调用图快照；已将本轮工具输出保存在临时目录，再将这 6 个文件恢复到本轮起步内容。修复提交仅包含 5 个产品文件、3 个现有测试文件和本记录。

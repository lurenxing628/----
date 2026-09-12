---
doc_type: issue-fix
slug: wbui-registry-environment
status: fixed
created: 2026-09-12
summary: 纠正环境合同测试的旧注入点，并移除导致无关PATH追加失效的裸PATH登记。
tags: [workbench, registry, cache, environment]
---

# 工作台登记环境合同收口

本轮两个 daily 失败来自测试注入点过时：真实环境消费者已经使用 `test_registry.SUPPLEMENTAL_REGRESSION_GROUPS` 聚合表，测试却仍修改旧 workbench 子表的模块属性，无法改变已经展开的聚合 tuple。测试的完整环境枚举、supplemental 目标及注入点改为真实聚合入口；原环境变化、无关环境不入指纹、秘密只存散列、owner 与 required/startup 隔离断言保留。

另外一个 serial 失败属于新增登记的实际问题：UI supplemental 将裸 `PATH` 加入指纹，使不影响程序解析的目录尾部追加也使缓存失效。仅删除这一个过度登记字段，保留 `node_executable_realpath`、`node_version` 和其余环境字段；原 `test_full_test_debt_fingerprint_ignores_irrelevant_path_append` 与 required 对应合同均未修改。解析到不同 Node 时仍由既有真实路径和版本探针失效，不改探针实现。

startup 原先就独立声明 `WERKZEUG_RUN_MAIN`。测试以这一明确既有字段区分共享输入，并单独锁定其变化影响 startup、不会进入 required；不从被测 entry 的结果动态推导豁免。新增未匹配 target 的负例及两个新增 registry 源文件的指纹变化检查。

## 验证

- 原仓复现两个旧注入失败：`2 failed / 1.47s`。
- 完整 `test_workbench_cache_environment.py` 160 项、完整 `test_workbench_ui_registry.py` 6 项、完整 `test_long_gate_manifest.py` 149 项及两个原 PATH 合同：**317 passed / 75.58s**。
- 既有 Node overlay PATH、probe memo 完整模块及 startup 共享环境合同：**10 passed / 10.28s**。
- 本机实际执行两个同版本、不同路径的测试 Node：无关 PATH 尾部追加指纹不变，解析到另一 Node 路径时指纹改变。此证据使用两个运行时字段，不登记裸 PATH。
- 3 个修改的 Python 文件 Ruff 通过；元数据文件 pyright 为 0 errors、0 warnings。未修改产品、门禁实现或冻结验证副本，未暂存或提交 root 内容。

日志、JUnit、原始文件散列与 Node 路径实测均在 `/tmp/aps-wbui-implementation-20260912/cache-environment-closure/`。本轮属于原仓局部回归，整仓最终状态由主线程汇总，不表述为 frozen 或 clean-worktree proof。

# 产品工具与本机工作流的边界

产品仓库不再依赖本机 Agent 工作流目录。`AGENTS.md` 是共享的最小入口；个人工作流和历史审计记录继续留本机，不参与产品门禁、打包和测试输入。

| 内容 | 共享位置 |
| --- | --- |
| Win7 打包 | `scripts/windows/package_win7.ps1` |
| 自检、变更检查、启动/查看/显式样例重跑 | `scripts/run_full_selftest.py`、`scripts/post_change_check.py`、`scripts/run_start_and_rerun_route.py` |
| 调用图提取及标准库 helper | `tools/checkup/` |
| 门禁 ratchet 基线 | `tools/baselines/` |
| 文档元数据验证和检索 | `tools/document_metadata/` |
| 源快照校验 helper | `tests/_support/workbench_source/` |
| 冻结工作台验收分母及优化器基准 | `tests/fixtures/workbench_contracts/`、`tests/fixtures/optimizer/` |
| 产品架构、决定、受门禁约束的文档 | `docs/dev/architecture/`、`docs/dev/decisions/`、`docs/dev/roadmaps/` |

调用图和 SCIP 索引默认写到忽略的 `.cache/aps-analysis/`，不写入版本化基线目录。`CHECKUP_CALLGRAPH` 等已有显式覆盖仍有效。搬迁不扩大 ratchet 允许集合；只更新已迁移路径标识并移除已解决的条目，不把历史验收状态提升为当前通过；冻结能力分母保持原始字节和 SHA-256。

启动脚本默认 `start-only`；`view-only` 不启动服务、不写库；`rerun` 必须显式给出 `--db-path`。样例重跑可能改写目标库，仅限明确授权的测试库。运行记录不能替代活进程实际数据库身份的证明。

从干净 checkout 进行测试：安装项目依赖后运行相关 pytest 与正常 pre-push 门禁。不复制本机 Agent 目录、不跳过检查来填补缺失依赖。Windows 打包仍需在支持的 Windows 构建环境完成，macOS 上的路径契约测试不等于 Windows 打包验收。

自检 runner 使用当前统一登记的非浏览器测试套件，不再调用已退役的阶段 smoke 脚本；缺失已登记测试立即失败。`--complex-repeat` 只追加当前 Excel 回归轮次，不替代浏览器或 Windows 打包验证。

浏览器抽样 pre-push 与日常门禁一样，通过 `tools/git_hook_checks.py` 重启到项目 `.venv` 解释器；不能让系统 Python 决定产品数据库、Flask 和 pytest 的版本。显式抽样可运行 `.venv/bin/python tools/git_hook_checks.py run-browser-lane-sample`，缺少项目环境时报错，不退回宿主解释器。

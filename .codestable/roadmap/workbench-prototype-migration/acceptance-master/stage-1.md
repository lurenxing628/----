# 任务 C 第一段交接

- **尚未完成全站验收**。基础分母为 58 族 / 599 原子动作；Main 追加 SH006..009 为 4 族 / 50 补充动作。两份账本保留所有待验项，未把 family、历史原型或组件测试算作通过。
- 范围与执行计划：`plan.md`；动作：`actions.json`、`shared-actions.json`。账本合同真实运行 1 passed / 0.88 秒。
- 新私有测试工厂：`final_master_server_support.py` 仅在当前测试进程组合真实 `LiveRunServer`、完整构建及私有 SQLite；不修改共享 factory/host，所有运行锁和路径仍经原守卫。
- 完整 build、全表快照、刷新与重启入口：`test_final_master_acceptance.py`。目前 `inspect`/`overview`/`resources` 脚本已编写；process/batches 仍待补齐，不能声称可运行完成。
- 新测试/辅助 Python 定点 Ruff 5 文件通过；定点 Pyright 5 文件 0 errors / 0 warnings。此前发现并修正了测试脚手架自己的 `Path + str` 拼接错误；不是产品缺陷。
- 两次实际完整构建失败均保留：`/private/tmp/aps-workbench-live-gzdztu65/full-build.log`、`/private/tmp/aps-workbench-live-xjt9o7xi/full-build.log`。错误是 navigation 新使用的 scrollX/scrollY 未登记为浏览器内建符号。构建失败时未连接业务数据库，隔离违规 0，锁正常释放；未进入浏览器。
- Main 随后已将 scrollX/scrollY 加入 `scripts/workbench/asset_sources.py:143`，**尚未重新构建验证**。当前遵守 5000 同资源正式测量独占窗口，C 暂停新测试、浏览器、build、全树 hash/扫描；本轮所有已启动进程已退出，无遗留 C 服务。
- 旧总览 mock HTTP 组件证据不能用于本轮全站验收；未复用任何未核对哈希的旧 passed。资源旧真实浏览器脚本将用当前完整工厂/构建重新运行，并保留每个脚本来源哈希，不冒称是新编写的验证逻辑。
- B/K/P 尚待实际运行，V 均待 Main 逐动作审视；不存在本轮业务验收通过数。此结论不会因短暂构建失败而虚增产品 bug。
- C 未执行 Git 写操作，未改共享产品、planning、原归档、指定旧预览；Main 已告知其提交 `c0097278` 和 19:23+08 hook 短暂 stash 窗口，后续源漂移会保留重跑。

## 恢复后的首条命令

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-final-master-c-pycache CHECKUP_CALLGRAPH=/tmp/aps-final-master-c-callgraph .venv/bin/python -B -m tests.workbench.test_final_master_acceptance --phase inspect
```

成功后同样前缀运行 `--phase overview`，再 `--phase resources`。必须等 Main 结束独占窗口才运行。

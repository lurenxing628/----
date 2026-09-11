# C: G05 三项旧回归交接

- 状态：工时、资源已通过定点回归；工艺已按 Main 确认修正旧能力断言，但末版尚未证明整项通过。只读与非法来源负边界保留，没有跳过用例或伪造正常接口成功。
- 固定源：`/private/tmp/aps-G05-failure-baseline-NEJgZ8/source`；公共 manifest SHA `ac34f31052f6593d4c4127f33fa4d027d4d14ac034a401d48dfaae48f03db859`。
- 独立副本与日志：`/private/tmp/aps-old-C-regressions.hSsQRk`。仅使用原工作区 Python 3.8 依赖；仓库模块来自独立 source。
- 当前 overlay：该目录 `source-overlay-5.json`，SHA `1540fa1a0a55c29fe11306d018230a7a6776e4907386123be89c77dd0f61635d`。4898 文件逐项 SHA/mode 复核通过，只有下表四个测试文件与公共源不同。
- 四文件封存包：该目录 `C-old3-test-overlay-v5.tar.gz`，SHA `9fcc32f9aced1746a915716df21227d8fc23abdb2363a97d8eea1f59844768fd`；包内四个相对路径、字节、SHA 与 mode 均已逐项核对，不含产品或 F 的文件。相对 v3 只有 `process_live_probe.cjs` 增量。

## 文件

| 原工作区路径 | SHA-256 | 修改 |
| --- | --- | --- |
| `tests/workbench/process_live_probe.cjs` | `34a993969aca5bdfb05998881eb2b92c6a361750017c0513e10436352671de0e` | 核对真实来源/能力并打开新增、导入后取消；显式注入只读能力/非法来源负边界；保留排序、明细、分页及刷新节点点击并核对恢复状态 |
| `tests/workbench/process_quota_widgets_probe.cjs` | `ba23996c32595239e10480e36b8c5e1f2fbb8b0d5d53a155f92b8f3ddbed9592` | 补载真实表头/筛选组件；精确点击校准详情而非新增的零件链接 |
| `tests/workbench/resource_live_probe.cjs` | `9349ed52048a85ca49635649abd061575f69bf384dcb850add2217be4724fb2a` | 精确定位系统主容器；返回时断言 MAT-011 条件恢复，再真实清空搜索，保留原 MAT-001 检查 |
| `tests/workbench/resource_live_server.py` | `b00f33dac9caf59c76b7a374ae7997cf8539ec0d7d36a90eb0c47e7de11a930b` | 接真实 launcher lock、WorkbenchRunRuntime、restore host、RequestHandler；正常停 HTTP/worker 后释放锁 |

`live_server.py` 未改，也未复制 F 的动态版本。公共副本不含 `run_server_management` helper，因此直接复用上述产品生命周期 API，未新增共享 helper 文件。

## 验证

- 原始三项失败在未改测试的独立副本复现，`baseline2.xml`：3 failed。Python 父进程、工艺及资源服务分别观察到 1041/1079/1036 条源码导入，越界为零。更早 `baseline.xml` 的旁路取证输出曾被隔离保护拦住，不作为导入绑定证明；该记录保留。
- 工时：`fix2.xml` 对应条目 PASS。`pytest-fix2/test_process_quota_widgets0/dg-browser-evidence/process-quota-ui.json` SHA `fce202110690c9838ff75d867db5bb1f2f522b4a88aa1b1433b7d4e2b779cc22`；8 场景、8 次刷新、19 个无效合同拒绝、36 图、42 个真实源码组件；丢失响应恢复、锁定/回执及原有数据库保留断言全部通过。该次完整命令为 1 passed / 1 failed，失败的是尚未补齐返回搜索动作的资源条目，不声称整条命令通过。
- 资源：`fix3.xml`，1 passed / 325.96s。根目录 `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-f_gb0ckj`；224 场景、1260 条 POST 响应记录、464 图，原有读写保留断言全部通过，unexpected HTTP/console/request failures 均为空。
- 资源 `resource-probe-results.json` SHA `2554758b57b0a1030b354f505b62f2f6b1d48ae9edd41171dd8c104b43dd11c2`；`resource-run-result.json` SHA `2f1cc3549cc57bd89cff6295cec0714489377f87d8d51686573f1064eeda75f5`。
- 资源 PID 81828 已退出，105 份服务/辅助进程导入记录均无越界，相关 PID 全部结束；`runtime_joined/locks_released/backups_and_templates_unchanged=true`。Ruff 单文件及三份 CJS 语法检查通过。
- 未启动新最终矩阵、344/5000 或完整质量门禁。上述为固定 G05 源加明确测试 overlay 的定点证据，不是 clean-worktree proof。

## 工艺末次结果

- Main 已确认按真实 `create/import=true` 修正旧禁用断言。正常打开/取消走未拦截接口；两个负边界只改真实 GET 响应的能力/来源字段，并记录故障注入，不冒充真实只读服务器。新增动作要求零 POST，原有只读 `route-preview` POST 和全库对比均保留。
- 按本次“一项跑一次”要求执行了 `process-final.xml`：1 failed / 20.86s。根目录 `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-xgz3rl9t`；第一场景通过，第二场景在新增非法来源检查等待错误文案时失败，后面的原工艺场景尚未执行。
- 真实页面先经过 `resource-api.js:99`，文案为“本机资源数据协议不匹配，未使用样例替代。”；测试误用了内层 `resource-contract.js:73` 的文案。末版仅修正此字符串，语法检查通过；未重复跑整项回归，不将局部现场写成 24 场景通过。
- 此次失败点前 77 张表逐项完全一致，服务日志零 POST；PID 86953/86941 均已结束，1097/983 条导入绑定无越界，runtime/锁正常收尾。原始 `process-run-result.json` SHA `2c9b1b6acc690daa66a31dc447a0725ba87fb689d465749f791eac2d5ab3a4c1`，`probe-errors.log` SHA `8a4e7c40eb6a512d72f8a9b30fc2cfc7c1e45adf7a6f604d513e96f3987e61dc`。
- 不再有待授权的能力语义决定；剩余验收项是末版工艺整项的通过证据，由 Main 冻结后的统一验证窗口取得。未修改 `BatchWorkspace.jsx`、`live_server.py` 或旧 `batch_widgets_probe.cjs`。

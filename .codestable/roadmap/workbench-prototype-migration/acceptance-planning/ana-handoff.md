# ANA 增量短交接

- 已关闭：授权的 `WBP-ANA-001.metrics/unavailable/tradeoffs`、`WBP-ANA-003.delivery/history/batch-gantt` 最小只读实现及四组合完整入口验证。未改算法、capturer、预算、schema 或写命令。
- 收敛指令后未启动新测试、补图或审查；此前已启动的进程正常结束。20 个应用阶段均正常关闭，没有遗留本轮服务。H/James 接手的四组测试未改。
- 产品 10 文件路径/SHA：`ana-product-binding.json`，SHA `36b62d51bbf2f2c373260df267bca921397135ad28b9c929fe8901d57e5529e8`。该文件是实现时快照，其中 pending 字样由本交接的后续实测状态补充，不改写其原字节。
- 源码、运行 PID、资产、数据库前后 SHA、K/P 对应关系及既有 16 帧索引：`ana-handoff-evidence.json`，SHA `f7cf9d4662c742394881e39346b19c94a9ac4dc052a6f99eb7b5dd5d30228fec`。只索引已生成图片，没有新增截图。
- 固定源：`/private/tmp/aps-final-d-source-ana-7Pj1pV/source`；3993 文件，聚合 SHA `bc0c24d7c8da520153163659cb75ae8c4a02962e86dacdd7150c6e27c6019bbd`。
- 完整构建：`22aa6cfc89dc6be4b80afdd8b502a1096e6eba01c6622fb1ca7c7908955a17c3`，225 资产 / 317 输入；共享 build-order SHA `bc14072b31ebe13fcad015c08afb176108465fc14557b4af217071c01ccc6bb3`。
- 已完成验证：46 项定点/复用服务回归；候选组件 1 项回归（四组合、228 检查、24 下载）；固定完整入口 16 passed。JUnit：`/tmp/aps-final-d-ana-service-final.xml`、`/tmp/aps-final-d-ana-candidate-widget.xml`、`/tmp/aps-final-d-ana-main-two.xml`、`/tmp/aps-final-d-ana-matrix.xml`。
- 首次副本漏带治理台账导致一次 pytest 收集失败，应用未启动；随后仅补三份入口依赖，原 3990 份代码/资源逐项不变。该失败不计为测试通过。

## 尚存阻断

K 为 **141/146**，不是 37 家族全部通过。以下五项仍未覆盖，不自动扩大产品修复：

| 冻结动作 | 当前边界 |
| --- | --- |
| `WBP-RUN-007.no-result` | 尚无对应真实无结果分支的完整入口证据，未伪造持久运行记录 |
| `WBP-GANTT-002.conflict-track` | 已有正常甘特与叠轨模型，不等于实际非空冲突叠轨的完整入口证据 |
| `WBP-DELAY-004.conflicts` | 冻结要求冲突明细；现有负荷汇总不能替代完整冲突明细证据 |
| `WBP-TRIAL-007.stale-conflict` | 候选 stale-preview 和草稿 stale-write 已过，但不能替代场景正式采用的 stale 分支 |
| `WBP-TRIAL-011.export-failure` | 本地 Blob 导出不能拿断网当失败；失败提示分支仍未验证 |

- P：**57 有对应证据 / 31 明确不适用 / 58 仍缺证**，逐项在 JSON。原成功命令回执已按具体请求区间与新进程后原行绑定；F5、原草稿、读取范围和选中对象采用实际标记，不借整链重启通算。
- 试调模式、基线、仅变更、搜索及结果页签在冻结说明中有 LS 恢复要求，未据“当前只是内存状态”改判不适用；缺证保留，交 Main 定统一收口范围，不启动新轮次。
- V：ANA 六动作仍待 Main 签核。P003 两动作沿用原 `round2-main-v-D-p003.json` 的精确签核范围，不扩大到 ANA、146 动作或下一合并源。
- E 的 `ActualGanttWorkspace` producer 修复未包含在本固定源；E06/G05 旧证明保持原样。最终合并源、完整门禁及必要单次补验等待 Main 的统一冻结窗口。本轮不是 final HEAD / clean-worktree proof，无 Git 写入或原库操作。

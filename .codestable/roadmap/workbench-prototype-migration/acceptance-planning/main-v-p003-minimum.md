# P003 最小 Main V 索引

- P003 已审批、已实现，12 项四组合测试通过；这里只交独立 V，不重开审批或旧控件审查。
- Main 已完成 20 full-page + 4 viewport 审查，两个动作 V 签核见 `../round2-main-v-D-p003.json`，SHA-256 `3b336969b115b73c8587fd969a56db9c300c004ca5d2735628582b40a3f1aa7a`。不扩大到其他动作或本次 ANA 增量。
- 机器索引：`main-v-p003-minimum-index.json`。共 20 张原始 full-page PNG，每张都有绝对路径、SHA-256、对应 actionID、width/theme 和原始实际响应报告。
- 四组合：1920/light `ja4vco32`；1920/dark `8pn4gd67`；1392/light `exypgb0l`；1392/dark `ry59xgim`。根目录均为 `/private/tmp/aps-final-d-source-p003-Z3GYfe/aps-workbench-live-<名称>`。

| 冻结 actionID | 每组必看场景 |
| --- | --- |
| `WBP-GANTT-003.predecessors` | `frozen-three-piece-predecessors`：共同工序的三个分件前序；`frozen-predecessor-outside-range`：切片外明确占位；`frozen-predecessor-full-plan-located`：用户点击后同一完整计划精确定位 |
| `WBP-GANTT-004.trial-link` | `original-task-draft-located`：原工序映射到新草稿 task_ref；`original-task-draft-refresh`：刷新仍为该草稿、该工序 |

- 不用 viewport 顶部画面替代下方关系区。单组中的显式 `nav` 入口另有 `original-task-canonical-entry` 原图和实际 200/永久引用报告，布局与上述原任务定位相同，不强制再扩充相同画面的 V 张数。
- 这些图只对应上述两个原子，不是 146 动作的全 V。其他 action 保持原独立状态。

## 当前待验证 ID

原账本 22 项仍保留；另追加一项旧通过证据不足，见末行。单组开发通过不从此清单删掉。

1. `WBP-RUN-007.no-result`
2. `WBP-PLAN-003.stale-conflict`
3. `WBP-PLAN-004.storage-failure`
4. `WBP-ANA-001.unavailable`
5. `WBP-ANA-001.tradeoffs`
6. `WBP-ANA-003.delivery`
7. `WBP-ANA-003.history`
8. `WBP-ANA-003.batch-gantt`
9. `WBP-ANA-004.gantt`
10. `WBP-ANA-005.download-failure`
11. `WBP-GANTT-002.conflict-track`
12. `WBP-DELAY-004.conflicts`
13. `WBP-TRIAL-001.load-failure`
14. `WBP-TRIAL-002.candidate-source`
15. `WBP-TRIAL-005.calendar-end`
16. `WBP-TRIAL-006.authorization`
17. `WBP-TRIAL-006.overlap`
18. `WBP-TRIAL-006.calendar`
19. `WBP-TRIAL-007.stale-conflict`
20. `WBP-TRIAL-011.export-failure`
21. `WBP-TRIAL-012.stale-write`
22. `WBP-TRIAL-012.storage-failure`
23. `WBP-ANA-001.metrics`：旧断言没有锁住完整四指标，撤回完整合同通过的推论；146 分母不变。

## 单组进度

- `pwdwkg3j` 的完整单组测试已实际通过候选甘特往返、未采用候选创建完整草稿、旧候选 stale preview 拒绝；仅 1920/light，不冒充四组合。
- `bbxvo4rc` 内新授权/重叠/日历/存储/错误引用分支已执行，后续旧取消断言因测试动作历史范围过宽失败。已只修断言到本次取消区间，整链重跑仍待完成。
- 成功采用继续使用独立、事实仍匹配的夹具。试调写入使旧候选事实散列变化时，409 是独立拒绝分支，绝不替代成功采用原子，也不改哈希、白名单或原记录。

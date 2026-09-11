# 共享控件剩余范围决定

- 原 50 个动作保留，46 个已有四组合真实 B/K，P 为只读视图不适用；下面 4 个仍 pending，不删除 ID，不以静态阅读替代生产功能通过。
- 范围证据来自固定 2ab72 构建的 `/private/tmp/aps-workbench-live-7kvfmq7f/final-master-remaining_controls.json`，SHA `5990fccc6dbc3d8b6d50a8ee20be5b601d87edbcae53dc3277de42cec4c448a4`。四组合逐项记录 `scope_decisions` 与实际 DOM 属性。该轮 16 场景通过、4 个主数据探针错误假设弹窗而失败；后者已经另根 `rp8dshb6` 只重跑 4/4 通过。原失败不改写。

## 批次列值计数

- `WBP-SH-006-C05` 当前 batch 自有表头显示全部列值，但不显示各值的出现次数。真实点击“筛选数量”取得 43 个 distinct 值，逐一与 SQLite `Batches.quantity` 去重结果相符；实际 label 仅是数值，不含计数。
- 当前产品：`frontend/workbench/app/BatchTable.jsx:16`；原型 batch 自有表头：`前端设计/ui_kits/workbench/BaseBatches.jsx:336`，同样只有列值；原型通用 Table 则在 `前端设计/components/data/Table.jsx:477` 显示出现次数。
- 决策点：该计数子项是否仅适用于通用 React Table，而不套用 batch 自有表头。若 Main 确认不适用，也应保留此 ID 和范围证据；C 没有新增计数 UI 或擅自改为通过。

## 日期约束

- `WBP-SH-008-C10` / `C11` / `C13` 分别为 min / max / readOnly。
- 原已完成 batch 原生日期动作记录了实际交期 input 的属性；新的日历批量开始/结束日期，在四组合均实测 `min=""`、`max=""`、`readOnly=false`。没有注入这些属性，也没有单独挂一个测试组件假装实际入口。
- 当前字段位置：`frontend/workbench/app/BatchControls.jsx:21`、`frontend/workbench/app/CalendarRangeDialog.jsx:60`。证据只涵盖明确记录的当前字段，不外推任意后续字段或未来版本。
- `disabled` 是不同的真实分支，已经完成：延迟原日历预览请求发送，两个日期 input 均随真实 loading 禁用，普通鼠标点击日期图标不会开弹层或改值；释放后取得真实 HTTP 200，无伪造成功响应。此项已绑定 `WBP-SH-008-C12`，不与上面 3 项混淆。
- 决策点：当前无这些属性的本域字段，是否接受按实际挂载范围记不适用；C 保持 B/K pending，交 Main 定义，不为覆盖补造业务限制。

## V 边界

- `main-v-minimum-index.json` 提供 8 组 / 32 张原始代表图，每图都有构建、源码、原报告、尺寸和 SHA。它是待 Main 看图的索引，不是 599/50 V 全通过。
- Main 的既有 `round2-main-decisions.md` 没有被 C 修改；此前 8 张工艺列宽定点 V 与 DETAIL 的决定不在本次重跑范围。

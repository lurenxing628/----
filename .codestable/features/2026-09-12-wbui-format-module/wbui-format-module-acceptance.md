---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-format-module
status: "completed-with-validation-limit"
summary: "共享日期与数字格式、显示消费者接入及原始精度例外实现已收尾；验收结论为completed-with-validation-limit。"
tags:
- workbench
- formatting
- ui
roadmap: workbench-ui-refinement
roadmap_item: wbui-format-module
created: '2026-09-12'
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

# 统一格式验收记录

- 新增 `frontend/workbench/app/WorkbenchFormat.js`，实现 dateTime/date/instant/number/integerText/percent/hours。
- `node tests/workbench-format.cjs` 通过。实测上海、UTC、纽约三个独立进程时区：工厂本地文本不漂移；同一 Z、+08:00、-04:00 时刻显示一致。覆盖闰年、年月日时分秒越界、误传时区、零值、未知、非有限数值、数值字符串、精度和百分比边界。
- 代码只改公共显示层，不修改 DTO、保存格式和时间轴计算；非法输入抛 TypeError。Python 定位工具查 ErrorBox 未找到 JS 符号，转由 `rg` 定位调用点。
- 保留 RunCandidate 已有超大整数 DTO：integerText 对 `9007199254740993` 与 30 位整数文本精确分组，测试拒绝前导零、符号、小数和科学计数法；number 仍只处理有限 number。
- percent 使用原生 Intl 百分比格式，避免先执行 JavaScript `ratio * 100` 导致有限大数溢出；Number.MAX_VALUE 的完整百分数字符串及非法精度合同测试通过。
- 本验证直接加载本轮源码，无独立 build_id；统一构建及浏览器验证尚由主线程推进，不能以该单测证明所有工作区完成。原工作区为 dirty，本项未执行 git add/commit。

## 消费者接入规则与分工

| 所有者 | 接入位置 | 口径 |
| --- | --- | --- |
| batch_resources | Batch / Resource / Calendar / Outsourcing | 本地日期用 date，datetime 用 dateTime，数值按明确精度 |
| plan_gantt | Plan / ActualGantt / PointGantt | 显示改格式，保留既有轴计算；原界面需要秒数时显式 seconds:true |
| run_workflow | Preflight / Run | 受理/开始/结束为本地日期时间，候选分数与工时按数值口径 |
| field_workflow | Field | 台账本地文本不做时区转换，未知不可换成当前时间 |
| analysis_workspaces | Dashboard / Report / Review / Calibration / MasterOverview | percent 输入为有限比值；合法超负荷和负差值正常显示，范围由领域 DTO 校验 |
| system_polish | System | `checkedAt` 显式使用 instant；业务日志/备份工厂文本使用 dateTime |
| interaction_contracts | Trial / Process | 编辑器仅修改显示转换，原提交值和草稿保留 |

示例：`WorkbenchFormat.dateTime(result.meta.as_of)`；`WorkbenchFormat.instant(report.checkedAt)`；`WorkbenchFormat.number(count,{digits:0})`；`WorkbenchFormat.percent(utilization)`。所有接口与构建顺序已发送对应 owner，主线程统一登记构建。

## 消费者静态复核与末次补齐

- 限定静态复核覆盖208个app运行源，记录225个文件SHA、42个文件中的80处命中及26处直接用途补充。原始报告保留在`evidence/workbench-ui/2026-09-12-final/format-consumer-closure/format-consumer-final-audit.json`，没有将命中全部当作显示缺陷。
- 补齐8处显示入口：系统文件大小2处、五种甘特/分析刻度及实际平均分钟偏差。系统文件仍按1024换算KB，事件行仍显示“事件记录”；时间坐标与wire不变，刻度保留原短日期、跨夜和秒数；平均偏差仍按原Math.round及正负号规则，仅统一千分位，非法数值明确报错。
- 甘特从真实JSX提取表达式，与6cf冻结原表达式逐项对照，23个案例及已有pytest入口通过；系统真实组件和独立临时元信息/API读取完成98个场景（原95加3个大小消费者案例），四主题/尺寸组合、44张截图，原维护动作、回执、锁定、下载和DTO保留检查均通过。原SystemLiveFiles在app内未找到当前挂载链，按源中保留组件补齐并独立验证，不冒称它是当前正式入口。
- CalendarContract.displayNumber继续服务日历输入往返、dirty比较和原配置精度；已有8.375/62.5精度合同不能换成固定一位小数。DatePicker的month/time/datetime-local及秒、毫秒和跨日min/max为原输入边界，不用通用日期函数改写。坐标、序列化、日期键、原文和控件部件标签的其他命中均记录保留理由。
- 当前补齐构建为`e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043`。构建与依赖/格式合同43 passed，新增甘特测试输入登记覆盖6 passed；上述分域结果不合并冒充全仓通过。

## 尚待整轮收口

- 当前统一构建的15视图完整浏览器矩阵、完整质量门禁及带UI证据的daily真实记录。
- 上述完成前，checklist的consumers-and-build保持pending，路线图不可仅据公共层和消费者局部测试标done。

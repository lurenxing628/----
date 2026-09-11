---
doc_type: feature-ff-note
feature: trial-task-origin-navigation
date: 2026-09-10
requirement: D-P003
tags: [workbench, trial, navigation]
---

# D-P003 原任务导航 Overlay

## 做了什么

Main已明确批准D-P003。本次只修改G owned导航解析器和对应测试，增加原任务只读定位字段；不改D的process_order/TrialContract/Workspace、不发可写票据、不改Main pages/JS、不挂载legacy。提案文件旧“待确认”标题不覆盖本轮明确批准。

## 精确 Schema

外层仍为 `{version: 1, view: "trial", context: ...}`。`Ref48`必须是JSON字符串，完整匹配 `^[0-9a-f]{48}$`；不trim、不换大小写、不查询或新建引用。

```text
TaskOrigin = {plan_ref: Ref48, operation_ref: Ref48, task_ref: Ref48}

Context =
  {base: {plan_ref: P}, task_origin: {plan_ref: P, operation_ref: O, task_ref: T},
   scope?: ExistingTrialDisplayScope}
  或
  {draft_ref: D, task_origin: {plan_ref: P, operation_ref: O, task_ref: T}}
```

- `task_origin`严格三键，不能为空或部分缺失，不允许多余键；context/base也按上述形式严格取键。所有层的重复JSON键仍拒绝。
- base形式必须只有`plan_ref`且与origin中的字符串完全相同；候选`base.candidate_ref`、不同base.plan_ref、scenario_ref、混合base/draft、仅origin无目标均拒绝。
- scope只在base形式按原合同允许；draft形式不新增scope。原时间范围、query、batch/resource显示条件不放宽，不缩小创建/采用的完整计划。
- 无`task_origin`时仍走原分支：candidate base、scenario_ref、draft_ref等旧输入行为不变。
- 这是格式和显式来源一致性校验，不证明引用真实存在，也不证明draft来自该计划。D读取后必须核实`data.base.plan_ref`，且唯一任务同时匹配`operation_ref`和`source_task_ref`，再使用该草稿任务自己的`task_ref`；无匹配/多匹配/错来源明确报错。
- 导航字段不进入create/change/save/adopt写合同；原`create_input`仍拒绝含task_origin的写请求。解析器仅用去除导航字段后的副本复用旧scope验证，不调用写服务。

## 两文件与 Hash

| 文件 | V4 preimage | Overlay postimage |
| --- | --- | --- |
| `web/routes/workbench/navigation_boot.py` | `405adefc94b0280fa6a187400d2277234d140bc349cb37d0ca6ef9cc529f785e` | `c62efce8731a28d33142525ace378582b7b2183c300fe0e7c8b3c052bc4b43f0` |
| `tests/workbench/test_final_navigation_boot.py` | `8fcb2b8aa35e148a34376c10870e1ae26377a2ce290d70f048cf8a0586598af3` | `53a03b7468e1e865ef095aab898a04cf47d91e41d4d56eaac94c52ee64fc746e` |

- `_trial_task_origin`在解析器148行，`_trial_context`在165行，`read_navigation`现为197行。生产imports未变化，其余原导航函数AST未变化，原12项导航测试class AST未变化。
- 两文件patch为 `.codestable/roadmap/workbench-prototype-migration/legacy-retirement/task-origin-overlay.patch`，SHA256 `ab3000ec1b5e1af9692e93d970eedadd686593a558c33e5b7193f68a3b2b288b`。preimage来自封存V4；另在私有两文件副本实际应用并逐一核对postimage，不冒充完整factory运行。
- 机器证据为同目录 `task-origin-overlay.json`，包含解析schema、文件hash、日志hash和验证范围。应用到后续完整snapshot时须再次检查preimage，禁止覆盖并行改动。

## 怎么验证的

- Python3.8.10：四项导航/legacy/layering/report-date专项共51 passed，0 failed；其中导航20项，新增task_origin正负测试8项。覆盖同源base/原scope/draft、所有部分键、额外键、各ref非法类型/长度/字符、候选/场景/混合/错base、重复JSON键、原写合同拒绝与无DB调用。
- Ruff通过；两文件Pyright 0 errors/0 warnings。日志在 `/private/tmp/aps-g-task-origin-overlay-0qAhvm/`。
- 这是Main dirty工作区的局部解析回归，不是浏览器、D真实草稿来源验证、完整质量门禁或clean proof。
- V4根 `/private/tmp/aps-g-retirement-candidate-u8YnDE` 及其3927文件candidate aggregate `e74e6dce3c8a196433692084dbdc4d94f3f9c4b79e952bc352c0e7ed8714b85b` 保持不变。V4的46项pytest、factory导入/旧方法/打印/手册/消息证据不覆盖此overlay，后续完整snapshot须单独验收。

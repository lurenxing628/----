---
doc_type: roadmap
slug: gantt-result-view-and-manual-adjustment
status: active
created: 2026-05-22
last_reviewed: 2026-05-22
tags: [scheduler, gantt, manual-adjustment, zoom, draft-version, win7]
related_requirements: [.codestable/requirements/gantt-readonly-result-view.md]
related_architecture: [.codestable/architecture/ARCHITECTURE.md, .codestable/architecture/ui-gantt.md]
---

# 甘特图查看、缩放与手工调整路线图

## 1. 背景

当前甘特图页面本来应该只是“看排产结果”：用户选一个排产版本，看每道工序排在哪天、哪台设备、哪个人员、是否超期、是否在关键链上。

现在真实体验有两个明显问题：

- **第一，能拖但不生效**。底层 Frappe Gantt 会让条形图被拖动、拉宽、拉窄，但主页面没有接保存回调，也没有后端接口接住这次拖动。用户拖完以后，只是当前浏览器里的图形动了；刷新页面、打开周计划、资源排班、报表，数据都没变。这会让调度员误以为自己已经修改了排产。
- **第二，看不清小时和分钟**。页面只有“日视图 / 周视图 / 月视图”。在日视图里，一格就是一天；拖动时也容易感觉“一拖就是一天”。36 分钟、51 分钟这类短工序即使条形不再变成空，也仍然太窄，用户没法方便地放大到小时或 15 分钟去看清楚。

所以这条路线不能从“让拖动保存”开始。正确顺序应该是：

1. 先把甘特图变成明确的**查看模式**，禁掉假拖动。
2. 再把查看能力做好，尤其是**小时 / 分钟级缩放**。
3. 再把短工序点击区、假期背景、今天高亮、关键工序外框和依赖线这些视觉标记全部对齐到当前缩放。
4. 再加范围保护和 Win7 Chrome 109 压测边界，避免 1 分钟视图把浏览器撑死。
5. 最后才另开后续主线做**模拟调整、草稿、校验、保存、正式采用**。

大白话说：先让用户看到的东西可信，再让用户看得细，最后再让用户改得安全。

## 2. 总路线设想

### 阶段总览

| 阶段 | 名称 | 用户看到什么 | 本阶段完成后能证明什么 |
|---|---|---|---|
| 0 | 只读基础合同与 vendor 治理 | 用户暂时看不到明显变化，但路线图、测试和本地 Frappe 补丁边界被写清楚 | 后续不会继续在压缩版 Frappe 里散修 |
| 1 | 查看模式收口 | 甘特图明确显示“查看模式”，条形不能拖动或拉伸，只能点击看详情 | 用户不会再被“假拖动”误导 |
| 2 | 时间缩放 | 用户可以在月、周、日、12 小时、6 小时、小时、15 分钟、5 分钟、1 分钟之间切换 | 短工序能看清具体小时分钟，不再只能看哪一天 |
| 3 | 缩放后的视觉标记对齐 | 假期/停工背景、今天高亮、关键工序外框、超期红框、外协虚线和依赖线都跟着缩放走 | 用户看到的标记不会因为缩放变成错位提示 |
| 4 | 范围保护和性能压测 | 细粒度范围太大时先提示缩小范围，不能让页面卡死 | 1 分钟视图在 Win7 Chrome 109 边界下有保护 |
| 5 | 说明书、页面帮助和 QA 收口 | 文档和页面都说清楚“这里是查看结果，不是正式调整” | 调度员能照着说明复查和培训 |
| 后续 | 模拟调整 / 草稿 / 场景 / 正式发布 | 另开独立实现主线，不进入第一版只读验收 | 只读甘特图没有验收完成前，不进入拖动编辑 |

### 为什么必须按这个顺序

1. **查看模式必须最先做**
   因为现在的问题不是“用户不能拖”，而是“用户能拖但系统没保存”。只要这个假交互存在，任何培训和说明书都会打架。

2. **缩放必须排第二**
   因为缩放是查看能力，不会改业务数据，风险低、收益高。它能立刻解决“看不到小时分钟”“短工序太窄”“日视图太粗”的问题。

3. **适配层必须在模拟调整前做**
   当前 Frappe 是本地压缩版，页面脚本直接把 `view_mode`、拖动、点击、依赖线装饰混在一起。后续如果直接加模拟调整，代码会继续变成补丁堆。适配层先把“查看 / 缩放 / 禁拖 / 模拟拖动事件”这些行为包住。

4. **模拟调整必须先草稿后发布**
   一次拖动可能影响设备、人员、物料、班次、停机、前后工序、交期和报表。如果直接改正式版本，出问题很难撤回，也很难解释谁改了什么。

### 本轮讨论后的拍板口径

本轮最终拍板：

1. 第一版时间缩放支持：
   月、周、日、12小时、6小时、小时、15分钟、5分钟、1分钟。

2. 第一版不做：
   秒级、0.1秒、精细拖动模式、拖动保存、模拟调整正式发布。

3. 时间口径：
   全部使用本地时间。
   页面上的日期范围按本地自然日解释：
   起始日 = 当天 00:00:00
   结束日 = 当天 23:59:59

4. 只读甘特图完成标准：
   用户能可信地查看正式排产结果，不能拖动误改；
   能通过缩放看清短工序的小时/分钟位置；
   所有视觉标记在缩放后仍对齐；
   Win7 Chrome 109 / 离线静态资源 / 本地部署边界下不能卡死。

5. 后续模拟调整版本模型：
   采用 `Draft -> Scenario -> Official Version` 三层模型。
   草稿和模拟方案不能直接写进正式 `Schedule` / `ScheduleHistory`。
   只有正式发布时，才分配新的正式版本、复制方案行、写正式历史和审计记录。

这个口径的意思是：第一版不是“能拖动的甘特图”，而是“可信、可缩放、可点击、不卡死的只读排产结果图”。模拟调整只保留方向和合同，等只读甘特图完整验收后再独立启动。

### 权限与审计拍板口径

第一版只读甘特图不新增复杂权限：

- 能访问排产结果页的人，都能查看甘特图、切换缩放、筛选、打开详情。
- 查看、缩放、筛选不产生审计事件。

后续模拟调整必须分权，不能只靠按钮显隐：

- `gantt.view`：查看正式甘特图、缩放、筛选、打开详情。
- `gantt.simulation.create`：进入模拟调整，创建 Draft 草稿。
- `gantt.simulation.save`：把通过校验的草稿保存为 Scenario 模拟方案。
- `gantt.simulation.publish`：把 Scenario 正式采用为新的 Official Version。
- `gantt.override_locked`：允许调整锁定工序，默认不给普通调度员。
- `gantt.admin`：草稿清理、异常回滚、权限兜底。

正式采用不是 `gantt_mode`，而是一类发布动作。它必须二次确认、原因必填、重新校验、确认基准版本未过期、生成新正式版本，并记录 `created_by / published_by / base_version / new_version / change_count / reason`。

## 3. 范围与明确不做

### 本 roadmap 覆盖

- 甘特图默认查看模式：禁用无效拖动和拉伸，只保留点击详情、筛选、配色、关键链、依赖线等查看能力。
- 甘特图时间缩放：从当前日/周/月，扩展到适合 APS 的半天、6 小时、小时、15 分钟、5 分钟、1 分钟查看。
- 甘特图缩放体验：第一版使用时间粒度下拉控件、当前粒度标识、横向滚动、定位到任务、短工序可点击热区、URL 可复现。
- 缩放后的视觉标记：短条命中区、假期/停工背景、今天高亮、关键工序外框、超期红框、外协虚线、依赖线和标签都必须跟缩放同步。
- 分钟级范围保护：1 分钟第一版不做虚拟滚动，先用范围保护、节点数保护和浏览器压测守住。
- 只读阶段版本一致性：甘特图只读查看正式排产版本，不新增任何保存、草稿、正式采用动作。
- 模拟调整后续方向：只保留 Draft / Scenario / Official Version 的边界和合同，不进入第一版只读验收。
- 用户提示：不说内部算法词，直接说明“哪道工序、为什么不能放、影响谁、下一步怎么办”。

### 明确不做

- 第一版不做“拖动保存”。先把假拖动关掉，避免误导。
- 第一版不替换 Frappe Gantt。继续使用本地静态资源，符合 Win7 离线交付边界。
- 第一版不新增 `POST /scheduler/gantt/adjustments/save-draft`，不新增正式采用接口。
- 第一版不写 `Schedule`，不写 `ScheduleHistory`，不改变正式版本指针。
- 不做“拖一下直接改旧正式版本”。后续正式采用必须生成新版本，旧版本不可原地改。
- 不做秒级和 0.1 秒级缩放，不做精细模式。后续如果业务证明需要，另起独立调研和路线。
- 不在整天、整周、整月视图里渲染过细网格。5 分钟和 1 分钟视图必须有日期范围保护。
- 不把草稿混进默认正式报表。草稿只能预览，默认报表和车间执行口径仍读正式版本。
- 只读甘特图没有验收完成前，不进入拖动编辑。
- 不引入外部 CDN、在线脚本或必须联网的前端资源。

## 4. 模块拆分（概设）

```text
甘特图查看、缩放与手工调整
├── 只读基础合同与 vendor 治理：先统一模式、时间、缩放、任务身份和补丁证据
├── 查看模式与交互边界：默认只读，禁止假拖动，保留点击详情
├── 时间缩放与时间尺：月/周/日/12小时/6小时/小时/15分钟/5分钟/1分钟查看，短工序可读，URL 可复现
├── 缩放后的视觉标记对齐：假期、今天、关键工序、超期、外协、依赖线都跟当前时间尺对齐
├── 性能范围保护：分钟级视图先拦过宽范围和过多节点，不做虚拟滚动大改
├── 用户提示与验收手册：页面帮助、说明书、浏览器压测步骤和回归测试同步
└── 后续模拟调整合同：Draft / Scenario / Official Version，只保留方向，不进入第一版只读实现
```

### 只读基础合同与 vendor 治理

- **职责**：先把第一版只读甘特图的合同写稳。这里管模式、缩放枚举、本地自然日、任务业务身份、Frappe 本地补丁说明和测试证据。
- **承载的子 feature**：`gantt-readonly-foundation-contract`
- **触碰的现有代码 / 模块**：路线图、items、`static/js/gantt_zoom.js`、`templates/scheduler/gantt.html`、`web_new_test/templates/scheduler/gantt.html`、`tests/regression_gantt_critical_outline_sync.py`、`.codestable/vendor/frappe-gantt-local-patches.md`。

### 查看模式与交互边界

- **职责**：把当前甘特图先变成可信的结果查看页。用户在这个模式下能点条形看详情，但不能拖动、不能拉伸、不能误以为修改已保存。
- **承载的子 feature**：`gantt-readonly-result-mode`
- **触碰的现有代码 / 模块**：`templates/scheduler/gantt.html`、`web_new_test/templates/scheduler/gantt.html`、`static/js/gantt_render.js`、`static/js/frappe-gantt.min.js`、`static/css/aps_gantt.css`、甘特图相关回归测试。

### 时间缩放与时间尺

- **职责**：让用户能从“看哪一天”放大到“看哪个小时、哪 15 分钟、哪 5 分钟、哪 1 分钟”。它只解决查看清楚，不承担保存排产。
- **承载的子 feature**：`gantt-readonly-time-zoom`
- **触碰的现有代码 / 模块**：`templates/scheduler/gantt.html` 的时间粒度控件、`static/js/gantt_ui.js` 的 URL 状态和默认值、`static/js/gantt_render.js` 的渲染与节假日背景、`static/js/frappe-gantt.min.js` 的时间尺和缩放、`static/css/aps_gantt.css` 的横向滚动和标签显示。

### 缩放后的视觉标记对齐

- **职责**：缩放以后，所有标记都要仍然指向同一个真实时间。短条的透明点击区只能方便点击，不能把真实工序时长放大；假期、今天、关键工序、超期、外协和依赖线都要跟当前时间尺对齐。
- **承载的子 feature**：`gantt-readonly-decoration-sync`
- **触碰的现有代码 / 模块**：`static/js/gantt_render.js`、`static/js/gantt_outline.js`、`static/js/frappe-gantt.min.js`、`tests/regression_gantt_zoom_decoration_sync.py`、`tests/regression_gantt_critical_outline_sync.py`。

### 性能范围保护

- **职责**：1 分钟视图第一版不做虚拟滚动，也不换组件。先用日期范围、列数和节点数估算把超宽页面拦住，并把 Win7 Chrome 109 压测步骤写成可复跑手册。
- **承载的子 feature**：`gantt-readonly-performance-guards`
- **触碰的现有代码 / 模块**：`static/js/gantt_zoom.js`、`static/js/gantt_render.js`、`static/js/gantt_ui.js`、`templates/scheduler/gantt.html`、`static/css/aps_gantt.css`、`tests/regression_gantt_zoom_range_guard.py`、`docs/dev/aps-browser-scheduler-qa-replay.md`。

### 用户提示与验收手册

- **职责**：把只读查看、缩放、短工序点击区和范围保护写成调度员能看懂的话，页面帮助、说明书和回归测试一起收口。
- **承载的子 feature**：`gantt-readonly-docs-and-qa`
- **触碰的现有代码 / 模块**：`static/docs/scheduler_manual.md`、`web/viewmodels/page_manuals_scheduler_outputs.py`、`static/js/gantt_contract.js`、`templates/scheduler/gantt.html`、`web_new_test/templates/scheduler/gantt.html`、`tests/regression_frontend_ui_language_polish.py`。

### 后续模拟调整合同

- **职责**：只保留方向和接口合同。未来模拟调整必须是 Draft → Scenario → Official Version，不能把草稿直接塞进正式排产历史。
- **承载的后续子 feature**：`gantt-adapter-contract`、`gantt-simulation-entry-shell`、`gantt-adjustment-draft-model`、`gantt-adjustment-validate-simulate`、`gantt-draft-save-and-preview`、`gantt-draft-publish-official-version`、`gantt-component-upgrade-spike`
- **触碰的现有代码 / 模块**：后续单独进入 feature 流程时再确认；第一版只读甘特图不改数据库、不新增保存接口。

### 模拟调整入口（后续方向）

- **职责**：在页面上明确拆开“查看结果”和“模拟调整”。查看模式不能拖；模拟调整模式才出现拖动、撤销、放弃、保存草稿等工具。
- **承载的子 feature**：`gantt-simulation-entry-shell`
- **触碰的现有代码 / 模块**：甘特图模板、CSS、前端状态管理、页面帮助、浏览器验证脚本。

### 调整草稿模型（后续方向）

- **职责**：记录“用户想怎么改”。例如把某道工序从 5 月 6 日 10:00 挪到 5 月 6 日 14:30，或者从设备 A 换到设备 B。这些只是草稿，不是正式排产。
- **承载的子 feature**：`gantt-adjustment-draft-model`
- **触碰的现有代码 / 模块**：新增数据库表或草稿持久化服务、调度版本查询服务、审计日志摘要、迁移和 schema。

### 后端校验与试算（后续方向）

- **职责**：判断一次拖动能不能成立。不能只看开始/结束时间，还要看设备占用、人员占用、工序前后顺序、工作日历、停机、齐套、交期、锁定工序和当前版本是否过期。
- **承载的子 feature**：`gantt-adjustment-validate-simulate`
- **触碰的现有代码 / 模块**：`core/services/scheduler/` 下新增调整校验服务，复用 `SchedulePlanQueryService`、工作日历、停机、批次物料和版本解析能力。

### Scenario 模拟方案预览（后续方向）

- **职责**：草稿通过校验后保存为 Scenario 模拟方案。用户能预览甘特图、周计划、资源排班和报表，但页面要一直标清“这是模拟方案，正式计划还没有改变”。
- **承载的子 feature**：`gantt-draft-save-and-preview`
- **触碰的现有代码 / 模块**：新增 Scenario 存储服务、`SchedulePlanQueryService`、甘特图、周计划、资源派工、报表显式预览入口。

### 正式采用（后续方向）

- **职责**：用户确认后，把 Scenario 模拟方案发布成新的正式排产版本。旧版本不原地修改；报表、周计划、资源排班和历史页都按新版本读取。
- **承载的子 feature**：`gantt-draft-publish-official-version`
- **触碰的现有代码 / 模块**：版本发布服务、历史记录、审计摘要、所有结果页的版本解析。

### 调整阶段用户提示与验收手册（后续方向）

- **职责**：把复杂规则翻译成调度员能看懂的话，并沉淀浏览器验收脚本和说明书。比如“不能放到这里：设备 M01 在 10:00 到 12:00 已安排 B002 第10道工序”。
- **承载的子 feature**：`gantt-adjustment-user-guide-and-qa`
- **触碰的现有代码 / 模块**：`static/docs/scheduler_manual.md`、页面帮助 viewmodel、浏览器 QA 文档、回归测试。

## 5. 阶段路线详设

### 阶段 0：只读甘特图基础合同与 vendor 治理

**目标**：先统一模式、时间、缩放、任务身份、vendor 补丁管理，避免后续继续在压缩版 Frappe 里散修。

**范围**：

- 定义 `gantt_mode=view`。
- 定义 `gantt_zoom=month/week/day/half-day/quarter-day/hour/fifteen-minute/five-minute/one-minute`。
- 定义本地时间与自然日边界。
- 定义任务业务身份：`base_version + base_plan_role + schedule_id + op_id`。
- 定义 vendor 文件补丁治理方式。
- 定义只读甘特图第一版不产生任何保存、草稿、正式采用动作。

**验收**：

- roadmap 和 items.yaml 都写明第一版只读边界。
- 测试计划里包含短工序、跨天、00:00 end、缩放、只读禁拖、性能范围保护。
- 明确 `static/js/frappe-gantt.min.js` 的修改必须有合同测试和补丁说明。

### 阶段 1：查看模式收口

**目标**：先把误导关掉。用户打开甘特图时，只能查看结果，不能拖动、不能拉伸。

**用户看到的变化**：

- 页面顶部或甘特图上方显示状态：`当前为查看模式，只能查看排产结果，不会修改计划。`
- 条形图仍然可以点击，弹出工序详情。
- 鼠标放到条形图上，不再出现“可以拖动 / 可以拉宽”的感觉。
- 条形两端不显示可拖动手柄。
- 用户尝试拖动时，条形图不移动；不会出现“拖完像是改了”的错觉。

**技术路线**：

- 在页面状态里引入 `gantt_mode=view`，默认就是查看模式。
- Frappe 初始化时传入只读行为，或者在本地 Frappe 里增加 APS 自己的 `readonly_dates` / `disable_drag` 分支。
- `bind_bar_events()` 必须在查看模式下不绑定拖动、拉伸、进度拖动事件。
- 保留 `on_click` 和弹窗，不影响点击详情、批次高亮、关键链装饰。
- CSS 去掉查看模式下的拖动手柄和拖动光标。
- 说明书和页面帮助同步写清：甘特图默认只看结果，要调整需要进入后续模拟调整模式。

**验收标准**：

- 在设备视图、人员视图、候选方案视图里，条形图都不能被拖动或拉伸。
- 点击条形图仍能看到工序详情。
- 切换筛选、配色、关键链、依赖线仍正常。
- 刷新页面后，排程位置和刷新前一致。
- 浏览器实测要覆盖短工序、长工序、跨天工序、外协工序。

**不做**：

- 不做拖动保存。
- 不做模拟草稿。
- 不改排产结果数据。

### 阶段 2：时间缩放和分钟级查看

**目标**：让用户能把甘特图放大到小时、15 分钟、5 分钟和 1 分钟，看清短工序到底在哪个时间段。

**用户看到的变化**：

- 时间粒度控件从现在的 `日视图 / 周视图 / 月视图`，扩展为：
  - `月`
  - `周`
  - `日`
  - `12小时`
  - `6小时`
  - `小时`
  - `15分钟`
  - `5分钟`
  - `1分钟`
- 第一版先用一个“时间粒度”下拉框完成切换；`放大`、`缩小`、`适合当前范围`、`回到日视图` 这类快捷按钮先不做，等只读缩放稳定后再评估。
- 选中 `小时` 后，顶部时间尺显示当天的小时。
- 选中 `15分钟` 后，能看清 36 分钟、51 分钟这类短工序的真实长度。
- 选中 `5分钟` 或 `1分钟` 后，能进一步确认短工序的开始/结束分钟，不需要猜它到底落在哪个小时间隔。
- 页面横向变宽时，有明显横向滚动，不挤坏布局。
- URL 里保留缩放状态，别人打开同一个链接能看到同样粒度。

**技术路线**：

- 新增 `gantt_zoom`，逐步替代旧的 `gantt_vm`；旧参数继续兼容。
- 新增 `GanttZoomSpec`：
  - `level`
  - `label`
  - `step_minutes`
  - `column_width_px`
  - `snap_minutes_view`
  - `snap_minutes_edit`
  - `min_visible_task_px`
- 初始建议：
  - `month`: 1 格约 1 月
  - `week`: 1 格约 1 周
  - `day`: 1 格 1 天
  - `half-day`: 1 格 12 小时
  - `quarter-day`: 1 格 6 小时
  - `hour`: 1 格 1 小时
  - `fifteen-minute`: 1 格 15 分钟
  - `five-minute`: 1 格 5 分钟
  - `one-minute`: 1 格 1 分钟
- Frappe 的时间宽度必须继续按真实毫秒差计算，不能回到“向下取整小时”的旧问题。
- 在小时、15 分钟、5 分钟和 1 分钟视图里，时间标题要显示小时/分钟，不要只显示日期数字。
- 日历背景、今天高亮、关键链线、依赖线，都必须按当前缩放重新计算位置。
- 宽范围 + 分钟级视图可能产生大量列，要做范围保护：
  - 超过一定天数时，提示用户缩小日期范围。
  - 不要让一个月的 15 分钟、5 分钟或 1 分钟格一次性撑爆页面。
  - 1 分钟视图默认只允许很短日期范围，例如单日或单班次范围。

**验收标准**：

- 36 分钟、51 分钟工序在日视图、小时视图、15 分钟、5 分钟、1 分钟视图下都可见、可点击。
- 小时视图能看出工序在当天几点开始、几点结束。
- 15 分钟、5 分钟和 1 分钟视图能看出短工序不是空条，也不是被夸大成一整天。
- 缩放后，关键链线、假期背景、超期红框位置仍对齐。
- URL 复制后能复现缩放状态。
- Chrome 109 / Win7 目标边界下不卡死。

**不做**：

- 不在这个阶段开放拖动保存。
- 不做草稿和发布。

### 阶段 3：缩放后的视觉标记对齐

**目标**：缩放后这些标记都不能错位：短条 hitbox、假期/停工背景、今天高亮、关键工序外框、超期红框、外协虚线、依赖线、标签、横向滚动定位。

**用户看到的变化**：

- 1 分钟、5 分钟、15 分钟视图里，短工序按真实时长显示，但仍然容易点中。
- 假期/停工背景按整天覆盖，不会在小时/分钟视图里只盖一小格。
- 今天高亮按整天覆盖。
- 关键工序外框、超期红框、外协虚线和依赖线跟真实任务条对齐。

**技术路线**：

- `.bar-hit` 只扩大点击区域，不改变 `.bar` 的真实宽度。
- 假期/停工背景和今天高亮按 `1440 / stepMinutes * columnWidth` 计算一天宽度。
- 关键工序 outline 继续跟随真实 `.bar`，不跟随透明点击区。
- 依赖线使用真实 bar 的 x 和 width，避免 `NaN`。
- 横向滚动定位改成 `diffMinutes / stepMinutes * columnWidth - columnWidth`。

**验收标准**：

- 36 分钟、51 分钟、73 分钟工序在小时/15分钟/5分钟/1分钟视图可见、可点。
- 跨天短工序、结束在 `00:00:00` 的短工序不会被错误扩成整天。
- 假期背景、今天高亮、关键工序外框、超期红框、外协虚线和依赖线都能随缩放对齐。

### 阶段 4：分钟级范围保护和性能压测

**目标**：1 分钟视图第一版不做虚拟滚动，不换组件；先用范围保护、节点数保护和浏览器压测守住页面不被撑死。

**范围保护建议**：

| 缩放 | step | column width | max_range_days | 说明 |
|---|---:|---:|---:|---|
| 月 | 1月 | 120px | 不设硬上限 | 仅粗看 |
| 周 | 1周 | 140px | 不设硬上限 | 仅粗看 |
| 日 | 1天 | 38px | 62天 | 当前主视图 |
| 12小时 | 720分钟 | 56px | 31天 | 适合看班次级 |
| 6小时 | 360分钟 | 56px | 21天 | 适合看半班/短日程 |
| 小时 | 60分钟 | 48px | 14天 | 适合看一天到两周 |
| 15分钟 | 15分钟 | 32px | 7天 | 适合看短工序 |
| 5分钟 | 5分钟 | 24px | 3天 | 适合看单日到数日 |
| 1分钟 | 1分钟 | 18px | 1天 | 只看单日/单班 |

**节点保护建议**：

```text
estimated_columns = ceil(range_minutes / step_minutes)

estimated_svg_nodes =
  estimated_columns * 3
  + task_count * 8
  + dependency_count * 2
  + holiday_marker_count
```

```text
soft_node_limit = 12000
hard_node_limit = 18000
hard_column_limit = 1500
```

**行为**：

- 超过 `max_range_days`：不渲染细粒度视图，提示用户缩小日期范围或切换到更粗粒度。
- 超过 `hard_node_limit` 或 `hard_column_limit`：不渲染，提示先筛选设备/人员/批次。
- 超过 `soft_node_limit` 但没超过硬限制：允许渲染，但显示性能提示。

**验收标准**：

- `one-minute + 2天`、`five-minute + 4天`、`fifteen-minute + 8天`、`hour + 15天` 都阻止渲染。
- 1分钟 / 单日 / 500任务以内不应卡死。
- 1分钟 / 单日 / 1000任务以上如果卡顿，可以通过范围保护或筛选提示接受。
- 不引入外部 CDN，离线静态资源可用。

### 阶段 5：说明书、页面帮助和浏览器验收收口

**目标**：把页面提示、说明书、页面帮助、浏览器压测手册和回归测试一起收口，让调度员知道这里是查看结果，不是正式调整。

**必须说明**：

- 当前为查看模式：这里只显示排产结果，拖动或拉伸任务条不会修改计划。
- 月/周/日适合看整体范围；12小时/6小时适合看班次附近；小时/15分钟/5分钟/1分钟适合看短工序的具体开始和结束时间。
- 范围太大时，系统会提示先缩小日期范围，避免页面卡顿。
- 很短的工序按真实时长显示，所以看起来可能很窄；透明点击区域只是方便点击，不代表工序时长被放大。
- 关键工序是会直接影响当前版本最晚完工时间的工序，系统用外框标出。

**验收标准**：

- 页面帮助、说明书和回归测试都覆盖只读、缩放、短工序、范围保护、Win7 Chrome 109 压测。
- 页面文案不把调度员带到“拖动已经保存”的误解里。
- `templates/scheduler/gantt.html` 和 `web_new_test/templates/scheduler/gantt.html` 保持同步。

### 后续路线：甘特适配层

**目标**：把 Frappe 的内部行为包起来，后续所有页面只跟 APS 自己的甘特接口说话。

**用户看到的变化**：

- 用户感知不一定大，但页面更稳定。
- 查看模式、缩放、点击详情、未来模拟拖动的边界会更清楚。

**技术路线**：

- 新增或整理 `static/js/gantt_adapter.js`。
- 适配层暴露统一方法：
  - `createGantt(host, tasks, options)`
  - `setMode("view" | "simulate")`
  - `setZoom(level)`
  - `onTaskClick(handler)`
  - `onDraftChange(handler)`
  - `destroy()`
- `gantt_render.js` 不再直接知道太多 Frappe 内部字段。
- Frappe 压缩文件只保留必要本地补丁，新增行为优先在适配层做。
- 给适配层写合同测试，锁住查看模式禁拖、缩放参数、短工序宽度和点击详情。

**验收标准**：

- 现有甘特图功能不退化。
- 适配层能同时支持查看模式和未来模拟模式的事件出口。
- 如果后续换 DHTMLX/Bryntum，后端草稿和校验接口不需要重写。

### 后续路线：模拟调整入口壳

**目标**：让用户明确知道“查看”和“调整”是两回事。

**用户看到的变化**：

- 默认是 `查看结果`。
- 页面上先出现灰色占位入口：`模拟调整（后续开放）`。
- 当前入口不能点击，不产生草稿、模拟方案或正式新版本。
- 草稿模型和校验服务完成后，才允许把入口升级成真实模拟调整模式。
- 真实模拟调整模式后续再显示：
  - `未保存调整 0 处`
  - `撤销`
  - `重做`
  - `放弃调整`
  - `保存为模拟方案`

**技术路线**：

- 本阶段继续保持 `data-gantt-mode="view"`，不切换到真实 `simulate`。
- 本阶段只增加禁用占位入口和用户说明，不绑定点击事件，不发保存请求。
- 后续 `gantt-adjustment-draft-model` 完成后，再开放真实 `simulate` 状态、未保存计数、撤销/重做和离开提醒。
- `保存为模拟方案` 在没有后端草稿服务前不能做假按钮；本阶段先不显示保存按钮。

**验收标准**：

- 查看模式和后续模拟调整入口视觉上能一眼区分。
- 当前入口必须是禁用态。
- 当前入口不产生未保存调整，因此不绑定离开页面提醒。
- 没有后端校验时，不允许出现“看起来保存成功”的提示。

### 后续路线：调整草稿模型

**目标**：系统能保存“用户想怎么改”，但不污染正式排产。

**用户看到的变化**：

- 模拟调整可以产生草稿编号。
- 页面能显示：`草稿基于 v15，正式计划还没有改变。`

**技术路线**：

- 新增草稿表或等价持久化结构：
  - 草稿编号
  - 基准版本
  - 基准方案角色
  - 草稿状态
  - 调整列表
  - 操作人
  - 原因
  - 创建时间 / 更新时间
- 调整项至少记录：
  - 工序 ID
  - 排程行 ID
  - 原开始 / 原结束
  - 新开始 / 新结束
  - 原资源 / 新资源
  - 调整类型
  - 调整原因
- 草稿不能改变 `ScheduleHistory` 的正式版本指针。

**验收标准**：

- 创建草稿后，正式甘特图、周计划、报表不变。
- 草稿能重新打开，看到未发布调整。
- 删除草稿不会影响正式版本。

### 后续路线：后端校验和试算

**目标**：拖动不再只是前端视觉动作。每次调整都要由后端判断能不能成立。

**用户看到的变化**：

- 拖动后系统显示：
  - `正在检查设备占用、人员占用和前后工序关系。`
  - `可以放到这里。`
  - 或者 `不能放到这里：设备 M01 在 10:00 到 12:00 已安排 B002 第10道工序。`
- 冲突列表可以点击定位到对应工序。

**技术路线**：

- 新增校验接口：
  - `POST /scheduler/gantt/adjustments/validate`
- 后端检查：
  - 版本是否还有效
  - 工序是否存在
  - 工序是否锁定
  - 前后工序是否倒挂
  - 设备是否重叠
  - 人员是否重叠
  - 工作日历是否允许
  - 停机是否冲突
  - 物料齐套是否满足
  - 是否造成交期延误
- 返回结构化冲突，不返回内部异常和图对象。

**验收标准**：

- 冲突提示必须是中文业务话。
- 每个 blocker 都说明“为什么不行”和“下一步怎么处理”。
- 无冲突时返回受影响工序清单。
- 校验失败不能保存草稿为可发布状态。

### 后续路线：保存 Scenario 模拟方案和预览

**目标**：用户可以把调整结果保存成 Scenario 模拟方案，拿来比较，但正式计划不变。Scenario 不占正式版本号，不写正式 `ScheduleHistory`。

**用户看到的变化**：

- 点击 `保存为模拟方案` 后，提示：
  - `已保存为模拟方案 S-20260522-001，正式计划还没有改变。`
- 甘特图、周计划、资源排班、报表可以显式选择这个 Scenario 预览。
- 页面一直显示模拟方案标识，不能让用户误当正式版本。

**技术路线**：

- 保存草稿时生成 Scenario 模拟方案记录，不占用 `ScheduleHistory.version`。
- 结果页选择必须明确区分：
  - 正式版本
  - Scenario 模拟方案
  - 对比方案
- 报表默认不能自动读取 Scenario，必须用户显式选择。

**验收标准**：

- 保存 Scenario 后，正式版本仍保持原样。
- 甘特图 / 周计划 / 资源排班 / 报表都能按 Scenario 预览。
- 页面和导出文件都能标出“模拟方案”。

### 后续路线：正式采用

**目标**：用户确认后，把 Scenario 模拟方案发布成新的正式排产版本。

**用户看到的变化**：

- 页面提供 `正式采用此版本`。
- 点击后出现二次确认：
  - `采用后，这个版本会成为后续甘特图、周计划、资源排班和报表的正式依据。确定采用吗？`
- 成功后提示：
  - `已正式采用 v17。`

**技术路线**：

- 发布前重新校验草稿是否基于最新正式版本。
- 发布不能原地改旧版本，必须生成新正式版本。
- 写审计：
  - 谁发布
  - 基于哪个版本
  - 发布成哪个版本
  - 改了哪些工序
  - 发布原因
- `VersionResolution` 仍然是结果页的统一版本入口。

**验收标准**：

- 发布后甘特图、周计划、资源排班、报表、历史页都读新版本。
- 旧版本仍可回看。
- 审计记录能看出谁做了这次正式采用。
- 并发发布要能阻止旧草稿覆盖新正式版本。

### 后续路线：模拟调整文档、帮助和浏览器压测

**目标**：让用户知道怎么用，也让后续能复测。

**用户看到的变化**：

- 说明书清楚分开：
  - 查看模式
  - 时间缩放
  - 模拟调整
  - 保存模拟方案
  - 正式采用
- 页面帮助不再说空泛术语。

**技术路线**：

- 更新 `static/docs/scheduler_manual.md`。
- 更新页面帮助 viewmodel。
- 更新浏览器压测手册。
- 增加至少一套复杂数据验收：
  - 短工序
  - 长工序
  - 外协
  - 缺资源
  - 设备冲突
  - 工序倒挂
  - 草稿保存
  - 模拟方案预览
  - 正式采用

**验收标准**：

- 浏览器能按手册复跑。
- 调度员不需要懂算法词，也能看懂冲突提示。
- 文档和页面真实行为一致。

### 后续路线：组件升级评估

**目标**：用真实证据决定继续 Frappe、封装 Frappe，还是换 Bryntum / DHTMLX / Syncfusion。

**用户看到的变化**：

- 这一阶段主要是技术验证，不一定直接改变页面。

**技术路线**：

- 在 Win7 Chrome 109、离线静态资源、当前数据量下做最小 POC。
- 对比：
  - 小时 / 分钟缩放
  - 只读模式
  - 拖动事件
  - 依赖线
  - 资源视图
  - 性能
  - 授权和离线部署
- 只有 Frappe 明确撑不住后续编辑能力时，才启动替换路线。

**验收标准**：

- 有 POC 证据，而不是凭感觉换组件。
- 不破坏 Win7、Python 3.8、离线交付边界。

## 6. 模块间接口契约 / 共享协议（架构层详设）

### 6.1 甘特查看状态协议

**方向**：后端页面模板 → 前端甘特图脚本

**形式**：`#gantt` 的 `data-*` 属性 + URL query

**契约**：

```text
data-gantt-mode: "view"
data-zoom-level: "month" | "week" | "day" | "half-day" | "quarter-day" | "hour" | "fifteen-minute" | "five-minute" | "one-minute"
data-version: str
data-plan-role: str
data-start-date: YYYY-MM-DD
data-end-date: YYYY-MM-DD
data-range-source: str
task-business-id: base_version + base_plan_role + schedule_id + op_id

URL query:
gantt_mode=view
gantt_zoom=month|week|day|half-day|quarter-day|hour|fifteen-minute|five-minute|one-minute
gantt_color=batch|priority|source|status
gantt_deps=critical|process|none
gantt_batch=<batch_id>
gantt_resource=<machine_id_or_operator_id>
```

**约束**：

- 默认 `gantt_mode=view`，查看模式必须禁用拖动和拉伸。
- 默认 `gantt_zoom=day`，但页面必须允许用户切到小时级。
- URL 参数必须能复现当前视图，方便用户发给别人一起看。
- 旧参数 `gantt_vm=Day|Week|Month` 可以兼容读取，但新实现以 `gantt_zoom` 为主。
- 页面日期 `start_date/end_date` 是本地日期。
- `start_date` 解释为当天 `00:00:00`。
- `end_date` 解释为当天 `23:59:59`。
- 后端若内部使用 `end_exclusive`，可以转换成次日 `00:00:00`，但页面、提示、测试都按 `23:59:59` 解释。
- 第一版只读甘特图不新增任何保存、草稿、正式采用动作。
- 第一版不允许 `simulate`、`adopt` 作为页面模式。后续 `simulate` 是编辑模式，`adopt` 是正式发布动作，不是甘特图查看模式。

### 6.2 甘特缩放配置

**方向**：前端 UI → 甘特适配层 → Frappe Gantt 或未来组件

**形式**：普通 JS 对象

**契约**：

```text
GanttZoomSpec:
  level: str                 # month/week/day/half-day/quarter-day/hour/fifteen-minute/five-minute/one-minute
  label: str                 # 月视图/周视图/日视图/12小时/6小时/小时/15分钟/5分钟/1分钟
  step_minutes: int          # 每一格代表多少分钟
  column_width_px: int       # 每一格宽度
  snap_minutes_view: int     # 查看模式点击/定位辅助，不保存
  snap_minutes_edit: int     # 模拟调整模式拖动吸附粒度
  min_hitbox_px: int         # 短工序点击热区，不等于真实显示宽度
  max_range_days: int | null # 当前粒度允许一次显示的最大天数
```

**建议初始值**：

```text
month:          step_minutes=43200, column_width_px=120, max_range_days=null
week:           step_minutes=10080, column_width_px=140, max_range_days=null
day:            step_minutes=1440,  column_width_px=38,  max_range_days=62
half-day:       step_minutes=720,   column_width_px=56,  max_range_days=31
quarter-day:    step_minutes=360,   column_width_px=56,  max_range_days=21
hour:           step_minutes=60,    column_width_px=48,  max_range_days=14
fifteen-minute: step_minutes=15,    column_width_px=32,  max_range_days=7
five-minute:    step_minutes=5,     column_width_px=24,  max_range_days=3
one-minute:     step_minutes=1,     column_width_px=18,  max_range_days=1
```

**约束**：

- 显示宽度必须按真实毫秒差计算，不能再用向下取整的小时/天差。
- 15 分钟、5 分钟和 1 分钟级可能非常宽，必须支持横向滚动，并限制日期范围。
- 小于 1 小时的工序必须看得见、点得到，但不能把真实时长夸大成更长的条。
- 假期/停工背景、今天高亮、关键链线条必须跟缩放比例同步。
- Win7 Chrome 109 下不能依赖新的浏览器 API。

### 6.3 后续调整草稿请求

**方向**：前端模拟调整 → 后端校验 / 草稿服务

**形式**：HTTP JSON API

**契约**：

```text
POST /scheduler/gantt/adjustments/validate
Request:
  {
    "request_id": "uuid-or-client-generated-id",
    "base_version": 15,
    "base_plan_role": "adopted",
    "draft_id": "optional-draft-id",
    "operation_id": 123,
    "schedule_id": 456,
    "batch_id": "B001",
    "drag_type": "move_time" | "resize_time" | "change_resource",
    "from_start": "2026-05-06 10:00:00",
    "from_end": "2026-05-06 11:00:00",
    "from_resource_id": "M01",
    "to_start": "2026-05-06 14:30:00",
    "to_end": "2026-05-06 15:30:00",
    "to_resource_id": "M01",
    "snap_minutes": 15,
    "repair_strategy": "single_op" | "shift_downstream" | "local_reschedule",
    "reason": "用户填写的调整原因"
  }

Response:
  {
    "status": "ok" | "blocked" | "warning" | "stale_version",
    "message": "给调度员看的中文说明",
    "draft_id": "optional-draft-id",
    "affected_operations": [...],
    "conflicts": [...],
    "resource_deltas": [...],
    "due_date_impact": {...},
    "refresh_hint": {...}
  }
```

**约束**：

- 本节只作为后续模拟调整合同，第一版只读甘特图不得新增这个接口。
- 任何保存前都必须走后端校验。
- `base_version` 必须仍存在，且没有被新的正式采用动作覆盖。
- `snap_minutes` 来自当前缩放/调整粒度，但后端仍要按真实时间校验，不能只信前端。
- 返回的 `message` 必须是业务中文，不暴露内部对象、图结构或算法调试样本。

### 6.4 后续 Draft / Scenario / Official Version 保存与发布

**方向**：前端模拟调整 → 后端草稿 / 版本服务 → 结果页

**形式**：HTTP JSON API + 版本查询服务

**契约**：

```text
POST /scheduler/gantt/adjustments/save-draft
Request:
  {
    "base_version": 15,
    "base_plan_role": "adopted",
    "draft_id": "optional-draft-id",
    "changes": [GanttAdjustmentChange],
    "reason": "保存说明"
  }
Response:
  {
    "status": "saved",
    "draft_id": "draft-20260522-001",
    "scenario_id": "scenario-20260522-001",
    "message": "已保存为模拟方案，正式计划还没有改变。"
  }

POST /scheduler/gantt/adjustments/publish
Request:
  {
    "scenario_id": "scenario-20260522-001",
    "base_version": 15,
    "confirm_text": "正式采用",
    "reason": "正式采用原因"
  }
Response:
  {
    "status": "published",
    "new_version": 17,
    "message": "已正式采用 v17。后续甘特图、周计划和报表都会按 v17 查看。"
  }
```

**约束**：

- 本节只作为后续模拟调整合同，第一版只读甘特图不得新增保存和发布接口。
- 后续版本模型固定为 `Draft -> Scenario -> Official Version`。
- Draft 是草稿，Scenario 是模拟方案，Official Version 是正式版本；三者不能混用。
- 保存草稿不能改变正式版本指针。
- 发布必须重新校验草稿，防止别人已经发布了更新版本。
- 正式采用必须二次确认，原因必填。
- 发布不能原地改旧 `Schedule` 行，必须生成新版本。
- 甘特图、周计划、资源排班、报表、历史页必须通过统一版本解析读取新版本。
- 审计日志至少记录：谁、什么时候、基于哪个版本、改了哪些工序、为什么改、发布成哪个版本。

### 6.5 冲突提示结构

**方向**：后端校验服务 → 前端冲突面板 / 提示条

**形式**：JSON 列表

**契约**：

```text
GanttAdjustmentConflict:
  code: str
  severity: "blocker" | "warning"
  operation_id: int
  batch_id: str
  resource_id: str | null
  start_time: str | null
  end_time: str | null
  user_message: str
  suggested_actions: list[str]
```

**示例**：

```text
{
  "code": "machine_overlap",
  "severity": "blocker",
  "operation_id": 123,
  "batch_id": "B001",
  "resource_id": "M01",
  "start_time": "2026-05-06 10:00:00",
  "end_time": "2026-05-06 12:00:00",
  "user_message": "不能放到这里：设备 M01 在 10:00 到 12:00 已经安排了 B002 第10道工序。",
  "suggested_actions": ["换一个时间", "换一台设备", "重新计算受影响工序"]
}
```

**约束**：

- 不允许只返回 `error` 或内部异常名。
- 不允许把 NetworkX 节点、原始对象、完整诊断样本直接给前端。
- 每条冲突必须能让用户知道下一步怎么处理。

## 7. 子 feature 清单

1. **gantt-readonly-foundation-contract** — 阶段 0 只读甘特图基础合同与 vendor 治理。
   - 所属模块：只读基础合同与 vendor 治理
   - 依赖：无
   - 状态：done
   - 对应 feature：`2026-05-22-gantt-readonly-docs-and-qa`
   - 备注：明确本地自然日、缩放枚举、任务业务身份、只读边界和 vendor 补丁证据。

2. **gantt-readonly-result-mode** — 阶段 1 甘特图查看模式收口。
   - 所属模块：查看模式与交互边界
   - 依赖：`gantt-readonly-foundation-contract`
   - 状态：done
   - 对应 feature：`2026-05-22-gantt-readonly-docs-and-qa`
   - 备注：默认只读，不能拖动或拉伸，点击详情、筛选、配色、关键工序和依赖线保留。

3. **gantt-readonly-time-zoom** — 阶段 2 只读甘特图时间缩放。
   - 所属模块：时间缩放与时间尺
   - 依赖：`gantt-readonly-result-mode`
   - 状态：done
   - 对应 feature：`2026-05-22-gantt-readonly-docs-and-qa`
   - 备注：支持 `month/week/day/half-day/quarter-day/hour/fifteen-minute/five-minute/one-minute`，URL 可复现，不做保存。

4. **gantt-readonly-decoration-sync** — 阶段 3 缩放后的视觉标记对齐。
   - 所属模块：缩放后的视觉标记对齐
   - 依赖：`gantt-readonly-time-zoom`
   - 状态：done
   - 对应 feature：`2026-05-22-gantt-readonly-docs-and-qa`
   - 备注：短条 hitbox、假期/停工背景、今天高亮、关键工序外框、超期红框、外协虚线、依赖线都随缩放对齐。

5. **gantt-readonly-performance-guards** — 阶段 4 分钟级视图范围保护和性能压测。
   - 所属模块：性能范围保护
   - 依赖：`gantt-readonly-decoration-sync`
   - 状态：done
   - 对应 feature：`2026-05-22-gantt-readonly-docs-and-qa`
   - 备注：1 分钟第一版不做虚拟滚动，先用 `max_range_days`、列数和节点数保护守住 Win7 Chrome 109。

6. **gantt-readonly-docs-and-qa** — 阶段 5 说明书、页面帮助和浏览器验收收口。
   - 所属模块：用户提示与验收手册
   - 依赖：`gantt-readonly-performance-guards`
   - 状态：done
   - 对应 feature：`2026-05-22-gantt-readonly-docs-and-qa`
   - 备注：把查看模式、缩放、短工序点击、范围保护、浏览器压测和回归测试全部落地。

7. **gantt-adapter-contract** — 后续甘特适配层。
   - 所属模块：后续模拟调整合同
   - 依赖：`gantt-readonly-docs-and-qa`
   - 状态：done
   - 对应 feature：`2026-05-22-gantt-adapter-contract`
   - 备注：已新增薄适配层；当前阶段不开放模拟调整保存。

8. **gantt-simulation-entry-shell** — 后续模拟调整入口壳。
   - 所属模块：后续模拟调整合同
   - 依赖：`gantt-adapter-contract`
   - 状态：done
   - 对应 feature：`2026-05-22-gantt-simulation-entry-shell`
   - 备注：已完成灰色占位入口，不开放拖动、草稿保存或正式采用。

9. **gantt-adjustment-draft-model** — 后续 Draft 草稿模型。
   - 所属模块：后续模拟调整合同
   - 依赖：`gantt-simulation-entry-shell`
   - 状态：planned
   - 对应 feature：未启动
   - 备注：草稿只记录用户想怎么改，不写正式 `Schedule/ScheduleHistory`；模拟入口边界清楚后再落库。

10. **gantt-adjustment-validate-simulate** — 后续拖动落点校验与试算。
    - 所属模块：后续模拟调整合同
    - 依赖：`gantt-adjustment-draft-model`
    - 状态：planned
    - 对应 feature：未启动
    - 备注：只校验和试算，不发布正式版本。

11. **gantt-draft-save-and-preview** — 后续 Scenario 模拟方案保存和预览。
    - 所属模块：后续模拟调整合同
    - 依赖：`gantt-adjustment-validate-simulate`
    - 状态：planned
    - 对应 feature：未启动
    - 备注：保存成模拟方案，正式计划仍不改变。

12. **gantt-draft-publish-official-version** — 后续 Official Version 正式采用。
    - 所属模块：后续模拟调整合同
    - 依赖：`gantt-draft-save-and-preview`
    - 状态：planned
    - 对应 feature：未启动
    - 备注：必须二次确认、原因必填、重新校验、生成新正式版本、写审计记录。

13. **gantt-component-upgrade-spike** — 后续甘特组件升级评估。
    - 所属模块：后续模拟调整合同
    - 依赖：`gantt-draft-publish-official-version`
    - 状态：planned
    - 对应 feature：未启动
    - 备注：这是 spike，不阻塞只读和缩放；主线模拟调整闭环完成后再评估，只有 Frappe 确实撑不住时才提出替换。

**最小闭环**：第 1 到第 6 条一起构成第一版闭环。它做完以后，用户打开当前甘特图会明确看到“查看模式”，条形图不能再被拖动或拉伸，月/周/日/12小时/6小时/小时/15分钟/5分钟/1分钟都能切换，短工序可见可点，范围过大时系统主动拦截，说明书和回归测试也都同步。模拟调整不在这个闭环里。

## 8. 排期思路

这条路线按“先可信、再看细、再能改”的顺序推进：

1. **先可信**：`gantt-readonly-result-mode` 先做。它解决当前最伤信任的问题：页面看起来能拖，实际什么都没保存。
2. **再看细**：`gantt-readonly-time-zoom` 第二个做。它解决你指出的“一拖就是一天、看不到小时分钟”的核心体验问题，而且它不改业务数据，风险比模拟调整低。
3. **再收边界**：`gantt-adapter-contract` 第三个做。它不是炫技，而是为了后面的模拟调整不继续靠补丁堆。
4. **最后再调整**：模拟调整拆成入口、草稿、校验、预览、正式采用五段。每段都有单独验收，任何一段没做完，都不能假装“拖动已经正式生效”。

这个顺序的好处是：每完成一步，用户都能立刻得到一个可信能力；任何阶段停下来，系统也不会处于半真半假的危险状态。

## 9. 观察项

- 改造前 `templates/scheduler/gantt.html` 只开放 `Day / Week / Month` 三个时间粒度，`static/js/gantt_ui.js` 也只接受这三种值；本轮只读缩放改造已经把第一版 9 档缩放作为必须验收项。
- 当前压缩版 `static/js/frappe-gantt.min.js` 内部已有 `Quarter Day` 和 `Half Day` 模式，但没有页面入口，也没有 APS 级 `hour / fifteen-minute / five-minute / one-minute` 缩放协议。
- 当前 Frappe 拖动吸附逻辑主要按当前列宽吸附，日视图下移动一格就是一天；即使短工序显示修好了，拖动颗粒度也仍然太粗。
- 改造前说明书 `static/docs/scheduler_manual.md` 已写“甘特图不支持拖拽任务条来改计划”，但真实页面仍可能被拖动；本轮只读查看模式必须把说明和真实行为对齐。
- `web_new_test/templates/scheduler/gantt.html` 必须同步模板改动，避免界面模式切换后两套模板口径漂移。
- 资源排班页也有内嵌甘特图，它的时间粒度和只读/编辑边界后续需要单独核对，避免两个甘特页面行为不一致。
- 报表默认不读取 Scenario 模拟方案；只有用户显式选择 Scenario 预览时才展示。后续 `gantt-draft-save-and-preview` 前仍要核实每个报表入口是否都遵守这条。

## 10. 变更日志

- 2026-05-22：新建路线图，覆盖甘特图只读查看、时间缩放、模拟调整草稿、后端校验、Scenario 模拟方案预览、正式采用和说明书验收。
- 2026-05-22：按 review 意见重写为“先查看模式、再缩放、再后续调整能力”的阶段路线；补充每阶段用户变化、技术路线、验收标准和明确不做。
- 2026-05-22：按讨论拍板把时间缩放主线收口为小时、15 分钟、5 分钟、1 分钟；当前 roadmap 不纳入秒级、0.1 秒和精细模式。
- 2026-05-22：完成只读甘特图第一版闭环，前 6 个只读阶段回写为 done；模拟调整、草稿、Scenario 和正式发布仍保留为后续 planned 路线。
- 2026-05-22：启动模拟调整入口壳；按对抗性审查结论，第一步只做禁用占位入口，不做“能拖但不保存”的半成品。
- 2026-05-22：完成模拟调整入口壳；页面显示禁用态“模拟调整（后续开放）”，说明书和回归测试锁住“不保存、不发布、不进入真实 simulate”。

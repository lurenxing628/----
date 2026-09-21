---
doc_type: roadmap
slug: workbench-file-imports-and-templates
status: implemented
created: 2026-09-21
last_reviewed: 2026-09-21
---

# 实施记录

按 roadmap 条目顺序记录实际做法、与方案的差异、验证证据。每条完成后追加，不覆盖前面的内容。

---

## 1. wbfile-calendar-consistency-fix（2026-09-21 完成）

### 问题

全局日历保存工时时，领域层会用"班次开始加工时"推出班次结束并一起存库（`core/services/scheduler/calendar/admin.py:108-112`）。之后再只改工时，工作台的一致性校验会把库里那个派生值当成事实，反过来用它算工时，于是判定"和你填的对不上"并拒绝。实测：

| 操作 | 修复前 | 修复后 |
|---|---|---|
| 某天存成 8 小时，再改 10 小时 | 拒绝 | 通过，班次结束由 16:00 重推为 18:00 |
| 某天存成休息，再改回上班 8 小时 | 拒绝 | 通过 |
| 只改效率（对照组） | 通过 | 通过 |
| 跨夜班表 22:30 到 06:30 那天只填 6 小时 | 拒绝 | 拒绝（有意保留） |

单日编辑与范围批量维护共用同一条校验链（`apply` 与 `_preview_days` 都调 `_proposed`，`_proposed` 调 `_check_proposed`），所以两条路径都受影响。

### 关键判断：判据不能是"本次有没有填班次起止"

第一版改成"本次没有单独设置班次起止时，就把库里的班次结束当派生值清掉"。这个判据看起来直接，实际是错的：它会把用户真实设置的跨夜班表也当成派生值重推，等于把 22:30 到 06:30 的夜班悄悄改成 08:00 开始的白班。跑测试立刻暴露，`tests/workbench/test_calendars.py` 与 `test_calendar_api.py` 里 4 个以 `NIGHT` 夹具（真实夜班 22:30 到 06:30）为场景的用例失败。

改用的判据是**开工时刻是否仍为默认值**。界面只让改工时、不让单独设置班次起止，所以开工时刻还是默认值的那些天，班次结束必然是推出来的；开工时刻不是默认值的是真实班表，只填工时会与它冲突，仍要拒绝并让用户先核对班表。库里没有单独记录"班次是谁设的"，这是在不改表结构的前提下能取到的最准判据，代码注释里已写明这一点。

### 改了什么

- `core/services/scheduler/calendar/admin.py`：提取模块级常量 `DEFAULT_SHIFT_START`，替换原先硬编码的默认开工时刻字面量，作为两层共用的单一来源。
- `core/services/workbench/resource/calendars.py`：新增 `_shift_window_is_derived(patch, row)`；`_proposed` 在判定为派生时清掉库里的班次结束让它按新工时重推；`_check_proposed` 新增 `derived_shift_window` 参数，派生时把班次结束排除在"未改项被规则改写"的比较之外。第二条"工时与班次起止对不上"的校验在显式填写班次起止时行为不变。
- `tests/workbench/test_calendars.py`：新增三个合同测试，分别锁住派生班次跟着工时重推、休息改回上班不误判、范围维护与单日保存同口径且真实班表仍拒绝。

### 验证

```
.venv/bin/python -m pytest -q tests/workbench/test_calendars.py tests/workbench/test_calendar_api.py
186 passed

.venv/bin/python -m pytest -q tests/calendar_maintenance/ tests/workbench/test_operator_shift_calendar.py \
  tests/workbench/test_plan_calendar.py tests/workbench/test_resource_calendar_summary.py \
  tests/workbench/test_zero_duration_calendar.py tests/workbench/test_resource_file_calendar_connection.py
407 passed

.venv/bin/python -m ruff check core/services/workbench/resource/calendars.py \
  core/services/scheduler/calendar/admin.py tests/workbench/test_calendars.py
All checks passed
```

未跑全量质量门禁，按用户既有约束只跑受影响专项。工作区有其他未提交改动，本条不构成干净工作区证明。

### 补充：浏览器探针同步（做第 2 条时才发现）

`tests/workbench/resource_aux_probe.cjs` 原来锁的正是这个缺陷行为：它在 2026-09-10 只填工时保存后点「休息日」，断言服务端返回 409 且提示"班次起止"被改写，记为 `retained-shift-window-protected`。修复后这一步变成 200。核对过界面只读展示班次起止、没有输入控件（`CalendarFields.jsx:36`），所以工作台上任何班次起止都是系统推出来的，这条断言在界面场景下是纯误伤。已把它改成锁新行为（能存成休息日、存后工时为 0），并在注释里写明真实跨夜班表仍要拒绝那条由 `tests/workbench/test_calendars.py` 的隐藏班次结束用例锁住。

---

## 2. wbfile-operator-machine（2026-09-21 完成）

### 与方案的三处差异

**服务层放在资源簇内，不新建顶层簇。** 原计划建 `core/services/workbench/relation_files/`。实际跑 `tests/gate_meta/test_workbench_cluster_layering.py` 报 `KeyError: 'relation_files'`：工作台的簇分层是有合同的，新顶层簇必须登记进分层表。而这个模块依赖资源查询服务、资源文件仓储、资源动作模型，本来就属于资源域，单独立簇只会造出一条 `relation_files → resource` 的跨簇依赖。改为 `core/services/workbench/resource/relation_files/`，分层表不用动，注册表作用域也被既有的 `core/services/workbench/resource/**/*.py` 覆盖。

**前端没做表选择层。** 原计划做 `FileTargetPicker.jsx` 让用户在"人员资料 / 可操作设备"之间选。实际改为人员页工具栏直接多出「导入可操作设备」「导出可操作设备」两个按钮：只有一类关联资料时，多一次点击换不来任何信息。按钮名字来自 `adapter.relationLabel(kind)`，`ResourceWorkspace.jsx` 不写死"可操作设备"四个字；将来加人员日历文件时，在 `ResourceLive.jsx` 的 `relationOf` 映射里加一项即可。

**共享弹窗的扩展点是四个契约字段，不是"扩展点"。** 原计划给 `ResourceMaterialActions.jsx` 加两个向后兼容扩展点。实际发现它里面有四处按 `kind === 'material'` 分叉的硬编码，都搬进了契约：`confirmationHint`（逐行提示）、`acknowledgeHint`（勾选文案）、`scopeLabel`（导出范围说的是哪类东西）、`rowsMatchSelection`（勾选几条是否就导出几行）。前三个对既有家族取值与原来逐字相同。

### 顺手修掉的一个既有缺陷

`ResourceMaterialActions.jsx` 原来无条件校验"导出预检行数必须等于勾选条数"。这条对一条记录出一行的家族成立，对关联资料是误报：勾 3 个人，名下 7 台设备，导出 7 行会被判成失败。改成由契约的 `rowsMatchSelection` 控制，关系家族置 false，并在契约里写明原因。

### 两个必须说明的实现点

**预检行的初始状态就是 rejected。** `action_row()` 默认 `result="rejected"`（默认不放行）。第一版我用 `row["result"] == "rejected"` 当"这行已出错"的判据，结果每一行都被当成已拒、分类逻辑整段被跳过，预检返回全 rejected 但 errors 为空。改成看 `row["errors"]` 是否非空，抽成模块级 `_blocked(row)` 并写明原因。

**确认阶段自己挡住拒绝行。** 资源家族靠路由层把 `can_confirm` 置 false 来挡，服务层的 `confirm_import` 只是跳过拒绝行。关系家族在 `confirm_import` 里直接 `WorkbenchCommandRejected`：整批原子这条合同不该依赖调用方记得看 `can_confirm`。

### 主操连带的处理

底层 `OperatorMachineService` 写入主操时会清掉同一个人其他设备的主操标记。所以预检阶段先按人算出"最终主操是哪一台"（`_final_primaries`），每一行的结果都据此得出，确认阶段照这个结果写、并把主操那行排到最后。用户在预检里就能看到"确认后 XX 不再是这个人的主操设备"，以及"这一行没有填主操设备，但同一份文件把主操给了别的设备，所以这里会变成非主操"。同一个人多行填"是"整组拒绝，不替用户挑。

`_final_primaries` 和 `_classify` 第一版圈复杂度都是 19，超过门禁阈值 15。按职责拆成 `_claimed_primaries` / `_current_primary` / `_primary_for` 和 `_after_values` / `_diff` / `_add_primary_notes`，没有登治理台账。

### 改了什么

新增：`core/models/workbench_relation_file.py`、`core/services/workbench/resource/relation_files/{__init__,file_codec,file_writer,files}.py`、`web/routes/workbench/relation_files.py`、`frontend/workbench/app/RelationFile{Contract.js,Actions.jsx}`（含 `static/workbench/app/` 两个产物）、`tests/workbench/{relation_file_support.py,test_relation_files.py,test_relation_file_api.py,relation_files_live_probe.cjs}`。

改动：`web/routes/workbench/registration.py`（注册路由）、`frontend/workbench/app/{resource-api.js,ResourceLive.jsx,ResourceWorkspace.jsx,ResourceMaterialContract.js,ResourceMaterialActions.jsx,ResourceMaterialPreview.jsx}`、`scripts/workbench/build-order.json`、`tools/test_registry_groups_workbench.py`、`tests/workbench/{resource_live_probe.cjs,resource_aux_probe.cjs}`。

### 验证

```
.venv/bin/python -m pytest -q tests/workbench/test_relation_files.py tests/workbench/test_relation_file_api.py
33 passed

.venv/bin/python -m pytest -q <workbench_resources 组全部 38 个文件>
2094 passed

.venv/bin/python -m pytest -q tests/gate_meta/
1257 passed（含簇分层、圈复杂度、文案词表）

.venv/bin/python -m pytest -q tests/workbench/test_resource_live_browser.py
1 passed（真机 Chromium 109，含新增 6 个关系文件场景乘 4 种视口主题，数据库逐表隔离断言通过）
```

真机探针的清理段落顺带验证了一条真实路径：文件导进来的关联，在人员详情的「编辑可操作设备」里解得掉——人员和设备只要还带着关联就删不掉（`core/services/workbench/resource/bulk.py:48`），所以探针必须先解除再删，数据库才能回到进入场景前的样子。

未跑全量质量门禁。工作区有其他未提交改动，本条不构成干净工作区证明。

---

## 3. wbfile-work-calendar（2026-09-21 完成）

### 三处与方案不同的裁决

**预检存储用上下文存储，不用日历现有的进程内存储。** roadmap 4.6 要求二选一。选上下文存储的理由是它与关系家族、资源家族同一条路径：前端契约完全一致，不用新增 `preview_capacity` 503 错误码，也不用为它写前端提示。代价是上传的文件字节在内存里留 15 分钟，单机离线场景可接受，关系家族已经这么做了。

**导出预检自己算读快照，不要求前端先持有一个。** roadmap 4.1 把 `snapshot_ref` 写成必填。实际做的时候发现日历页拿不出可绑的东西：月视图的快照绑的是一个月，导出范围是任意区间。所以新增 `range_snapshot(start, end)`，导出预检自己算并把 `snapshot_ref` 返回给前端；前端再次预检同一范围时可以带上它，范围内容变了就会被判过期（有测试锁住这两种情况）。

**导出只列已经单独配置过的日期。** roadmap 没写这一条。如果把范围内每一天都导出来，用户回导时会把"周末默认休息、工作日默认 8 小时"这些默认规则全部固化成显式数据行——一年就是 365 条。只导已配置的日期，导出文件原样回导必然全是"不变"，这条由测试和真机探针各锁一遍。模板说明里写明了这一点。

### 假期加班：保留 roadmap 的裁决，但补上提示

界面的输入模型禁止"假期 + 非零工时"（`core/models/workbench_calendar.py:77-81`），领域层允许。实施时复核过是否该把文件也收紧成和界面一致，结论是不收紧：`day_type` 决定留空时按哪个默认效率算，假期加班的效率通常和平时不同，禁掉会丢掉这个表达。但公开投影会把"假期且有工时"显示成工作日（`web/routes/workbench/calendars_projection.py:17-19`），所以预检对这种行加一条提示并要求勾选核对："这一天是假期但安排了工时，效率按排产设置里的假期效率算；日历页上会显示成工作日。"

### 复用日历服务的方式

文件家族不复制日历的领域校验，而是调 `WorkbenchCalendarService` 新增的三个公开入口：`range_states`（已有）一次读回整段、`day_state` 取某天完整状态、`proposed_row` 走与日历页同一条一致性校验、`write_day` 写一天。分成这三步是因为 roadmap 4.7 禁止逐行取快照：逐日调 `snapshot()` 会开上千次事务。`proposed_row` 收的是界面字段名但不经过界面的输入模型，这正是文件能表达假期加班的原因，函数注释里写明了。

### 顺手抽出的共用件

关系家族和日历家族的导入路由形状完全一样，把重复的五段抽进 `web/routes/workbench/resource_action_context.py`：`issue_file_preview`、`upload_body`、`download_args`、`file_response`、`confirm_body`、`resolve_import_preview`。资源家族的 `issue_preview` 还要兼顾批量删除（没有 `file_sha256`），没有并进来。关系家族改用共用件后 33 个测试原样通过。

### 改了什么

新增：`core/models/workbench_calendar_file.py`、`core/services/workbench/resource/calendar_files/{__init__,file_codec,file_writer,files}.py`、`web/routes/workbench/calendar_files.py`、`frontend/workbench/app/CalendarFile{Contract.js,Actions.jsx}`（含产物）、`tests/workbench/{calendar_file_support.py,test_calendar_files.py,test_calendar_file_api.py,calendar_files_live_probe.cjs}`。

改动：`core/services/workbench/resource/calendars.py`（三个公开入口）、`web/routes/workbench/{registration.py,resource_action_context.py,relation_files.py}`、`frontend/workbench/app/{resource-api.js,ResourceLive.jsx,ResourceCalendar.jsx,ResourceMaterialContract.js,ResourceMaterialActions.jsx}`、`scripts/workbench/build-order.json`、`tools/test_registry_groups_workbench.py`、`tests/workbench/resource_live_probe.cjs`。

### 验证

```
.venv/bin/python -m pytest -q tests/workbench/test_calendar_files.py tests/workbench/test_calendar_file_api.py
68 passed

.venv/bin/python -m pytest -q tests/workbench/test_calendar_files.py tests/workbench/test_calendar_file_api.py \
  tests/workbench/test_relation_files.py tests/workbench/test_relation_file_api.py \
  tests/workbench/test_calendars.py tests/workbench/test_calendar_api.py tests/gate_meta/
1547 passed

.venv/bin/python -m pytest -q tests/workbench/test_resource_live_browser.py
1 passed（真机 Chromium 109，新增 5 个日历文件场景乘 4 种视口主题，数据库逐表隔离断言通过）
```

真机探针的清理段落走的正是模板说明里写给用户的那条路：文件不做删除，要把某一天恢复成默认规则得用批量维护里的清除。

未跑全量质量门禁。工作区有其他未提交改动，本条不构成干净工作区证明。

---

## 4. wbfile-operator-calendar-editing（2026-09-21 完成）

### 核心裁决：个人日历以班次起止为准，工时不让用户填

全局日历只给工时、班次结束由系统按默认开工时刻推出来，第 1 条 feature 修的就是这个派生值反过来被当成事实的问题。个人日历的语义本来就是"这个人这天几点到几点上班"，所以这里直接以班次起止为准：用户填开始和结束，领域层的 `_normalize_shift_window` 按起止算工时；只填开始时按 8 小时推结束。界面上工时是只读的结果，不给输入框，从根上没有两个真相源。跨零点的夜班靠"结束早于开始"表达，有测试锁住 22:00–06:00 存成 8 小时。

### 写能力由月视图自己签发

roadmap 4.13 写的是"在人员详情的写上下文能力里新增 operator.calendar"。实际改成个人日历月视图接口自己签发这三个动作的写令牌，令牌绑的仍是人员当前状态（`reader.detail(ref).state`）。谁提供数据谁签能力，界面不用先拉一次人员详情再拉日历；人员被别人改过时令牌照样失效。有测试锁住两件事：别人的令牌改不了这个人的日历，月视图签的令牌也改不了人员本身。

### 范围清除是文件不做删除的前提

个人日历原先没有任何批量删除入口，界面上还明写"人员专属日历不变"。如果只做单日编辑，用户用文件导错一年就只能逐日清或者删人让数据级联消失。面板里的「按日期范围清除」是两段式：先只读预检这段时间里哪些天单独设过，再确认清掉。真机探针走的就是这条路。

### 面板的加载顺序约束

`ResourceWorkspace.jsx` 要渲染这个面板，构建器的静态依赖检查就要求面板先于它加载。而面板原本引用了在它之后加载的 `ResourceForms.Feedback` 和 `CalendarFields.Segment`，构建直接失败。按 `OperatorMachinePermissions.jsx` 的既有做法处理：反馈组件由宿主用 props 注入，分段按钮和刷新提示在面板内自带（各六行）。契约文件 `OperatorCalendarContract.js` 只依赖 `resource-contract.js`，放到了 `CalendarContract.js` 之后。

### 改了什么

新增：`core/models/workbench_operator_calendar.py`、`core/services/workbench/resource/operator_calendars.py`、`web/routes/workbench/operator_calendars.py`、`frontend/workbench/app/OperatorCalendar{Contract.js,Panel.jsx}`（含产物）、`tests/workbench/{test_operator_calendars.py,test_operator_calendar_api.py,operator_calendar_live_probe.cjs}`。

改动：`data/repositories/workbench_calendar_query_repo.py`（个人日历的行与身份读取）、`web/routes/workbench/registration.py`、`frontend/workbench/app/{resource-api.js,ResourceForms.jsx,ResourceWorkspace.jsx}`、`scripts/workbench/build-order.json`、`tools/test_registry_groups_workbench.py`、`tests/workbench/resource_live_probe.cjs`。

### 验证

```
.venv/bin/python -m pytest -q tests/workbench/test_operator_calendars.py tests/workbench/test_operator_calendar_api.py
43 passed

.venv/bin/python -m pytest -q <上面两个> tests/workbench/test_calendar_files.py tests/gate_meta/ \
  tests/workbench/test_ui_copy_glossary.py tests/workbench/test_fe01_resource_static_contract.py
1384 passed

.venv/bin/python -m pytest -q tests/workbench/test_resource_live_browser.py
1 passed（真机 Chromium 109，新增 3 个个人日历场景乘 4 种视口主题，数据库逐表隔离断言通过）
```

实施中被文案词表拦下六处：「预览」要写成「预检」、「引用」要写成「编号」、「跨度」要写成「时长」，已全部改掉。

未跑全量质量门禁。工作区有其他未提交改动，本条不构成干净工作区证明。

---

## 5. wbfile-operator-calendar-file（2026-09-21 完成）

### 能力对齐：界面存不了的组合，文件也存不了

roadmap 要求"与面板做能力对齐"。对齐点只有一个真问题：人员详情规定上班的日子必须挑班次开始（`workbench_operator_calendar._fields`），而领域层对缺失的开始时刻会补 08:00（`CalendarAdmin._normalize_shift_window` 的 `DEFAULT_SHIFT_START`）。所以判据不能看算完的行——算完的行永远有开始时刻——只能看填进来的值：

- 这一天原来就上班：班次开始可以留空，继承那条已经确认过的窗口；
- 新建的一天、或者把假期改回上班：必须自己填，不然 08:00 会悄悄替用户做主。

这两条都有测试锁住，文件和面板各跑一遍同一个"上班但没填开始"的输入，两边都拒绝。

### 顺手修掉第 4 条留下的一个缺陷

写第 5 条时发现 `WorkbenchOperatorCalendarService._proposed` 没有以当天原行为基底：面板每次都提交完整字段所以看不出来，但文件的"空格子保持原样"会因此把没填的项清成默认值。已改成先铺原行再打补丁，并且改成休息日时显式清掉班次，否则基底里的班次会把工时带回来，变成"休息日还有 8.5 小时"。

### 人员范围导出

个人日历的文件从人员页开，所以导出多一维人员：`scope.operator_refs` 不给就是全部人员，给了就只导这几个人。前端把日期区间和人员范围合成一个 `ExportScope`，列表里勾了人就默认「已选人员」。服务端把这次的人员范围原样回显在 `range` 里，前端对不上就不下载，避免导出的是别人的日历。编号本身不合法由资源层统一判据挡掉（422），范围形状不对由路由挡掉（400），两类各有测试。

### 人员页多挂一种附属资料

原来一类基础资料只能挂一种关联资料（`relationOf: {operator: 'operator_machine'}`），现在人员页要同时有「导入/导出可操作设备」和「导入/导出个人日历」。改成 `attachedTo: {operator: [...]}`，适配器给 `attachedFiles(kind)` 返回家族和名字，工具栏按它渲染，打开哪一种由按钮自己带 `family` 说，主机不替它猜。`resource-api.js` 的 `importOnlyKinds` 也要加上新家族，否则适配器命名空间校验会直接把整个工作区渲染打挂——第一次跑真机探针就是这样红的。

### 改了什么

新增：`core/services/workbench/resource/calendar_files/operator_files.py`、`tests/workbench/{test_operator_calendar_files.py,test_operator_calendar_file_api.py,operator_calendar_files_live_probe.cjs}`。

改动：`core/models/workbench_calendar_file.py`（拆成两类日历各自的列目录与说明）、`core/services/workbench/resource/{operator_calendars.py,calendar_files/{file_writer.py,files.py}}`、`web/routes/workbench/calendar_files.py`、`frontend/workbench/app/{resource-api.js,ResourceLive.jsx,ResourceWorkspace.jsx,ResourceMaterialActions.jsx,CalendarFileContract.js,CalendarFileActions.jsx}`（含产物）、`tools/test_registry_groups_workbench.py`、`tests/workbench/{resource_live_probe.cjs,test_calendar_file_api.py}`。

### 验证

```
.venv/bin/python -m pytest -q tests/workbench/test_operator_calendar_files.py tests/workbench/test_operator_calendar_file_api.py \
  tests/workbench/test_calendar_files.py tests/workbench/test_calendar_file_api.py \
  tests/workbench/test_operator_calendars.py tests/workbench/test_operator_calendar_api.py
163 passed

.venv/bin/python -m pytest -q tests/gate_meta/
1260 passed

.venv/bin/python tools/scan_ui_copy.py
0 处

.venv/bin/python -m pytest -q tests/workbench/test_resource_live_browser.py
1 passed（真机 Chromium 109，304 个场景 0 失败，新增 5 个个人日历文件场景乘 4 种视口主题，数据库逐表隔离断言通过）
```

复杂度门禁拦下 `_classify`（22）和 `_value`（16），按职责拆成 `_fields_for` / `_after_row` / `_describe` 和 `_code` / `_efficiency` / `_choice`，没有登记治理台账。

未跑全量质量门禁。工作区有其他未提交改动，本条不构成干净工作区证明。

---

## 6. wbfile-template-unification（2026-09-21 完成）

### 表描述协议落在哪里

`core/models/workbench_table_descriptor.py` 只放两样东西：协议校验和「填写说明」表的内容生成，不碰 openpyxl。
怎么落进工作簿在 `core/services/common/excel_instruction_sheet.py`——它在 `core/services/common/` 而不是工作台簇里，
因为七个写入器分属 facts / material / process / batch / execution / resource 六个簇，放进任何一个簇都会违反簇分层合同。

12 张表全部补上 `table_descriptor(kind)`，形状用 roadmap 4.2 写的那一份（`table_id` / `file_stem` /
`value_hint` / `error_hint` / `enum` / `nullable` / `sample_rows`）。第 3、5 条时先写的日历家族键名和它不一样，
这一条里改齐了。协议有硬性一条：**列的 label 必须就是文件里真正的表头**，因为读取器按表头认列；
关联与日历家族原来用的是不带「（只读）」后缀的 `LABELS`，改成统一走各自的 `public_columns`。

### 说明表的样子

固定第二张表，名字固定「填写说明」。三段：逐列的「列名 / 必填 / 能填什么 / 会报错的情况」，
「通用规则」，以及按可填列逐列给值的 2 到 3 行完整示例。示例行宽度由协议校验锁住，用户能照着抄。

表头批注从"贴一整段规则"收敛成一句示例值加「规则见「填写说明」表」；示例值取自第一行示例，不再各家族各存一份
`_EXAMPLES` 字典。批次模板原来往数据表写一行示例（用户得先删掉才能填），这一行移进了说明表，数据表只留表头。

枚举列加了下拉。只写工作簿没有 `add_data_validation`，openpyxl 3.0.10 下只能直接挂 `ws.data_validations.dataValidation`，
这条在共用件里注明了。工艺家族的 `preserve_carriage_returns` 会关掉数据表并改写它的临时 XML，所以说明表必须在它之后再建。

### 读取器统一为"读第一张，其余忽略并提示"

原来三种行为并存：资源、物料、工艺要求恰好一张，多一张整份拒绝；批次读第一张并提示；报工直接读第一张不检查。
统一为最宽松的那一档——否则模板和导出文件自己就带一张说明表，用户回导时会整份被拒。

多表提示走整批级的 `notices`，不是行错误：读取器回 `(rows, notices)`，服务放进预检文档（这样确认时的逐字比对
也盖住它），路由再放进响应信封的 `warnings`，前端现有的 `Issues` 组件直接就能显示，不用改前端。
批次原来的那句「仅导入第一张工作表。」也换成了同一句话。

其余字节级规则一条没动：布尔拒绝仍然只有批次数量列、报工单元格、工艺路线三处，写出方式仍然分只写工作簿和
普通工作簿两派。

### 服务端提示与说明表同源

各家族原来的 `INSTRUCTIONS` 常量是另写的一段散文，和说明表的规则讲同一件事。现在它由
`instructions_text(table_descriptor(kind))` 接通用规则得到，backend 这边只剩一份来源。
工艺的 `INSTRUCTIONS` 顺带从一个字符串改成按 kind 分，原来两类工艺共用一段话，工序工时的用户会看到工艺路线的规则。

### 两处明确没做，不是漏掉

- **前端弹窗上传前的那段提示仍然是各家族自己的 `importHint` 常量**。它要在用户还没上传文件时就显示，
  那时拿不到服务端的预检结果，除非加一个"取表描述"的接口或者做构建期代码生成。这是第 7 条「一致性门禁」
  该收口的事，留到那里连同用户文档一起比对。
- **报工家族不发多表提示**。它的读取器本来就只读第一张、忽略其余（正是这一条要求的行为），
  但它的预检弹窗没有任何显示整批级告知的位置，发了也没人看得见；为它单独做一个提示区不在这一条范围内。

### 改了什么

新增：`core/models/workbench_table_descriptor.py`、`core/services/common/excel_instruction_sheet.py`、
`tests/workbench/{table_template_support.py,test_table_descriptors.py}`。

改动（表描述）：`core/models/workbench_{resource,material,process,batch,relation,calendar}_file.py`、
`core/services/workbench/execution/field_report_files_codec.py`。

改动（写入器）：`core/services/workbench/facts/file_writer.py`、`core/services/workbench/material/file_codec.py`、
`core/services/workbench/process/file_writer.py`、`core/services/workbench/batch/file_codec.py`、
`core/services/workbench/execution/field_report_files_codec.py`、
`core/services/workbench/resource/{relation_files,calendar_files}/file_writer.py`。

改动（读取器与整批告知）：`core/services/workbench/facts/file_codec.py`、`core/services/workbench/material/file_codec.py`、
`core/services/workbench/process/{file_reader.py,file_codec.py}`、`core/services/workbench/batch/file_codec.py`、
`core/services/workbench/resource/{relation_files,calendar_files}/file_codec.py`、
`core/models/workbench_{resource_action,material_file}.py`（`build(..., notices)`）、
`core/services/workbench/{resource/files.py,material/files.py,process/files.py,resource/relation_files/files.py,resource/calendar_files/{files,operator_files}.py}`。

改动（路由）：`web/api_responses.py`（`query_success(..., warnings)`）、
`web/routes/workbench/{resource_actions,material_actions,process_files,process_action_context,relation_files,calendar_files,batch_files,process_file_exports}.py`。

改动（测试）：`tests/workbench/{resource,relation,calendar}_file_support.py`、
`tests/workbench/process_file_codec_support.py`（新增只取行的 `decode_rows`，避免 54 处调用点逐个改）、
`tests/workbench/{test_resource_file_codec,test_material_files,test_process_file_codec,test_file_reference_roundtrip,final_execution_artifacts}.py`、
`tests/workbench/resource_files_live_probe.cjs`、`tools/test_registry_groups_workbench.py`。

顺带补上第 2 到 5 条漏掉的两处：`tests/workbench/fe03_route_manifest.json` 少了 15 条新路由，
`tests/workbench/test_fe03_request_package_contract.py` 的注册器清单少了三个。

### 验证

```
.venv/bin/python -m pytest -q tests/workbench/test_table_descriptors.py
58 passed

.venv/bin/python -m pytest -q <资源/物料/关联/日历 17 个文件测试>
604 passed

.venv/bin/python -m pytest -q -k "process_file or batch_file or field_files or field_piece or execution_files or batch_transport"
591 passed

.venv/bin/python -m pytest -q -k "resource or material or calendar or relation"（排除真机浏览器组）
2345 passed, 3 skipped

.venv/bin/python -m pytest -q tests/gate_meta/
1260 passed

.venv/bin/python tools/scan_ui_copy.py
0 处

.venv/bin/python -m ruff check core/ web/ tests/workbench/
All checks passed

.venv/bin/python -m pytest -q tests/workbench/test_resource_live_browser.py
1 passed（真机 Chromium 109，304 个场景 0 失败，数据库逐表隔离断言通过）
```

`test_final_execution_{analytics,chain}.py` 两条真机用例失败，已在 HEAD 干净工作树上复跑同样失败，
与本轮改动无关，属既有问题。

复杂度门禁拦下 `check_table_descriptor`（18）和 `_check_column`（16），按职责拆成
`_check_columns` / `_check_rules` / `_check_column_enum` / `_nonempty_text`，没有登记治理台账。

未跑全量质量门禁。工作区有其他未提交改动，本条不构成干净工作区证明。

---

## 7. wbfile-manual-and-legacy-retirement（2026-09-21 完成）

### 列说明由工具生成，不人手写

`tools/generate_table_docs.py` 从 `core/models/workbench_table_catalog.py` 取 13 份表描述，
渲染成说明书第 1 章的 14 个标记区间（1 个总表 + 13 张表），`--check` 比对、`--write` 回写。
门禁是 `tests/gate_meta/test_table_doc_generation.py`：内容一致、区间成对、13 张表一个不少。

为什么不是"人写文档 + 测试解析表格比对"：格式微调就会误报，而且列说明和文件里第二张
「填写说明」表本来就该是同一份东西。散文段落（进入方式、这张表在流程里的位置）仍人工撰写，
不进这个门禁。

报工的两个格式版本同名同表，总表在同名时自动标出列数，不改 `display_name`（它同时是文件名）。

### 生成文档暴露出的四处描述错误（都在本轮前六条自己写的代码里）

写文档的过程本身是一次对账，改的是源头不是文档：

1. **只读列在用可填列的口吻说话。** `备注`/`设备类别` 在工种表可填、在别的表只读，
   却共用一句"随便写；要清除请填 \N"。文件里的说明表会教用户去填一列根本不会被导入的格子。
   拆出 `_READONLY_HINTS`。
2. **四类资源共用一份通用规则。** 工种表没有状态列也没有多值列，却带着"状态填英文代号"
   "多值列必须是 JSON 数组""设备授权要到人员详情里改"。改成 `_general_rules(kind)` 按类生成，
   `INSTRUCTIONS` 跟着从单值改成按类的字典。
3. **路线表和工时表共用图号提示。** 路线表能新增零件（`file_route.py` 有 create 分支），
   工时表不能（`file_hours_preview.py:59` 明确拒绝）。共用提示把"能新增"说成了"找不到就报错"。
   拆出 `_KIND_HINTS`。
4. **供应商默认周期说成纯选填。** 实测新增供应商缺这一列会被拒：
   `RESULT: rejected / 新增供应商必须明确填写有效默认周期`（域层 `value_policies.py` 是
   WRITE_REQUIRED）。列本身对已有供应商留空表示保持原样，所以不是必填列，但提示必须写明新增要填。

### 退役了什么

**启动期旧模板生成（7C）**：`_init_excel_templates` 从 `create_app` 摘掉，
`ensure_excel_templates` 连同 15 个旧模板修复助手（表头重写、布局修复、枚举下拉刷新）一起删，
`EXCEL_TEMPLATE_INIT_STATUS` 全仓无读取方，一并删。11 份 git 跟踪的旧模板 xlsx 删除。
`excel_templates.py` 496 行 → 156 行，只剩转换输出用的 `build_xlsx_bytes` +
`get_template_definition`，和各家族导出共用的 `sanitize_export_cell`。

保留的边界要说清楚：`EXCEL_TEMPLATE_DIR` 仍是运行时路径（`templates_excel/` 还放着
回转壳体单元产品数据和转换输出），`get_template_definition` + `excel_template_defaults.py`
仍被 `unit_excel` 转换输出和批次 codec 的启动期断言用着，都不能删。

**旧 Excel 页说明视图模型（7D）**：四份文件（1124 行）删除，`page_manuals_scheduler.py`
里的 `excel_batches`/`excel_calendar` 两个主题删除，共 13 个主题；端点映射删 13 条，
`related_manual_ids` 里的引用清干净，11 个只服务这些主题的共享片段删除。
主题数 33，无悬空引用。触发点是它们的 `full_manual_anchor` 全部指向第 1 章，重写后 11 个锚点失效。

### 测试侧的连带

`tests/_support/excel_templates.py` 原本存在的理由是 WARM 预建 11 个模板省掉每用例
COLD 重建（~174ms × 数百次）。启动期不再写模板，预建没有意义，只留共享目录登记。

`tests/excel_data_io/test_excel_template_contract.py`（914 行）里 16 个断言，退役后只剩
转换输出那一条还有对象，改写成 `test_conversion_output_templates.py`（80 行），原文件删除。

`_remove_enum_validations` 是删除范围里的助手，但 `_apply_sheet_layout` 无条件调它。
`build_xlsx_bytes` 的工作表一定来自新建工作簿，不可能带旧下拉，所以删调用而不是恢复助手。
这个 NameError 是跑 `tests/excel_data_io/` 才抓到的，说明删代码后必须按调用方向再跑一遍。

### 词表：真实列名照抄，散文按词表改

`tools/scan_ui_copy.py` 在 HEAD 是 0 处，重写后 17 处。分两类处理：
散文里的"新建/清空/回执"改成"新增/清除/回到"（4 处，真问题）；
`外协周期策略`、`显式工种编号数组`、`有效加工工时(h)` 是文件里的真实表头，用户必须照抄，
按词表里已有的同类裁决补说明书的豁免（`core/models/workbench_resource_file.py` 早就这么豁免过）。
报工列目录搬到 models 后，豁免路径跟着列定义走。

### 改了什么

改动（生成与门禁）：`tools/generate_table_docs.py`（总表同名消歧）、
`tests/gate_meta/test_table_doc_generation.py`（新增）、`tools/ui_copy_glossary.json`。

改动（描述修正）：`core/models/workbench_resource_file.py`、`core/models/workbench_process_file.py`、
`core/models/workbench_field_report_file.py`、`web/routes/workbench/resource_action_context.py`。

改动（文档）：`static/docs/scheduler_manual.md` 第 1 章整章 + 14.1/14.2/14.3、`README.md`、`DELIVERY_WIN7.md`。

改动（退役）：`web/bootstrap/factory.py`、`core/services/common/excel_templates.py`、
`web/viewmodels/page_manuals{,_common,_registry,_scheduler,_scheduler_admin,_system,_equipment,_personnel,_process}.py`，
删除 `web/viewmodels/page_manuals_{equipment,personnel,process}_excel.py`、`page_manuals_excel_demo.py`、
11 份 `templates_excel/*.xlsx`。

改动（测试）：`tests/_support/excel_templates.py`、`tests/conftest.py`、
`tests/excel_data_io/test_conversion_output_templates.py`（新增）、
删除 `tests/excel_data_io/test_excel_template_contract.py`、
`tests/config/test_config_manual_markdown.py`、`tests/web_pages/test_page_manual_registry.py`、
`tests/web_pages/test_frontend_ui_language_polish.py`、`tests/gate_meta/generate_conformance_report.py`。

### 明确没做的两件事

**第 6 条留下的前端 `importHint` 仍是各家族常量。** 它要在拿到预检结果前显示，没法从响应里取；
本条加的一致性门禁只覆盖说明书与表描述，没覆盖前端常量。要真正收口需要把表描述投影到前端资产，
是独立改动。

**`tests/web_pages/test_frontend_ui_language_polish.py` 还有 8 条失败。** 在 HEAD 干净工作树上
复跑是 9 失败 14 通过，本轮删掉其中 1 条（旧模板下载），其余 8 条一条不多一条不少，全是早前
退役留下的陈旧引用（`scheduler_run_options.py`、`scheduler_config_panel.py`、`legacy_result.html`、
`legacy_presentation.preview_fields`、`web/routes/material.py` 都已不存在）。这个文件不在日常门禁的
执行范围里（只被 py38 语法扫描扫到），所以烂了很久没人发现。不属本条范围，需要单独一条来裁决
每个契约现在该说什么。

`web/viewmodels/page_manuals_common.py` 里 `reports_filter_basics` 在 HEAD 就已经没有引用方，
不是本轮造成的，未动。

### 验证

```
.venv/bin/python -m tools.generate_table_docs --check
列说明与表描述一致。

.venv/bin/python -m pytest -q tests/gate_meta/test_table_doc_generation.py
4 passed

.venv/bin/python -m pytest -q tests/workbench/test_table_descriptors.py
71 passed

.venv/bin/python -m pytest -q <12 张表的文件家族测试 12 个文件>
664 passed

.venv/bin/python -m pytest -q tests/excel_data_io/
86 passed

.venv/bin/python -m pytest -q tests/web_pages tests/config tests/app_runtime
569 passed, 1 skipped

.venv/bin/python -m pytest -q tests/gate_meta
1264 passed（先红 3 条：两条边界棘轮基线引用已删文件，一条静默回退台账陈旧登记；
按各自的刷新入口处理后复跑全绿，见下）

.venv/bin/python -m pytest -q tests/workbench（排除 perf 与真机浏览器）
8368 passed, 518 deselected，41 分钟

.venv/bin/python tools/scan_ui_copy.py
0 处

.venv/bin/python -m ruff check core/ web/ tools/ tests/
All checks passed

.venv/bin/python .codestable/tools/validate-yaml.py --dir .codestable/roadmap/workbench-file-imports-and-templates/
3 passed（顺手给 implementation-notes.md 补上前置，它从建起来就缺）
```

三条门禁基线要跟着退役刷新，不刷新会红：
`python -m tools.scan_private_imports --refresh`（只少了 4 个已删视图模型的登记，没有新增债务）、
`python -m tools.scan_sql_boundary --refresh`（0 变化）、
手工从 `开发文档/技术债务治理台账.md` 删掉 `_init_excel_templates` 的静默回退登记
（它的 exit_condition 就是"去除静默吞异常或从本分类移出"，函数删了即达成）。

未跑全量质量门禁。工作区有其他未提交改动，本条不构成干净工作区证明。

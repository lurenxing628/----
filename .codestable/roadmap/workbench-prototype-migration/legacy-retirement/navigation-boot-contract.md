# 严格规范 nav：Main 对接合同

- 最新授权：G 已实际新增 `web/routes/workbench/navigation_boot.py`，只验证输入；Main 负责 pages/JS 读取与 400 呈现。本文件不是退役挂载许可；17 未通过，不删旧资源。
- 唯一入口：`read_navigation(view, args)`；args 原样传 `request.args`，不要先变成 dict 丢掉重复 query。外层参数合法且无 nav 才返回 None；有 nav 返回 JSON 可序列化 `{version: 1, view: str, context: dict}`；非法抛 `WorkbenchNavigationInvalid(ValueError)`。
- 此 helper 不连接数据库、不注册路由、不改状态、不给不存在或失效 ref 补映射。**格式合法不等于对象存在**；目标真实读接口继续核验永久绑定、当前正式/历史限制，失败不能 fallback。

## 1. 根与 URL

```json
{"version":1,"view":"gantt","context":{"plan_ref":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","range_start":"2026-09-10T08:00:00","range_end":"2026-09-11T08:00:00"}}
```

- nav 根必须恰好三键；version 必须 type=int 且等于 1，不接受 true、1.0、"1"。nav.view 必须等于调用传入的当前 view。
- 不论有无 nav，外层 query 只允许 view/nav，每键恰好一个字符串值；view 若存在也必须与当前 view 一致。`/workbench/trial` 可不带外层 view；若带别的 view 拒绝。无 nav 的旧 version/plan_role、未知 scope 和重复 view 也明确拒绝，不因 nav 缺失而跳过验证。
- 任意深度 JSON 重复键（包括转义后同名）、NaN/Infinity、不可 UTF-8 序列化的字符串、空 nav、非对象 root/context、未知字段都拒绝。
- 15 个已授权 view（含 delay）都接受 `context:{}`，含义仅为明确打开该工作区落地页，没有指定对象。不能把非法 ref 或有内容的无效 context 清成 `{}` 重试。
- 公开 ref 一律复用现有 48 位小写 hex 校验。旧 `version/plan_role/scenario_id` 不能直接塞入规范 nav；旧 GET 转换器须先得到既有永久 ref。

## 2. 首版字段白名单

这是旧 URL 等价承接的有界协议，不是任意新 UI state 的序列化格式。表中除说明的必填项外为可选；未知键拒绝，不删键后继续。

| view | 非空 context 支持内容 | 验证及目标消费 |
| --- | --- | --- |
| gantt / analysis / delay | 必填 plan_ref；可选 range_start、range_end | `PlanReadScope` + `PlanContract.workspaceScope`；时间字段出现就必须成对、真实本地完整秒、起点小于终点。完整计划要**省略两个时间键**，不传 null。只承接 plan workspace，不接 candidate/run-history 状态 |
| process | `{source:"production"}`，或下述按 kind 的精确结构 | `ResourceWorkspace.navigation`；公共 ref 复用现有 reference，日期复用 calendar_date |
| batches | entity_ref、focus、batchIds | entity_ref 出现必须合法；focus/batchIds 复用 batch_scope 验证，并原样供 BatchWorkspace 的 focus/batch_ids/entity_ref。batchIds 是实际页面消费的批次业务编号数组，不猜成永久 ref、不按名称找对象 |
| reports | 必填 scope；可选 topic、catalogOpen | scope 见下；topic 仅 delivery/records/machines/people/quality；catalogOpen 必须 bool。它只展开目录，不选择 overdue/utilization 等目录项 |
| review | 必填 scope | 不接受 topic：Review 的专题由当前组件固定，不能收下后忽略 |
| run | 仅 `{run_ref: <48hex>}` | validate_run_ref；RunWorkspace 的既有运行读取。预检输入/临时预算不属于这版规范 URL |
| trial | `{draft_ref}`、`{scenario_ref}` 或 `{base:{plan_ref 或 candidate_ref}, scope?}` | create_input / reference 与 TrialContract.target 的交集；base 必须二选一。scope 的显式时间不能 null |
| dashboard / field / fieldgantt / calib / basedata / system | 仅空 `{}` | 非空定位字段尚未纳入本版协议，明确 400，不扩大默认查询。不代表这些工作区的 history 内部导航不可用 |

process 按 kind：

- material/machine/operator/supplier：source、kind、entity_ref 必填，不接受 category、业务 ID 或其他字段。
- op_type：source、kind、entity_ref、category 必填；category 只 internal/external。
- part：source、kind、entity_ref 必填；stage 可为 route/source/hours；template_operation_ref、template_external_group_ref 若存在也必须是有效永久 ref。
- calendar：source、kind、month 必填；month=`YYYY-MM` 且真实年月；date 可选，须真实 ISO 日且属于 month。不接受 entity_ref。

reports/review 的 scope：

- plan_ref 必填且不可 null；可选 source、plan_finish_date_from、plan_finish_date_to、batch_ref、resource_type、resource_ref、query、focus。
- 复用 `ReportScope`：source 只 production，日期成对且不倒置，query 上限 200，resource_ref 需要 resource_type；已存在的 unassigned 语义保留。
- 可带 `kind:"execution_analysis"`，其他 kind 拒绝。旧 date_from/to 事件日期或 window_date_from/to 目录窗口不能混进此 scope。
- 目录指定项/目录窗口不在此版 nav，不能把它们塞进 topic 或 plan_finish_date。它们若成为旧 URL 的必需上下文，先返回不等价说明，不偷偷改报表范围。

trial scope 复用现有 create_input：range_start/end、batch_refs、resource_type/ref、query；已有 draft/scenario 不可重给 scope。导航不执行 create/change/save/adopt。

## 3. Main 接入点

1. `_host` 确认 view 后原样调用 `read_navigation(view, request.args)`；捕获且只捕获 WorkbenchNavigationInvalid，返回 `workbench/unavailable.html` 的 400。不要改成 `{}` 后启动默认页。
2. 推荐 boot 放 `navigation`，值为 None 或返回的根对象；它是服务器已验的身份输入，不是浏览器历史快照。Main 已约定 JS 在 read 时直接严格解析显式 nav，优先于 history。
3. history 中 entry_nav 与当前 URL 的规范 nav 不匹配时，不恢复旧对象。各域完整 filter/selection/scroll 仍走 WorkbenchPageContext/useSnapshot 和 history，不自动追加到 nav。
4. 主动切换导航时移除旧 nav，或只生成本表支持的下一精确 context。不能保留旧 nav 的 plan_ref 却显示另一对象；也不能在生成后删除未知字段冒充原查询仍完整。
5. 旧 POST 的成功/失败 flash 若跳进新 root，Main 还需在 boot 放经过现有公开投影的消息，并由新 root 可见呈现。不能只有 redirect 而交易结果丢失；此项不在 read_navigation 的输入职责内。

## 4. 验证和边界

- 源码定位使用私有 `CHECKUP_CALLGRAPH=/tmp/aps-g-navigation-callgraph`：whereis/callers canonical_json，whereis plan_reference；未改共享图。
- 已有 `tests/workbench/test_final_navigation_boot.py` 及 `final_navigation_support.py`，运行 `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-g-navigation-pycache .venv/bin/python -m unittest tests.workbench.test_final_navigation_boot -v`。第一次 11 测试通过；后续补了目标 JS 不接受显式 null 时间的拒绝用例，最终结果另记 handoff。
- 3 文件 Pyright 曾报告测试里 3 处 Optional 下标，已加真实非 None 断言，复跑 0 errors/0 warnings。这不是忽略错误；不更新 pyright 依赖。
- 最新 parser 专项 12 passed；包含 delay 和无 nav 时先验外层参数。旧 GET 另有 18 个真实私有 SQLite 测试，入口为 `resolve_legacy_get(conn, LegacyGetRequest)`，不经过新 host 猜测旧参数。
- Main 已通报正在接入 pages/boot/JS；G 未修改这些文件，也未替代 Main 的真实 factory HTML/浏览器验收。全站 17 和退役 18 均未以本 helper 标 passed。

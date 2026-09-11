# 旧 GET 转换接线合同

- 实际未挂载源码：`web/routes/workbench/legacy_navigation.py`、`legacy_navigation_plan.py`、`legacy_page_contract.py`。没有连接数据库、注册路由或补建身份；调用方提供既有connection。
- `resolve_legacy_get(conn, LegacyGetRequest(endpoint, tuple(request.args.items(multi=True)), path_values))`返回具名decision；非51页面endpoint返回None，不碰下载/JSON/health。重复query400，不先转dict。
- `LegacyGetDecision.kind`仅redirect/retired/restyle。`build_legacy_destination(decision)`仅接受redirect，再次调用read_navigation验证，生成/workbench或/workbench/trial的规范nav。无scope删除、非法ref替代或猜测UI状态。

## 等价边界

| 旧入口 | 当前转换规则 |
| --- | --- |
| 根dashboard，无query | 明确打开dashboard；有版本/日期/资源条件不能丢，改为说明 |
| gantt | 既有version/latest解析、role/scenario解析后，永久plan_ref SELECT并反解核对相同locator；复用旧日期/周偏移及62天显式范围上限，date-inclusive转原半开datetime范围；完整计划省略两个range键 |
| analysis | 只有原身份字段时进入同计划analysis；旧日期/资源只用于关联入口，不误当成新分析范围。非身份字段给说明，包括原来允许的单边关联日期 |
| 设备/人员/工种/供应商/零件/批次详情 | 精确路径字段查原记录，再SELECT既有entity_ref；工种类别来自原记录。任何附加query不丢弃后跳转 |
| material列表，无query | 明确进入production资料初始页 |
| reports | 旧统计/overlap日期/目录选择与当前导航的finish-date或目录默认值并不等价，明确说明；已支持原字段的链接保留原export口径，冻结实际版本，模拟方案用既有token脱敏 |
| 批次列表、资料分类列表、配置/日志/日历与导入编辑器 | 旧隐含status/tab、日历全量/月份、旧控件等未被当前nav消费，不跳到看似相同的默认页；明确退役说明，业务接口保留 |
| print/manual | dispatcher显式调用保留原parser的新模板handler，不经过通用retired |

- 合法缺省/latest可解析为当下真实版本；明确不存在版本404，非法参数400；缺少合法对比角色时不沿用旧页adopted回退，而是requested_role_unavailable说明。
- 永久身份缺失/绑定无效不修复、不改选；原SQLite/架构错误继续抛出，不能吞成空页面。读snapshot尊重外层事务。
- raw scenario与token同时存在必须指向同一方案。过期/重启丢失的旧token仍显式拒绝；成功转换后的永久ref不依赖旧token。
- 公开说明只包含受控版本、方案标签、规范日期、资源维度；不输出raw query/path/context或内部ID字典。原下载仍保留既有业务字段，raw scenario不会进入生成的HTML链接。
- `navigation_boot.read_navigation`支持delay与gantt/analysis相同三字段；无nav也先验证唯一view/nav，其余旧参数只在本转换器解析。

## Main 接线

1. G不改Main的pages/boot/JS。Main直接使用现有read_navigation返回对象，并验证前端消费；任意UI状态仍走history。
2. 收到17通过授权后，复核`candidate-review-index.json`全部preimage，应用`candidate-review.patch`。新结果、打印、手册、错误模板和presentation须一起应用。
3. 在所有既有blueprint完成注册、开始服务前，显式调用`web.routes.workbench.legacy_dispatch.install_legacy_retirement(app)`一次。函数已具体连接g.db、resolve_legacy_get、canonical URL和新retired模板，不需要另写converter。
4. 注册`test_final_navigation_boot.py`、`test_final_legacy_navigation.py`及两份support到门禁。私有候选HTTP测试提供精确调用范例，但不进入生产交付。
5. 原成功POST若最终进入新root，确认flash/message确实可见；当前候选新legacy_base已显示原flash。随后按资源矩阵实施候选资产排除、全站负向检查和回退演练。

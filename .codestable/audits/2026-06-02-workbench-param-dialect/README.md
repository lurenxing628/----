# 2026-06-02 工作台参数方言测绘 · 总索引

**起因**:推进 `reports-workbench-backlink`(前端工作台 roadmap 第7项)收口时,发现 11 个页面"说话方言不一样"——日期、资源、方案身份三族参数各拼各的。用户判断"LLM 当执行者自己定的细节是项目最大隐患",本次用 8-Agent workflow(`aps-param-dialect-survey`)做证据级测绘 + 对抗验证,核实该判断。

**方法**:6 路 OPUS survey(日期方言/资源方言/方案身份5层/现有脊梁/对抗复审根因) + 3 个怀疑者对抗验证"方案身份能否安全收敛"。全部结论带 `file:line` 证据。只读,未改任何代码。

> ⚠️ 数据可信度:日期/资源/方案身份/脊梁 5 路有完整结构化产物;**对抗复审根因那一路 Agent 未产出结构化结果(failed),该方向的结论是从其余证据推断,可信度中等、未实测**。

---

## 一句话结论

用户判断对七分。债分两种、藏身方式相反:

- **方言型债(吵闹)**:命名不统一——日期 13 种叫法、资源 9 种。全暴露在跨页接缝上,可机械枚举,**好治,今天能收**。
- **沉默型债(安静)**:语义被悄悄碾平——方案身份 5 层被某页用写死常量碾成 1 层。不报错、测试全绿,**只在"本不该相同的东西被当成相同"时出血。难发现,但全项目只 1 处真出血**。

用户"统一参数"的直觉:**对吵闹那批是解药,对安静那批是毒药**。同一动作在两类债上效果相反。

---

## 三类概念 × 处置

| 概念 | 规范名 | 现状 | 性质 | 处置 |
|---|---|---|---|---|
| 日期窗口 | `date_from/date_to` | 脊梁内部已统一,出站按目标页方言表重命名(甘特/资源负荷/停机发 `start_date/end_date`) | 翻译层,基本收口,3处窄缺口 | 补兜底,不推翻 |
| 资源/视角 | `resource_type/resource_id` | `normalize_report_resource_filter` 守门,7/11 表面在脊梁上 | 别名层,八成收口 | 收尾+拔第三套私有实现 |
| 方案身份 | `version+plan_role+scenario_id+source_table+status` 复合键 | 5 层语义,`collapse_safe=false` | 语义层 | **绝不能压成单 id**,补1处出血 |

**对抗验证铁证**:3/3 怀疑者判定"强收敛会焊死 bug"(预览被当正式复盘 / 旧正式冒充现行 / 页面与导出口径分叉 / version=latest 漂移)。

---

## 方案身份 5 层(逐层已核实代码)

1. **请求的** — URL 里要的(`plan_role`/`?version=`/`scenario_id`),未经存在性校验。`plan_id` 是死面包屑(从不进任何 resolver,grep 零命中)。
2. **实际选中的** — 版本解析+角色回退后真正读哪份数据(`version_resolution.selected_version` + `selected_role` + `source_table` + `candidate_id` + `status`)。
3. **模拟预览** — `scenario_id` 指向 `ScheduleAdjustmentScenario`(v13,物理隔离表),`is_simulation=True`,`status=scenario_preview`。
4. **历史正式(现行)** — `is_current_executable_official_version=True`,`can_write_feedback=True`。
5. **被替代旧正式** — `is_superseded_by_newer_version=True`(=`version < latest_executable_official_version`,**读时实时算**),`can_write_feedback=False`。

第 4↔5 层唯一分水岭是那个读时布尔。**一旦冻进 id/缓存键,新版本发布后旧正式永远冒充现行** → 这就是不能压成单 id 的命门。

---

## 🩸 那处真出血(已亲自核实,正中"不自欺"暗线反面)

`计划和现场实际`(execution_review)用写死常量假冒方案身份:

```python
# web/routes/reports_page_support.py:36
ADOPTED_PLAN_RESOLUTION = {"requested_role": "adopted", "selected_role": "adopted", "selected_label": "正式采用方案"}
# :368 _version_or_none 照收用户 ?version=(可能是旧版本 v5)
# :376 却把上面写死常量当 plan_resolution 发布 → 丢掉真实 is_superseded
```

- `core/services/report/execution_review.py:153` 引擎层硬钉 `host._resolve_plan(v, ROLE_ADOPTED, None)`;`:166-167` `plan_label`/`plan_role` 写死 adopted。
- `templates/reports/execution_review.html:56` 写死"正式采用方案";`grep is_superseded templates/` = 零命中。

**后果**:用户带【已被 v12 替代的旧正式 v5】回到该页,系统逐字节显示成"正式采用方案",看不出"历史版本"痕迹。这不是坏数据,是**陈旧数据被贴现行标签**——比静默兜底更隐蔽的自欺。

**今天没酿祸的唯一原因**:写现场记录另有独立闸会重解析挡住旧版本(`operation_execution_feedback_service.py:355-362`)。**显示层已在撒谎,写入层兜住了。** 这正是怀疑者反复强调"写侧那道独立重算闸不能以'和显示层重复'为由删掉"的原因——它是显示层撒谎时的最后防线。

### execution_review 的"刻意不对称"必须保留

怀疑者一致警告:用户"把复合键推广到所有页/消除跨页不一致"的方向,**一旦套到 execution_review 会拆掉拦截"预览被当正式复盘"的墙**。该页对 layer1/2/3 的命令式坍缩(硬钉 adopted + `_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS` 禁带 `plan_role/scenario_id`)是**故意的、救命的**,不是待消除的不一致。"对抗复审一直有问题"极可能根因在此(此条推断,未实测)。

---

## 吵闹的债:命名缺口(低风险,加兜底即可)

1. `utilization` 读侧只认 `start_date`,无 `date_from` 兜底(`reports_page_support.py:265`);`downtime` 同病(`:418`)。带 `date_from` 的旧 URL 打来 → 静默丢日期退默认7天。
2. 3 个导出口各认各拼写互为镜像:`utilization/downtime_export` 只认 `start_date`,`execution_review_export` 只认 `date_from`。
3. 甘特"设备/人员视图"切换按钮丢 `gantt_resource`(`gantt.html:88-93`) → 切视图丢已选资源筛选。

修法:让窄读侧向已有的宽看齐(抄 `navigation_context.py:89` / `execution_review` 已有的双拼写兜底),不发明新东西,不改语义,不会让任何页面变红。

---

## 收口标准(收口到已存在的三件套,不新发明)

1. **context 构造** → `build_workbench_plan_context`(`scheduler_workbench_links.py:183`,已是事实枢纽)。
2. **URL/参数族出口** → `query_for_target + _TARGET_QUERY_SPECS`(`scheduler_workbench_link_query.py`)。把现在平行手拼的两类导出 URL(`current_report_export_url`、resource_dispatch 的 `_export_url`)登记成 target 由它产出。
3. **资源归一** → `normalize_report_resource_filter → normalize_schedule_resource_filter`(model 底座)。并入 `resource_dispatch_service._normalize_scope_type` 这第三套私有实现;team 维度在 model 层单点裁决。

## 待清的重复/死代码

- plan-guard 字段拷贝 3 份各自维护(`scheduler_navigation_publish._plan_guard_fields:72` / `scheduler_reports_workbench._copy_plan_guard_fields:40` / `scheduler_resource_dispatch._copy_plan_guard_fields:62`)→ 合并到最完整的第一份。
- `scheduler_reports_workbench.py:141` 的 `_context_summary` 死代码(0 caller,grep 确认),活的是 `scheduler_workbench_links.py:254`。
- `ROLE_ADOPTED='adopted'` 在 5 文件各自重定义 → 收一处。

---

## 产物

- 完整 workflow 结构化结果(含全部 file:line):session task `we5m32r2f` 输出。
- 本 README 是提炼;原始证据在 workflow 产物。
- workflow 脚本:`.../workflows/scripts/aps-param-dialect-survey-wf_fc9c98da-068.js`(可 resume 复跑)。

## 教训(已记忆)

workflow 里 `agentType:'Explore'` 写死 haiku,本环境只放 OPUS → 404 全失败。修法:去掉 agentType 用默认 workflow-subagent,resume 只重跑失败路。见记忆 `workflow-explore-agent-haiku-trap`。

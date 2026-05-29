---
doc_type: verification
slug: resource-dispatch-site-records-review-repair
status: completed
created_at: 2026-05-29
updated_at: 2026-05-29
confidence: high
scope: 对资源派工现场记录 feature 与内部值外露 issue 未提交改动的深度 review，及四个根因修复加五项低优先清理
related_feature: 2026-05-28-resource-dispatch-site-records
related_issue: 2026-05-28-resource-dispatch-internal-execution-token-leak
tags:
  - scheduler
  - resource-dispatch
  - site-records
  - execution-feedback
  - review
  - repair
---

# 资源派工现场记录 review 核实与修复留档

## 0. 说明

本文件汇总对资源派工现场记录 feature（`2026-05-28-resource-dispatch-site-records`）与内部值外露 issue（`2026-05-28-resource-dispatch-internal-execution-token-leak`）一批未提交改动的深度 review 结果，以及随后的修复与验证。

- review 阶段未修改业务代码：主代理读取 feature 设计 / 验收 / issue fix-note 后，并行调用 5 个 Sub Agent 分方面（issue 清洗链路、Excel 导入核心服务、路由与装配、前端、测试）下钻引用链核查，主代理做结论合并与交叉验证。
- 修复阶段按根因逐个改，每处补能区分新旧行为的回归测试，并对其中两处做了“还原即失败”的反向验证。
- 全量测试 3772 passed。修复随后随 feature/issue 一并提交（commit `e6aef139`、`33efad94`）。

## 1. review 关键结论

### 1.1 交叉验证纠正的一处误判

一名 Sub Agent 把“删除完工数量上限校验（`_validate_finish_payload_against_plan`）”定为高危静默移除护栏。测试方向的 Sub Agent 通过 roadmap 字段表、items.yaml、本目录 `2026-05-28-explore-shop-floor-feedback-usage.md` 的 2026-05-29 订正块证明：这是**有决策背书的故意行为反转**——报废后为凑够良品会补投零件，产出总量超计划属正常生产，不再拦截。主代理核实 roadmap diff 后确认背书属实，非搭便车删护栏。

> 方法论提示：这些决策文档本身也在同一批未提交改动里，从 git 历史无法证明“决策先于代码”。提交说明里已点明该护栏移除是 roadmap 既定决策的落地。

### 1.2 确认健康的方面

- 事务“全或无”严格成立：单 conn + savepoint 嵌套，真正 commit 只在最外层一次，任一失败回滚整批。
- 无危险吞错：所有 except 要么转抛 AppError（保留异常链）、要么 `logger.exception` 落日志，无 `except: pass`、无静默 200。
- 正式方案写入护栏双重生效：候选 / 预览 / 历史正式 / 非最新正式四类均被 `can_write_feedback` 拦截。
- 模板 / 接口不泄漏 `op_id`、`schedule_id`、`state_revision`、`execution_snapshot_revision`。
- 测试是健康重构：旧实时按钮契约被新现场记录契约替代，setup 搬到 support 模块，无“因校验删除连带删测试”。

## 2. 四个根因修复

### P1 — 前端预填导致补完工被整单拒绝（中）

- 根因：`renderActualInlineForm` 把任务卡上已记录的实际开工 / 完工时间预填进可编辑且会进 payload 的 datetime-local 输入框。`fill_actual` 在 `status != completed` 时即启用，于是“补完工”提交会带上已记录的开工时间，被后端 `_validate_existing_actual_times`（“已记录实际开工，如需改错请走后续纠错流程”）整单拒绝。
- 修复：已记录的实际开工 / 完工改为只读展示块（看得见、不可编辑、不进 payload），仅未记录时给可编辑输入；完工已记录时连带隐藏完成 / 报废数量输入。删除因此变成死代码的 `dateTimeInputValue`。
- 验证：前端契约测试新增断言，锁住“只读展示、不预填可编辑值”，`node --check` 通过。

### P2 — remark 清洗黑名单过宽 / 大小写绕过 / 静默吞数据（中）

- 根因：`public_execution_remark` 用 5 张 label 字典全部键（26 个英文词）做全局黑名单，会误杀跨记录的合法说明（如在设备异常里写 `person`）；只 `strip` 不归一大小写，`Exception` 能绕过；命中清洗无任何日志。
- 修复：改为基于“本条记录自己的结构化码”（event_type / reported_status / reason_code / severity / handling_status）精准判定，新增 `internal_remark_tokens_from_event`，写入 / 汇总 / 展示三段链路统一传入本行码集合；判定用 `casefold` 归一大小写。
- 验证：新增“大写内部码也清洗”“跨记录无关英文码保留”两个回归，原 issue 清洗用例全部保留通过。

### P3 — 预览→确认幂等 token 因 datetime 往返不稳定（中，失败安全）

- 根因：`openpyxl(data_only=True)` 把日期单元格读成 datetime 对象，preview 用 `json.dumps(default=str)` 算 token（ISO），但经 Flask jsonify 下发再回传后 datetime 变成 RFC822 字符串，confirm 重算 token 不一致，误报“导入内容已经变化”。
- 修复：在读 Excel 源头 `read_actual_workbook_rows` 就把 datetime / date 归一成 `%Y-%m-%d %H:%M:%S` / `%Y-%m-%d` 字符串，全链路类型一致；只归一日期、不动数字，避免影响“完成数量必须是整数”的校验语义。
- 验证：新增用真实 datetime 单元格走 preview→confirm HTTP 往返的回归；用 sed 还原归一化确认测试会失败（能咬住该行为）。

### P4 — manual 入口复用 idempotency_key 时整体跳过校验（中，已被逐事件校验兜底）

- 根因：`record_actual_situation` 用 `_has_existing_plan_idempotency`（任一派生 key 命中即整体跳过 `validate_task_plan`），客户端复用同一 key 追加新内容时，新增部分逃过完工早于开工、暂停冲突等跨字段校验。
- 修复：改名为 `_plan_is_full_replay`，仅当该 plan 要写的全部事件都已存在（真正的纯重放）才跳过校验；任何新事件都跑完整校验。record_event 层的 fingerprint 幂等检测仍作兜底。
- 验证：新增“复用 key 追加非法完工仍被前置中文校验拦下”的回归；用 sed 把 all 改回 any 确认测试会失败。

## 3. 五项低优先清理

- 删除前端 `payload.event_time` 死字段（后端不读）及连带死代码 `localDateTimeText`。
- 删除未接线的 `_actual_import_preview_url` / `_actual_import_confirm_url`（路由本身保留）。
- 去掉 `_build_preview` 里 `status==ok` 分支内恒为真的 `if plan is not None`。
- 上传改走抽出的公共 `read_uploaded_excel_bytes`（空文件 + 16MB 友好中文校验），`read_uploaded_xlsx` 复用同一段；新增超大文件友好提示回归。
- `ResourceDispatchActualRecordService` 增加可选注入 `execution_service` / `feedback_service`，request_services 装配时传入已 cached 实例，消除请求内重复构造，且不反向依赖 web 装配层。

## 4. 验证证据

- 受影响领域回归：执行 / 资源派工 / 计划现场复盘 / 重排 / Excel / 标签 / viewmodel / 状态版本共 393 passed。
- 全量测试：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q` → 3772 passed。
- 静态：改动文件 ruff All checks passed、Python 3.8 py_compile 通过、`node --check static/js/resource_dispatch.js` 通过。

## 5. 相关文档

- `.codestable/features/2026-05-28-resource-dispatch-site-records/resource-dispatch-site-records-checklist.yaml`
- `.codestable/issues/2026-05-28-resource-dispatch-internal-execution-token-leak/resource-dispatch-internal-execution-token-leak-fix-note.md`
- `.codestable/compound/2026-05-28-explore-shop-floor-feedback-usage.md`
- `.codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-roadmap.md`

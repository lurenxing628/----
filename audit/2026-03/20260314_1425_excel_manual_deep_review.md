# Excel 用户说明补强深度审阅报告

- 时间：2026-03-14 14:25
- 触发原因：用户要求继续实现并做深度 review / 审计留痕
- 证据：
  - `evidence/DeepReview/reference_trace.md`
  - `tests/regression_config_manual_markdown.py`
  - `tests/regression_manual_entry_scope.py`
  - `.cursor/skills/aps-post-change-check/scripts/post_change_check.py` 运行结果
  - `git diff --name-only`

## 事实摘要

- 说明入口已从仅 `scheduler.*` 页面可见，扩展为复杂页面白名单控制，并按 endpoint 跳转到说明书对应章节。
- 说明书页已支持 `src` 来源页返回链路；来自非 `scheduler` 页面时会隐藏排产子导航。
- Excel 通用导入组件已补充：`.xlsx` 限制、首个工作表 `Sheet1`、先预览后确认、单行报错整份不导入、导入后再导出复核。
- Excel 关键页面帮助卡已补成字段级提示，覆盖了列名、格式示例、依赖前置数据和高风险模式提醒。
- `web/routes/scheduler_config.py` 已收敛为只从 `static/docs/scheduler_manual.md` 读取事实源，不再回退读取 `web_new_test/static/docs/scheduler_manual.md`。
- “技能等级”用户可见文案已统一为 `初级 / 普通 / 熟练`，并注明兼容英文 `beginner / normal / expert`。
- 回归结果：
  - `python tests/regression_config_manual_markdown.py`：PASS
  - `python tests/regression_manual_entry_scope.py`：PASS
  - 改后检查脚本：PASS（仅提示 `web/routes/scheduler_config.py::update_config` 复杂度 17，为既有问题）

## 结论与取舍

### 必须改（P0/P1）

- [x] 无未修复的 P0 / P1 问题。

### 本轮已修复的关键问题

- [x] 说明书事实源口径与运行时路径不完全一致：已把运行时读取逻辑收敛到 `static/docs`。
- [x] Excel 页的帮助提示还不够“照着填”：已补成字段级说明，不再只有笼统的“下载模板 / 上传预览”。
- [x] “技能等级=专家/熟练”存在口径冲突：已按真实服务层规则统一为 `熟练`。

### 建议改（P2）

- [ ] 若后续继续追求“未保存表单也不怕跳转”，需要补表单草稿持久化或局部抽屉式说明；当前方案只能保证“能回去”，不能保证“未保存输入不丢”。这是同页跳转方案的残余 UX 风险。
- [ ] 若后续复杂页面继续增加，建议把“复杂页面白名单”和“字段级帮助卡”抽成单独配置文件或 Python 事实源；当前集中在 `templates/components/ui_macros.html`，维护成本仍可接受，但会持续变大。

### 不建议改 / 暂缓

- [x] 不建议恢复“读 v2 镜像副本兜底”。这会重新引入事实源漂移风险，和本次“唯一事实源”目标冲突。
- [x] 不建议把说明入口改成新标签页。虽然能减少未保存输入丢失风险，但与用户已确认的“同页跳转”决策冲突。

## 成本与风险评估

- 预估总成本：S
- 当前回归风险：低
- 剩余主要风险：同页跳转下，未保存表单输入仍可能因用户离页而丢失；这属于产品决策残余风险，不是当前实现 bug。

## 建议结论

- 当前实现可继续推进，不建议因本轮 review 再阻塞上线。
- 若要继续迭代，优先级最高的下一项不是再补说明文案，而是决定是否要做“复杂表单草稿保留”。

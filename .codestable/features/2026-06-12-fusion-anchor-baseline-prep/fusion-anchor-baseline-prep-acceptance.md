# fusion-anchor-baseline-prep 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-12
> 关联方案 doc：fusion-anchor-baseline-prep-design.md（approved，Codex 设计两轮 BLOCK→PASS + 实现两轮 BLOCK→PASS-WITH-SUGGESTIONS，建议全采纳）
> 实现提交：（基线三件套主体）/ 5e98670c（实现审核 2 阻塞净修）/（复审建议两处）

## 1. 接口契约核对

- [x] `capture_ui_baseline.py` 手跑接口与 design 2.1 一致：复用 browser_support 造数起服（TemporaryDirectory + pytest.MonkeyPatch.context 适配 fixture 签名 + 手动 publish_shared_dir/reset_shared_dir）；遍历 FULL_UI_CONTRACT_PATHS × (light, dark)；产物 output/ui_baseline/<时间戳>/<安全化路径>__<theme>.png + index.md；退出码非 0 当且仅当任一页失败。
- [x] `ui_baseline_capture.mjs`：CDP captureScreenshot；复用 createCdpClientClass + WAIT_FOR_PAGE_STABLE_EXPRESSION；不碰探针本体。
- [x] 实现期修订均回填 design：① 守卫「只进组」被 test_required_groups_cover_required_registry 否决 → GUARD_TESTS+组双登记（挂载点 5 修订留痕）；② index.md 措辞 20 行两列。

## 2. 行为与决策核对

- [x] 决策 1 六类锚白名单（dashboard 正则/EXPECTED_PAGE_SIGNALS/language_polish 28 文件面+Python 文案补注/全模板扫描 3 测试/manual 系 2 脚本/CDP 探针 JS 硬锚）每条带可重跑命令，逐条实跑：grep 全命中、pytest 16 条全绿、verify_manual_styles OK。
- [x] 决策 2 不另立机器锚源：清单是导览 md，零 yaml 副本。
- [x] 决策 3 落档 drafts/anchor-baseline.md；缓存税两条（debt-ledger-sync 自税 + quickref 指纹）写明。
- [x] 决策 4 CDP 复用：load 事件先挂再 navigate（Codex 阻塞修复，照 probe.mjs:296-309）+ 落点校验（重定向页不进基线）+ navigate errorText 检查（防 Chrome 错误页掺假）+ 暗色两帧 rAF；browser_support/probe.mjs 零 diff（git diff 实证）。
- [x] 决策 5 产物纪律：output/ gitignore（git check-ignore 实证）+ hook 拉黑（git add 被拒实证）；无像素 diff 代码（grep 仅文档句命中）。
- [x] 决策 6 打印修复：print.css @media print 隐藏名单加 .sidebar 一行；print-to-pdf 前后实证（509KB→487KB 侧栏列消失）；屏幕介质零回归（required 几何契约+浏览器冒烟绿）。
- [x] 决策 7 打印回归清单并入第三节（必查项 5 条 + 消费方提示 + 可重跑命令）。
- [x] 挂载点 5 项落地；拔除沙盘：删 4 新文件 + print.css 一行 + 双登记两行即完全退出，零其它挂入。
- [x] Chrome/profile 清理照探针先例（关 client→SIGTERM→等 3s→SIGKILL→删 profile），实测 0 残留；waitForChromeExit 看 exitCode+signalCode。

## 3. 验收场景核对

- [x] S1 清单三节齐全，六类锚命令逐条实跑通过。
- [x] S2 实跑 3 次（修复迭代后各复跑）：20 页 × 亮/暗 = 40 PNG + index.md 全成功；dashboard 亮/暗两张目检——暗色深背景、亮色浅背景，主题正确。
- [x] S3 失败注入（无服务端口）：逐页错误 JSON + 退出码 1；py 层 returncode 与零输出双检查。
- [x] S4 print-to-pdf 前后对照实证（before 509390B 含侧栏列 / after 487410B 无）。
- [x] S5 test_print_css_contract.py 2 条绿；test_long_gate_manifest 25 条全绿（required registry 与组覆盖自洽）。
- [x] S6 required 门禁：daily gate 通过（并行会话 backup WIP 暂存验证后立即还原；浏览器几何冒烟 2 passed）。
- [x] S7 output/ui_baseline 不可入库：git check-ignore 命中 + git add 被 .gitignore 拒（实证输出留存）。
- [x] 反向核对全过：EXPECTED_PAGE_SIGNALS / language_polish / probe.mjs / browser_support.py 零 diff；CORE_BROWSER_SMOKE_PATHS 仍零消费方（grep 实证）；无像素 diff 代码。

## 4. 术语一致性

- 「锚点/爆点/截图基线/缓存税」四术语 design 与 anchor-baseline.md 同口径；清单头部明示「活文档 + EXPECTED_PAGE_SIGNALS 是机器真相源」。

## 5. 架构归并

- [x] ARCHITECTURE.md 模块索引补「改版基线三件套」条目（见下方归并提交）。
- [x] anchor-baseline.md 即 LIVE 导览档，roadmap items notes 的「开工前先查本产物」引用已可兑现。

## 6. requirement 回写

design frontmatter `requirement` 为空；本 feature 是工程基建（模块 G 守卫与门禁），非用户能力。结论：**无 requirement 回写**。

## 7. roadmap 回写

- [x] items.yaml：fusion-anchor-baseline-prep `status: done`（yaml 校验通过）。
- [x] 主文档第 3 条标 ✅ done。
- [x] 解锁效果：fusion-tokens-single-source（第 5 条）与 fusion-dashboard-cockpit（第 19 条）就绪。

## 8. attention.md 候选盘点

候选 1：「CDP 截图/采样必须先挂 Page.loadEventFired 再 navigate 再 await——直接 evaluate 稳定表达式会跑在旧 document 上静默截旧页」。
候选 2：「tests/app_runtime 的 _find_* 系函数是 pytest fail/skip 语义，手跑脚本要用 _resolve_* 纯探测版」。
（仅登记，落不落由用户定。）

## 9. 遗留

- Codex 复审两条小建议已修（signalCode 判断、_resolve_chrome）。
- print.css 的 `header, nav` 元素级选择器对未来新壳脆弱——归 fusion-tokens-single-source 顺手评估（design 2.5 已记）。
- ui_geometry_probe.mjs 379 行逼近大文件感知线——后续扩探针先拆传输层/采样层（design 2.5 已记）。
- 截图基线的「改版前基线」已留存 output/ui_baseline/20260612_032724/（40 张，本机产物不入库；后续动模板 feature 改版后复跑对照）。

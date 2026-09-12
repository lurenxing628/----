---
doc_type: feature-acceptance
feature: 2026-09-12-wbui-prototype-css-cleanup
status: "completed-with-validation-limit"
summary: "原型样式清理、导入快照保留及生产工作区样式集成实现已收尾；验收结论为completed-with-validation-limit。"
tags:
- workbench
- css
- prototype
roadmap: workbench-ui-refinement
roadmap_item: wbui-prototype-css-cleanup
created: '2026-09-12'
implementation_status: "done"
full_gate_status: "failed"
closure_reason: "用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。"
validation_limit: "原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。"
final_build_id: "e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043"
final_evidence: "evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json"
---

**本轮收尾与验证限制**：本项实现以构建 `e6964b9a4bc1c3e7855de1b0b677b0a402ba8063292a55f0778f9697c2f75043` 收尾，验收结论为 `completed-with-validation-limit`，统一证据见 `evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。原完整门禁exit2；pytest 16503项中16491 passed、1 failed、11 skipped。唯一失败为KB旧测试显示预期；仅helper修正后完整受影响模块1 passed / 7.20s。daily=passed；UI=passed；未取得全仓全绿证明。用户明确要求不再重跑完整门禁，原话：“整你完整门禁还跑干嘛，就失败一个小问题也花一个小时去跑？”。本轮按原full真实失败、唯一KB显示旧测试预期的完整模块复测通过，以及daily/UI实际结果收尾；关闭的是完整门禁重跑要求，不是将失败改成通过，也不代表用户签发全仓通过。下方局部验证及旧 build 记录保留原有范围和归属；本轮证据来自隔离 UI 快照，不构成 clean-worktree proof。

# 原型清理验收

## 本轮变更

- 原始 114 文件源与导入快照的哈希一致；原源冻结在 `/tmp/aps-wbui-implementation-20260912/prototype-cleanup-before/`，全前端起点另见主线程 `source-before.tar.gz`。
- 删除 37 条无元素创建者的旧规则，范围为旧首页 rest/fr 待办卡片及 dashboard/field 的退役片段。对原型入口脚本闭包和当前生产 app 双向查找，均无固定创建者；这些不是状态后缀动态生成类。
- 删除 19 条在同条件、同选择器、同属性下被后置有效声明覆盖的旧声明。删除的规则没有 `!important`，没有为凑数删除现存优先级保护。
- 698 条数字字号改为既定六档令牌，等距向上选择，保留字号以外的字重/行高。25 处白色文字改为双主题同值的 `--ui-text-inverse`。16 个桌面断点改到 1280/1366/1600；低于 1000 的小视窗专用条件保留。
- 甘特控件圆角源定义接 `--wb-radius-control`；计划页明确 4/8px 控件和弹层圆角改相应令牌。甘特条形/组的图形令牌以及基础资料 hub 原有显式圆角例外保留。
- 经 system owner 协调，将原型 SMOverview 自检改为默认关闭 details，保留诊断字段与原时区转换。生产 SystemLive 由 system owner 维护。
- 按规定只改 `前端设计/`，再 `import_prototype.py --update` 更新到 prototype；114 文件闭包未变化。未执行 static 构建、未改其他 owner 的 app JSX、未 git add/commit。

完整删除文本、原行号、覆盖证据、字号映射计数和前后哈希见 [prototype-css-changes.json](prototype-css-changes.json)。令牌引用比数字文本更长，源文本字节增加；本次不宣称资源包体积减少。

## 已完成验证

- 宿主 CSS parser 对全部导入 CSS 与入口 style 块解析：0 错误，0 半像素字号声明。
- `verify_snapshot` 校验 114 文件全部通过；`git diff --check -- frontend/workbench/prototype` 通过。
- 原生 `unittest` 运行 `tests.workbench.test_assets_build.WorkbenchAssetsBuildTest` 中 5 条针对性合同全部通过（10.010s）：`test_snapshot_paths_and_hashes`、`test_snapshot_drift_fails_closed`、`test_importer_rejects_external_resources_and_preserves_local_changes`、`test_entry_css_order_and_original_inline_rules`、`test_all_other_prototype_pages_still_compile`。测试在临时目录构建，不覆盖生产 static。
- Chromium 109.0.5414.46 对原型入口的改前/改后 × 浅/深色 4 个变体真实加载：导航到值班台与系统页，无脚本错误、无外网请求；自检默认关闭，Enter 可展开。1280×720 下侧栏文本 13.5px→14px、顶栏按钮 12.5px→13px。8 张截图及原始结果位于 `/tmp/aps-wbui-implementation-20260912/prototype-cleanup-browser/`。该证据针对原型源入口，不等于生产 15 个工作区的几何验收。
- 最终探针绑定当前 source-manifest SHA-256，运行前后核对全部 114 个源文件；耐久结果见 [prototype-browser-evidence.json](prototype-browser-evidence.json)，没有用清理前截图冒充最终源证据。

## 明确未通过的入口与剩余范围

- 同 5 条资产测试最初用 pytest 入口时，在 `tests/conftest.py` 的全局 fixture 导入既有调度代码失败：`optimizer_multi_start_dedup.py:19` 无法 import `native_multi_start_calendar_snapshot`。测试尚未执行即失败；后续原生 unittest 通过仅证明资产合同，不说明该全局导入问题已修复。
- `tests/workbench-native-style.cjs` 在改前即因缺少 `jsdom` 不能启动；给定 NODE_PATH 也未提供 `@babel/standalone` 和 `rrweb-cssom`。没有把该入口记录为通过，采用现有真实 Chromium 109 与本地已捆绑 Babel 完成可运行部分。
- 原型仍使用的甘特规则、动态状态类、日期选择器与窄屏弹窗、打印和触屏规则继续保留。不能把生产未装载或截图未命中自动解释为原型源码已死。
- 曾列出的最后 4 个内联 style 文件已由各 owner 收口；最终 `rg -n '<style' frontend/workbench/app --glob '*.jsx'` 返回无匹配。其余实时内联几何/主题变量效果不属于可删除静态 CSS。
- 统一 build_id 与生产浏览器 G1–G6/交互/质量门禁由主线程收口；完成前 integrated-browser 保持 pending。当前为 dirty worktree 局部证据，不能声称 clean-worktree proof。

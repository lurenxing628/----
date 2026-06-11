# fusion-tokens-single-source 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-12
> 关联方案 doc：fusion-tokens-single-source-design.md（approved，Codex 设计两轮 BLOCK→闭合 + 实现两轮 BLOCK→PASS-WITH-SUGGESTIONS，建议全采纳）
> 实现提交：（feat(令牌) 主体）/（修(令牌) shadow-md 坍缩净修）/（强化(令牌守卫) 锚断言升级）

## 1. 接口契约核对

- [x] 00-tokens.css 五段结构与 design 2.1 骨架一致（217 行 → 修复后 218 行）：语义层 --ui-*（回退链坍缩为直接值）/壳层结构 token 原名搬移/dark 纯 token 重赋值（非 token 行 0/红线 10）/别名块语义色旧名两组/头注释（唯一真相源声明+阈值跨语言对照）。
- [x] LOAD_WARNING_RATIO=0.75 / LOAD_DANGER_RATIO=0.90 公开于 dashboard_workbench_cards.py（模块 docstring 注明唯一真相源 + 第 15 条契约名）；workbench.py import 同对象。
- [x] 实现期偏差回填：--ui-shadow-md 坍缩初版取错（ui_contract fallback 一层值），Codex 审核抓出后改为旧运行时实际值（style.css 两层叠）——守卫补 COLLAPSED_VALUE_ANCHORS 防再漂。

## 2. 行为与决策核对

- [x] 决策 1 五段齐全；回退链坍缩值与旧运行时逐项对照（Codex 机械对照 HEAD~2：style.css 首 root 27 个/V1 root 6 个/ui_contract root 56 个/暗色块 54 个，除三定版色与有意省略的旧别名外零缺失零漂移；--ui-radius 0.375rem→6px 视觉等价——rem 基于 html 16px 根字号，body 14px 不影响）。
- [x] 决策 2 影响面：只动主色三 token（CDP 实证 #16a34a/#d97706/#dc2626）；四件套不动（--ui-success-text 仍 #15803d 实证）；A/B 亮暗两套都翻。
- [x] 决策 3 别名块只收语义色两组（--primary-color 系 6 名 + --aps-* 6 名）；壳层名原名搬移；白名单零 diff（--aps-bar-color/--aps-stack-gap/--aps-tone-* grep 计数前后一致：1/53）。
- [x] 决策 4 --space-1..7 新阶建档；--ui-space-1..6 旧阶原值保留（Codex 对照确认一致）。
- [x] 决策 5 阈值单点：守卫 is 断言 + viewmodels glob 唯一定义点断言；severity 判级行为零变化（dashboard 测试 13 条绿）。
- [x] 决策 6 守卫四断言 + 双登记（GUARD_TESTS + ui_layout 组，test_long_gate_manifest 26 条自洽）；先红后绿实证（style.css 播种 #abcdef 即红）；冻结字典初值=Codex 复算实测值（ui_contract 294/style 72/其余不变）。
- [x] 决策 7 锚迁移：token 断言指 00-tokens、组件选择器仍指 ui_contract（双读取拆分）；9 条绿。
- [x] 决策 8 全局 :focus-visible 在 ui_contract.css 末尾；输入框既有 :focus 特异性更高不被覆盖（Codex 核证）。
- [x] 决策 9 链首加载；static_versioning mtime 零配置生效（页面 ?v= 实证）。
- [x] 挂载点 7 项全落地；拔除沙盘：删 00-tokens.css + base.html 一行 + 还原两文件搬移段 + 还原阈值/锚/登记改动即完全退出。

## 3. 验收场景核对

- [x] S1 五段齐全（守卫断言钉死）。
- [x] S2 旧定义零残留：`^:root`/dark 定义块全仓仅 00-tokens.css（Codex rg 实证）；style.css 1000→963、ui_contract.css 6277→6139。
- [x] S3 全站渲染：web_pages 362 passed；几何 HTML 契约 + 真浏览器冒烟 2 条绿（CDP 探针硬锚不撞）。
- [x] S4 语义色生效实证：CDP getComputedStyle 三主色=定版值；--ui-success-text=#15803d 不动；A/B 对照（改前 20260612_032724 / 改后 20260612_041723）dashboard 亮暗目检版面零漂移。
- [x] S5 别名兼容实证：--primary-color=#2563eb / --aps-success=#16a34a 解析正确；壳层旧名 computed-style（--font-family/--sidebar-width=240px/--bg-color=#f1f5f9）与改前一致。
- [x] S6 阈值单点 is 断言绿；dashboard 行为零回归。
- [x] S7 守卫先红后绿 + 漂移注入自检（追加同名错误值即抓）。
- [x] S8 焦点环：全局规则上岗 + compatibility 反向抑制协同（Codex 核证无冲突）。
- [x] S9 锚迁移绿 + manifest 自洽绿。
- [x] S10 daily gate 通过（并行会话 WIP stash 隔离后跑，跑完即还原）。
- [x] 反向核对全过：其余 5 个 CSS / templates（除 base.html）/ JS / EXPECTED_PAGE_SIGNALS / language_polish 全零 diff（git diff --stat 0 行实证）。

## 4. 术语一致性

- 「token/别名块/裸 hex/冻结白名单」四术语 design、00-tokens.css 头注释、守卫测试 docstring 同口径。

## 5. 架构归并

- [x] ARCHITECTURE.md 补「设计令牌单一真相源」条目（见归并提交）。
- [x] anchor-baseline.md 第一节③⑤所涉锚未撞（manual-* 规则零 diff；language_polish 零 diff）；缓存税按预期吃 4 entry 作废 + GUARD_TESTS 登记一次全量重跑。

## 6. requirement 回写

design frontmatter `requirement` 为空；工程基建（模块 T 设计系统）非用户能力。结论：**无 requirement 回写**。

## 7. roadmap 回写

- [x] items.yaml：fusion-tokens-single-source `status: done`。
- [x] 主文档第 5 条标 ✅ done。
- [x] 解锁：fusion-hex-migration（第 6 条）、fusion-frontend-gates（第 4 条）、fusion-gantt-load-strip（第 15 条，依赖 9 未齐）就绪性刷新。

## 8. attention.md 候选盘点

候选 1：「CSS 回退链坍缩必须取链首文件的旧运行时实际值，不是本文件 fallback 字面值——shadow-md 两层叠被坍缩成一层就是这么漏的」。
（仅登记，落不落由用户定。）

## 9. 遗留

- 存量 678→675 裸 hex 与 180 块暗色散规则归 fusion-hex-migration（冻结白名单已就位，清零即下调字典）。
- px/rem 双写制（13px vs 0.8125rem 并存）归 hex-migration 顺手评估（design 2.5 已记）。
- 散 :focus 样式清理归第 10/6 条；--ui-space-* 旧阶消费方迁移归 debox/longtail 波次。
- 别名块期满删除时间点：hex-migration 完成后评估（00-tokens.css 头注释已标）。

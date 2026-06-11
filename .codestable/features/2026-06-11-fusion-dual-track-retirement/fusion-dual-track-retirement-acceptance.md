# fusion-dual-track-retirement 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-11
> 关联方案 doc：fusion-dual-track-retirement-design.md（approved，经 Codex 三轮设计审核 BLOCK→BLOCK→PASS）
> 实现提交：dab79ed2（步1）/ 93f86c7e（步2）/ a269c424（步3）/ 9831bda8（步4 原子）/ 3ae87ccb（步5）/ 540928ff（Codex 实现审核修复）/ 2396e0b9+378c69c3（并行会话误捎带撤回与修正）/ 248868b1（台账行号）/ 398a03f1（py38）/ 91eb10cc（速查表）

## 1. 接口契约核对

- [x] install_template_globals：web/bootstrap/template_globals.py 恰好 8 全局，与被删 render_bridge.py:68-80 注入面逐一对应（safe_url_for setdefault 语义保留，其余 7 个直赋）——Codex 实现审核脚本验证 count 8。
- [x] 35 路由 `from flask import render_template`：web/routes 命中 35，零 render_ui_template/web.ui_mode 残留。
- [x] versioned url_for 不丢：static_versioning context_processor 对 flask 原生渲染生效，实测 GET / 17 个 /static/ 链接全部带 ?v=（Codex 与我方双重实证——这是最大的静默回归风险点，已排除）。
- [x] _log_warning 内化 manual_src_security（先搬后删顺序遵守，函数体纯 logging 无状态）。

## 2. 行为与决策核对

- [x] 六步序逐步独立 commit 且各步验证留痕（见提交信息）。
- [x] 决策 7 台账两段式：删样本→留 scope 一刷（旧 ui_mode 条目清除）→收窄常量→二刷→check 0 错；后因步 4 行数变化补一次行号对齐（248868b1）。
- [x] 决策 8 style.css 临时双份：步 2 入守卫第 8 对，步 4 随守卫整体退役——守卫文件 git log 显示生卒于同一 feature，符合"临时保险"定位。
- [x] 探针 meta 删除 + 双入口判定改"壳结构+主题按钮"：错误页无壳结构已双方核证，无误判风险。
- [x] 明确不做反向核对：print.css 零 diff ✓；error_base.html 零 diff ✓；sidebar 无 icons 新增 ✓；APP_UI_MODE 轴测试零 diff ✓（system_health.py 的 ui_mode 键是 APP_UI_MODE 语义，保留正确）；manual_src_security 安全函数签名零变化 ✓。
- [x] 挂载点 6 项全部落地：base.html 覆盖、template_globals+factory、static_versioning:22、bat 2 处、tools 7 文件、界面设置卡+路由删除。
- [x] 拔除沙盘：本 feature 是删除型——"拔除"即恢复双轨，所有删除面有 git 历史可逆；无新增不可卸载挂入点（template_globals 是 8 全局的唯一安装点，可整文件移除）。

## 3. 验收场景核对

- [x] S1 步1：V2 gantt `<title>`=「甘特图（排程可视化）」实证。
- [x] S2 步2：v1 强制 cookie 渲染出侧栏壳（sidebar/top-header/workbench/style.css 链全在）；required 1724+221 绿。
- [x] S3 步3：GET /system/backup 无界面设置卡无表单；镜像守卫 8 对绿。
- [x] S4 步4：grep 残留逐项裁决（台账 JSON/render_bridge 标签字符串/docs 历史档案为白名单）；14 核心页面 200 且工作台入口齐；POST /system/ui-mode 404；import app 不炸；8 全局真渲染可用。
- [x] S5 **full gate 全净通过**（干净 worktree，质量门禁 17 步「质量门禁通过」）——过程中按门禁反馈逐项净修：台账行号、py38 tuple、速查表 3 处（各自独立 commit）。
- [x] S6 步5：base.css 物理删除全仓零引用；verify_manual_styles 单模式实跑 OK。
- [x] S7 视觉零变化：浏览器几何冒烟 2 passed（真 Chrome 渲染新壳）；步 2 中间态两壳仅静态链端点一行差异。

## 4. 术语一致性

- 「双轨/UI 模式/经典界面/现代界面」生产代码与 LIVE 文档零残留（README、系统速查表、手册、page_manuals 全部单界面口径）；docs/ 三份历史评审报告按 design 白名单保留。
- aps_ui_mode cookie 活代码零残留（Codex 审核抓出最后两处测试已修）。

## 5. 架构归并

- [x] ARCHITECTURE.md：工作台入口条目改单壳口径（双壳挂载叙述更新为唯一壳）、首页值班台条目"现代镜像"措辞清除——见下方归并提交。
- [x] 系统速查表（LIVE 门禁源）已同步（91eb10cc）。
- [x] ADR v2-sidebar-shell-promotion 即本 feature 的决策档案，无需另立。

## 6. requirement 回写

design frontmatter `requirement` 为空，本 feature 为架构退役（删除型技术债收口）非新增用户能力。结论：**无 requirement 回写**。

## 7. roadmap 回写

- [x] items.yaml：fusion-dual-track-retirement `status: done`（校验过）。
- [x] 主文档第 5 节第 2 条标 ✅ done；第 26 条补注"已随第 2 条完成按计划退役删除"。

## 8. attention.md 候选盘点

候选 1：「full gate 必须在干净 worktree 跑（git worktree add /tmp/xx HEAD + 链接 .venv），主工作区有并行会话 WIP 时直接跑必污染」。
候选 2：「速查表（开发文档/系统速查表.md）是 LIVE 门禁源——删路由必同步，check_quickref_vs_routes 对账」。
（仅登记，落不落由用户定。）

## 9. 遗留

- UI_MODE_STARTUP_SCOPE_PATHS 等旧常量名（内容已收窄到 manual_src_security）——Codex 建议改名，裁决暂不动：名字被台账 JSON scope 字段与 gate 测试消费，纯命名重构动受控台账收益小于风险，归后续 cs-refactor。
- V2 sidebar 打印可见缺陷（print.css 不认 .sidebar div）——存量缺陷，归 fusion-anchor-baseline-prep 打印介质回归清单。
- style.css「V1 收编区」六个 --aps-* 临时变量与 ui_contract.css 暗色重定义——归 fusion-tokens-single-source。
- 并行会话的 backup/restore 改动集（6 文件）仍在工作区未提交，归该会话自行收口；本 feature 曾误捎带其中 1 文件已撤回修正（2396e0b9+378c69c3）。

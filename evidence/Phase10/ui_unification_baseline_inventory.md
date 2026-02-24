# 全站 UI 统一基线盘点（Phase 0）

更新时间：2026-02-24

## 目标

在不改动后端业务逻辑和路由参数语义的前提下，建立“全站 UI 统一改造”的可量化基线。

## 模板规模

- `templates/`：48 个模板（含 `templates/components/ui_macros.html`）
- `web_new_test/templates/`：6 个模板
- 双模式渲染入口：`web/ui_mode.py`

## 关键样式入口

- V1：`static/css/base.css`
- V2：`web_new_test/static/css/style.css`
- 兼容层（新增）：`static/css/compatibility.css`
- 甘特图：`static/css/aps_gantt.css`、`static/css/frappe-gantt.css`

## 现状计数（改造前基线）

- `templates/**/*.html` 中 `style="..."` 使用：45+ 文件存在（重点集中在 `scheduler/system/process`）
- `templates/**/*.html` 中 `<button` 使用：30+ 文件存在
- `web_new_test/templates/**/*.html`：仅覆盖 `dashboard` 与 `scheduler` 部分页面

## 风险清单

- V1 页面对内联样式依赖较重，需分波次清理，避免一次性重写导致回归。
- 甘特图页面与第三方库样式耦合，需保留“强制覆盖策略”。
- UI 统一需兼顾 Win7 + Chrome109，不引入在线资源与新依赖。

## 本阶段新增资产

- 新增宏组件：`templates/components/ui_macros.html`
- 新增兼容样式：`static/css/compatibility.css`

## 下一步

- 将统一样式契约注入 `templates/base.html` 与 `web_new_test/templates/base.html`
- 优先落地排产链路：`batches` / `gantt` / `batches_manage` / `config`

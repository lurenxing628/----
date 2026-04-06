# APS 说明书布局与样式核验报告

- 核验日期：2026-03-15
- 留痕目标：记录本轮“说明书回归修复”实际执行过的脚本与结果

## 实际执行的命令

1. `python tests/regression_config_manual_markdown.py`
2. `python tests/regression_manual_entry_scope.py`
3. `python tests/regression_page_manual_registry.py`
4. `python tests/regression_frontend_common_interactions.py`
5. `python check_manual_layout.py`
6. `python verify_manual_styles.py`

## 结果摘要

### 回归脚本

| 脚本 | 结果 | 说明 |
|------|------|------|
| `tests/regression_config_manual_markdown.py` | PASS | 保持说明书 Markdown 渲染、JSON 契约、页面模式/整本模式行为稳定 |
| `tests/regression_manual_entry_scope.py` | PASS | 已覆盖全部可无参访问的 manual endpoint 渲染验证 |
| `tests/regression_page_manual_registry.py` | PASS | registry / manual_id / anchor 契约一致 |
| `tests/regression_frontend_common_interactions.py` | PASS | 基座脚本加载顺序与公共交互契约一致 |

### 样式/结构核验脚本

| 脚本 | 结果 | 说明 |
|------|------|------|
| `check_manual_layout.py` | PASS | 6 项 CSS 静态规则全部通过 |
| `verify_manual_styles.py` | PASS | `manual-related-body` 的 code/pre 样式、暗色样式、v1/v2 HTML 占位结构全部通过 |

## 关键事实

### `check_manual_layout.py`

- 已修复仓库根路径依赖，脚本不再要求从特定 CWD 启动。
- 已把“相关模块面板最小宽度”检查从宽松的字符串 `or` 改为精确规则匹配。
- 当前环境下未安装 `selenium`，因此浏览器自动化分支未执行；脚本明确输出了跳过原因，没有把“环境缺少浏览器驱动”误报成布局失败。

### `verify_manual_styles.py`

- 已改为本地 `Flask test_client` 校验，不再依赖外部启动服务。
- 实际验证了以下契约：
  - `.manual-related-body code` 基础样式存在
  - `.manual-related-body pre` 基础样式存在
  - 暗色主题下 `code/pre` 样式存在
  - v1/v2 下 `material.materials_page` 与 `scheduler.config_page` 的页面级说明均返回 200
  - 页面 HTML 中存在 `manual-main-column`、`manual-related-panel`、`manual-related-body`、`data-manual-markdown`、`config_manual.js`、`aps-config-manual-data`

## 结论

- 本轮说明书回归修复涉及的 6 个验证脚本均已实际执行并通过。
- 当前能被脚本化验证的结构、样式与入口契约，已经形成可失败门禁，不再停留在“只打印、不拦截”的状态。
- 仍未覆盖的部分只有真实浏览器渲染层面的 sticky/滚动/宽度观感；这部分需在具备 `selenium + ChromeDriver` 或手工浏览器环境时补跑。

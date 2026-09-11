---
doc_type: issue-fix
date: 2026-09-08
slug: trial-sidebar-footer
status: implemented
scope: local trial prototype sidebar
clean_worktree_proof: false
---

# 删除试调侧栏底部说明

按用户标记，删除侧栏底部的“回转壳体单元 / 本地示例工作区”，连同分隔线和占位一并移除。只删侧栏内容，不删正文的数据来源、预览提示或页面底部说明。

修改均位于 `前端设计/ui_kits/workbench/`：

- `trial-sample-views.js:51`：移除 `tr-sidebar-foot` 节点。
- `trial-sample.css`：移除对应样式及窄屏隐藏规则中的废弃选择器；侧栏导航继续使用原来的 flex 布局。
- `index.html`、`trial-sample.html`：更新上述两个共享资源的内容哈希。
- `tests/trial-sample-text.cjs:25`：增加节点不存在、14 个导航目的地保留、试调当前导航保持的浏览器断言。

实际验证：`trial-sample-text.cjs` 通过 12 个组合、192 个甘特标签，覆盖 1392x924、1920x1080、390x844 及双主题，新增的侧栏断言在 6 个尺寸/主题状态均通过。`workbench-offline-assets.cjs` 的 234 项本地资源/语法检查通过。

另用两桌面尺寸及双主题直接检查侧栏，占位、文案和导航共 16 项通过，导航底边与侧栏底边相同，没有残留页脚空白。截图与结果在 `/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-trial-sidebar-cUIkxw/`。主入口与独立试调入口的资源哈希全部核对一致。

修改前快照：`/tmp/aps-trial-sidebar-before-20260908.tgz`。甘特文本测试输出：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-trial-text-lzQcvw/`。临时目录可能被系统清理。

未更改图标、甘特展开逻辑、主题或任何方案数据。用户另提的现场实际甘特背景与图标问题在本轮只读检查，不包含在这次删除中。

现有未提交内容保持不动，未提交或强制加入受忽略的原型目录；既有暂存 `tests/gate_meta/test_frozen_bundle_contract.py` 的 200 行新增未变化。只完成原型局部验证，未运行 Python 整仓质量门禁或 Win7 实机，未新增依赖或联网资源。

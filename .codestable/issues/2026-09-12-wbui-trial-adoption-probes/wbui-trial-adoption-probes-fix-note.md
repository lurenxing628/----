---
doc_type: issue-fix
slug: wbui-trial-adoption-probes
status: fixed
created: 2026-09-12
summary: 修正采用历史测试的导航启动数据及场景采用测试的折叠目录定位。
tags: [workbench, browser-test, trial-adoption]
---

# 场景采用与采用历史浏览器测试收口

两个旧失败均先核对保存的报告和截图：`history-widgets.json` 没有浏览器异常，截图明确显示“工作台导航信息不完整，请检查本机安装文件。”；测试启动数据没有提供现行导航合同要求的字段。Python 夹具改为引用生产 `VIEW_TITLES`、`VIEW_ALIASES` 和 `navigation_groups()`，补齐导航与帮助入口。探针继续执行真实 `main.jsx`，明确核对每份应用源码及 main 只加载一次，并等待原 `scenario_ref` 的实际详情读取完成。

另一份采用测试的旧截图已经显示新正式方案，浏览器异常也为空；失败源于计划目录默认折叠后不再挂载表格。测试通过真实“展开计划目录”按钮展开，随后核对唯一选中行、勾选状态、精确版本 `41`、原回执 `plan_ref` 及当前/历史身份。后续产生版本 `42` 后仍须展示原回执对应的历史版本 `41`。私有编译补齐计划选择模型；“采用已暂停”提示定位限定在采用弹窗，避免与行内禁用原因重复命中。

没有修改产品或业务夹具 support，没有改用模拟成功响应，也没有删除原采用、回执、同 key 重放、恢复、失败、权限及数据库保留断言。算法计时窗口内只读取和编辑，获得主线程通知后才启动验证。

## 验证

- 两个完整 Python 模块一起运行：**2 passed / 58.61s**，Chrome `109.0.5414.46`。
- 场景采用：原 4 组尺寸/主题，72 个检查、52 张截图；57 份数据库保留证据全部通过。
- 采用历史：原 4 组尺寸/主题，24 个检查、8 张截图；5 份数据库保留证据全部通过，历史请求均为 GET。
- 浏览器异常及外部请求均为空；原行与类型、原场景、已有执行和保存安排与新正式计划的一致性均通过。
- 两个 CJS 语法检查、修改的 Python Ruff 及 diff 空白检查通过；各报告的 66 / 224 个源码散列与当前文件逐项一致。

证据保存在 `/tmp/aps-wbui-implementation-20260912/trial-adoption-residual-closure/`，包含旧失败实物、窄范围补丁、`full-modules-first.log/xml`、新截图、SQLite 保留报告及 `final-evidence.json`。本轮仅为当前源码私有编译后的原仓定点验证；没有运行整仓门禁、写入旧验证副本或操作 Git index，不表述为全局 build 或 clean-worktree proof。

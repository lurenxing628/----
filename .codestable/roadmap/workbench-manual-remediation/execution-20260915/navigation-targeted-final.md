# 导航专项最终源码验证

- 执行日期：2026-09-15；最终哈希回读时间：22:41:01（本机时间）。
- 范围：关联资料父表单刷新修复后，在全体源码冻结及主代理构建完成的状态下，只复验指定单个导航组件 Chromium 用例。不改产品或测试，不重建共享资产，不控制手动验收所用的浏览器。
- 未运行 `run_quality_gate.py`、任何全门禁或整仓测试。

## 实际命令与结果

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/workbench/test_resource_navigation_context.py ResourceNavigationContextTest.test_exact_context_pending_and_key_remount
```

- 1 个测试通过，耗时 14.283 秒，进程退出码 0。
- Chromium `109.0.5414.46`；1920×1080、1392×924，各自浅色/深色，共 4 组。
- 92/92 案例通过、32 张截图；页面脚本/控制台错误 `[]`，外部请求 `[]`。
- 62 份参与源码均通过测试内 SHA-256 校验；测试结束后再次只读核对，仍全部一致。
- 覆盖原对象精确定位、工序与外协组跨页定位、只读进入维护、日历定位、迟到响应隔离、待确认操作恢复后继续跳转等。每个案例均检查未发生业务写入。
- 本轮自动几何断言检查页面横溢、按钮内容溢出及弹窗边界，并检查工序及外协组定位目标在可视范围内。没有追加其他测试。

## 构建一致性

- 构建编号：`270587be0986ef9c91d207907ef4f05e6045b23240d1c44103c33e417deb68c7`。
- 目标 `chrome109`，263 份资产。现有清单的 355 个输入文件，在测试前与测试后均只读检查为 SHA-256 全部一致。
- `static/workbench/asset-manifest.json` SHA-256：`e0b9306f229ca03a79ce7235512e3353bb0127d0040fd3f4a0fe0ded34d29871`。

## 证据与边界

- 证据目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-resource-navigation-z-ieamy915/`。
- `navigation-result.json` SHA-256：`aa224fd6a8f431d2142e9de1aa4274d9079601f0f0591dfe8750032995f59b3b`。
- 该用例直接临时编译当前源码，报告明确 `global_build=false`、`scope=resource-navigation-current-source-component-mock`、`production_persistence_tested=false`。它验证导航组件与适配器交互合同，不代替主代理真实数据库手动闭环。
- 工作区已有大量修改；本记录属于当前工作区专项验证，不构成 clean-worktree proof。未执行更多测试，也未修改产品、测试或构建文件。

## 前一轮证据保留

22:07:19 的前一轮在构建 `b5b59b1812bdf2ef8fc26e2702bcaa45cf7fc8b8a661232c661b1396bb9e7a04` 下同样为 92/92 案例通过，耗时 14.316 秒；证据目录 `aps-resource-navigation-z-qwrfaf1i/` 的 `navigation-result.json` SHA-256 为 `e296cbbf6a50de88a08c5ac470fda775e7b44ec2fc1d5c705d275af95fb22100`。当时已查看该轮 1392 浅色工时定位和深色继续跳转截图。随后父表单刷新修复修改了参与源码，因此前一轮不作为最终源码证明；上面的 22:41 结果完成最终复验。

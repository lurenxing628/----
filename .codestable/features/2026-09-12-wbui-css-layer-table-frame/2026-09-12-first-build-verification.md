# 首次集成构建验证

- 构建 `02bd429d648b55ab11be3078a3de8aa4b48d047d38c283f3ddff7fa098c04ca4`。本轮验证时仍存在并行源码改动，不是最终全站 proof。
- 命令：`.venv/bin/python -m pytest tests/workbench/test_assets_build.py tests/workbench/test_entry.py tests/app_runtime/test_validate_dist_static_payload.py tests/web_pages/test_ui_contract_component_tokens.py -q`。
- 结果：50 passed、1 skipped、1 failed，耗时 90.81 秒。完整 asset build 模块、入口和发布 payload 内部一致性检查均未失败；唯一失败是 UI token 合同验证发现 `32-calendar-outsourcing.css` 源码已新增规则、首次发布 CSS 尚未重建。
- 校验开始时来源/发布 CSS 有 32-calendar-outsourcing、35-field 两处漂移；资产测试结束后 manifest 未变，已有 23 个来源输入变化。完整来源差异保存在 `/tmp/aps-wbui-first-build-followup-20260912/`。
- 未弱化 CSS 精确字节绑定，最终构建后应重跑失败的源/发布一致性合同。此次测试没有改主 static/workbench。

## Secondary-copy 真实只读页面

- `SECONDARY_COPY_RUN_BROWSER=1 .venv/bin/python -m pytest tests/workbench/test_secondary_copy_contrast.py::SecondaryCopyBrowserTest::test_real_readonly_pages -q -s`：1 passed，62.22 秒；底层 24 个真实页面案例全部通过。
- Chromium 109，process / reports / system × 1920 / 1392 × light / dark × before / after。before 是明确标记的删除一行 CSS 别名的合成候选，未冒充历史截图。
- 无浏览器错误、无外部请求、无写请求；真实临时数据库前后业务表一致，HTTP GET 响应与传输日志字节一致，assets_unchanged=true，isolation_violations=[]，服务正常停止。
- 首轮在4个案例后发现比较器错误地比较 border-style:none/width:0 的不可绘制 border-color；这些颜色继承 currentColor，随文字修正变化而不改变画面。已改为逐边记录真实宽度/样式，只在边框实际绘制时比较颜色，真实可见边框仍严格锁定，然后重跑全部24案例通过。
- 证据 `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-lz4mf9id/secondary-copy-result.json`。服务独立冻结首次静态构建，不代表之后并行源码变化。

## 补齐资产组件浏览器项

原资产组合唯一skip是未设置 WORKBENCH_BROWSER 的 asset-only 浏览器项。使用现场 Chromium109 和已安装 Playwright 补跑 `tests/workbench/test_assets_build.py::WorkbenchAssetsBuildTest::test_chrome109_local_assets_and_component_mount`，结果1 passed，44.91秒。该测试在独立temporaryroot重新构建并真实挂载，未修改主static。至此资产模块没有未执行项；源/static一致性因后续CSS改动失败仍待最终构建。

# 资源父表单修复的前端激活核对

- 时间：2026-09-15 22:40:23（Asia/Shanghai）。
- 构建：`270587be0986ef9c91d207907ef4f05e6045b23240d1c44103c33e417deb68c7`；355 个 inputs 的实文件哈希全部匹配，交付文件 263 个。
- 真实 5000 的 PID 仍为 `19236`，启动时间仍为 22:24:39；本阶段没有重启服务。

`pages.py:60` 在每次工作台请求中读取资源清单，`assets.py:54` 直接从磁盘读取；HTML 使用 `Cache-Control: no-store`。静态脚本的版本参数由 `static_versioning.py:82` 每次读取文件 mtime 后生成。

只读请求真实 `/workbench?view=basedata` 返回 200，HTML 的 216 个脚本引用与新 manifest 一致。`ResourceWorkspace.js` 和 `ResourceForms.js` 的缓存参数均从 `1789482111` 更新为 `1789483120`；两个真实下载响应均与磁盘新文件逐字节相同。因此重新加载工作台即可取得此次纯前端修复，无需重启后端。完整 URL、ETag、SHA-256 与 PID 证据见 `production-frontend-refresh.json`。

新增 `test_resource_context_refresh.py` 按实际 Chromium109 依赖，唯一归属显式 `workbench_browser`；`resource_context_refresh_probe.cjs` 仅为依赖，reviewed 记录已同步。静态核对其 50 个编译及直接依赖均覆盖，结果见 `resource-context-registration.json`。未运行测试、构建、门禁或业务写入。

# fusion-runtime-log-viewer 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-12
> 关联方案 doc：fusion-runtime-log-viewer-design.md（approved，经 Codex 三轮设计审核 BLOCK→BLOCK→PASS-WITH-SUGGESTIONS + 一轮实现审核零阻塞 PASS-WITH-SUGGESTIONS）
> 实现提交：ad6cfff9（步1 读取层）/ e86c9c59（步2-4 页面+诊断包+接门）/ b3415f9f（复杂度净修 16→9）

## 1. 接口契约核对

- [x] `read_log_entries_tail(log_path, *, max_entries=200)` → 倒序 [{"head","body","level"}]；文件不存在返回 []；OSError 穿透（test_io_error_propagates 钉死不吞错）。
- [x] `build_diagnostic_zip(log_dir, zip_path, *, operation_logs_text, info_text, operation_logs_arcname)` → 写调用方路径不返回 bytes（launcher.log 无轮转上限，全内存构包被设计审核否决）。
- [x] 常量单点：LOG_FILE_CHOICES 三文件 / MAX_ENTRIES 200 / TAIL_BLOCK_SIZE 64KB / MAX_ENTRY_BYTES 256KB / ENTRY_HUNT_BUDGET_BYTES 4MB / ENTRY_ANCHOR_RE bytes 正则 / DIAGNOSTIC_EXTRA_FILES 显式 launch_error。
- [x] 实现期偏差均已回填 design（非偷改）：① 巡锚模式取代「累计 256KB 即停」（初版会丢超长条目头行时间戳，单测抓出后净修，design 决策 2 已记录修订因由）；② error.html 用裸路径不用 url_for（error_boundary 契约测试实证降级 app 下 url_for BuildError 会把富错误页打跌进兜底页，design 决策 7 已记录）；③ direct_passthrough=False（send_file 默认 passthrough 时 call_on_close 永不触发，残留测试抓出，design 决策 4' 已记录）。

## 2. 行为与决策核对

- [x] 决策 1 白名单：file 参数严格相等匹配，`?file=../etc/passwd` flash 警告 302 回默认（测试钉死）；无路径拼接进读取。
- [x] 决策 2 边界规则：字节层先拼接后解码（跨块多字节中文完整）；锚点匹配 bytes 层；errors=replace；偏移 0 锚点须等前块拼入确认（at_file_start 防护 + 块边界专测）；截断切点回退合法 UTF-8 边界（纯中文超长样本断言无假 �）。
- [x] 决策 4 zip 白名单三类 + secret 结构性排除 + symlink 拒收（Codex 实现审核建议，islink 挡「白名单名字指向任意文件」）。
- [x] 决策 4' 临时 zip 生命周期：mkstemp→os.close(fd)→send_file→direct_passthrough=False→call_on_close 清理（回调内不碰 current_app，logger 请求期捕获）；构包失败当场清理 + flash；两条路径无残留测试钉死。
- [x] 决策 5 info 拼现有事实：APP_NAME/CURRENT_SCHEMA_VERSION/契约版本（Codex 抓出遗漏后补）/sys.version/platform/导出时间，无新立版本号。
- [x] 决策 6 操作日志 200 条附包；读取失败放 `operation_logs_读取失败.txt` 不中断导出（monkeypatch 测试钉死）。
- [x] 决策 7 接门双路径：render_error_template 注入 occurred_at（与日志同格式）；error.html 链接+时刻；minimal 兜底裸路径文本+时刻；JSON payload 零 diff。
- [x] 决策 8 只读：无 POST 路由（url_map 断言）、模板无删除/清空按钮（反向断言）、文案明示「只能查看、不能删除」。
- [x] 挂载点 6 项全落地：system.py import / system_nav 第 4 入口 / error.html+error_boundary / 速查表两路由（check_quickref_vs_routes OK）/ GUARD_TESTS + groups_misc 双登记（不新建组，group_count==8 不破）。
- [x] 拔除沙盘：删 system_runtime_logs.py + import 行 + 模板 + 宏第 4 行 + 速查表两行 + 守卫两登记 + style.css 尾段 + error 接门两处即完全退出；reader 纯函数无其它消费方（grep 验证唯一 import 点是路由与测试）。

## 3. 验收场景核对

- [x] S1 默认页：aps_error.log 倒序、最新在上、ERROR badge、traceback 区块化——页面测试 + 真 Chrome 截图目检（/tmp/runtime-logs-page.png：侧栏高亮系统管理、四入口导航、运行日志 active、两条 ERROR 折叠条目默认展开、导出诊断包按钮在 hero 右上）。
- [x] S2 切换/非法值：aps.log、launcher.log 各自内容；`../etc/passwd` 302+警告（测试钉死）。
- [x] S3 筛选：level=ERROR 滤掉 WARNING；q=备份 命中两条排除一条（测试钉死）。
- [x] S4 三态：空文件「暂无报错记录」/不存在「日志文件尚未产生」/读取失败「日志读取失败」200 不抛 500（monkeypatch 测试钉死）。
- [x] S5 读取层边界 15 条单测：跨块多字节、超长截断+巡锚续切+预算耗尽兜底、坏字节 replace、无锚点（含 3×256KB 大文件不整读断言）、块边界锚点防误判、level UNKNOWN、IO 错误穿透。真实日志冒烟：aps.log 200 条 6.3ms / launcher.log 1.2ms。
- [x] S6 诊断包 7 条测试：内容齐全（log+分卷+launch_error+info+操作日志）；secret/x.log.bak/notes.txt/symlink 全拒收；info 事实断言；两路径无残留临时文件（resp.close() 显式触发 call_on_close）。
- [x] S7 500 接门实证：真实 create_app + 抛 RuntimeError → 500 页含 /system/runtime-logs 链接 + 发生时刻 2026-06-12 01:42:34（与日志格式逐字一致）。
- [x] S8 只读反向断言绿；导出动作落操作日志（diagnostic_export 实测留痕）。
- [x] S9 check_quickref_vs_routes OK（两路由登记后文档=实现）。
- [x] S10 **full gate 17 步全净通过**（git worktree /tmp/gate-rlv + .venv 链接，「质量门禁通过」）；daily gate 抓出的 2 项已净修：runtime_logs_page 复杂度 16(F)→9(B)（抽 _apply_entry_filters）；backup.py 503 行系并行会话 WIP 在主工作区的干扰项，worktree 复跑无此项。

## 4. 术语一致性

- 「运行日志」（文件日志）与「操作日志」（OperationLogs 审计）页面命名并列、文案明示区别；速查表/模板/路由 docstring 同口径。
- 「诊断包」全链路统一（按钮文案/下载名 aps_诊断包_时间戳.zip/速查表）。

## 5. 架构归并

- [x] ARCHITECTURE.md 模块索引新增「系统管理运行日志与诊断包」条目（读取层算法、白名单红线、zip 生命周期、错误页接门一段式收录）；last_reviewed 刷新 2026-06-12。
- [x] 系统速查表（LIVE 门禁源）两路由已登记。
- [x] design 第 4 节预言的「reader 纯函数层被第 32 条备份健康提示复用」接口已就位（list_diagnostic_log_names/read_log_entries_tail 均无 Flask 依赖）。

## 6. requirement 回写

design frontmatter `requirement` 为空；本 feature 是 roadmap 模块 N 直生新能力，无既有 req doc 对应。能力定义已完整落在 roadmap 第 34 条与本 feature design（含红线修订留痕）。结论：**无 requirement 回写**（roadmap 起头型 feature，规划层即真相源）。

## 7. roadmap 回写

- [x] items.yaml：fusion-runtime-log-viewer `status: done`（yaml 校验通过）。
- [x] 主文档第 34 条标 ✅ done（含提交区间与 full gate 结论）。
- [x] 红线修订两段留痕：第 34 条正文改白名单制 + 变更日志新增修订条 + 旧条目加「已被修订取代」标注（Codex 建议）。

## 8. attention.md 候选盘点

候选 1：「send_file 路径下载必须 direct_passthrough=False 才能让 call_on_close 触发——默认 passthrough 时 WSGI 拿裸文件包装器，清理回调永不执行（临时文件类下载通用陷阱）」。
候选 2：「测试 app 渲染 error.html 类降级模板时禁用 url_for——未挂全量 bp 的最小 app 会 BuildError 把富错误页打跌进兜底页」。
（仅登记，落不落由用户定。）

## 9. 遗留

- Codex 实现审核四建议已全采纳（contract_version/symlink/块边界单测/可写环境重跑 pytest——27 条全绿）。
- 真 Chrome 截图目检完成 1 页（默认页全要素确认）；筛选页与空态页截图因 headless Chrome 截图进程挂起未产出（页面本身 200 + 页面测试已覆盖同场景断言，非功能缺陷，系本机 Chrome 137 headless 截图模式与 dev server 的握手问题）。
- 错误页「打开运行日志」裸路径依赖 factory 注册 system bp 时的 /system 前缀——前缀若改，error.html 与 error_boundary 两处文本要同步（已在模板注释明示）。
- launcher.log 行格式 `时间 [小写词]` 解析为 UNKNOWN 级别（实测 launcher 多数行带大写 LEVEL 可正常解析；纯小写变体归 UNKNOWN 呈现是诚实降级非缺陷）。

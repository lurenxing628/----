---
doc_type: decision
category: convention
date: 2026-09-21
slug: legacy-excel-retirement-and-browser-lane
status: active
area: quality-gate
tags: [excel, retirement, browser-lane, quality-gate, ratchet, conformance]
---

## 背景与授权

上一轮盘出三件"本轮不做"的事：前端动作词统一、`unit_excel` 子系统去留、遗留失败测试。
用户裁决：旧资料迁移不会再发生（`unit_excel` 退役）、效率百分比按推荐自动还原、动作词统一做、
把文案测试拿回日常门禁（推翻 `3aafeaf9` 的"低频、不进 required"决定）、全范围并行推进。

## 决定

1. **旧资料转换整体退役。** `core/services/process/unit_excel/`（1538 行）、
   `core/services/common/excel_template_defaults.py`（11 条旧模板清单）、
   `templates_excel/` 下的旧资料样本与 7 份转换输出参考表全部删除，目录随之清空。
   它的两个调用方（`unit_excel_converter.py`、`scripts/convert_rotary_shell_unit_excel.py`）
   上一轮就删了，这个包是被漏下的孤儿：全仓库只有一个测试 import 它，生产侧零引用。
   退役前最后一个提交打了标签 `retire/unit-excel-before-2026-09-21`。
   **以后不要因为"现场可能还有旧资料"把这套复活**——12 张业务表的模板一律由工作台按表描述现生成。

2. **`excel_templates.py` 收口成单一职责。** 155 行缩到 26 行，只留 `sanitize_export_cell`
   （四个生产用户：排产实际导出、校准导出、报表导出、报表 xlsx 导出）。`build_xlsx_bytes` 与
   `get_template_definition` 随旧模板清单一起退役。`batch/file_codec.py` 去掉对旧清单的表头
   交叉校验：表头本来同源，表描述的列标签直接取自 `workbench_batch_file.HEADERS`。

3. **失效路径字面量棘轮**（`tools/scan_dead_path_literals.py` + `tests/gate_meta/test_dead_path_literals.py`）
   进日常门禁的 focused 无条件车道。它抓的是"文件删了、引用它的字符串还在"，删除发生在哪个目录
   事先不知道，按影响面选组必然漏（2026-09-18 删旧路由层就漏了）。本轮它两次抓到真问题：
   一次抓到剪裁一致性脚本时还掉的 5 笔债，一次抓到测试夹具里指向已删交付文件的样例路径。
   **条目键是（源文件，失效字面量）两元组**，所以"改好一个、又写坏一个"仍然会红。

4. **实现一致性对标脚本剪裁后 pytest 化进门禁。** `tests/gate_meta/generate_conformance_report.py`
   739 → 417 行，新增 `tests/gate_meta/test_conformance_report.py` 进 focused 无条件车道。
   它以前只能人工敲命令跑，所以长期红着没人知道：第一次跑出 1 BLOCKER + 6 MAJOR，没有一条是
   实现真的出问题。删 5 项（甘特静态资源、关键路由、模板目录随对象消失；文件行数与债务台账重复；
   排产落库留痕的 167 行 AST 匹配与行为测试重复——`action=simulate/schedule` 在
   `test_scheduler_graph_operation_logs_contract.py:324`，同事务写入与整体回滚在
   `tests/candidate/test_scheduler_candidate_persistence_contract.py`），
   改指 2 项（退出备份三要件现在跨 `factory.py` 与 `launcher_shutdown.py`；排产默认值常量挪进
   `config_constants.py`）。
   **以后写这类检查，优先写行为测试，不要写实现结构的 AST 镜像**——它只会在下次重构时误报。

5. **Schema 表文档化改成棘轮。** 77 张表里 53 张在开发文档和速查表里都搜不到，这是真实文档缺口，
   不是检查陈旧，一次补齐要单独立项。欠账清单落在
   `.codestable/checkup/undocumented_tables_baseline.txt`：新建表没写文档会红，补完文档没从
   清单里划掉也会红，只能减不能增。**不要把新建的表加进清单。**

6. **浏览器运行时默认路径挪出 `/tmp`。** `scripts/run_workbench_opt_in_browser.py` 的默认
   Chromium 路径原先写死在 `/tmp/aps-chromium109-assessment/`，而 macOS 每日清理会把它掏空——
   代码注释里已经写明这一点，却还把默认值指在那儿，于是车道每次都以"运行时缺失"退出，
   看着像环境问题。改成先找 `~/.cache/aps-chromium109-assessment/stage/` 下的常驻副本，
   找不到时报错直接给出解压与去隔离属性的命令。

7. **删掉 7 个全仓库零引用的测试支撑脚本**（480 行）。它们存在的唯一理由是被测试 import，
   现在没人 import，只在 `.codestable` 历史文档里被提到（不算活引用）。
   `final_master_visual_index_support.py` 同样零引用，但被 `.gitignore:289` 单独点名忽略，
   是有意排除的，没动。

8. **浏览器车道的执行机制定为 pre-push 轮转抽样**（用户裁决）。2026-09-17 建起车道后，
   没有任何 CI workflow 或定时任务引用 `scripts/run_browser_test_lane.py`，"每周至少跑一次"
   只写在文档里；09-17 的裁决文档自己最后一行就写着"浏览器车道本机缺 Chromium 109 未实跑"。
   `test_frontend_ui_language_polish.py` 那 17 条用例烂了三天没人发现就是这么来的。
   现在 `tools/browser_lane_sample.py` 进 pre-push（`.pre-commit-config.yaml` 最后一个钩子），
   默认每次抽 2 个文件（实测约 80 秒），130 个文件约 65 次 push 覆盖一圈。
   **必须是轮转不是随机**：随机会让某些文件长期抽不到，也不可复现；轮转语义由
   `tests/gate_meta/test_browser_lane_sample.py` 锁住。
   游标写在 `evidence/browser-lane/sample-cursor.json`——**不能放进版本控制**，
   pre-push 写一个被跟踪的文件会弄脏工作区，把要求干净树的门禁卡死。
   本机没准备 Chromium 109 时抽样跳过而不拦 push（开发机不一定装运行时，拦下来只会逼人绕过钩子），
   但会往 stderr 喊出解压命令。整条车道仍用 `scripts/run_browser_test_lane.py` 手动跑。

## 未做与待裁决
- **"车道纯度门禁"不建。** 原计划要建一道门禁盯"车道文件里混进不需要浏览器的用例"，
  实测推翻了前提：静态判定说 `test_final_execution_chain.py` 8/8 都"不碰浏览器"，
  实跑 152 秒、要起 live server，因为它们通过 fixture 拿 server，源码里看不见关键词。
  严格判定下全车道只剩 4 个单发轻量用例，分散在 4 个文件里各 1 个。
  `test_frontend_ui_language_polish.py` 那种 17/19 的高比例混装是孤例，为它建常设门禁
  属于过度工程。**判断"哪些用例被误踢"必须实测耗时，不能只看静态特征。**
- **"执行器登记门禁"不建。** 原计划假设 `tests/_scripts_e2e/` 下的手工脚本已经烂掉，
  实测 25 个脚本语法与 import 全部有效；把范围放大到 tests/ 下全部 304 个非用例脚本，
  同样 0 问题。真正的孤儿是上面第 7 条那 7 个死支撑脚本，已删。
- `EXCEL_TEMPLATE_DIR` 配置的存废没动：`factory.py:213` 仍在运行时目录下现建空
  `templates_excel/`，但已经没人往里放文件、也没人读。属于 bootstrap 层的事，另议。
- `开发文档/` 下的实现计划表、阶段留痕、审查提示词仍提到已删的
  `unit_excel_converter.py`：它们是历史记录性文档，记录当时状态，不改。
  现状参考性的开发文档 11.5.3 与系统速查表两处已改。

## 验证

- 受影响面 `tests/excel_data_io` + `tests/gate_meta` + 批次/表描述/文案：1454 passed；
  三处因删 `templates_excel/**/*` 范围连锁失败的已修，复跑 297 passed。
- 失效路径棘轮 153 条目 / 256 处；实现一致性对标 7 项 0 差异；
  `tests/workbench` + `tests/excel_data_io` collect-only 9016 例无 import 断裂。
- 门禁能抓到偏移的实证：把 `backup(suffix="exit")` 改成 `suffix="shutdown"`，
  一致性门禁如期变红，还原后恢复绿。
- 拆出的 `test_frontend_ui_language_polish_browser.py` 真机 2 passed
  （Chromium 109.0.5414.46）。
- ruff 全绿。未跑正式全量门禁（用户明令只跑定向测试）；浏览器车道整体实跑结果见会话汇报。

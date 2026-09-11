# 私有 Factory 验收入口

统一入口为 `source_binding.py capture/check`，运行守卫为 `source_guard.FrozenSourceGuard`。所有应用代码从完成复制/打patch后的私有源码导入；harness也复制到同一私有根，不能把 Main 当隐式 sys.path 回落。

## 顺序

1. 新建唯一的 `/tmp/aps-g-retirement-candidate-XXXXXX` 根；`source/` 为candidate，`baseline/`为同一未打patch源码，`harness/`放本目录Python文件。
2. 用宿主Python3.14静态capture。自动发现非运行数据目录中的所有Python根，连同本地资产/测试，拒绝symlink；另外显式加入下面5项运行/测试事实源。它不是任意动态资源引用的完备推断器。
3. 用生成的 `.files` 清单 rsync。必须等复制进程结束，并执行 `check`；任何失败立即停止，不能继续apply。核对全部patch preimage后，用apply_patch只改私有source，再核对postimage。
4. 从两份最终源码分别capture manifest，记录上游来源/继承关系。测试前后均验证文件SHA与mode；不得修改正在使用的源码或harness。改动后新建绑定/运行名，保留失败回执。
5. runtime使用原Python3.8依赖；`FactoryCase` 把DB、日志、备份、模板、journal、HOME、TMPDIR全设为私有运行目录，再调用真实app/create_app。candidate显式安装 `install_legacy_retirement`；不设TESTING，不伪造flash。
6. 不把只检查已加载的core/data/web/tests当闭包。守卫检查全部 `__file__`、namespace路径、自定义模块别名；原checkout非依赖文件读取、越界写、外连和子进程都拒绝。
7. 正常pytest需要原 `tests/conftest.py` 及治理台账；不以 `--noconftest`、xfail、基线更新绕过缺项。pytest日志写私有runtime而非默认 `/dev/null`。

## 必需事实源

本次capture使用这些额外文件，调用方式为每项一个 `--extra`：

- `.codestable/roadmap/workbench-prototype-migration/workbench-capabilities.json`
- `.codestable/roadmap/workbench-prototype-migration/legacy-option-disposition.md`
- `.codestable/checkup/import_cycles_production_baseline.json`
- `.codestable/checkup/import_cycles_with_tests_baseline.json`
- `开发文档/技术债务治理台账.md`

增加被测路径时如守卫报缺文件，应明确加入原文件并新建快照，而不是从Main补读。根 `common/` 在本仓库不存在；实际共享代码在 `core/services/common/`，一直是静态盘点内容。

## 已验证脚本

- `run_factory_imports.py ROOT candidate|baseline --manifest ... --run UNIQUE`：12组实际preview/confirm/拒绝/刷新/回读/模板与导出，逐worker保存状态、HTML、文件与日志。
- `run_factory_matrix.py ROOT candidate|baseline --manifest ... --run UNIQUE`：51页面+39非页面GET/HEAD、113空表单POST。后者不是113条完整交易。
- `factory_report_worker.py SOURCE RUNTIME [--candidate]`：报表日期边界、实际打印身份/范围与手册字节。
- `factory_messages_worker.py SOURCE RUNTIME normal|invalid-navigation|missing-assets`：真实设备提交→旧GET→canonical消息，只消费一次；不证明浏览器显示。
- `frozen_pytest_worker.py SOURCE RUNTIME TEST...`：保留正常conftest；读/写/模块路径受守卫约束。
- worker须设置 `FACTORY_SOURCE_MANIFEST` 为对应绝对manifest路径；运行目录必须位于同一私有根的 `runs/UNIQUE`。来源和脚本的SHA应进入本轮交接。
- 正式循环扫描使用 `python -B -m tools.scan_import_cycles --fail-on-new-cycle`，含tests再加 `--include-tests`；从私有源码、限定sys.path运行，保留两个旧baseline，不传update-baseline。

F交付完整匹配构建后，先验证manifest全部源input及产物hash，再放入新的绑定快照做浏览器。服务器/浏览器是下一项单独验收，不能由这些HTTP脚本的passed替代。

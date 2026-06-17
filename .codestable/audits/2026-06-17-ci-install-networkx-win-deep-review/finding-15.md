# Finding 15：Excel 模板自动生成/修复绕过固定文件安全写入

- 优先级：P1 阻塞
- 结论：固定名运行文件安全只覆盖了部分文件。Excel 模板自动生成和修复仍直接对固定模板路径 `open(..., "wb")` / `wb.save(path)`，可以写穿同名软链接。

## 根因

本分支已经引入 `core/infrastructure/safe_files.py`，并在架构文档里把固定名运行文件安全作为全局约束。但 Excel 模板目录也是固定名交付目录，模板文件名也是固定名单，启动时会自动补齐和修复。这里没有走 safe_files，也没有 `lstat` 拒绝软链接。

大白话说：一部分“固定名字文件”已经走安全门了，但 Excel 模板还在从旁边小门直接写文件。

## 调用链

- Flask app 启动
- `web/bootstrap/factory.py::_init_excel_templates()`
- `core/services/common/excel_templates.py::ensure_excel_templates()`
- 缺模板时 `_write_xlsx(path, ...)`
- 旧模板需要修复时 `_refresh_existing_template_headers()` 或 `_refresh_existing_template_layout()`

## 证据

- `web/bootstrap/factory.py:228-232`：启动初始化调用 `ensure_excel_templates()`。
- `web/bootstrap/factory.py:325-326`：蓝图装配前执行 Excel 模板初始化。
- `core/services/common/excel_templates.py:145-155`：`_write_xlsx()` 直接 `open(path, "wb")`。
- `core/services/common/excel_templates.py:352-367`：修复表头后直接 `wb.save(path)`。
- `core/services/common/excel_templates.py:377-394`：修复布局后直接 `wb.save(path)`。
- `core/services/common/excel_templates.py:447-480`：`ensure_excel_templates()` 发现文件不存在就写入固定模板名。
- 主线程只读复现：在模板目录放入同名 broken symlink 后，`os.path.exists(path)` 为 false，`open(path, "wb")` 会写到软链接目标，软链接仍存在，外部目标文件被创建。

## 影响

- 如果模板目录被放入同名软链接，启动自动补模板会写到链接目标。
- 这和本分支“固定名文件不能写穿软链接”的安全目标不一致。

## 建议

- Excel 模板固定路径写入和修复统一走 safe_files 的安全写入策略。
- 对模板目录下的同名软链接、硬链接、非普通文件增加回归测试。
- 启动模板初始化遇到 unsafe path 应明确失败，不要删除链接后重写，也不要静默跳过。

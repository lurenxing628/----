# 引用链追踪报告（深度 Review 辅助）

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## web/routes/equipment_pages.py（Route 层）

### `_build_linked_operator_rows()` [私有]
- 位置：第 22-36 行
- 参数：links, operators
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_build_available_operator_rows()` [私有]
- 位置：第 39-53 行
- 参数：operators, linked_operator_ids
- 返回类型：Subscript(value=Name(id='List', ctx=Load()), slice=Index(val

### `_selected_op_type_name()` [私有]
- 位置：第 56-58 行
- 参数：op_types, machine
- 返回类型：Name(id='Any', ctx=Load())

### `list_page()` [公开]
- 位置：第 62-134 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（32 个）：`bp.get`, `MachineService`, `OpTypeService`, `parse_page_args`, `load_team_options`, `build_team_name_map`, `svc.list`, `set`, `OperatorMachineQueryService`, `om_q.list_links_with_operator_info`, `paginate_rows`, `render_template`, `strip`, `strftime`, `MachineDowntimeQueryService`

### `create_machine()` [公开]
- 位置：第 138-158 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `get`, `MachineService`, `svc.create`, `flash`, `redirect`, `url_for`, `getattr`

### `detail_page()` [公开]
- 位置：第 162-204 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（25 个）：`bp.get`, `MachineService`, `OperatorMachineService`, `MachineDowntimeService`, `OpTypeService`, `OperatorService`, `m_svc.get`, `link_svc.list_by_machine`, `dt_svc.list_by_machine`, `load_team_options`, `build_team_name_map`, `_build_linked_operator_rows`, `_build_available_operator_rows`, `render_template`, `getattr`

### `update_machine()` [公开]
- 位置：第 208-227 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `get`, `MachineService`, `svc.update`, `flash`, `redirect`, `url_for`, `getattr`

### `set_status()` [公开]
- 位置：第 231-238 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（2 处）：
  - `web/routes/personnel_pages.py:168` [Route] `op = svc.set_status(operator_id=operator_id, status=status)`
  - `web/routes/personnel_pages.py:202` [Route] `svc.set_status(oid, status=status)`
- **被调用者**（10 个）：`bp.post`, `get`, `MachineService`, `svc.set_status`, `flash`, `redirect`, `ValidationError`, `url_for`, `getattr`, `_machine_status_zh`

### `delete_machine()` [公开]
- 位置：第 242-249 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.post`, `MachineService`, `redirect`, `svc.delete`, `flash`, `url_for`, `getattr`

### `bulk_set_status()` [公开]
- 位置：第 253-280 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（15 个）：`bp.post`, `strip`, `getlist`, `MachineService`, `flash`, `redirect`, `ValidationError`, `join`, `url_for`, `getattr`, `svc.set_status`, `get`, `failed.append`, `len`, `str`

### `bulk_delete()` [公开]
- 位置：第 284-308 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（12 个）：`bp.post`, `getlist`, `MachineService`, `flash`, `redirect`, `join`, `url_for`, `getattr`, `svc.delete`, `failed.append`, `len`, `str`

### `add_link()` [公开]
- 位置：第 312-317 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（1 处）：
  - `web/routes/personnel_pages.py:247` [Route] `svc.add_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（8 个）：`bp.post`, `get`, `OperatorMachineService`, `svc.add_link`, `flash`, `redirect`, `url_for`, `getattr`

### `update_link()` [公开]
- 位置：第 321-333 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `get`, `OperatorMachineService`, `svc.update_link_fields`, `flash`, `redirect`, `url_for`, `getattr`

### `remove_link()` [公开]
- 位置：第 337-342 行
- 参数：machine_id
- 返回类型：无注解
- **调用者**（1 处）：
  - `web/routes/personnel_pages.py:273` [Route] `svc.remove_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（8 个）：`bp.post`, `get`, `OperatorMachineService`, `svc.remove_link`, `flash`, `redirect`, `url_for`, `getattr`

---
- 分析函数/方法数：14
- 找到调用关系：4 处
- 跨层边界风险：0 项

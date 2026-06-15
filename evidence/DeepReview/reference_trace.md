# 引用链追踪报告（深度 Review 辅助）

> 说明：本报告基于 AST 提取“定义”，并用文本搜索定位“调用点/被调用者”。
> 由于 Python 动态特性与启发式匹配限制，可能存在漏报/误报，仅作为审查线索。
> 建议：对每条调用关系回到源码上下文手工核对。

## web/routes/personnel_pages.py（Route 层）

### `list_page()` [公开]
- 位置：第 22-85 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（32 个）：`bp.get`, `OperatorService`, `MachineService`, `parse_page_args`, `load_team_options`, `build_team_name_map`, `list_simple_rows`, `link_rows.sort`, `paginate_rows`, `render_template`, `strip`, `op_svc.list`, `machines.get`, `append`, `links_by_operator.get`

### `create_operator()` [公开]
- 位置：第 89-103 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `get`, `OperatorService`, `svc.create`, `flash`, `redirect`, `getattr`, `url_for`

### `detail_page()` [公开]
- 位置：第 107-112 行
- 参数：operator_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（4 个）：`bp.get`, `build_personnel_detail_context`, `render_template`, `getattr`

### `update_operator()` [公开]
- 位置：第 116-125 行
- 参数：operator_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `get`, `OperatorService`, `svc.update`, `flash`, `redirect`, `url_for`, `getattr`

### `set_status()` [公开]
- 位置：第 129-136 行
- 参数：operator_id
- 返回类型：无注解
- **调用者**（2 处）：
  - `web/routes/equipment_pages.py:274` [Route] `m = svc.set_status(machine_id=machine_id, status=status)`
  - `web/routes/equipment_pages.py:309` [Route] `svc.set_status(mid, status=status)`
- **被调用者**（10 个）：`bp.post`, `get`, `OperatorService`, `svc.set_status`, `flash`, `redirect`, `ValidationError`, `url_for`, `getattr`, `_operator_status_zh`

### `delete_operator()` [公开]
- 位置：第 140-147 行
- 参数：operator_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（7 个）：`bp.post`, `OperatorService`, `redirect`, `svc.delete`, `flash`, `url_for`, `getattr`

### `bulk_set_status()` [公开]
- 位置：第 151-185 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（17 个）：`bp.post`, `strip`, `getlist`, `OperatorService`, `flash`, `redirect`, `ValidationError`, `join`, `url_for`, `getattr`, `svc.set_status`, `get`, `failed.append`, `failed_details.append`, `exception`

### `bulk_delete()` [公开]
- 位置：第 189-220 行
- 参数：无
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（14 个）：`bp.post`, `getlist`, `OperatorService`, `flash`, `redirect`, `join`, `url_for`, `getattr`, `svc.delete`, `failed.append`, `failed_details.append`, `exception`, `len`, `str`

### `add_link()` [公开]
- 位置：第 224-229 行
- 参数：operator_id
- 返回类型：无注解
- **调用者**（1 处）：
  - `web/routes/equipment_pages.py:367` [Route] `svc.add_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（8 个）：`bp.post`, `get`, `OperatorMachineService`, `svc.add_link`, `flash`, `redirect`, `url_for`, `getattr`

### `update_link()` [公开]
- 位置：第 233-246 行
- 参数：operator_id
- 返回类型：无注解
- **调用者**（0 处）：
  - （无外部调用者）
- **被调用者**（8 个）：`bp.post`, `get`, `OperatorMachineService`, `svc.update_link_fields`, `flash`, `redirect`, `url_for`, `getattr`

### `remove_link()` [公开]
- 位置：第 250-255 行
- 参数：operator_id
- 返回类型：无注解
- **调用者**（1 处）：
  - `web/routes/equipment_pages.py:392` [Route] `svc.remove_link(operator_id=operator_id, machine_id=machine_id)`
- **被调用者**（8 个）：`bp.post`, `get`, `OperatorMachineService`, `svc.remove_link`, `flash`, `redirect`, `url_for`, `getattr`

---
- 分析函数/方法数：11
- 找到调用关系：4 处
- 跨层边界风险：0 项

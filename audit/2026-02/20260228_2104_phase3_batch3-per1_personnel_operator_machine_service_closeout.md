## Phase3 / Batch3-Per1 留痕：Personnel OperatorMachineService（分层修复 + Excel 关联链路闭环）

- 时间：2026-02-28 21:04
- 目标：闭环人员-设备关联（OperatorMachine）服务的 Excel 导入链路：消除 Service 层直连 SQL、降低 `preview/apply` 圈复杂度到门禁阈值内，并将 `yes/no` 口径收敛到 `YesNo.*.value`，保证 Route→Service→Repo 分层一致。
- Schema 变更：无
- 开发文档回填：未触发（未新增/删除 Route；未变更模板列名/用户可见文案）

### 影响域（实际改动文件）

- `data/repositories/operator_machine_repo.py`
  - 新增 `delete_all()`：供 Excel REPLACE 模式清空关联使用，避免 Service 层执行 `DELETE FROM ...`。
- `core/services/personnel/operator_machine_service.py`
  - `preview_import_links/apply_import_links` 读取现有关联改为调用 `OperatorMachineRepository.list_simple_rows()`；
  - REPLACE 清空改为调用 `OperatorMachineRepository.delete_all()`；
  - 将 Excel 预览/落库逻辑拆分为若干私有 helper，确保：
    - **圈复杂度门禁**不新增超标函数
    - **单文件 500 行门禁**仍满足（通过压缩签名/调用的纵向展开，保留语义不变）
  - `主操设备` 的解析与判断统一使用 `YesNo.YES/NO.value`（字符串落库保持 `yes/no` 不变）。

### 结果与证据

- **Smoke（Personnel/关联导入链路）**
  - `python tests/smoke_phase3.py`：OK；产物：`evidence/Phase3/smoke_phase3_report.md`
  - `python tests/smoke_phase4.py`：OK；产物：`evidence/Phase4/smoke_phase4_report.md`
- **Architecture Fitness**
  - `python -m pytest tests/test_architecture_fitness.py -v`：9 passed
- **Conformance**
  - `python tests/generate_conformance_report.py`：OK；产物：`evidence/Conformance/conformance_report.md`

### 下一步（按计划）

- 继续 Phase3：进入 Equipment 域（`machine_downtime_service.py` 状态枚举与边界条件回归），完成本阶段 Process→Personnel→Equipment 的闭环。


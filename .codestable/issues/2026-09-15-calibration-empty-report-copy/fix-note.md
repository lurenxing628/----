---
doc_type: issue-fix-note
status: fixed
date: 2026-09-15
scope: calibration sample and export wording
---

# 校准缺报工与采用说明修复

- 手动现场：5005 的 CALIB-0915-01 至 05 尚无逐次报工，详情却显示“至少有一次报工的数量暂无数据”；同次手动导出的 `工时校准明细-2026-09-15T215721.xlsx` 仍写“采用与锁定：此功能尚未开通。”
- 根因：`calibration_samples._known_sum([])` 与“已有记录但字段缺失”都返回 `None`，后续未区别无记录；XLSX 元数据及只读模型仍沿用采用功能接入前的固定提示。
- 修复：无逐次报工只给出“尚无逐次报工记录，暂不能计算单件工时”，合并由无报工派生的数量、完工时间等重复原因；模板来源、历史暂停/异常与来源漂移检查继续保留。有报工但数量或工时未填时仍按真实缺口解释。
- 修复：XLSX 说明改为“请在工时校准页面预检并采用；采用后更新并锁定模板定额，已有批次不随之更改。”只读模型改为先预检提示，保留只读能力与空写入令牌；实际采用服务未接入时的错误保留。CSV 没有采用状态字段，已核查；当前 UI 已有正确的预检入口，无需改前端。
- 范围：本次仅改 `core/services/workbench/calibration_samples.py`、`core/services/workbench/calibration_export.py`、`core/models/workbench_calibration.py`，并在已有 `test_calibration_method.py`、`test_calibration_routes.py` 增补回归。
- 验证：新断言先复现 4 处失败；修复后校准方法文件和定向读取/CSV/XLSX测试共 37 项通过（4.98 秒）；实际采用预检/确认/回执与样本阈值专项另 5 项通过（1.68 秒），共 42 项。覆盖无报工、只有旧完工事件、数量/工时缺失、零数量、未全部完工、模板来源、至少 5 条、最多最近 20 条与中位数规则。`git diff --check` 指定本次 5 个代码/测试文件通过。
- 限制：未操作浏览器或业务数据库，未构建、未跑全门禁或整仓测试；浏览器重新读取与下载复核由主任务继续。既有 dirty 改动保留，没有提交。

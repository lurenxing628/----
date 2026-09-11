# 最终 Apply 小清单

日期：2026-09-11。**仅准备，未apply、未安装dispatcher、未删除资产、未起host。** HEAD只读核对为 `0cab59b6970a86393f610a2838feed9efc7523b2`。17尚未完成；以下不是执行许可，也不替B的252或E/D/F验收。

## 底本与执行顺序

- 产品底本是Main批准的 E `/private/tmp/aps-final-e-sealed-read-after-20260911-06/source`，aggregate `2d6c6f12a3b2496d791cd9eb6f846b4dd26260facc334d568a68166561cff1d5`；manifest SHA `ba451495b7edf2382794236913f3ab3b58574b75a5734e5af7218c957e390ce4`。G只核对本清单命中的文件，不重新审6532文件。
- 对应完整构建是该根的 `reentry-final-01/full-build/static/workbench`，manifest SHA `09f624979b2d9db12fa527ad4c62f610d61a7709d2da9df34732ab4840848b66`。G不改其315输入、223产物，不回拷V4旧构建。
- Main完成G05/17并明确授权后，重新核对 [manifest.json](manifest.json) 的全部before SHA及13个现有前提文件。任何漂移停止，不强制覆盖。HEAD本身不等于已含G05的完整产品底本。
- A：应用原24目标呈现patch；B：同一停服应用窗口接factory两处显式安装，不能在A/B半套状态启动。合计 **17修改+8新增=25路径**，无core/schema/前端改动。
- 先在新私有完整副本上完成 [定向回归](regressions.md)。再经Main确认进入C：删除枚举的124个旧UI文件并重新绑定源码/回归。**本次实际删除为0。**

## 25个真实产品目标

完整SHA、payload来源、回退文件与124条删除记录全部在 [manifest.json](manifest.json)；下表仅将SHA缩为12位方便扫读，`ABSENT`要求文件确实不存在。

| 动作 | Path | 旧SHA | 新SHA |
| --- | --- | --- | --- |
| 修改 | `web/routes/excel_demo.py` | `f1211ec554f8` | `54c34cc1c7c1` |
| 修改 | `web/routes/personnel_excel_links.py` | `72dce5664c30` | `82d3f8f6bcb5` |
| 修改 | `web/routes/personnel_excel_operator_calendar.py` | `812dba8731cc` | `e482f358b1e4` |
| 修改 | `web/routes/personnel_excel_operators.py` | `4e1bd6b2a7d7` | `2a9a36aed974` |
| 修改 | `web/routes/equipment_excel_links.py` | `857f1cf5e868` | `d5a2493d3770` |
| 修改 | `web/routes/equipment_excel_machines.py` | `183121af2cd6` | `43b1828ea39c` |
| 修改 | `web/routes/process_excel_op_types.py` | `bf625e474eb5` | `34ed34a73c19` |
| 修改 | `web/routes/process_excel_part_operation_hours.py` | `1808dc248f66` | `6407fedcbb8e` |
| 修改 | `web/routes/process_excel_routes.py` | `fb269c8ca9e0` | `df2e73a498be` |
| 修改 | `web/routes/process_excel_suppliers.py` | `4c8497fb1387` | `d5e1958dfdf3` |
| 修改 | `web/routes/domains/scheduler/scheduler_excel_batches.py` | `b65242bdc84d` | `f7f5070be43e` |
| 修改 | `web/routes/domains/scheduler/scheduler_excel_calendar.py` | `4c8fb478cae9` | `7097e502f656` |
| 修改 | `web/routes/domains/scheduler/scheduler_week_plan_print.py` | `aec072d0e1de` | `162124a242f6` |
| 修改 | `web/routes/domains/scheduler/scheduler_config.py` | `e74a3ea4c9ff` | `d0d0e0033ed2` |
| 修改 | `templates/error.html` | `98edd2658436` | `7bfdfe62329d` |
| 修改 | `templates/error_base.html` | `094c166f063b` | `04519caa2050` |
| 新增 | `templates/workbench/legacy_base.html` | `ABSENT` | `e2c31bd7ed39` |
| 新增 | `templates/workbench/legacy_result.html` | `ABSENT` | `fd60a1987b21` |
| 新增 | `templates/workbench/legacy_style.html` | `ABSENT` | `94063dd7f60f` |
| 新增 | `templates/workbench/manual.html` | `ABSENT` | `86f0a1c492eb` |
| 新增 | `templates/workbench/print.html` | `ABSENT` | `b53520121870` |
| 新增 | `templates/workbench/retired.html` | `ABSENT` | `d795b4fe5902` |
| 新增 | `web/routes/workbench/legacy_dispatch.py` | `ABSENT` | `cf3f34697701` |
| 新增 | `web/routes/workbench/legacy_presentation.py` | `ABSENT` | `4752cbcdacbf` |
| 修改 | `web/bootstrap/factory.py` | `1f3cad743e9f` | `e36dfb773dc2` |

## 补丁来源

- A使用原封存 [candidate-review.patch](../candidate-review.patch)，SHA `a6c1a20dce70b241046b09ecfcd349fd7c8dddb7a6f00ee0ea644d916fabd0e2`；index SHA `8e4fbad3b665f3e81be9fb6835df31ebaec2d90acc74b4f32a323cc0b29106fa`。24个preimage在当前Main和sealed06均相符，postimage与V4实测源码相符。
- 14个旧renderer只改模板字符串；其余10个新增/错误呈现payload精确位于 `../draft-payload/<目标path>`，逐文件hash在JSON。V4/source只作这24个postimage的对照来源，**不复制整棵candidate**。
- B使用 [mount.patch](mount.patch)，SHA `0cca58fd3d7853a70c6196db1c8d9c8ffb0ba36f90c95e68c6318fc7825ef1b3`：factory原39行前增加顶层installer import、原252行最后一个blueprint后增加一次调用。factory `1f3cad743e9f89504cc8bf6719eef700ef5424217c9e87f1f4ffa1a4150a26c8` → `e36dfb773dc236de7fe2dbf820cdd23c17e3284e608e490443cf2742a6d798bf`；后者只是内存推导并通过3.8语法解析，未运行。
- C使用 [retire-assets.patch](retire-assets.patch)，SHA `97e9592afb8036d2bcf997ba20540a88d46979b200845d2f8fa941e0627b4888`。它不会自行校验SHA，必须先核对JSON全部删除preimage；124条与当前Main、sealed06和原资产矩阵全部相符。禁止递归删除templates/static目录。
- 已有13个G辅助/测试文件在Main与sealed06一致，归G05现有产品前提，**不重复覆盖**；也不重放 `task-origin-overlay.patch`。

## 冲突行与保留资源

- **真实版本差异**：`navigation_boot.py:148`的task_origin新函数及165行分派、`test_final_navigation_boot.py`新增8测试不在V4中；`build-order.json:17`新增 `PlanProcessOrder.js` 在 `PlanContract.js` 前。覆盖V4会丢失D的新协议/加载依赖。这些path均不在本次apply中。
- **无当前字节冲突但必须保护**：`pages.py:62`的nav解析、73行navigation、74行flash消息、77行enabled_views；`main.jsx:15/65/78/136`消息消费；`WorkbenchNavigation.js:29`boot一致性；`unavailable.html:23`原flash消费。当前与V4字节相同，不虚构冲突、不再改写。
- 68个旧HTML分为：54个仅页面/组件、12个仍服务24条POST的结果模板、1个旧打印、1个旧手册。**只改GET适配器不足以删除后14个**，必须先完成A中的对应renderer替换并通过真实回归。
- 56个旧静态文件为9 CSS、45 JS、2 SVG；其中 `static/css/00-tokens.css`、`static/css/print.css` 在原打印仍有效时保留。其余也要等旧引用和入口退役。枚举集与sealed06构建inputs/outputs/dependencies交集为0，这只是清单证据，不代替HTTP/浏览器负向检查。
- 始终保留两份 `static/docs/*.md` 原说明书、真实 `EXCEL_TEMPLATE_DIR` 工作簿及导入/导出/上传文件、39非页面GET和113POST的业务实现、新print/manual/results/templates/error呈现、`workbench/index/recovery/unavailable`、E/D/F新前端及最终 `static/workbench/**`。本清单不清理DB、journal、日志、缓存或.DS_Store。

## 回退指针

- 17个修改和124个删除的逐文件preimage均指向 **sealed06/source/<path>**，SHA在JSON；V4/baseline只作字节相同的旧入口备份佐证，不能回退Main的pages/build-order/nav或整棵源码。
- 回退修改时先确认活文件仍等于本次postimage，再恢复对应preimage；新增8文件仅在postimage未被后续修改时移除。factory优先反向撤销两处hunk，不用整文件覆盖后来改动。
- **数据回退不随UI回退自动发生**。本轮没有创建/读取真实库保护备份，真实D1备份指针明确为null。执行前由Main记录一致性DB/WAL/SHM、journal和业务文件的实际备份路径与SHA；回退UI代码仍保留运行中新产生的D1记录。V4/E/B的fixture数据库不是生产恢复点。
- 真正需要另行数据恢复时，先保护当前最新数据，再走既有 `core/infrastructure/backup.py:238` / `core/services/system/backup_restore.py:19` 恢复与校验链；不得拿旧D0库覆盖新增事实。本次未执行回退。

Win7、package、release仍未做，但按本轮明确排除，**不列为本清单阻断项**。

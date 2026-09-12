---
doc_type: feature-design
feature: 2026-09-12-wbui-format-module
status: approved
summary: 提供严格区分工厂本地文本与带时区时刻的统一显示格式，保留未知与非法输入边界。
tags: [workbench, formatting, ui]
roadmap: workbench-ui-refinement
roadmap_item: wbui-format-module
---

# 统一显示格式

## 0. 术语与依据

工厂本地文本是无时区的业务日期时间，显示时不做时区转换。时刻是带 `Z` 或 `±HH:mm` 的 ISO 日期时间，显示为当前机器的本地时间。依据为路线图 `implementation-20260912.md` 第 2 条批准修订。

## 1. 目标与范围

新增无依赖的 `window.WorkbenchFormat`，供各工作区消除重复显示格式。复杂度为共享前端纯函数；不改变业务日期存储、排序、时间轴计算或领域 API。用户已授权整条路线图并行实施，消费者由对应 owner 接入。

## 2. 接口、流程与挂载点

现有页面各自 `replace('T', ' ')` 或 `toLocaleString`，空值与精度不一致。统一接口：

- `dateTime(value, {seconds=false})`：严格校验 `YYYY-MM-DD[T或空格]HH:mm[:ss[.小数]]`，输出 `YYYY-MM-DD HH:mm[:ss]`。
- `date(value)`：接受有效 `YYYY-MM-DD` 或上述本地日期时间，只输出日期。
- `instant(value, {seconds=false})`：要求完整有效 ISO 时间及 `Z`/`±HH:mm`，转换至本机后用统一年月日格式显示。
- `number(value, {digits=1})`：有限数值的中文千分位和固定小数；`percent(ratio,digits=1)` 接受有限比值并乘 100 显示百分数，允许合法超负荷或负差值；取值范围由各领域原有 DTO 合同限制；`hours(value,digits=1)` 显示数值与 ` h`。
- `integerText(value)`：专供已有 DTO 的 canonical 非负整数字符串，逐组三位添加千分位，不经 Number 转换；例如 `9007199254740993` 显示 `9,007,199,254,740,993`。前导零、正负号、小数和科学计数法明确拒绝。
- 全部接口仅 `null`、`undefined`、空串输出“未知”；其他非法值抛 `TypeError`。精度必须为 0..20 整数；不强制把数值字符串转成数值。

流程：DTO 已有数据 → 消费者按时间语义选接口 → 严格校验 → 显示文本；非法合同由既有工作区错误边界显式承接。

显示统一不改写领域编码：时间轴保留工厂时间的数值坐标和`wire`编码，刻度先经共享显示函数再按原来的短日期、换行和秒数精度排版；平均分钟偏差保留原来的取整规则。日历用于输入往返、dirty比较和原始配置核对的canonical数值文本保留原精度（例如`8.375`不能变为`8.4`）；日期选择器的月份、时分秒/毫秒、min/max原输入边界也继续使用对应控件格式。这些用途不通过通用固定小数显示函数重新编码。

挂载点为构建清单中全部消费者之前的 `WorkbenchFormat.js`。例如 `dateTime('2026-09-12T08:03:09')` 为 `2026-09-12 08:03`；上海时区 `instant('2026-09-12T00:03:09Z')` 同样为 `2026-09-12 08:03`。

## 3. 验收契约

- 工厂时间在上海、UTC 和纽约三种时区下显示不漂移；真实时刻按本机转换。
- 日期包含闰年、月底、分钟与秒数范围校验；非法日期不可被 Date 自动归一化。
- 空值、零值、负值、比值、非有限数值和非法精度明确区分。
- 公共合同独立测试通过；各域接入、统一构建、浏览器和总门禁证据由主线程合并，不提前标记完成。

## 4. 文档与验证边界

此 feature 的 design/checklist/acceptance 仅记录共享层及明确消费接入。工作区已有调度优化修改；不得提交或覆盖他人的状态，不能声称 clean-worktree proof。

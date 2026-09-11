---
doc_type: acceptance-evidence
status: interrupted
date: 2026-09-10
scope: immutable historical attempt, not final acceptance
---

# 中断尝试

## 结论

本次不是完整验收通过。Main 要求等待稳定窗口时，B 正常停止自有宿主并保留原目录；不复用此已标记失败的 fixture，不改写原始结果。

- 根目录：`/private/tmp/aps-final-foundation-B.xYPahs/aps-workbench-live-o424z_2k`。
- build_id：`69ab1c53713a21acffe9810a3311ddf79538d4adeb1f86955ef272c0463372d8`；215 files、307 inputs。
- manifest SHA-256：`e14d7a775c7a7110e78bc66e8ba4da9bde1847dde9838961917ca6086411ce59`。
- 源码前后变化为空；这只是 `unchanged_snapshot_not_final_HEAD`。
- 自有宿主 PID 64899 返回 0，`stopped=true`、`assets_unchanged=true`、`isolation_violations=[]`；没有执行重启矩阵。
- 原始浏览器报告有 21 cases、21 screenshots、23 次正常 production response，仅覆盖第一组合 1392x924-light。

## 分开归类

| 结果 | 实际证据 | 分类 |
|---|---|---|
| 14 项首屏通过、真实 current official caption 通过 | `foundation-browser.json` 的 first_view 和 catalog-official-caption | 局部成功，不外推 56 首屏 |
| 输入 CAT-B 后末值仅 B，甘特正文重复 6 份 | 5 个字符均有 trusted key；`real-typing-navigation-back-reload-FAILED.png/.txt`；后续显式刷新用例实际读值 B | 真实产品异常，已报告 Main |
| main/React 缺失注入未触发 | 旧 probe 只匹配无 query URL，实际脚本有 `?v=` | 测试缺陷，不是产品 boot fallback 失败 |
| malformed boot 可读失败及真实 reload 通过 | `malformed-boot` case | 单个故障恢复验证，不是业务成功 |
| workspace render 注入测试中页面关闭 | Main hold 后主动停止浏览器，未走完选择及注入 | 中断，不是产品渲染失败结论 |
| 一次 getResponseBody 缓存已驱逐 | 原 capture error 未带 URL | 采证失败；新 probe 记录 URL 并在导航前等待响应采集 |

输入异常的只读源代码嫌疑为 `frontend/workbench/app/PlanWorkspace.jsx:100-103`：delay 条件分析表、甘特、非 delay 分析表三处同层 key 均取 snapshot_ref。Main 已把三处不同 key 命名空间交 D 实施。B 未修改此产品文件；此记录本身不声称修复已通过新真实矩阵。

## 原始文件

- `foundation-result.json`：整体中断、构建、源码范围及正常宿主停止证据。
- `foundation-browser.json`：逐 case、真实响应、原 trusted key、分别记录的故障和普通错误。
- `screenshots/1392x924-light/real-typing-navigation-back-reload-FAILED.png` 和同名 `.txt`：输入后实际画面和重复正文。
- `foundation-responses/`：当次真实 API 响应。
- `sessions/`：当次宿主的 ready/final、运行时、行快照和隔离证据。

以上相对路径均基于本文件给出的历史 fixture 根目录，未复制或替换原始内容。

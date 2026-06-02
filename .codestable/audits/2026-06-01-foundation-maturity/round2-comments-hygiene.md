---
doc_type: audit
slug: foundation-maturity-comments-hygiene
scope: 第二轮 · 主控独立侦察的两个正交维度（注释名实/代码卫生），codemap 与模块 Agent 都不专门覆盖
summary: 全项目 docstring 覆盖率实测 + 代码卫生实测，结论是"代码很干净但几乎不自我解释"
status: current
created: 2026-06-02
last_reviewed: 2026-06-02
tags: [aps, audit, comments, docstring, hygiene]
depends_on: [foundation-maturity]
---

# 注释名实 与 代码卫生（主控独立侦察）

用脚本对全项目（core/web/data，不含 tests）做了量化，区别于 Agent 的语义判断。

## 一、注释/docstring 维度 —— 真问题：代码"很干净但很哑"

### 模块级 docstring 覆盖率（几乎为零）
| 层 | 有模块docstring | 总数 | 覆盖率 |
|---|---|---|---|
| scheduler | 7 | 128 | 5% |
| routes | 6 | 98 | 6% |
| services.other | 5 | 77 | 6% |
| viewmodels | 1 | 57 | 1% |
| models | 3 | 47 | 6% |
| scheduler.run | 0 | 37 | **0%** |
| repositories | 1 | 33 | 3% |
| algorithms | 2 | 32 | 6% |
| infra | 0 | 31 | **0%** |
| bootstrap | 1 | 26 | 3% |
| report | 1 | 13 | 7% |

### 函数级 docstring
- 公开函数/方法：**200/2183 = 9%** 有 docstring。
- 私有函数/方法：45/2677 = 1%。
- 全项目"设计意图/为什么/注意/避免/历史/兼容"类高价值注释：仅 71 处。

### 判断
这**不是**"注释写错了"（名实不符的注释很少），而是"注释根本不够"。后果在本项目尤其严重，因为：
1. 648 个模块单目录平铺，命名成族群但相似度高（resource_dispatch_support vs resource_dispatch_rows vs resource_dispatch_records），不读完不知道区别——而开头没有一句话 docstring。
2. 意图主要压在 `.codestable/` 外部文档里，而第一轮已发现外部文档一部分滞后 → 代码不自我解释 + 外部文档滞后 = 理解成本陡增。
3. 投入失衡：项目有 28 万行测试 + 2.3 万行门禁（钉住"行为"），但几乎没有注释（解释"意图"）。

### 整改方向（补，不是删）
- 优先给**单目录平铺、命名相似**的模块补一行模块级 docstring（scheduler 顶层 75 文件、resource_dispatch_* 14 个、gantt_* 13 个最该补）。
- 给**公开 service/viewmodel 入口函数**补 docstring（说清输入输出契约）。
- 不必追求私有函数全覆盖；重点是"开门见山说清这个模块/这个公开函数在干什么"。
- 可考虑做成轻量门禁：新增公开模块/函数要求模块级 docstring（避免再退化），但不强制回填全部历史。

## 二、代码卫生维度 —— 出乎意料地干净（校准用，多为好消息）
- **被注释掉的代码块（连续≥3行像代码的 #）：0 处**。
- **裸 print 调试残留：1 处**，且是 `web/bootstrap/launcher_observability.py:156` 故意写 stderr 的可观测性输出，非残留。
- 临时命名文件：第一轮已查，10 个命中全是正常业务词（backup/draft/template/copy），无 _v2/_tmp 垃圾。
- TODO/FIXME：全 core/web/data 仅 3 个。
- "临时/暂时"字样 98 处几乎全是面向用户的中文文案，非债务标记。

### 判断
"临时函数满天飞、调试残留遍地"的担忧**不成立**——这是高强度门禁+测试的正面成果。代码很干净。真正的债不在"脏"，而在"哑"（注释缺失，见上）和"半截迁移"（见主文档）。

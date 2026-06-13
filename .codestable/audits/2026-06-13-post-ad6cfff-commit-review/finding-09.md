---
doc_type: audit-finding
audit: 2026-06-13-post-ad6cfff-commit-review
finding_id: "maintainability-09"
nature: maintainability
severity: P2
confidence: medium
suggested_action: cs-refactor
status: resolved
---

# Finding 09：CSS token 守卫只锁住部分入口，暗色块和裸 hex 证据仍偏弱

## 速答

CSS token 单源化已经做了主干收口，`--ui-shadow-md` 的历史错值也已经修掉。剩余问题是守卫不够硬：亮色根变量锁得比较严，暗色块和裸 hex 主要靠数量红线，不能清楚证明“旧语义色不会从旁路回潮”。

## 关键证据

- `tests/web_pages/test_css_token_source_contract.py:56` — definitive colors 检查开始于 token 文件。
- `tests/web_pages/test_css_token_source_contract.py:59` — 亮色检查会先剥掉暗色块，所以锚守卫只对 light root 生效。
- `tests/web_pages/test_css_token_source_contract.py:70` — 暗色块测试只检查“纯 token 重赋值”。
- `tests/web_pages/test_css_token_source_contract.py:74` — 暗色块 offenders 只拦非 token 行，不拦旧语义 token 名在暗色块回潮。
- `tests/web_pages/test_css_token_source_contract.py:83` — 裸 hex 检查按文件数量冻结，不记录具体值和位置。
- `static/css/00-tokens.css:143` — 暗色块注释说明只重赋 token；当前内容没有明显错值，但守卫仍偏宽。

## 影响

这类问题短期不一定让页面马上坏，但它会让“单一真相源”保护网变薄。以后有人在暗色块补回旧语义色、或在其他 CSS 文件新增裸 hex，只要没超过数量红线，就可能漏过。

## 修复方向

可以补两类守卫：

- 暗色块禁止出现已经收编掉的旧语义 token 名，或要求暗色 token 也来自同一份明确锚表。
- 裸 hex 不只数数量，还记录允许值清单或允许位置清单，变动时能看到“哪个值从哪里冒出来”。

## 建议动作

建议走 `cs-refactor`，因为它主要是测试守卫和证据质量增强，不改变产品行为。

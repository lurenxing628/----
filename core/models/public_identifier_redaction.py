from __future__ import annotations

import re
from typing import Any

# Public / Diagnostics 边界(见 roadmap scheduler-global-optimizer 4.8)的内部标识脱敏单一真相源。
# 排产内部 id(op_id/node_id/candidate_key/source_table/scenario_id/各类内部 sample 等)只能进
# diagnostics,不得进入普通页面正文、普通 HTML、导出、导出文件名、OperationLogs 普通用户投影。
# 各 public 出口(optimizer/graph/excel/operation_log/趋势 attempts)统一引用本模块的 token 与
# redact 逻辑,不再各自手抄一份,避免清单漂移导致一处脱敏另一处漏。

REDACTED_INTERNAL_TEXT = "内部标识已省略"
REDACTED_INTERNAL_FIELD = "内部字段"

# 内部排产标识字段名:取各 public 出口禁用清单的并集(最全一份)。
# 这是兜底黑名单;各 public 投影自身仍保留白名单主防线,这里多禁无害、只会更严。
FORBIDDEN_INTERNAL_KEYS = frozenset(
    {
        "adopted_candidate_key",
        "attempts",
        "attempts_public",
        "baseline_best_candidate_key",
        "bottleneck_machine_ids_sample",
        "candidate_fingerprint",
        "candidate_id",
        "candidate_key",
        "critical_best_candidate_key",
        "critical_path_sample",
        "cycle_edges_sample",
        "from_node_id",
        "graph_score_sample",
        "matches_sample",
        "node_id",
        "node_metrics_sample",
        "op_code",
        "op_id",
        "raw_score_best_candidate_key",
        "schedule_id",
        "scenario_id",
        "selected_candidate_key",
        "source_table",
        "target_id",
        "to_node_id",
        "topological_order_sample",
        "unmatched_operation_ids_sample",
        "warnings_sample",
    }
)

# 内部调试容器名(并集)。
FORBIDDEN_INTERNAL_VALUE_TOKENS = (
    "adjustment_scenario_rows",
    "attempts_debug",
    "candidate_rows",
    "graph_debug",
    "graph_nodes",
    "resource_debug",
    "scheduler_candidate_selection",
    "top_level_debug",
)

OP_TOKEN_RE = re.compile(r"\bop:[^\s,;；，、)）\]}]+", re.IGNORECASE)
OP_CODE_TOKEN_RE = re.compile(r"\bOP[-_]?\d{2,}\b", re.IGNORECASE)
CANDIDATE_KEY_TOKEN_RE = re.compile(r"\b(?:graph_w\d+_of_\d+|baseline)\b", re.IGNORECASE)

_KEYS_ALTERNATION = "|".join(sorted(FORBIDDEN_INTERNAL_KEYS))
_VALUE_TOKENS_ALTERNATION = "|".join(re.escape(token) for token in FORBIDDEN_INTERNAL_VALUE_TOKENS)

_VALUE_TOKEN_RE = re.compile(r"\b(?:" + _VALUE_TOKENS_ALTERNATION + r")\b", re.IGNORECASE)

# 命中即判定"文本含内部标识"——用于 attempt / 趋势这类"含则丢弃 / 标记记录异常"场景。
# 注意:这里只认 graph_w 候选指纹形态,不认裸 "baseline" 单词——baseline 在候选标签里
# 是合法的"原算法方案"来源,只在 key:value 串或兜底 redact 时才抹掉。
INTERNAL_TEXT_RE = re.compile(
    r"\b(?:" + _KEYS_ALTERNATION + r")\b"
    r"|\bop:[^\s,;；，、)）\]}]+"
    r"|\bOP[-_]?\d{2,}\b"
    r"|\bgraph_w\d+_of_\d+\b"
    r"|\b(?:" + _VALUE_TOKENS_ALTERNATION + r")\b",
    re.IGNORECASE,
)

_FIELD_VALUE_RE = re.compile(
    r"['\"]?\b(?:" + _KEYS_ALTERNATION + r")\b['\"]?"
    r"\s*[:=：]\s*['\"]?[^'\"\s,;；，、)）\]}]+['\"]?(?:\s*/\s*['\"]?[^'\"\s,;；，、)）\]}]+['\"]?)*",
    re.IGNORECASE,
)


def contains_internal_identifier(value: Any) -> bool:
    """文本是否含内部排产标识(字段名 / op: / OPnn / graph_w 指纹 / 调试容器名)。"""
    return bool(INTERNAL_TEXT_RE.search(str(value or "")))


def is_forbidden_internal_key(key_text: Any) -> bool:
    """dict key 是否属于内部标识(禁止进入 public 投影)。空 key 也视为禁止。"""
    text = str(key_text or "").strip()
    if not text:
        return True
    lower = text.lower()
    if lower in FORBIDDEN_INTERNAL_KEYS or lower in FORBIDDEN_INTERNAL_VALUE_TOKENS:
        return True
    if OP_TOKEN_RE.search(text) or OP_CODE_TOKEN_RE.search(text):
        return True
    return bool(CANDIDATE_KEY_TOKEN_RE.search(text))


def redact_internal_text(value: Any) -> str:
    """把自由文本里的内部标识(key:value 串、op:/OPnn token、候选指纹、调试容器名、字段名)
    替换成安全占位。空串原样返回空串。"""
    text = str(value or "")
    if not text:
        return ""
    text = _FIELD_VALUE_RE.sub(REDACTED_INTERNAL_TEXT, text)
    text = OP_TOKEN_RE.sub(REDACTED_INTERNAL_TEXT, text)
    text = OP_CODE_TOKEN_RE.sub(REDACTED_INTERNAL_TEXT, text)
    text = CANDIDATE_KEY_TOKEN_RE.sub(REDACTED_INTERNAL_TEXT, text)
    text = _VALUE_TOKEN_RE.sub(REDACTED_INTERNAL_TEXT, text)
    for key in sorted(FORBIDDEN_INTERNAL_KEYS, key=len, reverse=True):
        text = re.sub(r"\b" + re.escape(key) + r"\b", REDACTED_INTERNAL_FIELD, text, flags=re.IGNORECASE)
    return text


__all__ = [
    "CANDIDATE_KEY_TOKEN_RE",
    "FORBIDDEN_INTERNAL_KEYS",
    "FORBIDDEN_INTERNAL_VALUE_TOKENS",
    "INTERNAL_TEXT_RE",
    "OP_CODE_TOKEN_RE",
    "OP_TOKEN_RE",
    "REDACTED_INTERNAL_FIELD",
    "REDACTED_INTERNAL_TEXT",
    "contains_internal_identifier",
    "is_forbidden_internal_key",
    "redact_internal_text",
]

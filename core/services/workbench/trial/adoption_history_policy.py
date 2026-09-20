"""Adoption-history read limits and rulings; TrialAdoptionHistoryRepository only returns bounded facts."""

from core.models.workbench_trial import reject

MAX_SCAN_ROWS = 100000
MAX_RECEIPTS = 1000
MAX_DIRECTORY_BYTES = 8 * 1024 * 1024
MAX_RECEIPT_BYTES = 64 * 1024
MAX_SCENARIO_BYTES = 32 * 1024 * 1024


def bound(size, limit):
    if type(size) is not int or size < 0:
        reject("adoption_history_invalid", "历史证据字段缺失或类型无效。")
    if size > limit:
        reject("query_too_large", "历史证据超过本批读取大小上限，未截断或转换原值。", 413)


def load_receipt(repo, key, limit=MAX_SCENARIO_BYTES):
    """One command receipt row whose outcome_json is bounded text; size is checked before the body is read."""
    size = repo.receipt_size(key)
    if size is None:
        reject("adoption_history_invalid", "原命令回执缺失，不能证明保存来源。")
    bound(size["bytes"], limit)
    row = repo.receipt_row(key)
    if type(row["outcome_json"]) is not str:
        reject("adoption_history_invalid", "采用回执不是有效结构化文本，未转换原值。")
    return row


def adoption_receipts(repo, scenario_ref):
    """Every trial.scenario.adopt receipt of one scenario, newest first; the scan, count and bytes are all capped."""
    selected, byte_count = [], 0
    for index, row in enumerate(repo.receipt_headers(MAX_SCAN_ROWS + 1)):
        if index >= MAX_SCAN_ROWS:
            reject("query_too_large", "命令目录超过100000条读取上限，未返回截断采用历史。", 413)
        if (row["action"], row["context_ref"]) != ("trial.scenario.adopt", scenario_ref):
            continue
        if len(selected) >= MAX_RECEIPTS:
            reject("query_too_large", "本场景采用回执超过1000条读取上限，未截断。", 413)
        item = load_receipt(repo, row["request_key"], MAX_RECEIPT_BYTES)
        byte_count += len(item["outcome_json"].encode("utf-8"))
        if byte_count > MAX_DIRECTORY_BYTES:
            reject("query_too_large", "采用回执目录超过8 MiB读取上限，未截断。", 413)
        selected.append(item)
    return sorted(selected, key=lambda r: (r["committed_at_utc"], r["request_key"]), reverse=True)


def load_history(repo, version):
    """The single ScheduleHistory row of one version with a bounded summary, or None when there is not exactly one."""
    heads = repo.history_heads(version)
    if len(heads) != 1:
        return None
    bound(heads[0]["bytes"], MAX_RECEIPT_BYTES)
    return repo.history_row(heads[0]["id"])


def load_scenario_headers(repo, scenario_ref):
    """(scenario header, source draft header) with both large JSON columns bounded but unread."""
    header = repo.sized_scenario_header(scenario_ref)
    if header is None:
        reject("entity_not_found", "未找到指定试调场景，未改查最新场景。", 404)
    bound(header.pop("bytes"), MAX_SCENARIO_BYTES)
    draft = repo.sized_draft_header(header["draft_ref"])
    if draft is None:
        reject("adoption_history_invalid", "场景的原永久草稿缺失。")
    bound(draft.pop("bytes"), MAX_SCENARIO_BYTES)
    return header, draft

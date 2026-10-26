"""Adoption-history read limits and rulings; TrialAdoptionHistoryRepository only returns bounded facts."""

from core.models.workbench_trial import reject

MAX_RECEIPTS = 1000
MAX_DIRECTORY_BYTES = 8 * 1024 * 1024
MAX_RECEIPT_BYTES = 64 * 1024
MAX_SCENARIO_BYTES = 32 * 1024 * 1024
# A trial.save outcome repeats the whole saved scenario, so it shares the scenario limit.
MAX_SAVE_RECEIPT_BYTES = MAX_SCENARIO_BYTES


def bound(size, limit, subject="历史内容"):
    if type(size) is not int or size < 0:
        reject("adoption_history_invalid", subject + "的内容大小无效，请联系维护人员核对数据。")
    if size > limit:
        reject("query_too_large", subject + "超过单次读取上限，请联系维护人员核对数据。", 413)


def load_receipt(repo, key):
    """The scenario's trial.save command body, with its UTF-8 limit enforced as it is consumed."""
    row = repo.receipt_row(key)
    if row is None:
        reject("adoption_history_invalid", "原保存结果缺失，无法确认方案来源。请联系维护人员核对。")
    if type(row["outcome_json"]) is not str:
        reject("adoption_history_invalid", "采用结果记录格式有误，请联系维护人员核对。")
    bound(len(row["outcome_json"].encode("utf-8")), MAX_SAVE_RECEIPT_BYTES, "保存结果")
    return row


def adoption_receipts(repo, scenario_ref):
    """Consume only this scenario's bounded adoption bodies, newest first."""
    selected, byte_count = [], 0
    for item in repo.adoption_receipts("trial.scenario.adopt", scenario_ref, MAX_RECEIPTS + 1):
        if len(selected) >= MAX_RECEIPTS:
            reject("query_too_large", "本试调方案的采用结果超过 1000 条读取上限，请联系维护人员处理。", 413)
        if type(item["outcome_json"]) is not str:
            reject("adoption_history_invalid", "采用结果记录格式有误，请联系维护人员核对。")
        size = len(item["outcome_json"].encode("utf-8"))
        bound(size, MAX_RECEIPT_BYTES, "保存结果")
        byte_count += size
        bound(byte_count, MAX_DIRECTORY_BYTES, "采用结果列表")
        selected.append(item)
    return selected


def history_audit_row(rows):
    """One captured history body, or None when this version has no unique audit."""
    if len(rows) != 1:
        return None
    raw = rows[0]["result_summary"]
    if type(raw) is not str:
        reject("adoption_history_invalid", "排产记录摘要的内容大小无效，请联系维护人员核对数据。")
    bound(len(raw.encode("utf-8")), MAX_RECEIPT_BYTES, "排产记录摘要")
    return rows[0]

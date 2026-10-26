"""Cell texts shared by every decision export table."""


def issue_text(value):
    """One cell for an issue code, an issue dict, or a list of either; nothing recorded stays empty."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("message") or value.get("code")
    return "；".join(str(item.get("message") or item.get("code")) if isinstance(item, dict) else str(item) for item in value or ()) or None


def baseline_ref(baseline):
    return baseline.get("candidate_ref") if baseline["kind"] == "candidate" else baseline.get("baseline_ref")


def boolean_text(value):
    return None if value is None else "是" if value else "否"

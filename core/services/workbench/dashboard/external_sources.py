"""Dashboard external evaluation-gap rows: subject text and the public gap shape."""


def subject(value, fallback):
    return value if type(value) is str and value.strip() else fallback


def gap(ref, title, issues):
    return {"source_ref": ref, "subject": title, "code": issues[0]["code"],
            "message": "；".join(issue["message"] for issue in issues)}

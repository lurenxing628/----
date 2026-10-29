"""Lossless private batch facts, with repeated record field names written once."""

from core.models.content import content_text


def record_content(rows):
    """Preserve homogeneous source row order, every field and its exact SQLite value."""
    if not rows:
        return {"columns": [], "values": []}
    columns = sorted(rows[0].keys())
    return {"columns": columns, "values": [[row[column] for column in columns] for row in rows]}


def shared_content(rows, names):
    """Replace repeated field values by stable, content-bound catalog indices."""
    catalogs = {}
    for name in names:
        values, by_content = [], {}
        for row in rows:
            text = content_text(row[name])
            if text not in by_content:
                by_content[text] = len(values)
                values.append(text)
            row[name] = by_content[text]
        catalogs[name] = values
    return catalogs

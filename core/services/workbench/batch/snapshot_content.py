"""Lossless private batch facts, with repeated record field names written once."""

from core.models.content import content_text


def record_content(rows):
    """Preserve homogeneous source row order, every field and its exact SQLite value."""
    if not rows:
        return {"columns": [], "values": []}
    columns = sorted(rows[0].keys())
    return {"columns": columns, "values": [[row[column] for column in columns] for row in rows]}


def shared_content(rows, names):
    """Replace repeated field values by stable, content-bound catalog indices.

    Rows are already ordered by their permanent dictionary key. Catalog order
    follows that order, and equality uses the existing lossless canonical
    codec. Object identity only avoids recoding an object within this call;
    equal values with distinct allocations receive the same catalog index.
    """
    catalogs = {}
    for name in names:
        values, by_content, by_object = [], {}, {}
        for row in rows:
            value = row[name]
            identity = id(value)
            if identity in by_object:
                index = by_object[identity]
            else:
                text = content_text(value)
                if text not in by_content:
                    by_content[text] = len(values)
                    values.append(text)
                index = by_content[text]
                by_object[identity] = index
            row[name] = index
        catalogs[name] = values
    return catalogs

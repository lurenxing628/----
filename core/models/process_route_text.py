"""Lossless, readable serialization of operation sequence/name pairs."""


def serialize_route_rows(rows):
    result = []
    for seq, name in rows:
        if any(char in name for char in ';；\r\n"') or name != name.strip():
            name = '"' + name.replace('"', '""') + '"'
        result.append(str(seq) + ": " + name)
    return "；".join(result)

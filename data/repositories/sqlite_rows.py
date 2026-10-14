"""Read SQLite storage classes independently of connection date converters."""

from core.infrastructure.schema_probe import table_columns


def raw_projection(conn, table):
    names = table_columns(conn, table)
    if not names:
        raise ValueError("Raw SQLite table has no columns: " + table)
    columns = ["+\"" + name.replace('"', '""') + '\" AS "wb_raw_' + str(index) + '"'
               for index, name in enumerate(names)]
    return names, ",".join(columns)

"""Stage bindings and dated batch allocations, separate from general stock."""

from .workbench_metadata_schema import canonical_sql


def objects():
    return {
        "BatchMaterialReviews": """CREATE TABLE BatchMaterialReviews (
            requirement_id INTEGER PRIMARY KEY REFERENCES BatchMaterials(id) ON DELETE CASCADE,
            batch_quantity INTEGER NOT NULL CHECK(batch_quantity >= 0))""",
        "BatchMaterialStages": """CREATE TABLE BatchMaterialStages (
            requirement_id INTEGER PRIMARY KEY REFERENCES BatchMaterials(id) ON DELETE CASCADE,
            operation_id INTEGER NOT NULL REFERENCES BatchOperations(id) ON DELETE RESTRICT)""",
        "BatchMaterialArrivals": """CREATE TABLE BatchMaterialArrivals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requirement_id INTEGER NOT NULL REFERENCES BatchMaterials(id) ON DELETE CASCADE,
            arrival_date TEXT NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0))""",
        "idx_material_arrival_requirement": "CREATE INDEX idx_material_arrival_requirement ON BatchMaterialArrivals(requirement_id)",
        "BatchQuantitySplits": """CREATE TABLE BatchQuantitySplits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_batch_id TEXT NOT NULL REFERENCES Batches(batch_id),
            child_batch_id TEXT NOT NULL UNIQUE REFERENCES Batches(batch_id),
            original_quantity INTEGER NOT NULL,
            split_quantity INTEGER NOT NULL,
            allocation_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
    }


def contract_issues(conn):
    actual = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master")}
    return [("missing_material_stages:" if name not in actual else "invalid_material_stages:") + name
            for name, sql in objects().items()
            if name not in actual or canonical_sql(sql) != canonical_sql(actual[name] or "")]


def install(conn):
    if not conn.in_transaction:
        raise RuntimeError("Material stages require a migration transaction.")
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    if names & set(objects()):
        issues = contract_issues(conn)
        if issues:
            raise RuntimeError("Cannot repair partial material stages: " + ";".join(issues))
        return
    for sql in objects().values():
        conn.execute(sql)

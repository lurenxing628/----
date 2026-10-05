"""Stage bindings and dated batch allocations, separate from general stock."""

from .schema_structure import schema_objects
from .workbench_metadata_schema import canonical_sql


def objects():
    return {
        "BatchMaterialReviews": """CREATE TABLE BatchMaterialReviews (
            requirement_id INTEGER PRIMARY KEY REFERENCES BatchMaterials(id) ON DELETE CASCADE,
            batch_quantity INTEGER CHECK(batch_quantity >= 0))""",
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
        "wb_material_quantity_basis": """CREATE TRIGGER wb_material_quantity_basis
            AFTER UPDATE OF quantity ON Batches
            WHEN NEW.quantity IS NOT OLD.quantity
            BEGIN
                INSERT OR IGNORE INTO BatchMaterialReviews(requirement_id,batch_quantity)
                    SELECT id, CASE WHEN typeof(OLD.quantity) = 'integer' AND OLD.quantity >= 0
                        THEN OLD.quantity ELSE NULL END
                    FROM BatchMaterials WHERE batch_id = NEW.batch_id;
                UPDATE Batches SET ready_status = 'no'
                    WHERE batch_id = NEW.batch_id AND EXISTS (
                        SELECT 1 FROM BatchMaterials m
                        JOIN BatchMaterialReviews r ON r.requirement_id = m.id
                        WHERE m.batch_id = NEW.batch_id
                            AND (r.batch_quantity IS NULL OR r.batch_quantity IS NOT NEW.quantity));
            END""",
    }


def contract_issues(conn, *, structure=None):
    actual = schema_objects(conn, structure=structure)
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

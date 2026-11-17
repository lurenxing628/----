"""Stage bindings and dated batch allocations, separate from general stock."""

from core.models.enums import positive_amount_check, positive_count_check

from .schema_structure import SchemaStructure
from .workbench_metadata_schema import canonical_sql


def objects():
    return {
        "BatchMaterialReviews": f"""CREATE TABLE BatchMaterialReviews (
            requirement_id INTEGER PRIMARY KEY REFERENCES BatchMaterials(id) ON DELETE CASCADE,
            batch_quantity INTEGER NOT NULL {positive_count_check('batch_quantity')})""",
        "BatchMaterialStages": """CREATE TABLE BatchMaterialStages (
            requirement_id INTEGER PRIMARY KEY REFERENCES BatchMaterials(id) ON DELETE CASCADE,
            operation_id INTEGER NOT NULL REFERENCES BatchOperations(id) ON DELETE RESTRICT)""",
        "BatchMaterialArrivals": f"""CREATE TABLE BatchMaterialArrivals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requirement_id INTEGER NOT NULL REFERENCES BatchMaterials(id) ON DELETE CASCADE,
            arrival_date TEXT NOT NULL,
            quantity REAL NOT NULL {positive_amount_check('quantity')})""",
        "idx_material_arrival_requirement": "CREATE INDEX idx_material_arrival_requirement ON BatchMaterialArrivals(requirement_id)",
        "BatchQuantitySplits": """CREATE TABLE BatchQuantitySplits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_batch_id TEXT NOT NULL REFERENCES Batches(batch_id),
            child_batch_id TEXT NOT NULL UNIQUE REFERENCES Batches(batch_id),
            original_quantity INTEGER NOT NULL,
            split_quantity INTEGER NOT NULL,
            allocation_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
        "idx_batch_quantity_splits_source": "CREATE INDEX idx_batch_quantity_splits_source ON BatchQuantitySplits(source_batch_id)",
        "wb_material_quantity_basis": """CREATE TRIGGER wb_material_quantity_basis
            AFTER UPDATE OF quantity ON Batches
            WHEN NEW.quantity IS NOT OLD.quantity
            BEGIN
                INSERT OR IGNORE INTO BatchMaterialReviews(requirement_id,batch_quantity)
                    SELECT id, OLD.quantity FROM BatchMaterials WHERE batch_id = NEW.batch_id;
                UPDATE Batches SET ready_status = 'no'
                    WHERE batch_id = NEW.batch_id AND EXISTS (
                        SELECT 1 FROM BatchMaterials m
                        JOIN BatchMaterialReviews r ON r.requirement_id = m.id
                        WHERE m.batch_id = NEW.batch_id
                            AND r.batch_quantity IS NOT NEW.quantity);
            END""",
    }


def contract_issues(structure: SchemaStructure):
    actual = structure.sql
    return [("missing_material_stages:" if name not in actual else "invalid_material_stages:") + name
            for name, sql in objects().items()
            if name not in actual or canonical_sql(sql) != canonical_sql(actual[name])]

"""Persist explicit operation binding and dated quantities; no readiness ruling."""

from .base_repo import BaseRepository


class BatchMaterialStageRepository(BaseRepository):
    def review(self, requirement_id, batch_quantity):
        self.execute("INSERT INTO BatchMaterialReviews(requirement_id,batch_quantity) VALUES(?,?) ON CONFLICT(requirement_id) DO UPDATE SET batch_quantity=excluded.batch_quantity",
                     (requirement_id, batch_quantity))

    def details(self, requirement_id):
        stage = self.fetchone("SELECT operation_id FROM BatchMaterialStages WHERE requirement_id=?", (requirement_id,))
        arrivals = self.fetchall("SELECT arrival_date,quantity FROM BatchMaterialArrivals WHERE requirement_id=? ORDER BY arrival_date,id", (requirement_id,))
        return {"operation_id": stage["operation_id"] if stage else None, "arrivals": arrivals}

    def replace(self, requirement_id, operation_id, arrivals):
        self.execute("DELETE FROM BatchMaterialStages WHERE requirement_id=?", (requirement_id,))
        if operation_id is not None:
            self.execute("INSERT INTO BatchMaterialStages(requirement_id,operation_id) VALUES(?,?)", (requirement_id, operation_id))
        self.execute("DELETE FROM BatchMaterialArrivals WHERE requirement_id=?", (requirement_id,))
        for row in arrivals:
            self.execute("INSERT INTO BatchMaterialArrivals(requirement_id,arrival_date,quantity) VALUES(?,?,?)",
                         (requirement_id, row["arrival_date"], row["quantity"]))

    def record_split(self, source, child, original, quantity, day):
        self.execute("INSERT INTO BatchQuantitySplits(source_batch_id,child_batch_id,original_quantity,split_quantity,allocation_date) VALUES(?,?,?,?,?)",
                     (source, child, original, quantity, day))


class TerritoryService:
    def summarize(self, records):
        return {
            "records": len(records),
            "territories": sorted(
                set(
                    r.get("territory")
                    for r in records
                    if r.get("territory")
                )
            )
        }


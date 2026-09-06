
class ProductionReport:
    def generate(self, records):
        return {
            "total_records": len(records),
            "records": list(records)
        }


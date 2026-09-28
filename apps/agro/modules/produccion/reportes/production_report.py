
class ProductionReport:
    def generate(self, records):
        return {
            "total_records": len(records),
            "records": list(records)
        }


# ---- additive PLUS (GPT-2): reporte nacional ----
def national_report(store):
    return ProductionReport().generate(
        store.list_productions()
    )

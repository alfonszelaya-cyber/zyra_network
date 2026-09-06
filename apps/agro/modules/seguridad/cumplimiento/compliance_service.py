
class AgroComplianceService:
    def verify(self, record, required_fields):
        missing = [
            field for field in required_fields
            if field not in record
        ]

        return {
            "compliant": not missing,
            "missing": missing
        }


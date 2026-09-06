
class GovernmentControlService:
    def verify(self, record, required_fields):
        missing = [
            field for field in required_fields
            if not record.get(field)
        ]

        return {
            "valid": not missing,
            "missing": missing
        }


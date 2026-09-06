
class AidControl:
    def verify(self, beneficiary_id, records):
        matches = [
            record for record in records
            if record.get("beneficiary_id") == beneficiary_id
        ]

        return {
            "beneficiary_id": beneficiary_id,
            "verified": bool(matches),
            "records": matches
        }


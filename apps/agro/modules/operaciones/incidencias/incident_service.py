
class IncidentService:
    def report(self, operation_id, description, severity="normal"):
        return {
            "operation_id": operation_id,
            "description": description,
            "severity": severity,
            "status": "open"
        }


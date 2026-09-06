
class TerritorialRiskService:
    def evaluate(self, territory, incidents):
        return {
            "territory": territory,
            "incident_count": len(incidents),
            "risk": "high" if len(incidents) >= 5 else "normal"
        }


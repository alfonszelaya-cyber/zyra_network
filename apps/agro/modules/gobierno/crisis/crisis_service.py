
class AgriculturalCrisisService:
    def declare(self, territory, crisis_type, severity):
        return {
            "territory": territory,
            "crisis_type": crisis_type,
            "severity": severity,
            "status": "active"
        }


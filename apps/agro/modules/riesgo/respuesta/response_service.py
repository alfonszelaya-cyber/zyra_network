
class RiskResponseService:
    def create(self, risk_id, actions):
        return {
            "risk_id": risk_id,
            "actions": list(actions),
            "status": "planned"
        }


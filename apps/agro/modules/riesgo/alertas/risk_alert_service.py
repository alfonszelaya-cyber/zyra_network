
class RiskAlertService:
    def create(self, risk_type, severity, target):
        return {
            "risk_type": risk_type,
            "severity": severity,
            "target": target
        }


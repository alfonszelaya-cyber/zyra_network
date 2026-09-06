
class ClimateRiskService:
    def evaluate(self, event_type, severity):
        return {
            "event_type": event_type,
            "severity": severity,
            "alert": severity in {"high", "critical"}
        }


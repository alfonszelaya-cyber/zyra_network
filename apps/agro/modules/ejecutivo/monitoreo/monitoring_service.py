
class ExecutiveMonitoring:
    def evaluate(self, alerts):
        return {
            "alerts": list(alerts),
            "count": len(alerts)
        }



class ExecutiveDashboard:
    def build(self, indicators):
        return {
            "indicators": dict(indicators),
            "count": len(indicators)
        }


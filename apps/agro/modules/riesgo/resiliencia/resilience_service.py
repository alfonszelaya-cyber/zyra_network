
class ResilienceService:
    def recovery_score(self, recovered, affected):
        if affected <= 0:
            raise ValueError("Affected must be positive")

        return recovered / affected


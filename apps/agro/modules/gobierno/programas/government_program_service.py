
class GovernmentProgramManager:
    def create(self, name, budget=None):
        return {
            "name": name,
            "budget": budget,
            "status": "active"
        }



class GovernmentProgramService:
    def create(self, name, requirements=None):
        return {
            "name": name,
            "requirements": list(requirements or [])
        }


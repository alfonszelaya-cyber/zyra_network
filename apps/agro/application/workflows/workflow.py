
class Workflow:
    def __init__(self):
        self.steps = []

    def add(self, step):
        if not callable(step):
            raise TypeError("Workflow step must be callable")
        self.steps.append(step)
        return self

    def run(self, context):
        result = context
        for step in self.steps:
            result = step(result)
        return result


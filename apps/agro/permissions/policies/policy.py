
class Policy:
    def __init__(self, name, allowed_actions):
        self.name = name
        self.allowed_actions = set(allowed_actions)

    def allows(self, action):
        return action in self.allowed_actions


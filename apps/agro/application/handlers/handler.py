
class CommandHandler:
    def handle(self, command):
        if not command.validate():
            raise ValueError("Invalid command")
        return self.execute(command)

    def execute(self, command):
        raise NotImplementedError


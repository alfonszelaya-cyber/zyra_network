
from apps.agro.registry.modules.registry import ModuleRegistry
from apps.agro.registry.menus.registry import MenuRegistry

class AgroApplication:
    name = "agro"

    def modules(self):
        return ModuleRegistry.all()

    def navigation(self):
        return MenuRegistry.build()

    def health(self):
        return {
            "application": self.name,
            "status": "operational"
        }

agro_application = AgroApplication()


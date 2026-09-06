
class MenuRegistry:
    _menus = {}

    @classmethod
    def register(cls, module, menu):
        cls._menus[module] = menu

    @classmethod
    def build(cls):
        return dict(cls._menus)


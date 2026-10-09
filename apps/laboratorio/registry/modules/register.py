"""Registro unico de modulos verticales activos."""


class RegistroModulos:
    def __init__(self):
        self._modulos = {}

    def registrar(self, manifiesto) -> None:
        if manifiesto is None or not hasattr(manifiesto, "id"):
            raise ValueError("Se esperaba un ManifiestoModulo.")
        if manifiesto.id in self._modulos:
            raise ValueError("Modulo duplicado: " + manifiesto.id)
        self._modulos[manifiesto.id] = manifiesto

    def registrar_varios(self, manifiestos) -> None:
        for m in manifiestos:
            self.registrar(m)

    def listar(self) -> list:
        return [
            {"id": m.id, "nombre": m.nombre, "version": m.version, "descripcion": m.descripcion}
            for _, m in sorted(self._modulos.items())
        ]

    def contiene(self, id_modulo: str) -> bool:
        return id_modulo in self._modulos

    def total(self) -> int:
        return len(self._modulos)

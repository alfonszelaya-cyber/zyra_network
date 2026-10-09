"""Registro unico de plantillas HTML de LABORATORIO."""


class RegistroPlantillas:
    def __init__(self):
        self._plantillas = {}

    def registrar(self, nombre: str, contenido: str) -> None:
        if not nombre or not isinstance(nombre, str):
            raise ValueError("Nombre de plantilla invalido.")
        if not isinstance(contenido, str) or not contenido.strip():
            raise ValueError("La plantilla requiere contenido.")
        if nombre in self._plantillas:
            raise ValueError("Plantilla duplicada: " + nombre)
        self._plantillas[nombre] = contenido

    def obtener(self, nombre: str) -> str:
        if nombre not in self._plantillas:
            raise ValueError("Plantilla no registrada: " + nombre)
        return self._plantillas[nombre]

    def listar(self) -> tuple:
        return tuple(sorted(self._plantillas))

    def total(self) -> int:
        return len(self._plantillas)

"""Manejador de escaneo por foto y avatar desde foto."""
from apps.laboratorio.application.use_cases.scan_photo import (
    CasoAvatarDesdeFoto,
    CasoEscanearFoto,
)
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorEscaneo:
    def __init__(self, caso_escanear, caso_avatar):
        self._caso_escanear = caso_escanear
        self._caso_avatar = caso_avatar

    def escanear(self, identidad, entrada_id: str) -> tuple:
        resultado = self._caso_escanear.ejecutar(identidad, entrada_id)
        return exito(resultado)

    def avatar(self, identidad, entrada_id: str) -> tuple:
        resultado = self._caso_avatar.ejecutar(identidad, entrada_id)
        return exito(resultado, 201)

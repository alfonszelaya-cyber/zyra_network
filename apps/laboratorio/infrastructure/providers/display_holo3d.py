"""Destino holografico volumetrico: registrado con honestidad (Ley 1)."""

from apps.laboratorio.shared.adapters.engine_adapter import AdaptadorMotor
from apps.laboratorio.shared.exceptions.pipeline_errors import (
    DestinoNoDisponibleError,
)
from apps.laboratorio.shared.interfaces.display_adapter import DisplayAdapter


class MotorHolo3D(AdaptadorMotor, DisplayAdapter):
    def __init__(self):
        AdaptadorMotor.__init__(self, "display_holo3d", "display", "0.1.0")
        self.marcar_no_disponible("hardware holografico volumetrico no conectado")

    def kind(self) -> str:
        return "holografico"

    def disponible(self) -> bool:
        return self.estado.value == "disponible"

    def capacidades(self) -> dict:
        return {
            "volumetrico": True,
            "profundidad_continua": True,
            "estado": self.estado.value,
            "motivo": self.motivo_estado,
        }

    def presentar(self, frame_bytes, config) -> dict:
        raise DestinoNoDisponibleError(
            "El destino holografico no tiene hardware conectado; se activara al conectarlo."
        )

"""Fabrica de Escenarios A/B/C validados."""
from apps.laboratorio.domain.scenario import Escenario
from apps.laboratorio.shared.enums.scenario_type import ScenarioType
from apps.laboratorio.shared.models.identifiers import nuevo_id


class EscenarioFactory:
    """Crea escenarios listos para evaluate_scenario()."""

    @staticmethod
    def crear(proyecto_id, tipo, titulo: str, descripcion: str = "", parametros=None) -> Escenario:
        if isinstance(tipo, str):
            tipo_enum = ScenarioType.validar(tipo)
        elif isinstance(tipo, ScenarioType):
            tipo_enum = tipo
        else:
            raise ValueError("tipo de escenario invalido.")
        return Escenario(
            id=nuevo_id("esc"),
            proyecto_id=proyecto_id,
            tipo=tipo_enum,
            titulo=titulo,
            descripcion=descripcion or "",
            parametros=dict(parametros or {}),
        )

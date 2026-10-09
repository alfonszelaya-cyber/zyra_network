"""LAB-CORE: Escenario A/B/C y evaluate_scenario().

Logica de dominio pura: sin HTTP, sin base de datos, sin framework.
La API y la persistencia son capas externas que la consumen.
"""

from dataclasses import dataclass, field
from typing import Dict

from apps.laboratorio.shared.enums.scenario_type import ScenarioType
from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador


@dataclass
class Escenario(EntidadBase):
    """Un escenario comparable (A, B o C) de un proyecto."""

    prefijo_id = "esc"

    proyecto_id: Identificador = None
    tipo: ScenarioType = ScenarioType.A
    titulo: str = ""
    descripcion: str = ""
    parametros: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        if self.proyecto_id is None:
            raise ValueError("El escenario requiere el id de su proyecto.")
        if not self.titulo.strip():
            raise ValueError("El escenario requiere un titulo.")
        self.titulo = self.titulo.strip()
        for clave, valor in self.parametros.items():
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise ValueError("Parametro no numerico: " + clave)

    def definir_parametro(self, clave: str, valor: float) -> None:
        """Define un parametro numerico del escenario."""
        if not isinstance(clave, str) or not clave.strip():
            raise ValueError("Clave de parametro invalida.")
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError("El parametro debe ser numerico.")
        self.parametros[clave.strip()] = float(valor)
        self.marcar_actualizacion()


def evaluate_scenario(escenario: Escenario) -> Dict[str, object]:
    """Evalua un escenario A/B/C con la regla oficial LAB-CORE.

    Parametros requeridos (escala 0 a 100):
      costo     -> menor es mejor
      beneficio -> mayor es mejor
      riesgo    -> menor es mejor
    Puntaje = 0.4*(100-costo) + 0.4*beneficio + 0.2*(100-riesgo).
    """
    if not isinstance(escenario, Escenario):
        raise ValueError("evaluate_scenario requiere un Escenario.")
    requeridos = ("costo", "beneficio", "riesgo")
    faltan = [k for k in requeridos if k not in escenario.parametros]
    if faltan:
        raise ValueError("Faltan parametros: " + ", ".join(faltan))
    for clave in requeridos:
        valor = escenario.parametros[clave]
        if not 0.0 <= valor <= 100.0:
            raise ValueError(
                "Parametro " + clave + " fuera de escala 0-100."
            )
    costo = escenario.parametros["costo"]
    beneficio = escenario.parametros["beneficio"]
    riesgo = escenario.parametros["riesgo"]
    puntaje = (
        0.4 * (100.0 - costo)
        + 0.4 * beneficio
        + 0.2 * (100.0 - riesgo)
    )
    return {
        "costo": round(costo, 4),
        "beneficio": round(beneficio, 4),
        "riesgo": round(riesgo, 4),
        "puntaje_total": round(puntaje, 4),
        "tipo": escenario.tipo.value,
    }

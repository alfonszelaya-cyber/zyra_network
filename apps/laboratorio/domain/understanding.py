"""Comprension: resultado real de analizar una entrada.

Los hallazgos declaran su certeza (estandar ZYRA): evidencia
encontrada para coincidencias literales, inferencia para
deducciones. Nunca se inventa: cada hallazgo lleva razon.
"""
from dataclasses import dataclass, field
from typing import Dict, List

from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador


@dataclass
class Comprension(EntidadBase):
    """Analisis real de una entrada capturada."""

    prefijo_id = "und"

    entrada_id: Identificador = None
    proyecto_id: Identificador = None
    resumen: str = ""
    hallazgos: List[Dict[str, str]] = field(default_factory=list)
    entidades: Dict[str, list] = field(default_factory=dict)
    dominio: str = ""
    confianza: float = 0.0

    def __post_init__(self):
        if self.entrada_id is None or self.proyecto_id is None:
            raise ValueError("La comprension requiere entrada_id y proyecto_id.")
        if not 0.0 <= float(self.confianza) <= 1.0:
            raise ValueError("La confianza debe estar entre 0.0 y 1.0.")
        self.resumen = str(self.resumen)[:300]

    @property
    def total_hallazgos(self) -> int:
        return len(self.hallazgos)

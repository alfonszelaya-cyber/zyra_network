"""Blueprint de diseno: la estructura antes de crear la escena.

Un blueprint declara componentes con nombre, tipo y requisitos.
Regla de produccion: un blueprint sin componentes no se guarda.
"""
from dataclasses import dataclass, field
from typing import List

from apps.laboratorio.shared.enums.creation_type import CreationType
from apps.laboratorio.shared.models.base import EntidadBase
from apps.laboratorio.shared.models.identifiers import Identificador


@dataclass
class Blueprint(EntidadBase):
    """Diseno estructural de un proyecto."""

    prefijo_id = "dsn"

    proyecto_id: Identificador = None
    nombre: str = ""
    tipo_creacion: CreationType = CreationType.PRESENTACION
    componentes: List[dict] = field(default_factory=list)

    def __post_init__(self):
        if self.proyecto_id is None:
            raise ValueError("El blueprint requiere el id de su proyecto.")
        if not self.nombre.strip():
            raise ValueError("El blueprint requiere nombre.")
        self.nombre = self.nombre.strip()

    def agregar_componente(self, nombre: str, tipo: str, requisitos: str = "") -> None:
        if not nombre or not nombre.strip():
            raise ValueError("El componente requiere nombre.")
        if not tipo or not tipo.strip():
            raise ValueError("El componente requiere tipo.")
        self.componentes.append({
            "nombre": nombre.strip()[:120],
            "tipo": tipo.strip()[:60],
            "requisitos": (requisitos or "").strip()[:500],
        })
        self.marcar_actualizacion()

    @property
    def es_valido(self) -> bool:
        return len(self.componentes) > 0 and all(
            c.get("nombre") and c.get("tipo") for c in self.componentes
        )

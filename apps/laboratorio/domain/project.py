"""Proyecto: agregado raiz de LABORATORIO.

Toda creacion (presentacion, ley, edificio, app, negocio...) es un
Proyecto con UN tipo oficial y UNA etapa de la cadena D1.
"""

from dataclasses import dataclass, field

from apps.laboratorio.shared.enums.creation_type import CreationType
from apps.laboratorio.shared.enums.pipeline_stage import PipelineStage
from apps.laboratorio.shared.enums.project_status import ProjectStatus
from apps.laboratorio.shared.models.base import EntidadBase


@dataclass
class Proyecto(EntidadBase):
    """Agregado raiz: identidad, tipo, etapa y estado del trabajo."""

    prefijo_id = "proy"

    titulo: str = ""
    descripcion: str = ""
    tipo_creacion: CreationType = CreationType.PRESENTACION
    etapa_actual: PipelineStage = PipelineStage.DESCRIBIR
    estado: ProjectStatus = ProjectStatus.BORRADOR
    propietario_zid: str = ""
    etiquetas: list = field(default_factory=list)

    def __post_init__(self):
        if not self.titulo.strip():
            raise ValueError("El proyecto requiere un titulo.")
        if not self.propietario_zid.strip():
            raise ValueError("El proyecto requiere un propietario ZID.")
        self.titulo = self.titulo.strip()
        self.propietario_zid = self.propietario_zid.strip()

    def avanzar_etapa(self) -> PipelineStage:
        """Avanza a la siguiente etapa de la cadena D1."""
        cadena = PipelineStage.cadena_completa()
        indice = cadena.index(self.etapa_actual.value)
        if indice >= len(cadena) - 1:
            raise ValueError("El proyecto ya esta en la ultima etapa.")
        self.etapa_actual = PipelineStage(cadena[indice + 1])
        self.marcar_actualizacion()
        return self.etapa_actual

    def cambiar_estado(self, nuevo: ProjectStatus) -> ProjectStatus:
        """Cambia el estado del ciclo de vida."""
        if not isinstance(nuevo, ProjectStatus):
            raise ValueError("Estado de proyecto invalido.")
        self.estado = nuevo
        self.marcar_actualizacion()
        return self.estado

    def agregar_etiqueta(self, etiqueta: str) -> None:
        """Agrega una etiqueta normalizada sin duplicar."""
        if not isinstance(etiqueta, str) or not etiqueta.strip():
            raise ValueError("Etiqueta invalida.")
        limpia = etiqueta.strip().lower()
        if limpia not in self.etiquetas:
            self.etiquetas.append(limpia)
        self.marcar_actualizacion()

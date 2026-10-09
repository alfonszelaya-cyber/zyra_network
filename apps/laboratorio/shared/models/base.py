"""Base comun de las entidades de dominio."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from apps.laboratorio.shared.models.identifiers import Identificador


def ahora_utc() -> datetime:
    """Momento actual en UTC con zona explicita."""
    return datetime.now(timezone.utc)


@dataclass
class EntidadBase:
    """Toda entidad tiene id y marcas de tiempo UTC."""

    id: Identificador
    creado_en: datetime = field(default_factory=ahora_utc)
    actualizado_en: datetime = field(default_factory=ahora_utc)

    def marcar_actualizacion(self) -> None:
        """Actualiza la marca de la ultima modificacion."""
        self.actualizado_en = ahora_utc()

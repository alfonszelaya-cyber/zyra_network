"""Mixin de version incremental."""

from dataclasses import dataclass, field


@dataclass
class VersionadoMixin:
    """Lleva el numero de version y la nota de cada cambio.

    Al heredar, listar este mixin despues de EntidadBase.
    """

    version: int = 1
    notas_version: list = field(default_factory=list)

    def nueva_version(self, nota: str = "") -> int:
        """Incrementa y devuelve el numero de version."""
        if not isinstance(nota, str):
            raise ValueError("La nota de version debe ser texto.")
        self.version += 1
        self.notas_version.append(nota)
        return self.version

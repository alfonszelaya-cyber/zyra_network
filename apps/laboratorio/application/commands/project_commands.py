"""Comandos de proyecto: intenciones de escritura inmutables."""

from dataclasses import dataclass

from apps.laboratorio.schemas.requests.project import SchemaCrearProyecto


@dataclass(frozen=True)
class ComandoCrearProyecto:
    titulo: str
    descripcion: str
    tipo: str
    etiquetas: tuple
    propietario_zid: str

    @classmethod
    def desde_request(cls, datos: dict, zid: str) -> "ComandoCrearProyecto":
        limpios = SchemaCrearProyecto.validar(datos)
        return cls(
            limpios["titulo"],
            limpios["descripcion"],
            limpios["tipo"],
            tuple(limpios["etiquetas"]),
            zid,
        )

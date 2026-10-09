"""Comandos de escenarios A/B/C."""

from dataclasses import dataclass

from apps.laboratorio.schemas.requests.scenario import SchemaCrearEscenario


@dataclass(frozen=True)
class ComandoCrearEscenario:
    proyecto_id: str
    tipo: str
    titulo: str
    descripcion: str
    parametros: dict

    @classmethod
    def desde_request(cls, proyecto_id: str, datos: dict) -> "ComandoCrearEscenario":
        limpios = SchemaCrearEscenario.validar(datos)
        return cls(
            proyecto_id,
            limpios["tipo"],
            limpios["titulo"],
            limpios["descripcion"],
            limpios["parametros"],
        )


@dataclass(frozen=True)
class ComandoEvaluarEscenario:
    escenario_id: str
    nota: str = ""

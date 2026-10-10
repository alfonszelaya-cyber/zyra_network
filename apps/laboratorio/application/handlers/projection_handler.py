"""Manejador de proyeccion: superficies, calibracion y frames."""
from apps.laboratorio.application.use_cases.projection import (
    CasoCalibrarSuperficie,
    CasoProyectarEnVivo,
    CasoRegistrarSuperficie,
)
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorProyeccion:
    def __init__(self, caso_registrar, caso_calibrar, caso_proyectar, repo_superficies, auditoria):
        self._caso_registrar = caso_registrar
        self._caso_calibrar = caso_calibrar
        self._caso_proyectar = caso_proyectar
        self._superficies = repo_superficies
        self._auditoria = auditoria

    def registrar(self, identidad, datos: dict) -> tuple:
        resultado = self._caso_registrar.ejecutar(identidad, datos)
        return exito(resultado, 201)

    def listar(self, identidad) -> tuple:
        superficies = self._superficies.listar_por_propietario(identidad.zid)
        return exito({
            "superficies": [
                CasoRegistrarSuperficie._a_dict(s) for s in superficies
            ],
            "total": len(superficies),
        })

    def calibrar(self, identidad, superficie_id: str, datos: dict) -> tuple:
        if not isinstance(datos, dict) or not isinstance(datos.get("corners"), list):
            raise ValueError("Falta el campo corners (4 esquinas).")
        resultado = self._caso_calibrar.ejecutar(
            identidad, superficie_id, datos["corners"]
        )
        return exito(resultado)

    def proyectar(self, identidad, escena_id: str, datos: dict) -> tuple:
        if not isinstance(datos, dict) or not str(datos.get("surface_id", "")).strip():
            raise ValueError("Falta el campo surface_id.")
        return self._caso_proyectar.ejecutar(
            identidad, escena_id, str(datos["surface_id"]).strip()
        )

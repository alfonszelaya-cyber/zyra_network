"""Manejador de salidas: registro, listado y prueba."""
from apps.laboratorio.application.use_cases.displays import (
    CasoProbarSalida,
    CasoRegistrarSalida,
)
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorSalidas:
    def __init__(self, caso_registrar, caso_probar, repo_salidas, auditoria):
        self._caso_registrar = caso_registrar
        self._caso_probar = caso_probar
        self._salidas = repo_salidas
        self._auditoria = auditoria

    def registrar(self, identidad, datos: dict) -> tuple:
        resultado = self._caso_registrar.ejecutar(identidad, datos)
        return exito(resultado, 201)

    def listar(self, identidad) -> tuple:
        salidas = self._salidas.listar_por_propietario(identidad.zid)
        return exito({
            "salidas": [CasoRegistrarSalida._a_dict(d) for d in salidas],
            "total": len(salidas),
        })

    def probar(self, identidad, salida_id: str) -> tuple:
        return self._caso_probar.ejecutar(identidad, salida_id)

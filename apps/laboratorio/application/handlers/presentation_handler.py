"""Manejador de presentaciones: crear, listar, reproducir, sellar."""
from apps.laboratorio.application.use_cases.build_presentation import (
    CasoCrearPresentacion,
    CasoReproducirPresentacion,
    CasoSellarPresentacion,
)
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorPresentaciones:
    def __init__(self, caso_crear, caso_reproducir, caso_sellar, repo_presentaciones, repo_proyectos, auditoria):
        self._caso_crear = caso_crear
        self._caso_reproducir = caso_reproducir
        self._caso_sellar = caso_sellar
        self._presentaciones = repo_presentaciones
        self._proyectos = repo_proyectos
        self._auditoria = auditoria

    def crear(self, identidad, proyecto_id: str, datos: dict) -> tuple:
        resultado = self._caso_crear.ejecutar(identidad, proyecto_id, datos)
        return exito(resultado, 201)

    def listar(self, identidad, proyecto_id: str) -> tuple:
        proyecto = self._proyectos.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        presentaciones = self._presentaciones.listar_por_proyectos([proyecto.id])
        return exito({
            "presentaciones": [
                CasoCrearPresentacion._a_dict(p) for p in presentaciones
            ],
            "total": len(presentaciones),
        })

    def obtener(self, identidad, presentacion_id: str) -> tuple:
        presentacion = self._presentaciones.obtener_exigir(presentacion_id)
        proyecto = self._proyectos.obtener_exigir(str(presentacion.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        return exito({"presentacion": CasoCrearPresentacion._a_dict(presentacion)})

    def reproducir(self, identidad, presentacion_id: str) -> tuple:
        return self._caso_reproducir.ejecutar(identidad, presentacion_id)

    def sellar(self, identidad, presentacion_id: str) -> tuple:
        resultado = self._caso_sellar.ejecutar(identidad, presentacion_id)
        return exito(resultado)

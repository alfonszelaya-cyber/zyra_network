"""Manejador de exportaciones: bundle y envio ZYRA."""
from apps.laboratorio.application.use_cases.export_deliverables import CasoExportarBundle
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorExportaciones:
    def __init__(self, caso, repo_exportaciones, repo_proyectos, auditoria):
        self._caso = caso
        self._exportaciones = repo_exportaciones
        self._proyectos = repo_proyectos
        self._auditoria = auditoria

    def crear(self, identidad, proyecto_id: str, datos: dict) -> tuple:
        resultado = self._caso.ejecutar(identidad, proyecto_id, datos)
        return exito(resultado, 201)

    def listar(self, identidad, proyecto_id: str) -> tuple:
        proyecto = self._proyectos.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        exportaciones = self._exportaciones.listar_por_proyectos([proyecto.id])
        return exito({
            "exportaciones": [CasoExportarBundle._a_dict(e) for e in exportaciones],
            "total": len(exportaciones),
        })

    def obtener(self, identidad, export_id: str) -> tuple:
        exportacion = self._exportaciones.obtener_exigir(export_id)
        proyecto = self._proyectos.obtener_exigir(str(exportacion.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        return exito({"exportacion": CasoExportarBundle._a_dict(exportacion)})

"""Manejador de renders: ejecutar, listar y descargar."""
from apps.laboratorio.application.use_cases.render_world import CasoRenderizarEscena
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorRenders:
    def __init__(self, caso, repo_renders, repo_escenas, repo_proyectos, auditoria):
        self._caso = caso
        self._renders = repo_renders
        self._escenas = repo_escenas
        self._proyectos = repo_proyectos
        self._auditoria = auditoria

    def renderizar(self, identidad, escena_id: str, datos: dict) -> tuple:
        if not isinstance(datos, dict) or not str(datos.get("quality", "")).strip():
            raise ValueError("Falta el campo quality.")
        resultado = self._caso.ejecutar(
            identidad, escena_id, str(datos["quality"]).strip().lower()
        )
        return exito(resultado, 201)

    def listar(self, identidad, escena_id: str) -> tuple:
        escena = self._escenas.obtener_exigir(escena_id)
        proyecto = self._proyectos.obtener_exigir(str(escena.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        resumenes = self._renders.listar_resumen_por_proyectos([proyecto.id])
        propios = [r for r in resumenes if r["escena_id"] == str(escena.id)]
        return exito({"renders": propios, "total": len(propios)})

    def descargar(self, identidad, render_id: str) -> tuple:
        render = self._renders.obtener_exigir(render_id)
        proyecto = self._proyectos.obtener_exigir(str(render.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        return 200, render.imagen, {
            "Content-Type": render.mime,
            "Content-Disposition": "inline; filename=render_" + render_id + "."
            + render.formato,
        }

    def descargar_profundidad(self, identidad, render_id: str) -> tuple:
        render = self._renders.obtener_exigir(render_id)
        proyecto = self._proyectos.obtener_exigir(str(render.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        if not render.tiene_profundidad:
            raise ValueError(
                "Este render (" + render.calidad.value
                + ") no produce canal de profundidad; usa alta, 3d o fotorreal."
            )
        return 200, render.profundidad, {
            "Content-Type": "image/png",
            "Content-Disposition": "inline; filename=depth_" + render_id + ".png",
        }

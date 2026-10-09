"""Caso de uso: renderizar escena en la escalera fotoreal."""
import time

from apps.laboratorio.application.workflows.photoreal_ladder import EscaleraFotoreal
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.domain.render import TrabajoRender
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.shared.enums.render_quality import RenderQuality
from apps.laboratorio.shared.helpers.hashing import sha256_bytes
from apps.laboratorio.shared.models.identifiers import nuevo_id


class CasoRenderizarEscena:
    def __init__(
        self, repo_renders, repo_escenas, repo_proyectos,
        repo_luces, repo_historial, escalera, auditoria,
    ):
        self._renders = repo_renders
        self._escenas = repo_escenas
        self._proyectos = repo_proyectos
        self._luces = repo_luces
        self._historial = repo_historial
        self._escalera = escalera
        self._auditoria = auditoria

    def ejecutar(self, identidad, escena_id: str, calidad_str: str) -> dict:
        escena = self._escenas.obtener_exigir(escena_id)
        proyecto = self._proyectos.obtener_exigir(str(escena.proyecto_id))
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        calidad = RenderQuality.validar(str(calidad_str))
        programa_luz = self._luces.obtener_por_escena(escena.id)
        resultado, duracion_ms = self._escalera.ejecutar(
            escena, calidad, programa_luz
        )
        render = TrabajoRender(
            id=nuevo_id("rnd"), proyecto_id=proyecto.id, escena_id=escena.id,
            calidad=calidad,
            formato="svg" if calidad is RenderQuality.BORRADOR else "png",
            ancho=resultado.ancho, alto=resultado.alto,
            imagen=resultado.imagen_bytes,
            profundidad=resultado.profundidad_bytes or b"",
            hash_sha256=sha256_bytes(resultado.imagen_bytes),
            duracion_ms=duracion_ms,
        )
        self._renders.agregar(render)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="render.terminado",
            detalle={"render_id": str(render.id), "calidad": calidad.value,
                     "duracion_ms": duracion_ms},
        ))
        self._auditoria.registrar(
            identidad, "render.ejecutar", str(render.id), "exito",
            {"calidad": calidad.value, "duracion_ms": duracion_ms,
             "profundidad": render.tiene_profundidad},
        )
        return {"render": self._a_dict(render)}

    @staticmethod
    def _a_dict(render) -> dict:
        return {
            "id": str(render.id),
            "proyecto_id": str(render.proyecto_id),
            "escena_id": str(render.escena_id),
            "calidad": render.calidad.value,
            "formato": render.formato,
            "ancho": render.ancho,
            "alto": render.alto,
            "hash_sha256": render.hash_sha256,
            "duracion_ms": render.duracion_ms,
            "tiene_profundidad": render.tiene_profundidad,
            "mime": render.mime,
            "creado_en": render.creado_en.isoformat(),
        }

"""Casos de uso de proyeccion: registrar, calibrar y proyectar.

Pipeline real: CALIBRACION (homografia DLT) -> RENDER raster ->
WARP (mapeo inverso con offset de bbox) -> frame PNG entregado.
Los errores de render/warp se re-lanzan con contexto completo
(Ley 1: nunca un 500 opaco).
"""
from apps.laboratorio.domain.surface import Superficie
from apps.laboratorio.infrastructure.providers.renderer_raster import (
    MotorRenderRaster,
)
from apps.laboratorio.infrastructure.providers.warper import (
    caja_del_cuadrilatero,
    warpear,
)
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.shared.enums.surface_kind import SurfaceKind
from apps.laboratorio.shared.models.identifiers import nuevo_id

RES_PROYECCION = (640, 360)


class CasoRegistrarSuperficie:
    def __init__(self, repo_superficies, auditoria):
        self._repo = repo_superficies
        self._auditoria = auditoria

    def ejecutar(self, identidad, datos: dict) -> dict:
        if not isinstance(datos, dict):
            raise ValueError("Cuerpo invalido.")
        nombre = str(datos.get("nombre", "")).strip()
        if not nombre:
            raise ValueError("La superficie requiere nombre.")
        superficie = Superficie(
            id=nuevo_id("sup"),
            propietario_zid=identidad.zid,
            nombre=nombre[:200],
            tipo=SurfaceKind.validar(str(datos.get("tipo", "pared"))),
        )
        self._repo.agregar(superficie)
        self._auditoria.registrar(
            identidad, "superficie.registrar", str(superficie.id), "exito",
            {"tipo": superficie.tipo.value},
        )
        return {"superficie": self._a_dict(superficie)}

    @staticmethod
    def _a_dict(superficie) -> dict:
        """Serializacion COMPLETA: incluye corners y homografia."""
        return {
            "id": str(superficie.id),
            "propietario_zid": superficie.propietario_zid,
            "nombre": superficie.nombre,
            "tipo": superficie.tipo.value,
            "corners": list(superficie.corners),
            "homografia": list(superficie.homografia),
            "calibrada": superficie.calibrada,
            "creado_en": superficie.creado_en.isoformat(),
        }


class CasoCalibrarSuperficie:
    def __init__(self, repo_superficies, calibrador, auditoria):
        self._repo = repo_superficies
        self._calibrador = calibrador
        self._auditoria = auditoria

    def ejecutar(self, identidad, superficie_id: str, corners: list) -> dict:
        superficie = self._repo.obtener_exigir_de(identidad.zid, superficie_id)
        if superficie.calibrada:
            raise ValueError("La superficie ya esta calibrada.")
        superficie.definir_corners(corners)
        H = self._calibrador.calibrar(
            superficie.corners, RES_PROYECCION[0], RES_PROYECCION[1]
        )
        superficie.marcar_calibrada(H)
        self._repo.actualizar_calibracion(superficie)
        self._auditoria.registrar(
            identidad, "superficie.calibrar", str(superficie.id), "exito",
            {"modo": "manual_4_puntos", "homografia_ok": True},
        )
        return {"superficie": CasoRegistrarSuperficie._a_dict(superficie)}


class CasoProyectarEnVivo:
    def __init__(self, repo_superficies, repo_escenas, repo_proyectos, auditoria):
        self._superficies = repo_superficies
        self._escenas = repo_escenas
        self._proyectos = repo_proyectos
        self._auditoria = auditoria

    def ejecutar(self, identidad, escena_id: str, superficie_id: str) -> tuple:
        escena = self._escenas.obtener_exigir(escena_id)
        proyecto = self._proyectos.obtener_exigir(str(escena.proyecto_id))
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        superficie = self._superficies.obtener_exigir_de(
            identidad.zid, superficie_id
        )
        if not superficie.calibrada:
            raise ValueError(
                "La superficie no esta calibrada: define sus 4 esquinas "
                "antes de proyectar."
            )
        if len(superficie.homografia) != 9:
            raise ValueError("La superficie calibrada no tiene homografia valida.")
        motor = MotorRenderRaster()
        try:
            resultado = motor.renderizar(
                escena,
                {"ancho": RES_PROYECCION[0], "alto": RES_PROYECCION[1]},
            )
            x0, y0, w, h = caja_del_cuadrilatero(superficie.corners)
            frame = warpear(
                resultado.imagen_bytes, superficie.homografia, w, h,
                origen_x=float(x0), origen_y=float(y0),
            )
        except Exception as exc:
            raise ValueError(
                "Proyeccion fallo en render/warp: "
                + type(exc).__name__ + ": " + str(exc)
            ) from exc
        self._auditoria.registrar(
            identidad, "proyeccion.frame", str(escena.id), "exito",
            {"superficie_id": str(superficie.id), "salida": [w, h]},
        )
        return 200, frame, {
            "Content-Type": "image/png",
            "Content-Disposition": "inline; filename=proyeccion_" + str(escena.id) + ".png",
            "X-Projection-Surface": str(superficie.id),
            "X-Projection-Mode": "frame-on-demand",
            "X-Projection-Salida": str(w) + "x" + str(h),
        }

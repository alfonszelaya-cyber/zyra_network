"""Escalera fotoreal: DUENO UNICO del mapeo calidad -> motor.

BORRADOR   -> SVG (MotorRenderSVG, sin profundidad)
ALTA       -> PNG 1920x1080 con relleno solido + profundidad
TRES_D     -> PNG con proyeccion perspectiva + profundidad
FOTORREAL  -> PNG 4K con iluminacion + profundidad

Las resoluciones salen de PoliticaCalidad (dueño de presets).
Nota honesta (Ley 1): el nivel FOTORREAL aplica iluminacion y
sombreado por capa reales; el fotorrealismo cinematografico
pleno (ray tracing, PBR completo) llega con el motor GPU.
"""
import time

from apps.laboratorio.domain.lighting import ProgramaLuz
from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.infrastructure.providers.renderer_3d import MotorRender3D
from apps.laboratorio.infrastructure.providers.renderer_photoreal import (
    MotorRenderFotoreal,
)
from apps.laboratorio.infrastructure.providers.renderer_raster import (
    MotorRenderRaster,
)
from apps.laboratorio.infrastructure.providers.renderer_svg import MotorRenderSVG
from apps.laboratorio.shared.enums.render_quality import RenderQuality
from apps.laboratorio.shared.exceptions.render_errors import (
    CalidadNoSoportadaError,
)
from apps.laboratorio.shared.interfaces.renderer import ResultadoRender
from apps.laboratorio.shared.policies.quality_policy import PoliticaCalidad


class EscaleraFotoreal:
    """Ejecuta el render en el motor de la calidad pedida."""

    def capacidades(self) -> dict:
        return {
            "escalera": RenderQuality.cadena(),
            "resoluciones": {
                q.value: [PoliticaCalidad.preset(q)["ancho"],
                          PoliticaCalidad.preset(q)["alto"]]
                for q in RenderQuality
            },
            "profundidad": {
                q.value: PoliticaCalidad.exige_profundidad(q)
                for q in RenderQuality
            },
            "nota": "FOTORREAL usa iluminacion real; ray tracing llega con el motor GPU",
        }

    def ejecutar(self, escena: Escena3D, calidad, programa_luz: ProgramaLuz = None) -> tuple:
        """Renderiza segun calidad; devuelve (ResultadoRender, duracion_ms)."""
        if isinstance(calidad, str):
            calidad = RenderQuality.validar(calidad)
        if not isinstance(calidad, RenderQuality):
            raise ValueError("Calidad de render invalida.")
        if not isinstance(escena, Escena3D):
            raise ValueError("Se esperaba una Escena3D.")
        preset = PoliticaCalidad.preset(calidad)
        inicio = time.perf_counter()
        if calidad is RenderQuality.BORRADOR:
            resultado = MotorRenderSVG().renderizar(
                escena.a_especificacion(), {}
            )
        elif calidad is RenderQuality.ALTA:
            resultado = MotorRenderRaster().renderizar(escena, preset)
        elif calidad is RenderQuality.TRES_D:
            resultado = MotorRender3D().renderizar(escena, preset)
        else:
            resultado = MotorRenderFotoreal().renderizar(escena, preset, programa_luz)
        duracion = round((time.perf_counter() - inicio) * 1000.0, 3)
        if PoliticaCalidad.exige_profundidad(calidad) and not resultado.tiene_profundidad:
            raise CalidadNoSoportadaError(
                "La calidad " + calidad.value + " exige profundidad y el motor no la produjo."
            )
        return resultado, duracion

"""Motor FOTOREAL: iluminacion real sobre el rasterizador en 4K.

Aplica el programa de luz de la escena (color dominante e
intensidad) con atenuacion por capa: el frente recibe mas luz
que el fondo. Es el primer escalon del fotorrealismo; el ray
tracing y el PBR completo llegan con el motor GPU.
"""
from apps.laboratorio.domain.lighting import ProgramaLuz
from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.infrastructure.providers.renderer_3d import (
    Z_POR_CAPA,
    MotorRender3D,
)
from apps.laboratorio.infrastructure.providers.renderer_raster import (
    PROFUNDIDAD_POR_CAPA,
    RasterizadorBase,
    hex_a_rgb,
)
from apps.laboratorio.shared.adapters.engine_adapter import AdaptadorMotor
from apps.laboratorio.shared.exceptions.render_errors import (
    EscenaVaciaError,
    RenderFallidoError,
)
from apps.laboratorio.shared.interfaces.renderer import Renderer, ResultadoRender

LUZ_POR_CAPA = {"fondo": 0.55, "medio": 0.75, "frente": 1.0}
LUZ_DEFECTO = ("#E2E8F0", 0.45)


class MotorRenderFotoreal(AdaptadorMotor, Renderer):
    """Calidad FOTORREAL: 4K, iluminacion por programa, profundidad."""

    def __init__(self):
        AdaptadorMotor.__init__(self, "renderer_photoreal", "renderer", "0.1.0")
        self.marcar_disponible()

    def capacidades(self) -> dict:
        return {
            "calidades": ["fotorreal"],
            "profundidad": True,
            "iluminacion": "programa de luz + atenuacion por capa",
            "resolucion": "4K segun PoliticaCalidad",
            "nota": "Ray tracing y PBR completo llegan con el motor GPU",
        }

    @staticmethod
    def _luz_de(programa_luz) -> tuple:
        """Color e intensidad de luz desde el programa real o defecto."""
        if programa_luz is None:
            return (
                hex_a_rgb(LUZ_DEFECTO[0]), float(LUZ_DEFECTO[1])
            )
        if not isinstance(programa_luz, ProgramaLuz):
            raise RenderFallidoError("Programa de luz invalido.")
        color = hex_a_rgb(programa_luz.color_dominate)
        mejor_intensidad = 0.0
        for paso in programa_luz.pasos:
            intensidad = float(paso.get("intensidad", 0.0))
            if intensidad > mejor_intensidad:
                mejor_intensidad = intensidad
        return color, max(0.05, min(1.0, mejor_intensidad))

    def renderizar(self, escena, opciones, programa_luz=None) -> ResultadoRender:
        if not isinstance(escena, Escena3D):
            raise RenderFallidoError("Se esperaba una Escena3D.")
        if not escena.es_renderizable:
            raise EscenaVaciaError("La escena no tiene objetos.")
        ancho = int(opciones.get("ancho", escena.ancho))
        alto = int(opciones.get("alto", escena.alto))
        luz_rgb, luz_int = self._luz_de(programa_luz)
        proyector = MotorRender3D()
        cx, cy = ancho / 2.0, alto / 2.0
        lienzo = RasterizadorBase(ancho, alto, (15, 23, 42))
        sx = ancho / escena.ancho
        sy = alto / escena.alto
        escala_texto = max(2, int(round(min(sx, sy) * 2)))
        orden = ("fondo", "medio", "frente")
        for capa in orden:
            z = Z_POR_CAPA[capa]
            depth_val = PROFUNDIDAD_POR_CAPA[capa]
            factor = LUZ_POR_CAPA[capa]
            ambiente = 1.0 - luz_int
            for obj in escena.objetos:
                if obj.get("capa", "medio") != capa:
                    continue
                base = hex_a_rgb(obj["color"])
                color = tuple(
                    max(0, min(255, int(
                        c * (ambiente + luz_int * factor * (l / 255.0))
                    )))
                    for c, l in zip(base, luz_rgb)
                )
                if obj["forma"] == "rect":
                    x1 = proyector._proyectar(obj["x"] * sx, cx, z)
                    y1 = proyector._proyectar(obj["y"] * sy, cy, z)
                    x2 = proyector._proyectar((obj["x"] + obj["w"]) * sx, cx, z)
                    y2 = proyector._proyectar((obj["y"] + obj["h"]) * sy, cy, z)
                    lienzo.rect(x1, y1, x2 - x1, y2 - y1, color, depth_val)
                elif obj["forma"] == "circle":
                    cxp = proyector._proyectar(obj["cx"] * sx, cx, z)
                    cyp = proyector._proyectar(obj["cy"] * sy, cy, z)
                    rp = obj["r"] * min(sx, sy) * (3.0 / (3.0 + z))
                    lienzo.circle(cxp, cyp, rp, color, depth_val)
                else:
                    lienzo.texto(
                        proyector._proyectar(obj["x"] * sx, cx, z),
                        proyector._proyectar(obj["y"] * sy, cy, z),
                        obj["contenido"], color, depth_val, escala_texto,
                    )
        return ResultadoRender(
            imagen_bytes=lienzo.imagen_png(),
            profundidad_bytes=lienzo.profundidad_png(),
            ancho=ancho,
            alto=alto,
            metadata={
                "formato": "png", "motor": "renderer_photoreal",
                "profundidad": True, "iluminacion": True,
            },
        )

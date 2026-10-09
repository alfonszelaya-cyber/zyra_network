"""Motor 3D: proyeccion perspectiva REAL sobre el rasterizador.

Cada capa recibe una profundidad Z (fondo lejos, frente cerca) y
los objetos se proyectan hacia un punto de fuga central:
  escala = f / (f + z)   y   x' = cx + (x - cx) * escala
El resultado es un PNG con perspectiva verdadera + PROFUNDIDAD.
"""
from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.infrastructure.providers.renderer_raster import (
    PROFUNDIDAD_POR_CAPA,
    MotorRenderRaster,
    RasterizadorBase,
    hex_a_rgb,
)
from apps.laboratorio.shared.adapters.engine_adapter import AdaptadorMotor
from apps.laboratorio.shared.exceptions.render_errors import (
    EscenaVaciaError,
    RenderFallidoError,
)
from apps.laboratorio.shared.interfaces.renderer import Renderer, ResultadoRender

Z_POR_CAPA = {"fondo": 2.0, "medio": 1.0, "frente": 0.2}
DISTANCIA_FOCAL = 3.0


class MotorRender3D(AdaptadorMotor, Renderer):
    """Calidad 3D: perspectiva con punto de fuga + profundidad."""

    def __init__(self):
        AdaptadorMotor.__init__(self, "renderer_3d", "renderer", "1.0.0")
        self.marcar_disponible()

    def capacidades(self) -> dict:
        return {
            "calidades": ["3d"],
            "profundidad": True,
            "proyeccion": "perspectiva con punto de fuga central",
            "z_por_capa": Z_POR_CAPA,
        }

    @staticmethod
    def _proyectar(valor, centro, z) -> float:
        """Proyeccion perspectiva de una coordenada sobre un eje."""
        escala = DISTANCIA_FOCAL / (DISTANCIA_FOCAL + z)
        return centro + (valor - centro) * escala

    def renderizar(self, escena, opciones) -> ResultadoRender:
        if not isinstance(escena, Escena3D):
            raise RenderFallidoError("Se esperaba una Escena3D.")
        if not escena.es_renderizable:
            raise EscenaVaciaError("La escena no tiene objetos.")
        ancho = int(opciones.get("ancho", escena.ancho))
        alto = int(opciones.get("alto", escena.alto))
        cx, cy = ancho / 2.0, alto / 2.0
        lienzo = RasterizadorBase(ancho, alto, (15, 23, 42))
        sx = ancho / escena.ancho
        sy = alto / escena.alto
        escala_texto = max(2, int(round(min(sx, sy) * 2)))
        orden = ("fondo", "medio", "frente")
        for capa in orden:
            z = Z_POR_CAPA[capa]
            depth_val = PROFUNDIDAD_POR_CAPA[capa]
            for obj in escena.objetos:
                if obj.get("capa", "medio") != capa:
                    continue
                color = hex_a_rgb(obj["color"])
                if obj["forma"] == "rect":
                    x1 = self._proyectar(obj["x"] * sx, cx, z)
                    y1 = self._proyectar(obj["y"] * sy, cy, z)
                    x2 = self._proyectar((obj["x"] + obj["w"]) * sx, cx, z)
                    y2 = self._proyectar((obj["y"] + obj["h"]) * sy, cy, z)
                    lienzo.rect(x1, y1, x2 - x1, y2 - y1, color, depth_val)
                elif obj["forma"] == "circle":
                    cxp = self._proyectar(obj["cx"] * sx, cx, z)
                    cyp = self._proyectar(obj["cy"] * sy, cy, z)
                    rp = obj["r"] * min(sx, sy) * (DISTANCIA_FOCAL / (DISTANCIA_FOCAL + z))
                    lienzo.circle(cxp, cyp, rp, color, depth_val)
                else:
                    lienzo.texto(
                        self._proyectar(obj["x"] * sx, cx, z),
                        self._proyectar(obj["y"] * sy, cy, z),
                        obj["contenido"], color, depth_val, escala_texto,
                    )
        return ResultadoRender(
            imagen_bytes=lienzo.imagen_png(),
            profundidad_bytes=lienzo.profundidad_png(),
            ancho=ancho,
            alto=alto,
            metadata={
                "formato": "png", "motor": "renderer_3d",
                "profundidad": True, "proyeccion": "perspectiva",
            },
        )

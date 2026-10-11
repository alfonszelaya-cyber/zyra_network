"""Motor 3D: perspectiva + CAMARA ORBITAL (mismo archivo)."""
import math

from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.infrastructure.providers.renderer_raster import (
    PROFUNDIDAD_POR_CAPA, RasterizadorBase, hex_a_rgb,
)
from apps.laboratorio.shared.adapters.engine_adapter import AdaptadorMotor
from apps.laboratorio.shared.exceptions.render_errors import (
    EscenaVaciaError, RenderFallidoError,
)
from apps.laboratorio.shared.interfaces.renderer import Renderer, ResultadoRender

Z_POR_CAPA = {"fondo": 2.0, "medio": 1.0, "frente": 0.2}
DISTANCIA_FOCAL = 3.0


class MotorRender3D(AdaptadorMotor, Renderer):
    def __init__(self):
        AdaptadorMotor.__init__(self, "renderer_3d", "renderer", "1.0.0")
        self.marcar_disponible()

    def capacidades(self) -> dict:
        return {"calidades": ["3d"], "profundidad": True,
                "proyeccion": "perspectiva con punto de fuga central", "z_por_capa": Z_POR_CAPA}

    @staticmethod
    def _proyectar(valor, centro, z):
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
        for capa in ("fondo", "medio", "frente"):
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
                    lienzo.texto(self._proyectar(obj["x"] * sx, cx, z),
                                 self._proyectar(obj["y"] * sy, cy, z),
                                 obj["contenido"], color, depth_val, escala_texto)
        return ResultadoRender(
            imagen_bytes=lienzo.imagen_png(), profundidad_bytes=lienzo.profundidad_png(),
            ancho=ancho, alto=alto,
            metadata={"formato": "png", "motor": "renderer_3d",
                      "profundidad": True, "proyeccion": "perspectiva"})


class CamaraOrbital:
    def __init__(self, distancia=3.0, azimut=0.0, elevacion=35.0):
        d = float(distancia)
        if not 1.0 <= d <= 10.0:
            raise ValueError("distancia entre 1 y 10.")
        self.distancia = d
        self.azimut = float(azimut) % 360.0
        e = float(elevacion)
        if not 5.0 <= e <= 85.0:
            raise ValueError("elevacion entre 5 y 85.")
        self.elevacion = e

    def girar(self, d_azimut, d_elevacion) -> dict:
        self.azimut = (self.azimut + float(d_azimut)) % 360.0
        self.elevacion = max(5.0, min(85.0, self.elevacion + float(d_elevacion)))
        return self.estado()

    def zoom(self, factor) -> dict:
        self.distancia = max(1.0, min(10.0, self.distancia * float(factor)))
        return self.estado()

    def estado(self) -> dict:
        return {"azimut": round(self.azimut, 2), "elevacion": round(self.elevacion, 2),
                "distancia": round(self.distancia, 3)}


class MotorRenderOrbital(AdaptadorMotor):
    def __init__(self):
        AdaptadorMotor.__init__(self, "renderer_orbital", "renderer", "1.0.0")
        self.marcar_disponible()

    def capacidades(self) -> dict:
        return {"proyeccion": "orbital 2.5D", "profundidad": True, "determinista": True}

    @staticmethod
    def _transformar(px, py, cx, cy, cos_a, sin_a, el, escala):
        dx, dy = px - cx, py - cy
        return (cx + (dx * cos_a - dy * sin_a) * escala,
                cy + (dx * sin_a + dy * cos_a) * el * escala)

    def renderizar_orbital(self, escena, opciones, camara) -> ResultadoRender:
        if not isinstance(escena, Escena3D):
            raise RenderFallidoError("Se esperaba una Escena3D.")
        if not escena.es_renderizable:
            raise EscenaVaciaError("La escena no tiene objetos.")
        if not isinstance(camara, CamaraOrbital):
            raise RenderFallidoError("Se esperaba una CamaraOrbital.")
        ancho = int(opciones.get("ancho", escena.ancho))
        alto = int(opciones.get("alto", escena.alto))
        lienzo = RasterizadorBase(ancho, alto, (15, 23, 42))
        sx = ancho / escena.ancho
        sy = alto / escena.alto
        cx, cy = ancho / 2.0, alto / 2.0
        az = math.radians(camara.azimut)
        el = math.sin(math.radians(camara.elevacion))
        cos_a, sin_a = math.cos(az), math.sin(az)
        f = camara.distancia
        for capa in ("fondo", "medio", "frente"):
            z = Z_POR_CAPA[capa] + (1.0 - el) * 0.5
            escala = f / (f + z)
            depth_val = PROFUNDIDAD_POR_CAPA[capa]
            for obj in escena.objetos:
                if obj.get("capa", "medio") != capa:
                    continue
                color = hex_a_rgb(obj["color"])
                if obj["forma"] == "rect":
                    x1, y1 = self._transformar(obj["x"] * sx, obj["y"] * sy, cx, cy, cos_a, sin_a, el, escala)
                    x2, y2 = self._transformar((obj["x"] + obj["w"]) * sx, (obj["y"] + obj["h"]) * sy, cx, cy, cos_a, sin_a, el, escala)
                    lienzo.rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1), color, depth_val)
                elif obj["forma"] == "circle":
                    px, py = self._transformar(obj["cx"] * sx, obj["cy"] * sy, cx, cy, cos_a, sin_a, el, escala)
                    lienzo.circle(px, py, obj["r"] * min(sx, sy) * escala, color, depth_val)
                else:
                    px, py = self._transformar(obj["x"] * sx, obj["y"] * sy, cx, cy, cos_a, sin_a, el, escala)
                    lienzo.texto(px, py, obj["contenido"], color, depth_val,
                                 max(2, int(round(min(sx, sy) * 2))))
        return ResultadoRender(
            imagen_bytes=lienzo.imagen_png(), profundidad_bytes=lienzo.profundidad_png(),
            ancho=ancho, alto=alto,
            metadata={"formato": "png", "motor": "renderer_orbital",
                      "proyeccion": "orbital 2.5D", "azimut": camara.azimut,
                      "elevacion": camara.elevacion, "distancia": camara.distancia,
                      "profundidad": True})

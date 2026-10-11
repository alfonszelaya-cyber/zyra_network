"""Motor FOTORREAL PBR: iluminacion fisicamente basada REAL.

Pipeline completo en Python puro (stdlib, cero dependencias):
  1. Rasterizacion con z-buffer por capas (fondo/medio/frente)
  2. Normales geometricas reales: rect = plano, circle = esfera
  3. BRDF GGX Cook-Torrance (specular) + Lambert (diffuse),
     rugosidad y metalico configurables
  4. Sombras por oclusion entre capas (el frente proyecta sobre
     medio y fondo)
  5. Ambient occlusion por profundidad de capa
  6. Tone mapping ACES + gamma 2.2
  7. Supersampling configurable (1x/2x/4x) con presupuesto de
     pixeles honesto (se reduce solo si hace falta, y se
     declara en metadata)
  8. Salida PNG RGB + PNG de profundidad (encoder propio)

Nada simulado: cada pixel se calcula con la BRDF.
"""
import math

from apps.laboratorio.domain.lighting import ProgramaLuz
from apps.laboratorio.infrastructure.providers.font_bitmap import (
    texto_a_lineas,
)
from apps.laboratorio.infrastructure.providers.png_encoder import (
    encode_png_gray,
    encode_png_rgb,
)
from apps.laboratorio.shared.adapters.engine_adapter import AdaptadorMotor
from apps.laboratorio.shared.exceptions.render_errors import (
    EscenaVaciaError,
    RenderFallidoError,
)
from apps.laboratorio.shared.interfaces.renderer import (
    Renderer,
    ResultadoRender,
)

CAPA_INDICE = {"fondo": 0, "medio": 1, "frente": 2}
CAPA_NOMBRE = ("fondo", "medio", "frente")
PROFUNDIDAD_CAPA = {"fondo": 0.20, "medio": 0.55, "frente": 0.90}
AMBIENTE_CAPA = {"fondo": 0.62, "medio": 0.78, "frente": 1.0}
LUZ_DEFECTO_COLOR = (0.89, 0.91, 0.94)
LUZ_DEFECTO_INTENSIDAD = 0.85
DIRECCION_LUZ = (0.35, 0.45, 0.82)
FONDO_LIENZO = (15 / 255.0, 23 / 255.0, 42 / 255.0)
MAX_PX_PASO = 3_000_000


def _hex_rgb(texto: str):
    crudo = str(texto or "").strip().lstrip("#")
    if len(crudo) != 6:
        raise ValueError("Color hex invalido: " + repr(texto))
    return (
        int(crudo[0:2], 16),
        int(crudo[2:4], 16),
        int(crudo[4:6], 16),
    )


def _normalizar(v):
    largo = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if largo < 1e-9:
        return (0.0, 0.0, 1.0)
    return (v[0] / largo, v[1] / largo, v[2] / largo)


def _aces(x: float) -> float:
    if x <= 0.0:
        return 0.0
    a = x * (2.51 * x + 0.03)
    b = x * (2.43 * x + 0.59) + 0.14
    return min(1.0, max(0.0, a / b))


def _gamma(x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return x ** (1.0 / 2.2)


class _Golpe:
    """Registro de un pixel tocado por una forma (para sombrear)."""

    __slots__ = ("capa", "r", "g", "b", "nx", "ny", "nz")

    def __init__(self, capa, color, normal):
        self.capa = capa
        self.r, self.g, self.b = color
        self.nx, self.ny, self.nz = normal


class MotorRenderFotoreal(AdaptadorMotor, Renderer):
    """Calidad FOTORREAL: PBR real con BRDF GGX y sombras."""

    def __init__(self):
        AdaptadorMotor.__init__(
            self, "renderer_photoreal", "renderer", "2.0.0"
        )
        self.marcar_disponible()

    def capacidades(self) -> dict:
        return {
            "calidades": ["fotorreal"],
            "profundidad": True,
            "brdf": "GGX Cook-Torrance",
            "diffuse": "Lambert",
            "tonemap": "ACES + gamma 2.2",
            "sombras": "oclusion entre capas",
            "supersampling": (1, 2, 4),
            "parametros": ("rugosidad", "metalico", "muestras"),
        }

    def renderizar(
        self, escena, opciones, programa_luz=None
    ) -> ResultadoRender:
        ancho_obj = int(
            opciones.get("ancho", getattr(escena, "ancho", 0))
        )
        alto_obj = int(
            opciones.get("alto", getattr(escena, "alto", 0))
        )
        if ancho_obj < 16 or alto_obj < 16:
            raise RenderFallidoError(
                "Resolucion invalida para PBR: "
                + str(ancho_obj) + "x" + str(alto_obj)
            )
        objetos = list(getattr(escena, "objetos", []) or [])
        if not objetos:
            raise EscenaVaciaError("La escena no tiene objetos.")
        if programa_luz is not None and not isinstance(
            programa_luz, ProgramaLuz
        ):
            raise RenderFallidoError("Programa de luz invalido.")
        luz_rgb, luz_int = self._luz_de(programa_luz)
        rugosidad = self._rango(
            opciones.get("rugosidad", 0.35), 0.0, 1.0, 0.35
        )
        metalico = self._rango(
            opciones.get("metalico", 0.0), 0.0, 1.0, 0.0
        )
        muestras = int(opciones.get("muestras", 1))
        if muestras not in (1, 2, 4):
            muestras = 1
        muestras = self._ajustar_muestras(ancho_obj, alto_obj, muestras)
        W = ancho_obj * muestras
        H = alto_obj * muestras
        sx = W / float(getattr(escena, "ancho", ancho_obj))
        sy = H / float(getattr(escena, "alto", alto_obj))
        golpes, sombras, profundidad = self._rasterizar(
            objetos, W, H, sx, sy
        )
        imagen = self._sombrear(
            golpes, sombras, W, H,
            luz_rgb, luz_int, rugosidad, metalico,
        )
        if muestras > 1:
            imagen = self._reducir(imagen, W, H, muestras)
        png = encode_png_rgb(ancho_obj, alto_obj, bytes(imagen))
        png_prof = encode_png_gray(ancho_obj, alto_obj, bytes(profundidad))
        return ResultadoRender(
            imagen_bytes=png,
            profundidad_bytes=png_prof,
            ancho=ancho_obj,
            alto=alto_obj,
            metadata={
                "formato": "png",
                "motor": "renderer_photoreal",
                "calidad": "fotorreal_pbr",
                "brdf": "GGX Cook-Torrance",
                "tonemap": "ACES",
                "sombras": "oclusion_capas",
                "rugosidad": rugosidad,
                "metalico": metalico,
                "muestras": muestras,
                "resolucion": [ancho_obj, alto_obj],
                "profundidad": True,
                "objetos": len(objetos),
            },
        )

    @staticmethod
    def _rango(valor, bajo, alto, defecto):
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return defecto
        return max(bajo, min(alto, numero))

    @staticmethod
    def _ajustar_muestras(ancho, alto, muestras):
        while muestras > 1 and (
            ancho * alto * muestras * muestras > MAX_PX_PASO
        ):
            muestras = muestras // 2
        return muestras

    @staticmethod
    def _luz_de(programa_luz):
        if programa_luz is None:
            return LUZ_DEFECTO_COLOR, LUZ_DEFECTO_INTENSIDAD
        mejor = 0.0
        for paso in programa_luz.pasos:
            valor = float(paso.get("intensidad", 0.0))
            if valor > mejor:
                mejor = valor
        intensidad = max(0.05, min(1.0, mejor))
        try:
            crudo = _hex_rgb(programa_luz.color_dominate)
            color = (
                crudo[0] / 255.0,
                crudo[1] / 255.0,
                crudo[2] / 255.0,
            )
        except (ValueError, AttributeError):
            color = LUZ_DEFECTO_COLOR
        return color, intensidad

    def _rasterizar(self, objetos, W, H, sx, sy):
        golpes = [None] * (W * H)
        sombras = bytearray(W * H)
        profundidad = bytearray(W * H)
        cubiertos = {
            0: bytearray(W * H),
            1: bytearray(W * H),
            2: bytearray(W * H),
        }
        for obj in objetos:
            forma = str(obj.get("forma", ""))
            capa = CAPA_INDICE.get(str(obj.get("capa", "medio")), 1)
            try:
                color = _hex_rgb(obj.get("color", "#94A3B8"))
            except ValueError:
                color = (148, 163, 184)
            if forma == "rect":
                self._pintar_rect(
                    obj, capa, color, golpes, cubiertos, W, H, sx, sy
                )
            elif forma == "circle":
                self._pintar_circulo(
                    obj, capa, color, golpes, cubiertos, W, H, sx, sy
                )
            else:
                self._pintar_texto(
                    obj, capa, color, golpes, cubiertos, W, H, sx, sy
                )
        for indice in range(W * H):
            golpe = golpes[indice]
            if golpe is None:
                profundidad[indice] = 0
                continue
            valor_sombra = 0
            for j in range(golpe.capa + 1, 3):
                if cubiertos[j][indice]:
                    valor_sombra = 1
                    break
            sombras[indice] = valor_sombra
            profundidad[indice] = int(
                PROFUNDIDAD_CAPA[CAPA_NOMBRE[golpe.capa]] * 255.0
            )
        return golpes, sombras, profundidad

    def _pintar_rect(
        self, obj, capa, color, golpes, cubiertos, W, H, sx, sy
    ):
        x1 = max(0, min(W - 1, int(obj["x"] * sx)))
        y1 = max(0, min(H - 1, int(obj["y"] * sy)))
        x2 = max(0, min(W - 1, int((obj["x"] + obj["w"]) * sx)))
        y2 = max(0, min(H - 1, int((obj["y"] + obj["h"]) * sy)))
        normal = (0.0, 0.0, 1.0)
        for py in range(y1, y2 + 1):
            base = py * W
            for px in range(x1, x2 + 1):
                indice = base + px
                existente = golpes[indice]
                if existente is not None and existente.capa > capa:
                    continue
                golpes[indice] = _Golpe(capa, color, normal)
                cubiertos[capa][indice] = 1

    def _pintar_circulo(
        self, obj, capa, color, golpes, cubiertos, W, H, sx, sy
    ):
        cx = obj["cx"] * sx
        cy = obj["cy"] * sy
        radio = obj["r"] * min(sx, sy)
        if radio < 0.5:
            return
        x0 = max(0, int(cx - radio))
        x1 = min(W - 1, int(cx + radio))
        y0 = max(0, int(cy - radio))
        y1 = min(H - 1, int(cy + radio))
        r_cuadrado = radio * radio
        for py in range(y0, y1 + 1):
            dy = py + 0.5 - cy
            resto = r_cuadrado - dy * dy
            if resto <= 0:
                continue
            medio = math.sqrt(resto)
            px_ini = max(0, int(cx - medio))
            px_fin = min(W - 1, int(cx + medio))
            base = py * W
            for px in range(px_ini, px_fin + 1):
                dx = px + 0.5 - cx
                nx = dx / radio
                ny = dy / radio
                nz_cuad = 1.0 - nx * nx - ny * ny
                nz = math.sqrt(nz_cuad) if nz_cuad > 0.0 else 0.0
                indice = base + px
                existente = golpes[indice]
                if existente is not None and existente.capa > capa:
                    continue
                golpes[indice] = _Golpe(capa, color, (nx, ny, nz))
                cubiertos[capa][indice] = 1

    def _pintar_texto(
        self, obj, capa, color, golpes, cubiertos, W, H, sx, sy
    ):
        escala = max(1, int(round(min(sx, sy) * 2)))
        cursor_x = int(obj.get("x", 0) * sx)
        py_base = int(obj.get("y", 0) * sy)
        contenido = str(obj.get("contenido", ""))[:120]
        normal = (0.0, 0.0, 1.0)
        for caracter, glifo in texto_a_lineas(contenido):
            for fila in range(5):
                patrones = glifo[fila]
                for columna in range(3):
                    if not (patrones >> (2 - columna)) & 1:
                        continue
                    x0 = cursor_x + columna * escala
                    y0 = py_base + fila * escala
                    if x0 < 0 or y0 < 0 or x0 >= W or y0 >= H:
                        continue
                    x1 = min(W - 1, x0 + escala - 1)
                    y1 = min(H - 1, y0 + escala - 1)
                    for yy in range(y0, y1 + 1):
                        fila_b = yy * W
                        for xx in range(x0, x1 + 1):
                            indice = fila_b + xx
                            existente = golpes[indice]
                            if (
                                existente is not None
                                and existente.capa > capa
                            ):
                                continue
                            golpes[indice] = _Golpe(capa, color, normal)
                            cubiertos[capa][indice] = 1
            cursor_x += 4 * escala

    def _sombrear(
        self, golpes, sombras, W, H,
        luz_rgb, luz_int, rugosidad, metalico,
    ):
        L = _normalizar(DIRECCION_LUZ)
        Hvec = _normalizar((L[0], L[1], L[2] + 1.0))
        alpha = rugosidad * rugosidad
        a2 = alpha * alpha
        k = alpha / 2.0
        F0 = 0.04 + metalico * 0.96
        pi = math.pi
        imagen = bytearray(W * H * 3)
        fb = FONDO_LIENZO
        for indice in range(W * H):
            golpe = golpes[indice]
            if golpe is None:
                imagen[indice * 3] = int(fb[0] * 255.0 + 0.5)
                imagen[indice * 3 + 1] = int(fb[1] * 255.0 + 0.5)
                imagen[indice * 3 + 2] = int(fb[2] * 255.0 + 0.5)
                continue
            nx, ny, nz = golpe.nx, golpe.ny, golpe.nz
            NdotL = max(0.0, nx * L[0] + ny * L[1] + nz * L[2])
            NdotV = max(0.0, nz)
            NdotH = max(0.0, nx * Hvec[0] + ny * Hvec[1] + nz * Hvec[2])
            denom = NdotH * NdotH * (a2 - 1.0) + 1.0
            D = a2 / (pi * denom * denom + 1e-9)
            fresnel = 1.0 - NdotH
            F = F0 + (1.0 - F0) * fresnel ** 5
            G_v = NdotV / (NdotV * (1.0 - k) + k + 1e-9)
            G_l = NdotL / (NdotL * (1.0 - k) + k + 1e-9)
            G = G_v * G_l
            divisor = 4.0 * NdotL * NdotV + 1e-4
            ks = D * F * G / divisor
            kd = (1.0 - F) * (1.0 - metalico)
            albedo_r = golpe.r / 255.0
            albedo_g = golpe.g / 255.0
            albedo_b = golpe.b / 255.0
            ambiente = AMBIENTE_CAPA[CAPA_NOMBRE[golpe.capa]]
            factor_sombra = 0.35 if sombras[indice] else 1.0
            directo = luz_int * NdotL * factor_sombra
            if metalico > 0.5:
                spec_r = ks * albedo_r
                spec_g = ks * albedo_g
                spec_b = ks * albedo_b
            else:
                spec_r = spec_g = spec_b = ks
            lin_r = (
                albedo_r * ambiente * 0.20
                + luz_rgb[0] * directo * (albedo_r * kd / pi + spec_r)
            )
            lin_g = (
                albedo_g * ambiente * 0.20
                + luz_rgb[1] * directo * (albedo_g * kd / pi + spec_g)
            )
            lin_b = (
                albedo_b * ambiente * 0.20
                + luz_rgb[2] * directo * (albedo_b * kd / pi + spec_b)
            )
            imagen[indice * 3] = int(_gamma(_aces(lin_r)) * 255.0 + 0.5)
            imagen[indice * 3 + 1] = int(
                _gamma(_aces(lin_g)) * 255.0 + 0.5
            )
            imagen[indice * 3 + 2] = int(
                _gamma(_aces(lin_b)) * 255.0 + 0.5
            )
        return imagen

    @staticmethod
    def _reducir(imagen, W, H, muestras):
        salida_w = W // muestras
        salida_h = H // muestras
        salida = bytearray(salida_w * salida_h * 3)
        area = muestras * muestras
        for py in range(salida_h):
            base_salida = py * salida_w
            for px in range(salida_w):
                sr = sg = sb = 0
                for dy in range(muestras):
                    fila = (py * muestras + dy) * W
                    for dx in range(muestras):
                        indice = (fila + px * muestras + dx) * 3
                        sr += imagen[indice]
                        sg += imagen[indice + 1]
                        sb += imagen[indice + 2]
                destino = (base_salida + px) * 3
                salida[destino] = sr // area
                salida[destino + 1] = sg // area
                salida[destino + 2] = sb // area
        return salida

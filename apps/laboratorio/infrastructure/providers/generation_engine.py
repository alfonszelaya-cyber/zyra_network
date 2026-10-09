"""Motor de generacion: 7 formatos reales desde una Escena3D.

Fase 4: naked3d (parallax sin lentes), holograma (proyeccion
estilizada) y oligrama (mapa de red) se suman a imagen, pagina,
modelo y animacion. Cero duplicacion: reutiliza MotorRenderSVG.
El video MP4 NO se simula: llega en fase 6.
"""
import json

from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.infrastructure.providers.hologram_engine import MotorHolograma
from apps.laboratorio.infrastructure.providers.naked3d_engine import MotorNaked3D
from apps.laboratorio.infrastructure.providers.oligram_engine import MotorOligrama
from apps.laboratorio.infrastructure.providers.renderer_svg import MotorRenderSVG
from apps.laboratorio.infrastructure.security.html_sanitizer import escapar


class MotorGeneracionReal:
    """Genera entregables reales desde una Escena3D."""

    def __init__(self):
        self._renderer = MotorRenderSVG()
        self._naked3d = MotorNaked3D()
        self._holograma = MotorHolograma()
        self._oligrama = MotorOligrama()

    def capacidades(self) -> dict:
        return {
            "disponibles": (
                "imagen", "pagina", "modelo", "animacion",
                "naked3d", "holograma", "oligrama",
            ),
            "no_disponibles": {
                "video_mp4": "El motor de secuencia llega en fase 6",
                "modelo_gltf_completo": "Se amplia en fase 6 con mallas reales",
            },
        }

    def generar(self, escena: Escena3D, formato: str) -> bytes:
        if not isinstance(escena, Escena3D):
            raise ValueError("Se esperaba una Escena3D.")
        if formato == "imagen":
            return self._generar_imagen(escena)
        if formato == "pagina":
            return self._generar_pagina(escena)
        if formato == "modelo":
            return self._generar_modelo(escena)
        if formato == "animacion":
            return self._generar_animacion(escena)
        if formato == "naked3d":
            return self._naked3d.generar(escena)
        if formato == "holograma":
            return self._holograma.generar(escena)
        if formato == "oligrama":
            return self._oligrama.generar(escena)
        raise ValueError(
            "El formato '" + str(formato)
            + "' no esta disponible. El video MP4 llega con el motor de secuencia (fase 6)."
        )

    def _generar_imagen(self, escena: Escena3D) -> bytes:
        resultado = self._renderer.renderizar(escena.a_especificacion(), {})
        return resultado.imagen_bytes

    def _generar_pagina(self, escena: Escena3D) -> bytes:
        import base64 as b64
        svg = self._generar_imagen(escena).decode("utf-8")
        filas = []
        for i, obj in enumerate(escena.objetos, 1):
            detalle = ", ".join(
                k + "=" + escapar(v) for k, v in sorted(obj.items())
                if k not in ("forma", "color")
            )
            filas.append(
                "<tr><td>" + str(i) + "</td>"
                + '<td><span class="pill">' + escapar(obj["forma"]) + "</span></td>"
                + '<td><span class="pill">' + escapar(obj.get("capa", "medio")) + "</span></td>"
                + '<td><code style="color:#93C5FD">' + escapar(obj["color"]) + "</code></td>"
                + "<td>" + detalle + "</td></tr>"
            )
        html = (
            "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<title>" + escapar(escena.nombre) + "</title>"
            "<style>body{background:#0B1220;color:#E2E8F0;font-family:system-ui,sans-serif;padding:24px}"
            "h1{font-size:22px}.pill{background:rgba(37,99,235,.15);color:#93C5FD;border-radius:999px;padding:2px 10px;font-size:12px}"
            "table{border-collapse:collapse;width:100%;max-width:860px}td,th{border-bottom:1px solid #1E293B;padding:8px;text-align:left;font-size:14px}"
            "th{color:#94A3B8;font-size:12px;text-transform:uppercase}img{max-width:100%;border-radius:12px;border:1px solid #1E293B}</style></head><body>"
            "<h1>" + escapar(escena.nombre) + "</h1>"
            "<p style='color:#94A3B8'>Escena generada por ZYRA LABORATORIO - " + str(len(escena.objetos)) + " objetos</p>"
            "<img alt='render de la escena' src='data:image/svg+xml;base64,"
            + b64.b64encode(svg.encode("utf-8")).decode("ascii")
            + "'><h2 style='font-size:16px;margin-top:20px'>Objetos y profundidad</h2>"
            "<table><thead><tr><th>#</th><th>Forma</th><th>Capa</th><th>Color</th><th>Parametros</th></tr></thead><tbody>"
            + "\n".join(filas) + "</tbody></table></body></html>"
        )
        return html.encode("utf-8")

    def _generar_modelo(self, escena: Escena3D) -> bytes:
        nodos = []
        for i, obj in enumerate(escena.objetos):
            nodo = {
                "name": obj["forma"] + "_" + str(i),
                "extras": {
                    "color": obj["color"], "forma": obj["forma"],
                    "capa": obj.get("capa", "medio"),
                },
            }
            if obj["forma"] == "rect":
                nodo["translation"] = [obj["x"], obj["y"], 0.0]
                nodo["extras"]["tamano"] = [obj["w"], obj["h"]]
            elif obj["forma"] == "circle":
                nodo["translation"] = [obj["cx"], obj["cy"], 0.0]
                nodo["extras"]["radio"] = obj["r"]
            else:
                nodo["translation"] = [obj["x"], obj["y"], 0.0]
                nodo["extras"]["texto"] = obj["contenido"]
            nodos.append(nodo)
        modelo = {
            "asset": {"version": "2.0", "generator": "ZYRA LABORATORIO glTF-lite"},
            "scene": 0,
            "scenes": [{"name": escapar(escena.nombre), "nodes": list(range(len(nodos)))}],
            "nodes": nodos,
            "extras": {
                "dimensiones": [escena.ancho, escena.alto],
                "nota": "glTF-lite exportado por LABORATORIO (fase 4)",
            },
        }
        return json.dumps(modelo, ensure_ascii=True, indent=2).encode("utf-8")

    def _generar_animacion(self, escena: Escena3D) -> bytes:
        if not escena.objetos:
            from apps.laboratorio.shared.exceptions.render_errors import RenderFallidoError
            raise RenderFallidoError("La escena no tiene objetos para animar.")
        resultado = self._renderer.renderizar(escena.a_especificacion(), {})
        svg = resultado.imagen_bytes.decode("utf-8")
        centro_x = escena.ancho / 2.0
        centro_y = escena.alto / 2.0
        animacion = (
            '<animateTransform attributeName="transform" attributeType="XML" '
            'type="rotate" from="0 ' + str(centro_x) + " " + str(centro_y)
            + '" to="360 ' + str(centro_x) + " " + str(centro_y)
            + '" dur="12s" repeatCount="indefinite"/>'
        )
        if "</svg>" in svg:
            svg = svg.replace("</svg>", animacion + "</svg>", 1)
        return svg.encode("utf-8")

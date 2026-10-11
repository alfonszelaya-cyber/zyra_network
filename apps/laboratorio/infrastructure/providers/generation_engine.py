"""Motor de generacion: 8 formatos reales desde una Escena3D.

imagen/pagina/animacion: SVG y HTML reales.
modelo: glTF 2.0 JSON con buffer base64 embebido.
modelo_glb: GLB binario (JSON chunk + BIN chunk, alineado a 4).
naked3d/holograma/oligrama: motores dedicados.
Mallas reales POSITION VEC3 + indices u16, accessors con min/max,
materiales pbrMetallicRoughness. Y-arriba; Z por capa
(fondo 0.0, medio 0.5, frente 1.0). Textos NO se malla-fican
(declarados en extras: sin geometria falsa).
"""
import base64 as b64
import json
import math
import struct

from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.infrastructure.providers.hologram_engine import MotorHolograma
from apps.laboratorio.infrastructure.providers.naked3d_engine import MotorNaked3D
from apps.laboratorio.infrastructure.providers.oligram_engine import MotorOligrama
from apps.laboratorio.infrastructure.providers.renderer_svg import MotorRenderSVG
from apps.laboratorio.infrastructure.security.html_sanitizer import escapar

Z_CAPA = {"fondo": 0.0, "medio": 0.5, "frente": 1.0}
SEG_CIRCULO = 24


def _hex_rgb(texto: str):
    crudo = str(texto or "").strip().lstrip("#")
    if len(crudo) != 6:
        return (0.58, 0.64, 0.72)
    return (
        int(crudo[0:2], 16) / 255.0,
        int(crudo[2:4], 16) / 255.0,
        int(crudo[4:6], 16) / 255.0,
    )


def _empaquetar_glb(gltf: dict, binario: bytes) -> bytes:
    json_crudo = json.dumps(
        gltf, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    pad_json = (4 - len(json_crudo) % 4) % 4
    json_crudo += b" " * pad_json
    pad_bin = (4 - len(binario) % 4) % 4
    bin_crudo = binario + b"\x00" * pad_bin
    total = 12 + 8 + len(json_crudo) + 8 + len(bin_crudo)
    return (
        struct.pack("<III", 0x46546C67, 2, total)
        + struct.pack("<II", len(json_crudo), 0x4E4F534A)
        + json_crudo
        + struct.pack("<II", len(bin_crudo), 0x004E4942)
        + bin_crudo
    )


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
                "imagen", "pagina", "modelo", "modelo_glb",
                "animacion", "naked3d", "holograma", "oligrama",
            ),
            "gltf": "2.0 con mallas reales y materiales PBR",
            "glb": "contenedor binario JSON+BIN alineado a 4",
            "no_disponibles": {
                "video_mp4": "El motor de secuencia llega con el motor GPU",
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
        if formato == "modelo_glb":
            return self._generar_glb(escena)
        if formato == "animacion":
            return self._generar_animacion(escena)
        if formato == "naked3d":
            return self._naked3d.generar(escena)
        if formato == "holograma":
            return self._holograma.generar(escena)
        if formato == "oligrama":
            return self._oligrama.generar(escena)
        raise ValueError(
            "El formato '" + str(formato) + "' no esta disponible. Validos: "
            + ", ".join(self.capacidades()["disponibles"])
        )

    def _generar_imagen(self, escena: Escena3D) -> bytes:
        resultado = self._renderer.renderizar(escena.a_especificacion(), {})
        return resultado.imagen_bytes

    def _generar_pagina(self, escena: Escena3D) -> bytes:
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

    @staticmethod
    def _geometria_objeto(obj, alto):
        forma = str(obj.get("forma", ""))
        capa = str(obj.get("capa", "medio"))
        z = Z_CAPA.get(capa, 0.5)

        def punto(px, py):
            return (float(px), float(alto) - float(py), z)

        if forma == "rect":
            x, y, w, h = obj["x"], obj["y"], obj["w"], obj["h"]
            posiciones = [
                punto(x, y), punto(x + w, y),
                punto(x + w, y + h), punto(x, y + h),
            ]
            indices = [0, 1, 2, 0, 2, 3]
            return posiciones, indices
        if forma == "circle":
            cx, cy, r = float(obj["cx"]), float(obj["cy"]), float(obj["r"])
            posiciones = [punto(cx, cy)]
            for i in range(SEG_CIRCULO):
                ang = 2.0 * math.pi * i / SEG_CIRCULO
                posiciones.append(punto(
                    cx + r * math.cos(ang), cy + r * math.sin(ang)
                ))
            indices = []
            for i in range(1, SEG_CIRCULO):
                siguiente = i + 1 if i + 1 <= SEG_CIRCULO else 1
                indices.extend([0, i, siguiente])
            return posiciones, indices
        return None, None

    def _construir_gltf(self, escena: Escena3D, con_buffer_uri: bool):
        buffer_bin = bytearray()
        bufferViews = []
        accessors = []
        meshes = []
        nodes = []
        materials = []
        textos = []
        offset = 0
        for i, obj in enumerate(escena.objetos):
            forma = str(obj.get("forma", ""))
            if forma not in ("rect", "circle"):
                textos.append({
                    "indice": i, "forma": forma,
                    "contenido": str(obj.get("contenido", "")),
                    "capa": str(obj.get("capa", "medio")),
                })
                continue
            posiciones, indices = self._geometria_objeto(obj, escena.alto)
            if posiciones is None:
                continue
            plano = []
            for (px, py, pz) in posiciones:
                plano.extend((px, py, pz))
            datos_pos = struct.pack("<" + str(len(plano)) + "f", *plano)
            pad_pos = (4 - len(datos_pos) % 4) % 4
            datos_pos += b"\x00" * pad_pos
            datos_idx = struct.pack("<" + str(len(indices)) + "H", *indices)
            pad_idx = (4 - len(datos_idx) % 4) % 4
            datos_idx += b"\x00" * pad_idx
            vista_pos = len(bufferViews)
            bufferViews.append({
                "buffer": 0, "byteOffset": offset,
                "byteLength": len(datos_pos), "target": 34962,
            })
            offset += len(datos_pos)
            vista_idx = len(bufferViews)
            bufferViews.append({
                "buffer": 0, "byteOffset": offset,
                "byteLength": len(datos_idx), "target": 34963,
            })
            offset += len(datos_idx)
            acc_pos = len(accessors)
            accessors.append({
                "bufferView": vista_pos,
                "componentType": 5126,
                "count": len(posiciones),
                "type": "VEC3",
                "min": [min(plano[0::3]), min(plano[1::3]), min(plano[2::3])],
                "max": [max(plano[0::3]), max(plano[1::3]), max(plano[2::3])],
            })
            acc_idx = len(accessors)
            accessors.append({
                "bufferView": vista_idx,
                "componentType": 5123,
                "count": len(indices),
                "type": "SCALAR",
            })
            color = _hex_rgb(obj.get("color", "#94A3B8"))
            material = len(materials)
            materials.append({
                "pbrMetallicRoughness": {
                    "baseColorFactor": [color[0], color[1], color[2], 1.0],
                    "metallicFactor": 0.05,
                    "roughnessFactor": 0.55,
                },
                "name": "mat_" + forma + "_" + str(i),
            })
            mesh = len(meshes)
            meshes.append({
                "name": forma + "_" + str(i),
                "primitives": [{
                    "attributes": {"POSITION": acc_pos},
                    "indices": acc_idx,
                    "material": material,
                    "mode": 4,
                }],
            })
            nodes.append({
                "mesh": mesh,
                "name": forma + "_" + str(i),
                "extras": {
                    "capa": str(obj.get("capa", "medio")),
                    "color": str(obj.get("color", "")),
                },
            })
            buffer_bin += datos_pos
            buffer_bin += datos_idx
        binario = bytes(buffer_bin)
        if con_buffer_uri:
            uri = (
                "data:application/octet-stream;base64,"
                + b64.b64encode(binario).decode("ascii")
            )
            buffers = [{"byteLength": len(binario), "uri": uri}]
        else:
            buffers = [{"byteLength": len(binario)}]
        gltf = {
            "asset": {
                "version": "2.0",
                "generator": "ZYRA LABORATORIO glTF 2.0 real",
            },
            "scene": 0,
            "scenes": [{
                "name": escapar(escena.nombre),
                "nodes": list(range(len(nodes))),
            }],
            "nodes": nodes,
            "meshes": meshes,
            "materials": materials,
            "accessors": accessors,
            "bufferViews": bufferViews,
            "buffers": buffers,
            "extras": {
                "escena": [escena.ancho, escena.alto],
                "conversion": "Y-arriba; Z por capa fondo=0.0 medio=0.5 frente=1.0",
                "objetos_texto": textos,
                "nota": "los textos no se malla-fican (sin geometria falsa)",
            },
        }
        return gltf, binario

    def _generar_modelo(self, escena: Escena3D) -> bytes:
        gltf, _binario = self._construir_gltf(escena, con_buffer_uri=True)
        return json.dumps(gltf, ensure_ascii=True, indent=2).encode("utf-8")

    def _generar_glb(self, escena: Escena3D) -> bytes:
        gltf, binario = self._construir_gltf(escena, con_buffer_uri=False)
        return _empaquetar_glb(gltf, binario)

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

"""IMPRESION 3D: STL binario + G-code marlin real."""
import math
import struct


def _normal(tri):
    ax, ay, az = tri[0]
    bx, by, bz = tri[1]
    cx, cy, cz = tri[2]
    nx = (by - ay) * (cz - az) - (bz - az) * (cy - ay)
    ny = (bz - az) * (cx - ax) - (bx - ax) * (cz - az)
    nz = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    largo = math.sqrt(nx * nx + ny * ny + nz * nz)
    if largo < 1e-9:
        return (0.0, 0.0, 1.0)
    return (nx / largo, ny / largo, nz / largo)


class MotorImpresion3D:
    def capacidades(self) -> dict:
        return {"stl": "binario estandar", "gcode": "marlin estandar",
                "formas": ("rect=caja", "circle=cilindro"),
                "envio": "archivo .gcode a SD/USB de la impresora"}

    @staticmethod
    def _caja(x, y, z, w, d, h):
        p = [(x, y, z), (x + w, y, z), (x + w, y + d, z), (x, y + d, z),
             (x, y, z + h), (x + w, y, z + h), (x + w, y + d, z + h), (x, y + d, z + h)]
        tris = []
        for a, b, c, d in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                           (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)):
            tris.append((p[a], p[b], p[c]))
            tris.append((p[a], p[c], p[d]))
        return tris

    @staticmethod
    def _cilindro(cx, cy, z, r, h, seg=16):
        tris = []
        for i in range(seg):
            a1 = 2.0 * math.pi * i / seg
            a2 = 2.0 * math.pi * (i + 1) / seg
            x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
            x2, y2 = cx + r * math.cos(a2), cy + r * math.sin(a2)
            tris.append(((cx, cy, z), (x1, y1, z), (x2, y2, z)))
            tris.append(((cx, cy, z + h), (x2, y2, z + h), (x1, y1, z + h)))
            tris.append(((x1, y1, z), (x2, y2, z), (x2, y2, z + h)))
            tris.append(((x1, y1, z), (x2, y2, z + h), (x1, y1, z + h)))
        return tris

    def generar_stl(self, objetos) -> dict:
        if not isinstance(objetos, list) or not objetos:
            raise ValueError("objetos requiere al menos 1 forma.")
        tris = []
        for obj in objetos:
            if not isinstance(obj, dict):
                raise ValueError("cada objeto debe ser dict.")
            forma = str(obj.get("forma", ""))
            x = float(obj.get("x", 0.0))
            y = float(obj.get("y", 0.0))
            if forma == "rect":
                w = float(obj.get("w", 10.0))
                h = float(obj.get("h", 10.0))
                alto = max(0.5, float(obj.get("alto_3d", h / 10.0)))
                tris.extend(self._caja(x, y, 0.0, w, h, alto))
            elif forma == "circle":
                r = float(obj.get("r", 5.0))
                alto = max(0.5, float(obj.get("alto_3d", r / 5.0)))
                tris.extend(self._cilindro(x + r, y + r, 0.0, r, alto))
            else:
                raise ValueError("forma no imprimible: " + repr(forma))
        binario = bytearray()
        binario += b"ZYRA LABORATORIO STL export".ljust(80, b"\x00")
        binario += struct.pack("<I", len(tris))
        for tri in tris:
            binario += struct.pack("<3f", *_normal(tri))
            for p in tri:
                binario += struct.pack("<3f", *p)
            binario += struct.pack("<H", 0)
        return {"stl_binario": bytes(binario), "triangulos": len(tris),
                "bytes": len(binario), "formato": "stl-binario"}

    def generar_gcode(self, objetos, altura_capa_mm=0.2, densidad_relleno=0.3,
                      velocidad_mm_s=1500, temperatura_hotend=200, temperatura_cama=60) -> dict:
        if altura_capa_mm <= 0 or altura_capa_mm > 1.0:
            raise ValueError("altura_capa_mm entre 0 y 1.")
        if not 0.0 <= densidad_relleno <= 1.0:
            raise ValueError("densidad_relleno entre 0 y 1.")
        if velocidad_mm_s <= 0:
            raise ValueError("velocidad_mm_s positiva.")
        self.generar_stl(objetos)
        ancho = min(200.0, max(float(o.get("x", 0.0)) + float(o.get("w", o.get("r", 5.0))) * 2
                               for o in objetos if isinstance(o, dict)))
        largo = min(200.0, max(float(o.get("y", 0.0)) + float(o.get("h", o.get("r", 5.0))) * 2
                               for o in objetos if isinstance(o, dict)))
        alto_max = max(float(o.get("alto_3d", float(o.get("h", o.get("r", 10.0))) / 10.0))
                       for o in objetos if isinstance(o, dict))
        g = ["; ZYRA LABORATORIO - G-code",
             "M104 S{}".format(int(temperatura_hotend)),
             "M140 S{}".format(int(temperatura_cama)),
             "G21", "G90", "M82", "G28",
             "M109 S{}".format(int(temperatura_hotend)),
             "M190 S{}".format(int(temperatura_cama)),
             "G92 E0", "G1 Z0.2 F1000", "G1 X5 Y5 F3000"]
        capas = max(1, int(alto_max / altura_capa_mm))
        paso = max(0.4, 0.8 / max(densidad_relleno, 0.01))
        for capa in range(capas):
            z = round(0.2 + capa * altura_capa_mm, 3)
            g.append("; capa {}".format(capa + 1))
            g.append("G1 Z{} F{}".format(z, int(velocidad_mm_s / 4)))
            g.append("G1 X0 Y0 F{}".format(int(velocidad_mm_s)))
            g.append("G1 X{} Y0 F{}".format(round(ancho, 2), int(velocidad_mm_s)))
            yy = 0.0
            par = False
            while yy < largo:
                x_ini = round(ancho, 2) if par else 0.0
                x_fin = 0.0 if par else round(ancho, 2)
                g.append("G1 X{} Y{} F{}".format(x_ini, round(yy, 2), int(velocidad_mm_s)))
                g.append("G1 X{} Y{} F{}".format(x_fin, round(min(yy + paso, largo), 2), int(velocidad_mm_s)))
                yy += paso
                par = not par
        g += ["M104 S0", "M140 S0", "G28 X0 Y0", "M84", "; fin ZYRA"]
        texto = "\n".join(g) + "\n"
        return {"gcode": texto, "lineas": len(g), "capas": capas,
                "bytes": len(texto.encode("utf-8"))}

    def disenar_y_preparar(self, objetos, altura_capa_mm=0.2,
                           densidad_relleno=0.3, velocidad_mm_s=1500) -> dict:
        stl = self.generar_stl(objetos)
        g = self.generar_gcode(objetos, altura_capa_mm, densidad_relleno, velocidad_mm_s)
        return {"stl": {"triangulos": stl["triangulos"], "bytes": stl["bytes"]},
                "gcode": {"capas": g["capas"], "lineas": g["lineas"], "bytes": g["bytes"]},
                "instrucciones": "descarga el .gcode a la SD/USB de tu impresora y manda imprimir"}

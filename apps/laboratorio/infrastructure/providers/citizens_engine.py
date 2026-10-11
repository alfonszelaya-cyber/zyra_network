"""Ciudadanos simulados + SIMULACION DE DESASTRES (EX-DES)."""
import math

CELULA = 50.0
UMBRAL_AGLO = 6
VEL_DEFECTO = 1.4
ESTADOS = ("en_ruta", "en_punto", "evacuando")
DESASTRES = {
    "terremoto": {"multiplicador": 2.0, "ayuda": ("rescate urbano", "albergues", "atencion medica")},
    "inundacion": {"multiplicador": 1.3, "ayuda": ("botes de rescate", "albergues en altura", "agua potable")},
    "incendio": {"multiplicador": 1.8, "ayuda": ("bomberos", "rutas libres de humo", "atencion respiratoria")},
    "erupcion": {"multiplicador": 1.5, "ayuda": ("mascarillas", "evacuacion amplio radio", "refugios cerrados")},
}


def _num(v, n):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(n + " debe ser numerico.")
    return float(v)


class Ciudadano:
    __slots__ = ("id", "nombre", "rol", "x", "y", "velocidad", "agenda", "indice", "estado", "color")

    def __init__(self, id_c, nombre, rol, x, y, velocidad, agenda, color="#38BDF8"):
        self.id = str(id_c)
        self.nombre = str(nombre)[:80]
        self.rol = str(rol)[:40]
        self.x = _num(x, "x")
        self.y = _num(y, "y")
        if velocidad <= 0:
            raise ValueError("velocidad debe ser positiva.")
        self.velocidad = float(velocidad)
        if not agenda:
            raise ValueError("agenda requiere al menos un punto.")
        self.agenda = [(_num(p[0], "ax"), _num(p[1], "ay")) for p in agenda]
        self.indice = 0
        self.estado = "en_ruta"
        self.color = str(color)[:7]

    def a_dict(self):
        return {"id": self.id, "nombre": self.nombre, "rol": self.rol,
                "x": round(self.x, 3), "y": round(self.y, 3),
                "velocidad": round(self.velocidad, 3), "estado": self.estado,
                "destino": list(self.agenda[self.indice]), "color": self.color}


class MotorCiudadanos:
    def __init__(self):
        self._todos = []
        self._salidas = []
        self._tiempo = 0.0

    def capacidades(self):
        return {"origenes": ("descripcion", "foto", "escaneo"), "estados": ESTADOS,
                "desastres": sorted(DESASTRES.keys())}

    def poblar(self, ciudadanos, salidas=None) -> dict:
        if not isinstance(ciudadanos, list) or not ciudadanos:
            raise ValueError("ciudadanos requiere lista con al menos 1.")
        self._todos = []
        self._salidas = [(_num(s[0], "sx"), _num(s[1], "sy")) for s in (salidas or [])]
        self._tiempo = 0.0
        for i, esp in enumerate(ciudadanos):
            if not isinstance(esp, dict):
                raise ValueError("ciudadanos[" + str(i) + "] debe ser objeto.")
            origen = str(esp.get("origen", "descripcion")).strip()
            if origen == "descripcion":
                nombre = str(esp.get("nombre", "")).strip()
                if not nombre:
                    raise ValueError("descripcion requiere nombre.")
                rol = str(esp.get("rol", "peaton"))
                color = str(esp.get("color", "#38BDF8"))
            elif origen == "foto":
                nombre = str(esp.get("nombre", "Foto-" + str(i + 1)))
                rol = str(esp.get("rol", "peaton"))
                color = str(esp.get("color_foto", esp.get("color", "#F59E0B")))
            elif origen == "escaneo":
                nombre = str(esp.get("nombre", "Escaneado-" + str(i + 1)))
                rol = "visitante"
                if not esp.get("puntos"):
                    raise ValueError("escaneo requiere puntos.")
                color = "#EC4899"
            else:
                raise ValueError("origen desconocido: " + repr(origen))
            x = _num(esp.get("x", 0.0), "x")
            y = _num(esp.get("y", 0.0), "y")
            vel = _num(esp.get("velocidad", VEL_DEFECTO), "velocidad")
            agenda = esp.get("agenda") or [[x, y]]
            self._todos.append(Ciudadano("cit-" + str(i + 1).zfill(5), nombre, rol, x, y, vel, agenda, color))
        return {"poblacion": len(self._todos), "salidas": len(self._salidas)}

    def paso(self, dt=1.0) -> dict:
        dt = _num(dt, "dt")
        if dt <= 0 or dt > 10.0:
            raise ValueError("dt entre 0 y 10.")
        self._tiempo += dt
        for c in self._todos:
            dx = c.agenda[c.indice][0] - c.x
            dy = c.agenda[c.indice][1] - c.y
            dist = math.hypot(dx, dy)
            if dist < 0.5:
                c.indice = (c.indice + 1) % len(c.agenda)
            else:
                paso = min(c.velocidad * dt, dist)
                c.x += dx / dist * paso
                c.y += dy / dist * paso
            if c.estado != "evacuando":
                c.estado = "en_ruta"
        return {"tiempo": round(self._tiempo, 3), "poblacion": len(self._todos),
                "aglomeraciones": self._aglomeraciones()}

    def _aglomeraciones(self):
        celdas = {}
        for c in self._todos:
            k = (int(c.x // CELULA), int(c.y // CELULA))
            celdas.setdefault(k, []).append(c.id)
        return [{"celda": list(k), "cantidad": len(v), "ciudadanos": v[:20]}
                for k, v in sorted(celdas.items()) if len(v) >= UMBRAL_AGLO]

    def evacuar(self) -> dict:
        if not self._salidas:
            raise ValueError("evacuar requiere salidas.")
        for c in self._todos:
            mejor = min(self._salidas, key=lambda s: math.hypot(s[0] - c.x, s[1] - c.y))
            c.agenda = [mejor]
            c.indice = 0
            c.estado = "evacuando"
            c.velocidad = c.velocidad * 1.6
        return {"evacuando": len(self._todos), "salidas": len(self._salidas)}

    def declarar_zonas_seguras(self, zonas) -> dict:
        if not isinstance(zonas, list) or not zonas:
            raise ValueError("zonas_seguras requiere al menos 1.")
        limpias = []
        for z in zonas:
            if not (isinstance(z, (list, tuple)) and len(z) == 3):
                raise ValueError("cada zona debe ser [x, y, radio].")
            x, y, r = _num(z[0], "zx"), _num(z[1], "zy"), _num(z[2], "zr")
            if r <= 0:
                raise ValueError("radio positivo requerido.")
            limpias.append((x, y, r))
        self._zonas = limpias
        return {"zonas_seguras": len(limpias)}

    def simular_desastre(self, tipo, epicentro, radio_afectacion, zonas_seguras) -> dict:
        spec = DESASTRES.get(str(tipo or "").strip())
        if spec is None:
            raise ValueError("desastre desconocido: " + repr(tipo)
                             + ". Validos: " + ", ".join(sorted(DESASTRES)))
        if not (isinstance(epicentro, (list, tuple)) and len(epicentro) == 2):
            raise ValueError("epicentro debe ser [x, y].")
        ex, ey = _num(epicentro[0], "ex"), _num(epicentro[1], "ey")
        radio = _num(radio_afectacion, "radio")
        if radio <= 0:
            raise ValueError("radio positivo.")
        self.declarar_zonas_seguras(zonas_seguras)
        afectados = 0
        t_max = 0.0
        for c in self._todos:
            if math.hypot(c.x - ex, c.y - ey) <= radio:
                afectados += 1
                zx, zy, _zr = min(self._zonas, key=lambda s: math.hypot(s[0] - c.x, s[1] - c.y))
                c.agenda = [(zx, zy)]
                c.indice = 0
                c.estado = "evacuando"
                c.velocidad = c.velocidad * spec["multiplicador"]
                if c.velocidad > 0:
                    t_max = max(t_max, math.hypot(zx - c.x, zy - c.y) / c.velocidad)
        return {"tipo": tipo, "epicentro": [ex, ey], "radio_afectacion": radio,
                "afectados": afectados, "poblacion": len(self._todos),
                "zonas_seguras": [list(z) for z in self._zonas],
                "ayuda_necesaria": list(spec["ayuda"]),
                "pasos_estimados_evacuacion": round(t_max, 2)}

    def estado_poblacion(self) -> dict:
        return {"tiempo": round(self._tiempo, 3), "poblacion": len(self._todos),
                "ciudadanos": [c.a_dict() for c in self._todos[:200]],
                "salidas": [list(s) for s in self._salidas]}

    def total(self) -> int:
        return len(self._todos)

"""Motor de CIUDADANOS SIMULADOS para gemelos digitales.

Origenes reales: descripcion, foto (colores via MotorAvatar),
escaneo (puntos del scanner). Comportamiento determinista:
agenda, aglomeraciones por densidad, evacuacion a salidas.
"""
import math

CELULA = 50.0
UMBRAL_AGLO = 6
VEL_DEFECTO = 1.4
ESTADOS = ("en_ruta", "en_punto", "evacuando")


def _num(v, n):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(n + " debe ser numerico.")
    return float(v)


class Ciudadano:
    __slots__ = ("id", "nombre", "rol", "x", "y", "velocidad", "agenda",
                 "indice", "estado", "color")

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
                "velocidad": self.velocidad, "estado": self.estado,
                "destino": list(self.agenda[self.indice]), "color": self.color}


class MotorCiudadanos:
    def __init__(self):
        self._todos = []
        self._salidas = []
        self._tiempo = 0.0

    def capacidades(self) -> dict:
        return {"origenes": ("descripcion", "foto", "escaneo"),
                "estados": ESTADOS,
                "deteccion": ("aglomeraciones", "evacuacion", "densidad"),
                "uso": "gemelo digital de parques, ciudades, edificios, videojuegos"}

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
                    raise ValueError("escaneo requiere puntos del scan real.")
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
            raise ValueError("dt debe estar entre 0 y 10.")
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
            clave = (int(c.x // CELULA), int(c.y // CELULA))
            celdas.setdefault(clave, []).append(c.id)
        return [{"celda": list(k), "cantidad": len(v), "ciudadanos": v[:20]}
                for k, v in sorted(celdas.items()) if len(v) >= UMBRAL_AGLO]

    def evacuar(self) -> dict:
        if not self._salidas:
            raise ValueError("evacuar requiere salidas definidas en poblar.")
        for c in self._todos:
            mejor = min(self._salidas, key=lambda s: math.hypot(s[0] - c.x, s[1] - c.y))
            c.agenda = [mejor]
            c.indice = 0
            c.estado = "evacuando"
            c.velocidad = c.velocidad * 1.6
        return {"evacuando": len(self._todos), "salidas": len(self._salidas)}

    def estado_poblacion(self) -> dict:
        return {"tiempo": round(self._tiempo, 3), "poblacion": len(self._todos),
                "ciudadanos": [c.a_dict() for c in self._todos[:200]],
                "salidas": [list(s) for s in self._salidas]}

    def total(self) -> int:
        return len(self._todos)

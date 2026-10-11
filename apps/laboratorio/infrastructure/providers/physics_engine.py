"""Motor FISICO real: gravedad, velocidad, colisiones AABB con rebote."""
GRAVEDAD_DEFECTO = 9.81
MAX_CUERPOS = 2000


class Cuerpo:
    __slots__ = ("id", "x", "y", "w", "h", "vx", "vy", "masa", "rebote")

    def __init__(self, id_c, x, y, w, h, masa=1.0, rebote=0.5):
        self.id = str(id_c)
        self.x = float(x)
        self.y = float(y)
        self.w = float(w)
        self.h = float(h)
        if self.w <= 0 or self.h <= 0:
            raise ValueError("dimensiones deben ser positivas.")
        self.vx = 0.0
        self.vy = 0.0
        self.masa = float(masa)
        if self.masa <= 0:
            raise ValueError("masa debe ser positiva.")
        self.rebote = float(rebote)
        if not 0.0 <= self.rebote <= 1.0:
            raise ValueError("rebote entre 0 y 1.")

    def a_dict(self):
        return {"id": self.id, "x": round(self.x, 3), "y": round(self.y, 3),
                "w": self.w, "h": self.h, "vx": round(self.vx, 3),
                "vy": round(self.vy, 3), "masa": self.masa, "rebote": self.rebote}


class MotorFisico:
    def __init__(self, gravedad=GRAVEDAD_DEFECTO, friccion=0.02):
        self._g = float(gravedad)
        if self._g < 0:
            raise ValueError("gravedad no puede ser negativa.")
        self._fric = float(friccion)
        if not 0.0 <= self._fric <= 1.0:
            raise ValueError("friccion entre 0 y 1.")
        self._cuerpos = []
        self._t = 0.0

    def capacidades(self) -> dict:
        return {"integracion": "Euler semi-implicito dt fijo",
                "gravedad": self._g, "colisiones": "AABB con rebote",
                "determinista": True}

    def agregar(self, id_c, x, y, w, h, masa=1.0, rebote=0.5) -> dict:
        if len(self._cuerpos) >= MAX_CUERPOS:
            raise ValueError("maximo de cuerpos alcanzado.")
        c = Cuerpo(id_c, x, y, w, h, masa, rebote)
        self._cuerpos.append(c)
        return c.a_dict()

    def impulso(self, id_c, vx, vy) -> dict:
        for c in self._cuerpos:
            if c.id == str(id_c):
                c.vx += float(vx)
                c.vy += float(vy)
                return c.a_dict()
        raise ValueError("Cuerpo desconocido: " + str(id_c))

    @staticmethod
    def _toca(a, b):
        return not (a.x + a.w <= b.x or b.x + b.w <= a.x
                    or a.y + a.h <= b.y or b.y + b.h <= a.y)

    def _resolver(self, a, b):
        sx = min(a.x + a.w - b.x, b.x + b.w - a.x)
        sy = min(a.y + a.h - b.y, b.y + b.h - a.y)
        mt = a.masa + b.masa
        if sx < sy:
            d = 1.0 if a.x < b.x else -1.0
            corr = sx * (a.masa / mt)
            a.x -= d * corr
            b.x += d * (sx - corr)
            vr = a.vx - b.vx
            if (d > 0 and vr > 0) or (d < 0 and vr < 0):
                e = min(a.rebote, b.rebote)
                imp = -(1.0 + e) * vr / (1.0 / a.masa + 1.0 / b.masa)
                a.vx += imp / a.masa
                b.vx -= imp / b.masa
            return {"par": [a.id, b.id], "normal": "x"}
        d = 1.0 if a.y < b.y else -1.0
        corr = sy * (a.masa / mt)
        a.y -= d * corr
        b.y += d * (sy - corr)
        vr = a.vy - b.vy
        if (d > 0 and vr > 0) or (d < 0 and vr < 0):
            e = min(a.rebote, b.rebote)
            imp = -(1.0 + e) * vr / (1.0 / a.masa + 1.0 / b.masa)
            a.vy += imp / a.masa
            b.vy -= imp / b.masa
        return {"par": [a.id, b.id], "normal": "y"}

    def paso(self, dt=0.016) -> dict:
        dt = float(dt)
        if dt <= 0 or dt > 0.1:
            raise ValueError("dt debe estar entre 0 y 0.1.")
        self._t += dt
        for c in self._cuerpos:
            c.vy += self._g * dt
            f = max(0.0, 1.0 - self._fric * dt)
            c.vx *= f
            c.vy *= f
            c.x += c.vx * dt
            c.y += c.vy * dt
        colisiones = []
        n = len(self._cuerpos)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = self._cuerpos[i], self._cuerpos[j]
                if self._toca(a, b):
                    colisiones.append(self._resolver(a, b))
        return {"tiempo": round(self._t, 4), "cuerpos": n,
                "colisiones": colisiones[:50], "total_colisiones": len(colisiones)}

    def estado(self) -> dict:
        return {"tiempo": round(self._t, 4), "gravedad": self._g,
                "friccion": self._fric,
                "cuerpos": [c.a_dict() for c in self._cuerpos[:200]]}

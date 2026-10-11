"""PRESENTACION HOLOGRAFICA INTERACTIVA.

Proyeccion (HDMI/UDP/web por salida universal) e INDEPENDIENTE del
control (telefono/PC/tablet por navegador). El telefono es el
tactil: tocas el punto a explicar y queda anotado en la proyeccion.
"""
import time

from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.infrastructure.providers.hologram_engine import MotorHolograma
from apps.laboratorio.shared.models.identifiers import nuevo_id

ACCIONES_VALIDAS = ("avanzar", "retroceder", "ir_a", "tocar_punto", "finalizar")


def _escapar(texto):
    return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escena_para_holograma(nombre):
    try:
        return Escena3D(nombre=nombre, ancho=900, alto=700, objetos=[])
    except TypeError:
        try:
            return Escena3D(nombre, 900, 700, [])
        except Exception:
            esc = Escena3D.__new__(Escena3D)
            for atributo, valor in (("nombre", nombre), ("ancho", 900), ("alto", 700), ("objetos", [])):
                setattr(esc, atributo, valor)
            return esc


class SesionPresentacion:
    def __init__(self, id_sesion, presentacion, proyector):
        self.id = str(id_sesion)
        self._presentacion = presentacion
        self._proyector = proyector
        self._holograma = MotorHolograma()
        self.paso_actual = 0
        self.activa = True
        self.anotaciones = []
        self.historial = []
        self.iniciada_en = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _pasos(self):
        return list(getattr(self._presentacion, "pasos", []) or [])

    def total_pasos(self):
        return len(self._pasos())

    def _registrar(self, accion, detalle):
        entrada = {"accion": str(accion), "detalle": dict(detalle or {}),
                   "momento": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self.historial.append(entrada)
        return entrada

    def _paso_datos(self):
        pasos = self._pasos()
        if not pasos:
            return {"indice": 0, "total": 0, "titulo": "", "contenido": ""}
        paso = pasos[min(self.paso_actual, len(pasos) - 1)]
        try:
            datos = paso.a_dict() if hasattr(paso, "a_dict") else dict(paso)
        except Exception:
            datos = {"titulo": str(getattr(paso, "titulo", ""))}
        datos["indice"] = self.paso_actual
        datos["total"] = len(pasos)
        return datos

    def avanzar(self):
        total = self.total_pasos()
        if self.paso_actual < total - 1:
            self.paso_actual += 1
        self._registrar("avanzar", {"paso": self.paso_actual})
        return {"paso": self.paso_actual, "total": total}

    def retroceder(self):
        if self.paso_actual > 0:
            self.paso_actual -= 1
        self._registrar("retroceder", {"paso": self.paso_actual})
        return {"paso": self.paso_actual, "total": self.total_pasos()}

    def ir_a(self, indice):
        indice = int(indice)
        total = self.total_pasos()
        if not 0 <= indice < total:
            raise ValueError("indice fuera de rango 0.." + str(total - 1))
        self.paso_actual = indice
        self._registrar("ir_a", {"paso": indice})
        return {"paso": self.paso_actual, "total": total}

    def tocar_punto(self, x, y, etiqueta=""):
        xv = float(x)
        yv = float(y)
        if xv < 0 or yv < 0:
            raise ValueError("coordenadas no pueden ser negativas.")
        anotacion = {"id": "anot-" + str(len(self.anotaciones) + 1).zfill(4),
                     "paso": self.paso_actual, "x": round(xv, 2), "y": round(yv, 2),
                     "etiqueta": str(etiqueta or "")[:200],
                     "momento": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self.anotaciones.append(anotacion)
        self._registrar("tocar_punto", {"paso": self.paso_actual, "x": anotacion["x"], "y": anotacion["y"]})
        return dict(anotacion)

    def anotaciones_del_paso(self, indice=None):
        indice = self.paso_actual if indice is None else int(indice)
        return [dict(a) for a in self.anotaciones if a["paso"] == indice]

    def frame_holograma(self):
        paso = self._paso_datos()
        titulo = str(paso.get("titulo", "") or ("Paso " + str(paso["indice"] + 1)))
        svg = self._holograma.generar(_escena_para_holograma(titulo)).decode("utf-8")
        texto = str(paso.get("contenido", "") or paso.get("descripcion", "") or "")
        marcas = []
        if texto:
            y = 60
            for i in range(0, min(len(texto), 240), 60):
                marcas.append('<text x="24" y="' + str(y) + '" fill="#E2E8F0" font-size="16" font-family="sans-serif">' + _escapar(texto[i:i + 60]) + "</text>")
                y += 24
        for a in self.anotaciones_del_paso():
            marcas.append('<circle cx="' + str(a["x"]) + '" cy="' + str(a["y"]) + '" r="10" fill="none" stroke="#F59E0B" stroke-width="3"><animate attributeName="r" values="6;14;6" dur="1.6s" repeatCount="indefinite"/></circle>')
        if marcas and "</svg>" in svg:
            svg = svg.replace("</svg>", "".join(marcas) + "</svg>", 1)
        return svg.encode("utf-8")

    def estado(self):
        return {"sesion": str(self.id), "activa": self.activa, "paso_actual": self.paso_actual,
                "total_pasos": self.total_pasos(), "anotaciones_total": len(self.anotaciones),
                "anotaciones_paso": self.anotaciones_del_paso(), "iniciada_en": self.iniciada_en,
                "paso": self._paso_datos()}

    def finalizar(self):
        self.activa = False
        self._registrar("finalizar", {"anotaciones": len(self.anotaciones)})
        return {"sesion": str(self.id), "duracion_pasos": self.total_pasos(),
                "anotaciones": len(self.anotaciones), "historial": list(self.historial)}


class PresentacionRemota:
    def __init__(self, repo_presentaciones, proyector):
        self._repo = repo_presentaciones
        self._proyector = proyector
        self._sesiones = {}

    def capacidades(self):
        return {"control": ("telefono", "pc", "tablet"), "acciones": ACCIONES_VALIDAS,
                "proyeccion": "MotorHolo3D salida universal (independiente del control)",
                "tactil": "el navegador de control es el tactil"}

    def crear_sesion(self, presentacion_id):
        id_limpio = str(presentacion_id or "").strip()
        if not id_limpio:
            raise ValueError("presentacion_id requerido.")
        presentacion = self._repo.obtener_exigir(id_limpio)
        id_sesion = str(nuevo_id("ses"))
        sesion = SesionPresentacion(id_sesion, presentacion, self._proyector)
        self._sesiones[id_sesion] = sesion
        return {"sesion": id_sesion, "presentacion": id_limpio,
                "total_pasos": sesion.total_pasos(),
                "vista_control": "/laboratorio/api/v1/presentations/remote/" + id_sesion + "/view"}

    def sesion(self, id_sesion):
        sesion = self._sesiones.get(str(id_sesion or "").strip())
        if sesion is None:
            raise ValueError("Sesion desconocida: " + str(id_sesion))
        return sesion

    def listar_sesiones(self):
        return {"activas": [{"sesion": str(sid), "paso": s.paso_actual, "total": s.total_pasos()}
                             for sid, s in sorted(self._sesiones.items()) if s.activa],
                "total": len(self._sesiones)}

    def proyectar_paso_actual(self, id_sesion):
        sesion = self.sesion(id_sesion)
        frame = sesion.frame_holograma()
        canal = "web-sesion-" + str(sesion.id)
        if not any(d.get("nombre") == canal
                   for d in self._proyector.listar_destinos().get("destinos", [])):
            self._proyector.registrar_destino("web", "", canal)
        entrega = self._proyector.presentar(frame, {})
        return {"sesion": str(sesion.id), "paso": sesion.paso_actual, "proyeccion": entrega}

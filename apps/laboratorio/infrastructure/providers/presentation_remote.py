"""Presentacion holografica interactiva + MODO CURSO (EX-4)."""
import json
import time

from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.infrastructure.providers.hologram_engine import MotorHolograma
from apps.laboratorio.shared.models.identifiers import nuevo_id

ACCIONES_VALIDAS = ("avanzar", "retroceder", "ir_a", "tocar_punto", "finalizar")


def _escapar(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escena_holo(nombre):
    try:
        return Escena3D(nombre=nombre, ancho=900, alto=700, objetos=[])
    except TypeError:
        try:
            return Escena3D(nombre, 900, 700, [])
        except Exception:
            esc = Escena3D.__new__(Escena3D)
            for a, v in (("nombre", nombre), ("ancho", 900), ("alto", 700), ("objetos", [])):
                setattr(esc, a, v)
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
        e = {"accion": str(accion), "detalle": dict(detalle or {}),
             "momento": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self.historial.append(e)
        return e

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
        xv, yv = float(x), float(y)
        if xv < 0 or yv < 0:
            raise ValueError("coordenadas no pueden ser negativas.")
        a = {"id": "anot-" + str(len(self.anotaciones) + 1).zfill(4),
             "paso": self.paso_actual, "x": round(xv, 2), "y": round(yv, 2),
             "etiqueta": str(etiqueta or "")[:200],
             "momento": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self.anotaciones.append(a)
        self._registrar("tocar_punto", {"paso": self.paso_actual, "x": a["x"], "y": a["y"]})
        return dict(a)

    def anotaciones_del_paso(self, indice=None):
        indice = self.paso_actual if indice is None else int(indice)
        return [dict(a) for a in self.anotaciones if a["paso"] == indice]

    def frame_holograma(self):
        paso = self._paso_datos()
        titulo = str(paso.get("titulo", "") or ("Paso " + str(paso["indice"] + 1)))
        svg = self._holograma.generar(_escena_holo(titulo)).decode("utf-8")
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
                "proyeccion": "MotorHolo3D salida universal",
                "tactil": "el navegador de control es el tactil"}

    def crear_sesion(self, presentacion_id):
        pid = str(presentacion_id or "").strip()
        if not pid:
            raise ValueError("presentacion_id requerido.")
        presentacion = self._repo.obtener_exigir(pid)
        sid = str(nuevo_id("ses"))
        self._sesiones[sid] = SesionPresentacion(sid, presentacion, self._proyector)
        return {"sesion": sid, "presentacion": pid,
                "total_pasos": self._sesiones[sid].total_pasos(),
                "vista_control": "/laboratorio/api/v1/presentations/remote/" + sid + "/view"}

    def sesion(self, id_sesion):
        s = self._sesiones.get(str(id_sesion or "").strip())
        if s is None:
            raise ValueError("Sesion desconocida: " + str(id_sesion))
        return s

    def listar_sesiones(self):
        return {"activas": [{"sesion": str(k), "paso": v.paso_actual, "total": v.total_pasos()}
                             for k, v in sorted(self._sesiones.items()) if v.activa],
                "total": len(self._sesiones)}

    def proyectar_paso_actual(self, id_sesion):
        sesion = self.sesion(id_sesion)
        frame = sesion.frame_holograma()
        canal = "web-sesion-" + str(sesion.id)
        if not any(d.get("nombre") == canal
                   for d in self._proyector.listar_destinos().get("destinos", [])):
            self._proyector.registrar_destino("web", "", canal)
        return {"sesion": str(sesion.id), "paso": sesion.paso_actual,
                "proyeccion": self._proyector.presentar(frame, {})}


class ModoCurso:
    """Capacitacion: evaluacion real + certificado firmado y sellado en la Red."""

    def __init__(self, repo_presentaciones, outbox, firmador, cliente=None):
        self._repo = repo_presentaciones
        self._outbox = outbox
        self._firmador = firmador
        self._cliente = cliente
        self._cursos = {}

    def capacidades(self):
        return {"evaluacion": "opcion multiple con calificacion automatica",
                "certificado": "firmado (HMAC) + sellado en ZYRA via outbox"}

    def crear_curso(self, presentacion_id, preguntas, umbral_aprobacion=0.7):
        pid = str(presentacion_id or "").strip()
        if not pid:
            raise ValueError("presentacion_id requerido.")
        presentacion = self._repo.obtener_exigir(pid)
        if not isinstance(preguntas, list) or not preguntas:
            raise ValueError("preguntas requiere al menos 1.")
        limpias = []
        for i, p in enumerate(preguntas):
            if not isinstance(p, dict):
                raise ValueError("pregunta " + str(i) + " debe ser objeto.")
            texto = str(p.get("texto", "")).strip()
            opciones = list(p.get("opciones", []))
            correcta = p.get("correcta")
            if not texto or len(opciones) < 2 or isinstance(correcta, bool) \
                    or not isinstance(correcta, int) or not 0 <= correcta < len(opciones):
                raise ValueError("pregunta " + str(i) + " invalida.")
            limpias.append({"texto": texto[:300],
                            "opciones": [str(o)[:120] for o in opciones],
                            "correcta": correcta})
        umbral = float(umbral_aprobacion)
        if not 0.0 < umbral <= 1.0:
            raise ValueError("umbral_aprobacion entre 0 y 1.")
        cid = str(nuevo_id("cur"))
        self._cursos[cid] = {"id": cid, "presentacion_id": pid,
                             "titulo": str(getattr(presentacion, "titulo", ""))[:120],
                             "preguntas": limpias, "umbral": umbral, "resultados": {}}
        return {"curso": cid, "presentacion": pid, "preguntas": len(limpias), "umbral": umbral}

    def _curso(self, cid):
        curso = self._cursos.get(str(cid or "").strip())
        if curso is None:
            raise ValueError("Curso desconocido: " + str(cid))
        return curso

    def responder(self, curso_id, zid, respuestas):
        curso = self._curso(curso_id)
        if not isinstance(respuestas, list) or len(respuestas) != len(curso["preguntas"]):
            raise ValueError("respuestas debe tener " + str(len(curso["preguntas"])) + " valores.")
        detalle = []
        aciertos = 0
        for i, (preg, resp) in enumerate(zip(curso["preguntas"], respuestas)):
            ok = isinstance(resp, int) and not isinstance(resp, bool) and resp == preg["correcta"]
            aciertos += 1 if ok else 0
            detalle.append({"pregunta": i, "correcta": ok})
        puntaje = round(aciertos / len(curso["preguntas"]), 4)
        aprobado = puntaje >= curso["umbral"]
        curso["resultados"][str(zid)] = {"puntaje": puntaje, "aprobado": aprobado}
        return {"curso": str(curso["id"]), "zid": str(zid),
                "puntaje": puntaje, "aprobado": aprobado, "detalle": detalle}

    def certificar(self, curso_id, zid):
        curso = self._curso(curso_id)
        z = str(zid or "").strip()
        if not z:
            raise ValueError("zid requerido.")
        resultado = curso["resultados"].get(z)
        if resultado is None:
            raise ValueError("El ZID no ha respondido el curso.")
        if not resultado["aprobado"]:
            raise ValueError("Curso no aprobado: " + str(resultado["puntaje"])
                             + " < " + str(curso["umbral"]))
        contenido = json.dumps(
            {"curso": str(curso["id"]), "presentacion": curso["presentacion_id"],
             "titulo": curso["titulo"], "zid": z, "puntaje": resultado["puntaje"]},
            sort_keys=True)
        firma = self._firmador.firmar_documento("cert-" + str(curso["id"]) + "-" + z, contenido)
        self._outbox.encolar("laboratorio.curso.certificado", "zyra/documents/seal",
                             {"titulo": "Certificado: " + curso["titulo"], "contenido": contenido})
        if self._cliente is not None:
            self._outbox.procesar(self._cliente.entregar)
        stats = self._outbox.estadisticas()
        if stats.get("enviado", 0) > 0:
            estado = "sellado_en_zyra"
        elif stats.get("error", 0) > 0:
            estado = "error_red"
        else:
            estado = "pendiente_red"
        return {"certificado": firma, "estado_red": estado, "outbox": stats}

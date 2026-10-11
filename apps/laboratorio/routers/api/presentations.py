"""Rutas de presentaciones + control remoto + MODO CURSO."""
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo
from apps.laboratorio.schemas.responses.envelopes import exito
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError

RUTA_CREAR = "/laboratorio/api/v1/projects/{proyecto_id}/presentations"
RUTA_ITEM = "/laboratorio/api/v1/presentations/{presentacion_id}"
RUTA_PLAY = RUTA_ITEM + "/play"
RUTA_SELLAR = RUTA_ITEM + "/seal"
RUTA_SESIONES = "/laboratorio/api/v1/presentations/remote"
RUTA_SESION = RUTA_SESIONES + "/{sesion_id}"
RUTA_ACCION = RUTA_SESION + "/accion"
RUTA_TOQUE = RUTA_SESION + "/tocar"
RUTA_FRAME = RUTA_SESION + "/frame.svg"
RUTA_VISTA = RUTA_SESION + "/view"
RUTA_PROYECTAR = RUTA_SESION + "/proyectar"
RUTA_VIDEO = "/laboratorio/api/v1/presentations/{presentacion_id}/video"
RUTA_CURSO_CREAR = "/laboratorio/api/v1/presentations/{presentacion_id}/curso"
RUTA_CURSO_RESPONDER = "/laboratorio/api/v1/presentations/curso/{curso_id}/responder"
RUTA_CURSO_CERTIFICAR = "/laboratorio/api/v1/presentations/curso/{curso_id}/certificar"


def registrar_rutas(app) -> None:
    manejador = app.contenedor.obtener("manejador_presentaciones")
    remota = app.contenedor.obtener("presentacion_remota")
    modocurso = app.contenedor.obtener("modocurso")

    def _sesion_o_404(sid):
        try:
            return remota.sesion(sid)
        except ValueError as exc:
            raise EntidadNoEncontradaError(str(exc), sid)

    def _crear(ctx):
        return manejador.crear(ctx.identidad, ctx.ruta_params["proyecto_id"], ctx.json())

    def _listar(ctx):
        return manejador.listar(ctx.identidad, ctx.ruta_params["proyecto_id"])

    def _obtener(ctx):
        return manejador.obtener(ctx.identidad, ctx.ruta_params["presentacion_id"])

    def _reproducir(ctx):
        return manejador.reproducir(ctx.identidad, ctx.ruta_params["presentacion_id"])

    def _sellar(ctx):
        return manejador.sellar(ctx.identidad, ctx.ruta_params["presentacion_id"])

    def _crear_sesion(ctx):
        datos = ctx.json()
        return remota.crear_sesion(datos.get("presentacion_id", ""))

    def _listar_sesiones(ctx):
        return remota.listar_sesiones()

    def _estado(ctx):
        return _sesion_o_404(ctx.ruta_params["sesion_id"]).estado()

    def _accion(ctx):
        datos = ctx.json()
        accion = str(datos.get("accion", "")).strip()
        sesion = _sesion_o_404(ctx.ruta_params["sesion_id"])
        if accion == "avanzar":
            return sesion.avanzar()
        if accion == "retroceder":
            return sesion.retroceder()
        if accion == "ir_a":
            return sesion.ir_a(datos.get("indice", 0))
        if accion == "finalizar":
            return sesion.finalizar()
        raise ValueError("accion desconocida: " + repr(accion))

    def _tocar(ctx):
        datos = ctx.json()
        sesion = _sesion_o_404(ctx.ruta_params["sesion_id"])
        return sesion.tocar_punto(datos.get("x", 0.0), datos.get("y", 0.0), str(datos.get("etiqueta", "")))

    def _frame(ctx):
        sesion = _sesion_o_404(ctx.ruta_params["sesion_id"])
        return 200, sesion.frame_holograma(), {"Content-Type": "image/svg+xml", "Cache-Control": "no-store"}

    def _vista(ctx):
        sesion_id = ctx.ruta_params["sesion_id"]
        _sesion_o_404(sesion_id)
        base = "/laboratorio/api/v1/presentations/remote/" + sesion_id
        html = ("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                "<title>Control</title><style>body{background:#0B1220;color:#E2E8F0;"
                "font-family:system-ui,sans-serif;text-align:center;padding:16px}"
                "button{font-size:22px;margin:6px;padding:14px 22px;border-radius:12px;"
                "border:1px solid #1E293B;background:#111827;color:#93C5FD}"
                "img{max-width:100%;border-radius:12px;border:1px solid #1E293B}</style></head><body>"
                "<h3>Control de proyeccion</h3>"
                "<img id='f' src='" + base + "/frame.svg'>"
                "<div><button onclick='acc(\"retroceder\")'>&#9664; Atras</button>"
                "<button onclick='acc(\"avanzar\")'>Siguiente &#9654;</button></div>"
                "<p style='color:#94A3B8;font-size:13px'>Toca la imagen para marcar el punto a explicar</p>"
                "<script>function acc(a){fetch('" + base + "/accion',{method:'POST',"
                "headers:{'Content-Type':'application/json'},body:JSON.stringify({accion:a})})"
                ".then(r=>r.json()).then(refrescar)}"
                "var f=document.getElementById('f');"
                "f.addEventListener('click',function(e){var r=f.getBoundingClientRect();"
                "var x=(e.clientX-r.left)*900/r.width;var y=(e.clientY-r.top)*700/r.height;"
                "fetch('" + base + "/tocar',{method:'POST',headers:{'Content-Type':'application/json'},"
                "body:JSON.stringify({x:x,y:y})}).then(()=>refrescar());});"
                "function refrescar(){f.src='" + base + "/frame.svg?t='+Date.now();}"
                "setInterval(refrescar,3000);</script></body></html>")
        return 200, html.encode("utf-8"), {"Content-Type": "text/html; charset=utf-8"}

    def _proyectar(ctx):
        return remota.proyectar_paso_actual(ctx.ruta_params["sesion_id"])

    def _curso_crear(ctx):
        datos = ctx.json()
        return exito(modocurso.crear_curso(
            ctx.ruta_params["presentacion_id"], datos.get("preguntas", []),
            datos.get("umbral_aprobacion", 0.7)))

    def _curso_responder(ctx):
        datos = ctx.json()
        return exito(modocurso.responder(ctx.ruta_params["curso_id"],
                                         ctx.identidad.zid, datos.get("respuestas", [])))

    def _curso_certificar(ctx):
        return exito(modocurso.certificar(ctx.ruta_params["curso_id"], ctx.identidad.zid))

    app.registrar("POST", RUTA_CREAR, _crear, PermisoCodigo.PRESENTAR, "Crear presentacion con pasos")
    app.registrar("GET", RUTA_CREAR, _listar, PermisoCodigo.VER, "Listar presentaciones")
    app.registrar("GET", RUTA_ITEM, _obtener, PermisoCodigo.VER, "Obtener presentacion")
    app.registrar("GET", RUTA_PLAY, _reproducir, PermisoCodigo.VER, "Reproducir slideshow real")
    app.registrar("POST", RUTA_SELLAR, _sellar, PermisoCodigo.PRESENTAR, "Sellar en ZYRA via outbox")
    app.registrar("POST", RUTA_SESIONES, _crear_sesion, PermisoCodigo.PRESENTAR, "Abrir sesion interactiva")
    app.registrar("GET", RUTA_SESIONES, _listar_sesiones, PermisoCodigo.VER, "Listar sesiones interactivas")
    app.registrar("GET", RUTA_SESION, _estado, PermisoCodigo.VER, "Estado de la sesion interactiva")
    app.registrar("POST", RUTA_ACCION, _accion, PermisoCodigo.PRESENTAR, "Accion de control")
    app.registrar("POST", RUTA_TOQUE, _tocar, PermisoCodigo.PRESENTAR, "Tocar punto a explicar")
    app.registrar("GET", RUTA_FRAME, _frame, PermisoCodigo.VER, "Frame holografico del paso actual")
    app.registrar("GET", RUTA_VISTA, _vista, PermisoCodigo.VER, "Vista de control desde telefono o PC")
    app.registrar("POST", RUTA_PROYECTAR, _proyectar, PermisoCodigo.PRESENTAR, "Proyectar paso actual")
    app.registrar("POST", RUTA_CURSO_CREAR, _curso_crear, PermisoCodigo.PRESENTAR, "Crear curso de capacitacion")
    app.registrar("POST", RUTA_CURSO_RESPONDER, _curso_responder, PermisoCodigo.VER, "Responder evaluacion")
    app.registrar("POST", RUTA_CURSO_CERTIFICAR, _curso_certificar, PermisoCodigo.VER, "Certificado firmado + sellado en la Red")

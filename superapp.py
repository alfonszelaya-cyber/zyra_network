"""ZYRA SuperApp: una sola entrada bonita.

Arranca los servidores internos (cada uno con su
store y su cliente de red, independientes entre si)
y los expone bajo UNA sola entrada publica:
/             portal
/verificar    verificador publico (gratis)
/verify       proxy a la Red
/mpe /agro /axis /semilla /nexo /subastas /ciclo /laboratorio
/health       estado del servicio
"""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = Path(
    os.environ.get("SUPERAPP_DATA_DIR") or (ROOT / "data")
)
DATA_DIR.mkdir(parents=True, exist_ok=True)

PORT = int(
    os.environ.get("PORT")
    or os.environ.get("SUPERAPP_PORT")
    or 8080
)

if os.environ.get("ZYRA_URL"):
    ZYRA_URL = os.environ["ZYRA_URL"].strip().strip('"\'()').rstrip("/")
elif os.environ.get("ZYRA_HOST"):
    _h = os.environ["ZYRA_HOST"].strip().strip('"\'()').rstrip("/")
    if _h and "." not in _h:
        _h = _h + ".onrender.com"
    ZYRA_URL = ("https://" + _h).rstrip("/")
else:
    ZYRA_URL = ""

APPS = {}

class _SimpleClient:
    """Fallback client, same never-raises contract."""

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")
        self._token = (
            os.environ.get("ZYRA_API_TOKEN", "") or ""
        ).strip()

    def get(self, path: str):
        return self._call("GET", path)

    def post(self, path: str, payload: dict):
        return self._call("POST", path, payload)

    def _call(self, method, path, payload=None):
        if not self._base:
            return (False, None, "ZYRA_URL not configured")
        data = (
            json.dumps(payload).encode("utf-8")
            if payload is not None
            else None
        )
        try:
            headers = {"Content-Type": "application/json"}
            if self._token:
                headers["Authorization"] = "Bearer " + self._token
            request = urllib.request.Request(
                self._base + path,
                data=data,
                method=method,
                headers=headers,
            )
            with urllib.request.urlopen(request, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if body.get("ok") is True:
                return (True, body.get("data"), None)
            error = body.get("error", {})
            return (False, None, str(error.get("message", "rejected")))
        except Exception as exc:
            return (False, None, str(exc))

def _db(name: str):
    from shared_engines.storage.database import SQLiteAdapter
    return SQLiteAdapter(
        str(DATA_DIR / name), busy_timeout_ms=10_000
    )

def _clock():
    from shared_engines.common.clocks import SystemClock
    return SystemClock()

def _start_mpe():
    from apps.mi_primer_empleo.infrastructure.persistence.mpe_store import MpeStore
    from apps.mi_primer_empleo.infrastructure.network.network_client import NetworkClient
    from apps.mi_primer_empleo.server import serve_mpe
    store = MpeStore(_db("mpe.db"), _clock())
    client = NetworkClient(ZYRA_URL)
    server = serve_mpe(store, client, host="127.0.0.1", port=0)
    return server, "Mi Primer Empleo"

def _start_agro():
    from apps.agro.infrastructure.persistence.agro_store import AgroStore
    from apps.agro.infrastructure.network.network_client import NetworkClient
    from apps.agro.server import serve_agro
    store = AgroStore(_db("agro.db"), _clock())
    client = NetworkClient(ZYRA_URL)
    server = serve_agro(store, client, host="127.0.0.1", port=0)
    return server, "AGRO"

def _start_axis():
    from apps.axis.infrastructure.persistence.axis_store import AxisStore
    from apps.axis.infrastructure.network.network_client import NetworkClient
    from apps.axis.life_history.integration import build_life_history
    from apps.axis.server import serve_axis
    db = _db("axis.db")
    clock = _clock()
    store = AxisStore(db, clock)
    client = NetworkClient(ZYRA_URL)
    lh = build_life_history(db=db, clock=clock, network_client=client)
    server = serve_axis(
        store, client, host="127.0.0.1", port=0,
        life_history_service=lh,
    )
    return server, "AXIS"

def _start_semilla():
    from apps.semilla.infrastructure.persistence.semilla_store import SemillaStore
    from apps.semilla.infrastructure.network.network_client import NetworkClient
    from apps.semilla.server import serve_semilla
    store = SemillaStore(_db("semilla.db"), _clock())
    client = NetworkClient(ZYRA_URL)
    server = serve_semilla(store, client, host="127.0.0.1", port=0)
    return server, "SEMILLA"

def _start_nexo():
    from apps.nexo.infrastructure.persistence.nexo_store import NexoStore
    from apps.nexo.infrastructure.network.network_client import NetworkClient
    from apps.nexo.server import serve_nexo
    store = NexoStore(_db("nexo.db"), _clock())
    client = NetworkClient(ZYRA_URL)
    server = serve_nexo(store, client, host="127.0.0.1", port=0)
    try:
        from apps.nexo.services.startup import attach_live_runtime as _ng_attach
        _ng_attach(server)
    except Exception:
        pass
    return server, "NEXO"

def _start_subastas():
    from apps.subastas.infrastructure.persistence.subastas_store import SubastasStore
    from apps.subastas.server import serve_subastas
    try:
        from apps.subastas.infrastructure.network.network_client import NetworkClient
        client = NetworkClient(ZYRA_URL)
    except Exception:
        client = _SimpleClient(ZYRA_URL)
    store = SubastasStore(_db("subastas.db"), _clock())
    server = serve_subastas(store, client, host="127.0.0.1", port=0)
    return server, "SUBASTAS"

def _start_ciclo():
    from apps.ciclo_digital.infrastructure.persistence.ciclo_store import CicloStore
    from apps.ciclo_digital.infrastructure.network.network_client import NetworkClient
    from apps.ciclo_digital.server import serve_ciclo
    store = CicloStore(_db("ciclo.db"), _clock())
    client = NetworkClient(ZYRA_URL)
    server = serve_ciclo(store, client, host="127.0.0.1", port=0)
    return server, "CICLO-DIGITAL"

def _start_laboratorio():
    from apps.laboratorio.infrastructure.api.app import montar_aplicacion
    app_lab = montar_aplicacion(str(DATA_DIR / "laboratorio.db"))

    class _ManejadorLab(BaseHTTPRequestHandler):
        def _atender(self):
            largo = int(self.headers.get("Content-Length", 0) or 0)
            cuerpo = self.rfile.read(largo) if largo else b""
            status, headers_out, salida = app_lab.despachar(
                self.command, self.path, dict(self.headers), cuerpo
            )
            self.send_response(int(status))
            for clave, valor in headers_out.items():
                self.send_header(clave, valor)
            self.send_header("Content-Length", str(len(salida)))
            self.end_headers()
            self.wfile.write(salida)

        def do_GET(self):
            self._atender()

        def do_POST(self):
            self._atender()

        def do_PUT(self):
            self._atender()

        def do_PATCH(self):
            self._atender()

        def do_DELETE(self):
            self._atender()

        def log_message(self, formato, *args):
            return

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _ManejadorLab)
    return servidor, "LABORATORIO"

STARTERS = [
    ("/mpe", _start_mpe),
    ("/agro", _start_agro),
    ("/axis", _start_axis),
    ("/semilla", _start_semilla),
    ("/nexo", _start_nexo),
    ("/subastas", _start_subastas),
    ("/ciclo", _start_ciclo),
    ("/laboratorio", _start_laboratorio),
]

def boot_apps():
    errors = []
    for prefix, starter in STARTERS:
        try:
            server, label = starter()
            port = int(server.server_address[1])
            threading.Thread(
                target=server.serve_forever, daemon=True
            ).start()
            APPS[prefix] = {"port": port, "label": label}
            print(
                "[superapp] " + label + " up on 127.0.0.1:"
                + str(port) + " at " + prefix + "/*"
            )
        except Exception as exc:
            errors.append(prefix + ": " + str(exc))
            print("[superapp] " + prefix + " FAILED: " + str(exc))
    return errors

ERROR_PAGE = (
    "<html><head><meta charset='utf-8'>"
    "<title>ZYRA</title></head>"
    "<body style='font-family:sans-serif;background:#0d1117;"
    "color:#e6edf3;padding:32px'>"
    "<h1>ZYRA</h1><p>__MSG__</p>"
    "<p><a href='/' style='color:#8b949e'>Volver al portal</a></p>"
    "</body></html>"
)

NOT_FOUND_PAGE = ERROR_PAGE.replace("__MSG__", "Ruta desconocida.")

class PortalHandler(BaseHTTPRequestHandler):
    server_version = "ZYRA-SuperApp/1.0"

    def _send(self, status, content_type, payload):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, status, html):
        self._send(
            status, "text/html; charset=utf-8",
            html.encode("utf-8"),
        )

    def _read_portal(self, name):
        return (ROOT / "portal" / name).read_bytes()

    def _sesion(self):
        cruda = self.headers.get("Cookie", "") or ""
        for parte in cruda.split(";"):
            if "=" in parte:
                k, v = parte.split("=", 1)
                if k.strip() == "zyra_zid":
                    return v.strip()
        return None

    def _pagina_entrar(self, mensaje):
        aviso = ""
        if mensaje:
            aviso = "<p style='color:#f85149'>" + mensaje + "</p>"
        html = (
            "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Entrar a ZYRA</title>"
            "<style>body{font-family:system-ui,sans-serif;background:#0d1117;"
            "color:#e6edf3;max-width:520px;margin:0 auto;padding:32px 16px}"
            "input,button{width:100%;padding:12px;margin:6px 0;border-radius:8px;"
            "border:1px solid #30363d;background:#161b22;color:#e6edf3;"
            "box-sizing:border-box;font-size:16px}"
            "button{background:#238636;border:none;font-weight:700}"
            "</style></head><body>"
            "<h1>Entrar a ZYRA</h1>"
            + aviso +
            "<form method='POST' action='/entrar'>"
            "<input name='zid' placeholder='Tu ZID' required>"
            "<input name='clave' type='password' placeholder='Tu clave'>"
            "<button>Entrar</button></form>"
            "<p><a href='/' style='color:#8b949e'>Volver al portal</a></p>"
            "</body></html>"
        )
        return html

    def _proxy(self, target):
        length = int(
            self.headers.get("Content-Length", 0) or 0
        )
        body = self.rfile.read(length) if length > 0 else None
        headers = {}
        zid_s = self._sesion()
        if zid_s:
            headers["x-zyra-zid"] = zid_s
            ruta_obj = (self.path or "").split("?", 1)[0]
            if ruta_obj.startswith("/laboratorio"):
                if zid_s == os.environ.get("ZYRA_OWNER_ZID", "Z-OWNER-ALFONSZELAYA"):
                    headers["x-zyra-roles"] = os.environ.get(
                        "ZYRA_ROLES_DUENO", "LAB_GOBERNADOR")
                else:
                    headers["x-zyra-roles"] = "LAB_ESPECTADOR"
        ct = self.headers.get("Content-Type")
        if ct:
            headers["Content-Type"] = ct
        request = urllib.request.Request(
            target, data=body, method=self.command,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as resp:
                payload = resp.read()
                self._send(
                    resp.status,
                    resp.headers.get(
                        "Content-Type",
                        "text/html; charset=utf-8",
                    ),
                    payload,
                )
        except urllib.error.HTTPError as exc:
            try:
                payload = exc.read()
            except Exception:
                payload = b""
            ct2 = (
                exc.headers.get(
                    "Content-Type",
                    "text/html; charset=utf-8",
                )
                if exc.headers
                else "text/html; charset=utf-8"
            )
            self._send(exc.code, ct2, payload)
        except Exception as exc:
            self._send_html(
                502,
                ERROR_PAGE.replace(
                    "__MSG__",
                    "La app no esta disponible ahora: " + str(exc),
                ),
            )

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            base = self._read_portal("index.html").decode("utf-8")
            zid_s = self._sesion()
            if zid_s:
                estado = (
                    '<p class="estado ok">Conectado: ' + zid_s
                    + ' &middot; <a href="/salir" style="color:#f85149">Salir</a></p>')
                DESCRIPCIONES = {
                    "/mpe": "Empleos, propuestas y credenciales laborales",
                    "/agro": "Productores, ayudas y precios justos",
                    "/axis": "Salud, justicia y seguridad",
                    "/semilla": "Educacion con historial verificado",
                    "/nexo": "Nucleo contable y fiscal",
                    "/subastas": "Marketplace con confianza",
                    "/ciclo": "Reciclaje y arqueologia",
                    "/laboratorio": "Experimentos, simulaciones y proyecciones",
                }
                tarjetas = ""
                for _pref, _inf in APPS.items():
                    _ic = "/icon-app" + _pref.replace("/", "-") + ".png"
                    _desc = DESCRIPCIONES.get(_pref, "Abrir aplicacion")
                    tarjetas += (
                        '<a class="opcion" href="' + _pref + '/">'
                        + '<div style="display:flex;align-items:center;gap:16px">'
                        + '<img src="' + _ic + '" alt="" style="width:60px;height:60px;border-radius:16px;flex-shrink:0">'
                        + '<div><b style="font-size:20px">' + _inf["label"] + '</b>'
                        + '<span style="display:block;font-size:13px;color:#8b949e;margin-top:3px">' + _desc + '</span></div>'
                        + '</div></a>')
                seccion = (
                    '<div class="menu">' + tarjetas + '</div>'
                    + '<p class="tag" style="margin-top:22px;margin-bottom:8px">Verificador publico</p>'
                    + '<div class="menu">'
                    + '<a class="opcion" href="/verificar"><b style="font-size:19px">Verificar</b>'
                    + '<span>Confirma la autenticidad de un documento</span></a>'
                    + '</div>')
                i1 = base.find('<div class="menu">')
                i2 = base.find('</div>', i1) + len('</div>')
                base = base[:i1] + seccion + base[i2:]
                base = base.replace('.opcion{display:flex;flex-direction:column;gap:2px;text-decoration:none;background:#11162b;',
                    '.opcion{display:block;text-decoration:none;background:#11162b;')
            else:
                estado = ""
            base = base.replace("__ESTADO__", estado, 1)
            self._send_html(200, base)
            return

        if path == "/inicio":
            try:
                d_i = self._read_portal("inicio.html")
            except Exception:
                d_i = b"<html><body></body></html>"
            self._send(200, "text/html; charset=utf-8", d_i)
            return

        if path == "/registro":
            _reg_html = '''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ZYRA - Crear mi ZID</title>
<script src="https://unpkg.com/@zxing/library@0.21.3/umd/index.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,Arial;background:#12162e;color:#e8eaf6;padding:16px;max-width:520px;margin:0 auto}
h1{font-size:22px;text-align:center;margin:8px 0 4px;color:#fff}
.sub{text-align:center;color:#9aa0c3;font-size:13px;margin-bottom:8px}
.prog{text-align:center;color:#7c8cf8;font-weight:800;font-size:13px;margin-bottom:12px;letter-spacing:1px}
.paso{display:none}
.paso.act{display:block}
label{display:block;color:#9aa0c3;font-size:14px;margin:14px 0 6px}
input,select{width:100%;padding:12px;border-radius:10px;border:1px solid #2a2f55;background:#0d1126;color:#fff;font-size:16px}
.estado{text-align:center;font-size:13px;color:#9aa0c3;padding:6px;min-height:20px}
.preview{display:none;width:100%;border-radius:10px;margin-top:6px}
button{width:100%;margin-top:10px;padding:13px;border:0;border-radius:10px;font-size:15px;font-weight:700;color:#fff;background:#262b52}
button.ok{background:#1f6f43}
button.big{margin-top:16px;padding:15px;font-size:16px;font-weight:800;background:linear-gradient(90deg,#7c5cff,#ff5c8a)}
button:disabled{opacity:.45}
.mini{background:none;color:#a78bfa;font-size:13px;padding:8px;width:auto;margin:4px auto;display:block;border:none;cursor:pointer}
#zonaEdit{display:none;margin-top:8px;background:#0d1126;border:1px solid #2a2f55;border-radius:12px;padding:10px}
#cvEdit{width:100%;touch-action:none;border-radius:8px;display:block}
#videozona{display:none;position:relative;border-radius:12px;overflow:hidden;margin-top:8px;background:#000}
video{width:100%;display:block;transform:scaleX(-1)}
.ov{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none}
a{color:#a78bfa}
#desglose{margin-top:14px;font-size:13px}
#resp{margin-top:14px}
#jserr{display:none;background:#2a1414;border:1px solid #f85149;color:#f85149;border-radius:10px;padding:10px;margin-top:10px;font-size:12px;word-break:break-all}
.zid{font-size:20px;font-weight:800;color:#3fb950;letter-spacing:1px}
.chk{color:#3fb950!important;font-weight:700}
.mal{color:#f85149!important}
.titulopaso{font-size:17px;font-weight:800;color:#fff;text-align:center;margin-bottom:6px}
</style>
</head>
<body>
<h1>Crear mi ZID</h1>
<p class="sub">Red de confianza digital</p>
<div class="prog" id="prog">PASO 1 DE 5</div>
<form onsubmit="return enviar(event)">
<div class="paso act" id="ps1">
<label>Nombre completo (nombres y apellidos)</label>
<input id="nombre" autocomplete="name">
<label>Tipo de documento legal</label>
<select id="tipoDoc">
<option value="dui">DUI El Salvador (2 lados)</option>
<option value="pasaporte">Pasaporte (1 lado)</option>
<option value="licencia">Licencia de conducir (2 lados)</option>
<option value="id_usa">ID de estado / EAD USA (2 lados)</option>
<option value="permiso">Permiso legal / otro documento</option>
</select>
<label>Fecha de vencimiento del documento (si aparece en el)</label>
<input type="date" id="vencimiento">
<button type="button" class="big" onclick="irDe1()">Continuar</button>
</div>
<div class="paso" id="ps2">
<div class="titulopaso">LADO FRONTAL — toma la cara con tu foto</div>
<input type="file" id="fileF" accept="image/*" capture="environment" style="display:none" onchange="cargarDoc(this,'F')">
<input type="file" id="galF" accept="image/*" style="display:none" onchange="cargarDoc(this,'F')">
<button type="button" class="big" id="btF" onclick="tomarFoto('F')">TOMAR FOTO FRONTAL</button>
<button type="button" class="mini" onclick="elegirArchivo('F')">o elegir archivo existente</button>
<div class="estado" id="stF"></div>
<img class="preview" id="pF" alt="" onclick="reeditar('F')">
<button type="button" class="mini" onclick="irAPaso(1)">Volver</button>
</div>
<div class="paso" id="ps3">
<div class="titulopaso">LADO DE ATRAS (REVERSO)</div>
<input type="file" id="fileA" accept="image/*" capture="environment" style="display:none" onchange="cargarDoc(this,'A')">
<input type="file" id="galA" accept="image/*" style="display:none" onchange="cargarDoc(this,'A')">
<button type="button" class="big" id="btA" onclick="tomarFoto('A')">TOMAR FOTO REVERSO</button>
<button type="button" class="mini" onclick="elegirArchivo('A')">o elegir archivo existente</button>
<div class="estado" id="stA"></div>
<img class="preview" id="pA" alt="" onclick="reeditar('A')">
<div class="estado" id="notaRev"></div>
<button type="button" class="ok" id="bIr4" disabled onclick="irAPaso(4)">Continuar</button>
<button type="button" class="mini" onclick="saltarReverso()">Mi documento no tiene reverso: continuar sin el</button>
<button type="button" class="mini" onclick="irAPaso(2)">Volver</button>
</div>
<div class="paso" id="ps4">
<label>3) Selfie en vivo (rostro entero dentro de la guia, buena luz)</label>
<div id="videozona"><video id="v" autoplay playsinline muted></video><canvas class="ov" id="ov"></canvas></div>
<div class="estado" id="stProv">Motor de deteccion: preparando...</div>
<div class="estado" id="stV">Pulsa ABRIR CAMARA para comenzar</div>
<button type="button" class="big" id="bAbrirCam" onclick="abrirCamara()">ABRIR CAMARA</button>
<button type="button" class="ok" id="bSelfie" style="display:none" onclick="capturarSelfie()">CAPTURAR SELFIE</button>
<button type="button" id="bRepSelfie" style="display:none" onclick="abrirCamara()">REPETIR SELFIE</button>
<img class="preview" id="pS" alt="">
<button type="button" class="ok" id="bIr5" style="display:none" onclick="irAPaso(5)">Continuar</button>
<button type="button" class="mini" onclick="irAPaso(3)">Volver</button>
</div>
<div class="paso" id="ps5">
<label>4) Crea tu clave de acceso (min 8)</label>
<input type="password" id="clave">
<label>Repite la clave</label>
<input type="password" id="clave2">
<button class="big" type="submit">Crear mi ZID</button>
<button type="button" class="mini" onclick="irAPaso(4)">Volver</button>
</div>
<div id="zonaEdit">
<p style="color:#9aa0c3;font-size:13px;text-align:center">Mueve las 4 bolas verdes a las ESQUINAS del documento.</p>
<canvas id="cvEdit"></canvas>
<button type="button" class="mini" onclick="autoEsquinas()">Reintentar deteccion automatica</button>
<button type="button" class="ok" onclick="recortarDoc()">Recortar y GUARDAR (escaneo recto)</button>
<button type="button" onclick="usarFotoCompleta()">Usar foto completa sin recortar</button>
</div>
<div id="desglose"></div>
<div id="jserr"></div>
<div id="resp"></div>
</form>
<p style="text-align:center;margin-top:14px"><a href="/">Volver</a> | <a href="/entrar">Ya tengo ZID</a></p>
<p style="text-align:center;color:#4a4f7a;font-size:11px;margin-top:10px">ZYRA registro v23 - OCR automatico</p>
<script>
window.onerror=function(m,u,l){try{var b=document.getElementById("jserr");if(b){b.style.display="block";b.innerHTML="Error interno (linea "+l+"): "+m}}catch(e){}};
var DF="",DA="",DS="";
var datosDocF=null,datosDocA=null,minorBloqueado=false;
var docImg=null,docLado="",docCrudoF="",docCrudoA="",editListo=false;
var quad=null,procesandoDoc=false;
var cam=null,cara=null,alineado=false,detTipo="",apiCara=null,mpDetector=null,capturando=false;
var promesaCara=null;
var ZX=null,zxListo=false;
function R(id){return document.getElementById(id)}
function kb(s){return Math.round(s.length*3/4/1024)}
function dormir(ms){return new Promise(function(res){setTimeout(res,ms)})}
function partesNombre(v){return (v||"").trim().split(/\s+/).filter(function(x){return x.length>1})}
function propIdeal(){return R("tipoDoc").value=="pasaporte"?1.41:1.586}
function zyComprimir(dataUrl,maxLado,calidad){return new Promise(function(res){var im=new Image();im.onload=function(){var w=im.width,h=im.height,e=Math.min(1,maxLado/Math.max(w,h)),c=document.createElement("canvas");c.width=Math.round(w*e);c.height=Math.round(h*e);c.getContext("2d").drawImage(im,0,0,c.width,c.height);res(c.toDataURL("image/jpeg",calidad).split(",").pop())};im.onerror=function(){res(dataUrl.split(",").pop())};im.src=dataUrl})}
function luma(dataUrl){return new Promise(function(res){var im=new Image();im.onload=function(){var c=document.createElement("canvas");c.width=40;c.height=40;c.getContext("2d").drawImage(im,0,0,40,40);var d=c.getContext("2d").getImageData(0,0,40,40).data,t=0;for(var i=0;i<d.length;i+=4){t+=0.299*d[i]+0.587*d[i+1]+0.114*d[i+2]}res(t/(d.length/4))};im.onerror=function(){res(99)};im.src=dataUrl})}
function cargarScript(s){return new Promise(function(res,rej){var e=document.createElement("script");e.src=s;e.onload=res;e.onerror=rej;document.head.appendChild(e)})}
function setProv(t){var e=R("stProv");if(e)e.innerHTML="Motor de deteccion: "+t}
function conTimeout(p,ms,msg){return Promise.race([p,dormir(ms).then(function(){throw new Error(msg)})])}
function ensureCara(){
if(detTipo)return Promise.resolve(detTipo);
if(!promesaCara){
promesaCara=(async function(){
try{if(window.ZXing&&ZXing.BrowserMultiFormatReader){ZX=new ZXing.BrowserMultiFormatReader();zxListo=true}}catch(e){}
var m=null,fs=null;
try{
m=await import("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs");
fs=await m.FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm");
}catch(e){m=null}
if(m&&fs){
var dels=["GPU","CPU"];
for(var i=0;i<dels.length;i++){
try{
mpDetector=await m.FaceDetector.createFromOptions(fs,{baseOptions:{modelAssetPath:"https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",delegate:dels[i]},runningMode:"IMAGE",minDetectionConfidence:0.25});
detTipo="mediapipe";setProv("MediaPipe (Google, "+dels[i]+")");return detTipo;
}catch(e2){}
}
}
try{
await cargarScript("https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js");
await faceapi.nets.tinyFaceDetector.loadFromUri("https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights");
detTipo="faceapi";setProv("face-api.js (respaldo)");
return detTipo;
}catch(e3){}
try{if(window.FaceDetector){apiCara=new FaceDetector({fastMode:true,maxDetectedFaces:1});detTipo="nativo";setProv("nativo del navegador");return detTipo}}catch(e4){}
setProv("NO disponible (exige luz y encuadre manual)");return "";
})();
}
return promesaCara;
}
function cajaMP(fuente){
try{
var res=mpDetector.detect(fuente);
if(res&&res.detections&&res.detections.length){
var b=res.detections[0].boundingBox;
return {x:b.originX,y:b.originY,w:b.width,h:b.height};
}
}catch(e){}
return null;
}
async function cajaEnVideo(v){
var t=await ensureCara();if(!t)return null;
try{
if(t=="mediapipe")return cajaMP(v);
if(t=="faceapi"){
var r=await faceapi.detectSingleFace(v,new faceapi.TinyFaceDetectorOptions({inputSize:320,scoreThreshold:0.3}));
if(r){return {x:r.box.x,y:r.box.y,w:r.box.width,h:r.box.height}}
return null;
}
if(t=="nativo"){var fs2=await apiCara.detect(v);if(fs2.length){var b4=fs2[0].boundingBox;return {x:b4.x,y:b4.y,w:b4.width,h:b4.height}}}
}catch(e){}
return null;
}
function irAPaso(n){
var i;
for(i=1;i<=5;i++){var e=R("ps"+i);if(e)e.className="paso"+(i==n?" act":"")}
R("prog").innerHTML="PASO "+n+" DE 5";
if(n!=4){stopCam()}
if(n==2){R("stF").innerHTML=DF?("FRONTAL guardado: "+kb(DF)+" KB — toca la foto para rehacer"):"Este paso guarda el lado FRONTAL (la cara con tu foto).";}
if(n==3){
var t=R("tipoDoc").value;
R("stA").innerHTML=DA?("REVERSO guardado: "+kb(DA)+" KB — toca la foto para rehacer"):"Este paso guarda el lado de ATRAS (reverso).";
if(t=="pasaporte"){R("notaRev").innerHTML="Pasaporte: no tiene reverso. Continua.";R("notaRev").className="estado chk";R("bIr4").disabled=false}
else if(t=="permiso"){R("notaRev").innerHTML="Si tu permiso tiene reverso, tomale foto. Si no, usa el boton de abajo.";R("notaRev").className="estado";R("bIr4").disabled=!DA}
else{R("notaRev").innerHTML="Este documento SI requiere reverso.";R("notaRev").className="estado";R("bIr4").disabled=!DA}
}
window.scrollTo(0,0);
}
function saltarReverso(){
DA="";R("stA").innerHTML="";R("pA").style.display="none";
irAPaso(4);
}
function irDe1(){
var nm=R("nombre").value.trim();
if(nm.length<3||partesNombre(nm).length<2){R("resp").innerHTML="<p style='color:#f85149'>Escribe tu nombre y apellido (ej: Juan Perez).</p>";window.scrollTo(0,document.body.scrollHeight);return}
R("resp").innerHTML="";
irAPaso(2);
}
function tomarFoto(lado){
if(procesandoDoc){R("st"+lado).innerHTML="Espera: procesando la foto anterior...";return}
var inp=R(lado=="F"?"fileF":"fileA");
inp.value="";
inp.click();
}
function elegirArchivo(lado){
if(procesandoDoc){R("st"+lado).innerHTML="Espera: procesando la foto anterior...";return}
var inp=R(lado=="F"?"galF":"galA");
inp.value="";
inp.click();
}
function quadInicial(im){
var pr=propIdeal();
var fw=im.width*0.8,fh=fw/pr;
if(fh>im.height*0.92){fh=im.height*0.92;fw=fh*pr}
var x=(im.width-fw)/2,y=(im.height-fh)/2;
return {tl:{x:x,y:y},tr:{x:x+fw,y:y},br:{x:x+fw,y:y+fh},bl:{x:x,y:y+fh}};
}
function detectarEsquinas(im){
try{
var W=460;
var sc=Math.min(1,W/im.width);
var cw=Math.max(80,Math.round(im.width*sc)),ch=Math.max(60,Math.round(im.height*sc));
var c=document.createElement("canvas");c.width=cw;c.height=ch;
var g=c.getContext("2d");g.drawImage(im,0,0,cw,ch);
var d=g.getImageData(0,0,cw,ch).data;
var N=cw*ch;
var lum=new Float32Array(N);
var i,s=0,s2=0;
for(i=0;i<N;i++){var k=i*4;lum[i]=0.299*d[k]+0.587*d[k+1]+0.114*d[k+2];s+=lum[i];s2+=lum[i]*lum[i];}
var mu=s/N,va=s2/N-mu*mu,de=Math.sqrt(Math.max(0,va))||1;
var vis=new Uint8Array(N);
var cola=new Int32Array(N);
var best=null,bestScore=0;
var pasadas=[1,-1];
for(var pi=0;pi<2;pi++){
var sg=pasadas[pi];
for(i=0;i<N;i++)vis[i]=0;
for(i=0;i<N;i++){
if(vis[i])continue;
if((lum[i]-mu)*sg<=0.32*de)continue;
vis[i]=1;
var qh=0,qt=0;cola[qt++]=i;
var minx=1e9,maxx=-1,miny=1e9,maxy=-1,cnt=0;
while(qh<qt){
var p=cola[qh++];cnt++;
var py=(p/cw)|0,px=p%cw;
if(px<minx)minx=px;if(px>maxx)maxx=px;if(py<miny)miny=py;if(py>maxy)maxy=py;
var q;
if(px+1<cw){q=p+1;if(!vis[q]&&(lum[q]-mu)*sg>0.32*de){vis[q]=1;cola[qt++]=q}}
if(px-1>=0){q=p-1;if(!vis[q]&&(lum[q]-mu)*sg>0.32*de){vis[q]=1;cola[qt++]=q}}
if(py+1<ch){q=p+cw;if(!vis[q]&&(lum[q]-mu)*sg>0.32*de){vis[q]=1;cola[qt++]=q}}
if(py-1>=0){q=p-cw;if(!vis[q]&&(lum[q]-mu)*sg>0.32*de){vis[q]=1;cola[qt++]=q}}
}
var w=(maxx-minx+1)/cw,h2=(maxy-miny+1)/ch;
var r=w/h2;
var lleno=cnt/((maxx-minx+1)*(maxy-miny+1)||1);
if(cnt>N*0.05&&w>0.20&&w<0.99&&h2>0.10&&h2<0.99&&r>0.45&&r<3.4&&lleno>0.55){
var score=cnt*lleno;
var dr=Math.abs(r-propIdeal());
score*=Math.max(0.35,1.6-dr);
if(score>bestScore){bestScore=score;best={minx:minx,maxx:maxx,miny:miny,maxy:maxy};}
}
}
}
if(!best)return null;
var mx=((best.minx+best.maxx)/2)*im.width/cw;
var my=((best.miny+best.maxy)/2)*im.height/ch;
var gw0=(best.maxx-best.minx+1)*im.width/cw;
var gh0=(best.maxy-best.miny+1)*im.height/ch;
var r0=gw0/(gh0||1);
var pr=propIdeal();
var gw,ghe;
if(r0>0.5&&r0<3.2){gw=Math.min(im.width*0.98,gw0*1.10);ghe=Math.min(im.height*0.98,gh0*1.10)}
else{ghe=Math.min(im.height*0.98,gh0*1.10);gw=ghe*pr}
if(gw/ghe<0.5){gw=ghe*0.5}
if(gw/ghe>3.2){gw=ghe*3.2}
var gx=mx-gw/2,gy=my-ghe/2;
if(gx<3)gx=3;if(gy<3)gy=3;
if(gx+gw>im.width-3)gx=im.width-3-gw;
if(gy+ghe>im.height-3)gy=im.height-3-ghe;
return {tl:{x:gx,y:gy},tr:{x:gx+gw,y:gy},br:{x:gx+gw,y:gy+ghe},bl:{x:gx,y:gy+ghe}};
}catch(e){return null}
}
function edadDe(iso){try{var f=new Date(iso+"T00:00:00");if(isNaN(f))return -1;var h=new Date();var e=h.getFullYear()-f.getFullYear();var m=h.getMonth()-f.getMonth();if(m<0||(m===0&&h.getDate()<f.getDate()))e--;return e}catch(e){return -1}}
function nombresCoinciden(a,b){try{a=(a||"").toLowerCase().replace(/[^a-z ]/g,"").split(/\s+/).filter(function(x){return x.length>2});b=(b||"").toLowerCase().replace(/[^a-z ]/g,"").split(/\s+/).filter(function(x){return x.length>2});if(!a.length||!b.length)return true;var hit=0;for(var i=0;i<a.length;i++){if(b.indexOf(a[i])>=0)hit++}return hit>0}catch(e){return true}}
function parseAAMVA(raw){
try{
var claves=["DAB","DAC","DAD","DBB","DAQ","DAG","DAI","DAJ","DAK","DCF"];
var fnd=[];
for(var c=0;c<claves.length;c++){
var ix=raw.indexOf(claves[c]);
while(ix>=0){fnd.push([ix,claves[c]]);ix=raw.indexOf(claves[c],ix+1)}
}
fnd.sort(function(a,b){return a[0]-b[0]});
if(fnd.length<3)return null;
var res={};
for(var i=0;i<fnd.length;i++){
var fin=(i+1<fnd.length)?fnd[i+1][0]:Math.min(fnd[i][0]+70,raw.length);
res[fnd[i][1]]=raw.slice(fnd[i][0]+3,fin).trim();
}
if(!res.DBB||res.DBB.length<8)return null;
var iso=res.DBB.slice(4,8)+"-"+res.DBB.slice(0,2)+"-"+res.DBB.slice(2,4);
return {nombre:((res.DAC||"")+" "+(res.DAD||"")+" "+(res.DAB||"")).trim(),nacimiento:iso,edad:edadDe(iso),numero:(res.DAQ||res.DCF||""),direccion:((res.DAI||"")+" "+(res.DAG||"")+" "+(res.DAJ||"")+" "+(res.DAK||"")).trim()};
}catch(e){return null}
}
async function leerCodigoDeCanvas(cv){
try{
if(window.BarcodeDetector){
try{
var bd=new BarcodeDetector({formats:["pdf417","qr_code","code_128","code_39"]});
var fs=await bd.detect(cv);
if(fs&&fs.length){var rv=fs[0].rawValue||"";if(rv.length>20)return parseAAMVA(rv)}
}catch(e){}
}
if(zxListo){
try{
var res2=await ZX.decodeFromCanvas(cv);
if(res2&&res2.length){var t2=res2[0].getText()||"";if(t2.length>20)return parseAAMVA(t2)}
}catch(e){}
}
}catch(e){}
return null;
}
async function leerCodigo(dataUrl){
try{
var im=new Image();
var p=new Promise(function(res){im.onload=function(){res(true)};im.onerror=function(){res(false)};im.src="data:image/jpeg;base64,"+dataUrl});
var ok=await p;if(!ok)return null;
var cv=document.createElement("canvas");cv.width=im.width;cv.height=im.height;
cv.getContext("2d").drawImage(im,0,0);
var d1=await leerCodigoDeCanvas(cv);
if(d1)return d1;
var cv2=document.createElement("canvas");
cv2.width=Math.round(im.width/2);cv2.height=Math.round(im.height/2);
cv2.getContext("2d").drawImage(im,0,0,cv2.width,cv2.height);
return await leerCodigoDeCanvas(cv2);
}catch(e){}
return null;
}
function sinRaros(s){var r="";var ok="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";for(var i=0;i<s.length;i++){var ch=s.charAt(i);if(ok.indexOf(ch)>=0||ch===" ")r+=ch}return r}
async function ocrDoc(dataUrl){
try{
if(!window.Tesseract)return null;
var ret=await Tesseract.recognize("data:image/jpeg;base64,"+dataUrl,"eng");
var t=(ret&&ret.data&&ret.data.text)?ret.data.text:"";
if(t.trim().length<20)return null;
var lineas=t.split("\n");
var nombre="";
for(var i=0;i<lineas.length;i++){
var ln=sinRaros(lineas[i]).trim();
var partes=ln.split(" ").filter(function(x){return x.length>2});
if(partes.length>=2&&!nombre){nombre=partes.join(" ")}
}
var fechas=[];
var pedazos=t.split(/[^0-9]/);
var buf="";
for(var j=0;j<pedazos.length;j++){
if(pedazos[j].length>0){buf+=pedazos[j];if(buf.length===8){fechas.push(buf);buf=""}}else{if(buf.length===8)fechas.push(buf);buf=""}}
if(buf.length===8)fechas.push(buf);
return {nombre:nombre,texto:t.trim().substring(0,400),fechas:fechas};
}catch(e){return null}
}
async function leerTodo(comp){
var r1=await leerCodigo(comp);
if(r1)return r1;
var r2=await ocrDoc(comp);
if(r2){try{var nm=R("nombre").value.trim();if(r2.nombre&&nm.length<3){R("nombre").value=r2.nombre}}catch(e){}}
return r2;
}
function mostrarDesglose(){
var d=R("desglose");if(!d)return;
var h="";var fuente=null,nom=R("nombre").value.trim();
if(datosDocF){fuente=datosDocF;h+="<p style='color:#3fb950'>FRONTAL leido: "+(fuente.nombre||"(sin nombre)")+" | Nac: "+(fuente.nacimiento||"?")+" | Edad: "+fuente.edad+"</p>"}
if(datosDocA){fuente=datosDocA;h+="<p style='color:#3fb950'>REVERSO leido: "+(fuente.nombre||"(sin nombre)")+" | Nac: "+(fuente.nacimiento||"?")+" | Edad: "+fuente.edad+" | No.: "+(fuente.numero||"(no leido)")+((fuente.direccion)?" | Dir: "+fuente.direccion:"")+"</p>"}
if(!datosDocF&&!datosDocA){h="<p style='color:#9aa0c3'>Desglose: este documento no trae codigo legible (o no se detecto). El registro sigue normal.</p>";minorBloqueado=false}
if(fuente){
if(fuente.edad>=0&&fuente.edad<18){minorBloqueado=true;h+="<p style='color:#f85149;font-weight:700'>MENOR DE EDAD ("+fuente.edad+"): registro de adultos bloqueado. Los menores se registran con tutor.</p>"}
else{minorBloqueado=false;if(fuente.edad>=0){h+="<p style='color:#3fb950'>Mayoria de edad por documento: "+fuente.edad+" anos</p>"}}
if(fuente.nombre&&nom&&nombresCoinciden(fuente.nombre,nom)){h+="<p style='color:#3fb950'>Cruce de nombre: coincide</p>"}
else if(fuente.nombre&&nom){h+="<p style='color:#f0b429'>Aviso: el nombre escrito no coincide con el del documento</p>"}
if(fuente.nombre&&nom.length<3){R("nombre").value=fuente.nombre}
}
var fv=R("vencimiento")?R("vencimiento").value:"";
if(fv){var hoy=new Date();hoy.setHours(0,0,0,0);var fvd=new Date(fv+"T00:00:00");if(fvd&&fvd<hoy){h+="<p style='color:#f85149;font-weight:700'>Documento VENCIDO ("+fv+"): no se acepta.</p>"}else{h+="<p style='color:#3fb950'>Vencimiento del documento: "+fv+"</p>"}}
if(fuente&&fuente.texto){h+="<p style='color:#7c8cf8'>Texto leido por OCR del documento (revisalo y corrige si algo salio mal): "+fuente.texto.split("<").join("&lt;")+"</p>"}
d.innerHTML=h;
}
async function cargarDoc(inp,lado){
var f=inp.files&&inp.files[0];if(!f)return;
if(procesandoDoc)return;
procesandoDoc=true;
var bt=R(lado=="F"?"btF":"btA");
bt.disabled=true;
var st=R("st"+lado);
st.innerHTML="PROCESANDO (maximo 15s)...";
st.className="estado";st.style.color="#f0b429";
try{
var fr2=new FileReader();
var pfr=new Promise(function(res,rej){fr2.onload=function(){res(fr2.result)};fr2.onerror=function(){rej(new Error("lectura"))}});
fr2.readAsDataURL(f);
var crudo=await conTimeout(pfr,15000,"lectura lenta");
var comp=await conTimeout(zyComprimir(crudo,1200,0.78),15000,"compresion lenta");
var pL=leerTodo(comp);
pL.then(function(_leido){if(_leido){if(lado=="A"){datosDocA=_leido}else{datosDocF=_leido}}});
var L=await conTimeout(luma(comp),15000,"luz lenta");
if(L<40){st.innerHTML="Foto muy oscura (luz "+Math.round(L)+"/100). Tomala con buena luz.";st.className="estado mal";procesandoDoc=false;bt.disabled=false;return}
abrirEditor(lado,comp);
procesandoDoc=false;bt.disabled=false;
}catch(e){
st.innerHTML="La foto tardo demasiado ("+e+"). Reintenta o elige otra.";
st.className="estado mal";
procesandoDoc=false;bt.disabled=false;
}
}
function abrirEditor(lado,comp){
docLado=lado;
if(lado=="F"){docCrudoF=comp}else{docCrudoA=comp}
var st=R("st"+lado);st.className="estado";st.style.color="#9aa0c3";
var im=new Image();
st.innerHTML="Abriendo editor...";
im.onload=function(){
docImg=im;
quad=quadInicial(im);
R("zonaEdit").style.display="block";
pintarEditor();
if(!editListo){iniciarEdit();editListo=true}
st.innerHTML="Ajusta si hace falta y GUARDA (o Reintentar deteccion).";
autoEsquinas();
};
im.src="data:image/jpeg;base64,"+comp;
}
function autoEsquinas(){
if(!docImg)return;
var st=R("st"+docLado);
st.innerHTML="Buscando esquinas (rapido)...";
var im=docImg,lado=docLado;
var q=null;
try{q=detectarEsquinas(im)}catch(e){}
if(q&&docImg===im){
quad=q;pintarEditor();
st.innerHTML="Esquinas detectadas. Verifica y GUARDA.";
}else if(docImg===im){
st.innerHTML="Coloca las 4 bolas en las esquinas con el dedo.";
}
}
function pintarEditor(){
var cv=R("cvEdit"),g=cv.getContext("2d"),im=docImg;
if(!im||!quad)return;
var maxW=Math.min(480,im.width);
cv.width=maxW;cv.height=Math.round(maxW*im.height/im.width);
var e=cv.width/im.width;
g.clearRect(0,0,cv.width,cv.height);
g.drawImage(im,0,0,cv.width,cv.height);
g.fillStyle="rgba(0,0,0,0.45)";
g.beginPath();
g.moveTo(0,0);g.lineTo(cv.width,0);g.lineTo(cv.width,cv.height);g.lineTo(0,cv.height);g.closePath();
g.moveTo(quad.tl.x*e,quad.tl.y*e);g.lineTo(quad.tr.x*e,quad.tr.y*e);g.lineTo(quad.br.x*e,quad.br.y*e);g.lineTo(quad.bl.x*e,quad.bl.y*e);g.closePath();
g.fill("evenodd");
g.strokeStyle="#3fb950";g.lineWidth=3;
g.beginPath();
g.moveTo(quad.tl.x*e,quad.tl.y*e);g.lineTo(quad.tr.x*e,quad.tr.y*e);g.lineTo(quad.br.x*e,quad.br.y*e);g.lineTo(quad.bl.x*e,quad.bl.y*e);g.closePath();
g.stroke();
var pts=[quad.tl,quad.tr,quad.br,quad.bl];
for(var i=0;i<4;i++){
g.fillStyle="#3fb950";
g.beginPath();g.arc(pts[i].x*e,pts[i].y*e,11,0,6.3);g.fill();
g.fillStyle="#0d1126";
g.beginPath();g.arc(pts[i].x*e,pts[i].y*e,4,0,6.3);g.fill();
}
}
function clampQuad(){
if(!docImg||!quad)return;
var pts=[quad.tl,quad.tr,quad.br,quad.bl];
for(var i=0;i<4;i++){
if(pts[i].x<2)pts[i].x=2;
if(pts[i].y<2)pts[i].y=2;
if(pts[i].x>docImg.width-2)pts[i].x=docImg.width-2;
if(pts[i].y>docImg.height-2)pts[i].y=docImg.height-2;
}
}
function iniciarEdit(){
var cv=R("cvEdit");
var arr=-1;
function pos(ev){var r=cv.getBoundingClientRect();var t=(ev.touches&&ev.touches[0])||ev;return {x:(t.clientX-r.left)*cv.width/r.width,y:(t.clientY-r.top)*cv.height/r.height}}
function abajo(ev){
if(!docImg||!quad)return;
var p=pos(ev);var e=cv.width/docImg.width;
var pts=[quad.tl,quad.tr,quad.br,quad.bl];
var mejor=-1,md=52;
for(var i=0;i<4;i++){
var dd=Math.hypot(p.x-pts[i].x*e,p.y-pts[i].y*e);
if(dd<md){md=dd;mejor=i}
}
arr=mejor;
if(arr>=0)ev.preventDefault();
}
function mover(ev){
if(arr<0||!docImg||!quad)return;
var p=pos(ev);var e=cv.width/docImg.width;
var pts=[quad.tl,quad.tr,quad.br,quad.bl];
pts[arr].x=p.x/e;pts[arr].y=p.y/e;
clampQuad();pintarEditor();ev.preventDefault();
}
cv.addEventListener("pointerdown",abajo,false);
cv.addEventListener("pointermove",mover,false);
["pointerup","pointercancel","pointerleave"].forEach(function(t){cv.addEventListener(t,function(){arr=-1},false)});
}
function resolverH(srcp,dstp){
var A=[];
for(var i=0;i<8;i++){
var x=srcp[i][0],y=srcp[i][1],u=dstp[i][0],v=dstp[i][1];
if(i<4)A.push([x,y,1,0,0,0,-x*u,-y*u,u]);
else A.push([0,0,0,x,y,1,-x*v,-y*v,v]);
}
for(var c2=0;c2<8;c2++){
var piv=c2,r2;
for(r2=c2+1;r2<8;r2++){if(Math.abs(A[r2][c2])>Math.abs(A[piv][c2]))piv=r2}
var tmp=A[c2];A[c2]=A[piv];A[piv]=tmp;
var pv=A[c2][c2];if(Math.abs(pv)<1e-12)return null;
for(var j2=c2;j2<=8;j2++)A[c2][j2]/=pv;
for(r2=0;r2<8;r2++){
if(r2===c2)continue;
var f2=A[r2][c2];if(f2===0)continue;
for(var j3=c2;j3<=8;j3++)A[r2][j3]-=f2*A[c2][j3];
}
}
return [A[0][8],A[1][8],A[2][8],A[3][8],A[4][8],A[5][8],A[6][8],A[7][8],1];
}
function inversaH(H){
var a=H[0],b=H[1],c=H[2],d=H[3],e=H[4],f=H[5],g2=H[6],h2=H[7],ii=H[8];
var det=a*(e*ii-f*h2)-b*(d*ii-f*g2)+c*(d*h2-e*g2);
if(Math.abs(det)<1e-12)return null;
return [
(e*ii-f*h2)/det,(c*h2-b*ii)/det,(b*f-c*e)/det,(f*g2-d*ii)/det,(a*ii-c*g2)/det,(c*d-a*f)/det,(d*h2-e*g2)/det,(b*g2-a*h2)/det,(a*e-b*d)/det
];
}
function warpQuad(im,q,maxLado){
try{
function dist(ax,ay,bx,by){return Math.hypot(ax-bx,ay-by)}
var dw=(dist(q.tl.x,q.tl.y,q.tr.x,q.tr.y)+dist(q.bl.x,q.bl.y,q.br.x,q.br.y))/2;
var dh=(dist(q.tl.x,q.tl.y,q.bl.x,q.bl.y)+dist(q.tr.x,q.tr.y,q.br.x,q.br.y))/2;
if(dw<40||dh<40)return null;
var esc=Math.min(1,maxLado/Math.max(dw,dh));
var W2=Math.max(20,Math.round(dw*esc)),H2b=Math.max(20,Math.round(dh*esc));
var srcp=[[q.tl.x,q.tl.y],[q.tr.x,q.tr.y],[q.br.x,q.br.y],[q.bl.x,q.bl.y]];
var dstp=[[0,0],[W2,0],[W2,H2b],[0,H2b]];
var Hf=resolverH(srcp,dstp);if(!Hf)return null;
var Hi=inversaH(Hf);if(!Hi)return null;
var cf=document.createElement("canvas");cf.width=im.width;cf.height=im.height;
var gf=cf.getContext("2d");gf.drawImage(im,0,0);
var df=gf.getImageData(0,0,im.width,im.height).data;
var cd=document.createElement("canvas");cd.width=W2;cd.height=H2b;
var gd=cd.getContext("2d");
var od=gd.createImageData(W2,H2b);
var out=od.data,xp,yp;
for(yp=0;yp<H2b;yp++){
for(xp=0;xp<W2;xp++){
var w3=Hi[6]*xp+Hi[7]*yp+Hi[8];
var fx=(Hi[0]*xp+Hi[1]*yp+Hi[2])/w3;
var fy=(Hi[3]*xp+Hi[4]*yp+Hi[5])/w3;
var x0=Math.floor(fx),y0=Math.floor(fy);
if(x0<0||y0<0||x0>=im.width-1||y0>=im.height-1)continue;
var dx=fx-x0,dy=fy-y0;
var i00=(y0*im.width+x0)*4,i10=i00+4,i01=i00+im.width*4,i11=i01+4;
var o=(yp*W2+xp)*4;
for(var ch3=0;ch3<3;ch3++){
out[o+ch3]=df[i00+ch3]*(1-dx)*(1-dy)+df[i10+ch3]*dx*(1-dy)+df[i01+ch3]*(1-dx)*dy+df[i11+ch3]*dx*dy;
}
out[o+3]=255;
}
}
gd.putImageData(od,0,0);
return cd.toDataURL("image/jpeg",0.82).split(",").pop();
}catch(e){return null}
}
function medirCalidad(dataUrl){
return new Promise(function(res){
var im=new Image();
im.onload=function(){
var W=240;
var sc=Math.min(1,W/im.width);
var cw=Math.max(40,Math.round(im.width*sc)),ch2=Math.max(40,Math.round(im.height*sc));
var c=document.createElement("canvas");c.width=cw;c.height=ch2;
var g=c.getContext("2d");g.drawImage(im,0,0,cw,ch2);
var d=g.getImageData(0,0,cw,ch2).data;
var t=0,n=cw*ch2,gr=0,i;
for(i=0;i<n;i++){var k=i*4;t+=0.299*d[k]+0.587*d[k+1]+0.114*d[k+2]}
var br=t/n;
for(i=1;i<n-1;i++){
var k1=i*4,k2=(i+1)*4,k3=(i-1)*4;
var v1=0.299*d[k1]+0.587*d[k1+1]+0.114*d[k1+2];
var v2=0.299*d[k2]+0.587*d[k2+1]+0.114*d[k2+2];
var v3=0.299*d[k3]+0.587*d[k3+1]+0.114*d[k3+2];
gr+=Math.abs(v2-v1)+Math.abs(v2-v3);
}
res({brillo:br,nitidez:gr/((n-2)*2)});
};
im.onerror=function(){res({brillo:128,nitidez:9})};
im.src="data:image/jpeg;base64,"+dataUrl;
});
}
function stretchLuz(dataUrl){
return new Promise(function(res){
var im=new Image();
im.onload=function(){
var c=document.createElement("canvas");c.width=im.width;c.height=im.height;
var g=c.getContext("2d");g.drawImage(im,0,0);
var d=g.getImageData(0,0,im.width,im.height).data;
var t=0,n=im.width*im.height,i;
for(i=0;i<n;i++){var k=i*4;t+=0.299*d[k]+0.587*d[k+1]+0.114*d[k+2]}
var br=t/n;
var f=Math.max(1,Math.min(2.1,105/br));
if(f<=1.02){res(dataUrl);return}
for(i=0;i<n*4;i+=4){
d[i]=Math.min(255,d[i]*f);
d[i+1]=Math.min(255,d[i+1]*f);
d[i+2]=Math.min(255,d[i+2]*f);
}
g.putImageData(g.getImageData(0,0,im.width,im.height),0,0);
res(c.toDataURL("image/jpeg",0.82).split(",").pop());
};
im.onerror=function(){res(dataUrl)};
im.src="data:image/jpeg;base64,"+dataUrl;
});
}
function guardarEn(l,comp,txt){
if(l=="F"){DF=comp}else{DA=comp}
var pv=R(l=="F"?"pF":"pA");
pv.src="data:image/jpeg;base64,"+comp;pv.style.display="block";
var st=R("st"+l);
st.innerHTML=txt;st.className="estado chk";
R("zonaEdit").style.display="none";docImg=null;
mostrarDesglose();
if(l=="F"){irAPaso(3)}else{R("bIr4").disabled=false;irAPaso(4)}
}
async function recortarDoc(){
if(!docImg||!quad)return;
var st=R("st"+docLado);
st.innerHTML="Escaneando (correccion de perspectiva)...";
var comp=warpQuad(docImg,quad,1100);
if(!comp){
var xs=[quad.tl.x,quad.tr.x,quad.br.x,quad.bl.x],ys=[quad.tl.y,quad.tr.y,quad.br.y,quad.bl.y];
var x0=Math.max(0,Math.min.apply(null,xs)),y0=Math.max(0,Math.min.apply(null,ys));
var x1=Math.min(docImg.width,Math.max.apply(null,xs)),y1=Math.min(docImg.height,Math.max.apply(null,ys));
var c=document.createElement("canvas");
c.width=Math.max(20,Math.round(x1-x0));c.height=Math.max(20,Math.round(y1-y0));
c.getContext("2d").drawImage(docImg,x0,y0,c.width,c.height,0,0,c.width,c.height);
comp=c.toDataURL("image/jpeg",0.8).split(",").pop();
}
guardarEn(docLado,comp,"GUARDADO (escaneo recto): "+kb(comp)+" KB");
}
function usarFotoCompleta(){
var comp=docLado=="F"?docCrudoF:docCrudoA;
if(!comp)return;
guardarEn(docLado,comp,"GUARDADO COMPLETO: "+kb(comp)+" KB (sin recortar)");
}
function reeditar(lado){
var comp=lado=="F"?docCrudoF:docCrudoA;
if(comp)abrirEditor(lado,comp);
}
async function abrirCamara(){
var st=R("stV");
try{
R("videozona").style.display="block";
R("bAbrirCam").style.display="none";
R("bRepSelfie").style.display="none";
cam=await navigator.mediaDevices.getUserMedia({video:{facingMode:"user",width:{ideal:640},height:{ideal:480}}});
var v=R("v");v.srcObject=cam;
R("bSelfie").style.display="block";
st.innerHTML="Centra tu rostro dentro de la guia con buena luz.";
ensureCara();loop();
}catch(e){
st.innerHTML="No se pudo abrir la camara: "+e;st.className="estado mal";
R("bAbrirCam").style.display="block";
}
}
function stopCam(){
if(cam){try{cam.getTracks().forEach(function(t){t.stop()})}catch(e){}}
cam=null;
R("videozona").style.display="none";
R("bSelfie").style.display="none";
}
async function loop(){
var v=R("v"),ov=R("ov");
setInterval(async function(){
if(!cam||v.readyState<2)return;
var vw=v.videoWidth,vh=v.videoHeight;if(!vw)return;
if(ov.width!=vw){ov.width=vw;ov.height=vh}
var g=ov.getContext("2d");g.clearRect(0,0,ov.width,ov.height);
var o={cx:vw/2,cy:vh*0.46,rx:vw*0.22,ry:vh*0.31};
try{
var caja=await cajaEnVideo(v);
cara=caja;
alineado=false;
if(caja){
var fcx=caja.x+caja.w/2,fcy=caja.y+caja.h/2;
var nx=(fcx-o.cx)/(o.rx*0.55),ny=(fcy-o.cy)/(o.ry*0.55);
var wr=caja.w/vw;
alineado=((nx*nx+ny*ny)<=1&&wr>0.16&&wr<0.60);
var col=alineado?"#3fb950":"#f0b429";
g.strokeStyle="rgba(63,185,80,0.25)";if(!alineado)g.strokeStyle="rgba(240,180,41,0.25)";
g.lineWidth=9;
g.beginPath();g.ellipse(o.cx,o.cy,o.rx,o.ry,0,0,6.3);g.stroke();
g.strokeStyle=col;g.lineWidth=1.6;
g.beginPath();g.ellipse(o.cx,o.cy,o.rx,o.ry,0,0,6.3);g.stroke();
g.lineWidth=4;
var angs=[0.785,2.356,3.927,5.498];
for(var a2=0;a2<4;a2++){
g.beginPath();
g.ellipse(o.cx,o.cy,o.rx,o.ry,0,angs[a2]-0.38,angs[a2]+0.38);
g.stroke();
}
if(alineado){g.strokeStyle="#3fb950";g.lineWidth=3;g.strokeRect(caja.x,caja.y,caja.w,caja.h)}
if(!capturando){
if(alineado){R("stV").innerHTML="Encuadre perfecto: pulsa CAPTURAR";R("stV").className="estado";R("stV").style.color="#3fb950"}
else{R("stV").innerHTML="Centra tu rostro dentro de la guia (entero, no a medias)";R("stV").className="estado";R("stV").style.color="#f0b429"}
}
}else{
g.strokeStyle="#f85149";g.lineWidth=3;
g.beginPath();g.ellipse(o.cx,o.cy,o.rx,o.ry,0,0,6.3);g.stroke();
if(!capturando){R("stV").innerHTML="No veo tu rostro. Busca buena luz frente a la camara.";R("stV").style.color="#9aa0c3"}
}
}catch(e){}
},250);
}
async function capturarSelfie(){
if(capturando)return false;
var st=R("stV"),v=R("v");
if(!cam||!v.videoWidth){st.innerHTML="Abre la camara primero.";st.className="estado mal";return false}
capturando=true;R("bSelfie").disabled=true;
st.innerHTML="Verificando luz, rostro y encuadre...";st.className="estado";
st.style.color="#f0b429";
var i=0;while(!cara&&i<10){await dormir(300);i++}
var c=document.createElement("canvas");c.width=v.videoWidth;c.height=v.videoHeight;
var g=c.getContext("2d");g.translate(c.width,0);g.scale(-1,1);g.drawImage(v,0,0);
var crudo=c.toDataURL("image/jpeg",0.85);
var L=await luma(crudo);
if(L<60){
st.innerHTML="LUZ INSUFICIENTE ("+Math.round(L)+"/100). NO se guardo.";
st.className="estado mal";
capturando=false;R("bSelfie").disabled=false;
return false;
}
if(detTipo!=""&&!cara){
st.innerHTML="NO VEO TU ROSTRO con buena luz. NO se guardo.";
st.className="estado mal";
capturando=false;R("bSelfie").disabled=false;
return false;
}
if(detTipo!=""&&!alineado){
st.innerHTML="ENCUADRE INCOMPLETO: rostro entero dentro de la guia. NO se guardo.";
st.className="estado mal";
capturando=false;R("bSelfie").disabled=false;
return false;
}
var comp=await zyComprimir(crudo,720,0.65);
DS=comp;
stopCam();
R("bAbrirCam").style.display="none";
R("bRepSelfie").style.display="block";
R("bIr5").style.display="block";
R("pS").src="data:image/jpeg;base64,"+comp;R("pS").style.display="block";
st.innerHTML="SELFIE GUARDADA: "+kb(comp)+" KB (luz "+Math.round(L)+"/100, encuadre verificado)";st.className="estado chk";
capturando=false;R("bSelfie").disabled=false;
setTimeout(function(){irAPaso(5)},900);
return true;
}
async function enviar(ev){ev.preventDefault();var Rr=R("resp");
var c1=R("clave").value,c2=R("clave2").value;
var tipo=R("tipoDoc").value;
var nmv=R("nombre").value.trim();
var reqRev=(tipo=="dui"||tipo=="licencia"||tipo=="id_usa");
if(nmv.length<3||partesNombre(nmv).length<2){Rr.innerHTML="<p style='color:#f85149'>Falta nombre y apellido (ej: Juan Perez).</p>";window.scrollTo(0,document.body.scrollHeight);return false}
if(minorBloqueado){Rr.innerHTML="<p style='color:#f85149'>El documento indica MENOR de edad: los menores se registran con tutor.</p>";return false}
if(c1!==c2){Rr.innerHTML="<p style='color:#f85149'>Las claves no coinciden.</p>";return false}
if(c1.length<8){Rr.innerHTML="<p style='color:#f85149'>La clave necesita minimo 8 caracteres.</p>";return false}
if(!DF){Rr.innerHTML="<p style='color:#f85149'>Falta el documento frontal (paso 2).</p>";return false}
if(reqRev&&!DA){Rr.innerHTML="<p style='color:#f85149'>Este documento requiere el reverso (paso 3).</p>";return false}
if(!DS){Rr.innerHTML="<p style='color:#f85149'>Falta la selfie (paso 4).</p>";return false}
          var fv2=R("vencimiento")?R("vencimiento").value:"";
          if(fv2){var hoy2=new Date();hoy2.setHours(0,0,0,0);var fvd2=new Date(fv2+"T00:00:00");if(fvd2&&fvd2<hoy2){Rr.innerHTML="<p style='color:#f85149;font-weight:700'>DOCUMENTO VENCIDO ("+fv2+"): un documento vencido no es prueba de identidad legal. NO se crea el ZID.</p>";window.scrollTo(0,document.body.scrollHeight);return false}}
Rr.innerHTML="<p style='color:#8b949e'>Enviando a la Red ("+kb(DF)+" y "+kb(DS)+" KB)...</p>";
window.scrollTo(0,document.body.scrollHeight);
try{var r=await fetch("/registro/nuevo",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({nombre:nmv,clave:c1,doc_image_b64:DF,doc_back_b64:DA,selfie_image_b64:DS,doc_type:tipo,doc_number:((datosDocA&&datosDocA.numero)||(datosDocF&&datosDocF.numero)||"")})});
var j=await r.json();
if(j.ok&&j.zid){Rr.innerHTML="<div style='background:#0f2a1a;border:1px solid #238636;border-radius:12px;padding:14px'><p style='color:#3fb950;font-weight:800;font-size:17px'>REGISTRO EXITOSO</p><p>Tu ZID unico fue creado:</p><p class='zid'>"+j.zid+"</p><p>Guarda tu ZID y tu clave. Nadie mas puede crearlo.</p><p><a href='/entrar'>ENTRAR AHORA</a></p></div>";}
else if(j.codigo==="mantenimiento"){Rr.innerHTML="<div style='background:#2a2410;border:1px solid #f0b429;border-radius:12px;padding:14px'><p style='color:#f0b429;font-weight:800'>BIOMETRIA EN MANTENIMIENTO</p><p>"+(j.error||"")+"</p><p>Tu solicitud quedo guardada. El registro funciono completo: los datos llegaron a la Red.</p><p><a href='/registro'>Volver a intentar</a></p></div>";}
else{Rr.innerHTML="<p style='color:#f85149;font-weight:700'>NO SE PUDO CREAR EL ZID</p><p>"+(j.error||"Motivo desconocido")+"</p>";}}
catch(e){Rr.innerHTML="<div style='background:#2a1414;border:1px solid #f85149;border-radius:12px;padding:14px'><p style='color:#f85149;font-weight:700'>La Red no respondio</p><p>Detalle tecnico: "+e+"</p></div>";}
window.scrollTo(0,document.body.scrollHeight);
return false}
setTimeout(function(){ensureCara()},800);
</script>
</body>
</html>
'''
            self._send(200, "text/html; charset=utf-8", _reg_html.encode("utf-8"))
            return
        if path == "/version":
            try:
                d_v = self._read_portal("version.txt")
            except Exception:
                d_v = b"0"
            self._send(200, "text/plain; charset=utf-8", d_v)
            return

        if path.startswith("/icon-") and path.endswith(".png"):
            try:
                datos_i = self._read_portal(path[1:])
            except Exception:
                self._send_html(404, NOT_FOUND_PAGE)
                return
            self._send(200, "image/png", datos_i)
            return
        if path == "/health":
            apps = {
                p: {"label": v["label"], "port": v["port"]}
                for p, v in APPS.items()
            }
            payload = json.dumps(
                {
                    "ok": True,
                    "service": "zyra-superapp",
                    "apps": apps,
                }
            ).encode("utf-8")
            self._send(200, "application/json", payload)
            return
        if path == "/entrar":
            self._send_html(200, self._pagina_entrar(""))
            return
        if path == "/salir":
            self.send_response(303)
            self.send_header("Set-Cookie", "zyra_zid=; Max-Age=0; Path=/; HttpOnly")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Location", "/entrar")
            self.end_headers()
            return
        if path == "/version":
            try:
                dv = self._read_portal("version.txt")
            except Exception:
                dv = b"0"
            self._send(200, "text/plain; charset=utf-8", dv)
            return
        if path == "/verificar":
            self._send_html(
                200,
                self._read_portal("verificar.html").decode("utf-8"),
            )
            return
        if path == "/manifest.json":
            self._send(200, "application/manifest+json", self._read_portal("manifest.json"))
            return
        if path == "/sw.js":
            self._send(200, "application/javascript; charset=utf-8", self._read_portal("sw.js"))
            return
        if path == "/icon-192.png":
            self._send(200, "image/png", self._read_portal("icon-192.png"))
            return
        if path == "/icon-512.png":
            self._send(200, "image/png", self._read_portal("icon-512.png"))
            return

        if path == "/verificar.js":
            self._send(
                200,
                "application/javascript; charset=utf-8",
                self._read_portal("verificar.js"),
            )
            return
        if path == "/mpe/register":
            self._send_html(200, "<!doctype html><html lang='es'><head><meta charset='utf-8'><meta http-equiv='refresh' content='0;url=/registro'><title>ZYRA</title></head><body></body></html>")
            return
        if path.startswith("/icon-") and path.endswith(".png"):
            try:
                datos_i = self._read_portal(path[1:])
            except Exception:
                self._send_html(404, NOT_FOUND_PAGE)
                return
            self._send(200, "image/png", datos_i)
            return
        for prefix, info in APPS.items():
            if path == prefix or path.startswith(prefix + "/"):
                self._proxy(
                    "http://127.0.0.1:"
                    + str(info["port"]) + self.path
                )
                return
        self._send_html(404, NOT_FOUND_PAGE)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/entrar":
            largo = int(self.headers.get("Content-Length", 0) or 0)
            crudo = self.rfile.read(largo).decode("utf-8") if largo else ""
            from urllib.parse import unquote_plus as _uq
            zid = ""
            clave = ""
            for par in crudo.split("&"):
                if "=" in par:
                    k, v = par.split("=", 1)
                    if k == "zid":
                        zid = _uq(v).strip()
                    elif k == "clave":
                        clave = _uq(v).strip()
            owner = os.environ.get("ZYRA_OWNER_ZID", "")
            clave_req = os.environ.get("ZYRA_CLAVE_DUENO", "")
            if zid == owner and clave_req and clave == clave_req:
                self.send_response(303)
                self.send_header("Set-Cookie", "zyra_zid=" + zid + "; Path=/; Max-Age=604800; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
                return
            cred_ok = False
            try:
                import sqlite3 as _sq, hashlib as _hs
                con = _sq.connect(str(DATA_DIR / "credenciales.db"))
                fila = con.execute("SELECT sal, hash FROM credenciales WHERE zid = ?", (zid,)).fetchone()
                con.close()
                if fila:
                    cred_ok = (_hs.sha256((fila[0] + clave).encode()).hexdigest() == fila[1])
            except Exception:
                cred_ok = False
            if cred_ok:
                self.send_response(303)
                self.send_header("Set-Cookie", "zyra_zid=" + zid + "; Path=/; Max-Age=604800; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
                return
            self._send_html(403, self._pagina_entrar(
                "ZID o clave incorrectos. Si no tienes ZID, registrate en Registro."))
            return
        if path == "/registro/nuevo":
            if not ZYRA_URL:
                self._send(503, "application/json", json.dumps({"ok": False, "error": "Red no configurada"}).encode())
                return
            largo = int(self.headers.get("Content-Length", 0) or 0)
            crudo = self.rfile.read(largo).decode("utf-8") if largo else ""
            try:
                dd = json.loads(crudo or "{}")
            except Exception:
                dd = {}
            nombre = str(dd.get("nombre", "")).strip()
            clave = str(dd.get("clave", ""))
            db64 = str(dd.get("doc_image_b64", ""))
            sb64 = str(dd.get("selfie_image_b64", ""))
            if len(nombre) < 3 or len(clave) < 8 or not db64 or not sb64:
                self._send(400, "application/json", json.dumps({"ok": False, "error": "Falta nombre, clave (min 8), documento o selfie"}).encode())
                return
            _pe = {"kind": "person", "name": nombre, "display_name": nombre, "actor": os.environ.get("ZYRA_ENROLL_ACTOR", "superapp"), "doc_image_b64": db64, "selfie_image_b64": sb64}
            _tdoc = str(dd.get("doc_type", "")).strip()
            if _tdoc:
                _pe["doc_kind"] = _tdoc
                if _tdoc == "dui":
                    _pe["doc_country"] = "SV"
                elif _tdoc in ("licencia", "id_usa"):
                    _pe["doc_country"] = "US"
            _ndoc = str(dd.get("doc_number", "")).strip()
            if _ndoc:
                _pe["doc_number"] = _ndoc
            payload_e = json.dumps(_pe).encode("utf-8")
            q_e = urllib.request.Request(ZYRA_URL + "/identity/enroll", data=payload_e, method="POST")
            q_e.add_header("Content-Type", "application/json")
            q_e.add_header("Authorization", "Bearer " + os.environ.get("ZYRA_API_TOKEN", ""))
            cuerpo_e = ""
            status_e = None
            try:
                with urllib.request.urlopen(q_e, timeout=60) as re_:
                    status_e = re_.status
                    cuerpo_e = re_.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as he_:
                status_e = he_.code
                try:
                    cuerpo_e = he_.read().decode("utf-8", "replace")
                except Exception:
                    cuerpo_e = ""
            except Exception as ex_:
                self._send(502, "application/json", json.dumps({"ok": False, "error": "Sin conexion con la Red (host configurado: " + (ZYRA_URL.split("//")[-1].split("/")[0] if ZYRA_URL else "(vacio)") + "): " + str(ex_)[:180]}).encode())
                return
            try:
                je_ = json.loads(cuerpo_e or "{}")
            except Exception:
                je_ = {}
            if status_e in (200, 201) and je_.get("ok") is True:
                dx_ = je_.get("data") or je_
                if isinstance(dx_, dict):
                    zid = str(dx_.get("zid") or dx_.get("identity_id") or dx_.get("id") or "")
            elif "biometrics_unavailable" in cuerpo_e or "face engine not installed" in cuerpo_e:
                try:
                    import sqlite3 as _sq2
                    con2 = _sq2.connect(str(DATA_DIR / "credenciales.db"))
                    con2.execute("CREATE TABLE IF NOT EXISTS pendientes (nombre TEXT, doc_b64 TEXT, selfie_b64 TEXT, fecha TEXT)")
                    con2.execute("INSERT INTO pendientes VALUES (?, ?, ?, datetime('now'))", (nombre, db64, sb64))
                    con2.commit()
                    con2.close()
                except Exception:
                    pass
                self._send(200, "application/json", json.dumps({"ok": False, "codigo": "mantenimiento", "error": "Biometria en mantenimiento. Tu solicitud quedo guardada."}).encode())
                return
            else:
                emsg = ""
                if isinstance(je_.get("error"), dict):
                    emsg = str(je_["error"].get("message", ""))
                if not emsg:
                    emsg = cuerpo_e[:250] or ("HTTP " + str(status_e))
                self._send(502, "application/json", json.dumps({"ok": False, "error": emsg}).encode())
                return
            zid = locals().get("zid", "")
            if not zid and status_e in (200, 201) and isinstance(je_, dict):
                dx2 = je_.get("data") or je_
                if isinstance(dx2, dict):
                    zid = str(dx2.get("zid") or dx2.get("identity_id") or dx2.get("id") or "")
                    if not zid and isinstance(dx2.get("identity"), dict):
                        zid = str(dx2["identity"].get("zid") or "")
            if not zid:
                self._send(500, "application/json", json.dumps({"ok": False, "error": "La Red no devolvio ZID"}).encode())
                return
            import secrets as _sc, hashlib as _hs, sqlite3 as _sq
            sal = _sc.token_hex(16)
            hc = _hs.sha256((sal + clave).encode()).hexdigest()
            con = _sq.connect(str(DATA_DIR / "credenciales.db"))
            con.execute("CREATE TABLE IF NOT EXISTS credenciales (zid TEXT PRIMARY KEY, sal TEXT, hash TEXT)")
            con.execute("INSERT OR REPLACE INTO credenciales VALUES (?, ?, ?)", (zid, sal, hc))
            con.commit()
            con.close()
            self._send(200, "application/json", json.dumps({"ok": True, "zid": zid}).encode())
            return
        if path == "/verify":
            if not ZYRA_URL:
                self._send_html(
                    503,
                    ERROR_PAGE.replace(
                        "__MSG__", "ZYRA_URL no configurada"
                    ),
                )
                return
            self._proxy(ZYRA_URL + "/verify")
            return
        for prefix, info in APPS.items():
            if path == prefix or path.startswith(prefix + "/"):
                self._proxy(
                    "http://127.0.0.1:"
                    + str(info["port"]) + self.path
                )
                return
        self._send_html(404, NOT_FOUND_PAGE)

    def log_message(self, fmt, *args):
        print("[superapp] " + (fmt % args))

def main():
    print("[superapp] data dir: " + str(DATA_DIR))
    if not ZYRA_URL:
        print(
            "[superapp] WARNING: ZYRA_URL/ZYRA_HOST no configurada"
            " - apps degradadas"
        )
    errors = boot_apps()
    if errors:
        print("[superapp] STARTUP ERRORS: " + str(errors))
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), PortalHandler)
    print(
        "[superapp] LIVE on port " + str(PORT)
        + " - apps: " + str(list(APPS.keys()))
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    main()

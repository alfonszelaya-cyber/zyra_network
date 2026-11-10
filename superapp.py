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
.preview{display:none;width:100%;max-width:330px;border-radius:10px;margin:6px auto 0;border:1px solid #2a2f55}
button{width:100%;margin-top:10px;padding:13px;border:0;border-radius:10px;font-size:15px;font-weight:700;color:#fff;background:#262b52}
button.ok{background:#1f6f43}
button.big{margin-top:16px;padding:15px;font-size:16px;font-weight:800;background:linear-gradient(90deg,#7c5cff,#ff5c8a)}
button:disabled{opacity:.45}
.mini{background:none;color:#a78bfa;font-size:13px;padding:8px;width:auto;margin:4px auto;display:block;border:none;cursor:pointer}
.videozona{display:none;position:relative;border-radius:12px;overflow:hidden;margin-top:8px;margin-left:auto;margin-right:auto;background:#000;max-width:330px;border:1px solid #2a2f55;box-shadow:0 6px 24px rgba(0,0,0,0.5)}
video{width:100%;display:block}
.ov{position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none}
a{color:#a78bfa}
#desglose{margin-top:14px;font-size:13px}
#resp{margin-top:14px}
#jserr{display:none;background:#2a1414;border:1px solid #f85149;color:#f85149;border-radius:10px;padding:10px;margin-top:10px;font-size:12px;word-break:break-all}
.zid{font-size:20px;font-weight:800;color:#3fb950;letter-spacing:1px}
.chk{color:#3fb950!important;font-weight:700}
.mal{color:#f85149!important}
.titulopaso{font-size:17px;font-weight:800;color:#fff;text-align:center;margin-bottom:6px}
.bloc{background:#2a1414;border:1px solid #f85149;color:#f85149;border-radius:10px;padding:10px;margin-top:8px;font-weight:700;text-align:center}
</style>
</head>
<body>
<h1>Crear mi ZID</h1>
<p class="sub">Red de confianza digital</p>
<div class="prog" id="prog">PASO 1 DE 5</div>
<form onsubmit="return enviar(event)">
<div class="paso act" id="ps1">
<label>Nombre completo (1 o 2 nombres y 1 o 2 apellidos)</label>
<input id="nombre" autocomplete="name">
<label>Tipo de documento legal</label>
<select id="tipoDoc">
<option value="dui">DUI El Salvador (2 lados)</option>
<option value="pasaporte">Pasaporte (1 lado)</option>
<option value="licencia">Licencia de conducir (2 lados)</option>
<option value="id_usa">ID de estado / EAD USA (2 lados)</option>
<option value="permiso">Permiso legal / otro documento</option>
</select>
<button type="button" class="big" onclick="irDe1()">Continuar</button>
</div>
<div class="paso" id="ps2">
<div class="titulopaso">PASO 2: LADO FRONTAL (la cara con tu foto)</div>
<div class="videozona" id="vzF"><video id="vdF" autoplay playsinline muted></video><canvas class="ov" id="ovF"></canvas></div>
<div class="estado" id="stF">Pulsa ABRIR CAMARA. La primera vez carga el escaner (~10 seg), luego es instantaneo.</div>
<button type="button" class="big" id="bAbrirF" onclick="abrirCamF()">ABRIR CAMARA</button>
<button type="button" class="ok" id="bCapF" style="display:none" onclick="capturarF()">CAPTURAR FOTO</button>
<input type="file" id="galF" accept="image/*" style="display:none" onchange="desdeArchivo(this,'F')">
<button type="button" class="mini" onclick="R('galF').click()">o elegir archivo existente</button>
<img class="preview" id="pF" alt="" onclick="rehacer('F')">
<div id="blocF"></div>
<button type="button" class="mini" onclick="irAPaso(1)">Volver</button>
</div>
<div class="paso" id="ps3">
<div class="titulopaso">PASO 3: LADO DE ATRAS (REVERSO)</div>
<div class="videozona" id="vzA"><video id="vdA" autoplay playsinline muted></video><canvas class="ov" id="ovA"></canvas></div>
<div class="estado" id="stA">Pulsa ABRIR CAMARA. El escaner buscara las 4 esquinas del documento.</div>
<button type="button" class="big" id="bAbrirA" onclick="abrirCamA()">ABRIR CAMARA</button>
<button type="button" class="ok" id="bCapA" style="display:none" onclick="capturarA()">CAPTURAR FOTO</button>
<input type="file" id="galA" accept="image/*" style="display:none" onchange="desdeArchivo(this,'A')">
<button type="button" class="mini" onclick="R('galA').click()">o elegir archivo existente</button>
<img class="preview" id="pA" alt="" onclick="rehacer('A')">
<div id="blocA"></div>
<div class="estado" id="notaRev"></div>
<button type="button" class="ok" id="bIr4" disabled onclick="irAPaso(4)">Continuar</button>
<button type="button" class="mini" onclick="saltarReverso()">Mi documento no tiene reverso: continuar sin el</button>
<button type="button" class="mini" onclick="irAPaso(2)">Volver</button>
</div>
<div class="paso" id="ps4">
<div class="titulopaso">PASO 4: BIOMETRIA — tu rostro en vivo</div>
<div class="videozona" id="vzS"><video id="v" autoplay playsinline muted style="transform:scaleX(-1)"></video><canvas class="ov" id="ovS"></canvas></div>
<div class="estado" id="stProv">Motor de deteccion: preparando...</div>
<div class="estado" id="stV">Pulsa ABRIR CAMARA</div>
<button type="button" class="big" id="bAbrirCam" onclick="abrirCamara()">ABRIR CAMARA</button>
<button type="button" class="ok" id="bSelfie" style="display:none" onclick="capturarSelfie()">CAPTURAR SELFIE</button>
<button type="button" id="bRepSelfie" style="display:none" onclick="abrirCamara()">REPETIR SELFIE</button>
<img class="preview" id="pS" alt="">
<div id="blocS"></div>
<button type="button" class="ok" id="bIr5" style="display:none" onclick="irAPaso(5)">Continuar</button>
<button type="button" class="mini" onclick="irAPaso(3)">Volver</button>
</div>
<div class="paso" id="ps5">
<label>8) Crea tu clave de acceso (min 8)</label>
<input type="password" id="clave">
<label>Repite la clave</label>
<input type="password" id="clave2">
<button class="big" type="submit">Crear mi ZID</button>
<button type="button" class="mini" onclick="irAPaso(4)">Volver</button>
</div>
<div id="desglose"></div>
<div id="jserr"></div>
<div id="resp"></div>
</form>
<p style="text-align:center;margin-top:14px"><a href="/">Volver</a> | <a href="/entrar">Ya tengo ZID</a></p>
<p style="text-align:center;color:#4a4f7a;font-size:11px;margin-top:10px">ZYRA registro v37 - control de nombre + captura compacta</p>
<script>
window.onerror=function(m,u,l){try{var b=document.getElementById("jserr");if(b){b.style.display="block";b.innerHTML="Error interno (linea "+l+"): "+m}}catch(e){}};
var DF="",DA="",DS="";
var datosDocF=null,datosDocA=null;
var minorBloqueado=false,docVencido=false,nombreNoCoincide=false,bioRechazada=false;
var camF=null,camA=null,cam=null,cara=null,alineado=false,detTipo="",apiCara=null,mpDetector=null,capturando=false;
var promesaCara=null,faListo=false;
var ivF=null,ivA=null,quadF=null,quadA=null,ocvListo=false;
function R(id){return document.getElementById(id)}
function kb(s){return Math.round(s.length*3/4/1024)}
function dormir(ms){return new Promise(function(res){setTimeout(res,ms)})}
function partesNombre(v){return (v||"").trim().split(/\s+/).filter(function(x){return x.length>1})}
function propIdeal(){return R("tipoDoc").value=="pasaporte"?1.41:1.586}
function saveSes(){try{sessionStorage.setItem("zyraReg",JSON.stringify({DF:DF,DA:DA,DS:DS,nm:R("nombre").value,td:R("tipoDoc").value,paso:(document.querySelector(".paso.act")||{}).id}))}catch(e){}}
function loadSes(){try{var s=sessionStorage.getItem("zyraReg");if(!s)return null;return JSON.parse(s)}catch(e){return null}}
function zyComprimir(dataUrl,maxLado,calidad){return new Promise(function(res){var im=new Image();im.onload=function(){var w=im.width,h=im.height,e=Math.min(1,maxLado/Math.max(w,h)),c=document.createElement("canvas");c.width=Math.round(w*e);c.height=Math.round(h*e);c.getContext("2d").drawImage(im,0,0,c.width,c.height);res(c.toDataURL("image/jpeg",calidad).split(",").pop())};im.onerror=function(){res(dataUrl.split(",").pop())};im.src=dataUrl})}
function luma(dataUrl){return new Promise(function(res){var im=new Image();im.onload=function(){var c=document.createElement("canvas");c.width=40;c.height=40;c.getContext("2d").drawImage(im,0,0,40,40);var d=c.getContext("2d").getImageData(0,0,40,40).data,t=0;for(var i=0;i<d.length;i+=4){t+=0.299*d[i]+0.587*d[i+1]+0.114*d[i+2]}res(t/(d.length/4))};im.onerror=function(){res(99)};im.src=dataUrl})}
function cargarScript(s){return new Promise(function(res,rej){var e=document.createElement("script");e.src=s;e.onload=res;e.onerror=rej;document.head.appendChild(e)})}
function setProv(t){var e=R("stProv");if(e)e.innerHTML="Motor de deteccion: "+t}
function conTimeout(p,ms,msg){return Promise.race([p,dormir(ms).then(function(){throw new Error(msg)})])}
function cargarOpenCV(){
if(window.cv&&window.cv.Mat)return Promise.resolve();
return new Promise(function(res,rej){
if(!document.getElementById("ocvjs")){
var s=document.createElement("script");
s.id="ocvjs";s.src="https://docs.opencv.org/4.9.0/opencv.js";
s.onerror=function(){rej(new Error("no cargo opencv"))};
document.head.appendChild(s);
}
var iv=setInterval(function(){
if(window.cv&&window.cv.Mat){clearInterval(iv);res()}
},120);
setTimeout(function(){clearInterval(iv);rej(new Error("opencv timeout"))},60000);
});
}
function ensureCara(){
if(detTipo)return Promise.resolve(detTipo);
if(!promesaCara){
promesaCara=(async function(){
try{
await cargarScript("https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js");
await faceapi.nets.tinyFaceDetector.loadFromUri("https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights");
try{await faceapi.nets.faceLandmark68TinyNet.loadFromUri("https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights");await faceapi.nets.faceRecognitionNet.loadFromUri("https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights");faListo=true}catch(e2){}
detTipo="faceapi";setProv("face-api.js"+(faListo?" (con comparador)":""));
return detTipo;
}catch(e3){}
try{
var m=await import("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs");
var fs=await m.FilesetResolver.forVisionTasks("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm");
var dels=["GPU","CPU"];
for(var i=0;i<dels.length;i++){
try{
mpDetector=await m.FaceDetector.createFromOptions(fs,{baseOptions:{modelAssetPath:"https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",delegate:dels[i]},runningMode:"IMAGE",minDetectionConfidence:0.25});
detTipo="mediapipe";setProv("MediaPipe (Google, "+dels[i]+")");return detTipo;
}catch(e4){}
}
}catch(e5){}
try{if(window.FaceDetector){apiCara=new FaceDetector({fastMode:true,maxDetectedFaces:1});detTipo="nativo";setProv("nativo del navegador");return detTipo}}catch(e6){}
setProv("NO disponible");return "";
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
if(t=="faceapi"){
var r=await faceapi.detectSingleFace(v,new faceapi.TinyFaceDetectorOptions({inputSize:320,scoreThreshold:0.3}));
if(r){return {x:r.box.x,y:r.box.y,w:r.box.width,h:r.box.height}}
return null;
}
if(t=="mediapipe")return cajaMP(v);
if(t=="nativo"){var fs2=await apiCara.detect(v);if(fs2.length){var b4=fs2[0].boundingBox;return {x:b4.x,y:b4.y,w:b4.width,h:b4.height}}}
}catch(e){}
return null;
}
async function rostroEnImagen(dataUrl){
try{
var im=new Image();
var ok=await new Promise(function(res){im.onload=function(){res(true)};im.onerror=function(){res(false)};im.src="data:image/jpeg;base64,"+dataUrl});
if(!ok)return null;
var sc=Math.min(1,800/Math.max(im.width,im.height));
var c=document.createElement("canvas");
c.width=Math.round(im.width*sc);c.height=Math.round(im.height*sc);
c.getContext("2d").drawImage(im,0,0,c.width,c.height);
var t=await ensureCara();
if(t=="faceapi"){
var r=await faceapi.detectSingleFace(c,new faceapi.TinyFaceDetectorOptions({inputSize:416,scoreThreshold:0.35}));
return r?{x:r.box.x/sc,y:r.box.y/sc,w:r.box.width/sc,h:r.box.height/sc}:null;
}
if(t=="mediapipe"){
var b=cajaMP(c);
if(b)return {x:b.x/sc,y:b.y/sc,w:b.w/sc,h:b.h/sc};
}
if(t=="nativo"){var fs3=await apiCara.detect(c);if(fs3.length){var b5=fs3[0].boundingBox;return {x:b5.x/sc,y:b5.y/sc,w:b5.width/sc,h:b5.height/sc}}}
}catch(e){}
return null;
}
function edadDe(iso){try{var f=new Date(iso+"T00:00:00");if(isNaN(f))return -1;var h=new Date();var e=h.getFullYear()-f.getFullYear();var m=h.getMonth()-f.getMonth();if(m<0||(m===0&&h.getDate()<f.getDate()))e--;return e}catch(e){return -1}}
function nombresCoinciden(a,b){
try{
a=(a||"").toLowerCase().replace(/[^a-z ]/g," ").split(/\s+/).filter(function(x){return x.length>2});
b=(b||"").toLowerCase().replace(/[^a-z ]/g," ").split(/\s+/).filter(function(x){return x.length>2});
if(!a.length||!b.length)return true;
var hit=0;
for(var i=0;i<a.length;i++){if(b.indexOf(a[i])>=0)hit++}
return hit>=1;
}catch(e){return true}
}
function parseAAMVA(raw){
try{
var claves=["DAB","DAC","DAD","DCS","DBB","DBA","DAQ","DAG","DAI","DAJ","DAK","DCF","DAU"];
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
var valor=raw.slice(fnd[i][0]+3,fin).split(String.fromCharCode(10))[0].trim();
res[fnd[i][1]]=valor;
}
var nac="",venc="";
if(res.DBB&&res.DBB.length===8)nac=res.DBB.slice(4,8)+"-"+res.DBB.slice(0,2)+"-"+res.DBB.slice(2,4);
if(res.DBA&&res.DBA.length===8)venc=res.DBA.slice(4,8)+"-"+res.DBA.slice(0,2)+"-"+res.DBA.slice(2,4);
var nombre=((res.DAC||"")+" "+(res.DAD||"")+" "+(res.DCS||res.DAB||"")).trim();
return {nombre:(nombre&&nombre.length>3)?nombre:null,nacimiento:nac,edad:(nac?edadDe(nac):-1),numero:(res.DAQ||res.DCF||""),direccion:((res.DAI||"")+" "+(res.DAG||"")+" "+(res.DAJ||"")+" "+(res.DAK||"")).trim(),vencimiento:venc,confiable:true};
}catch(e){return null}
}
function fechasDeTexto(t){
var venc="",nac="";
var T=t.toUpperCase();
var lineas=T.split(String.fromCharCode(10));
for(var i=0;i<lineas.length;i++){
var LN=lineas[i];
var tieneVenc=(LN.indexOf("EXP")>=0||LN.indexOf("VENC")>=0||LN.indexOf("CADU")>=0);
var tieneNac=(LN.indexOf("NACIMIENTO")>=0||LN.indexOf("BIRTH")>=0||LN.indexOf("DOB")>=0);
if(!tieneVenc&&!tieneNac)continue;
var ventana=LN;
for(var w=1;w<=2;w++){if(lineas[i+w])ventana=ventana+" "+lineas[i+w]}
var mfechas=ventana.match(/(\d{1,2})[\/\.\-](\d{1,2})[\/\.\-](\d{4})/g);
if(!mfechas)continue;
var p=mfechas[0].split(/[\/\.\-]/);
var iso=p[2]+"-"+("0"+p[1]).slice(-2)+"-"+("0"+p[0]).slice(-2);
if(tieneVenc&&!venc)venc=iso;
if(tieneNac&&!nac)nac=iso;
}
return {vencimiento:venc,nacimiento:nac};
}

function nombreDeTexto(t){
try{
var T=t.toUpperCase();
var etiquetas=["GIVEN NAME","NOMBRES","NOMBRE /"];
var idx=-1,usada="";
for(var e2=0;e2<etiquetas.length;e2++){
var ix2=T.indexOf(etiquetas[e2]);
if(ix2>=0){idx=ix2;usada=etiquetas[e2];break}
}
if(idx<0)return null;
var misma=T.substring(idx+usada.length);
var finL=misma.indexOf(String.fromCharCode(10));
var enMisma=(finL>=0?misma.substring(0,finL):misma).replace(/[^A-Z ]/g," ").trim();
var cand=[];
var pp1=enMisma.split(/\s+/).filter(function(x){return x.length>2});
if(pp1.length>=1)cand.push(pp1.join(" "));
if(!cand.length){
var resto=(finL>=0?misma.substring(finL):"");
var ls=resto.split(String.fromCharCode(10));
for(var k=0;k<ls.length&&k<3;k++){
var cln=ls[k].replace(/[^A-Z ]/g," ").trim();
var pp=cln.split(/\s+/).filter(function(x){return x.length>2});
if(pp.length>=1){cand.push(pp.join(" "));break}
}
}
if(cand.length){var nm=cand.join(" ");return (nm.length>3)?nm:null}
return null;
}catch(e){return null}
}

async function ocrPatrones(dataUrl){
try{
if(!window.Tesseract)return null;
var ret=await conTimeout(Tesseract.recognize("data:image/jpeg;base64,"+dataUrl,"eng"),25000,"ocr lento");
var t=(ret&&ret.data&&ret.data.text)?ret.data.text:"";
if(t.length<15)return null;
var TU=t.toUpperCase();
var esReverso=(TU.indexOf("IDSLV")>=0)||(TU.indexOf("<<<<")>=0);
var esFrontalTexto=(TU.indexOf("IDENTIDAD")>=0)||(TU.indexOf("IDENTIFICATION")>=0);
var fe=fechasDeTexto(t);
var nm=nombreDeTexto(t);
return {esReverso:esReverso,esFrontalTexto:esFrontalTexto,vencimiento:fe.vencimiento,nacimiento:fe.nacimiento,nombre:nm,texto:TU.trim().substring(0,300)};
}catch(e){return null}
}
async function leerCodigoDeCanvas(cv){
try{
if(window.BarcodeDetector){
var bd=new BarcodeDetector({formats:["pdf417","qr_code","code_128","code_39"]});
var fs=await bd.detect(cv);
if(fs&&fs.length){var rv=fs[0].rawValue||"";if(rv.length>20)return parseAAMVA(rv)}
}
}catch(e){}
return null;
}
async function leerCodigo(dataUrl){
try{
var im=new Image();
var ok=await new Promise(function(res){im.onload=function(){res(true)};im.onerror=function(){res(false)};im.src="data:image/jpeg;base64,"+dataUrl});
if(!ok)return null;
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
async function clasificarLado(comp){
var rostro=await rostroEnImagen(comp);
var ocr=null;
try{ocr=await conTimeout(ocrPatrones(comp),25000,"lectura lenta")}catch(e1){}
var cod=await leerCodigo(comp);
var fuente=cod||null;
var esFrontal=null,motivo="";
if(rostro){esFrontal=true;motivo="rostro del titular visible"}
else if(cod){esFrontal=false;motivo="codigo de barras detectado"}
else if(ocr&&ocr.esReverso){esFrontal=false;motivo="zona MRZ leida"}
else if(ocr&&ocr.esFrontalTexto){esFrontal=true;motivo="encabezado del frontal"}
else{motivo="no se pudo identificar el lado: repite con buena luz y el documento llenando el recuadro"}
return {esFrontal:esFrontal,motivo:motivo,rostro:rostro,codigo:fuente,ocr:ocr};
}
function irAPaso(n){
var i;
for(i=1;i<=5;i++){var e=R("ps"+i);if(e)e.className="paso"+(i==n?" act":"")}
R("prog").innerHTML="PASO "+n+" DE 5";
stopCamF();stopCamA();stopCam();
if(n==2){R("stF").innerHTML=DF?("LADO FRONTAL guardado ("+kb(DF)+" KB) — toca la foto para rehacer"):"Pulsa ABRIR CAMARA: el recuadro verde buscara las esquinas del documento.";}
if(n==3){
var t=R("tipoDoc").value;
R("stA").innerHTML=DA?("LADO REVERSO guardado ("+kb(DA)+" KB) — toca la foto para rehacer"):"Pulsa ABRIR CAMARA: el recuadro verde buscara las esquinas.";
if(t=="pasaporte"){R("notaRev").innerHTML="Pasaporte: no tiene reverso. Continua.";R("notaRev").className="estado chk";R("bIr4").disabled=false}
else if(t=="permiso"){R("notaRev").innerHTML="Si tu permiso tiene reverso, tomale foto. Si no, usa el boton de abajo.";R("notaRev").className="estado";R("bIr4").disabled=!DA}
else{R("notaRev").innerHTML="Este documento SI requiere reverso.";R("notaRev").className="estado";R("bIr4").disabled=!DA}
}
saveSes();
window.scrollTo(0,0);
}
function saltarReverso(){
DA="";datosDocA=null;R("stA").innerHTML="";R("pA").style.display="none";
irAPaso(4);
}
function irDe1(){
var nm=R("nombre").value.trim();
var ps=partesNombre(nm);
if(nm.length<3||ps.length<2){R("resp").innerHTML="<p style='color:#f85149'>Escribe tu nombre y apellido (1 o 2 de cada uno).</p>";window.scrollTo(0,document.body.scrollHeight);return}
R("resp").innerHTML="";
irAPaso(2);
}
function mostrarDesglose(){
var d=R("desglose");if(!d)return;
var h="";var nom=R("nombre").value.trim();
minorBloqueado=false;docVencido=false;nombreNoCoincide=false;
var fuenteF=datosDocF,fuenteA=datosDocA;
if(!fuenteF&&!fuenteA){
h="<p style='color:#9aa0c3'>Sin datos automaticos legibles. El motor verificara tu rostro contra el documento.</p>";
d.innerHTML=h;return;
}
if(fuenteF){
if(fuenteF.confiable&&fuenteF.nombre){
h+="<p style='color:#3fb950'>FRONTAL (leido): "+fuenteF.nombre+" | Nac: "+(fuenteF.nacimiento||"?")+" | Edad: "+fuenteF.edad+"</p>";
if(nom.length>=3&&!nombresCoinciden(fuenteF.nombre,nom)){nombreNoCoincide=true;h+="<p style='color:#f85149;font-weight:700'>NO COINCIDE: el nombre escrito difiere del documento. Corrigelo.</p>";}
else{h+="<p style='color:#3fb950'>Cruce de nombre: coincide</p>";}
}
}
var venc="";
if(fuenteA&&fuenteA.vencimiento)venc=fuenteA.vencimiento;
if(!venc&&fuenteF&&fuenteF.vencimiento)venc=fuenteF.vencimiento;
if(venc){
var hoy=new Date();hoy.setHours(0,0,0,0);
var fvd=new Date(venc+"T00:00:00");
if(fvd&&fvd<hoy){docVencido=true;h+="<p style='color:#f85149;font-weight:700'>DOCUMENTO VENCIDO ("+venc+"): NO SE ACEPTA.</p>";}
else{h+="<p style='color:#3fb950'>Vencimiento: "+venc+" — valido</p>";}
}
if(fuenteF&&fuenteF.nacimiento){
var ed2=edadDe(fuenteF.nacimiento);
if(ed2>=0&&ed2<18){minorBloqueado=true;h+="<p style='color:#f85149;font-weight:700'>MENOR DE EDAD ("+ed2+"): se registra con tutor.</p>";}
}
if(fuenteA){
var pa=[];
if(fuenteA.numero)pa.push("No.: "+fuenteA.numero);
if(fuenteA.direccion)pa.push("Dir: "+fuenteA.direccion);
if(pa.length)h+="<p style='color:#3fb950'>REVERSO: "+pa.join(" | ")+"</p>";
}
if(fuenteF&&fuenteF.texto){h+="<p style='color:#7c8cf8'>OCR: "+fuenteF.texto.split("<").join("&lt;")+"</p>";}
d.innerHTML=h;
}
function bloquear(lado,mensaje){
var b=R("bloc"+lado);
if(b){b.className="bloc";b.innerHTML=mensaje}
}
function limpiarBloc(lado){
var b=R("bloc"+lado);
if(b){b.innerHTML=""}
}
function aplicarFiltros(lado){
if(lado=="F"){limpiarBloc("F");limpiarBloc("A")}
var f=datosDocF;
if(f){
if(f.confiable&&f.nombre){
var nom=R("nombre").value.trim();
if(nom.length>=3&&!nombresCoinciden(f.nombre,nom)){
nombreNoCoincide=true;
bloquear("F","BLOQUEADO: el nombre escrito no coincide con el documento. Corrigelo y vuelve a guardar.");
return false;
}
}
var venc=(datosDocA&&datosDocA.vencimiento)||(f.vencimiento)||"";
if(venc){
var hoy=new Date();hoy.setHours(0,0,0,0);
var fvd=new Date(venc+"T00:00:00");
if(fvd&&fvd<hoy){
docVencido=true;
bloquear(lado,"BLOQUEADO: DOCUMENTO VENCIDO ("+venc+"). NO puedes continuar.");
return false;
}
}
if(f.nacimiento){
var ed2=edadDe(f.nacimiento);
if(ed2>=0&&ed2<18){
minorBloqueado=true;
bloquear(lado,"BLOQUEADO: MENOR DE EDAD ("+ed2+"). Los menores se registran con tutor.");
return false;
}
}
}
return true;
}
function cargarOpenCV(){
if(window.cv&&window.cv.Mat)return Promise.resolve();
return new Promise(function(res,rej){
if(!document.getElementById("ocvjs")){
var s=document.createElement("script");
s.id="ocvjs";s.src="https://docs.opencv.org/4.9.0/opencv.js";
s.onerror=function(){rej(new Error("no cargo opencv"))};
document.head.appendChild(s);
}
var iv=setInterval(function(){
if(window.cv&&window.cv.Mat){clearInterval(iv);res()}
},120);
setTimeout(function(){clearInterval(iv);rej(new Error("opencv timeout"))},60000);
});
}
function ordenarPts(pts){
pts.sort(function(a,b){return a.y-b.y});
var t=pts.slice(0,2),b2=pts.slice(2);
t.sort(function(a,b){return a.x-b.x});
b2.sort(function(a,b){return a.x-b.x});
return {tl:t[0],tr:t[1],br:b2[1],bl:b2[0]};
}
function detectarQuadPro(vid){
if(!window.cv||!window.cv.Mat)return null;
var v=R(vid);
if(!v.videoWidth)return null;
var SW=320;
var sc=Math.min(1,SW/v.videoWidth);
var cw=Math.round(v.videoWidth*sc),ch=Math.round(v.videoHeight*sc);
var c=document.createElement("canvas");c.width=cw;c.height=ch;
c.getContext("2d").drawImage(v,0,0,cw,ch);
var src=cv.imread(c);
var gray=new cv.Mat(),blur=new cv.Mat(),edg=new cv.Mat();
cv.cvtColor(src,gray,cv.COLOR_RGBA2GRAY);
cv.GaussianBlur(gray,blur,new cv.Size(5,5),0);
cv.Canny(blur,edg,50,150);
try{cv.dilate(edg,edg,new cv.Mat(),new cv.Point(-1,-1),2)}catch(e){}
var cont=new cv.MatVector(),hier=new cv.Mat();
cv.findContours(edg,cont,hier,cv.RETR_LIST,cv.CHAIN_APPROX_SIMPLE);
var best=null,bestA=0;
for(var i=0;i<cont.size();i++){
var cnt=cont.get(i);
var area=Math.abs(cv.contourArea(cnt));
if(area<cw*ch*0.08||area>cw*ch*0.97){cnt.delete();continue}
var per=cv.arcLength(cnt,true);
var ap=new cv.Mat();
cv.approxPolyDP(cnt,ap,0.02*per,true);
if(ap.rows===4&&cv.isContourConvex(ap)){
if(area>bestA){
var pts=[];
for(var p=0;p<4;p++)pts.push({x:ap.data32S[p*2],y:ap.data32S[p*2+1]});
best=ordenarPts(pts);
bestA=area;
}
}
ap.delete();cnt.delete();
}
cont.delete();hier.delete();edg.delete();blur.delete();gray.delete();src.delete();
if(!best)return null;
var inv=1/sc;
return {tl:{x:best.tl.x*inv,y:best.tl.y*inv},tr:{x:best.tr.x*inv,y:best.tr.y*inv},br:{x:best.br.x*inv,y:best.br.y*inv},bl:{x:best.bl.x*inv,y:best.bl.y*inv}};
}
function warpPro(vid,q){
var v=R(vid);
var cw=v.videoWidth,ch=v.videoHeight;
var c=document.createElement("canvas");c.width=cw;c.height=ch;
c.getContext("2d").drawImage(v,0,0);
var src=cv.imread(c);
var d1=Math.hypot(q.tr.x-q.tl.x,q.tr.y-q.tl.y),d2=Math.hypot(q.br.x-q.bl.x,q.br.y-q.bl.y);
var dw=Math.max(d1,d2);
var d3=Math.hypot(q.bl.x-q.tl.x,q.bl.y-q.tl.y),d4=Math.hypot(q.br.x-q.tr.x,q.br.y-q.tr.y);
var dh=Math.max(d3,d4);
var srcTri=cv.matFromArray(4,1,cv.CV_32FC2,[q.tl.x,q.tl.y,q.tr.x,q.tr.y,q.br.x,q.br.y,q.bl.x,q.bl.y]);
var dstTri=cv.matFromArray(4,1,cv.CV_32FC2,[0,0,dw,0,dw,dh,0,dh]);
var M=cv.getPerspectiveTransform(srcTri,dstTri);
var dst=new cv.Mat();
cv.warpPerspective(src,dst,M,new cv.Size(Math.round(dw),Math.round(dh)));
var out=document.createElement("canvas");
cv.imshow(out,dst);
src.delete();dst.delete();M.delete();srcTri.delete();dstTri.delete();
return out.toDataURL("image/jpeg",0.9).split(",").pop();
}
async function abrirCamF(){
stopCamA();
R("stF").innerHTML="Cargando escaner profesional (solo la primera vez)...";
try{await cargarOpenCV();ocvListo=true}catch(e){R("stF").innerHTML="El escaner profesional no cargo: usa 'elegir archivo existente'.";R("stF").className="estado mal";return}
await abrirCamGen("vdF","vzF","bAbrirF","bCapF","stF",function(c){camF=c;ivF=setInterval(function(){loopSeguir("vdF","ovF",function(q){quadF=q})},450)});
}
async function abrirCamA(){
stopCamF();
R("stA").innerHTML="Cargando escaner profesional (solo la primera vez)...";
try{await cargarOpenCV();ocvListo=true}catch(e){R("stA").innerHTML="El escaner profesional no cargo: usa 'elegir archivo existente'.";R("stA").className="estado mal";return}
await abrirCamGen("vdA","vzA","bAbrirA","bCapA","stA",function(c){camA=c;ivA=setInterval(function(){loopSeguir("vdA","ovA",function(q){quadA=q})},450)});
}
async function abrirCamGen(vid,zn,bAbrir,bCap,st,cb){
try{
R(zn).style.display="block";
R(bAbrir).style.display="none";
R(bCap).style.display="none";
var c=await navigator.mediaDevices.getUserMedia({video:{facingMode:"environment",width:{ideal:1280},height:{ideal:720}}});
var v=R(vid);v.srcObject=c;
R(bCap).style.display="block";
R(st).innerHTML="El recuadro verde buscara las 4 esquinas del documento. Acerca el documento hasta llenarlo.";
cb(c);
}catch(e){
R(st).innerHTML="No se pudo abrir la camara: "+e;R(st).className="estado mal";
R(bAbrir).style.display="block";
}
}
function stopCamGen(c,iv,zn,bCap,bAbrir){
if(iv){clearInterval(iv)}
if(c){try{c.getTracks().forEach(function(t){t.stop()})}catch(e){}}
R(zn).style.display="none";
R(bCap).style.display="none";
R(bAbrir).style.display="block";
}
function stopCamF(){stopCamGen(camF,ivF,"vzF","bCapF","bAbrirF");camF=null;ivF=null;quadF=null}
function stopCamA(){stopCamGen(camA,ivA,"vzA","bCapA","bAbrirA");camA=null;ivA=null;quadA=null}
function stopCam(){
if(cam){try{cam.getTracks().forEach(function(t){t.stop()})}catch(e){}}
cam=null;R("vzS").style.display="none";R("bSelfie").style.display="none";
}
function loopSeguir(vid,ovId,cb){
var q=detectarQuadPro(vid);
cb(q);
var v=R(vid),ov=R(ovId);
if(!v.videoWidth)return;
var vw=v.videoWidth,vh=v.videoHeight;
if(ov.width!=vw){ov.width=vw;ov.height=vh}
var g=ov.getContext("2d");
g.clearRect(0,0,vw,vh);
if(q){
g.strokeStyle="#3fb950";g.lineWidth=5;
g.beginPath();
g.moveTo(q.tl.x,q.tl.y);g.lineTo(q.tr.x,q.tr.y);g.lineTo(q.br.x,q.br.y);g.lineTo(q.bl.x,q.bl.y);g.closePath();
g.stroke();
var pts=[q.tl,q.tr,q.br,q.bl];
for(var i=0;i<4;i++){
g.fillStyle="#3fb950";
g.beginPath();g.arc(pts[i].x,pts[i].y,11,0,6.3);g.fill();
}
if(vid=="vdF"){R("stF").innerHTML="DOCUMENTO ENMARCADO: pulsa CAPTURAR";R("stF").className="estado chk"}
else{R("stA").innerHTML="DOCUMENTO ENMARCADO: pulsa CAPTURAR";R("stA").className="estado chk"}
}else{
if(vid=="vdF"){R("stF").innerHTML="Buscando las esquinas del documento...";R("stF").className="estado"}
else{R("stA").innerHTML="Buscando las esquinas del documento...";R("stA").className="estado"}
}
}
async function capturarF(){await capturarDocGen("vdF","F",function(){return quadF},function(){stopCamF()})}
async function capturarA(){await capturarDocGen("vdA","A",function(){return quadA},function(){stopCamA()})}
async function capturarDocGen(vid,lado,getQ,stopFn){
var v=R(vid);
if(!v.videoWidth){return}
var st=R("st"+lado);
var q=getQ();
if(!q){
st.innerHTML="El escaner no vio el documento: acercalo hasta que el recuadro lo enmarque y captura.";
st.className="estado mal";
return;
}
st.innerHTML="Recortando con correccion de perspectiva y leyendo...";
st.className="estado";st.style.color="#f0b429";
var comp=null;
try{
if(window.cv&&window.cv.Mat){
comp=warpPro(vid,q);
comp=(await zyComprimir("data:image/jpeg;base64,"+comp,1200,0.78));
}else{
var c=document.createElement("canvas");
var wq=Math.round(Math.max(q.tr.x-q.tl.x,q.br.x-q.bl.x));
var hq=Math.round(Math.max(q.bl.y-q.tl.y,q.br.y-q.tr.y));
c.width=wq;c.height=hq;
c.getContext("2d").drawImage(v,q.tl.x,q.tl.y,wq,hq,0,0,wq,hq);
var crudo=c.toDataURL("image/jpeg",0.9);
stopFn();
comp=await zyComprimir("data:image/jpeg;base64,"+crudo,1200,0.78);
}
}catch(e){
st.innerHTML="Error recortando: "+e;st.className="estado mal";
return;
}
stopFn();
var st2=R("st"+lado);
st2.innerHTML="Verificando el lado y leyendo (OCR puede tardar unos segundos)...";
var cl=await clasificarLado(comp);
var quieroFrontal=(lado=="F");
if(cl.esFrontal===null){
st2.innerHTML=cl.motivo;st2.className="estado mal";
return;
}
if(quieroFrontal&&!cl.esFrontal){
st2.innerHTML="ESTA FOTO ES EL REVERSO. Este paso es para el FRONTAL. Tomala de nuevo.";st2.className="estado mal";
bloquear(lado,"BLOQUEADO: tomaste el reverso en el paso del frontal.");
return;
}
if(!quieroFrontal&&cl.esFrontal){
st2.innerHTML="ESTA FOTO ES EL FRONTAL. Este paso es para el REVERSO. Tomala de nuevo.";st2.className="estado mal";
bloquear(lado,"BLOQUEADO: tomaste el frontal en el paso del reverso.");
return;
}
var fuente=cl.codigo||null;
if(!fuente&&cl.ocr){
fuente={nombre:cl.ocr.nombre||null,nacimiento:cl.ocr.nacimiento||"",edad:(cl.ocr.nacimiento?edadDe(cl.ocr.nacimiento):-1),numero:"",direccion:"",vencimiento:cl.ocr.vencimiento||"",confiable:!!(cl.ocr.nombre||cl.ocr.vencimiento),texto:cl.ocr.texto};
}
if(lado=="F"){datosDocF=fuente;DF=comp}else{datosDocA=fuente;DA=comp}
var pv=R(lado=="F"?"pF":"pA");
pv.src="data:image/jpeg;base64,"+comp;pv.style.display="block";
mostrarDesglose();
saveSes();
var ok=aplicarFiltros(lado);
if(!ok){
st2.innerHTML="FILTRO DE BLOQUEO ACTIVO — mira el mensaje en rojo.";
st2.className="estado mal";
return;
}
limpiarBloc(lado);
st2.innerHTML="LADO "+(lado=="F"?"FRONTAL":"REVERSO")+" guardado y VERIFICADO ("+kb(comp)+" KB)";
st2.className="estado chk";
if(lado=="F"){irAPaso(3)}else{R("bIr4").disabled=false;irAPaso(4)}
}
async function desdeArchivo(inp,lado){
var f=inp.files&&inp.files[0];if(!f)return;
var st=R("st"+lado);
st.innerHTML="PROCESANDO...";
st.className="estado";st.style.color="#f0b429";
try{
var fr2=new FileReader();
var pfr=new Promise(function(res,rej){fr2.onload=function(){res(fr2.result)};fr2.onerror=function(){rej(new Error("lectura"))}});
fr2.readAsDataURL(f);
var crudo=await conTimeout(pfr,15000,"lectura lenta");
var comp=await conTimeout(zyComprimir(crudo,1200,0.75),15000,"compresion lenta");
var cl=await clasificarLado(comp);
var quieroFrontal=(lado=="F");
if(cl.esFrontal===null){
st.innerHTML=cl.motivo;st.className="estado mal";return;
}
if(quieroFrontal&&!cl.esFrontal){
st.innerHTML="ESTA FOTO ES EL REVERSO. Este paso es para el FRONTAL.";st.className="estado mal";
bloquear(lado,"BLOQUEADO: tomaste el reverso en el paso del frontal.");
return;
}
if(!quieroFrontal&&cl.esFrontal){
st.innerHTML="ESTA FOTO ES EL FRONTAL. Este paso es para el REVERSO.";st.className="estado mal";
bloquear(lado,"BLOQUEADO: tomaste el frontal en el paso del reverso.");
return;
}
var fuente=cl.codigo||null;
if(!fuente&&cl.ocr){
fuente={nombre:cl.ocr.nombre||null,nacimiento:cl.ocr.nacimiento||"",edad:(cl.ocr.nacimiento?edadDe(cl.ocr.nacimiento):-1),numero:"",direccion:"",vencimiento:cl.ocr.vencimiento||"",confiable:!!(cl.ocr.nombre||cl.ocr.vencimiento),texto:cl.ocr.texto};
}
if(lado=="F"){datosDocF=fuente;DF=comp}else{datosDocA=fuente;DA=comp}
var pv=R(lado=="F"?"pF":"pA");
pv.src="data:image/jpeg;base64,"+comp;pv.style.display="block";
mostrarDesglose();
saveSes();
var ok=aplicarFiltros(lado);
if(!ok){
st.innerHTML="FILTRO DE BLOQUEO ACTIVO — mira el mensaje en rojo.";
st.className="estado mal";
inp.value="";
return;
}
limpiarBloc(lado);
st.innerHTML="LADO "+(lado=="F"?"FRONTAL":"REVERSO")+" guardado y VERIFICADO ("+kb(comp)+" KB)";
st.className="estado chk";
inp.value="";
if(lado=="F"){irAPaso(3)}else{R("bIr4").disabled=false;irAPaso(4)}
}catch(e){
st.innerHTML="Error: "+e;st.className="estado mal";
}
}
function rehacer(lado){
if(lado=="F"){DF="";datosDocF=null;R("pF").style.display="none";limpiarBloc("F");irAPaso(2)}
else{DA="";datosDocA=null;R("pA").style.display="none";R("bIr4").disabled=true;limpiarBloc("A");irAPaso(3)}
}
async function abrirCamara(){
var st=R("stV");
try{
R("vzS").style.display="block";
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
async function loop(){
var v=R("v"),ov=R("ovS");
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
if(!capturando){
if(alineado){R("stV").innerHTML="Encuadre perfecto: pulsa CAPTURAR";R("stV").style.color="#3fb950"}
else{R("stV").innerHTML="Centra tu rostro dentro de la guia";R("stV").style.color="#f0b429"}
}
}else{
g.strokeStyle="#f85149";g.lineWidth=3;
g.beginPath();g.ellipse(o.cx,o.cy,o.rx,o.ry,0,0,6.3);g.stroke();
if(!capturando){R("stV").innerHTML="No veo tu rostro. Busca buena luz.";R("stV").style.color="#9aa0c3"}
}
}catch(e){}
},250);
}
async function capturarSelfie(){
if(capturando)return false;
var st=R("stV"),v=R("v");
var bl=R("blocS");
if(bl)bl.innerHTML="";
if(!cam||!v.videoWidth){st.innerHTML="Abre la camara primero.";st.className="estado mal";return false}
capturando=true;R("bSelfie").disabled=true;
st.innerHTML="Verificando luz, rostro y encuadre...";st.style.color="#f0b429";
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
st.innerHTML="NO VEO TU ROSTRO con claridad. NO se guardo.";
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
var comp=await zyComprimir(crudo,640,0.6);
DS=comp;
stopCam();
R("bAbrirCam").style.display="none";
R("bRepSelfie").style.display="block";
R("pS").src="data:image/jpeg;base64,"+comp;R("pS").style.display="block";
st.innerHTML="SELFIE GUARDADA: "+kb(comp)+" KB (luz "+Math.round(L)+"/100)";st.className="estado chk";
capturando=false;R("bSelfie").disabled=false;
var stB=R("blocS");
bioRechazada=false;
if(faListo&&DF){
if(stB)stB.innerHTML="<p style='color:#f0b429;text-align:center'>COMPARANDO tu rostro con el del documento...</p>";
try{
var im1=new Image(),im2=new Image();
var p1=new Promise(function(res){im1.onload=res;im1.onerror=res;im1.src="data:image/jpeg;base64,"+DF});
var p2=new Promise(function(res){im2.onload=res;im2.onerror=res;im2.src="data:image/jpeg;base64,"+DS});
await Promise.all([p1,p2]);
var r1=await faceapi.detectSingleFace(im1,new faceapi.TinyFaceDetectorOptions({inputSize:416})).withFaceDescriptor();
var r2b=await faceapi.detectSingleFace(im2,new faceapi.TinyFaceDetectorOptions({inputSize:416})).withFaceDescriptor();
if(r1&&r2b){
var dist=faceapi.euclideanDistance(r1.descriptor,r2b.descriptor);
if(dist>0.66){
bioRechazada=true;
if(stB)stB.innerHTML="<p class='bloc'>BLOQUEADO: tu rostro NO coincide con el del documento (distancia "+dist.toFixed(2)+" — maximo 0.66). NO puedes pasar a la clave. Usa tu propio documento.</p>";
R("bIr5").style.display="none";
capturando=false;R("bSelfie").disabled=false;
saveSes();
return false;
}else{
if(stB)stB.innerHTML="<p style='color:#3fb950;text-align:center;font-weight:700'>Biometria local APROBADA (dist "+dist.toFixed(2)+").</p>";
}
}else{
if(stB)stB.innerHTML="<p style='color:#9aa0c3;text-align:center'>Pre-chequeo no disponible: el motor de la Red hara la comparacion al crear el ZID.</p>";
}
}catch(e){if(stB)stB.innerHTML=""}
}
R("bIr5").style.display="block";
saveSes();
setTimeout(function(){irAPaso(5)},900);
return true;
}
async function enviar(ev){ev.preventDefault();var Rr=R("resp");
var c1=R("clave").value,c2=R("clave2").value;
var tipo=R("tipoDoc").value;
var nmv=R("nombre").value.trim();
var reqRev=(tipo=="dui"||tipo=="licencia"||tipo=="id_usa");
if(nmv.length<3||partesNombre(nmv).length<2){Rr.innerHTML="<p style='color:#f85149'>Escribe tu nombre y apellido.</p>";window.scrollTo(0,document.body.scrollHeight);return false}
if(docVencido){Rr.innerHTML="<p style='color:#f85149;font-weight:700'>DOCUMENTO VENCIDO: NO se crea el ZID.</p>";return false}
if(minorBloqueado){Rr.innerHTML="<p style='color:#f85149;font-weight:700'>MENOR DE EDAD: los menores se registran con tutor.</p>";return false}
if(nombreNoCoincide){Rr.innerHTML="<p style='color:#f85149;font-weight:700'>El nombre no coincide con el documento. Corrigelo.</p>";return false}
if(bioRechazada){Rr.innerHTML="<p style='color:#f85149;font-weight:700'>Biometria rechazada en el paso 4: tu rostro no coincide con el documento.</p>";return false}
if(c1!==c2){Rr.innerHTML="<p style='color:#f85149'>Las claves no coinciden.</p>";return false}
if(c1.length<8){Rr.innerHTML="<p style='color:#f85149'>La clave necesita minimo 8 caracteres.</p>";return false}
if(!DF){Rr.innerHTML="<p style='color:#f85149'>Falta el documento frontal (paso 2).</p>";return false}
if(reqRev&&!DA){Rr.innerHTML="<p style='color:#f85149'>Este documento requiere el reverso (paso 3).</p>";return false}
if(!DS){Rr.innerHTML="<p style='color:#f85149'>Falta la selfie (paso 4).</p>";return false}
Rr.innerHTML="<p style='color:#8b949e'>Enviando a la Red ("+kb(DF)+" y "+kb(DS)+" KB). El motor comparara tu rostro con el documento...</p>";
window.scrollTo(0,document.body.scrollHeight);
try{var r=await fetch("/registro/nuevo",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({nombre:nmv,clave:c1,doc_image_b64:DF,doc_back_b64:DA,selfie_image_b64:DS,doc_type:tipo,doc_number:((datosDocA&&datosDocA.numero)||(datosDocF&&datosDocF.numero)||"")})});
var txt=await r.text();
var j=null;
try{j=JSON.parse(txt)}catch(e2){}
if(j&&j.ok&&j.zid){Rr.innerHTML="<div style='background:#0f2a1a;border:1px solid #238636;border-radius:12px;padding:14px'><p style='color:#3fb950;font-weight:800;font-size:17px'>REGISTRO EXITOSO</p><p>Tu ZID unico fue creado:</p><p class='zid'>"+j.zid+"</p><p>Guarda tu ZID y tu clave. Nadie mas puede crearlo.</p><p><a href='/entrar'>ENTRAR AHORA</a></p></div>";}
else if(j&&j.codigo==="mantenimiento"){Rr.innerHTML="<div style='background:#2a2410;border:1px solid #f0b429;border-radius:12px;padding:14px'><p style='color:#f0b429;font-weight:800'>BIOMETRIA EN MANTENIMIENTO</p><p>"+(j.error||"")+"</p><p><a href='/registro'>Volver a intentar</a></p></div>";}
else if(j&&j.error){
var em="HTTP "+r.status;
if(j.error.message)em+=" | "+j.error.message;
if(j.error.reason)em+=" | razon: "+j.error.reason;
if(j.error.doc_match_score!==undefined&&j.error.doc_match_score!==null)em+=" | puntaje: "+String(j.error.doc_match_score).substring(0,6)+" (auto>=0.40)";
if(j.error.case_status)em+=" | estado: "+j.error.case_status;
Rr.innerHTML="<p style='color:#f85149;font-weight:700'>NO SE PUDO CREAR EL ZID</p><p>"+em+"</p>";}
else{
var em2="HTTP "+r.status+" | respuesta: "+txt.substring(0,300);
if(r.status===502){em2+=" — la Red se esta reiniciando (Render): espera 2 minutos y vuelve a intentar."}
Rr.innerHTML="<p style='color:#f85149;font-weight:700'>NO SE PUDO CREAR EL ZID</p><p>"+em2+"</p>";}}
catch(e){Rr.innerHTML="<div style='background:#2a1414;border:1px solid #f85149;border-radius:12px;padding:14px'><p style='color:#f85149;font-weight:700'>La Red no respondio</p><p>Detalle: "+e+"</p></div>";}
window.scrollTo(0,document.body.scrollHeight);
return false}
(function(){var s=loadSes();if(s&&(s.DF||s.DA||s.DS)){
DF=s.DF||"";DA=s.DA||"";DS=s.DS||"";
if(s.nm)R("nombre").value=s.nm;
if(s.td)R("tipoDoc").value=s.td;
var dest=2;
if(DS){dest=5}else if(DA){dest=4}else if(DF){dest=3}
irAPaso(dest);
if(DF){var pF2=R("pF");pF2.src="data:image/jpeg;base64,"+DF;pF2.style.display="block"}
if(DA){var pA2=R("pA");pA2.src="data:image/jpeg;base64,"+DA;pA2.style.display="block"}
if(DS){var pS2=R("pS");pS2.src="data:image/jpeg;base64,"+DS;pS2.style.display="block";R("bIr5").style.display="block"}
if(DA&&R("tipoDoc").value!="pasaporte"){R("bIr4").disabled=false}
mostrarDesglose();
var rst=R("resp");if(rst)rst.innerHTML="<p style='color:#7c8cf8'>Sesion restaurada: tus fotos siguen aqui.</p>";
}})();
setTimeout(function(){ensureCara()},800);
</script>
<script>

(function(){
  if (window.__zyraPuertaV37) { return; }
  window.__zyraPuertaV37 = true;
  function R(id){ return document.getElementById(id); }
  function toast(msg, mal){
    var t = document.getElementById("toastv37");
    if (!t) {
      t = document.createElement("div");
      t.id = "toastv37";
      t.style.cssText = "position:fixed;left:12px;right:12px;bottom:18px;z-index:99999;padding:12px 14px;border-radius:12px;font-size:14px;font-weight:700;color:#fff;box-shadow:0 6px 24px rgba(0,0,0,0.5);display:none";
      document.body.appendChild(t);
    }
    t.style.background = mal ? "#b62324" : "#1f6f3f";
    t.textContent = msg;
    t.style.display = "block";
    if (t.__h) { clearTimeout(t.__h); }
    t.__h = setTimeout(function(){ t.style.display = "none"; }, 7000);
  }
  function normTokens(s){
    var v = (s || "").toUpperCase();
    var de = "ÁÀÄÂÃÉÈËÊÍÌÏÎÓÒÖÔÕÚÙÜÛÑÇ";
    var aa = "AAAAAEEEEIIIIOOOOOUUUUNC";
    var i = 0;
    for (i = 0; i < de.length; i++) { v = v.split(de.charAt(i)).join(aa.charAt(i)); }
    v = v.replace(/[^A-Z ]/g, " ");
    var parts = v.split(" ");
    var out = [];
    var j = 0;
    for (j = 0; j < parts.length; j++) { if (parts[j].length > 1) { out.push(parts[j]); } }
    return out;
  }
  function coincide(nombreDoc, nombreReg){
    var d = normTokens(nombreDoc);
    var r = normTokens(nombreReg);
    if (d.length === 0 || r.length === 0) { return false; }
    if (r.length === 1) { return (d.length === 1 && d[0] === r[0]); }
    var k = 0;
    for (k = 0; k < r.length; k++) { if (d.indexOf(r[k]) === -1) { return false; } }
    return true;
  }
  function sesion(){
    try { return JSON.parse(sessionStorage.getItem("zyraReg") || "null"); } catch (e) { return null; }
  }
  function nombreRegistro(){
    var el = R("nombre");
    if (el && el.value) { return el.value; }
    var s = sesion();
    return (s && s.nm) ? s.nm : "";
  }
  function imagenFrente(){
    var s = sesion();
    return (s && s.DF) ? s.DF : "";
  }
  async function verificarNombre(){
    var reg = nombreRegistro();
    if (normTokens(reg).length < 2) {
      toast("Escribe tu nombre completo (1 o 2 nombres y 1 o 2 apellidos) en el PASO 1.", true);
      return false;
    }
    if (window.nombreNoCoincide === true) {
      toast("EL NOMBRE NO COINCIDE con el documento. No puedes pasar a la biometría.", true);
      return false;
    }
    var df = imagenFrente();
    if (!df) {
      toast("No encuentro la foto del documento. Vuelve al PASO 2 y toma la foto del frente.", true);
      return false;
    }
    toast("Verificando que tu nombre coincida con el documento...", false);
    var texto = "";
    try {
      if (typeof Tesseract === "undefined") {
        if (typeof cargarScript === "function") {
          await cargarScript("https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js");
        }
      }
      var imgArg = (df.indexOf("data:") === 0) ? df : ("data:image/jpeg;base64," + df);
      var r = await Tesseract.recognize(imgArg, "eng");
      texto = (r && r.data && r.data.text) ? r.data.text : "";
    } catch (e) { texto = ""; }
    if (!texto) {
      toast("No pudimos leer el documento. Toma la foto de nuevo: buena luz, sin reflejos, documento llenando la guía.", true);
      return false;
    }
    var nombreDoc = (typeof nombreDeTexto === "function") ? nombreDeTexto(texto) : null;
    if (!nombreDoc) {
      toast("No pudimos leer el NOMBRE del documento. Vuelve al PASO 2 y reescanea con buena luz.", true);
      return false;
    }
    if (!coincide(nombreDoc, reg)) {
      toast("EL NOMBRE NO COINCIDE: el documento dice '" + nombreDoc + "'. No puedes pasar a la biometría.", true);
      return false;
    }
    return true;
  }
  var original = window.irAPaso;
  if (typeof original !== "function") { return; }
  window.irAPaso = function(n){
    if (n === 4) {
      verificarNombre().then(function(ok){
        if (ok) { toast("Nombre verificado: coincide con el documento.", false); original(4); }
      });
      return;
    }
    return original(n);
  };
})();

/*ZYRA-V6-BEGIN*/eval(atob('LypaWVJBLVJFVkYgdjE0IC0gbnVjbGVvIGRlIHJlZ2lzdHJvIHJldkYgKHRvZG8gbG8gZGUgdjEzOiA0IGVzcXVpbmFzLCBtb3RvciBmYWNpYWwgRU4gVklWTywgT0NSIG11bHRpLXBhc2UgY29uIGxlY3R1cmEgY29uZmlybWFibGUsIGVudmlvIGZhaWwtY2xvc2VkIHF1ZSBjcmVhIGVsIFpJRCwgYW50aS1ibG9xdWVvIGxlZ2FkbyBjb24gYm90b24gImkiIGRlIGRpYWdub3N0aWNvOyBOVUVWTyBlbiB2MTQ6IDEpIEZPVE8gMTYwMHB4IGNvbiBtZWpvciBKUEVHIHBhcmEgcXVlIGVsIE9DUiBsZWEgZWwgbm9tYnJlIGNvbXBsZXRvIHkgY2xhcm8sIDIpIEdVSUEgcXVlIGFnYXJyYSBlbCBkb2N1bWVudG8gYXVucXVlIGVzdGUgc29icmUgdGVsYSBkZSBjb2xvciAobWFzY2FyYSBwb3Igc2F0dXJhY2lvbjogbGEgdGFyamV0YSBlcyBwb2NvIHNhdHVyYWRhLCBsYSB0ZWxhIGRlIGNvbG9yIGJyaWxsYSB5IHNlIGNvbmZ1bmRpYSBjb24gZWwgdW1icmFsIGRlIGJyaWxsbyksIDMpIEFVVE8tQ0FQVFVSQSBjb24gY3VlbnRhIGF0cmFzIHRhbWJpZW4gY3VhbmRvIGVsIGRvY3VtZW50byBsbGVuYSB0b2RvIGVsIGN1YWRybywgNCkgT0NSIGNvbiBwYXNlIGV4dHJhIGRlIHRleHRvIGRpc3BlcnNvIChQU00gMTEpIHBhcmEgbG9zIGNhbXBvcyBzdWVsdG9zIGRlbCBkb2N1bWVudG8sIDUpIFBBTkVMIERFIExFQ1RVUkEgc2luIGNhbGxlam9uIHNpbiBzYWxpZGE6IHNpIGVsIE9DUiBzYWx0byB1bmEgcGFsYWJyYSwgdHUgbm9tYnJlIGRlbCBwYXNvIDEgbWFuZGEgeSBzZSBhY2VwdGEgbGEgY29ycmVjY2lvbiBjb24gYWxndW5hIGxldHJhIHJlYWwgbGVpZGE7IHlhIG5vIHZ1ZWx2ZSBlbCBwYW5lbCBhIGNhZGEgcmF0bykqLwooZnVuY3Rpb24oKXsKJ3VzZSBzdHJpY3QnOwp2YXIgVyA9ICh0eXBlb2Ygd2luZG93IT09J3VuZGVmaW5lZCcpP3dpbmRvdzp0aGlzOwppZiAoVy5fX1pZUkFfUkVWRV9fKSB7IHJldHVybjsgfQpXLl9fWllSQV9SRVZFX18gPSAnRic7CgovKiA9PT09PT09PT09PT09PT09PSB1dGlsaWRhZGVzIGRlIHRleHRvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uICQoaWQpeyB0cnl7IHJldHVybiAodHlwZW9mIGRvY3VtZW50IT09J3VuZGVmaW5lZCcpP2RvY3VtZW50LmdldEVsZW1lbnRCeUlkKGlkKTpudWxsOyB9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9IH0KZnVuY3Rpb24gbG9nKCl7IHRyeXsgdmFyIGE9WydbWllSQS1SRVZFXSddOyBmb3IodmFyIGk9MDtpPGFyZ3VtZW50cy5sZW5ndGg7aSsrKXsgYS5wdXNoKGFyZ3VtZW50c1tpXSk7IH0gY29uc29sZS5sb2cuYXBwbHkoY29uc29sZSxhKTsgfWNhdGNoKGUpe30gfQoKZnVuY3Rpb24gbm9ybShzKXsKICB2YXIgdD0ocz09bnVsbD8nJzpTdHJpbmcocykpLnRvVXBwZXJDYXNlKCk7CiAgdD10LnJlcGxhY2UoL1tcdTAwQzFcdTAwQzBcdTAwQzRcdTAwQzJdL2csJ0EnKS5yZXBsYWNlKC9bXHUwMEM5XHUwMEM4XHUwMENCXHUwMENBXS9nLCdFJykucmVwbGFjZSgvW1x1MDBDRFx1MDBDQ1x1MDBDRlx1MDBDRV0vZywnSScpLnJlcGxhY2UoL1tcdTAwRDNcdTAwRDJcdTAwRDZcdTAwRDRdL2csJ08nKS5yZXBsYWNlKC9bXHUwMERBXHUwMEQ5XHUwMERDXHUwMERCXS9nLCdVJykucmVwbGFjZSgvXHUwMEQxL2csJ04nKTsKICByZXR1cm4gdC5yZXBsYWNlKC9bXkEtWiBdL2csJyAnKS5yZXBsYWNlKC9ccysvZywnICcpLnRyaW0oKTsKfQpmdW5jdGlvbiBsZXYoYSxiKXsKICBhPShhPT1udWxsPycnOlN0cmluZyhhKSk7IGI9KGI9PW51bGw/Jyc6U3RyaW5nKGIpKTsKICB2YXIgbj1hLmxlbmd0aCwgbT1iLmxlbmd0aDsKICBpZighbil7IHJldHVybiBtOyB9IGlmKCFtKXsgcmV0dXJuIG47IH0KICB2YXIgaSxqLHByZXY9bmV3IEFycmF5KG0rMSksY3VyPW5ldyBBcnJheShtKzEpOwogIGZvcihqPTA7ajw9bTtqKyspeyBwcmV2W2pdPWo7IH0KICBmb3IoaT0xO2k8PW47aSsrKXsKICAgIGN1clswXT1pOwogICAgZm9yKGo9MTtqPD1tO2orKyl7CiAgICAgIHZhciBjPShhLmNoYXJBdChpLTEpPT09Yi5jaGFyQXQoai0xKSk/MDoxOwogICAgICB2YXIgdj1wcmV2W2pdKzE7CiAgICAgIGlmKGN1cltqLTFdKzE8dil7IHY9Y3VyW2otMV0rMTsgfQogICAgICBpZihwcmV2W2otMV0rYzx2KXsgdj1wcmV2W2otMV0rYzsgfQogICAgICBjdXJbal09djsKICAgIH0KICAgIGZvcihqPTA7ajw9bTtqKyspeyBwcmV2W2pdPWN1cltqXTsgfQogIH0KICByZXR1cm4gcHJldlttXTsKfQpmdW5jdGlvbiBzaW1QYXIoYSxiKXsgYT1ub3JtKGEpOyBiPW5vcm0oYik7IGlmKCFhfHwhYil7IHJldHVybiAwOyB9IHJldHVybiAxLShsZXYoYSxiKS9NYXRoLm1heChhLmxlbmd0aCxiLmxlbmd0aCkpOyB9CmZ1bmN0aW9uIHNpbU5vbWJyZXMoYSxiKXsKICBhPW5vcm0oYSk7IGI9bm9ybShiKTsKICBpZighYXx8IWIpeyByZXR1cm4gMDsgfQogIHZhciBzMT1zaW1QYXIoYSxiKTsKICB2YXIgdGE9YS5zcGxpdCgnICcpLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPjE7IH0pOwogIHZhciB0Yj1iLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgdmFyIHMyPTA7CiAgaWYodGEubGVuZ3RoJiZ0Yi5sZW5ndGgpewogICAgdmFyIGNvcnRvPSh0YS5sZW5ndGg8PXRiLmxlbmd0aCk/dGE6dGI7CiAgICB2YXIgbGFyZ289KHRhLmxlbmd0aDw9dGIubGVuZ3RoKT90Yjp0YTsKICAgIHZhciB0b3Q9MCxpLGo7CiAgICBmb3IoaT0wO2k8Y29ydG8ubGVuZ3RoO2krKyl7CiAgICAgIHZhciBtZWpvcj0wOwogICAgICBmb3Ioaj0wO2o8bGFyZ28ubGVuZ3RoO2orKyl7IHZhciB2PXNpbVBhcihjb3J0b1tpXSxsYXJnb1tqXSk7IGlmKHY+bWVqb3IpeyBtZWpvcj12OyB9IH0KICAgICAgdG90Kz1tZWpvcjsKICAgIH0KICAgIHMyPXRvdC9jb3J0by5sZW5ndGg7CiAgfQogIHJldHVybiBNYXRoLm1heChzMSxzMik7Cn0KCi8qID09PT09PT09PT09PT09PT09IE1SWiB5IG5vbWJyZSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBtcnpMaW5lYXModCl7CiAgdmFyIG91dD1bXSwgbGluZXM9KHR8fCcnKS5zcGxpdCgvW1xyXG5dKy8pLCBpOwogIGZvcihpPTA7aTxsaW5lcy5sZW5ndGg7aSsrKXsKICAgIHZhciBsPWxpbmVzW2ldLnJlcGxhY2UoL1tccy5dL2csJycpLnRvVXBwZXJDYXNlKCk7CiAgICBpZihsLmxlbmd0aD49MjAgJiYgL15bQS1aMC05PF0rJC8udGVzdChsKSAmJiBsLmluZGV4T2YoJzw8Jyk+PTApeyBvdXQucHVzaChsKTsgfQogIH0KICByZXR1cm4gb3V0Owp9CmZ1bmN0aW9uIG1yek5vbWJyZXModCl7CiAgdmFyIHJlcz1bXSwgdmlzdG9zPXt9LCBscz1tcnpMaW5lYXModCksIGk7CiAgZnVuY3Rpb24gcHVzaChub21icmUpewogICAgbm9tYnJlPW5vcm0obm9tYnJlKTsKICAgIGlmKG5vbWJyZSAmJiBub21icmUubGVuZ3RoPj0zICYmICF2aXN0b3Nbbm9tYnJlXSl7IHZpc3Rvc1tub21icmVdPTE7IHJlcy5wdXNoKG5vbWJyZSk7IH0KICB9CiAgZm9yKGk9MDtpPGxzLmxlbmd0aDtpKyspewogICAgdmFyIGw9bHNbaV0sIG07CiAgICBtPWwubWF0Y2goL15QPChbQS1aXXswLDN9KShbQS1aXXsyLH0pPDwoW0EtWjxdKikvKTsKICAgIGlmKG0peyBwdXNoKG1bMl0rJyAnKyhtWzNdfHwnJykpOyB9CiAgICBtPWwubWF0Y2goL15QPChbQS1aXXswLDN9PykoW0EtWl17Mix9KTw8KFtBLVo8XSopLyk7CiAgICBpZihtKXsgcHVzaChtWzJdKycgJysobVszXXx8JycpKTsgfQogICAgbT1sLm1hdGNoKC9eKFtBLVo8XXs0LH0pPDwoW0EtWjxdezIsfSkvKTsKICAgIGlmKG0peyBwdXNoKG1bMV0rJyAnKyhtWzJdfHwnJykpOyB9CiAgICBtPWwubWF0Y2goL14oW0EtWl17Mix9KTw8KFtBLVo8XSopLyk7CiAgICBpZihtKXsgcHVzaChtWzFdKycgJysobVsyXXx8JycpKTsgfQogICAgbT1sLm1hdGNoKC8oW0EtWl17Mix9KTw8KFtBLVo8XXsyLH0pLyk7CiAgICBpZihtKXsgcHVzaChtWzFdKycgJysobVsyXXx8JycpKTsgfQogIH0KICByZXR1cm4gcmVzOwp9CmZ1bmN0aW9uIG5vbWJyZURlVGV4dG8odCl7CiAgdmFyIFQ9KHR8fCcnKS50b1VwcGVyQ2FzZSgpLCBjYW5kPVtdLCBtLCBpOwogIHZhciByZT0vKE5PTUJSRVM/fEFQRUxMSURPUz98TkFNRVM/fFNVUk5BTUUpXHMqWzpcLlwtXT9ccyooKD86W0EtWlx1MDBDMVx1MDBDOVx1MDBDRFx1MDBEM1x1MDBEQVx1MDBEQ1x1MDBEMV1bQS1aXHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxXXsxLDE1fSkoPzpbXHNcLl0rW0EtWlx1MDBDMVx1MDBDOVx1MDBDRFx1MDBEM1x1MDBEQVx1MDBEQ1x1MDBEMV1bQS1aXHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxXXsxLDE1fSl7MCw0fSkvZzsKICB3aGlsZSgobT1yZS5leGVjKFQpKSE9PW51bGwpeyBpZihtWzJdKXsgY2FuZC5wdXNoKG1bMl0pOyB9IH0KICBjYW5kPWNhbmQuY29uY2F0KG1yek5vbWJyZXMoVCkpOwogIHZhciBsaW5lcz1ULnNwbGl0KC9bXHJcbl0rLyk7CiAgZm9yKGk9MDtpPGxpbmVzLmxlbmd0aDtpKyspewogICAgdmFyIHc9bGluZXNbaV0ucmVwbGFjZSgvW15BLVpcdTAwQzFcdTAwQzlcdTAwQ0RcdTAwRDNcdTAwREFcdTAwRENcdTAwRDEgXS9nLCcgJykudHJpbSgpLnNwbGl0KC9ccysvKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD49MzsgfSk7CiAgICBpZih3Lmxlbmd0aD49MiAmJiB3Lmxlbmd0aDw9NCl7IGNhbmQucHVzaCh3LmpvaW4oJyAnKSk7IH0KICB9CiAgcmV0dXJuIGNhbmQ7Cn0KZnVuY3Rpb24gdG9rZW5zRGUocyl7IHJldHVybiBub3JtKHMpLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7IH0KZnVuY3Rpb24gcGFyUGFyZWNpZG8odDEsdDIpewogIGlmKHQxPT09dDIpeyByZXR1cm4gdHJ1ZTsgfQogIGlmKHNpbVBhcih0MSx0Mik+PTAuNzgpeyByZXR1cm4gdHJ1ZTsgfQogIGlmKHQxLmxlbmd0aD49NCYmdDIubGVuZ3RoPj00JiYodDEuaW5kZXhPZih0Mik9PT0wfHx0Mi5pbmRleE9mKHQxKT09PTApKXsgcmV0dXJuIHRydWU7IH0KICByZXR1cm4gZmFsc2U7Cn0KLyogPT09PT09PT09PT09IGd1YXJkaWFuYXMgZGUgbGEgbGVjdHVyYSBjb25maXJtYWRhIChwYXNvIDIpID09PT09PT09PT09PSAqLwpmdW5jdGlvbiB0b2tlbnNOb21icmVEZSh0ZXh0byl7CiAgdmFyIFQ9bm9ybSh0ZXh0bykuc3BsaXQoJyAnKSwgb3V0PVtdLCBpLCBqOwogIGZvcihpPTA7aTxULmxlbmd0aDtpKyspewogICAgdmFyIHQ9VFtpXTsKICAgIGlmKHQubGVuZ3RoPDN8fHQubGVuZ3RoPjE1KXsgY29udGludWU7IH0KICAgIGlmKCEvXltBLVpdKyQvLnRlc3QodCkpeyBjb250aW51ZTsgfQogICAgdmFyIG1hbGE9ZmFsc2U7CiAgICBmb3Ioaj0wO2o8UEFMQUJSQVNfTk9fTk9NQlJFLmxlbmd0aDtqKyspeyBpZih0LmluZGV4T2YoUEFMQUJSQVNfTk9fTk9NQlJFW2pdKT09PTApeyBtYWxhPXRydWU7IGJyZWFrOyB9IH0KICAgIGlmKCFtYWxhKXsgb3V0LnB1c2godCk7IH0KICB9CiAgcmV0dXJuIG91dDsKfQpmdW5jdGlvbiBlZGljaW9uQWNlcHRhYmxlKHRleHRvRWRpdGFkbywgb2NyVG9rcyl7CiAgdmFyIHRva3M9dG9rZW5zRGUodGV4dG9FZGl0YWRvKSwgaSwgajsKICBpZighdG9rcy5sZW5ndGh8fCFvY3JUb2tzfHwhb2NyVG9rcy5sZW5ndGgpeyByZXR1cm4gZmFsc2U7IH0KICBmb3IoaT0wO2k8dG9rcy5sZW5ndGg7aSsrKXsKICAgIHZhciBwYXNhPWZhbHNlOwogICAgZm9yKGo9MDtqPG9jclRva3MubGVuZ3RoO2orKyl7CiAgICAgIGlmKHBhclBhcmVjaWRvKHRva3NbaV0sb2NyVG9rc1tqXSkpeyBwYXNhPXRydWU7IGJyZWFrOyB9CiAgICAgIGlmKHRva3NbaV0ubGVuZ3RoPj01JiZvY3JUb2tzW2pdLmxlbmd0aD49NSYmbGV2KHRva3NbaV0sb2NyVG9rc1tqXSk8PTIpeyBwYXNhPXRydWU7IGJyZWFrOyB9CiAgICB9CiAgICBpZighcGFzYSl7IHJldHVybiBmYWxzZTsgfQogIH0KICByZXR1cm4gdHJ1ZTsKfQp2YXIgUEFMQUJSQVNfTk9fTk9NQlJFPVsnRE9NSUNJTElPJywnRElSRUNDSU9OJywnQ09MT05JQScsJ0JBUlJJTycsJ1JFU0lERU5DSUEnLCdDQVNFUklPJywnQ0FOVE9OJywnQUxERUEnLCdTRUNUT1InLCdPQlNFUlZBQ0lPTicsJ0VTVEFETycsJ0RPTkFOVEUnLCdHUlVQTycsJ1NBTkdSRScsJ1NBTkcnLCdNVU5JQ0lQSU8nLCdERVBBUlRBTUVOVE8nLCdGRUNIQScsJ05BQ0lNSUVOVE8nLCdTRVhPJywnTkFDSU9OQUxJREFEJywnRk9MSU8nLCdOVU1FUk8nLCdET0NVTUVOVE8nLCdDRURVTEEnLCdJREVOVElEQUQnLCdMSUNFTkNJQScsJ1JFUFVCTEknLCdTRUNSRVRBUklBJywnRU1JU0lPTicsJ1ZFTkNJTUlFTlRPJywnQ0xBU0UnLCdDQVRFR09SSUEnLCdFTkRPUlNFTUVOVCcsJ1JFU1RSSUNUSU9OJywnQUREUkVTUycsJ0xVR0FSJywnRURBRCcsJ1BBUkVOJywnRklMSUFDSU9OJywnRklMSUFDSU9OJywnTUFSQ0EnLCdTUEVDSU1FTicsJ1NBTVBMRScsJ1ZPVEFDSU9OJywnVE9NQURPUicsJ05BQ0lPJywnRE9NJywnTk9NQlJFUycsJ05PTUJSRScsJ0FQRUxMSURPUycsJ0FQRUxMSURPJywnQ0lVREFEJywnQVZFTklEQScsJ0JPVUxFVkFSRCcsJ0RVSScsJ0RQSSddOwpmdW5jdGlvbiBwYXJlY2VOb21icmVMaW5lYShjKXsKICB2YXIgdz0oY3x8JycpLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgaWYody5sZW5ndGg8Mnx8dy5sZW5ndGg+NSl7IHJldHVybiBmYWxzZTsgfQogIHZhciBtYWxvcz17J0VMJzoxLCdMQSc6MSwnTE9TJzoxLCdMQVMnOjEsJ0RFJzoxLCdERUwnOjF9OwogIGZvcih2YXIgaT0wO2k8dy5sZW5ndGg7aSsrKXsKICAgIGlmKG1hbG9zW3dbaV1dKXsgcmV0dXJuIGZhbHNlOyB9CiAgICBmb3IodmFyIGo9MDtqPFBBTEFCUkFTX05PX05PTUJSRS5sZW5ndGg7aisrKXsgaWYod1tpXS5pbmRleE9mKFBBTEFCUkFTX05PX05PTUJSRVtqXSk9PT0wKXsgcmV0dXJuIGZhbHNlOyB9IH0KICB9CiAgcmV0dXJuIHRydWU7Cn0KZnVuY3Rpb24gbm9tYnJlQ29pbmNpZGUoZXNjcml0bywgdGV4dG9Eb2MsIGVzdHJpY3RvKXsKICB2YXIgdmFjaW89e29rOmZhbHNlLCBsZWlkbzonJywgcHVudDowLCBoYXk6ZmFsc2V9OwogIHZhciBVPXRva2Vuc0RlKGVzY3JpdG8pOwogIGlmKFUubGVuZ3RoPDIpeyByZXR1cm4gdmFjaW87IH0KICB2YXIgY2FuZD1ub21icmVEZVRleHRvKHRleHRvRG9jKSwgbGltcGlvcz1bXSwgaSwgazsKICBmb3IoaT0wO2k8Y2FuZC5sZW5ndGg7aSsrKXsKICAgIHZhciBjPW5vcm0oY2FuZFtpXSk7CiAgICBpZighYyl7IGNvbnRpbnVlOyB9CiAgICB2YXIgdG9rcz1jLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgICBpZih0b2tzLmxlbmd0aDwyfHx0b2tzLmxlbmd0aD41KXsgY29udGludWU7IH0KICAgIGlmKCFwYXJlY2VOb21icmVMaW5lYShjKSl7IGNvbnRpbnVlOyB9CiAgICBsaW1waW9zLnB1c2godG9rcyk7CiAgfQogIHZhciBUMj1ub3JtKHRleHRvRG9jKS5zcGxpdCgnICcpLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPjE7IH0pOwogIHZhciB2aXN0YXM9e30sIGkyLCBMMjsKICBmb3IoaTI9MDtpMjxsaW1waW9zLmxlbmd0aDtpMisrKXsgdmlzdGFzW2xpbXBpb3NbaTJdLmpvaW4oJyAnKV09MTsgfQogIGZvcihpMj0wO2kyPFQyLmxlbmd0aDtpMisrKXsKICAgIGZvcihMMj0yO0wyPD00ICYmIGkyK0wyPD1UMi5sZW5ndGg7TDIrKyl7CiAgICAgIHZhciB3aW49VDIuc2xpY2UoaTIsaTIrTDIpLmpvaW4oJyAnKTsKICAgICAgaWYoIXZpc3Rhc1t3aW5dICYmIHBhcmVjZU5vbWJyZUxpbmVhKHdpbikpeyB2aXN0YXNbd2luXT0xOyBsaW1waW9zLnB1c2god2luLnNwbGl0KCcgJykpOyB9CiAgICB9CiAgfQogIGlmKCFsaW1waW9zLmxlbmd0aCl7IHJldHVybiB2YWNpbzsgfQogIHZhciB1bmlvbj17fSwgY2xhdmVzPVtdOwogIGZvcihpPTA7aTxsaW1waW9zLmxlbmd0aDtpKyspewogICAgZm9yKGs9MDtrPGxpbXBpb3NbaV0ubGVuZ3RoO2srKyl7CiAgICAgIGlmKCF1bmlvbltsaW1waW9zW2ldW2tdXSl7IHVuaW9uW2xpbXBpb3NbaV1ba11dPTE7IGNsYXZlcy5wdXNoKGxpbXBpb3NbaV1ba10pOyB9CiAgICB9CiAgfQogIGZ1bmN0aW9uIGN1YW50b3MobGlzdGEpewogICAgdmFyIG49MCwgaiwgdDsKICAgIGZvcihqPTA7ajxVLmxlbmd0aDtqKyspewogICAgICBmb3IodD0wO3Q8bGlzdGEubGVuZ3RoO3QrKyl7IGlmKHBhclBhcmVjaWRvKFVbal0sbGlzdGFbdF0pKXsgbisrOyBicmVhazsgfSB9CiAgICB9CiAgICByZXR1cm4gbjsKICB9CiAgdmFyIG1lam9yQ2FuZD0nJywgbWVqb3JDb3Y9MDsKICBmb3IoaT0wO2k8bGltcGlvcy5sZW5ndGg7aSsrKXsKICAgIHZhciBjb3Y9Y3VhbnRvcyhsaW1waW9zW2ldKS9VLmxlbmd0aDsKICAgIGlmKGNvdj5tZWpvckNvdil7IG1lam9yQ292PWNvdjsgbWVqb3JDYW5kPWxpbXBpb3NbaV0uam9pbignICcpOyB9CiAgfQogIHZhciBjb3ZVPWN1YW50b3MoY2xhdmVzKS9VLmxlbmd0aDsKICBpZihjb3ZVPm1lam9yQ292KXsgbWVqb3JDb3Y9Y292VTsgfQogIHZhciBuTWF0Y2g9Y3VhbnRvcyhjbGF2ZXMpLCBtZWpvclNpbT0wLCBqMywgdDM7CiAgZm9yKGozPTA7ajM8VS5sZW5ndGg7ajMrKyl7CiAgICBmb3IodDM9MDt0MzxjbGF2ZXMubGVuZ3RoO3QzKyspewogICAgICBpZihwYXJQYXJlY2lkbyhVW2ozXSxjbGF2ZXNbdDNdKSl7IHZhciBzdj1zaW1QYXIoVVtqM10sY2xhdmVzW3QzXSk7IGlmKHN2Pm1lam9yU2ltKXsgbWVqb3JTaW09c3Y7IH0gfQogICAgfQogIH0KICB2YXIgb2s7CiAgaWYobWVqb3JDb3Y+PTAuOTk5KXsgb2s9dHJ1ZTsgfQogIGVsc2UgaWYoZXN0cmljdG8peyBvaz1mYWxzZTsgfQogIGVsc2UgaWYobk1hdGNoPj0yICYmIGNvdlU+PTAuNSl7IG9rPXRydWU7IH0KICBlbHNlIGlmKG5NYXRjaD49MSAmJiBjb3ZVPj0wLjUgJiYgbWVqb3JTaW0+PTAuODApeyBvaz10cnVlOyB9CiAgZWxzZSBpZihuTWF0Y2g+PTEgJiYgbWVqb3JTaW0+PTAuOTgpeyBvaz10cnVlOyB9CiAgZWxzZXsgb2s9ZmFsc2U7IH0KICByZXR1cm4ge29rOm9rLCBsZWlkbzptZWpvckNhbmQsIHB1bnQ6bWVqb3JDb3YsIGhheTp0cnVlfTsKfQoKLyogPT09PT09PT09PT09PT09PT0gZGV0ZWNjaW9uIGRlIGxhZG8gPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gZGV0ZWN0YXJMYWRvKHRleHRvLCB0aWVuZUNhcmEpewogIHZhciB0PSh0ZXh0b3x8JycpLnRvVXBwZXJDYXNlKCk7CiAgdmFyIHJldj0wLCBmcmU9MCwgaTsKICB2YXIgbHQ9KHQubWF0Y2goLzwvZyl8fFtdKS5sZW5ndGg7CiAgaWYobHQ+PTYpeyByZXR1cm4gJ3JldmVyc28nOyB9CiAgaWYoL1BERjRJPzcvLnRlc3QodC5yZXBsYWNlKC9ccy9nLCcnKSkpeyByZXYrPTIuNTsgfQogIHZhciBSVnM9WydET01JQ0lMSU8nLCdESVJFQ0NJT04nLCdESVJFQ0NJXHUwMEQzTicsJ0NPTE9OSUEnLCdCQVJSSU8nLCdSRVNJREVOQ0lBJywnQ0FTRVJJTycsJ0NBTlRPTicsJ0FMREVBJywnU0VDVE9SJywnT0JTRVJWQUNJT04nLCdPQlNFUlZBQ0lcdTAwRDNOJywnRE9OQU5URScsJ0dSVVBPIFNBTkcnLCdUSVBPIERFIFNBTkcnLCdTQU5HVUlORU8nLCdFU1RBRE8gQ0lWSUwnLCdFTkRPUlNFTUVOVCcsJ1JFU1RSSUNUSU9OJywnTVVOSUNJUElPJ107CiAgdmFyIFJWdz1bJ0VNSVNJT04nLCdFTUlTSVx1MDBEM04nLCdWRU5DSU1JRU5UTycsJ1ZFTkNFJywnRVhQSVJFUycsJ0lTU1VFRCcsJ1ZBTElERVonLCdFWFBJUkEnLCdDTEFTRScsJ0NBVEVHT1JJQScsJ0NBVEVHT1JcdTAwQ0RBJywnSVNTJywnRVhQJ107CiAgdmFyIEZSPVsnTk9NQlJFUycsJ0FQRUxMSURPUycsJ05BTUVTJywnU1VSTkFNRScsJ0dJVkVOJywnRFVJJywnRE9DVU1FTlRPIFVOSUNPJywnRE9DVU1FTlRPIFx1MDBEQU5JQ08nLCdDRURVTEEnLCdDXHUwMEM5RFVMQScsJ0lERU5USURBRCcsJ0xJQ0VOQ0lBJywnRFJJVkVSJywnTkFDSU1JRU5UTycsJ0JJUlRIJywnU0VYTycsJ1NFWCcsJ05BQ0lPTkFMSURBRCcsJ05BQ0lPTkFMSVRZJywnRk9MSU8nLCdSRVBVQkxJJywnTlVNRVJPJywnTlx1MDBEQU1FUk8nLCdOVU1CRVInLCdJRCBOTyddOwogIGZvcihpPTA7aTxSVnMubGVuZ3RoO2krKyl7IGlmKHQuaW5kZXhPZihSVnNbaV0pPj0wKXsgcmV2Kz0yOyB9IH0KICBmb3IoaT0wO2k8UlZ3Lmxlbmd0aDtpKyspeyBpZih0LmluZGV4T2YoUlZ3W2ldKT49MCl7IHJldis9MC43NTsgfSB9CiAgZm9yKGk9MDtpPEZSLmxlbmd0aDtpKyspeyBpZih0LmluZGV4T2YoRlJbaV0pPj0wKXsgZnJlKz0xOyB9IH0KICBpZih0aWVuZUNhcmEpeyBmcmUrPTQ7IH0KICBpZihyZXY+PTMuNSAmJiByZXY+ZnJlKzEpeyByZXR1cm4gJ3JldmVyc28nOyB9CiAgaWYoZnJlPj0zICYmIGZyZT5yZXYrMSl7IHJldHVybiAnZnJlbnRlJzsgfQogIGlmKHJldj5mcmUgJiYgcmV2Pj0yKXsgcmV0dXJuICdyZXZlcnNvJzsgfQogIGlmKGZyZT5yZXYgJiYgZnJlPj0yKXsgcmV0dXJuICdmcmVudGUnOyB9CiAgcmV0dXJuICdkZXNjb25vY2lkbyc7Cn0KCi8qID09PT09PT09PT09PT09PT09IGdhbmNobyBwYXJhIHBydWViYXMgKG5vZGUsIHNpbiBET00pID09PT09PT09PT09PT09PT09ICovCmlmICh0eXBlb2YgZG9jdW1lbnQ9PT0ndW5kZWZpbmVkJyB8fCB0eXBlb2YgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQhPT0nZnVuY3Rpb24nKXsKICBXLl9fWllSQV9URVNUX189e25vcm06bm9ybSxsZXY6bGV2LHNpbVBhcjpzaW1QYXIsc2ltTm9tYnJlczpzaW1Ob21icmVzLG1yekxpbmVhczptcnpMaW5lYXMsbXJ6Tm9tYnJlczptcnpOb21icmVzLG5vbWJyZURlVGV4dG86bm9tYnJlRGVUZXh0byxub21icmVDb2luY2lkZTpub21icmVDb2luY2lkZSxkZXRlY3RhckxhZG86ZGV0ZWN0YXJMYWRvLGV2YWx1YUNhcmE6ZXZhbHVhQ2FyYSxlYXJEZTplYXJEZSxjZW50cm9EZTpjZW50cm9EZSxxdWFkVmFsaWRvOnF1YWRWYWxpZG8sYXJlYVF1YWQ6YXJlYVF1YWQsZXRpcXVldGFDb21wb25lbnRlczpldGlxdWV0YUNvbXBvbmVudGVzLGVzcXVpbmFzRGVNYXNjYXJhOmVzcXVpbmFzRGVNYXNjYXJhLG1lZGlhbmFRdWFkOm1lZGlhbmFRdWFkLHF1YWRFc3RhYmxlOnF1YWRFc3RhYmxlLG5pdG9EZTpuaXRvRGUsZnJhY2Npb25CbGFuY286ZnJhY2Npb25CbGFuY28sdG9rZW5zTm9tYnJlRGU6dG9rZW5zTm9tYnJlRGUsZWRpY2lvbkFjZXB0YWJsZTplZGljaW9uQWNlcHRhYmxlLGVsZWdpclRleHRvOmVsZWdpclRleHRvLHBhclBhcmVjaWRvOnBhclBhcmVjaWRvLHRva2Vuc0RlOnRva2Vuc0RlLHRvZG9Pa1BhcmFDcmVhcjp0b2RvT2tQYXJhQ3JlYXJ9OwogIHJldHVybjsKfQoKLyogPT09PT09PT09PT09PT09PT0gZ2FuY2hvIGRlIHBydWViYXMgY29uIERPTSBzaW11bGFkbyA9PT09PT09PT09PT09PT09PSAqLwpXLl9fWllSQV9SRVZGX1RFU1RfXz17fTsKCi8qID09PT09PT09PT09PT09PT09IGZldGNoIGNvbiByZWludGVudG9zICsgd2FybXVwID09PT09PT09PT09PT09PT09ICovCihmdW5jdGlvbigpewogIGlmKFcuX196eUZldGNoRml4KXsgcmV0dXJuOyB9CiAgVy5fX3p5RmV0Y2hGaXg9MTsKICB2YXIgX2Y9Vy5mZXRjaD9XLmZldGNoLmJpbmQoVyk6bnVsbDsKICBpZighX2YpeyByZXR1cm47IH0KICBXLmZldGNoPWZ1bmN0aW9uKCl7CiAgICB2YXIgYXJncz1hcmd1bWVudHMsIG49MDsKICAgIGZ1bmN0aW9uIG90cm8oKXsgcmV0dXJuIF9mLmFwcGx5KG51bGwsYXJncykudGhlbihmdW5jdGlvbihyKXsKICAgICAgaWYoWzUwMCw1MDIsNTAzLDUwNCw0MTNdLmluZGV4T2Yoci5zdGF0dXMpPj0wICYmIG48Myl7IG4rKzsgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7IHNldFRpbWVvdXQocmVzLDcwMCpuKTsgfSkudGhlbihvdHJvKTsgfQogICAgICByZXR1cm4gcjsKICAgIH0sIGZ1bmN0aW9uKGUpewogICAgICBpZihuPDMpeyBuKys7IHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpeyBzZXRUaW1lb3V0KHJlcyw3MDAqbik7IH0pLnRoZW4ob3Rybyk7IH0KICAgICAgdGhyb3cgZTsKICAgIH0pOyB9CiAgICByZXR1cm4gb3RybygpOwogIH07CiAgdHJ5eyBfZihXLmxvY2F0aW9uLnBhdGhuYW1lLHtjYWNoZTonbm8tc3RvcmUnLGhlYWRlcnM6eyd4LXp5LXdhcm11cCc6JzEnfX0pLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH1jYXRjaChlKXt9Cn0pKCk7CgovKiA9PT09PT09PT09PT09PT09PSBlc3RhZG8gZGVsIGZsdWpvID09PT09PT09PT09PT09PT09ICovCnZhciBFU1Q9e3Bhc286MSwgdGlwbzonZGVzY29ub2NpZG8nLCBuZWNlc2l0YVJldmVyc286dHJ1ZSwgbm9tYnJlT2s6ZmFsc2UsIGZyZW50ZU9rOmZhbHNlLCByZXZlcnNvT2s6ZmFsc2UsIHNlbGZpZU9rOmZhbHNlLCBpbnRlbnRvczozLCBmcmVudGVJbWc6JycsIHJldmVyc29JbWc6JycsIHNlbGZpZUltZzonJywgZXNjcml0bzonJywgZnJlbnRlVGV4dG86JycsIHJldmVyc29UZXh0bzonJywgY2FyYVZpdmE6bnVsbCwgY2FyYURvYzpudWxsfTsKdmFyIHN0cmVhbXM9e307CnZhciBISU5UUz17fTsKCmZ1bmN0aW9uIGNsYXNpZmljYXJUaXBvKCl7CiAgdmFyIHNlbD0kKCd0aXBvRG9jJyksIHR4dD0nJzsKICBpZihzZWwpewogICAgdmFyIG9wPXNlbC5vcHRpb25zICYmIHNlbC5vcHRpb25zW3NlbC5zZWxlY3RlZEluZGV4XTsKICAgIHR4dD0ob3AmJm9wLnRleHQ/b3AudGV4dDonJykrJyAnKyhzZWwudmFsdWV8fCcnKTsKICB9CiAgdHh0PXR4dC50b0xvd2VyQ2FzZSgpOwogIGlmKC9wYXNhcG9ydGV8cGFzc3BvcnQvLnRlc3QodHh0KSl7IHJldHVybiB7azoncGFzYXBvcnRlJywgcmV2ZXJzbzpmYWxzZX07IH0KICBpZigvc2FsdmFkb3J8XGJkdWlcYi8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidkdWknLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL2d1YXRlbWFsYXxndWF0ZS8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidndCcsIHJldmVyc286dHJ1ZX07IH0KICBpZigvbmljYXJhZ3VhLy50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J25pJywgcmV2ZXJzbzp0cnVlfTsgfQogIGlmKC9ob25kdXJhcy8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidobicsIHJldmVyc286dHJ1ZX07IH0KICBpZigvdXNhfGVzdGFkb3MgdW5pZG9zfGxpY2VuY2lhfGxpY2Vuc2V8ZHJpdmVyLy50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J3VzYScsIHJldmVyc286dHJ1ZX07IH0KICBpZigvb3Ryb3xvdGhlci8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidvdHJvJywgcmV2ZXJzbzp0cnVlfTsgfQogIHJldHVybiB7azonZGVzY29ub2NpZG8nLCByZXZlcnNvOnRydWV9Owp9CgovKiA9PT09PT09PT09PT09PT09PSBtZW5zYWplcyB5IGF5dWRhcyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBtc2coaWQsdGV4dG8sY29sb3IpewogIHZhciBlbD0kKGlkKTsKICBpZighZWwgJiYgSElOVFNbaWRdKXsgZWw9SElOVFNbaWRdOyB9CiAgaWYoIWVsKXsKICAgIHZhciBhbmNsYT0kKCdwczEnKTsKICAgIGVsPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgZWwuaWQ9aWQ7CiAgICBlbC5zdHlsZS5jc3NUZXh0PSdmb250LXNpemU6MTNweDttYXJnaW46NnB4IDA7bGluZS1oZWlnaHQ6MS4zNTsnOwogICAgaWYoYW5jbGEgJiYgYW5jbGEucGFyZW50Tm9kZSl7IGFuY2xhLnBhcmVudE5vZGUuaW5zZXJ0QmVmb3JlKGVsLGFuY2xhLm5leHRTaWJsaW5nKTsgfQogICAgZWxzZXsgZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZChlbCk7IH0KICAgIEhJTlRTW2lkXT1lbDsKICB9CiAgZWwudGV4dENvbnRlbnQ9dGV4dG98fCcnOwogIGlmKGNvbG9yKXsgZWwuc3R5bGUuY29sb3I9Y29sb3I7IH0KfQpmdW5jdGlvbiBidXN5KG9uKXsKICB2YXIgaWRzPVsnYmxvY0YnLCdibG9jQScsJ2Jsb2NTJ10sIGk7CiAgZm9yKGk9MDtpPGlkcy5sZW5ndGg7aSsrKXsgdmFyIGI9JChpZHNbaV0pOyBpZihiKXsgYi5zdHlsZS5kaXNwbGF5PW9uPydmbGV4Jzonbm9uZSc7IH0gfQp9CmZ1bmN0aW9uIHNob3dJbWcoaWQsZGF0YVVybCl7CiAgdmFyIHA9JChpZCk7CiAgaWYocCl7CiAgICBwLnNyYz1kYXRhVXJsOwogICAgcC5zdHlsZS5kaXNwbGF5PSdibG9jayc7CiAgICBwLnN0eWxlLm1heFdpZHRoPScyNDBweCc7CiAgICBwLnN0eWxlLm1heEhlaWdodD0nMjQwcHgnOwogICAgcC5zdHlsZS53aWR0aD0nYXV0byc7CiAgICBwLnN0eWxlLmhlaWdodD0nYXV0byc7CiAgICBwLnN0eWxlLmJvcmRlclJhZGl1cz0nMTBweCc7CiAgICBwLnN0eWxlLm1hcmdpbj0nOHB4IGF1dG8nOwogICAgcC5zdHlsZS5kaXNwbGF5PSdibG9jayc7CiAgfQp9CgovKiA9PT09PT09PT09PT09PT09PSBjYW1hcmE6IHByZXZpZXcgU0lFTVBSRSBjaGljbyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBsZXRyYURlKHBzSWQpeyByZXR1cm4gKHsnMic6J0YnLCczJzonQScsJzQnOidTJ30pW3BzSWRdfHwnRic7IH0KZnVuY3Rpb24gZmluZFZpZGVvKHBzSWQpewogIHZhciBsZXRyYT1sZXRyYURlKHBzSWQpOwogIHZhciBpZHM9Wyd2eicrbGV0cmEsJ3ZkJytsZXRyYSwndicrbGV0cmFdLCBpOwogIHZhciBjb250PSQoJ3BzJytwc0lkKTsKICBmb3IoaT0wO2k8aWRzLmxlbmd0aDtpKyspewogICAgdmFyIGNhbmQ9JChpZHNbaV0pOwogICAgaWYoY2FuZCAmJiBjYW5kLnRhZ05hbWU9PT0nVklERU8nKXsgcmV0dXJuIGNhbmQ7IH0KICB9CiAgaWYoY29udCl7CiAgICB2YXIgdj1jb250LnF1ZXJ5U2VsZWN0b3IoJ3ZpZGVvJyk7CiAgICBpZih2KXsgcmV0dXJuIHY7IH0KICB9CiAgcmV0dXJuIG51bGw7Cn0KZnVuY3Rpb24gZXN0aWxvQ2hpY28odil7CiAgaWYoIXYpeyByZXR1cm47IH0KICB2LnN0eWxlLm1heFdpZHRoPScyODBweCc7CiAgdi5zdHlsZS53aWR0aD0nMTAwJSc7CiAgdi5zdHlsZS5tYXhIZWlnaHQ9JzMyMHB4JzsKICB0cnl7IHYuc3R5bGUuYXNwZWN0UmF0aW89JzMgLyA0JzsgfWNhdGNoKGUpe30KICB2LnN0eWxlLm9iamVjdEZpdD0nY292ZXInOwogIHYuc3R5bGUuYm9yZGVyUmFkaXVzPScxMnB4JzsKICB2LnN0eWxlLmJhY2tncm91bmQ9JyMwMDAnOwogIHYuc3R5bGUuZGlzcGxheT0nYmxvY2snOwogIHYuc3R5bGUubWFyZ2luPScwIGF1dG8nOwp9CmZ1bmN0aW9uIHZpYnJhcigpeyB0cnl7IGlmKG5hdmlnYXRvci52aWJyYXRlKXsgbmF2aWdhdG9yLnZpYnJhdGUoNzApOyB9IH1jYXRjaChlKXt9IH0KZnVuY3Rpb24gYWxpbmVhck92ZXJsYXkocHNJZCwgdil7CiAgdHJ5ewogICAgdmFyIE9WPXsnMic6J292RicsJzMnOidvdkEnLCc0Jzonb3ZTJ307CiAgICB2YXIgb3Y9JChPVltwc0lkXSk7IGlmKCFvdnx8IXYpeyByZXR1cm47IH0KICAgIHZhciB6PSQoJ3Z6JytsZXRyYURlKHBzSWQpKTsgaWYoIXopeyByZXR1cm47IH0KICAgIHZhciB2cj12LmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpLCB6cj16LmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpOwogICAgaWYoIXZyLndpZHRofHwhdnIuaGVpZ2h0KXsgcmV0dXJuOyB9CiAgICBvdi5zdHlsZS5wb3NpdGlvbj0nYWJzb2x1dGUnOwogICAgb3Yuc3R5bGUubGVmdD1NYXRoLnJvdW5kKHZyLmxlZnQtenIubGVmdCkrJ3B4JzsKICAgIG92LnN0eWxlLnRvcD1NYXRoLnJvdW5kKHZyLnRvcC16ci50b3ApKydweCc7CiAgICBvdi5zdHlsZS53aWR0aD12ci53aWR0aCsncHgnOwogICAgb3Yuc3R5bGUuaGVpZ2h0PXZyLmhlaWdodCsncHgnOwogICAgdHJ5eyBvdi5zdHlsZS5vYmplY3RGaXQ9J2NvdmVyJzsgfWNhdGNoKGUyKXt9CiAgICBvdi5zdHlsZS5ib3JkZXJSYWRpdXM9JzEycHgnOwogICAgb3Yuc3R5bGUuekluZGV4PSc1JzsKICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIHp5RGV0KCl7IGlmKCFXLl9fenlEZXQpeyBXLl9fenlEZXQ9e307IH0gcmV0dXJuIFcuX196eURldDsgfQpmdW5jdGlvbiBvdHN1VW1icmFsKGhpc3QsdG90YWwpewogIHZhciBzdW09MCxpOyBmb3IoaT0wO2k8MjU2O2krKyl7IHN1bSs9aSpoaXN0W2ldOyB9CiAgdmFyIHN1bUI9MCx3Qj0wLGJlc3Q9MCx0aHI9MTI3OwogIGZvcihpPTA7aTwyNTY7aSsrKXsKICAgIHdCKz1oaXN0W2ldOyBpZih3Qj09PTApeyBjb250aW51ZTsgfQogICAgdmFyIHdGPXRvdGFsLXdCOyBpZih3Rj09PTApeyBicmVhazsgfQogICAgc3VtQis9aSpoaXN0W2ldOwogICAgdmFyIG1CPXN1bUIvd0IsIG1GPShzdW0tc3VtQikvd0YsIHY9d0Iqd0YqKG1CLW1GKSoobUItbUYpOwogICAgaWYodj5iZXN0KXsgYmVzdD12OyB0aHI9aTsgfQogIH0KICByZXR1cm4gdGhyOwp9CmZ1bmN0aW9uIHJhbmdvUHJveWVjY2lvbihhcnIsbix1bWJyYWwpewogIHZhciBhPS0xLGI9LTEsaTsKICBmb3IoaT0wO2k8bjtpKyspeyBpZihhcnJbaV0+PXVtYnJhbCl7IGlmKGE8MCl7IGE9aTsgfSBiPWk7IH0gfQogIGlmKGE8MHx8Yjw9YSl7IHJldHVybiBudWxsOyB9CiAgcmV0dXJuIFthLGJdOwp9Ci8qID09PT09PT09PT09PSBkZXRlY2Npb24gUkVBTCBkZWwgZG9jdW1lbnRvOiA0IGVzcXVpbmFzID09PT09PT09PT09PSAqLwpmdW5jdGlvbiBldGlxdWV0YUNvbXBvbmVudGVzKG1hc2ssIHcsIGgpewogIHZhciBsYWI9bmV3IEludDMyQXJyYXkodypoKSwgcGlsYT1uZXcgSW50MzJBcnJheSh3KmgpOwogIHZhciBtZWpvcj17dGFtOjAsaWQ6MH0sIGlkPTAsIGk7CiAgZm9yKGk9MDtpPHcqaDtpKyspewogICAgaWYobWFza1tpXSYmIWxhYltpXSl7CiAgICAgIGlkKys7IHZhciBzcD0wLCB0YW09MDsKICAgICAgcGlsYVtzcCsrXT1pOyBsYWJbaV09aWQ7CiAgICAgIHdoaWxlKHNwPjApewogICAgICAgIHZhciBwPXBpbGFbLS1zcF07IHRhbSsrOwogICAgICAgIHZhciB4PXAldywgeT0ocC14KS93OwogICAgICAgIGlmKHg+MCYmbWFza1twLTFdJiYhbGFiW3AtMV0peyBsYWJbcC0xXT1pZDsgcGlsYVtzcCsrXT1wLTE7IH0KICAgICAgICBpZih4PHctMSYmbWFza1twKzFdJiYhbGFiW3ArMV0peyBsYWJbcCsxXT1pZDsgcGlsYVtzcCsrXT1wKzE7IH0KICAgICAgICBpZih5PjAmJm1hc2tbcC13XSYmIWxhYltwLXddKXsgbGFiW3Atd109aWQ7IHBpbGFbc3ArK109cC13OyB9CiAgICAgICAgaWYoeTxoLTEmJm1hc2tbcCt3XSYmIWxhYltwK3ddKXsgbGFiW3Ard109aWQ7IHBpbGFbc3ArK109cCt3OyB9CiAgICAgIH0KICAgICAgaWYodGFtPm1lam9yLnRhbSl7IG1lam9yPXt0YW06dGFtLGlkOmlkfTsgfQogICAgfQogIH0KICByZXR1cm4ge2xhYjpsYWIsIG1lam9yOm1lam9yfTsKfQpmdW5jdGlvbiBlc3F1aW5hc0RlTWFzY2FyYShsYWIsIGlkLCB3LCBoKXsKICB2YXIgdGw9bnVsbCx0cj1udWxsLGJyPW51bGwsYmw9bnVsbCwgeCx5LHA7CiAgZm9yKHk9MDt5PGg7eSsrKXsKICAgIGZvcih4PTA7eDx3O3grKyl7CiAgICAgIHA9eSp3K3g7CiAgICAgIGlmKGxhYltwXSE9PWlkKXsgY29udGludWU7IH0KICAgICAgdmFyIHM9eCt5LCBkMj14LXk7CiAgICAgIGlmKCF0bHx8czx0bC5zKXsgdGw9e3g6eCx5OnksczpzfTsgfQogICAgICBpZighYnJ8fHM+YnIucyl7IGJyPXt4OngseTp5LHM6c307IH0KICAgICAgaWYoIXRyfHxkMj50ci5kKXsgdHI9e3g6eCx5OnksZDpkMn07IH0KICAgICAgaWYoIWJsfHxkMjxibC5kKXsgYmw9e3g6eCx5OnksZDpkMn07IH0KICAgIH0KICB9CiAgcmV0dXJuIHt0bDp0bCx0cjp0cixicjpicixibDpibH07Cn0KZnVuY3Rpb24gYXJlYVF1YWQocSl7CiAgaWYoIXF8fCFxLnRsfHwhcS50cnx8IXEuYnJ8fCFxLmJsKXsgcmV0dXJuIDA7IH0KICB2YXIgcHRzPVtxLnRsLHEudHIscS5icixxLmJsXSwgYT0wLCBpOwogIGZvcihpPTA7aTw0O2krKyl7IHZhciBwPXB0c1tpXSwgcj1wdHNbKGkrMSklNF07IGErPXAueCpyLnktci54KnAueTsgfQogIHJldHVybiBNYXRoLmFicyhhKS8yOwp9CmZ1bmN0aW9uIHF1YWRWYWxpZG8ocSwgZHcsIGRoKXsKICBpZighcXx8IXEudGx8fCFxLnRyfHwhcS5icnx8IXEuYmwpeyByZXR1cm4ge29rOmZhbHNlLCBtb3Rpdm86J2Zvcm1hJ307IH0KICB2YXIgcHRzPVtxLnRsLHEudHIscS5icixxLmJsXSwgaSwgc2lnPTA7CiAgZm9yKGk9MDtpPDQ7aSsrKXsKICAgIHZhciBhPXB0c1tpXSwgYj1wdHNbKGkrMSklNF0sIGM9cHRzWyhpKzIpJTRdOwogICAgdmFyIGNyPShiLngtYS54KSooYy55LWIueSktKGIueS1hLnkpKihjLngtYi54KTsKICAgIGlmKE1hdGguYWJzKGNyKTwwLjUpeyByZXR1cm4ge29rOmZhbHNlLCBtb3Rpdm86J2Zvcm1hJ307IH0KICAgIHZhciBzPWNyPjA/MTotMTsKICAgIGlmKHNpZz09PTApeyBzaWc9czsgfSBlbHNlIGlmKHMhPT1zaWcpeyByZXR1cm4ge29rOmZhbHNlLCBtb3Rpdm86J2Zvcm1hJ307IH0KICB9CiAgZnVuY3Rpb24gZHN0KGEsYil7IHZhciBkeD1hLngtYi54LCBkeT1hLnktYi55OyByZXR1cm4gTWF0aC5zcXJ0KGR4KmR4K2R5KmR5KTsgfQogIHZhciBhcj1kc3QocS50bCxxLnRyKSwgYWI9ZHN0KHEudHIscS5iciksIGFpPWRzdChxLmJyLHEuYmwpLCBhej1kc3QocS5ibCxxLnRsKTsKICB2YXIgbW49TWF0aC5taW4oYXIsYWIsYWksYXopOwogIGlmKG1uPE1hdGgubWF4KGR3LGRoKSowLjA5KXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidwZXF1ZW5vJ307IH0KICB2YXIgZnI9YXJlYVF1YWQocSkvKGR3KmRoKTsKICBpZihmcj4wLjk0KXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidmb3JtYSd9OyB9CiAgdmFyIGFzcD0oYXIrYWkpL01hdGgubWF4KDEsKGFiK2F6KSk7CiAgaWYoYXNwPDAuNDV8fGFzcD4yLjUpeyByZXR1cm4ge29rOmZhbHNlLCBtb3Rpdm86J2Zvcm1hJ307IH0KICBpZihmcjwwLjEwKXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidwZXF1ZW5vJywgZnJhYzpmcn07IH0KICByZXR1cm4ge29rOnRydWUsIGZyYWM6ZnIsIGFzcDphc3B9Owp9CmZ1bmN0aW9uIG5pdG9EZShsdW0sIGR3LCBkaCwgY2FqYSl7CiAgdmFyIHgwPTEseTA9MSx4MT1kdy0xLHkxPWRoLTE7CiAgaWYoY2FqYSl7IHgwPU1hdGgubWF4KDEsY2FqYS54KzEpOyB5MD1NYXRoLm1heCgxLGNhamEueSsxKTsgeDE9TWF0aC5taW4oZHctMSxjYWphLngrY2FqYS53LTEpOyB5MT1NYXRoLm1pbihkaC0xLGNhamEueStjYWphLmgtMSk7IH0KICB2YXIgcz0wLHMyPTAsaz0wLHgseTsKICBmb3IoeT15MDt5PHkxO3krKyl7CiAgICBmb3IoeD14MDt4PHgxO3grKyl7CiAgICAgIHZhciBwPXkqZHcreDsKICAgICAgdmFyIGxwPTQqbHVtW3BdLWx1bVtwLTFdLWx1bVtwKzFdLWx1bVtwLWR3XS1sdW1bcCtkd107CiAgICAgIHMrPWxwOyBzMis9bHAqbHA7IGsrKzsKICAgIH0KICB9CiAgaWYoIWspeyByZXR1cm4ge3Y6MH07IH0KICB2YXIgbT1zL2s7CiAgcmV0dXJuIHt2OihzMi9rKS1tKm19Owp9CmZ1bmN0aW9uIGZyYWNjaW9uQmxhbmNvKGx1bSwgZHcsIGRoLCBjYWphKXsKICB2YXIgeDA9MCx5MD0wLHgxPWR3LHkxPWRoLGs9MCxiPTAseCx5OwogIGlmKGNhamEpeyB4MD1NYXRoLm1heCgwLGNhamEueCk7IHkwPU1hdGgubWF4KDAsY2FqYS55KTsgeDE9TWF0aC5taW4oZHcsY2FqYS54K2NhamEudyk7IHkxPU1hdGgubWluKGRoLGNhamEueStjYWphLmgpOyB9CiAgZm9yKHk9eTA7eTx5MTt5KyspeyBmb3IoeD14MDt4PHgxO3grKyl7IGsrKzsgaWYobHVtW3kqZHcreF0+PTI0Nil7IGIrKzsgfSB9IH0KICByZXR1cm4gaz8oYi9rKTowOwp9CmZ1bmN0aW9uIG1lZGlhbmFOdW0oYSl7CiAgaWYoIWF8fCFhLmxlbmd0aCl7IHJldHVybiAwOyB9CiAgdmFyIGI9YS5zbGljZSgpLnNvcnQoZnVuY3Rpb24oeCx5KXsgcmV0dXJuIHgteTsgfSk7CiAgcmV0dXJuIGJbTWF0aC5mbG9vcihiLmxlbmd0aC8yKV07Cn0KZnVuY3Rpb24gbWVkaWFuYVF1YWQoaGlzdCl7CiAgaWYoIWhpc3R8fCFoaXN0Lmxlbmd0aCl7IHJldHVybiBudWxsOyB9CiAgdmFyIEs9Wyd0bCcsJ3RyJywnYnInLCdibCddLCByZXM9e30sIGksIGssIHhzLCB5czsKICBmb3Ioaz0wO2s8Sy5sZW5ndGg7aysrKXsKICAgIHhzPVtdOyB5cz1bXTsKICAgIGZvcihpPTA7aTxoaXN0Lmxlbmd0aDtpKyspeyBpZihoaXN0W2ldJiZoaXN0W2ldW0tba11dKXsgeHMucHVzaChoaXN0W2ldW0tba11dLngpOyB5cy5wdXNoKGhpc3RbaV1bS1trXV0ueSk7IH0gfQogICAgaWYoIXhzLmxlbmd0aCl7IHJldHVybiBudWxsOyB9CiAgICByZXNbS1trXV09e3g6bWVkaWFuYU51bSh4cyksIHk6bWVkaWFuYU51bSh5cyl9OwogIH0KICByZXR1cm4gcmVzOwp9CmZ1bmN0aW9uIHF1YWRFc3RhYmxlKGhpc3QpewogIHZhciBtZWQ9bWVkaWFuYVF1YWQoaGlzdCksIEs9Wyd0bCcsJ3RyJywnYnInLCdibCddLCBpLCBrOwogIGlmKCFtZWR8fCFoaXN0fHxoaXN0Lmxlbmd0aDw0KXsgcmV0dXJuIGZhbHNlOyB9CiB2YXIgdG9sPTAuMDIqTWF0aC5tYXgoaGlzdFswXS52d3x8NjQwLCBoaXN0WzBdLnZofHw0ODApOwogIGZvcihrPTA7azxLLmxlbmd0aDtrKyspewogICAgZm9yKGk9TWF0aC5tYXgoMCxoaXN0Lmxlbmd0aC00KTtpPGhpc3QubGVuZ3RoO2krKyl7CiAgICAgIHZhciBxPWhpc3RbaV0mJmhpc3RbaV1bS1trXV07CiAgICAgIGlmKCFxfHwhbWVkW0tba11dKXsgcmV0dXJuIGZhbHNlOyB9CiAgICAgIHZhciBkeD1xLngtbWVkW0tba11dLngsIGR5PXEueS1tZWRbS1trXV0ueTsKICAgICAgaWYoTWF0aC5zcXJ0KGR4KmR4K2R5KmR5KT50b2wpeyByZXR1cm4gZmFsc2U7IH0KICAgIH0KICB9CiAgcmV0dXJuIHRydWU7Cn0KZnVuY3Rpb24gZGV0ZWN0YXJEb2NRdWFkKHYpewogIHRyeXsKICAgIHZhciBEPXp5RGV0KCk7CiAgICB2YXIgdnc9di52aWRlb1dpZHRofHwwLCB2aD12LnZpZGVvSGVpZ2h0fHwwOwogICAgaWYoIXZ3fHwhdmgpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIGR3PTE2MCwgZGg9TWF0aC5yb3VuZChkdyp2aC92dyk7CiAgICBpZihkaDw4KXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciBjPUQuY3ZROyBpZighYyl7IGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7IEQuY3ZRPWM7IH0KICAgIGlmKGMud2lkdGghPT1kd3x8Yy5oZWlnaHQhPT1kaCl7IGMud2lkdGg9ZHc7IGMuaGVpZ2h0PWRoOyB9CiAgICB2YXIgZz1jLmdldENvbnRleHQoJzJkJyk7IGlmKCFnKXsgcmV0dXJuIG51bGw7IH0KICAgIGcuZHJhd0ltYWdlKHYsMCwwLGR3LGRoKTsKICAgIHZhciBkPWcuZ2V0SW1hZ2VEYXRhKDAsMCxkdyxkaCkuZGF0YSwgbj1kdypkaCwgaSwgeCwgeTsKICAgIHZhciBsdW09bmV3IFVpbnQ4QXJyYXkobiksIHN1bT0wOwogICAgZm9yKGk9MDtpPG47aSsrKXsgbHVtW2ldPShkW2kqNF0qMytkW2kqNCsxXSo0K2RbaSo0KzJdKT4+Mzsgc3VtKz1sdW1baV07IH0KICAgIHZhciBsdXo9c3VtL247CiAgICAvKiBOVUVWTyB2MTQ6IG1hc2NhcmEgYW50aS10ZWxhIGRlIGNvbG9yLiBFbiBncmlzLCB1bmEgdGVsYSByb3NhL3JvamEKICAgICAgIGNsYXJhIHNlIHZlIGNhc2kgaWd1YWwgcXVlIGxhIHRhcmpldGEgeSBlbCB1bWJyYWwgZGUgT3RzdSBubyBzZXBhcmE6CiAgICAgICBsYSBndWlhIG5vIGFnYXJyYSBsYXMgNCBlc3F1aW5hcy4gTGEgVEFSSkVUQSBlcyBjbGFyYSB5IFBPQ08gc2F0dXJhZGE7CiAgICAgICBsYSB0ZWxhIGRlIGNvbG9yIGVzIE1VWSBzYXR1cmFkYS4gUHJ1ZWJvIHByaW1lcm8gY29uIGVzYSBtYXNjYXJhIHkgc2kKICAgICAgIG5vIGRhIHVuIGN1YWRyaWxhdGVybyB2YWxpZG8gY2FpZ28gYWwgdW1icmFsIGRlIE90c3UgKGZvbmRvIG9zY3VybykuICovCiAgICBmdW5jdGlvbiByZXN1bHRhZG9EZU1hc2NhcmEobWFza0Fycil7CiAgICAgIHZhciB0b3QyPTAsIGkyOwogICAgICBmb3IoaTI9MDtpMjxuO2kyKyspeyBpZihtYXNrQXJyW2kyXSl7IHRvdDIrKzsgfSB9CiAgICAgIGlmKHRvdDI8biowLjAzfHx0b3QyPm4qMC45NjUpeyByZXR1cm4gbnVsbDsgfQogICAgICB2YXIgY2MyPWV0aXF1ZXRhQ29tcG9uZW50ZXMobWFza0FycixkdyxkaCk7CiAgICAgIGlmKCFjYzIubWVqb3IuaWR8fGNjMi5tZWpvci50YW08biowLjA0KXsgcmV0dXJuIG51bGw7IH0KICAgICAgdmFyIHEyPWVzcXVpbmFzRGVNYXNjYXJhKGNjMi5sYWIsY2MyLm1lam9yLmlkLGR3LGRoKTsKICAgICAgaWYoIXEyLnRsfHwhcTIudHJ8fCFxMi5icnx8IXEyLmJsKXsgcmV0dXJuIG51bGw7IH0KICAgICAgdmFyIHZhbDI9cXVhZFZhbGlkbyhxMixkdyxkaCk7CiAgICAgIGlmKCF2YWwyLm9rKXsgcmV0dXJuIG51bGw7IH0KICAgICAgdmFyIHhhPU1hdGgubWF4KDAsTWF0aC5taW4ocTIudGwueCxxMi5ibC54KSksIHhiPU1hdGgubWluKGR3LE1hdGgubWF4KHEyLnRyLngscTIuYnIueCkpOwogICAgICB2YXIgeWE9TWF0aC5tYXgoMCxNYXRoLm1pbihxMi50bC55LHEyLnRyLnkpKSwgeWI9TWF0aC5taW4oZGgsTWF0aC5tYXgocTIuYmwueSxxMi5ici55KSk7CiAgICAgIHZhciBjYWphMj17eDp4YSx5OnlhLHc6TWF0aC5tYXgoMSx4Yi14YSksaDpNYXRoLm1heCgxLHliLXlhKX07CiAgICAgIHZhciBudDI9bml0b0RlKGx1bSxkdyxkaCxjYWphMik7CiAgICAgIHZhciBibGEyPWZyYWNjaW9uQmxhbmNvKGx1bSxkdyxkaCxjYWphMik7CiAgICAgIHZhciBzeDI9dncvZHcsIHN5Mj12aC9kaDsKICAgICAgcmV0dXJuIHt0bDp7eDpxMi50bC54KnN4Mix5OnEyLnRsLnkqc3kyfSwgdHI6e3g6cTIudHIueCpzeDIseTpxMi50ci55KnN5Mn0sIGJyOnt4OnEyLmJyLngqc3gyLHk6cTIuYnIueSpzeTJ9LCBibDp7eDpxMi5ibC54KnN4Mix5OnEyLmJsLnkqc3kyfSwgbHV6Omx1eiwgbml0bzpudDIudiwgYmxhbmNvOmJsYTIsIHZ3OnZ3LCB2aDp2aCwgZnJhYzp2YWwyLmZyYWN9OwogICAgfQogICAgdmFyIG1hc2tTPW5ldyBVaW50OEFycmF5KG4pLCB0b3RTPTA7CiAgICBmb3IoaT0wO2k8bjtpKyspewogICAgICB2YXIgcjQ9ZFtpKjRdLCBnND1kW2kqNCsxXSwgYjQ9ZFtpKjQrMl07CiAgICAgIHZhciBteD0ocjQ+ZzQpPyhyND5iND9yNDpiNCk6KGc0PmI0P2c0OmI0KSwgbW49KHI0PGc0KT8ocjQ8YjQ/cjQ6YjQpOihnNDxiND9nNDpiNCk7CiAgICAgIGlmKChteC1tbik8PTcwJiZsdW1baV0+PTEzMCl7IG1hc2tTW2ldPTE7IHRvdFMrKzsgfQogICAgfQogICAgaWYodG90Uz49biowLjAzKXsKICAgICAgdmFyIHJTPXJlc3VsdGFkb0RlTWFzY2FyYShtYXNrUyk7CiAgICAgIGlmKHJTKXsgcmV0dXJuIHJTOyB9CiAgICB9CiAgICB2YXIgbGI9bmV3IFVpbnQ4QXJyYXkobik7CiAgICBmb3IoeT0xO3k8ZGgtMTt5KyspeyBmb3IoeD0xO3g8ZHctMTt4KyspeyB2YXIgcHA9eSpkdyt4OyBsYltwcF09KGx1bVtwcF0qNCtsdW1bcHAtMV0rbHVtW3BwKzFdK2x1bVtwcC1kd10rbHVtW3BwK2R3XSk+PjM7IH0gfQogICAgdmFyIGhpc3Q9bmV3IEludDMyQXJyYXkoMjU2KTsgZm9yKGk9MDtpPG47aSsrKXsgaGlzdFtsYltpXV0rKzsgfQogICAgdmFyIHRocj1vdHN1VW1icmFsKGhpc3Qsbik7CiAgICB2YXIgbWFzaz1uZXcgVWludDhBcnJheShuKSwgdG90PTA7CiAgICBmb3IoaT0wO2k8bjtpKyspeyB2YXIgdjE9KGxiW2ldPnRocik/MTowOyBtYXNrW2ldPXYxOyB0b3QrPXYxOyB9CiAgICBpZih0b3Q8biowLjAzKXsgcmV0dXJuIG51bGw7IH0KICAgIGlmKHRvdD5uKjAuOTY1KXsKICAgICAgdmFyIG50MD1uaXRvRGUobHVtLGR3LGRoLG51bGwpOwogICAgICByZXR1cm4ge2xsZW5vOnRydWUsIGx1ejpsdXosIG5pdG86bnQwLnYsIGJsYW5jbzpmcmFjY2lvbkJsYW5jbyhsdW0sZHcsZGgsbnVsbCksIHZ3OnZ3LCB2aDp2aH07CiAgICB9CiAgICB2YXIgY2M9ZXRpcXVldGFDb21wb25lbnRlcyhtYXNrLGR3LGRoKTsKICAgIGlmKCFjYy5tZWpvci5pZHx8Y2MubWVqb3IudGFtPG4qMC4wNCl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgcT1lc3F1aW5hc0RlTWFzY2FyYShjYy5sYWIsY2MubWVqb3IuaWQsZHcsZGgpOwogICAgaWYoIXEudGx8fCFxLnRyfHwhcS5icnx8IXEuYmwpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIHZhbD1xdWFkVmFsaWRvKHEsZHcsZGgpOwogICAgdmFyIHgwPU1hdGgubWF4KDAsTWF0aC5taW4ocS50bC54LHEuYmwueCkpLCB4MT1NYXRoLm1pbihkdyxNYXRoLm1heChxLnRyLngscS5ici54KSk7CiAgICB2YXIgeTA9TWF0aC5tYXgoMCxNYXRoLm1pbihxLnRsLnkscS50ci55KSksIHkxPU1hdGgubWluKGRoLE1hdGgubWF4KHEuYmwueSxxLmJyLnkpKTsKICAgIHZhciBjYWphPXt4OngwLHk6eTAsdzpNYXRoLm1heCgxLHgxLXgwKSxoOk1hdGgubWF4KDEseTEteTApfTsKICAgIHZhciBudD1uaXRvRGUobHVtLGR3LGRoLGNhamEpOwogICAgdmFyIGJsYT1mcmFjY2lvbkJsYW5jbyhsdW0sZHcsZGgsY2FqYSk7CiAgICB2YXIgc3g9dncvZHcsIHN5PXZoL2RoOwogICAgZnVuY3Rpb24gZXNjKHApeyByZXR1cm4ge3g6cC54KnN4LCB5OnAueSpzeX07IH0KICAgIHZhciByZXM9e3RsOmVzYyhxLnRsKSwgdHI6ZXNjKHEudHIpLCBicjplc2MocS5iciksIGJsOmVzYyhxLmJsKSwgbHV6Omx1eiwgbml0bzpudC52LCBibGFuY286YmxhLCB2dzp2dywgdmg6dmh9OwogICAgaWYoIXZhbC5vayl7IHJlcy5kZXNjYXJ0YWRvPXZhbC5tb3Rpdm87IHJldHVybiByZXM7IH0KICAgIHJlcy5mcmFjPXZhbC5mcmFjOwogICAgcmV0dXJuIHJlczsKICB9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9Cn0KZnVuY3Rpb24gZGV0ZWN0YXJEb2NCb3godil7CiAgdHJ5ewogICAgdmFyIEQ9enlEZXQoKTsKICAgIHZhciBjPUQuY3ZEb2M7CiAgICBpZighYyl7IGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7IEQuY3ZEb2M9YzsgfQogICAgdmFyIGR3PTEyOCwgZGg9TWF0aC5tYXgoOCxNYXRoLnJvdW5kKDEyOCooKHYudmlkZW9IZWlnaHR8fDMpLygodi52aWRlb1dpZHRofHw0KSoxLjApKSkpOwogICAgaWYoYy53aWR0aCE9PWR3fHxjLmhlaWdodCE9PWRoKXsgYy53aWR0aD1kdzsgYy5oZWlnaHQ9ZGg7IH0KICAgIHZhciBnPWMuZ2V0Q29udGV4dCgnMmQnKTsgaWYoIWcpeyByZXR1cm4gbnVsbDsgfQogICAgZy5kcmF3SW1hZ2UodiwwLDAsZHcsZGgpOwogICAgdmFyIGQ9Zy5nZXRJbWFnZURhdGEoMCwwLGR3LGRoKS5kYXRhLCBuPWR3KmRoOwogICAgdmFyIGhpc3Q9bmV3IEludDMyQXJyYXkoMjU2KSwgbHVtPW5ldyBVaW50OEFycmF5KG4pLCBpLHgseTsKICAgIGZvcihpPTA7aTxuO2krKyl7IHZhciByPWRbaSo0XSwgZ2c9ZFtpKjQrMV0sIGI9ZFtpKjQrMl07IGx1bVtpXT0ociozK2dnKjQrYik+PjM7IGhpc3RbbHVtW2ldXSsrOyB9CiAgICB2YXIgdGhyPW90c3VVbWJyYWwoaGlzdCxuKTsKICAgIHZhciBmaWxhcz1uZXcgSW50MzJBcnJheShkaCksIGNvbHM9bmV3IEludDMyQXJyYXkoZHcpLCB0b3Q9MDsKICAgIGZvcih5PTA7eTxkaDt5KyspeyBmb3IoeD0wO3g8ZHc7eCsrKXsgaWYobHVtW3kqZHcreF0+dGhyKXsgZmlsYXNbeV0rKzsgY29sc1t4XSsrOyB0b3QrKzsgfSB9IH0KICAgIGlmKHRvdDxuKjAuMDR8fHRvdD5uKjAuOTg1KXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciByZj1yYW5nb1Byb3llY2Npb24oZmlsYXMsZGgsTWF0aC5tYXgoMixNYXRoLnJvdW5kKGR3KjAuMTgpKSk7CiAgICB2YXIgcmM9cmFuZ29Qcm95ZWNjaW9uKGNvbHMsZHcsTWF0aC5tYXgoMixNYXRoLnJvdW5kKGRoKjAuMTgpKSk7CiAgICBpZighcmZ8fCFyYyl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgc3g9KHYudmlkZW9XaWR0aHx8NjQwKS9kdywgc3k9KHYudmlkZW9IZWlnaHR8fDQ4MCkvZGg7CiAgICB2YXIgYng9cmNbMF0qc3gsIGJ5PXJmWzBdKnN5LCBidz0ocmNbMV0rMS1yY1swXSkqc3gsIGJoPShyZlsxXSsxLXJmWzBdKSpzeTsKICAgIGlmKGJ3PDh8fGJoPDgpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIHN1bWE9MCwgaTI7CiAgICBmb3IoaTI9MDtpMjxuO2kyKyspeyBzdW1hKz1sdW1baTJdOyB9CiAgICB2YXIgbHV6PXN1bWEvbjsKICAgIHZhciBzdW1WPTAsIHN1bVYyPTAsIG4yPTAsIHgyLCB5MjsKICAgIGZvcih5Mj0xO3kyPGRoLTE7eTIrKyl7CiAgICAgIGZvcih4Mj0xO3gyPGR3LTE7eDIrKyl7CiAgICAgICAgdmFyIGlpPXkyKmR3K3gyOwogICAgICAgIHZhciBsYXA9NCpsdW1baWldLWx1bVtpaS0xXS1sdW1baWkrMV0tbHVtW2lpLWR3XS1sdW1baWkrZHddOwogICAgICAgIHN1bVYrPWxhcDsgc3VtVjIrPWxhcCpsYXA7IG4yKys7CiAgICAgIH0KICAgIH0KICAgIHZhciBtZWRpYT1zdW1WL01hdGgubWF4KDEsbjIpOwogICAgdmFyIHZhckw9KHN1bVYyL01hdGgubWF4KDEsbjIpKS1tZWRpYSptZWRpYTsKICAgIHJldHVybiB7eDpieCwgeTpieSwgdzpidywgaDpiaCwgbHV6Omx1eiwgbml0bzoodmFyTD49NDApLCBmb2NvOk1hdGgucm91bmQodmFyTCl9OwogIH1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0KfQpmdW5jdGlvbiBjZW50cm9EZShwdW50b3MpewogIHZhciBzeD0wLCBzeT0wLCBpOwogIGZvcihpPTA7aTxwdW50b3MubGVuZ3RoO2krKyl7IHN4Kz1wdW50b3NbaV0ueDsgc3krPXB1bnRvc1tpXS55OyB9CiAgcmV0dXJuIHt4OnN4L3B1bnRvcy5sZW5ndGgsIHk6c3kvcHVudG9zLmxlbmd0aH07Cn0KZnVuY3Rpb24gZWFyRGUocHVudG9zKXsKICBpZighcHVudG9zfHxwdW50b3MubGVuZ3RoPDYpeyByZXR1cm4gMTsgfQogIGZ1bmN0aW9uIGQyKGEsYil7IHZhciBkeD1hLngtYi54LCBkeT1hLnktYi55OyByZXR1cm4gTWF0aC5zcXJ0KGR4KmR4K2R5KmR5KTsgfQogIHZhciBoPWQyKHB1bnRvc1swXSxwdW50b3NbM10pOwogIGlmKGg8MWUtNil7IHJldHVybiAxOyB9CiAgcmV0dXJuIChkMihwdW50b3NbMV0scHVudG9zWzVdKStkMihwdW50b3NbMl0scHVudG9zWzRdKSkvKDIqaCk7Cn0KZnVuY3Rpb24gZXZhbHVhQ2FyYShpbmZvKXsKICB2YXIgcj17dmlzdGE6dHJ1ZSwgb2s6ZmFsc2UsIHRhbTonYmllbicsIG1vdGl2bzonJywgY29kOicnfTsKICBpZihpbmZvLmx1ejw1NSl7IHIuY29kPSdsdXonOyByLm1vdGl2bz0nUE9DQSBMVVo6IHBvbiB0dSBjYXJhIGhhY2lhIGxhIGx1eiBvIGVuY2llbmRlIHVuYSBsYW1wYXJhLic7IHJldHVybiByOyB9CiAgaWYoaW5mby5uaXRvPDE4KXsgci5jb2Q9J25pdG8nOyByLm1vdGl2bz0nTm8gc2UgdmUgTklUSURPOiBzb3N0XHUwMEU5biBlbCB0ZWxlZm9ubyBmaXJtZSB5IGVzcGVyYSBlbCBlbmZvcXVlLic7IHJldHVybiByOyB9CiAgaWYoaW5mby50YW08MC4zOCl7IHIudGFtPSdsZWpvcyc7IHIuY29kPSdsZWpvcyc7IHIubW90aXZvPSdBQ0VSQ0FURTogdHUgY2FyYSBzZSB2ZSBtdXkgcGVxdWVcdTAwRjFhIGVuIGVsIG92YWxvLic7IHJldHVybiByOyB9CiAgaWYoaW5mby50YW0+MC44Nil7IHIudGFtPSdjZXJjYSc7IHIuY29kPSdjZXJjYSc7IHIubW90aXZvPSdBTEVKQVRFIHVuIHBvY28gcGFyYSBxdWUgdHUgY2FyYSBxdWVwYSBlbnRlcmEgZW4gZWwgb3ZhbG8uJzsgcmV0dXJuIHI7IH0KICBpZihNYXRoLmFicyhpbmZvLmZ4LTAuNSk+MC4xM3x8aW5mby5meTwwLjM2fHxpbmZvLmZ5PjAuNjgpeyByLmNvZD0nZnVlcmEnOyByLm1vdGl2bz0nQ2VudHJhIHR1IGNhcmEgZGVudHJvIGRlbCBPVkFMTywgbWlyYW5kbyBhIGxhIGNhbWFyYS4nOyByZXR1cm4gcjsgfQogIGlmKE1hdGguYWJzKGluZm8ucm9sbCk+MTQpeyByLmNvZD0ncm9sbCc7IHIubW90aXZvPSdFbmRlcmV6YSBsYSBjYWJlemE6IG5vIGxhIGluY2xpbmVzIGEgbG9zIGxhZG9zLic7IHJldHVybiByOyB9CiAgaWYoTWF0aC5hYnMoaW5mby55YXcpPjAuMjApeyByLmNvZD0neWF3Jzsgci5tb3Rpdm89J01pcmEgREUgRlJFTlRFIGEgbGEgY2FtYXJhLCBubyBkZSBsYWRvLic7IHJldHVybiByOyB9CiAgaWYoaW5mby5vam9zPDAuMTMpeyByLmNvZD0nb2pvcyc7IHIubW90aXZvPSdBYnJlIGxvcyBvam9zIHkgbWlyYSBmaWpvIGEgbGEgY2FtYXJhLic7IHJldHVybiByOyB9CiAgci5vaz10cnVlOyByLm1vdGl2bz0nUGVyZmVjdG86IHNvc3RcdTAwRTluIGxhIHBvc2ljaW9uLi4uJzsKICByZXR1cm4gcjsKfQpmdW5jdGlvbiBuaXRvRGVSZ2JhKGRhdG9zLCBkdywgZGgsIGNhamEpewogIHZhciB4MD1NYXRoLm1heCgxLGNhamEueCsxKSwgeTA9TWF0aC5tYXgoMSxjYWphLnkrMSk7CiAgdmFyIHgxPU1hdGgubWluKGR3LTEsY2FqYS54K2NhamEudy0xKSwgeTE9TWF0aC5taW4oZGgtMSxjYWphLnkrY2FqYS5oLTEpOwogIHZhciBzPTAsczI9MCxrPTAseCx5OwogIGZvcih5PXkwO3k8eTE7eSsrKXsKICAgIGZvcih4PXgwO3g8eDE7eCsrKXsKICAgICAgdmFyIHA9eSpkdyt4OwogICAgICB2YXIgbDE9KGRhdG9zW3AqNF0qMytkYXRvc1twKjQrMV0qNCtkYXRvc1twKjQrMl0pPj4zOwogICAgICB2YXIgbDI9KGRhdG9zWyhwLTEpKjRdKjMrZGF0b3NbKHAtMSkqNCsxXSo0K2RhdG9zWyhwLTEpKjQrMl0pPj4zOwogICAgICB2YXIgbDM9KGRhdG9zWyhwKzEpKjRdKjMrZGF0b3NbKHArMSkqNCsxXSo0K2RhdG9zWyhwKzEpKjQrMl0pPj4zOwogICAgICB2YXIgbDQ9KGRhdG9zWyhwLWR3KSo0XSozK2RhdG9zWyhwLWR3KSo0KzFdKjQrZGF0b3NbKHAtZHcpKjQrMl0pPj4zOwogICAgICB2YXIgbDU9KGRhdG9zWyhwK2R3KSo0XSozK2RhdG9zWyhwK2R3KSo0KzFdKjQrZGF0b3NbKHArZHcpKjQrMl0pPj4zOwogICAgICB2YXIgbHA9NCpsMS1sMi1sMy1sNC1sNTsKICAgICAgcys9bHA7IHMyKz1scCpscDsgaysrOwogICAgfQogIH0KICBpZighayl7IHJldHVybiAwOyB9CiAgdmFyIG09cy9rOwogIHJldHVybiAoczIvayktbSptOwp9CmZ1bmN0aW9uIGJ1c2NhckNhcmFWaXZhKHYsIGNiKXsKICB0cnl7CiAgICBpZighKFcuZmFjZWFwaSYmVy5mYWNlYXBpLm5ldHMmJlcuZmFjZWFwaS5uZXRzLnRpbnlGYWNlRGV0ZWN0b3ImJlcuZmFjZWFwaS5UaW55RmFjZURldGVjdG9yT3B0aW9ucykpeyBjYihudWxsKTsgcmV0dXJuOyB9CiAgICB2YXIgRD16eURldCgpOwogICAgdmFyIHZ3PXYudmlkZW9XaWR0aHx8NjQwLCB2aD12LnZpZGVvSGVpZ2h0fHw0ODA7CiAgICB2YXIgZHc9MjI0LCBkaD1NYXRoLm1heCg4MCxNYXRoLnJvdW5kKGR3KnZoL3Z3KSk7CiAgICB2YXIgYz1ELmN2Q2FyYTsKICAgIGlmKCFjKXsgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsgRC5jdkNhcmE9YzsgfQogICAgaWYoYy53aWR0aCE9PWR3fHxjLmhlaWdodCE9PWRoKXsgYy53aWR0aD1kdzsgYy5oZWlnaHQ9ZGg7IH0KICAgIHZhciBnPWMuZ2V0Q29udGV4dCgnMmQnKTsgaWYoIWcpeyBjYihudWxsKTsgcmV0dXJuOyB9CiAgICBnLmRyYXdJbWFnZSh2LDAsMCxkdyxkaCk7CiAgICB2YXIgZGF0b3M9bnVsbDsKICAgIHRyeXsgZGF0b3M9Zy5nZXRJbWFnZURhdGEoMCwwLGR3LGRoKS5kYXRhOyB9Y2F0Y2goZSl7IGRhdG9zPW51bGw7IH0KICAgIHZhciBvcHQ9bmV3IFcuZmFjZWFwaS5UaW55RmFjZURldGVjdG9yT3B0aW9ucyh7aW5wdXRTaXplOjIyNCwgc2NvcmVUaHJlc2hvbGQ6MC40NX0pOwogICAgVy5mYWNlYXBpLmRldGVjdFNpbmdsZUZhY2UoYyxvcHQpLndpdGhGYWNlTGFuZG1hcmtzKCkud2l0aEZhY2VEZXNjcmlwdG9yKCkudGhlbihmdW5jdGlvbihyKXsKICAgICAgdHJ5ewogICAgICAgIGlmKCFyfHwhci5kZXRlY3Rpb24peyBjYih7dmlzdGE6ZmFsc2UsIG9rOmZhbHNlLCB0OkRhdGUubm93KCl9KTsgcmV0dXJuOyB9CiAgICAgICAgdmFyIGI9ci5kZXRlY3Rpb24uYm94OwogICAgICAgIHZhciBmeD0oYi54K2Iud2lkdGgvMikvZHcsIGZ5PShiLnkrYi5oZWlnaHQvMikvZGg7CiAgICAgICAgdmFyIHRhbT1iLmhlaWdodC9kaDsKICAgICAgICB2YXIgcm9sbD0wLCB5YXc9MCwgb2pvcz0xOwogICAgICAgIGlmKHIubGFuZG1hcmtzKXsKICAgICAgICAgIHZhciBMPXIubGFuZG1hcmtzLmdldExlZnRFeWUoKSwgUj1yLmxhbmRtYXJrcy5nZXRSaWdodEV5ZSgpLCBOPXIubGFuZG1hcmtzLmdldE5vc2UoKTsKICAgICAgICAgIGlmKEwmJlImJkwubGVuZ3RoPj00JiZSLmxlbmd0aD49NCl7CiAgICAgICAgICAgIHZhciBsYz1jZW50cm9EZShMKSwgcmM9Y2VudHJvRGUoUik7CiAgICAgICAgICAgIHJvbGw9TWF0aC5hdGFuMihyYy55LWxjLnksIHJjLngtbGMueCkqMTgwL01hdGguUEk7CiAgICAgICAgICAgIHZhciBteD0obGMueCtyYy54KS8yOwogICAgICAgICAgICBpZihOJiZOLmxlbmd0aD40KXsgeWF3PShOWzRdLngtbXgpL01hdGgubWF4KDEsYi53aWR0aCk7IH0KICAgICAgICAgICAgb2pvcz1NYXRoLm1pbihlYXJEZShMKSwgZWFyRGUoUikpOwogICAgICAgICAgfQogICAgICAgIH0KICAgICAgICB2YXIgY2FqYT17eDpNYXRoLnJvdW5kKGIueCp2dy9kdyksIHk6TWF0aC5yb3VuZChiLnkqdmgvZGgpLCB3Ok1hdGgucm91bmQoYi53aWR0aCp2dy9kdyksIGg6TWF0aC5yb3VuZChiLmhlaWdodCp2aC9kaCl9OwogICAgICAgIGNhamEueD1NYXRoLm1heCgwLHZ3LWNhamEueC1jYWphLncpOwogICAgICAgIHZhciBsdXo9MCwgbml0bz0wOwogICAgICAgIGlmKGRhdG9zKXsKICAgICAgICAgIHZhciByeDA9TWF0aC5tYXgoMCxNYXRoLnJvdW5kKGIueCkpLCByeTA9TWF0aC5tYXgoMCxNYXRoLnJvdW5kKGIueSkpOwogICAgICAgICAgdmFyIHJ4MT1NYXRoLm1pbihkdyxNYXRoLnJvdW5kKGIueCtiLndpZHRoKSksIHJ5MT1NYXRoLm1pbihkaCxNYXRoLnJvdW5kKGIueStiLmhlaWdodCkpOwogICAgICAgICAgdmFyIHM9MCxrPTAseCx5OwogICAgICAgICAgZm9yKHk9cnkwO3k8cnkxO3krKyl7IGZvcih4PXJ4MDt4PHJ4MTt4KyspeyBzKz0oZGF0b3NbKHkqZHcreCkqNF0qMytkYXRvc1soeSpkdyt4KSo0KzFdKjQrZGF0b3NbKHkqZHcreCkqNCsyXSk+PjM7IGsrKzsgfSB9CiAgICAgICAgICBsdXo9az8ocy9rKTowOwogICAgICAgICAgbml0bz0ocngxPnJ4MCsyJiZyeTE+cnkwKzIpP25pdG9EZVJnYmEoZGF0b3MsZHcsZGgse3g6cngwLHk6cnkwLHc6cngxLXJ4MCxoOnJ5MS1yeTB9KTowOwogICAgICAgIH0KICAgICAgICB2YXIgZGU9ZXZhbHVhQ2FyYSh7Zng6ZngsZnk6ZnksdGFtOnRhbSxyb2xsOnJvbGwseWF3Onlhdyxvam9zOm9qb3MsbHV6Omx1eixuaXRvOm5pdG99KTsKICAgICAgICBjYih7dmlzdGE6dHJ1ZSwgb2s6ZGUub2ssIGNvZDpkZS5jb2QsIG1vdGl2bzpkZS5tb3Rpdm8sIHRhbTpkZS50YW0sIGZ4OmZ4LCBmeTpmeSwgY2FqYTpjYWphLCBsdXo6bHV6LCBuaXRvOm5pdG8sIG9qb3M6b2pvcywgcm9sbDpyb2xsLCB5YXc6eWF3LCB0OkRhdGUubm93KCl9KTsKICAgICAgfWNhdGNoKGUpeyBjYihudWxsKTsgfQogICAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgY2IobnVsbCk7IH0pOwogIH1jYXRjaChlKXsgY2IobnVsbCk7IH0KfQpmdW5jdGlvbiBlbm1hcmNhclZlcmRlKHBzSWQsIHYpewogIC8qIHYxMTogY29udG9ybm8gUE9MSUdPTkFMIHJlYWwgcXVlIHNpZ3VlIGFsIGRvY3VtZW50byAocHMgMiB5IDMpIHkgT1ZBTE8gY29uIG1vdG9yIGZhY2lhbCAocHMgNCkgKi8KICB0cnl7CiAgICB2YXIgT1Y9eycyJzonb3ZGJywnMyc6J292QScsJzQnOidvdlMnfTsKICAgIHZhciBvdklkPU9WW3BzSWRdOwogICAgaWYoIW92SWQpeyByZXR1cm47IH0KICAgIHZhciBzdElkPShwc0lkPT09JzInKT8nc3RGJzooKHBzSWQ9PT0nMycpPydzdEEnOidzdFYnKTsKICAgIHZhciBEPXp5RGV0KCk7CiAgICB2YXIgc3Q9RFtwc0lkXTsKICAgIGlmKCFzdCl7IHN0PURbcHNJZF09e2NhamE6bnVsbCwgdDotMWU5LCBlc3RhZG86JycsIGl2Om51bGx9OyB9CiAgICBzdC50MD1EYXRlLm5vdygpOyBzdC5jYWphPW51bGw7IHN0LmVzdGFkbz0nJzsgc3QuYXV0bz0wOyBzdC5hdXRvSGVjaG89ZmFsc2U7IHN0LmNkPTA7IHN0Lmhpc3Q9W107CiAgICB2YXIgcGludGFyRG9jPWZ1bmN0aW9uKGNhamEsIGVzdGFkbyl7CiAgICAgIHRyeXsKICAgICAgICB2YXIgb3Y9JChvdklkKTsgaWYoIW92KXsgcmV0dXJuOyB9CiAgICAgICAgdmFyIHZ3PSh2JiZ2LnZpZGVvV2lkdGgpfHwwLCB2aD0odiYmdi52aWRlb0hlaWdodCl8fDA7CiAgICAgICAgaWYoIXZ3fHwhdmgpeyByZXR1cm47IH0KICAgICAgICBpZihvdi53aWR0aCE9PXZ3fHxvdi5oZWlnaHQhPT12aCl7IG92LndpZHRoPXZ3OyBvdi5oZWlnaHQ9dmg7IH0KICAgICAgICB2YXIgZz1vdi5nZXRDb250ZXh0KCcyZCcpOyBpZighZyl7IHJldHVybjsgfQogICAgICAgIGcuY2xlYXJSZWN0KDAsMCx2dyx2aCk7CiAgICAgICAgdmFyIHgseSx3LGg7CiAgICAgICAgaWYoIWNhamEpeyB4PU1hdGgucm91bmQodncqMC4wNyk7IHk9TWF0aC5yb3VuZCh2aCowLjA5KTsgdz12dy14KjI7IGg9dmgteSoyOyB9CiAgICAgICAgZWxzZXsgeD1jYWphLng7IHk9Y2FqYS55OyB3PWNhamEudzsgaD1jYWphLmg7IH0KICAgICAgICBpZih3PDEwfHxoPDEwKXsgcmV0dXJuOyB9CiAgICAgICAgdmFyIGNvbD0oZXN0YWRvPT09J29rJyk/JyMzZmI5NTAnOigoZXN0YWRvPT09J21hbCcpPycjYzAzOTJiJzonI2UzYjM0MScpOwogICAgICAgIGcuc3Ryb2tlU3R5bGU9Y29sOyBnLmxpbmVXaWR0aD01OwogICAgICAgIHZhciBMPU1hdGgucm91bmQoTWF0aC5taW4odyxoKSooY2FqYT8wLjE2OjAuMTQpKTsKICAgICAgICBnLmJlZ2luUGF0aCgpOwogICAgICAgIGcubW92ZVRvKHgseStMKTsgZy5saW5lVG8oeCx5KTsgZy5saW5lVG8oeCtMLHkpOwogICAgICAgIGcubW92ZVRvKHgrdy1MLHkpOyBnLmxpbmVUbyh4K3cseSk7IGcubGluZVRvKHgrdyx5K0wpOwogICAgICAgIGcubW92ZVRvKHgrdyx5K2gtTCk7IGcubGluZVRvKHgrdyx5K2gpOyBnLmxpbmVUbyh4K3ctTCx5K2gpOwogICAgICAgIGcubW92ZVRvKHgrTCx5K2gpOyBnLmxpbmVUbyh4LHkraCk7IGcubGluZVRvKHgseStoLUwpOwogICAgICAgIGcuc3Ryb2tlKCk7CiAgICAgICAgZy5zYXZlKCk7CiAgICAgICAgZy5nbG9iYWxBbHBoYT1jYWphPzAuNDU6MC4yMDsKICAgICAgICBnLmxpbmVXaWR0aD0xLjY7IGcuc3Ryb2tlUmVjdCh4LHksdyxoKTsKICAgICAgICBnLnJlc3RvcmUoKTsKICAgICAgfWNhdGNoKGUpe30KICAgIH07CiAgICB2YXIgcGludGFyUXVhZD1mdW5jdGlvbihxdWFkLCBlc3RhZG8sIG51bWVybyl7CiAgICAgIHRyeXsKICAgICAgICB2YXIgb3Y9JChvdklkKTsgaWYoIW92KXsgcmV0dXJuOyB9CiAgICAgICAgdmFyIHZ3PSh2JiZ2LnZpZGVvV2lkdGgpfHwwLCB2aD0odiYmdi52aWRlb0hlaWdodCl8fDA7CiAgICAgICAgaWYoIXZ3fHwhdmgpeyByZXR1cm47IH0KICAgICAgICBpZihvdi53aWR0aCE9PXZ3fHxvdi5oZWlnaHQhPT12aCl7IG92LndpZHRoPXZ3OyBvdi5oZWlnaHQ9dmg7IH0KICAgICAgICB2YXIgZz1vdi5nZXRDb250ZXh0KCcyZCcpOyBpZighZyl7IHJldHVybjsgfQogICAgICAgIGcuY2xlYXJSZWN0KDAsMCx2dyx2aCk7CiAgICAgICAgaWYocXVhZCYmcXVhZC50bCYmcXVhZC50ciYmcXVhZC5iciYmcXVhZC5ibCl7CiAgICAgICAgICB2YXIgY29sPShlc3RhZG89PT0nb2snKT8nIzNmYjk1MCc6KChlc3RhZG89PT0nbWFsJyk/JyNlNjdlMjInOicjZTNiMzQxJyk7CiAgICAgICAgICB0cnl7CiAgICAgICAgICAgIGcuZmlsbFN0eWxlPSdyZ2JhKDAsMCwwLDAuNDUpJzsKICAgICAgICAgICAgZy5iZWdpblBhdGgoKTsKICAgICAgICAgICAgZy5yZWN0KDAsMCx2dyx2aCk7CiAgICAgICAgICAgIGcubW92ZVRvKHF1YWQudGwueCxxdWFkLnRsLnkpOyBnLmxpbmVUbyhxdWFkLnRyLngscXVhZC50ci55KTsgZy5saW5lVG8ocXVhZC5ici54LHF1YWQuYnIueSk7IGcubGluZVRvKHF1YWQuYmwueCxxdWFkLmJsLnkpOyBnLmNsb3NlUGF0aCgpOwogICAgICAgICAgICBnLmZpbGwoJ2V2ZW5vZGQnKTsKICAgICAgICAgIH1jYXRjaChlRil7IGcuZmlsbFN0eWxlPSdyZ2JhKDAsMCwwLDAuMjIpJzsgZy5maWxsUmVjdCgwLDAsdncsdmgpOyB9CiAgICAgICAgICBnLnN0cm9rZVN0eWxlPWNvbDsgZy5saW5lV2lkdGg9NTsgZy5saW5lSm9pbj0ncm91bmQnOwogICAgICAgICAgZy5iZWdpblBhdGgoKTsKICAgICAgICAgIGcubW92ZVRvKHF1YWQudGwueCxxdWFkLnRsLnkpOyBnLmxpbmVUbyhxdWFkLnRyLngscXVhZC50ci55KTsgZy5saW5lVG8ocXVhZC5ici54LHF1YWQuYnIueSk7IGcubGluZVRvKHF1YWQuYmwueCxxdWFkLmJsLnkpOyBnLmNsb3NlUGF0aCgpOwogICAgICAgICAgZy5zdHJva2UoKTsKICAgICAgICAgIGcuZmlsbFN0eWxlPWNvbDsKICAgICAgICAgIHZhciBwdHM9W3F1YWQudGwscXVhZC50cixxdWFkLmJyLHF1YWQuYmxdLCBpOwogICAgICAgICAgZm9yKGk9MDtpPDQ7aSsrKXsgZy5iZWdpblBhdGgoKTsgZy5hcmMocHRzW2ldLngscHRzW2ldLnksOSwwLE1hdGguUEkqMik7IGcuZmlsbCgpOyB9CiAgICAgICAgfWVsc2V7CiAgICAgICAgICB2YXIgeDI9TWF0aC5yb3VuZCh2dyowLjA3KSwgeTI9TWF0aC5yb3VuZCh2aCowLjEyKSwgdzI9dncteDIqMiwgaDI9dmgteTIqMjsKICAgICAgICAgIGcuc3Ryb2tlU3R5bGU9KGVzdGFkbz09PSdtYWwnKT8nI2U2N2UyMic6JyM5YWEwYTYnOwogICAgICAgICAgZy5saW5lV2lkdGg9NDsgZy5zZXRMaW5lRGFzaChbMTQsMTBdKTsKICAgICAgICAgIGcuc3Ryb2tlUmVjdCh4Mix5Mix3MixoMik7CiAgICAgICAgICBnLnNldExpbmVEYXNoKFtdKTsKICAgICAgICB9CiAgICAgICAgaWYobnVtZXJvPjApewogICAgICAgICAgZy5zYXZlKCk7CiAgICAgICAgICBnLmZvbnQ9J2JvbGQgMTEwcHggc2Fucy1zZXJpZic7IGcudGV4dEFsaWduPSdjZW50ZXInOyBnLnRleHRCYXNlbGluZT0nbWlkZGxlJzsKICAgICAgICAgIGcubGluZVdpZHRoPTEwOyBnLnN0cm9rZVN0eWxlPSdyZ2JhKDAsMCwwLDAuNTUpJzsKICAgICAgICAgIGcuc3Ryb2tlVGV4dChTdHJpbmcobnVtZXJvKSx2dy8yLHZoLzIpOwogICAgICAgICAgZy5maWxsU3R5bGU9JyMzZmI5NTAnOyBnLmZpbGxUZXh0KFN0cmluZyhudW1lcm8pLHZ3LzIsdmgvMik7CiAgICAgICAgICBnLnJlc3RvcmUoKTsKICAgICAgICB9CiAgICAgIH1jYXRjaChlKXt9CiAgICB9OwogICAgdmFyIHBpbnRhck92YWxvPWZ1bmN0aW9uKGVzdGFkbywgbnVtZXJvLCBpbmZvKXsKICAgICAgdHJ5ewogICAgICAgIHZhciBvdj0kKG92SWQpOyBpZighb3YpeyByZXR1cm47IH0KICAgICAgICB2YXIgdnc9KHYmJnYudmlkZW9XaWR0aCl8fDAsIHZoPSh2JiZ2LnZpZGVvSGVpZ2h0KXx8MDsKICAgICAgICBpZighdnd8fCF2aCl7IHJldHVybjsgfQogICAgICAgIGlmKG92LndpZHRoIT09dnd8fG92LmhlaWdodCE9PXZoKXsgb3Yud2lkdGg9dnc7IG92LmhlaWdodD12aDsgfQogICAgICAgIHZhciBnPW92LmdldENvbnRleHQoJzJkJyk7IGlmKCFnKXsgcmV0dXJuOyB9CiAgICAgICAgZy5jbGVhclJlY3QoMCwwLHZ3LHZoKTsKICAgICAgICB2YXIgY3g9dncqMC41LCBjeT12aCowLjUyLCByeD12dyowLjMwLCByeT12aCowLjM4OwogICAgICAgIHZhciBjb2w9KGVzdGFkbz09PSdvaycpPycjM2ZiOTUwJzooKGVzdGFkbz09PSdjYXJhJyk/JyNlM2IzNDEnOicjOWFhMGE2Jyk7CiAgICAgICAgdHJ5ewogICAgICAgICAgZy5maWxsU3R5bGU9J3JnYmEoMCwwLDAsMC40MCknOwogICAgICAgICAgZy5iZWdpblBhdGgoKTsKICAgICAgICAgIGcucmVjdCgwLDAsdncsdmgpOwogICAgICAgICAgZy5tb3ZlVG8oY3grcngsY3kpOwogICAgICAgICAgaWYoZy5lbGxpcHNlKXsgZy5lbGxpcHNlKGN4LGN5LHJ4LHJ5LDAsMCxNYXRoLlBJKjIpOyB9IGVsc2UgeyBnLnJlY3QoY3gtcngsY3ktcnkscngqMixyeSoyKTsgfQogICAgICAgICAgZy5maWxsKCdldmVub2RkJyk7CiAgICAgICAgfWNhdGNoKGVGKXsgZy5maWxsU3R5bGU9J3JnYmEoMCwwLDAsMC4yMiknOyBnLmZpbGxSZWN0KDAsMCx2dyx2aCk7IH0KICAgICAgICBnLnNhdmUoKTsKICAgICAgICBnLnN0cm9rZVN0eWxlPWNvbDsgZy5saW5lV2lkdGg9NjsKICAgICAgICBnLmJlZ2luUGF0aCgpOyBpZihnLmVsbGlwc2UpeyBnLmVsbGlwc2UoY3gsY3kscngscnksMCwwLE1hdGguUEkqMik7IH0gZWxzZSB7IGcuc3Ryb2tlUmVjdChjeC1yeCxjeS1yeSxyeCoyLHJ5KjIpOyB9CiAgICAgICAgZy5zdHJva2UoKTsKICAgICAgICBnLnJlc3RvcmUoKTsKICAgICAgICBpZihpbmZvJiZpbmZvLmNhamEmJmluZm8uY2FqYS53PjQpewogICAgICAgICAgZy5zdHJva2VTdHlsZT0oZXN0YWRvPT09J29rJyk/JyMzZmI5NTAnOicjZTNiMzQxJzsgZy5saW5lV2lkdGg9MzsKICAgICAgICAgIGcuc3Ryb2tlUmVjdChpbmZvLmNhamEueCxpbmZvLmNhamEueSxpbmZvLmNhamEudyxpbmZvLmNhamEuaCk7CiAgICAgICAgfQogICAgICAgIHZhciBwcm9nPShzdCYmc3QuYXV0byk/TWF0aC5taW4oMSxzdC5hdXRvLzQpOjA7CiAgICAgICAgaWYocHJvZz4wKXsKICAgICAgICAgIGcuc2F2ZSgpOyBnLnN0cm9rZVN0eWxlPScjM2ZiOTUwJzsgZy5saW5lV2lkdGg9ODsKICAgICAgICAgIGcuYmVnaW5QYXRoKCk7CiAgICAgICAgICBnLmFyYyhjeCxjeSxNYXRoLm1heChyeCxyeSkrMTYsLU1hdGguUEkvMiwtTWF0aC5QSS8yK3Byb2cqTWF0aC5QSSoyKTsKICAgICAgICAgIGcuc3Ryb2tlKCk7IGcucmVzdG9yZSgpOwogICAgICAgIH0KICAgICAgICBpZihudW1lcm8+MCl7CiAgICAgICAgICBnLnNhdmUoKTsKICAgICAgICAgIGcuZm9udD0nYm9sZCAxMTBweCBzYW5zLXNlcmlmJzsgZy50ZXh0QWxpZ249J2NlbnRlcic7IGcudGV4dEJhc2VsaW5lPSdtaWRkbGUnOwogICAgICAgICAgZy5saW5lV2lkdGg9MTA7IGcuc3Ryb2tlU3R5bGU9J3JnYmEoMCwwLDAsMC41NSknOwogICAgICAgICAgZy5zdHJva2VUZXh0KFN0cmluZyhudW1lcm8pLHZ3LzIsdmgvMik7CiAgICAgICAgICBnLmZpbGxTdHlsZT0nIzNmYjk1MCc7IGcuZmlsbFRleHQoU3RyaW5nKG51bWVybyksdncvMix2aC8yKTsKICAgICAgICAgIGcucmVzdG9yZSgpOwogICAgICAgIH0KICAgICAgfWNhdGNoKGUpe30KICAgIH07CiAgICB2YXIgdWx0aW1vPScnOwogICAgdmFyIGF2aXNhcj1mdW5jdGlvbihjb2RlLHR4dCxjb2xvcil7IGlmKGNvZGUhPT11bHRpbW8peyB1bHRpbW89Y29kZTsgbXNnKHN0SWQsdHh0LGNvbG9yKTsgfSB9OwogICAgaWYocHNJZD09PSc0Jyl7CiAgICAgIHBpbnRhck92YWxvKCcnLDAsbnVsbCk7CiAgICAgIGF2aXNhcignaW5pJywnUG9uIHR1IGNhcmEgZGVudHJvIGRlbCBPVkFMTy4gTGEgY2FwdHVyYSBlcyBBVVRPTUFUSUNBIGN1YW5kbyB0b2RvIGVzdGUgY29ycmVjdG8uJywnI2E2MCcpOwogICAgICBpZihzdC5pdil7IHRyeXsgY2xlYXJJbnRlcnZhbChzdC5pdik7IH1jYXRjaChlKXt9IH0KICAgICAgc3QuaXY9c2V0SW50ZXJ2YWwoZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICBpZighc3RyZWFtc1twc0lkXSl7IHJldHVybjsgfQogICAgICAgICAgYnVzY2FyQ2FyYVZpdmEodixmdW5jdGlvbihpbmZvKXsKICAgICAgICAgICAgdHJ5ewogICAgICAgICAgICAgIEVTVC5jYXJhVml2YT1pbmZvOwogICAgICAgICAgICAgIGlmKCFpbmZvfHwhaW5mby52aXN0YSl7CiAgICAgICAgICAgICAgICBzdC5hdXRvPTA7IHN0LmNkPTA7CiAgICAgICAgICAgICAgICBwaW50YXJPdmFsbygnY2FyYScsMCxpbmZvfHxudWxsKTsKICAgICAgICAgICAgICAgIGF2aXNhcigoaW5mbyYmaW5mby5jb2QpfHwnbm9kZXQnLChpbmZvJiZpbmZvLm1vdGl2byl8fCdCdXNjYW5kbyB0dSBjYXJhLi4uIGJ1ZW5hIGx1eiwgc2luIGdvcnJhIG5pIGxlbnRlcyBvc2N1cm9zLicsJyNhNjAnKTsKICAgICAgICAgICAgICAgIHJldHVybjsKICAgICAgICAgICAgICB9CiAgICAgICAgICAgICAgdmFyIG51bWVybz0wOwogICAgICAgICAgICAgIGlmKGluZm8ub2speyBzdC5hdXRvPShzdC5hdXRvfHwwKSsxOyB9IGVsc2UgeyBzdC5hdXRvPTA7IHN0LmNkPTA7IH0KICAgICAgICAgICAgICBpZihzdC5hdXRvPj00KXsKICAgICAgICAgICAgICAgIHN0LmNkPShzdC5jZHx8MCkrMTsKICAgICAgICAgICAgICAgIG51bWVybz1NYXRoLm1heCgxLDQtc3QuY2QpOwogICAgICAgICAgICAgICAgcGludGFyT3ZhbG8oJ29rJyxudW1lcm8saW5mbyk7CiAgICAgICAgICAgICAgICBhdmlzYXIoJ2NkJytudW1lcm8sJ0NhcHR1cmFuZG8gZW4gJytudW1lcm8rJy4uLiBubyB0ZSBtdWV2YXMuJywnIzA4MCcpOwogICAgICAgICAgICAgICAgaWYoc3QuY2Q+PTQmJiFzdC5hdXRvSGVjaG8pewogICAgICAgICAgICAgICAgICBzdC5hdXRvSGVjaG89dHJ1ZTsgdmlicmFyKCk7CiAgICAgICAgICAgICAgICAgIHByb2Nlc2FyU2VsZmllKCk7CiAgICAgICAgICAgICAgICB9CiAgICAgICAgICAgICAgICByZXR1cm47CiAgICAgICAgICAgICAgfQogICAgICAgICAgICAgIHBpbnRhck92YWxvKGluZm8ub2s/J29rJzonY2FyYScsMCxpbmZvKTsKICAgICAgICAgICAgICBhdmlzYXIoaW5mby5vaz8ncHJlJzppbmZvLmNvZCwgaW5mby5tb3Rpdm8sIGluZm8ub2s/JyMwODAnOicjYTYwJyk7CiAgICAgICAgICAgIH1jYXRjaChlMyl7fQogICAgICAgICAgfSk7CiAgICAgICAgfWNhdGNoKGUpe30KICAgICAgfSw0MzApOwogICAgfWVsc2V7CiAgICAgIHBpbnRhckRvYyhudWxsLCcnKTsKICAgICAgYXZpc2FyKCdpbmknLCdCdXNjYW5kbyBlbCBkb2N1bWVudG8uLi4gcG9ubG8gc29icmUgZm9uZG8gT1NDVVJPLCBzaW4gYnJpbGxvLiBMYXMgNCBlc3F1aW5hcyBzZSBtYXJjYW4gc29sYXMuJywnI2E2MCcpOwogICAgICBpZihzdC5pdil7IHRyeXsgY2xlYXJJbnRlcnZhbChzdC5pdik7IH1jYXRjaChlKXt9IH0KICAgICAgc3QuaXY9c2V0SW50ZXJ2YWwoZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICBpZighc3RyZWFtc1twc0lkXSl7IHJldHVybjsgfQogICAgICAgICAgdmFyIHE9ZGV0ZWN0YXJEb2NRdWFkKHYpOwogICAgICAgICAgdmFyIGVzdD0nbWFsJywgY29kPSdub25lJywgdHh0PSdCdXNjYW5kbyBlbCBkb2N1bWVudG8uLi4gcG9ubG8gc29icmUgZm9uZG8gT1NDVVJPLCBsbGVuYW5kbyBlbCBtYXJjbywgc2luIGJyaWxsby4nLCBjb2w9JyNhNjAnLCBxdWFkPW51bGwsIG51bWVybz0wOwogICAgICAgICAgaWYocSYmcS5sbGVubyl7CiAgICAgICAgICAgIHZhciBiMT1xLmx1ej49NjAsIGIyPXEubml0bz49NDAsIGIzPShxLmJsYW5jbz09bnVsbCl8fChxLmJsYW5jbzw9MC4yMik7CiAgICAgICAgICAgIHN0LmF1dG89MDsKICAgICAgICAgICAgaWYoIWIxKXsgc3QuY2Q9MDsgZXN0PSdtYWwnOyBjb2Q9J2x1eic7IHR4dD0nUE9DQSBMVVo6IGJ1c2NhIG1lam9yIGlsdW1pbmFjaW9uIG8gdXNhIEVsZWdpciBhcmNoaXZvIGNvbiB1bmEgZm90byBkZSBjZXJjYS4nOyBjb2w9JyNjMDAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYoIWIyKXsgc3QuY2Q9MDsgZXN0PSdtYWwnOyBjb2Q9J25pdG8nOyB0eHQ9J05vIHNlIHZlIE5JVElETzogc29zdFx1MDBFOW4gZmlybWUsIGVzcGVyYSBlbCBlbmZvcXVlIHkgZXZpdGEgZWwgYnJpbGxvLic7IGNvbD0nI2MwMCc7IH0KICAgICAgICAgICAgZWxzZSBpZighYjMpeyBzdC5jZD0wOyBlc3Q9J21hbCc7IGNvZD0nYmxhJzsgdHh0PSdIYXkgUkVGTEVKTyBlbiBlbCBkb2N1bWVudG86IGluY2xcdTAwRURuYWxvIHVuIHBvY28gcGFyYSBxdWl0YXIgZWwgYnJpbGxvLic7IGNvbD0nI2MwMCc7IH0KICAgICAgICAgICAgZWxzZXsKICAgICAgICAgICAgICAvKiBOVUVWTyB2MTQ6IHNpIGVsIGRvY3VtZW50byBsbGVuYSBlbCBjdWFkcm8gY29uIGx1eiB5IG5pdGlkZXosCiAgICAgICAgICAgICAgICAgdGFtYmllbiBjYXB0dXJhIFNPTE8gY29uIGN1ZW50YSBhdHJhcyAoYW50ZXMgb2JsaWdhYmEgYSB0b2NhcgogICAgICAgICAgICAgICAgIENBUFRVUkFSKS4gTWlzbW8gMy0yLTEgcXVlIGN1YW5kbyBoYXkgNCBlc3F1aW5hcy4gKi8KICAgICAgICAgICAgICBzdC5jZD0oc3QuY2R8fDApKzE7CiAgICAgICAgICAgICAgbnVtZXJvPU1hdGgubWF4KDEsNC1zdC5jZCk7CiAgICAgICAgICAgICAgZXN0PSdvayc7IGNvZD0nY2QnK251bWVybzsgdHh0PSdDYXB0dXJhbmRvIGVuICcrbnVtZXJvKycuLi4gbm8gdGUgbXVldmFzLic7IGNvbD0nIzA4MCc7CiAgICAgICAgICAgICAgaWYoc3QuY2Q+PTQmJiFzdC5hdXRvSGVjaG8pewogICAgICAgICAgICAgICAgc3QuYXV0b0hlY2hvPXRydWU7IHZpYnJhcigpOwogICAgICAgICAgICAgICAgbWFuZWphcihwc0lkPT09JzInPydiQ2FwRic6J2JDYXBBJyk7CiAgICAgICAgICAgICAgICByZXR1cm47CiAgICAgICAgICAgICAgfQogICAgICAgICAgICB9CiAgICAgICAgICAgIHBpbnRhckRvYyhudWxsLCBlc3QpOwogICAgICAgICAgfWVsc2UgaWYocSl7CiAgICAgICAgICAgIHF1YWQ9cTsKICAgICAgICAgICAgc3QuaGlzdC5wdXNoKHF1YWQpOwogICAgICAgICAgICBpZihzdC5oaXN0Lmxlbmd0aD43KXsgc3QuaGlzdC5zaGlmdCgpOyB9CiAgICAgICAgICAgIHZhciBjMT1xLmx1ej49NjAsIGMyPXEubml0bz49NDAsIGMzPShxLmJsYW5jbz09bnVsbCl8fChxLmJsYW5jbzw9MC4yMCk7CiAgICAgICAgICAgIHN0LmF1dG89MDsgc3QuY2Q9MDsKICAgICAgICAgICAgaWYocS5kZXNjYXJ0YWRvPT09J3BlcXVlbm8nKXsgZXN0PSdtYWwnOyBjb2Q9J2Zhcic7IHR4dD0nQUNFUkNBVEU6IGVsIGRvY3VtZW50byBzZSB2ZSBtdXkgcGVxdWVcdTAwRjFvIGVuIGxhIGZvdG8uJzsgY29sPScjYTYwJzsgfQogICAgICAgICAgICBlbHNlIGlmKHEuZGVzY2FydGFkbz09PSdmb3JtYScpeyBlc3Q9J21hbCc7IGNvZD0nZm9ybWEnOyB0eHQ9J05vIHZlbyBiaWVuIGxhcyA0IGVzcXVpbmFzOiBhY1x1MDBFOXJjYXRlIHkgdXNhIHVuIGZvbmRvIG9zY3Vyby4nOyBjb2w9JyNhNjAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYoIWMxKXsgZXN0PSdtYWwnOyBjb2Q9J2x1eic7IHR4dD0nUE9DQSBMVVo6IGJ1c2NhIG1lam9yIGlsdW1pbmFjaW9uIG8gdXNhIEVsZWdpciBhcmNoaXZvIGNvbiB1bmEgZm90byBkZSBjZXJjYS4nOyBjb2w9JyNjMDAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYoIWMyKXsgZXN0PSdtYWwnOyBjb2Q9J25pdG8nOyB0eHQ9J05vIHNlIHZlIE5JVElETzogc29zdFx1MDBFOW4gZmlybWUsIGVzcGVyYSBlbCBlbmZvcXVlIHkgZXZpdGEgZWwgYnJpbGxvLic7IGNvbD0nI2MwMCc7IH0KICAgICAgICAgICAgZWxzZSBpZighYzMpeyBlc3Q9J21hbCc7IGNvZD0nYmxhJzsgdHh0PSdIYXkgUkVGTEVKTyBlbiBlbCBkb2N1bWVudG86IGluY2xcdTAwRURuYWxvIHVuIHBvY28gcGFyYSBxdWl0YXIgZWwgYnJpbGxvLic7IGNvbD0nI2MwMCc7IH0KICAgICAgICAgICAgZWxzZSBpZihxdWFkRXN0YWJsZShzdC5oaXN0KSl7CiAgICAgICAgICAgICAgc3QuYXV0bz0xOwogICAgICAgICAgICAgIHN0LmNkPShzdC5jZHx8MCkrMTsKICAgICAgICAgICAgICBudW1lcm89TWF0aC5tYXgoMSw0LXN0LmNkKTsKICAgICAgICAgICAgICBlc3Q9J29rJzsgY29kPSdjZCcrbnVtZXJvOyB0eHQ9J0NhcHR1cmFuZG8gZW4gJytudW1lcm8rJy4uLiBubyB0ZSBtdWV2YXMuJzsgY29sPScjMDgwJzsKICAgICAgICAgICAgICBpZihzdC5jZD49NCYmIXN0LmF1dG9IZWNobyl7CiAgICAgICAgICAgICAgICBzdC5hdXRvSGVjaG89dHJ1ZTsgdmlicmFyKCk7CiAgICAgICAgICAgICAgICBtYW5lamFyKHBzSWQ9PT0nMic/J2JDYXBGJzonYkNhcEEnKTsKICAgICAgICAgICAgICAgIHJldHVybjsKICAgICAgICAgICAgICB9CiAgICAgICAgICAgIH1lbHNlewogICAgICAgICAgICAgIGVzdD0nY2FzaSc7IGNvZD0nZXNwZXJhJzsgdHh0PSdEb2N1bWVudG8gZGV0ZWN0YWRvLiBTb3N0ZW5sbyBxdWlldG8gcGFyYSBjYXB0dXJhciBzb2xvLi4uJzsgY29sPScjMDgwJzsKICAgICAgICAgICAgfQogICAgICAgICAgICBwaW50YXJRdWFkKHF1YWQsIGVzdCwgbnVtZXJvKTsKICAgICAgICAgIH1lbHNlewogICAgICAgICAgICBzdC5hdXRvPTA7IHN0LmNkPTA7CiAgICAgICAgICAgIGlmKERhdGUubm93KCktc3QudD4xMjAwKXsgc3QuY2FqYT1udWxsOyB9CiAgICAgICAgICAgIHZhciBjYWphRj1kZXRlY3RhckRvY0JveCh2KTsKICAgICAgICAgICAgaWYoY2FqYUYpewogICAgICAgICAgICAgIHN0LmNhamE9Y2FqYUY7IHN0LnQ9RGF0ZS5ub3coKTsKICAgICAgICAgICAgICBlc3Q9KGNhamFGLm5pdG8mJmNhamFGLmx1ej49NTUpPydjYXNpJzonbWFsJzsKICAgICAgICAgICAgICBjb2Q9KGVzdD09PSdjYXNpJyk/J2Fwcm94JzonY2FsJzsKICAgICAgICAgICAgICB0eHQ9KGVzdD09PSdjYXNpJyk/J0Nhc2k6IHNvc3RcdTAwRTluIHF1aWV0by4gQ29uIGZvbmRvIG9zY3VybyBtYXJjbyBsYXMgNCBlc3F1aW5hcyB5IGNhcHR1cm8gc29sby4nOidTZSB2ZSBmbG9qbzogbVx1MDBFMXMgbHV6LCBmaXJtZSwgc2luIGJyaWxsby4nOwogICAgICAgICAgICAgIGNvbD0oZXN0PT09J2Nhc2knKT8nI2E2MCc6JyNjMDAnOwogICAgICAgICAgICB9ZWxzZSBpZihEYXRlLm5vdygpLXN0LnQ+MTIwMCl7CiAgICAgICAgICAgICAgY29kPSdub25lJzsgdHh0PSdCdXNjYW5kbyBlbCBkb2N1bWVudG8uLi4gcG9ubG8gc29icmUgZm9uZG8gT1NDVVJPLCBsbGVuYW5kbyBlbCBtYXJjbywgc2luIGJyaWxsby4nOwogICAgICAgICAgICB9CiAgICAgICAgICAgIHBpbnRhckRvYyhjYWphRnx8c3QuY2FqYXx8bnVsbCwgZXN0KTsKICAgICAgICAgIH0KICAgICAgICAgIGF2aXNhcihjb2QsdHh0LGNvbCk7CiAgICAgICAgfWNhdGNoKGUpe30KICAgICAgfSwzMDApOwogICAgfQogICAgaWYoIXYuX196eU1hcmNvKXsKICAgICAgdi5fX3p5TWFyY289MTsKICAgICAgdi5hZGRFdmVudExpc3RlbmVyKCdwbGF5aW5nJyxmdW5jdGlvbigpeyB0cnl7IGFsaW5lYXJPdmVybGF5KHBzSWQsIHYpOyBpZihwc0lkPT09JzQnKXsgcGludGFyT3ZhbG8oJycsMCxudWxsKTsgfSBlbHNlIHsgcGludGFyRG9jKG51bGwsJycpOyB9IH1jYXRjaChlKXt9IH0pOwogICAgICB2LmFkZEV2ZW50TGlzdGVuZXIoJ2xvYWRlZG1ldGFkYXRhJyxmdW5jdGlvbigpeyB0cnl7IGFsaW5lYXJPdmVybGF5KHBzSWQsIHYpOyBpZihwc0lkPT09JzQnKXsgcGludGFyT3ZhbG8oJycsMCxudWxsKTsgfSBlbHNlIHsgcGludGFyRG9jKG51bGwsJycpOyB9IH1jYXRjaChlKXt9IH0pOwogICAgfQogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gaW50ZW50YXJFbmZvcXVlKHN0KXsKICB0cnl7CiAgICB2YXIgdHI9KHN0JiZzdC5nZXRWaWRlb1RyYWNrcyk/c3QuZ2V0VmlkZW9UcmFja3MoKVswXTpudWxsOwogICAgaWYoIXRyKXsgcmV0dXJuOyB9CiAgICB2YXIgY2Fwcz10ci5nZXRDYXBhYmlsaXRpZXM/dHIuZ2V0Q2FwYWJpbGl0aWVzKCk6bnVsbDsKICAgIGlmKGNhcHMmJmNhcHMuZm9jdXNNb2RlJiZjYXBzLmZvY3VzTW9kZS5qb2luJiZjYXBzLmZvY3VzTW9kZS5qb2luKCcgJykuaW5kZXhPZignY29udGludW91cycpPj0wKXsKICAgICAgdmFyIHA9dHIuYXBwbHlDb25zdHJhaW50cyh7YWR2YW5jZWQ6W3tmb2N1c01vZGU6J2NvbnRpbnVvdXMnfV19KTsKICAgICAgaWYocCYmcC5jYXRjaCl7IHAuY2F0Y2goZnVuY3Rpb24oKXt9KTsgfQogICAgfQogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gYWJyaXJDYW0ocHNJZCwgZmFjaW5nLCBzdElkLCBjYXBJZCl7CiAgdmFyIHY9ZmluZFZpZGVvKHBzSWQpOwogIGlmKCF2KXsgbXNnKHN0SWQsJ05vIGVuY29udHJlIGVsIHZpZGVvIGRlIGxhIGNhbWFyYSBlbiBsYSBwYWdpbmEuJywgJyNjMDAnKTsgcmV0dXJuIFByb21pc2UucmVqZWN0KG5ldyBFcnJvcignc2luIHZpZGVvJykpOyB9CiAgaWYoIW5hdmlnYXRvci5tZWRpYURldmljZXMgfHwgIW5hdmlnYXRvci5tZWRpYURldmljZXMuZ2V0VXNlck1lZGlhKXsKICAgIG1zZyhzdElkLCdUdSBuYXZlZ2Fkb3Igbm8gcGVybWl0ZSBjYW1hcmEuIFVzYSBsYSBvcGNpb24gZGUgZ2FsZXJpYS4nLCAnI2MwMCcpOwogICAgcmV0dXJuIFByb21pc2UucmVqZWN0KG5ldyBFcnJvcignc2luIGNhbWFyYScpKTsKICB9CiAgcGFyYXJDYW0ocHNJZCk7CiAgdmFyIHpvbmE9JCgndnonK2xldHJhRGUocHNJZCkpOwogIGlmKHpvbmEpeyB6b25hLnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsgfQogIG1zZyhzdElkLCdQaWRpZW5kbyBwZXJtaXNvIGRlIGNhbWFyYS4uLicsJycpOwogIHZhciBkb2Nab25hPShwc0lkPT09JzInfHxwc0lkPT09JzMnKTsKICByZXR1cm4gbmF2aWdhdG9yLm1lZGlhRGV2aWNlcy5nZXRVc2VyTWVkaWEoe2F1ZGlvOmZhbHNlLCB2aWRlbzp7ZmFjaW5nTW9kZTpmYWNpbmcsIHdpZHRoOntpZGVhbDpkb2Nab25hPzE5MjA6MTI4MH0sIGhlaWdodDp7aWRlYWw6ZG9jWm9uYT8xMDgwOjcyMH19fSkudGhlbihmdW5jdGlvbihzdCl7CiAgICBzdHJlYW1zW3BzSWRdPXN0OwogICAgdi5zcmNPYmplY3Q9c3Q7CiAgICB0cnl7IHYuc2V0QXR0cmlidXRlKCdwbGF5c2lubGluZScsJ3BsYXlzaW5saW5lJyk7IH1jYXRjaChlKXt9CiAgICB2Lm11dGVkPXRydWU7CiAgICB0cnl7IHYuc3R5bGUudHJhbnNmb3JtPShwc0lkPT09JzQnKT8nc2NhbGVYKC0xKSc6Jyc7IH1jYXRjaChlTSl7fQogICAgaW50ZW50YXJFbmZvcXVlKHN0KTsKICAgIHZhciBwPXYucGxheSgpOyBpZihwJiZwLmNhdGNoKXsgcC5jYXRjaChmdW5jdGlvbigpe30pOyB9CiAgICBlc3RpbG9DaGljbyh2KTsKICAgIHZhciBjYXA9JChjYXBJZCk7CiAgICBpZihjYXApeyBjYXAuZGlzYWJsZWQ9ZmFsc2U7IGNhcC5zdHlsZS5kaXNwbGF5PScnOyBjYXAuc3R5bGUudmlzaWJpbGl0eT0ndmlzaWJsZSc7IGNhcC5zdHlsZS5wb2ludGVyRXZlbnRzPSdhdXRvJzsgY2FwLnN0eWxlLnBvc2l0aW9uPWNhcC5zdHlsZS5wb3NpdGlvbnx8J3JlbGF0aXZlJzsgY2FwLnN0eWxlLnpJbmRleD0nOTk5OSc7IH0KICAgIHZhciBPVj17JzInOidvdkYnLCczJzonb3ZBJywnNCc6J292Uyd9OwogICAgdmFyIG92PSQoT1ZbcHNJZF0pOwogICAgaWYob3YpeyBvdi5zdHlsZS5wb2ludGVyRXZlbnRzPSdub25lJzsgfQogICAgdmFyIHpvbmE9JCgndnonK2xldHJhRGUocHNJZCkpOwogICAgaWYoem9uYSl7IHpvbmEuc3R5bGUucG9zaXRpb249J3JlbGF0aXZlJzsgfQogICAgZW5tYXJjYXJWZXJkZShwc0lkLCB2KTsKICAgIGFsaW5lYXJPdmVybGF5KHBzSWQsIHYpOwogICAgc2V0VGltZW91dChmdW5jdGlvbigpeyB0cnl7IGFsaW5lYXJPdmVybGF5KHBzSWQsIHYpOyB9Y2F0Y2goZSl7fSB9LDI1MCk7CiAgICB2YXIgcT0ocHNJZD09PSc0Jyk7CiAgICBtc2coc3RJZCwgcT8nQ2FtYXJhIGxpc3RhLiBQb24gdHUgY2FyYSBlbiBlbCBPVkFMTzogc2UgY2FwdHVyYSBTT0xPIGN1YW5kbyB0b2RvIGVzdGUgY29ycmVjdG8uJzonQ2FtYXJhIGxpc3RhLiBCdXNjbyBsYXMgNCBlc3F1aW5hcyBkZWwgZG9jdW1lbnRvOiBzb3N0XHUwMEU5bmxvIHF1aWV0byB5IGNhcHR1cm8gc29sby4nLCcjMDgwJyk7CiAgICByZXR1cm4gdHJ1ZTsKICB9KS5jYXRjaChmdW5jdGlvbihlKXsKICAgIGlmKHpvbmEpeyB0cnl7IHpvbmEuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH1jYXRjaChlMil7fSB9CiAgICBtc2coc3RJZCwnTm8gcHVkZSBhYnJpciBsYSBjYW1hcmEgKCcrKGUmJmUubmFtZT9lLm5hbWU6J2Vycm9yJykrJykuIFB1ZWRlcyB1c2FyIGxhIGdhbGVyaWEgbyByZXZpc2EgZWwgcGVybWlzby4nLCcjYzAwJyk7CiAgICB0aHJvdyBlOwogIH0pOwp9CmZ1bmN0aW9uIHBhcmFyQ2FtKHBzSWQpewogIHZhciBzdD1zdHJlYW1zW3BzSWRdOwogIGlmKHN0KXsKICAgIHRyeXsgc3QuZ2V0VHJhY2tzKCkuZm9yRWFjaChmdW5jdGlvbih0KXsgdHJ5eyB0LnN0b3AoKTsgfWNhdGNoKGUpe30gfSk7IH1jYXRjaChlKXt9CiAgfQogIHN0cmVhbXNbcHNJZF09bnVsbDsKICB0cnl7CiAgICB2YXIgdnY9ZmluZFZpZGVvKHBzSWQpOwogICAgaWYodnYpeyB2di5zdHlsZS50cmFuc2Zvcm09Jyc7IH0KICB9Y2F0Y2goZVQpe30KICB0cnl7CiAgICB2YXIgRD16eURldCgpLCBzdEQ9RFtwc0lkXTsKICAgIGlmKHN0RCYmc3RELml2KXsgY2xlYXJJbnRlcnZhbChzdEQuaXYpOyBzdEQuaXY9bnVsbDsgfQogICAgaWYocHNJZD09PSc0Jyl7IEVTVC5jYXJhVml2YT1udWxsOyB9CiAgfWNhdGNoKGUpe30KICB0cnl7CiAgICB2YXIgem9uYT0kKCd2eicrbGV0cmFEZShwc0lkKSk7CiAgICBpZih6b25hKXsgem9uYS5zdHlsZS5kaXNwbGF5PSdub25lJzsgfQogICAgdmFyIE9WPXsnMic6J292RicsJzMnOidvdkEnLCc0Jzonb3ZTJ307CiAgICB2YXIgb3Y9JChPVltwc0lkXSk7CiAgICBpZihvdil7IHZhciBnPW92LmdldENvbnRleHQoJzJkJyk7IGlmKGcpeyBnLmNsZWFyUmVjdCgwLDAsb3Yud2lkdGh8fDEsb3YuaGVpZ2h0fHwxKTsgfSB9CiAgfWNhdGNoKGUpe30KfQpmdW5jdGlvbiBwYXJhclRvZGFzKCl7IHZhciBrOyBmb3IoayBpbiBzdHJlYW1zKXsgcGFyYXJDYW0oayk7IH0gfQpmdW5jdGlvbiBjYXB0dXJhclZpZGVvKHBzSWQsIG1heERpbSl7CiAgdmFyIHY9ZmluZFZpZGVvKHBzSWQpOwogIGlmKCF2IHx8ICF2LnZpZGVvV2lkdGggfHwgIXN0cmVhbXNbcHNJZF0peyByZXR1cm4gbnVsbDsgfQogIHZhciB3PXYudmlkZW9XaWR0aCwgaD12LnZpZGVvSGVpZ2h0OwogIHZhciBzYz1NYXRoLm1pbigxLChtYXhEaW18fDEwMjQpL01hdGgubWF4KHcsaCkpOwogIHZhciBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOwogIGMud2lkdGg9TWF0aC5yb3VuZCh3KnNjKTsgYy5oZWlnaHQ9TWF0aC5yb3VuZChoKnNjKTsKICBjLmdldENvbnRleHQoJzJkJykuZHJhd0ltYWdlKHYsMCwwLGMud2lkdGgsYy5oZWlnaHQpOwogIHZhciBkPWMudG9EYXRhVVJMKCdpbWFnZS9qcGVnJywwLjkpOwogIHBhcmFyQ2FtKHBzSWQpOwogIHJldHVybiBkOwp9CmZ1bmN0aW9uIGRvd25zY2FsZShkYXRhVXJsLCBtYXhEaW0pewogIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpewogICAgdmFyIGltPW5ldyBJbWFnZSgpOwogICAgaW0ub25sb2FkPWZ1bmN0aW9uKCl7CiAgICAgIHZhciBzYz1NYXRoLm1pbigxLChtYXhEaW18fDEwMjQpL01hdGgubWF4KGltLndpZHRoLGltLmhlaWdodCkpOwogICAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgICAgYy53aWR0aD1NYXRoLm1heCgxLE1hdGgucm91bmQoaW0ud2lkdGgqc2MpKTsKICAgICAgYy5oZWlnaHQ9TWF0aC5tYXgoMSxNYXRoLnJvdW5kKGltLmhlaWdodCpzYykpOwogICAgICBjLmdldENvbnRleHQoJzJkJykuZHJhd0ltYWdlKGltLDAsMCxjLndpZHRoLGMuaGVpZ2h0KTsKICAgICAgcmVzKGMudG9EYXRhVVJMKCdpbWFnZS9qcGVnJywwLjkpKTsKICAgIH07CiAgICBpbS5vbmVycm9yPWZ1bmN0aW9uKCl7IHJlcyhkYXRhVXJsKTsgfTsKICAgIGltLnNyYz1kYXRhVXJsOwogIH0pOwp9CmZ1bmN0aW9uIGFyY2hpdm9BRGF0b3MoZmlsZSl7CiAgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyxyZWopewogICAgdmFyIGZyPW5ldyBGaWxlUmVhZGVyKCk7CiAgICBmci5vbmxvYWQ9ZnVuY3Rpb24oKXsgcmVzKFN0cmluZyhmci5yZXN1bHQpKTsgfTsKICAgIGZyLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVqKG5ldyBFcnJvcignbm8gcHVkZSBsZWVyIGVsIGFyY2hpdm8nKSk7IH07CiAgICBmci5yZWFkQXNEYXRhVVJMKGZpbGUpOwogIH0pOwp9CgovKiA9PT09PT09PT09PT09PT09PSBPQ1IgY29uIGNhY2hlICsgbWVqb3JhIGRlIGltYWdlbiA9PT09PT09PT09PT09PT09PSAqLwp2YXIgY2FjaGVPY3I9e30sIHByb21lc2FXb3JrZXI9bnVsbDsKZnVuY3Rpb24gYWJyaXJXb3JrZXJPY3IoKXsKICBpZihwcm9tZXNhV29ya2VyKXsgcmV0dXJuIHByb21lc2FXb3JrZXI7IH0KICB0cnl7CiAgICBpZih0eXBlb2YgVGVzc2VyYWN0IT09J3VuZGVmaW5lZCcgJiYgVGVzc2VyYWN0LmNyZWF0ZVdvcmtlcil7CiAgICAgIHByb21lc2FXb3JrZXI9VGVzc2VyYWN0LmNyZWF0ZVdvcmtlcignc3BhK2VuZycsMSx7bG9nZ2VyOmZ1bmN0aW9uKCl7fX0pLnRoZW4oZnVuY3Rpb24odyl7IHJldHVybiB3OyB9KS5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gbnVsbDsgfSk7CiAgICAgIHJldHVybiBwcm9tZXNhV29ya2VyOwogICAgfQogIH1jYXRjaChlKXt9CiAgcHJvbWVzYVdvcmtlcj1Qcm9taXNlLnJlc29sdmUobnVsbCk7CiAgcmV0dXJuIHByb21lc2FXb3JrZXI7Cn0KZnVuY3Rpb24gbWVqb3JhckltYWdlbihkYXRhVXJsKXsKICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsKICAgIHZhciBpbT1uZXcgSW1hZ2UoKTsKICAgIGltLm9ubG9hZD1mdW5jdGlvbigpewogICAgICB0cnl7CiAgICAgICAgdmFyIGFuY2hvPWltLndpZHRoLCBhbHRvPWltLmhlaWdodDsKICAgICAgICB2YXIgZXNjMT1NYXRoLm1pbigzLCBNYXRoLm1heCgxLCAxNDAwL01hdGgubWF4KDEsTWF0aC5taW4oYW5jaG8sYWx0bykpKSk7CiAgICAgICAgdmFyIGVzYzI9TWF0aC5taW4oMSwgMjYwMC9NYXRoLm1heCgxLE1hdGgubWF4KGFuY2hvLGFsdG8pKSk7CiAgICAgICAgdmFyIHNjPU1hdGgubWluKGVzYzEsZXNjMik7CiAgICAgICAgaWYoIShzYz4wKSl7IHNjPTE7IH0KICAgICAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgICAgICBjLndpZHRoPU1hdGgubWF4KDEsTWF0aC5yb3VuZChhbmNobypzYykpOwogICAgICAgIGMuaGVpZ2h0PU1hdGgubWF4KDEsTWF0aC5yb3VuZChhbHRvKnNjKSk7CiAgICAgICAgdmFyIGc9Yy5nZXRDb250ZXh0KCcyZCcpOwogICAgICAgIGlmKCFnKXsgcmVzKG51bGwpOyByZXR1cm47IH0KICAgICAgICBnLmltYWdlU21vb3RoaW5nRW5hYmxlZD10cnVlOwogICAgICAgIHRyeXsgZy5pbWFnZVNtb290aGluZ1F1YWxpdHk9J2hpZ2gnOyB9Y2F0Y2goZTIpe30KICAgICAgICBnLmRyYXdJbWFnZShpbSwwLDAsYy53aWR0aCxjLmhlaWdodCk7CiAgICAgICAgdmFyIGlkZD1nLmdldEltYWdlRGF0YSgwLDAsYy53aWR0aCxjLmhlaWdodCksIHA9aWRkLmRhdGEsIG49cC5sZW5ndGgvNDsKICAgICAgICB2YXIgaGlzdD1uZXcgSW50MzJBcnJheSgyNTYpLCBpLCBrLCBzdW09MDsKICAgICAgICBmb3IoaT0wO2k8bjtpKyspeyB2YXIgcj1wW2kqNF0sIGdnPXBbaSo0KzFdLCBiPXBbaSo0KzJdOyB2YXIgbD0ociozK2dnKjQrYik+PjM7IHBbaSo0XT1sOyBwW2kqNCsxXT1sOyBwW2kqNCsyXT1sOyBoaXN0W2xdKys7IHN1bSs9bDsgfQogICAgICAgIHZhciBtZWRpYT1zdW0vTWF0aC5tYXgoMSxuKTsKICAgICAgICB2YXIgZ2FuPTE7CiAgICAgICAgaWYobWVkaWE8MTA1KXsgZ2FuPTAuNzI7IH0KICAgICAgICBlbHNlIGlmKG1lZGlhPjE4NSl7IGdhbj0xLjI1OyB9CiAgICAgICAgdmFyIGFjYz0wLCBsbz0wLCBoaT0yNTU7CiAgICAgICAgZm9yKGs9MDtrPDI1NjtrKyspeyBhY2MrPWhpc3Rba107IGlmKGFjYz49biowLjAyKXsgbG89azsgYnJlYWs7IH0gfQogICAgICAgIGFjYz0wOwogICAgICAgIGZvcihrPTI1NTtrPj0wO2stLSl7IGFjYys9aGlzdFtrXTsgaWYoYWNjPj1uKjAuMDIpeyBoaT1rOyBicmVhazsgfSB9CiAgICAgICAgdmFyIGVzYz0oaGk+bG8pPzI1NS8oaGktbG8pOjE7CiAgICAgICAgZm9yKGk9MDtpPG47aSsrKXsgdmFyIHY9KHBbaSo0XS1sbykqZXNjOyB2PXY8MD8wOih2PjI1NT8yNTU6dik7IHY9MjU1Kk1hdGgucG93KHYvMjU1LGdhbik7IHBbaSo0XT12OyBwW2kqNCsxXT12OyBwW2kqNCsyXT12OyB9CiAgICAgICAgdmFyIHRtcD1uZXcgVWludDhBcnJheShuKTsKICAgICAgICBmb3IoaT0wO2k8bjtpKyspeyB0bXBbaV09cFtpKjRdOyB9CiAgICAgICAgdmFyIGFuY2hvMj1jLndpZHRoOwogICAgICAgIGZvcih2YXIgeT0xO3k8Yy5oZWlnaHQtMTt5KyspewogICAgICAgICAgZm9yKHZhciB4PTE7eDxhbmNobzItMTt4KyspewogICAgICAgICAgICB2YXIgcT15KmFuY2hvMit4OwogICAgICAgICAgICB2YXIgYmw9KHRtcFtxXSt0bXBbcS0xXSt0bXBbcSsxXSt0bXBbcS1hbmNobzJdK3RtcFtxK2FuY2hvMl0pKjAuMjsKICAgICAgICAgICAgdmFyIHYyPXRtcFtxXSswLjQqKHRtcFtxXS1ibCk7CiAgICAgICAgICAgIHYyPXYyPDA/MDoodjI+MjU1PzI1NTp2Mik7CiAgICAgICAgICAgIHZhciB3Mz1xKjQ7IHBbdzNdPXYyOyBwW3czKzFdPXYyOyBwW3czKzJdPXYyOwogICAgICAgICAgfQogICAgICAgIH0KICAgICAgICBnLnB1dEltYWdlRGF0YShpZGQsMCwwKTsKICAgICAgICByZXMoYyk7CiAgICAgIH1jYXRjaChlKXsgcmVzKG51bGwpOyB9CiAgICB9OwogICAgaW0ub25lcnJvcj1mdW5jdGlvbigpeyByZXMobnVsbCk7IH07CiAgICBpbS5zcmM9ZGF0YVVybDsKICB9KTsKfQpmdW5jdGlvbiByZWNvcnRlU3VwZXJpb3IoY3YpewogIHRyeXsKICAgIHZhciB3PWN2LndpZHRoLCBoPU1hdGgucm91bmQoY3YuaGVpZ2h0KjAuNjIpOwogICAgaWYodzw0MHx8aDw0MCl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgIGMud2lkdGg9dzsgYy5oZWlnaHQ9aDsKICAgIGMuZ2V0Q29udGV4dCgnMmQnKS5kcmF3SW1hZ2UoY3YsMCwwLHcsaCwwLDAsdyxoKTsKICAgIHJldHVybiBjOwogIH1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0KfQpmdW5jdGlvbiByZWNvbm9jZXJDb24oaW1nLCBwc20pewogIHJldHVybiBhYnJpcldvcmtlck9jcigpLnRoZW4oZnVuY3Rpb24odyl7CiAgICBmdW5jdGlvbiBjb25UZXNzKCl7CiAgICAgIHJldHVybiBUZXNzZXJhY3QucmVjb2duaXplKGltZywnc3BhK2VuZycse2xvZ2dlcjpmdW5jdGlvbigpe319KS50aGVuKGZ1bmN0aW9uKHIpeyByZXR1cm4gKHImJnIuZGF0YSYmci5kYXRhLnRleHQpP3IuZGF0YS50ZXh0OicnOyB9KS5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gJyc7IH0pOwogICAgfQogICAgaWYoISh3JiZ3LnJlY29nbml6ZSkpeyByZXR1cm4gY29uVGVzcygpOyB9CiAgICB2YXIgcHJlPSh3LnNldFBhcmFtZXRlcnMmJnBzbSk/dy5zZXRQYXJhbWV0ZXJzKHt0ZXNzZWRpdF9wYWdlc2VnX21vZGU6U3RyaW5nKHBzbSl9KTpQcm9taXNlLnJlc29sdmUoKTsKICAgIHJldHVybiBwcmUudGhlbihmdW5jdGlvbigpeyByZXR1cm4gdy5yZWNvZ25pemUoaW1nKTsgfSkudGhlbihmdW5jdGlvbihyKXsKICAgICAgaWYody5zZXRQYXJhbWV0ZXJzKXsgdHJ5eyB3LnNldFBhcmFtZXRlcnMoe3Rlc3NlZGl0X3BhZ2VzZWdfbW9kZTonMyd9KS5jYXRjaChmdW5jdGlvbigpe30pOyB9Y2F0Y2goZTIpe30gfQogICAgICByZXR1cm4gKHImJnIuZGF0YSYmci5kYXRhLnRleHQpP3IuZGF0YS50ZXh0OicnOwogICAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmV0dXJuIGNvblRlc3MoKTsgfSk7CiAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmV0dXJuICcnOyB9KTsKfQpmdW5jdGlvbiBvY3JNdWx0aShkYXRhVXJsLCBlc0J1ZW5vKXsKICBpZih0eXBlb2YgVGVzc2VyYWN0PT09J3VuZGVmaW5lZCcgfHwgIVRlc3NlcmFjdC5yZWNvZ25pemUpewogICAgcmV0dXJuIFByb21pc2UucmVzb2x2ZShbXSk7CiAgfQogIHJldHVybiBtZWpvcmFySW1hZ2VuKGRhdGFVcmwpLnRoZW4oZnVuY3Rpb24oY3YpewogICAgdmFyIHZhcnM9W107CiAgICBpZihjdil7CiAgICAgIHZhcnMucHVzaCh7aW1nOmN2LCBwc206JzMnfSk7CiAgICAgIHZhciByYz1yZWNvcnRlU3VwZXJpb3IoY3YpOwogICAgICBpZihyYyl7IHZhcnMucHVzaCh7aW1nOnJjLCBwc206JzYnfSk7IH0KICAgICAgLyogTlVFVk8gdjE0OiBwYXNlIGRpc3BlcnNvIChQU00gMTEpIHBhcmEgbG9zIGNhbXBvcyBzdWVsdG9zIGRlbAogICAgICAgICBkb2N1bWVudG8gKE5PTUJSRVMgLyBBUEVMTElET1MgdmFuIGVuIGxpbmVhcyBzZXBhcmFkYXMgeSBlbCBwYXNlCiAgICAgICAgIG5vcm1hbCBhIHZlY2VzIGxvcyBzYWx0YSkuIGVzQnVlbm8gY29ydGEgYXBlbmFzIGFjaWVydGEuICovCiAgICAgIHZhcnMucHVzaCh7aW1nOmN2LCBwc206JzExJ30pOwogICAgfQogICAgdmFycy5wdXNoKHtpbWc6ZGF0YVVybCwgcHNtOiczJ30pOwogICAgdmFyIGk9MCwgdGV4dG9zPVtdOwogICAgZnVuY3Rpb24gcGFzbygpewogICAgICBpZihpPj12YXJzLmxlbmd0aCl7IHJldHVybiBQcm9taXNlLnJlc29sdmUodGV4dG9zKTsgfQogICAgICB2YXIgcj12YXJzW2krK107CiAgICAgIHJldHVybiByZWNvbm9jZXJDb24oci5pbWcsIHIucHNtKS50aGVuKGZ1bmN0aW9uKHQpewogICAgICAgIGlmKHQpeyB0ZXh0b3MucHVzaCh0KTsgfQogICAgICAgIGlmKHQmJmVzQnVlbm8mJmVzQnVlbm8odCkpeyByZXR1cm4gdGV4dG9zOyB9CiAgICAgICAgcmV0dXJuIHBhc28oKTsKICAgICAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmV0dXJuIHBhc28oKTsgfSk7CiAgICB9CiAgICByZXR1cm4gcGFzbygpOwogIH0pOwp9CmZ1bmN0aW9uIGVsZWdpclRleHRvKHRleHRvcywgZXNjcml0byl7CiAgdmFyIG1lam9yPScnLCBtaj0tMSwgaTsKICBmb3IoaT0wO2k8dGV4dG9zLmxlbmd0aDtpKyspewogICAgdmFyIHQ9dGV4dG9zW2ldfHwnJywgcD0wOwogICAgaWYoZXNjcml0byl7CiAgICAgIHZhciBuYz1ub21icmVDb2luY2lkZShlc2NyaXRvLHQsZmFsc2UpOwogICAgICBwPShuYy5vaz8xMDAwOjApKyhuYy5wdW50fHwwKSoxMDA7CiAgICB9CiAgICBwKz1NYXRoLm1pbig1MCwodC5yZXBsYWNlKC9bXkEtWjAtOV0vZ2ksJycpLmxlbmd0aCkvMzApOwogICAgaWYocD5tail7IG1qPXA7IG1lam9yPXQ7IH0KICB9CiAgcmV0dXJuIG1lam9yOwp9CmZ1bmN0aW9uIGhhY2VyT2NyKGRhdGFVcmwpewogIGlmKGNhY2hlT2NyW2RhdGFVcmxdKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZShjYWNoZU9jcltkYXRhVXJsXSk7IH0KICBpZih0eXBlb2YgVGVzc2VyYWN0PT09J3VuZGVmaW5lZCcgfHwgIVRlc3NlcmFjdC5yZWNvZ25pemUpewogICAgcmV0dXJuIFByb21pc2UucmVqZWN0KG5ldyBFcnJvcignT0NSIG5vIGRpc3BvbmlibGUsIHJldmlzYSB0dSBpbnRlcm5ldCcpKTsKICB9CiAgcmV0dXJuIG9jck11bHRpKGRhdGFVcmwsIGZ1bmN0aW9uKHQpeyByZXR1cm4gKHR8fCcnKS5yZXBsYWNlKC9bXkEtWjAtOV0vZ2ksJycpLmxlbmd0aD49MzQ7IH0pLnRoZW4oZnVuY3Rpb24odGV4dG9zKXsKICAgIHZhciB0PWVsZWdpclRleHRvKHRleHRvcywgbnVsbCk7CiAgICBjYWNoZU9jcltkYXRhVXJsXT10fHwnJzsKICAgIHJldHVybiB0fHwnJzsKICB9KTsKfQpmdW5jdGlvbiBvY3JGcmVudGUoZGF0YVVybCl7CiAgaWYoY2FjaGVPY3JbZGF0YVVybF0peyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKGNhY2hlT2NyW2RhdGFVcmxdKTsgfQogIHJldHVybiBvY3JNdWx0aShkYXRhVXJsLCBmdW5jdGlvbih0KXsgcmV0dXJuIG5vbWJyZUNvaW5jaWRlKEVTVC5lc2NyaXRvLCB0fHwnJywgZmFsc2UpLm9rOyB9KS50aGVuKGZ1bmN0aW9uKHRleHRvcyl7CiAgICB2YXIgdD1lbGVnaXJUZXh0byh0ZXh0b3MsIEVTVC5lc2NyaXRvKTsKICAgIGlmKHQpeyBjYWNoZU9jcltkYXRhVXJsXT10OyB9CiAgICByZXR1cm4gdHx8Jyc7CiAgfSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IGJpb21ldHJpYSBmYWNpYWwgPT09PT09PT09PT09PT09PT0gKi8KdmFyIGZhY2VQPW51bGw7CmZ1bmN0aW9uIGNhcmdhckZhY2VBcGkoKXsKICBpZihmYWNlUCl7IHJldHVybiBmYWNlUDsgfQogIGZhY2VQPW5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyxyZWopewogICAgZnVuY3Rpb24gbGlzdG8oKXsgcmV0dXJuIFcuZmFjZWFwaSAmJiBXLmZhY2VhcGkubmV0cyAmJiBXLmZhY2VhcGkubmV0cy50aW55RmFjZURldGVjdG9yICYmIFcuZmFjZWFwaS5uZXRzLmZhY2VSZWNvZ25pdGlvbk5ldDsgfQogICAgZnVuY3Rpb24gbW9kZWxvcyhiYXNlKXsKICAgICAgcmV0dXJuIFByb21pc2UuYWxsKFsKICAgICAgICBXLmZhY2VhcGkubmV0cy50aW55RmFjZURldGVjdG9yLmxvYWRGcm9tVXJpKGJhc2UpLAogICAgICAgIFcuZmFjZWFwaS5uZXRzLmZhY2VMYW5kbWFyazY4TmV0LmxvYWRGcm9tVXJpKGJhc2UpLAogICAgICAgIFcuZmFjZWFwaS5uZXRzLmZhY2VSZWNvZ25pdGlvbk5ldC5sb2FkRnJvbVVyaShiYXNlKQogICAgICBdKTsKICAgIH0KICAgIGZ1bmN0aW9uIGluaWNpYXIoKXsKICAgICAgdmFyIGJhc2U9J2h0dHBzOi8vY2RuLmpzZGVsaXZyLm5ldC9naC9qdXN0YWR1ZGV3aG9oYWNrcy9mYWNlLWFwaS5qc0AwLjIyLjIvd2VpZ2h0cyc7CiAgICAgIG1vZGVsb3MoYmFzZSkudGhlbihmdW5jdGlvbigpeyByZXMoKTsgfSwgZnVuY3Rpb24oKXsgbW9kZWxvcygnaHR0cHM6Ly9qdXN0YWR1ZGV3aG9oYWNrcy5naXRodWIuaW8vZmFjZS1hcGkuanMvbW9kZWxzJykudGhlbihmdW5jdGlvbigpeyByZXMoKTsgfSwgcmVqKTsgfSk7CiAgICB9CiAgICBpZihsaXN0bygpKXsgaW5pY2lhcigpOyByZXR1cm47IH0KICAgIHZhciBzPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ3NjcmlwdCcpOwogICAgcy5zcmM9J2h0dHBzOi8vY2RuLmpzZGVsaXZyLm5ldC9ucG0vZmFjZS1hcGkuanNAMC4yMi4yL2Rpc3QvZmFjZS1hcGkubWluLmpzJzsKICAgIHMub25sb2FkPWZ1bmN0aW9uKCl7IGlmKGxpc3RvKCkpeyBpbmljaWFyKCk7IH0gZWxzZSB7IHJlaihuZXcgRXJyb3IoJ2ZhY2VhcGkgbm8gcXVlZG8gbGlzdG8nKSk7IH0gfTsKICAgIHMub25lcnJvcj1mdW5jdGlvbigpeyByZWoobmV3IEVycm9yKCdubyBzZSBwdWRvIGNhcmdhciBlbCB2ZXJpZmljYWRvciBmYWNpYWwnKSk7IH07CiAgICBkb2N1bWVudC5oZWFkLmFwcGVuZENoaWxkKHMpOwogIH0pOwogIHJldHVybiBmYWNlUDsKfQpmdW5jdGlvbiBjb25UaW1lb3V0KHAsIG1zKXsKICByZXR1cm4gUHJvbWlzZS5yYWNlKFtwLCBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpeyBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IHJlcyhudWxsKTsgfSwgbXMpOyB9KV0pOwp9CmZ1bmN0aW9uIGRldGVjdGFyQ2FyYUVuKGRhdGFVcmwsIGludGVudG8pewogIHJldHVybiBjYXJnYXJGYWNlQXBpKCkudGhlbihmdW5jdGlvbigpewogICAgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7CiAgICAgIHZhciBpbT1uZXcgSW1hZ2UoKTsKICAgICAgaW0ub25sb2FkPWZ1bmN0aW9uKCl7CiAgICAgICAgdHJ5ewogICAgICAgICAgdmFyIHRhbT0oaW50ZW50bz09PTIpPzUxMjozMjA7CiAgICAgICAgICB2YXIgb3B0PW5ldyBXLmZhY2VhcGkuVGlueUZhY2VEZXRlY3Rvck9wdGlvbnMoe2lucHV0U2l6ZTp0YW0sIHNjb3JlVGhyZXNob2xkOihpbnRlbnRvPT09Mik/MC4zOjAuNH0pOwogICAgICAgICAgVy5mYWNlYXBpLmRldGVjdFNpbmdsZUZhY2UoaW0sb3B0KS53aXRoRmFjZUxhbmRtYXJrcygpLndpdGhGYWNlRGVzY3JpcHRvcigpLnRoZW4oZnVuY3Rpb24ocil7CiAgICAgICAgICAgIGlmKHImJnIuZGV0ZWN0aW9uKXsgcmVzKHIpOyByZXR1cm47IH0KICAgICAgICAgICAgaWYoaW50ZW50bz09PTIpeyByZXMobnVsbCk7IHJldHVybjsgfQogICAgICAgICAgICByZXMoZGV0ZWN0YXJDYXJhRW4oZGF0YVVybCwoaW50ZW50bz09PTEpPzI6MSkpOwogICAgICAgICAgfSkuY2F0Y2goZnVuY3Rpb24oKXsKICAgICAgICAgICAgaWYoaW50ZW50bz09PTIpeyByZXMobnVsbCk7IHJldHVybjsgfQogICAgICAgICAgICByZXMoZGV0ZWN0YXJDYXJhRW4oZGF0YVVybCwoaW50ZW50bz09PTEpPzI6MSkpOwogICAgICAgICAgfSk7CiAgICAgICAgfWNhdGNoKGUpeyByZXMobnVsbCk7IH0KICAgICAgfTsKICAgICAgaW0ub25lcnJvcj1mdW5jdGlvbigpeyByZXMobnVsbCk7IH07CiAgICAgIGltLnNyYz1kYXRhVXJsOwogICAgfSk7CiAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmV0dXJuIG51bGw7IH0pOwp9CmZ1bmN0aW9uIHJlY29ydGVDYXJhKGRhdGFVcmwpewogIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpewogICAgdmFyIGltPW5ldyBJbWFnZSgpOwogICAgaW0ub25sb2FkPWZ1bmN0aW9uKCl7CiAgICAgIHRyeXsKICAgICAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgICAgICBjLndpZHRoPU1hdGgubWF4KDQwLE1hdGgucm91bmQoaW0ud2lkdGgqMC42MikpOwogICAgICAgIGMuaGVpZ2h0PU1hdGgubWF4KDQwLE1hdGgucm91bmQoaW0uaGVpZ2h0KjAuNjYpKTsKICAgICAgICBjLmdldENvbnRleHQoJzJkJykuZHJhd0ltYWdlKGltLDAsMCxpbS53aWR0aCxNYXRoLnJvdW5kKGltLmhlaWdodCowLjkpLDAsMCxjLndpZHRoLGMuaGVpZ2h0KTsKICAgICAgICByZXMoYy50b0RhdGFVUkwoJ2ltYWdlL2pwZWcnLDAuOSkpOwogICAgICB9Y2F0Y2goZSl7IHJlcyhudWxsKTsgfQogICAgfTsKICAgIGltLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVzKG51bGwpOyB9OwogICAgaW0uc3JjPWRhdGFVcmw7CiAgfSk7Cn0KZnVuY3Rpb24gZGV0ZWN0YXJDYXJhRG9jKGRhdGFVcmwpewogIGlmKCFkYXRhVXJsKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZShudWxsKTsgfQogIHJldHVybiBkZXRlY3RhckNhcmFFbihkYXRhVXJsKS50aGVuKGZ1bmN0aW9uKHIpewogICAgaWYociYmci5kZXRlY3Rpb24peyByZXR1cm4gcjsgfQogICAgcmV0dXJuIHJlY29ydGVDYXJhKGRhdGFVcmwpLnRoZW4oZnVuY3Rpb24ocmVjKXsKICAgICAgaWYoIXJlYyl7IHJldHVybiBudWxsOyB9CiAgICAgIHJldHVybiBkZXRlY3RhckNhcmFFbihyZWMsMSk7CiAgICB9KTsKICB9KTsKfQpmdW5jdGlvbiBkaXN0RihhLGIpewogIHZhciBzPTAsaTsKICBmb3IoaT0wO2k8YS5sZW5ndGg7aSsrKXsgdmFyIGQ9YVtpXS1iW2ldOyBzKz1kKmQ7IH0KICByZXR1cm4gTWF0aC5zcXJ0KHMpOwp9CgovKiA9PT09PT09PT09PT09PT09PSBndWFyZGlhbiBkZSBvcmRlbiAxLTItMy00LTUgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gcGVybWl0aWRvSGFzdGEoKXsKICB2YXIgcD0xOwogIGlmKEVTVC5ub21icmVPayl7IHA9MjsgfQogIGlmKEVTVC5ub21icmVPayAmJiBFU1QuZnJlbnRlT2speyBwPTM7IH0KICBpZihFU1Qubm9tYnJlT2sgJiYgRVNULmZyZW50ZU9rICYmIChFU1QucmV2ZXJzb09rIHx8ICFFU1QubmVjZXNpdGFSZXZlcnNvKSl7IHA9NDsgfQogIGlmKEVTVC5zZWxmaWVPayAmJiBwPj00KXsgcD01OyB9CiAgcmV0dXJuIHA7Cn0KZnVuY3Rpb24gbW9zdHJhclBhc28obil7CiAgdmFyIGksZWwsIHJiPSQoJ3p5QnRuUmVwRm90bycpOwogIGlmKHJiKXsgcmIuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH0KICBmb3IoaT0xO2k8PTU7aSsrKXsKICAgIGVsPSQoJ3BzJytpKTsKICAgIGlmKGVsKXsKICAgICAgZWwuY2xhc3NOYW1lPSdwYXNvJysoaT09PW4/JyBhY3QnOicnKTsKICAgICAgZWwuc3R5bGUuZGlzcGxheT0nJzsKICAgIH0KICB9CiAgdmFyIHByPSQoJ3Byb2cnKTsKICBpZihwcil7IHByLnRleHRDb250ZW50PSdQQVNPICcrbisnIERFIDUnOyB9CiAgaWYoRVNULnBhc28+PTIgJiYgRVNULnBhc288PTQgJiYgRVNULnBhc28hPT1uKXsgdHJ5eyBwYXJhckNhbShFU1QucGFzbyk7IH1jYXRjaChlKXt9IH0KICBFU1QucGFzbz1uOwogIGlmKG49PT01KXsKICAgIHZhciBhPSQoJ2NsYXZlJyksIGI9JCgnY2xhdmUyJyk7CiAgICBpZihhKXsgYS5kaXNhYmxlZD1mYWxzZTsgfQogICAgaWYoYil7IGIuZGlzYWJsZWQ9ZmFsc2U7IH0KICAgIHRyeXsgYmFycmVNZW5zYWplcygpOyB9Y2F0Y2goZSl7fQogICAgdHJ5eyBsaW1waWFMZWdhZG8oKTsgfWNhdGNoKGUpe30KICAgIHRyeXsgcGludGFEaWFnKCk7IH1jYXRjaChlKXt9CiAgICB2YXIgcmY9RVNULmZyZW50ZU9rPydGcmVudGUgT0snOidGQUxUQSBGUkVOVEUnOwogICAgdmFyIHJyPSghRVNULm5lY2VzaXRhUmV2ZXJzb3x8RVNULnJldmVyc29Payk/J1JldmVyc28gT0snOidGQUxUQSBSRVZFUlNPJzsKICAgIHZhciBycz1FU1Quc2VsZmllT2s/J1NlbGZpZSB2ZXJpZmljYWRhJzonU0VMRklFIFNJTiBWRVJJRklDQVInOwogICAgdmFyIHRvZG89KEVTVC5mcmVudGVPayYmRVNULnNlbGZpZU9rJiYoIUVTVC5uZWNlc2l0YVJldmVyc298fEVTVC5yZXZlcnNvT2spKTsKICAgIG1zZygnenlSZXN1bWVuNScsJ1ZlcmlmaWNhY2lvbiBmaW5hbDogJytyZisnIHwgJytycisnIHwgJytycysnLiBFc2NyaWJlIHR1IGNsYXZlIDIgdmVjZXMgeSBjcmVhIHR1IFpJRC4nLHRvZG8/JyMwODAnOicjYzAwJyk7CiAgfQogIHRyeXsgdmFyIGFjdD0kKCdwcycrbik7IGlmKGFjdCYmYWN0LnNjcm9sbEludG9WaWV3KXsgYWN0LnNjcm9sbEludG9WaWV3KHtiZWhhdmlvcjonc21vb3RoJyxibG9jazonc3RhcnQnfSk7IH0gfWNhdGNoKGUpe30KfQpmdW5jdGlvbiBhdmFuemFyKG4peyBtb3N0cmFyUGFzbyhuKTsgfQpmdW5jdGlvbiB2ZXJpZmljYXIoKXsKICB0cnl7CiAgICB2YXIgYWN0PWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJy5wYXNvLmFjdCcpOwogICAgdmFyIHJuPWFjdCYmYWN0LmlkP3BhcnNlSW50KFN0cmluZyhhY3QuaWQpLnJlcGxhY2UoJ3BzJywnJyksMTApOjA7CiAgICBpZihybj49MSYmcm48PTUmJnJuIT09RVNULnBhc28peyBFU1QucGFzbz1ybjsgfQogIH1jYXRjaChlKXt9CiAgdHJ5eyB2YWxpZGFyUGFzbzEodHJ1ZSk7IH1jYXRjaChlKXt9CiAgdmFyIHBlcj1wZXJtaXRpZG9IYXN0YSgpOwogIGlmKEVTVC5wYXNvPnBlcil7CiAgICBpZihwZXI9PT0xKXsgbXNnKCd6eUd1YXJkaWEnLCdQYXJhIHNlZ3VpciwgZXNjcmliZSB0dSBub21icmUgeSBlbGlnZSBlbCB0aXBvIGRlIGRvY3VtZW50byBlbiBlbCBwYXNvIDEuJywnI2E2MCcpOyB9CiAgICBlbHNleyBtc2coJ3p5R3VhcmRpYScsJ1RlIHJlZ3Jlc28gYWwgcGFzbyAnK3BlcisnIHBhcmEgc2VndWlyIGVuIG9yZGVuLicsJyNhNjAnKTsgfQogICAgbW9zdHJhclBhc28ocGVyKTsKICB9CiAgdmFyIHNlbD0kKCd0aXBvRG9jJyk7CiAgaWYoc2VsICYmIHNlbC52YWx1ZSAmJiAvcGFzYXBvcnRlfHBhc3Nwb3J0L2kudGVzdCgoc2VsLm9wdGlvbnMmJnNlbC5vcHRpb25zW3NlbC5zZWxlY3RlZEluZGV4XSYmc2VsLm9wdGlvbnNbc2VsLnNlbGVjdGVkSW5kZXhdLnRleHQpfHwnJykpewogICAgdmFyIHBzMz0kKCdwczMnKSwgbnI9JCgnbm90YVJldicpOwogICAgaWYocHMzKXsgcHMzLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgICBpZihucil7IG5yLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgfQp9CnZhciB2dGltZXI9bnVsbDsKZnVuY3Rpb24gcHJvZ3JhbWFyVmVyaWZpY2FyKCl7CiAgaWYodnRpbWVyKXsgcmV0dXJuOyB9CiAgdnRpbWVyPXNldFRpbWVvdXQoZnVuY3Rpb24oKXsgdnRpbWVyPW51bGw7IHRyeXsgdmVyaWZpY2FyKCk7IH1jYXRjaChlKXt9IH0sMTIwKTsKfQp0cnl7CiAgbmV3IE11dGF0aW9uT2JzZXJ2ZXIocHJvZ3JhbWFyVmVyaWZpY2FyKS5vYnNlcnZlKGRvY3VtZW50LmJvZHkse2NoaWxkTGlzdDp0cnVlLHN1YnRyZWU6dHJ1ZSxhdHRyaWJ1dGVzOnRydWUsYXR0cmlidXRlRmlsdGVyOlsnc3R5bGUnLCdjbGFzcycsJ2hpZGRlbicsJ2Rpc2FibGVkJ119KTsKfWNhdGNoKGUpe30KCi8qID09PT09PT09PT09PT09PT09IHBhc28gMTogc29sbyBmb3JtYXRvIGRlbCBub21icmUgKHZhbGlkYSBTT0xPIGFsIGNvbnRpbnVhciwgbnVuY2EgbWllbnRyYXMgZXNjcmliZXMpID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHZhbGlkYXJQYXNvMShzaWxlbmNpb3NvKXsKICB2YXIgaW5wPSQoJ25vbWJyZScpLCBzZWw9JCgndGlwb0RvYycpOwogIHZhciB2PWlucD8oaW5wLnZhbHVlfHwnJykudHJpbSgpOicnOwogIHZhciBsZXRyYXM9L15bQS1aYS16XHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxXHUwMEUxXHUwMEU5XHUwMEVEXHUwMEYzXHUwMEZBXHUwMEZDXHUwMEYxXSsoIFtBLVphLXpcdTAwQzFcdTAwQzlcdTAwQ0RcdTAwRDNcdTAwREFcdTAwRENcdTAwRDFcdTAwRTFcdTAwRTlcdTAwRURcdTAwRjNcdTAwRkFcdTAwRkNcdTAwRjFdKykqJC8udGVzdCh2KTsKICB2YXIgbnA9dj92LnNwbGl0KC9ccysvKS5sZW5ndGg6MDsKICB2YXIgb2s9KHYubGVuZ3RoPj01ICYmIGxldHJhcyAmJiBucD49Mik7CiAgdmFyIHQ9Y2xhc2lmaWNhclRpcG8oKTsKICBFU1QudGlwbz10Lms7CiAgRVNULm5lY2VzaXRhUmV2ZXJzbz10LnJldmVyc287CiAgdmFyIHRpcG9Paz0hIShzZWwgJiYgU3RyaW5nKHNlbC52YWx1ZXx8JycpLmxlbmd0aD4wKTsKICBFU1Qubm9tYnJlT2s9b2s7CiAgRVNULmVzY3JpdG89bm9ybSh2KTsKICBpZihzaWxlbmNpb3NvKXsgcmV0dXJuIG9rJiZ0aXBvT2s7IH0KICBpZihpbnApeyBpbnAuc3R5bGUuYm9yZGVyQ29sb3I9b2s/Jyc6JyNjMDAnOyB9CiAgdmFyIG1ubz0nJzsKICBpZighb2speyBtbm89dj8nRXNjcmliZSB0dSBub21icmUgeSB0dSBhcGVsbGlkbyAoc29sbyBsZXRyYXMgeSBlc3BhY2lvczsgc2lydmUgY29uIDEgbyAyIG5vbWJyZXMgeSAxIG8gMiBhcGVsbGlkb3MpLic6J0VzY3JpYmUgdHUgbm9tYnJlIHkgdHUgYXBlbGxpZG8gcGFyYSBjb250aW51YXIuJzsgfQogIG1zZygnenlFcnJOb21icmUnLG1ubyxtbm8/JyNjMDAnOicnKTsKICB2YXIgbXRpPXRpcG9Paz8nJzonRWxpZ2UgdHUgdGlwbyBkZSBkb2N1bWVudG8gZW4gbGEgbGlzdGEuJzsKICBtc2coJ3p5RXJyVGlwbycsbXRpLG10aT8nI2MwMCc6JycpOwogIHJldHVybiBvayYmdGlwb09rOwp9CmZ1bmN0aW9uIGxpbXBpYXJFcnJvcmVzUGFzbzEoKXsKICB2YXIgZTE9JCgnenlFcnJOb21icmUnKTsgaWYoZTEgJiYgZTEudGV4dENvbnRlbnQpeyBlMS50ZXh0Q29udGVudD0nJzsgZTEuc3R5bGUuY29sb3I9Jyc7IH0KICB2YXIgZTI9JCgnenlFcnJUaXBvJyk7IGlmKGUyICYmIGUyLnRleHRDb250ZW50KXsgZTIudGV4dENvbnRlbnQ9Jyc7IGUyLnN0eWxlLmNvbG9yPScnOyB9CiAgdmFyIGlucD0kKCdub21icmUnKTsgaWYoaW5wICYmIGlucC5zdHlsZS5ib3JkZXJDb2xvcil7IGlucC5zdHlsZS5ib3JkZXJDb2xvcj0nJzsgfQp9CmZ1bmN0aW9uIHJlc2V0ZWFyRG9jdW1lbnRvKCl7CiAgRVNULmZyZW50ZU9rPWZhbHNlOyBFU1QucmV2ZXJzb09rPWZhbHNlOyBFU1Quc2VsZmllT2s9ZmFsc2U7IEVTVC5pbnRlbnRvcz0zOyBFU1QuY2FyYURvYz1udWxsOwp9CgovKiA9PT09PT09PT09PT09PT09PSBwYXNvIDI6IGZyZW50ZSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBmYWxsb0xlY3R1cmFGcmVudGUobSl7CiAgYnVzeShmYWxzZSk7CiAgbXNnKCdzdEYnLG0rJyBUb2NhIENBUFRVUkFSIGRlIG51ZXZvLCBjb24gYnVlbmEgbHV6IHkgc2luIGJyaWxsby4nLCcjYzAwJyk7Cn0KZnVuY3Rpb24gYXZhbnphclRyYXNGcmVudGUoKXsKICBhdmFuemFyKEVTVC5uZWNlc2l0YVJldmVyc28/Mzo0KTsKICBpZihFU1QubmVjZXNpdGFSZXZlcnNvKXsKICAgIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsgdHJ5eyBhYnJpckNhbSgnMycsJ2Vudmlyb25tZW50Jywnc3RBJywnYkNhcEEnKS5jYXRjaChmdW5jdGlvbigpe30pOyB9Y2F0Y2goZSl7fSB9LDUwMCk7CiAgfQp9CmZ1bmN0aW9uIGFjZXB0YXJGcmVudGVDb25maXJtYWRvKHRleHRvT0NSLCBsZWN0dXJhKXsKICBFU1QuZnJlbnRlT2s9dHJ1ZTsKICBFU1QuZnJlbnRlVGV4dG89KHRleHRvT0NSfHwnJykrJ1xuTEVDVFVSQSBDT05GSVJNQURBOiAnK2xlY3R1cmE7CiAgb2N1bHRhckNvbmZpcm1hY2lvbkxlY3R1cmEoKTsKICBtc2coJ3N0RicsJ1x1MjcxMyBGcmVudGUgY29uZmlybWFkbzogJytsZWN0dXJhLCcjMDgwJyk7CiAgYXZhbnphclRyYXNGcmVudGUoKTsKfQpmdW5jdGlvbiBhYnJpckNvbmZpcm1hY2lvbkxlY3R1cmEodGV4dG9PQ1IsIGxlaWRvKXsKICB0cnl7CiAgICB2YXIgY29udD0kKCd6eUxlY0JveCcpOwogICAgaWYoIWNvbnQpewogICAgICBjb250PWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgICBjb250LmlkPSd6eUxlY0JveCc7CiAgICAgIGNvbnQuc3R5bGUuY3NzVGV4dD0nYm9yZGVyOjFweCBzb2xpZCAjN2MzYWVkO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjEwcHg7bWFyZ2luOjhweCAwO2JhY2tncm91bmQ6IzE3MTIyYjsnOwogICAgICB2YXIgcHMyPSQoJ3BzMicpOwogICAgICBpZihwczImJnBzMi5pbnNlcnRCZWZvcmUpeyBwczIuaW5zZXJ0QmVmb3JlKGNvbnQscHMyLmZpcnN0Q2hpbGQpOyB9IGVsc2UgeyBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKGNvbnQpOyB9CiAgICAgIHZhciB0MT1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgICAgdDEuc3R5bGUuY3NzVGV4dD0nZm9udC1zaXplOjEzcHg7Y29sb3I6I2U2ZTZmYTttYXJnaW4tYm90dG9tOjZweDtsaW5lLWhlaWdodDoxLjM1Oyc7CiAgICAgIHQxLnRleHRDb250ZW50PSdObyBwdWRlIGNvbmZpcm1hciBlbCBub21icmUgY29uIHNlZ3VyaWRhZC4gRXN0byBmdWUgbG8gcXVlIExFXHUwMENEIGRlbCBkb2N1bWVudG8uIENvcnJpZ2UgU09MTyBsYXMgbGV0cmFzIG1hbCBsZVx1MDBFRGRhcyB5IGNvbmZpcm1hOic7CiAgICAgIGNvbnQuYXBwZW5kQ2hpbGQodDEpOwogICAgICB2YXIgaW5wPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2lucHV0Jyk7CiAgICAgIGlucC5pZD0nenlMZWNJbic7CiAgICAgIGlucC50eXBlPSd0ZXh0JzsKICAgICAgaW5wLmF1dG9jb21wbGV0ZT0nb2ZmJzsKICAgICAgaW5wLnBsYWNlaG9sZGVyPSdOb21icmUgbGVpZG8gZGVsIGRvY3VtZW50byc7CiAgICAgIGlucC5zdHlsZS5jc3NUZXh0PSd3aWR0aDoxMDAlO2JveC1zaXppbmc6Ym9yZGVyLWJveDtwYWRkaW5nOjEwcHg7Ym9yZGVyLXJhZGl1czoxMHB4O2JvcmRlcjoxcHggc29saWQgIzQ0NDtiYWNrZ3JvdW5kOiMwZTBiMWU7Y29sb3I6I2ZmZjtmb250LXNpemU6MTVweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHg7JzsKICAgICAgY29udC5hcHBlbmRDaGlsZChpbnApOwogICAgICB2YXIgYjE9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnYnV0dG9uJyk7CiAgICAgIGIxLmlkPSd6eUxlY0J0bic7CiAgICAgIGIxLnR5cGU9J2J1dHRvbic7CiAgICAgIGIxLnRleHRDb250ZW50PSdDb25maXJtYXI6IGFzXHUwMEVEIHNlIGxlZSBlbiBtaSBkb2N1bWVudG8nOwogICAgICBiMS5zdHlsZS5jc3NUZXh0PSdkaXNwbGF5OmJsb2NrO3dpZHRoOjEwMCU7cGFkZGluZzoxMXB4O2JvcmRlcjowO2JvcmRlci1yYWRpdXM6MTBweDtiYWNrZ3JvdW5kOiM3YzNhZWQ7Y29sb3I6I2ZmZjtmb250LXNpemU6MTRweDtmb250LXdlaWdodDo2MDA7bWFyZ2luLWJvdHRvbTo2cHg7JzsKICAgICAgY29udC5hcHBlbmRDaGlsZChiMSk7CiAgICAgIHZhciBiMj1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdidXR0b24nKTsKICAgICAgYjIuaWQ9J3p5TGVjUmVwJzsKICAgICAgYjIudHlwZT0nYnV0dG9uJzsKICAgICAgYjIudGV4dENvbnRlbnQ9J01lam9yIHJlcGl0byBsYSBmb3RvJzsKICAgICAgYjIuc3R5bGUuY3NzVGV4dD0nZGlzcGxheTpibG9jazt3aWR0aDoxMDAlO3BhZGRpbmc6MTBweDtib3JkZXI6MDtib3JkZXItcmFkaXVzOjEwcHg7YmFja2dyb3VuZDojMmMyYzNjO2NvbG9yOiNkZGQ7Zm9udC1zaXplOjEzcHg7JzsKICAgICAgY29udC5hcHBlbmRDaGlsZChiMik7CiAgICAgIHZhciBtPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgICBtLmlkPSd6eUxlY01zZyc7CiAgICAgIG0uc3R5bGUuY3NzVGV4dD0nZm9udC1zaXplOjEzcHg7bWFyZ2luLXRvcDo2cHg7bGluZS1oZWlnaHQ6MS4zNTsnOwogICAgICBjb250LmFwcGVuZENoaWxkKG0pOwogICAgICBiMS5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICB2YXIgdj1ub3JtKCQoJ3p5TGVjSW4nKT8kKCd6eUxlY0luJykudmFsdWU6JycpOwogICAgICAgICAgdmFyIG9jclRva3M9dG9rZW5zTm9tYnJlRGUoY29udC5fX29jcnx8JycpOwogICAgICAgICAgaWYoIXRva2Vuc0RlKHYpLmxlbmd0aCl7IG1zZygnenlMZWNNc2cnLCdFc2NyaWJlIGxvIHF1ZSBzZSBsZWUgZW4gZWwgZG9jdW1lbnRvIChzb2xvIGxldHJhcykuJywnI2MwMCcpOyByZXR1cm47IH0KICAgICAgICAgIC8qIE5VRVZPIHYxNDogc2luIGNhbGxlam9uIHNpbiBzYWxpZGEuIEFudGVzLCBzaSBlbCBPQ1IgaGFiaWEKICAgICAgICAgICAgIHNhbHRhZG8gdW5hIHBhbGFicmEgKGVqLiBubyBsZXlvIEFMRk9OU08pLCBlbCBndWFyZGFycmFpbAogICAgICAgICAgICAgcmVjaGF6YWJhIGxhIGNvcnJlY2Npb24gYXVucXVlIGVzY3JpYmllcmFzIHR1cyBub21icmVzCiAgICAgICAgICAgICB2ZXJkYWRlcm9zIHkgZWwgcGFuZWwgdm9sdmlhIFNJRU1QUkUuIEFob3JhIHR1IG5vbWJyZSBkZWwKICAgICAgICAgICAgIHBhc28gMSBtYW5kYTogZWwgZ3VhcmRhcnJhaWwgc29sbyBleGlnZSBxdWUgbGEgY29ycmVjY2lvbgogICAgICAgICAgICAgZ3VhcmRlIGFsZ3VuYSByZWxhY2lvbiBjb24gbG8gcXVlIHNlIGxleW8gZGVsIGRvY3VtZW50by4gKi8KICAgICAgICAgIHZhciBuYz1ub21icmVDb2luY2lkZShFU1QuZXNjcml0bywgdiwgZmFsc2UpOwogICAgICAgICAgaWYoIW5jLm9rKXsKICAgICAgICAgICAgbXNnKCd6eUxlY01zZycsJ0NvbiBlc2EgbGVjdHVyYSB0dSBub21icmUgc2lndWUgc2luIGNvaW5jaWRpci4gUmV2aXNhIHR1IG5vbWJyZSBkZWwgcGFzbyAxIG8gcmVwaXRlIGxhIGZvdG8uJywnI2MwMCcpOwogICAgICAgICAgICByZXR1cm47CiAgICAgICAgICB9CiAgICAgICAgICBpZihvY3JUb2tzLmxlbmd0aD4wJiYhZWRpY2lvbkFjZXB0YWJsZSh2LCBvY3JUb2tzKSl7CiAgICAgICAgICAgIHZhciB2ZD10b2tlbnNEZSh2KSwgY29tcGFydGU9ZmFsc2UsIGkxLCBqMTsKICAgICAgICAgICAgZm9yKGkxPTA7aTE8dmQubGVuZ3RoJiYhY29tcGFydGU7aTErKyl7CiAgICAgICAgICAgICAgZm9yKGoxPTA7ajE8b2NyVG9rcy5sZW5ndGg7ajErKyl7IGlmKHBhclBhcmVjaWRvKHZkW2kxXSxvY3JUb2tzW2oxXSkpeyBjb21wYXJ0ZT10cnVlOyBicmVhazsgfSB9CiAgICAgICAgICAgIH0KICAgICAgICAgICAgaWYoIWNvbXBhcnRlKXsKICAgICAgICAgICAgICBtc2coJ3p5TGVjTXNnJywnRXNhIGxlY3R1cmEgbm8gc2UgcGFyZWNlIGEgbG8gcXVlIExFXHUwMENEIGRlbCBkb2N1bWVudG8uIENvcnJpZ2UgbGFzIGxldHJhcyBtYWwgbGVcdTAwRURkYXMgbyByZXBpdGUgbGEgZm90byBjb24gbWVqb3IgbHV6LicsJyNjMDAnKTsKICAgICAgICAgICAgICByZXR1cm47CiAgICAgICAgICAgIH0KICAgICAgICAgIH0KICAgICAgICAgIGFjZXB0YXJGcmVudGVDb25maXJtYWRvKGNvbnQuX19vY3J8fCcnLCB2KTsKICAgICAgICB9Y2F0Y2goZSl7fQogICAgICB9KTsKICAgICAgYjIuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKCl7CiAgICAgICAgdHJ5ewogICAgICAgICAgb2N1bHRhckNvbmZpcm1hY2lvbkxlY3R1cmEoKTsKICAgICAgICAgIG1zZygnc3RGJywnVG9jYSBDQVBUVVJBUiB5IHJlcGl0ZSBsYSBmb3RvOiBidWVuYSBsdXosIHNpbiBicmlsbG8sIHF1ZSBlbCBkb2N1bWVudG8gbGxlbmUgZWwgbWFyY28uJywnI2E2MCcpOwogICAgICAgIH1jYXRjaChlKXt9CiAgICAgIH0pOwogICAgfQogICAgY29udC5fX29jcj10ZXh0b09DUnx8Jyc7CiAgICB2YXIgaW5wMj0kKCd6eUxlY0luJyk7CiAgICBpZihpbnAyKXsgaW5wMi52YWx1ZT0obGVpZG98fCcnKTsgfQogICAgY29udC5zdHlsZS5kaXNwbGF5PSdibG9jayc7CiAgICBtc2coJ3p5TGVjTXNnJywnJywnJyk7CiAgICBtc2coJ3N0RicsJ1JldmlzYSBhYmFqbyBsbyBxdWUgbGVcdTAwRUQgZGVsIGRvY3VtZW50bzogcHVlZGVzIGNvcnJlZ2lyIGxhcyBsZXRyYXMgbWFsIGxlXHUwMEVEZGFzLicsJyNhNjAnKTsKICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIG9jdWx0YXJDb25maXJtYWNpb25MZWN0dXJhKCl7CiAgdmFyIGM9JCgnenlMZWNCb3gnKTsKICBpZihjKXsgYy5zdHlsZS5kaXNwbGF5PSdub25lJzsgfQp9CmZ1bmN0aW9uIHByb2Nlc2FyRnJlbnRlKGRhdGFVcmwpewogIEVTVC5mcmVudGVPaz1mYWxzZTsKICBFU1QuY2FyYURvYz1udWxsOwogIG9jdWx0YXJDb25maXJtYWNpb25MZWN0dXJhKCk7CiAgYnVzeSh0cnVlKTsKICBtc2coJ3N0RicsJ0xleWVuZG8gZWwgZG9jdW1lbnRvIChwYXNlIDEgZGUgMykuLi4nLCcnKTsKICBFU1QuZnJlbnRlSW1nPWRhdGFVcmw7CiAgc2hvd0ltZygncEYnLGRhdGFVcmwpOwogIHZhciBwQ2FyYT1jb25UaW1lb3V0KGRldGVjdGFyQ2FyYUVuKGRhdGFVcmwpLDE1MDAwKTsKICB2YXIgcFR4dD1vY3JGcmVudGUoZGF0YVVybCkuY2F0Y2goZnVuY3Rpb24oZSl7IHJldHVybiAnT0NSX0VSUjonKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOicnKTsgfSk7CiAgUHJvbWlzZS5hbGwoW3BDYXJhLHBUeHRdKS50aGVuKGZ1bmN0aW9uKHIpewogICAgdmFyIGNhcmE9clswXSwgdGV4dG89clsxXXx8Jyc7CiAgICBpZih0ZXh0by5pbmRleE9mKCdPQ1JfRVJSOicpPT09MCl7IGZhbGxvTGVjdHVyYUZyZW50ZSgnTm8gcHVkZSBsZWVyIGVsIGRvY3VtZW50byAoJyt0ZXh0by5zbGljZSg4KSsnKS4nKTsgcmV0dXJuOyB9CiAgICBpZih0ZXh0by5yZXBsYWNlKC9ccy9nLCcnKS5sZW5ndGg8MTUpeyBmYWxsb0xlY3R1cmFGcmVudGUoJ05vIGxlXHUwMEVEIHN1ZmljaWVudGUgdGV4dG8uIEFjXHUwMEU5cmNhdGUsIGJ1ZW5hIGx1eiwgcXVlIGVsIGRvY3VtZW50byBsbGVuZSBlbCBtYXJjby4nKTsgcmV0dXJuOyB9CiAgICB2YXIgbGFkbz1kZXRlY3RhckxhZG8odGV4dG8sISEoY2FyYSYmY2FyYS5kZXRlY3Rpb24pKTsKICAgIGlmKGxhZG89PT0ncmV2ZXJzbycpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbXNnKCdzdEYnLCdFc28gZXMgZWwgUkVWRVJTTyAoc2UgdmVuIGRpcmVjY2lvbmVzIG8gbGEgem9uYSBNUlopLiBOZWNlc2l0byBlbCBGUkVOVEU6IGRvbmRlIGVzdFx1MDBFMSB0dSBGT1RPIHkgdHVzIGRhdG9zLiBWdWVsdmUgYSBjYXB0dXJhci4nLCcjYzAwJyk7CiAgICAgIHJldHVybjsKICAgIH0KICAgIGlmKGxhZG8hPT0nZnJlbnRlJyAmJiAhKGNhcmEmJmNhcmEuZGV0ZWN0aW9uKSl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBtc2coJ3N0RicsJ05vIHB1ZGUgY29uZmlybWFyIHF1ZSBzZWEgZWwgRlJFTlRFLiBBc2VnXHUwMEZBcmF0ZSBkZSBxdWUgc2UgdmVhIHR1IGZvdG8geSB0dXMgZGF0b3MsIHNpbiBicmlsbG8sIHkgdnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICBpZihjYXJhJiZjYXJhLmRldGVjdGlvbiYmY2FyYS5kZXNjcmlwdG9yKXsgRVNULmNhcmFEb2M9Y2FyYS5kZXNjcmlwdG9yOyB9CiAgICB2YXIgbmM9bm9tYnJlQ29pbmNpZGUoRVNULmVzY3JpdG8sdGV4dG8sbXJ6TGluZWFzKHRleHRvKS5sZW5ndGg+MCk7CiAgICBpZihuYy5oYXkgJiYgIW5jLm9rKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIGFicmlyQ29uZmlybWFjaW9uTGVjdHVyYSh0ZXh0bywgbmMubGVpZG8pOwogICAgICByZXR1cm47CiAgICB9CiAgICBFU1QuZnJlbnRlT2s9dHJ1ZTsKICAgIEVTVC5mcmVudGVUZXh0bz10ZXh0bzsKICAgIG1zZygnc3RGJywnXHUyNzEzIEZyZW50ZSBsZVx1MDBFRGRvIGNvcnJlY3RhbWVudGUuJysobmMub2s/KCcgTm9tYnJlOiAnK25jLmxlaWRvKycuJyk6JycpLCcjMDgwJyk7CiAgICBidXN5KGZhbHNlKTsKICAgIGF2YW56YXJUcmFzRnJlbnRlKCk7CiAgfSk7Cn0KZnVuY3Rpb24gbm9tYnJlTm9Db2luY2lkZU1zZyh0eHQpewogIHJlc2V0ZWFyRG9jdW1lbnRvKCk7CiAgdmFyIG5uPSQoJ25vbWJyZU5vQ29pbmNpZGUnKTsKICBpZihubil7IG5uLnRleHRDb250ZW50PXR4dDsgbm4uc3R5bGUuZGlzcGxheT0nYmxvY2snOyBubi5zdHlsZS5jb2xvcj0nI2MwMCc7IH0KICBtc2coJ3N0QScsJycpOyBtc2coJ3N0RicsJycpOwogIG1zZygnenlFcnJOb21icmUnLHR4dCsnIFNpIHR1IG5vbWJyZSBlc3RcdTAwRTEgYmllbiBlc2NyaXRvLCB0YW1iaVx1MDBFOW4gcHVlZGVzIHJlcGV0aXIgbGEgZm90byBkZWwgZG9jdW1lbnRvIGNvbiBidWVuYSBsdXogeSBzaW4gYnJpbGxvLicsJyNjMDAnKTsKICBhdmFuemFyKDEpOwogIGJvdG9uUmVwZXRpckZvdG8oKTsKfQpmdW5jdGlvbiBib3RvblJlcGV0aXJGb3RvKCl7CiAgdmFyIGI9JCgnenlCdG5SZXBGb3RvJyk7CiAgaWYoIWIpewogICAgYj1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdidXR0b24nKTsKICAgIGIuaWQ9J3p5QnRuUmVwRm90byc7CiAgICBiLnR5cGU9J2J1dHRvbic7CiAgICBiLnRleHRDb250ZW50PSdSZXBldGlyIGxhIGZvdG8gZGVsIGRvY3VtZW50byc7CiAgICBiLnN0eWxlLmNzc1RleHQ9J2Rpc3BsYXk6YmxvY2s7bWFyZ2luOjhweCAwO3BhZGRpbmc6MTFweCAxNHB4O2JvcmRlcjowO2JvcmRlci1yYWRpdXM6MTBweDtiYWNrZ3JvdW5kOiM3YzNhZWQ7Y29sb3I6I2ZmZjtmb250LXNpemU6MTRweDtmb250LXdlaWdodDo2MDA7d2lkdGg6MTAwJTsnOwogICAgYi5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oKXsgdHJ5eyBhdmFuemFyKDIpOyB9Y2F0Y2goZSl7fSB9KTsKICAgIHZhciBhbmNsYT0kKCd6eUVyck5vbWJyZScpOwogICAgaWYoYW5jbGEmJmFuY2xhLnBhcmVudE5vZGUpeyBhbmNsYS5wYXJlbnROb2RlLmluc2VydEJlZm9yZShiLGFuY2xhLm5leHRTaWJsaW5nKTsgfQogICAgZWxzZXsgZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZChiKTsgfQogIH0KICBiLnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsKfQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyAzOiByZXZlcnNvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHJldmVyc29BY2VwdGFibGUodGV4dG8pewogIHZhciB0PSh0ZXh0b3x8JycpLnRvVXBwZXJDYXNlKCk7CiAgaWYoKHQubWF0Y2goLzwvZyl8fFtdKS5sZW5ndGg+PTYpeyByZXR1cm4gdHJ1ZTsgfQogIGlmKC9QREY0ST83Ly50ZXN0KHQucmVwbGFjZSgvXHMvZywnJykpKXsgcmV0dXJuIHRydWU7IH0KICB2YXIgZnVlcnRlcz1bJ0RPTUlDSUxJTycsJ0RJUkVDQ0lPTicsJ0RJUkVDQ0lcdTAwRDNOJywnQ09MT05JQScsJ0JBUlJJTycsJ1JFU0lERU5DSUEnLCdDQVNFUklPJywnQ0FOVE9OJywnQUxERUEnLCdPQlNFUlZBQ0lPTicsJ09CU0VSVkFDSVx1MDBEM04nLCdFU1RBRE8gQ0lWSUwnLCdET05BTlRFJywnR1JVUE8gU0FORycsJ1RJUE8gREUgU0FORycsJ0VORE9SU0VNRU5UJywnUkVTVFJJQ1RJT04nLCdBRERSRVNTJ107CiAgdmFyIGksYz0wOwogIGZvcihpPTA7aTxmdWVydGVzLmxlbmd0aDtpKyspeyBpZih0LmluZGV4T2YoZnVlcnRlc1tpXSk+PTApeyBjKys7IH0gfQogIGlmKGM+PTIpeyByZXR1cm4gdHJ1ZTsgfQogIGlmKEVTVC50aXBvPT09J3VzYScgJiYgL1xiKElTU3xFWFB8RER8NER8NEZ8UkVTVHxFTkR8REwpXGIvLnRlc3QodCkpeyByZXR1cm4gdHJ1ZTsgfQogIHJldHVybiBmYWxzZTsKfQpmdW5jdGlvbiBwcm9jZXNhclJldmVyc28oZGF0YVVybCl7CiAgRVNULnJldmVyc29Paz1mYWxzZTsKICBidXN5KHRydWUpOwogIG1zZygnc3RBJywnTGV5ZW5kbyBlbCByZXZlcnNvLi4uJywnJyk7CiAgRVNULnJldmVyc29JbWc9ZGF0YVVybDsKICBzaG93SW1nKCdwQScsZGF0YVVybCk7CiAgaGFjZXJPY3IoZGF0YVVybCkudGhlbihmdW5jdGlvbih0ZXh0byl7CiAgICBpZih0ZXh0by5yZXBsYWNlKC9ccy9nLCcnKS5sZW5ndGg8MTAgJiYgIXJldmVyc29BY2VwdGFibGUodGV4dG8pKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RBJywnTm8gbGVcdTAwRUQgc3VmaWNpZW50ZSB0ZXh0byBlbiBlbCByZXZlcnNvLiBBY1x1MDBFOXJjYXRlLCBidWVuYSBsdXosIHkgdnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICB2YXIgY2FyYVBlbmQ9bnVsbDsKICAgIHZhciBsYWRvPWRldGVjdGFyTGFkbyh0ZXh0byxmYWxzZSk7CiAgICBpZihsYWRvPT09J2ZyZW50ZScpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbXNnKCdzdEEnLCdFc28gZXMgZWwgRlJFTlRFIChzZSB2ZSBsYSBmb3RvIHkgbG9zIGRhdG9zKS4gTmVjZXNpdG8gZWwgUkVWRVJTTzogZGlyZWNjaW9uZXMgbyBsYSB6b25hIE1SWi4gVnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICBpZihsYWRvIT09J3JldmVyc28nICYmICFyZXZlcnNvQWNlcHRhYmxlKHRleHRvKSl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBtc2coJ3N0QScsJ05vIHB1ZGUgY29uZmlybWFyIHF1ZSBzZWEgZWwgUkVWRVJTTy4gTXVlc3RyYSBsYXMgZGlyZWNjaW9uZXMgbyBsYSB6b25hIGRlIHJheWl0YXMvTVJaIHkgdnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICB2YXIgbmM9bm9tYnJlQ29pbmNpZGUoRVNULmVzY3JpdG8sdGV4dG8sbXJ6TGluZWFzKHRleHRvKS5sZW5ndGg+MCk7CiAgICBpZihuYy5oYXkgJiYgIW5jLm9rKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG5vbWJyZU5vQ29pbmNpZGVNc2coJ0VsIG5vbWJyZSBkZWwgZG9jdW1lbnRvICgnK25jLmxlaWRvKycpIG5vIGNvaW5jaWRlIGNvbiBsbyBxdWUgZXNjcmliaXN0ZS4gQ29ycmlnZSB0dSBub21icmUgZW4gZWwgcGFzbyAxOiBwdWVkZSB0ZW5lciAxIG8gMiBub21icmVzIHkgMSBvIDIgYXBlbGxpZG9zLicpOwogICAgICByZXR1cm47CiAgICB9CiAgICBFU1QucmV2ZXJzb09rPXRydWU7CiAgICBFU1QucmV2ZXJzb1RleHRvPXRleHRvOwogICAgbXNnKCdzdEEnLCdcdTI3MTMgUmV2ZXJzbyBsZVx1MDBFRGRvIGNvcnJlY3RhbWVudGUuJywnIzA4MCcpOwogICAgYnVzeShmYWxzZSk7CiAgICBhdmFuemFyKDQpOwogICAgc2V0VGltZW91dChmdW5jdGlvbigpeyB0cnl7IGFicmlyQ2FtKCc0JywndXNlcicsJ3N0VicsJ2JTZWxmaWUnKS5jYXRjaChmdW5jdGlvbigpe30pOyB9Y2F0Y2goZSl7fSB9LDUwMCk7CiAgfSkuY2F0Y2goZnVuY3Rpb24oZSl7CiAgICBidXN5KGZhbHNlKTsKICAgIG1zZygnc3RBJywnRXJyb3IgbGV5ZW5kbyBlbCByZXZlcnNvOiAnKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOicnKSsnLiBWdWVsdmUgYSBjYXB0dXJhci4nLCcjYzAwJyk7CiAgfSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IHBhc28gNDogc2VsZmllID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHByb2Nlc2FyU2VsZmllKCl7CiAgRVNULnNlbGZpZU9rPWZhbHNlOwogIHZhciBpbWc9Y2FwdHVyYXJWaWRlbygnNCcsMTA0OCk7CiAgaWYoIWltZyl7IG1zZygnc3RWJywnUHJpbWVybyBhYnJlIGxhIGNcdTAwRTFtYXJhIHkgcG9uIHR1IGNhcmEgZGVudHJvIGRlbCBtYXJjby4nLCcjYzAwJyk7IHJldHVybjsgfQogIEVTVC5zZWxmaWVJbWc9aW1nOwogIHNob3dJbWcoJ3BTJyxpbWcpOwogIGJ1c3kodHJ1ZSk7CiAgbXNnKCdzdFYnLCdDb21wYXJhbmRvIHR1IGNhcmEgY29uIGxhIGRlbCBkb2N1bWVudG8uLi4nLCcnKTsKICB2YXIgcERvYz1FU1QuY2FyYURvYz9Qcm9taXNlLnJlc29sdmUoRVNULmNhcmFEb2MpOmNvblRpbWVvdXQoZGV0ZWN0YXJDYXJhRG9jKEVTVC5mcmVudGVJbWd8fEVTVC5yZXZlcnNvSW1nfHwnJyksMTUwMDApLnRoZW4oZnVuY3Rpb24ocil7IHJldHVybiAociYmci5kZXRlY3Rpb24mJnIuZGVzY3JpcHRvcik/ci5kZXNjcmlwdG9yOm51bGw7IH0pOwogIHZhciBwU2VsPWNvblRpbWVvdXQoZGV0ZWN0YXJDYXJhRW4oaW1nKSwxNTAwMCk7CiAgUHJvbWlzZS5hbGwoW3BEb2MscFNlbF0pLnRoZW4oZnVuY3Rpb24ocil7CiAgICB2YXIgZERvYz1yWzBdLCBlblNlbD1yWzFdOwogICAgaWYoIWREb2MpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgZmFsbG9TZWxmaWUoJ05vIHB1ZGUgdmVyIGJpZW4gbGEgY2FyYSBlbiBsYSBmb3RvIGRlbCBkb2N1bWVudG8uIFZhbW9zIGEgcmVwZXRpciBsYSBmb3RvIGRlbCBkb2N1bWVudG8gY29uIG1lam9yIGx1ei4nKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgaWYoIWVuU2VsIHx8ICFlblNlbC5kZXRlY3Rpb24pewogICAgICBidXN5KGZhbHNlKTsKICAgICAgZmFsbG9TZWxmaWUoJ05vIHB1ZGUgdmVyIHR1IGNhcmEgZW4gbGEgc2VsZmllLiBNZWpvciBsYSBsdXosIHF1XHUwMEVEdGF0ZSBnb3JyYSBvIGxlbnRlcyBvc2N1cm9zLicpOwogICAgICByZXR1cm47CiAgICB9CiAgICB2YXIgZD1kaXN0RihkRG9jLGVuU2VsLmRlc2NyaXB0b3IpOwogICAgaWYoZDw9MC42MCl7CiAgICAgIEVTVC5zZWxmaWVPaz10cnVlOwogICAgICBFU1QuaW50ZW50b3M9MzsKICAgICAgbXNnKCdzdFYnLCdcdTI3MTMgVmVyaWZpY2FjaVx1MDBGM24gZmFjaWFsIHN1cGVyYWRhLiBQYXNhbmRvIGEgdHUgY2xhdmUuJywnIzA4MCcpOwogICAgICBidXN5KGZhbHNlKTsKICAgICAgYXZhbnphcig1KTsKICAgIH1lbHNlewogICAgICBidXN5KGZhbHNlKTsKICAgICAgZmFsbG9TZWxmaWUoJ1R1IGNhcmEgbm8gY29pbmNpZGUgY29uIGxhIGRlbCBkb2N1bWVudG8gKGRpc3RhbmNpYSAnK2QudG9GaXhlZCgyKSsnKS4nKTsKICAgIH0KICB9KS5jYXRjaChmdW5jdGlvbihlKXsKICAgIGJ1c3koZmFsc2UpOwogICAgZmFsbG9TZWxmaWUoJ0VsIHZlcmlmaWNhZG9yIGZhY2lhbCBubyBjYXJnXHUwMEYzOiAnKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOicnKSsnLiBSZXZpc2EgdHUgaW50ZXJuZXQgeSByZWludGVudGEuJyk7CiAgfSk7Cn0KZnVuY3Rpb24gZmFsbG9TZWxmaWUobSl7CiAgRVNULmludGVudG9zLS07CiAgaWYoRVNULmludGVudG9zPD0wKXsKICAgIEVTVC5pbnRlbnRvcz0zOwogICAgRVNULnNlbGZpZU9rPWZhbHNlOwogICAgbXNnKCdzdFYnLCdTZSBhZ290YXJvbiBsb3MgMyBpbnRlbnRvcy4gVm9sdmVtb3MgYSBsYSBmb3RvIGRlbCBkb2N1bWVudG87IHJldlx1MDBFRHNhbGEgeSB2dWVsdmUgYSB0b21hcmxhLCB5IHNlZ3VpbW9zIGVuIG9yZGVuIHBvciBsb3MgcGFzb3MuJywnI2E2MCcpOwogICAgYXZhbnphcigyKTsKICB9ZWxzZXsKICAgIG1zZygnc3RWJywnXHUyNzE3ICcrbSsnIFRlIHF1ZWRhbiAnK0VTVC5pbnRlbnRvcysnIGludGVudG8ocykuIFRvY2EgQ0FQVFVSQVIgZGUgbnVldm8uJywnI2MwMCcpOwogIH0KfQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyA1OiBjbGF2ZSArIFpJRCA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiB2YWxpZGFyQ2xhdmVzKCl7CiAgdmFyIGE9JCgnY2xhdmUnKSwgYj0kKCdjbGF2ZTInKSwgZD0kKCdkZXNnbG9zZScpOwogIGlmKCFhfHwhYil7IHJldHVybjsgfQogIGlmKCFiLnZhbHVlKXsgaWYoZCl7IGQudGV4dENvbnRlbnQ9Jyc7IH0gcmV0dXJuOyB9CiAgaWYoYS52YWx1ZT09PWIudmFsdWUpewogICAgaWYoZCl7IGQudGV4dENvbnRlbnQ9J1x1MjcxMyBMYXMgY2xhdmVzIGNvaW5jaWRlbi4gVG9jYSBlbCBib3RcdTAwRjNuIHBhcmEgY3JlYXIgdHUgWklELic7IGQuc3R5bGUuY29sb3I9JyMwODAnOyB9CiAgICBoYWJpbGl0YXJTdWJtaXQoKTsKICB9ZWxzZXsKICAgIGlmKGQpeyBkLnRleHRDb250ZW50PSdcdTI3MTcgTGFzIGNsYXZlcyBubyBjb2luY2lkZW4uIENvcnJcdTAwRURnZWxhcyBhcXVcdTAwRUQsIG5vIHNhbGVzIGRlbCBwYXNvIDUgaGFzdGEgcXVlIGNvaW5jaWRhbi4nOyBkLnN0eWxlLmNvbG9yPScjYzAwJzsgfQogIH0KfQpmdW5jdGlvbiBoYWJpbGl0YXJTdWJtaXQoKXsKICB2YXIgcHM9JCgncHM1Jyk7CiAgaWYoIXBzKXsgcmV0dXJuOyB9CiAgdmFyIGJ0bnM9cHMucXVlcnlTZWxlY3RvckFsbCgnYnV0dG9uLCBpbnB1dFt0eXBlPWJ1dHRvbl0sIGlucHV0W3R5cGU9c3VibWl0XSwgW3JvbGU9YnV0dG9uXScpLCBpLCBoYXk9ZmFsc2U7CiAgZm9yKGk9MDtpPGJ0bnMubGVuZ3RoO2krKyl7CiAgICB2YXIgZXNTdWJtaXQ9ZmFsc2U7CiAgICB0cnl7IGVzU3VibWl0PSgoYnRuc1tpXS5nZXRBdHRyaWJ1dGUoJ3R5cGUnKXx8JycpLnRvTG93ZXJDYXNlKCk9PT0nc3VibWl0Jyk7IH1jYXRjaChlVCl7IGVzU3VibWl0PWZhbHNlOyB9CiAgICB2YXIgdD0oKGJ0bnNbaV0udGV4dENvbnRlbnR8fCcnKSsnICcrKGJ0bnNbaV0udmFsdWV8fCcnKSkudG9VcHBlckNhc2UoKTsKICAgIGlmKGVzU3VibWl0fHwvQ1JFQVJ8UkVHSVNUUnxGSU5BTElaQVJ8Q09OVElOVUFSfEVOVklBUnxBQ0VQVEFSfFpJRC8udGVzdCh0KSl7IGJ0bnNbaV0uZGlzYWJsZWQ9ZmFsc2U7IGhheT10cnVlOyB9CiAgfQogIGlmKCFoYXkpeyBtc2coJ3p5Q2xhdmVPaycsJ1NpIG5vIHZlcyBlbCBib3RcdTAwRjNuIHBhcmEgY3JlYXIgdHUgWklELCBhdlx1MDBFRHNhbWUuJywnI2E2MCcpOyB9Cn0KCi8qID09PT09PT09PT09PT09PT09IHBhc28gNTogZmlsdHJvIGZpbmFsIGFudGVzIGRlbCBlbnZpbyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBjbGF2ZXNMaXN0YXMoKXsKICB2YXIgYT0kKCdjbGF2ZScpLCBiPSQoJ2NsYXZlMicpOwogIHJldHVybiAhIShhJiZiJiZhLnZhbHVlJiZhLnZhbHVlPT09Yi52YWx1ZSYmU3RyaW5nKGEudmFsdWUpLmxlbmd0aD49OCk7Cn0KZnVuY3Rpb24gZm90b3NDb21wbGV0YXMoKXsKICByZXR1cm4gISEoRVNULmZyZW50ZU9rJiZFU1Quc2VsZmllT2smJighRVNULm5lY2VzaXRhUmV2ZXJzb3x8RVNULnJldmVyc29PaykpOwp9CmZ1bmN0aW9uIHJlbGxlbmFyRm90b3NGb3JtdWxhcmlvKCl7CiAgdmFyIHBzNT0kKCdwczUnKTsKICB2YXIgZj1wczU/KHBzNS5xdWVyeVNlbGVjdG9yKCdmb3JtJyl8fG51bGwpOm51bGw7CiAgaWYoIWYpeyB0cnl7IGY9ZG9jdW1lbnQucXVlcnlTZWxlY3RvcignZm9ybScpOyB9Y2F0Y2goZSl7IGY9bnVsbDsgfSB9CiAgaWYoIWZ8fCFmLmVsZW1lbnRzKXsgcmV0dXJuOyB9CiAgdmFyIGVscz1mLmVsZW1lbnRzLCBpOwogIGZvcihpPTA7aTxlbHMubGVuZ3RoO2krKyl7CiAgICB2YXIgZWw9ZWxzW2ldOwogICAgaWYoIWVsKXsgY29udGludWU7IH0KICAgIHZhciB0YWc9ZWwudGFnTmFtZXx8Jyc7CiAgICBpZih0YWchPT0nSU5QVVQnJiZ0YWchPT0nVEVYVEFSRUEnKXsgY29udGludWU7IH0KICAgIHZhciB0PSgoZWwudHlwZXx8JycpKycnKS50b0xvd2VyQ2FzZSgpOwogICAgaWYodGFnPT09J0lOUFVUJyYmdCE9PSdoaWRkZW4nJiZ0IT09J3RleHQnKXsgY29udGludWU7IH0KICAgIGlmKChlbC52YWx1ZXx8JycpLmxlbmd0aD4xMCl7IGNvbnRpbnVlOyB9CiAgICB2YXIgbm9tPSgoKGVsLm5hbWV8fCcnKSsnJykrJyAnKygoZWwuaWR8fCcnKSsnJykpLnRvTG93ZXJDYXNlKCk7CiAgICBpZigvZnJlbnRlfGZyb250YWx8YW52ZXJzb3xmb3RvZnxkb2MxfGZvdG8xLy50ZXN0KG5vbSkpeyBpZihFU1QuZnJlbnRlSW1nKXsgZWwudmFsdWU9RVNULmZyZW50ZUltZzsgfSB9CiAgICBlbHNlIGlmKC9yZXZlcnNvfGRvcnNvfHRyYXNlcmF8Zm90b3Jldnxkb2MyfGZvdG8yLy50ZXN0KG5vbSkpeyBpZihFU1QucmV2ZXJzb0ltZyl7IGVsLnZhbHVlPUVTVC5yZXZlcnNvSW1nOyB9IH0KICAgIGVsc2UgaWYoL3NlbGZpZXxyb3N0cm98ZmFjaWFsfGNhcmF8ZmFjZXxmb3RvM3xmb3Rvcy8udGVzdChub20pKXsgaWYoRVNULnNlbGZpZUltZyl7IGVsLnZhbHVlPUVTVC5zZWxmaWVJbWc7IH0gfQogIH0KfQpmdW5jdGlvbiBndWFyZGlhRW52aW8oZXYpewogIGZ1bmN0aW9uIGJsb3F1ZWFyKCl7CiAgICBpZihldil7IHRyeXsgaWYoZXYucHJldmVudERlZmF1bHQpeyBldi5wcmV2ZW50RGVmYXVsdCgpOyB9IGlmKGV2LnN0b3BQcm9wYWdhdGlvbil7IGV2LnN0b3BQcm9wYWdhdGlvbigpOyB9IGlmKGV2LnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbil7IGV2LnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbigpOyB9IH1jYXRjaChlKXt9IH0KICAgIHJldHVybiBmYWxzZTsKICB9CiAgaWYoIWNsYXZlc0xpc3RhcygpKXsKICAgIG1zZygnenlDbGF2ZU9rJywnQW50ZXMgZGUgY3JlYXIgdHUgWklEOiBlc2NyaWJlIGxhIGNsYXZlIHkgcmVwaXRlbGEgKG1pbiA4LCBpZ3VhbGVzKS4nLCcjYzAwJyk7CiAgICByZXR1cm4gYmxvcXVlYXIoKTsKICB9CiAgaWYoIUVTVC5ub21icmVPayl7CiAgICBtc2coJ3p5RXJyTm9tYnJlJywnRmFsdGEgdHUgbm9tYnJlLiBFc2NyaWJlbG8geSB0b2NhIENvbnRpbnVhci4nLCcjYzAwJyk7CiAgICBhdmFuemFyKDEpOwogICAgcmV0dXJuIGJsb3F1ZWFyKCk7CiAgfQogIGlmKEVTVC5mcmVudGVUZXh0byl7CiAgICB2YXIgbmNGPW5vbWJyZUNvaW5jaWRlKEVTVC5lc2NyaXRvLCBFU1QuZnJlbnRlVGV4dG8sIGZhbHNlKTsKICAgIGlmKG5jRi5oYXkgJiYgIW5jRi5vayl7CiAgICAgIG1zZygnenlFcnJOb21icmUnLCdUdSBub21icmUgKCcrRVNULmVzY3JpdG8rJykgbm8gY29pbmNpZGUgY29uIGVsIGRvY3VtZW50byB5YSB2ZXJpZmljYWRvICgnK25jRi5sZWlkbysnKS4gQ29ycmlnZSB0dSBub21icmUgZW4gZWwgcGFzbyAxLicsJyNjMDAnKTsKICAgICAgYXZhbnphcigxKTsKICAgICAgcmV0dXJuIGJsb3F1ZWFyKCk7CiAgICB9CiAgfQogIGlmKCFFU1QuZnJlbnRlT2spewogICAgbXNnKCdzdEYnLCBFU1QuZnJlbnRlSW1nPydMYSBmb3RvIGRlbCBGUkVOVEUgbm8gcGFzXHUwMEYzIGxhIGxlY3R1cmEuIFRlIGxsZXZvIGFsIHBhc28gMiBwYXJhIHJlcGV0aXJsYSAobGFzIGRlbWFzIGZvdG9zIHNlIGNvbnNlcnZhbikuJzonRmFsdGEgbGEgZm90byBkZWwgRlJFTlRFIGRlbCBkb2N1bWVudG8uIFRlIGxsZXZvIGFsIHBhc28gMiBwYXJhIHRvbWFybGEgKGxhcyBkZW1hcyBmb3RvcyBzZSBjb25zZXJ2YW4pLicsJyNjMDAnKTsKICAgIGF2YW56YXIoMik7CiAgICByZXR1cm4gYmxvcXVlYXIoKTsKICB9CiAgaWYoRVNULm5lY2VzaXRhUmV2ZXJzbyYmIUVTVC5yZXZlcnNvT2spewogICAgbXNnKCdzdEEnLCBFU1QucmV2ZXJzb0ltZz8nTGEgZm90byBkZWwgUkVWRVJTTyBubyBwYXNcdTAwRjMgbGEgbGVjdHVyYS4gVGUgbGxldm8gYWwgcGFzbyAzIHBhcmEgcmVwZXRpcmxhLic6J0ZhbHRhIGxhIGZvdG8gZGVsIFJFVkVSU08gZGVsIGRvY3VtZW50by4gVGUgbGxldm8gYWwgcGFzbyAzIHBhcmEgdG9tYXJsYS4nLCcjYzAwJyk7CiAgICBhdmFuemFyKDMpOwogICAgcmV0dXJuIGJsb3F1ZWFyKCk7CiAgfQogIGlmKCFFU1Quc2VsZmllSW1nKXsKICAgIG1zZygnc3RWJywnRmFsdGEgbGEgc2VsZmllLiBUZSBsbGV2byBhbCBwYXNvIDQgcGFyYSB0b21hcmxhLicsJyNjMDAnKTsKICAgIGF2YW56YXIoNCk7CiAgICByZXR1cm4gYmxvcXVlYXIoKTsKICB9CiAgaWYoIUVTVC5zZWxmaWVPayl7CiAgICBtc2coJ3N0VicsJ0xhIHNlbGZpZSBOTyBwYXNcdTAwRjMgbGEgdmVyaWZpY2FjaVx1MDBGM24gZmFjaWFsLiBUZSBsbGV2byBhbCBwYXNvIDQgcGFyYSByZXBldGlybGE6IGJ1ZW5hIGx1eiB5IGNhcmEgY2VudHJhZGEgZW4gZWwgXHUwMEYzdmFsby4nLCcjYzAwJyk7CiAgICBhdmFuemFyKDQpOwogICAgcmV0dXJuIGJsb3F1ZWFyKCk7CiAgfQogIHJlbGxlbmFyRm90b3NGb3JtdWxhcmlvKCk7CiAgbXNnKCd6eUNsYXZlT2snLCdUb2RvIHZlcmlmaWNhZG86IGNyZWFuZG8gdHUgWklELi4uJywnIzA4MCcpOwogIHJldHVybiB0cnVlOwp9CgovKiA9PT09PT09PT09PT09PT09PSB2MTM6IGFudGktYmxvcXVlbyBsZWdhZG8gKyBkaWFnbm9zdGljbyBlbiB2aXZvID09PT09PT09PT09PT09PT09CiAgIEVsIGVycm9yIHJvam8gIkZhbHRhIGxhIGZvdG8gZnJvbnRhbCAocGFzbyAyKSIgTk8gZXN0YSBlbiBlc3RlIG51Y2xlbzogdmllbmUgZGUKICAgY29kaWdvIHZpZWpvIGRlIHN1cGVyYXBwLnB5IGZ1ZXJhIGRlbCBibG9xdWUgbWFyY2FkbyAodW4gc2NyaXB0IGxlZ2FkbyBxdWUKICAgcmUtdmFsaWRhIGFsIGVudmlhciB5IGJsb3F1ZWEsIG8gdGV4dG8gcmVzaWR1YWwgZW4gcGFudGFsbGEpLiBBcXVpIHNlIGhhY2U6CiAgIDEpIGxpbXBpYUxlZ2FkbygpOiBkZXRlY3RhIGZ1bmNpb25lcyBnbG9iYWxlcyBjdXlvIGNvZGlnbyBjb250aWVuZSBlc2UgdGV4dG8geQogICAgICBsYXMgdnVlbHZlIG5vLW9wOyBhZGVtYXMgc2UgdHJhZ2EgbG9zIGFsZXJ0L2NvbmZpcm0gY29uIGVzZSB0ZXh0by4KICAgMikgcHJlZW1wdEVudmlvKCk6IG95ZW50ZSBlbiBXSU5ET1cgZW4gZmFzZSBjYXB0dXJhICh3aW5kb3cgY29ycmUgQU5URVMgcXVlCiAgICAgIGRvY3VtZW50IHkgcXVlIGVsIGZvcm0pLiBTaSBUT0RPIHlhIHBhc28sIHJlbGxlbmEgbGFzIGZvdG9zLCBhdmlzYSAiY3JlYW5kbwogICAgICB0dSBaSUQiIHkgY29ydGEgYSBsb3Mgb3llbnRlcyBsZWdhZG9zIGNvbiBzdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24sIGRlamFuZG8KICAgICAgcXVlIGVsIGVudmlvIG5hdGl2byBkZWwgZm9ybXVsYXJpbyBzaWdhLiBTaSBmYWx0YSBhbGdvLCBubyB0b2NhIG5hZGEuCiAgIDMpIGJhcnJlTWVuc2FqZXMoKTogYm9ycmEgdGV4dG9zIHJvam9zIHJlc2lkdWFsZXMgeSByZS1oYWJpbGl0YSBib3RvbmVzCiAgICAgIGRlc2hhYmlsaXRhZG9zIFNPTE8gY3VhbmRvIHRvZG8geWEgcGFzby4KICAgNCkgcGFuZWxEaWFnKCk6IGJvdG9uICJpIiBmaWpvIGFiYWpvIGEgbGEgZGVyZWNoYTsgbXVlc3RyYSBxdWUgYmxvcXVlYSwgbG9zCiAgICAgIGNhbXBvcyBkZWwgZm9ybXVsYXJpbywgZWwgYWN0aW9uL21ldGhvZCB5IGxhcyBmdW5jaW9uZXMgbGVnYWRhcyBoYWxsYWRhcy4KKi8KdmFyIERJQUc9e2xlZ2FkbzpbXSxhbGVydGFzOjAsdWx0U3VibWl0OicnLHVsdENsaWNrOicnfTsKdmFyIFRYX1JPSkE9L2ZhbHRhLnswLDI0fWZyb250YWx8ZnJvbnRhbC57MCwyNH1wYXNvXHMqMi9pOwpmdW5jdGlvbiBob3JhMTMoKXsKICB0cnl7IHJldHVybiAobmV3IERhdGUoKSkudG9JU09TdHJpbmcoKS5zbGljZSgxMSwxOSk7IH1jYXRjaChlKXsgcmV0dXJuICcnOyB9Cn0KZnVuY3Rpb24gdG9kb09rUGFyYUNyZWFyKCl7CiAgaWYoIWNsYXZlc0xpc3RhcygpKXsgcmV0dXJuIGZhbHNlOyB9CiAgaWYoIUVTVC5ub21icmVPayl7IHJldHVybiBmYWxzZTsgfQogIGlmKCFFU1QuZnJlbnRlT2speyByZXR1cm4gZmFsc2U7IH0KICBpZihFU1QubmVjZXNpdGFSZXZlcnNvJiYhRVNULnJldmVyc29Payl7IHJldHVybiBmYWxzZTsgfQogIGlmKCFFU1Quc2VsZmllSW1nfHwhRVNULnNlbGZpZU9rKXsgcmV0dXJuIGZhbHNlOyB9CiAgaWYoRVNULmZyZW50ZVRleHRvKXsKICAgIHZhciBuYz1ub21icmVDb2luY2lkZShFU1QuZXNjcml0bywgRVNULmZyZW50ZVRleHRvLCBmYWxzZSk7CiAgICBpZihuYy5oYXkmJiFuYy5vayl7IHJldHVybiBmYWxzZTsgfQogIH0KICByZXR1cm4gdHJ1ZTsKfQpmdW5jdGlvbiBsaW1waWFMZWdhZG8oKXsKICB2YXIgbm9tYnJlcz1bXTsKICB0cnl7CiAgICB2YXIga3M9T2JqZWN0LmdldE93blByb3BlcnR5TmFtZXMoVyk7CiAgICBmb3IodmFyIGk9MDtpPGtzLmxlbmd0aDtpKyspewogICAgICB2YXIgaz1rc1tpXTsKICAgICAgdHJ5ewogICAgICAgIHZhciB2PVdba107CiAgICAgICAgaWYodHlwZW9mIHY9PT0nZnVuY3Rpb24nJiZ2LnRvU3RyaW5nJiZUWF9ST0pBLnRlc3Qodi50b1N0cmluZygpKSYmayE9PSdsaW1waWFMZWdhZG8nKXsKICAgICAgICAgIG5vbWJyZXMucHVzaChrKTsKICAgICAgICAgIFdba109ZnVuY3Rpb24oKXt9OwogICAgICAgIH0KICAgICAgfWNhdGNoKGUpe30KICAgIH0KICB9Y2F0Y2goZSl7fQogIHRyeXsKICAgIGlmKHR5cGVvZiBXLmFsZXJ0PT09J2Z1bmN0aW9uJyYmIVcuX196eUFsZXJ0MTMpewogICAgICB2YXIgYTA9Vy5hbGVydDsKICAgICAgVy5hbGVydD1mdW5jdGlvbihtKXsgaWYoVFhfUk9KQS50ZXN0KFN0cmluZyhtPT1udWxsPycnOm0pKSl7IERJQUcuYWxlcnRhcysrOyByZXR1cm47IH0gcmV0dXJuIGEwLmFwcGx5KFcsYXJndW1lbnRzKTsgfTsKICAgICAgVy5fX3p5QWxlcnQxMz10cnVlOwogICAgfQogICAgaWYodHlwZW9mIFcuY29uZmlybT09PSdmdW5jdGlvbicmJiFXLl9fenlDb25maXJtMTQpewogICAgICB2YXIgYzA9Vy5jb25maXJtOwogICAgICBXLmNvbmZpcm09ZnVuY3Rpb24obSl7IGlmKFRYX1JPSkEudGVzdChTdHJpbmcobT09bnVsbD8nJzptKSkpeyBESUFHLmFsZXJ0YXMrKzsgcmV0dXJuIHRydWU7IH0gcmV0dXJuIGMwLmFwcGx5KFcsYXJndW1lbnRzKTsgfTsKICAgICAgVy5fX3p5Q29uZmlybTE0PXRydWU7CiAgICB9CiAgfWNhdGNoKGUpe30KICBESUFHLmxlZ2Fkbz1ub21icmVzOwogIGlmKG5vbWJyZXMubGVuZ3RoKXsgbG9nKCd2MTQ6IGZ1bmNpb25lcyBsZWdhZGFzIG5ldXRyYWxpemFkYXM6Jywgbm9tYnJlcy5qb2luKCcsJykpOyB9Cn0KZnVuY3Rpb24gYmFycmVNZW5zYWplcygpewogIGlmKCF0b2RvT2tQYXJhQ3JlYXIoKSl7IHJldHVybjsgfQogIHRyeXsKICAgIHZhciBub2Rlcz1kb2N1bWVudC5ib2R5P2RvY3VtZW50LmJvZHkucXVlcnlTZWxlY3RvckFsbCgnZGl2LHNwYW4scCxsaSxzZWN0aW9uJyk6W107CiAgICBmb3IodmFyIGk9MDtpPG5vZGVzLmxlbmd0aCYmaTw4MDA7aSsrKXsKICAgICAgdmFyIGVsPW5vZGVzW2ldOwogICAgICBpZighZWx8fGVsLmlkPT09J3p5UmVzdW1lbjUnfHxlbC5pZD09PSd6eURpYWcxNCcpeyBjb250aW51ZTsgfQogICAgICB2YXIgdD1lbC50ZXh0Q29udGVudHx8Jyc7CiAgICAgIGlmKFRYX1JPSkEudGVzdCh0KSYmdC5sZW5ndGg8MzAwKXsKICAgICAgICBlbC50ZXh0Q29udGVudD0nJzsKICAgICAgICBpZihlbC5zdHlsZSl7IGVsLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgICAgIH0KICAgIH0KICB9Y2F0Y2goZSl7fQogIHRyeXsKICAgIHZhciBwczU9JCgncHM1Jyk7CiAgICBpZihwczUpewogICAgICB2YXIgYnM9cHM1LnF1ZXJ5U2VsZWN0b3JBbGwoJ2J1dHRvbiwgaW5wdXRbdHlwZT1zdWJtaXRdJyk7CiAgICAgIGZvcih2YXIgaz0wO2s8YnMubGVuZ3RoO2srKyl7IGlmKGJzW2tdLmRpc2FibGVkKXsgYnNba10uZGlzYWJsZWQ9ZmFsc2U7IH0gfQogICAgfQogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gcGludGFEaWFnKCl7CiAgdmFyIGI9JCgnenlEaWFnMTQnKTsKICBpZighYnx8Yi5zdHlsZS5kaXNwbGF5PT09J25vbmUnKXsgcmV0dXJuOyB9CiAgdmFyIEw9W107CiAgTC5wdXNoKCdudWNsZW86IFJFViBGIHYxNCBhY3Rpdm8nKTsKICBMLnB1c2goJ2VzdGFkbzogbm9tYnJlT2s9JytFU1Qubm9tYnJlT2srJyBmcmVudGVPaz0nK0VTVC5mcmVudGVPaysnIHJldmVyc29Paz0nK0VTVC5yZXZlcnNvT2srJyAobmVjZXNpdGFSZXZlcnNvPScrRVNULm5lY2VzaXRhUmV2ZXJzbysnKSBzZWxmaWVPaz0nK0VTVC5zZWxmaWVPaysnIHBhc289JytFU1QucGFzbyk7CiAgTC5wdXNoKCd0b2RvT2tQYXJhQ3JlYXI6ICcrKHRvZG9Pa1BhcmFDcmVhcigpPydTSSc6J05PJykpOwogIEwucHVzaCgnbGVnYWRvIG5ldXRyYWxpemFkbzogJysoRElBRy5sZWdhZG8ubGVuZ3RoP0RJQUcubGVnYWRvLmpvaW4oJywgJyk6JyhuaW5ndW5hIGZ1bmNpb24gY29uIGVsIHRleHRvIHJvam8pJykpOwogIEwucHVzaCgnYWxlcnRhcyByb2phcyB0cmFnYWRhczogJytESUFHLmFsZXJ0YXMpOwogIHZhciBmPW51bGw7CiAgdHJ5eyB2YXIgcHM1PSQoJ3BzNScpOyBmPXBzNT8ocHM1LnF1ZXJ5U2VsZWN0b3IoJ2Zvcm0nKXx8ZG9jdW1lbnQucXVlcnlTZWxlY3RvcignZm9ybScpKTpudWxsOyB9Y2F0Y2goZSl7fQogIGlmKGYpewogICAgTC5wdXNoKCdmb3JtIGFjdGlvbjogJysoZi5nZXRBdHRyaWJ1dGUoJ2FjdGlvbicpfHwnKGVzdGEgbWlzbWEgcGFnaW5hKScpKycgIG1ldGhvZDogJysoKChmLm1ldGhvZHx8J2dldCcpKycnKS50b1VwcGVyQ2FzZSgpKSk7CiAgICB0cnl7CiAgICAgIHZhciBlbHM9Zi5lbGVtZW50cywgdmlzPVtdOwogICAgICBmb3IodmFyIGk9MDtpPGVscy5sZW5ndGgmJnZpcy5sZW5ndGg8MTY7aSsrKXsKICAgICAgICB2YXIgZWw9ZWxzW2ldOwogICAgICAgIGlmKCFlbHx8IWVsLm5hbWUpeyBjb250aW51ZTsgfQogICAgICAgIHZpcy5wdXNoKGVsLm5hbWUrJz0nKygoKGVsLnZhbHVlfHwnJykubGVuZ3RoPjApPygnT0soJytlbC52YWx1ZS5sZW5ndGgrJyknKTonVkFDSU8nKSk7CiAgICAgIH0KICAgICAgTC5wdXNoKCdjYW1wb3M6ICcrKHZpcy5qb2luKCcgfCAnKXx8JyhuaW5ndW5vIGNvbiBuYW1lKScpKTsKICAgIH1jYXRjaChlKXt9CiAgfWVsc2V7CiAgICBMLnB1c2goJ2Zvcm06IE5PIGhheSA8Zm9ybT4gKGVsIGxlZ2FkbyBjcmVhIGVsIFpJRCBwb3IgSlMvZmV0Y2gpJyk7CiAgfQogIHRyeXsKICAgIHZhciBjYW5kPWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoJ1tvbmNsaWNrXSxbb25zdWJtaXRdJyk7CiAgICB2YXIgaGl0cz1bXTsKICAgIGZvcih2YXIgaj0wO2o8Y2FuZC5sZW5ndGgmJmhpdHMubGVuZ3RoPDQ7aisrKXsKICAgICAgdmFyIGM9Y2FuZFtqXTsKICAgICAgdmFyIHM9KChjLmdldEF0dHJpYnV0ZSgnb25jbGljaycpfHwnJykrJyAnKyhjLmdldEF0dHJpYnV0ZSgnb25zdWJtaXQnKXx8JycpKS50cmltKCk7CiAgICAgIGlmKFRYX1JPSkEudGVzdChzKSl7IGhpdHMucHVzaCgoKGMuaWR8fGMudGFnTmFtZSl8fCc/JykrJzogJytzLnJlcGxhY2UoL1xzKy9nLCcgJykuc2xpY2UoMCwxNTApKTsgfQogICAgfQogICAgaWYoaGl0cy5sZW5ndGgpewogICAgICBMLnB1c2goJ3ZhbGlkYWNpb24gbGVnYWRhIGVuIGF0cmlidXRvczonKTsKICAgICAgZm9yKHZhciBxPTA7cTxoaXRzLmxlbmd0aDtxKyspeyBMLnB1c2goJyAgJytoaXRzW3FdKTsgfQogICAgfQogIH1jYXRjaChlKXt9CiAgaWYoRElBRy51bHRDbGljayl7IEwucHVzaCgndWx0aW1vIGNsaWNrOiAnK0RJQUcudWx0Q2xpY2spOyB9CiAgaWYoRElBRy51bHRTdWJtaXQpeyBMLnB1c2goJ3VsdGltbyBzdWJtaXQ6ICcrRElBRy51bHRTdWJtaXQpOyB9CiAgYi50ZXh0Q29udGVudD1MLmpvaW4oJ1xuJyk7Cn0KZnVuY3Rpb24gcGFuZWxEaWFnKCl7CiAgdHJ5ewogICAgaWYoJCgnenlEaWFnMTQnKSl7IHJldHVybjsgfQogICAgdmFyIGNoaXA9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2Jyk7CiAgICBjaGlwLmlkPSd6eURpYWdDaGlwMTQnOwogICAgY2hpcC5zdHlsZS5jc3NUZXh0PSdwb3NpdGlvbjpmaXhlZDtyaWdodDoxMHB4O2JvdHRvbToxMHB4O3otaW5kZXg6MjE0NzQ4MzY0Njt3aWR0aDozMHB4O2hlaWdodDozMHB4O2JvcmRlci1yYWRpdXM6NTAlO2JhY2tncm91bmQ6IzExMTtjb2xvcjojMGYwO2ZvbnQ6Ym9sZCAxNXB4LzMwcHggbW9ub3NwYWNlO3RleHQtYWxpZ246Y2VudGVyO2N1cnNvcjpwb2ludGVyO29wYWNpdHk6LjU7Ym94LXNoYWRvdzowIDFweCA0cHggcmdiYSgwLDAsMCwuNCk7JzsKICAgIGNoaXAudGV4dENvbnRlbnQ9J2knOwogICAgY2hpcC50aXRsZT0nZGlhZ25vc3RpY28gdjE0JzsKICAgIGNoaXAuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKCl7CiAgICAgIHZhciBiPSQoJ3p5RGlhZzE0Jyk7CiAgICAgIGlmKCFiKXsgcmV0dXJuOyB9CiAgICAgIHZhciB2aXNpYmxlPShiLnN0eWxlLmRpc3BsYXk9PT0nbm9uZScpOwogICAgICBiLnN0eWxlLmRpc3BsYXk9dmlzaWJsZT8nYmxvY2snOidub25lJzsKICAgICAgaWYodmlzaWJsZSl7IHBpbnRhRGlhZygpOyB9CiAgICB9KTsKICAgIHZhciBib3g9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgncHJlJyk7CiAgICBib3guaWQ9J3p5RGlhZzE0JzsKICAgIGJveC5zdHlsZS5jc3NUZXh0PSdkaXNwbGF5Om5vbmU7cG9zaXRpb246Zml4ZWQ7bGVmdDo4cHg7cmlnaHQ6OHB4O2JvdHRvbTo0OHB4O3otaW5kZXg6MjE0NzQ4MzY0NTttYXgtaGVpZ2h0OjU1JTtvdmVyZmxvdzphdXRvO2JhY2tncm91bmQ6IzBiMGIwYjtjb2xvcjojMGYwO2ZvbnQ6MTFweC8xLjQ1IG1vbm9zcGFjZTtwYWRkaW5nOjEwcHg7Ym9yZGVyLXJhZGl1czo4cHg7d2hpdGUtc3BhY2U6cHJlLXdyYXA7d29yZC1icmVhazpicmVhay1hbGw7Ym94LXNoYWRvdzowIDRweCAxNnB4IHJnYmEoMCwwLDAsLjUpO21hcmdpbjowOyc7CiAgICBib3gudGV4dENvbnRlbnQ9J251Y2xlbzogUkVWIEYgdjE0JzsKICAgIGRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQoYm94KTsKICAgIGRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQoY2hpcCk7CiAgfWNhdGNoKGUpe30KfQpmdW5jdGlvbiBwcmVlbXB0RW52aW8oKXsKICBXLmFkZEV2ZW50TGlzdGVuZXIoJ3N1Ym1pdCcsZnVuY3Rpb24oZXYpewogICAgdHJ5ewogICAgICB2YXIgZj1ldi50YXJnZXQ7CiAgICAgIGlmKCFmfHwhZi50YWdOYW1lfHxmLnRhZ05hbWUhPT0nRk9STScpeyByZXR1cm47IH0KICAgICAgRElBRy51bHRTdWJtaXQ9aG9yYTEzKCkrJyAnKyhmLmdldEF0dHJpYnV0ZSgnYWN0aW9uJyl8fCcoZXN0YSBtaXNtYSBwYWdpbmEpJykrJyBbJysoKChmLm1ldGhvZHx8J2dldCcpKycnKS50b1VwcGVyQ2FzZSgpKSsnXSc7CiAgICAgIHZhciBwczU9JCgncHM1Jyk7CiAgICAgIGlmKHBzNSYmcHM1LmNvbnRhaW5zKGYpJiZ0b2RvT2tQYXJhQ3JlYXIoKSl7CiAgICAgICAgcmVsbGVuYXJGb3Rvc0Zvcm11bGFyaW8oKTsKICAgICAgICBiYXJyZU1lbnNhamVzKCk7CiAgICAgICAgbXNnKCd6eUNsYXZlT2snLCdUb2RvIHZlcmlmaWNhZG86IGNyZWFuZG8gdHUgWklELi4uJywnIzA4MCcpOwogICAgICAgIHBpbnRhRGlhZygpOwogICAgICAgIGlmKGV2LnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbil7IGV2LnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbigpOyB9CiAgICAgIH0KICAgIH1jYXRjaChlKXt9CiAgfSx0cnVlKTsKICBXLmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbihldil7CiAgICB0cnl7CiAgICAgIHZhciBwczU9JCgncHM1JyksIGVsPWV2LnRhcmdldDsKICAgICAgaWYoIXBzNXx8IWVsfHwhcHM1LmNvbnRhaW5zKGVsKSl7IHJldHVybjsgfQogICAgICB2YXIgYj1lbCwgZXNCb3Rvbj1mYWxzZSwgcHJvZj0wOwogICAgICB3aGlsZShiJiZiIT09cHM1JiZwcm9mPDYpewogICAgICAgIHZhciB0Zz1iLnRhZ05hbWV8fCcnOwogICAgICAgIGlmKHRnPT09J0JVVFRPTid8fCh0Zz09PSdJTlBVVCcmJigoKGIudHlwZXx8JycpPT09J3N1Ym1pdCcpfHwoKGIudHlwZXx8JycpPT09J2ltYWdlJykpKXx8KGIuZ2V0QXR0cmlidXRlJiZiLmdldEF0dHJpYnV0ZSgncm9sZScpPT09J2J1dHRvbicpKXsgZXNCb3Rvbj10cnVlOyBicmVhazsgfQogICAgICAgIGI9Yi5wYXJlbnROb2RlOyBwcm9mKys7CiAgICAgIH0KICAgICAgaWYoIWVzQm90b258fCFiKXsgcmV0dXJuOyB9CiAgICAgIHZhciB0eT0oYi50YWdOYW1lPT09J0JVVFRPTicpPygoKGIuZ2V0QXR0cmlidXRlKCd0eXBlJykpfHwnc3VibWl0JykrJycpLnRvTG93ZXJDYXNlKCk6KCgoYi50eXBlfHwnJykrJycpLnRvTG93ZXJDYXNlKCkpOwogICAgICB2YXIgZW5Gb3JtPWZhbHNlLCBwPWI7CiAgICAgIHdoaWxlKHApeyBpZihwLnRhZ05hbWU9PT0nRk9STScpeyBlbkZvcm09dHJ1ZTsgYnJlYWs7IH0gcD1wLnBhcmVudE5vZGU7IH0KICAgICAgRElBRy51bHRDbGljaz1ob3JhMTMoKSsnICcrKGIuaWR8fGIudGFnTmFtZSkrJyB0eXBlPScrdHkrJyBmb3JtPScrKGVuRm9ybT8nc2knOidubycpOwogICAgICBpZih0eT09PSdzdWJtaXQnJiZlbkZvcm0mJnRvZG9Pa1BhcmFDcmVhcigpKXsKICAgICAgICByZWxsZW5hckZvdG9zRm9ybXVsYXJpbygpOwogICAgICAgIGJhcnJlTWVuc2FqZXMoKTsKICAgICAgICBtc2coJ3p5Q2xhdmVPaycsJ1RvZG8gdmVyaWZpY2FkbzogY3JlYW5kbyB0dSBaSUQuLi4nLCcjMDgwJyk7CiAgICAgICAgaWYoZXYuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKXsgZXYuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKCk7IH0KICAgICAgfQogICAgfWNhdGNoKGUpe30KICB9LHRydWUpOwp9CgpmdW5jdGlvbiBlbmdhbmNoYXJFbnZpb0ZpbmFsKCl7CiAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignc3VibWl0JyxmdW5jdGlvbihldil7CiAgICB0cnl7CiAgICAgIHZhciBwczU9JCgncHM1JyksIGY9ZXYudGFyZ2V0OwogICAgICBpZihwczUmJmYmJnBzNS5jb250YWlucyhmKSl7IGd1YXJkaWFFbnZpbyhldik7IH0KICAgIH1jYXRjaChlKXt9CiAgfSx0cnVlKTsKICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oZXYpewogICAgdHJ5ewogICAgICB2YXIgcHM1PSQoJ3BzNScpLCBlbD1ldi50YXJnZXQ7CiAgICAgIGlmKCFwczV8fCFlbHx8IXBzNS5jb250YWlucyhlbCkpeyByZXR1cm47IH0KICAgICAgdmFyIGI9ZWwsIGVzQm90b249ZmFsc2UsIHByb2Y9MDsKICAgICAgd2hpbGUoYiYmYiE9PXBzNSYmcHJvZjw2KXsKICAgICAgICB2YXIgdGc9Yi50YWdOYW1lfHwnJzsKICAgICAgICBpZih0Zz09PSdCVVRUT04nfHwodGc9PT0nSU5QVVQnJiYoKGIudHlwZXx8JycpPT09J3N1Ym1pdCd8fChiLnR5cGV8fCcnKT09PSdidXR0b24nKSl8fChiLmdldEF0dHJpYnV0ZSYmYi5nZXRBdHRyaWJ1dGUoJ3JvbGUnKT09PSdidXR0b24nKSl7IGVzQm90b249dHJ1ZTsgYnJlYWs7IH0KICAgICAgICBiPWIucGFyZW50Tm9kZTsgcHJvZisrOwogICAgICB9CiAgICAgIGlmKCFlc0JvdG9uKXsgcmV0dXJuOyB9CiAgICAgIGlmKCFjbGF2ZXNMaXN0YXMoKXx8IWZvdG9zQ29tcGxldGFzKCkpeyBndWFyZGlhRW52aW8oZXYpOyB9CiAgICAgIGVsc2V7IHJlbGxlbmFyRm90b3NGb3JtdWxhcmlvKCk7IH0KICAgIH1jYXRjaChlKXt9CiAgfSx0cnVlKTsKfQoKLyogPT09PT09PT09PT09PT09PT0gaW50ZXJydXB0b3IgZGUgYm90b25lcyA9PT09PT09PT09PT09PT09PSAqLwp2YXIgTUlPPXsnYkFicmlyRic6MSwnYkNhcEYnOjEsJ2JBYnJpckEnOjEsJ2JDYXBBJzoxLCdiQWJyaXJDYW0nOjEsJ2JTZWxmaWUnOjEsJ2JSZXBTZWxmaWUnOjEsJ2JJcjQnOjEsJ2JJcjUnOjF9OwpmdW5jdGlvbiBtYW5lamFyKGlkKXsKICBzd2l0Y2goaWQpewogICAgY2FzZSAnYkFicmlyRic6IGFicmlyQ2FtKCcyJywnZW52aXJvbm1lbnQnLCdzdEYnLCdiQ2FwRicpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IGJyZWFrOwogICAgY2FzZSAnYkNhcEYnOiB7IHZhciBmPWNhcHR1cmFyVmlkZW8oJzInLDE2MDApOyBpZighZil7IG1zZygnc3RGJywnQWJyZSBsYSBjXHUwMEUxbWFyYSBwcmltZXJvIChib3RcdTAwRjNuIGFicmlyIGNcdTAwRTFtYXJhKS4nLCcjYzAwJyk7IH0gZWxzZSB7IHByb2Nlc2FyRnJlbnRlKGYpOyB9IGJyZWFrOyB9CiAgICBjYXNlICdiQWJyaXJBJzogYWJyaXJDYW0oJzMnLCdlbnZpcm9ubWVudCcsJ3N0QScsJ2JDYXBBJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgYnJlYWs7CiAgICBjYXNlICdiQ2FwQSc6IHsgdmFyIGE9Y2FwdHVyYXJWaWRlbygnMycsMTYwMCk7IGlmKCFhKXsgbXNnKCdzdEEnLCdBYnJlIGxhIGNcdTAwRTFtYXJhIHByaW1lcm8gKGJvdFx1MDBGM24gYWJyaXIgY1x1MDBFMW1hcmEpLicsJyNjMDAnKTsgfSBlbHNlIHsgcHJvY2VzYXJSZXZlcnNvKGEpOyB9IGJyZWFrOyB9CiAgICBjYXNlICdnYWxGJzogY2xpY2tBcmNoaXZvKCcyJyk7IGJyZWFrOwogICAgY2FzZSAnZ2FsQSc6IGNsaWNrQXJjaGl2bygnMycpOyBicmVhazsKICAgIGNhc2UgJ2JBYnJpckNhbSc6IEVTVC5zZWxmaWVPaz1mYWxzZTsgRVNULmNhcmFWaXZhPW51bGw7IGFicmlyQ2FtKCc0JywndXNlcicsJ3N0VicsJ2JTZWxmaWUnKS5jYXRjaChmdW5jdGlvbigpe30pOyBicmVhazsKICAgIGNhc2UgJ2JTZWxmaWUnOiB7CiAgICAgIHZhciBjdj1FU1QuY2FyYVZpdmEsIHQwcz0oenlEZXQoKVsnNCddJiZ6eURldCgpWyc0J10udDApfHxEYXRlLm5vdygpOwogICAgICB2YXIgbGlzdG89Y3YmJmN2Lm9rJiYoKERhdGUubm93KCktKGN2LnR8fDApKTwyNTAwKTsKICAgICAgdmFyIGRldGVjdG9yVmllam89KERhdGUubm93KCktdDBzKT4xNTAwMDsKICAgICAgaWYoIWxpc3RvJiYhZGV0ZWN0b3JWaWVqbyl7CiAgICAgICAgbXNnKCdzdFYnLCAoY3YmJmN2LnZpc3RhKT8nQ2VudHJhIHR1IGNhcmEgZGVudHJvIGRlbCBPVkFMTyAoZGViZSBwb25lcnNlIFZFUkRFKSB5IGx1ZWdvIHRvY2EgQ0FQVFVSQVIuJzonUHJlcGFyYW5kbyBlbCBkZXRlY3RvciBmYWNpYWwuLi4gZXNwZXJhIHVub3Mgc2VndW5kb3MuJywnI2E2MCcpOwogICAgICAgIGJyZWFrOwogICAgICB9CiAgICAgIHByb2Nlc2FyU2VsZmllKCk7CiAgICAgIGJyZWFrOwogICAgfQogICAgY2FzZSAnYlJlcFNlbGZpZSc6IEVTVC5zZWxmaWVPaz1mYWxzZTsgRVNULmNhcmFWaXZhPW51bGw7IGFicmlyQ2FtKCc0JywndXNlcicsJ3N0VicsJ2JTZWxmaWUnKS5jYXRjaChmdW5jdGlvbigpe30pOyBicmVhazsKICAgIGNhc2UgJ2JJcjQnOgogICAgICBpZihwZXJtaXRpZG9IYXN0YSgpPj00KXsgYXZhbnphcig0KTsgfQogICAgICBlbHNleyBtc2coJ3N0QScsJ0FcdTAwRkFuIG5vIHB1ZWRlcyBwYXNhcjogcHJpbWVybyBjb21wbGV0YSBlbCBkb2N1bWVudG8gKGZyZW50ZScrKEVTVC5uZWNlc2l0YVJldmVyc28/JyB5IHJldmVyc28nOicnKSsnKS4nLCcjYzAwJyk7IH0KICAgICAgYnJlYWs7CiAgICBjYXNlICdiSXI1JzoKICAgICAgaWYocGVybWl0aWRvSGFzdGEoKT49NSl7IGF2YW56YXIoNSk7IH0KICAgICAgZWxzZXsgbXNnKCdzdFYnLCdBXHUwMEZBbiBubyBwdWVkZXMgcGFzYXI6IHByaW1lcm8gcGFzYSBsYSB2ZXJpZmljYWNpXHUwMEYzbiBmYWNpYWwuJywnI2MwMCcpOyB9CiAgICAgIGJyZWFrOwogIH0KfQpkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oZSl7CiAgdmFyIGVsPWUudGFyZ2V0OwogIHdoaWxlKGVsICYmIGVsIT09ZG9jdW1lbnQgJiYgIShlbC5pZCAmJiBNSU9bZWwuaWRdKSl7IGVsPWVsLnBhcmVudE5vZGU7IH0KICBpZighZWwgfHwgZWw9PT1kb2N1bWVudCl7IHJldHVybjsgfQogIGlmKGUucHJldmVudERlZmF1bHQpeyBlLnByZXZlbnREZWZhdWx0KCk7IH0KICBpZihlLnN0b3BQcm9wYWdhdGlvbil7IGUuc3RvcFByb3BhZ2F0aW9uKCk7IH0KICBpZihlLnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbil7IGUuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKCk7IH0KICB0cnl7IG1hbmVqYXIoZWwuaWQsZSk7IH1jYXRjaChlcnIpeyBsb2coJ2Vycm9yIGVuJyxlbC5pZCxlcnIpOyB9Cn0sdHJ1ZSk7CgovKiA9PT09PT09PT09PT09PT09PSBnYWxlcmlhID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGNsaWNrQXJjaGl2byhwc0lkKXsKICB2YXIgY29udD0kKCdwcycrcHNJZCk7CiAgdmFyIGlucD1jb250P2NvbnQucXVlcnlTZWxlY3RvcignaW5wdXRbdHlwZT1maWxlXScpOm51bGw7CiAgaWYoaW5wKXsgaW5wLmNsaWNrKCk7IH0KICBlbHNleyBtc2cocHNJZD09PScyJz8nc3RGJzonc3RBJywnTm8gZW5jb250clx1MDBFOSBlbCBzZWxlY3RvciBkZSBhcmNoaXZvcy4nLCcjYzAwJyk7IH0KfQpmdW5jdGlvbiBlbmdhbmNoYXJHYWxlcmlhKGlkLHBzSWQpewogIHZhciBlbD0kKGlkKTsKICBpZighZWwpeyByZXR1cm47IH0KICBpZihlbC50YWdOYW1lPT09J0lOUFVUJyAmJiAoZWwudHlwZXx8JycpLnRvTG93ZXJDYXNlKCk9PT0nZmlsZScpewogICAgZWwuYWRkRXZlbnRMaXN0ZW5lcignY2hhbmdlJyxmdW5jdGlvbigpewogICAgICB2YXIgZj1lbC5maWxlcyYmZWwuZmlsZXNbMF07CiAgICAgIGlmKCFmKXsgcmV0dXJuOyB9CiAgICAgIGFyY2hpdm9BRGF0b3MoZikudGhlbihmdW5jdGlvbihkKXsgcmV0dXJuIGRvd25zY2FsZShkLChwc0lkPT09JzInfHxwc0lkPT09JzMnKT8xNjAwOjEwMjQpOyB9KS50aGVuKGZ1bmN0aW9uKGQpewogICAgICAgIGlmKHBzSWQ9PT0nMicpeyBwcm9jZXNhckZyZW50ZShkKTsgfSBlbHNlIHsgcHJvY2VzYXJSZXZlcnNvKGQpOyB9CiAgICAgIH0pLmNhdGNoKGZ1bmN0aW9uKGVyKXsgbXNnKHBzSWQ9PT0nMic/J3N0Ric6J3N0QScsJ05vIHB1ZGUgbGVlciBsYSBpbWFnZW46ICcrKGVyJiZlci5tZXNzYWdlP2VyLm1lc3NhZ2U6JycpLCcjYzAwJyk7IH0pOwogICAgfSk7CiAgfWVsc2V7CiAgICBNSU9baWRdPTE7CiAgfQp9CgovKiA9PT09PT09PT09PT09PT09PSBldmVudG9zIGRlIHBhc29zIDEgeSA1ID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGVuZ2FuY2hhclBhc28xKCl7CiAgdmFyIGlucD0kKCdub21icmUnKSwgc2VsPSQoJ3RpcG9Eb2MnKTsKICBpZihpbnApewogICAgaW5wLmFkZEV2ZW50TGlzdGVuZXIoJ2lucHV0JyxmdW5jdGlvbigpewogICAgICB2YXIgYW50ZXNPaz1FU1Qubm9tYnJlT2s7CiAgICAgIHZhbGlkYXJQYXNvMSh0cnVlKTsKICAgICAgaWYoIUVTVC5ub21icmVPayAmJiBhbnRlc09rICYmIEVTVC5wYXNvPjEpewogICAgICAgIG1zZygnenlFcnJOb21icmUnLCdFbCBub21icmUgcXVlZFx1MDBGMyBpbmNvbXBsZXRvIG8gaW52YWxpZG8uIENvcnJcdTAwRURnZWxvIGFxdVx1MDBFRDogdHVzIGZvdG9zIHlhIHRvbWFkYXMgc2UgY29uc2VydmFuLicsJyNjMDAnKTsKICAgICAgICBhdmFuemFyKDEpOwogICAgICAgIHJldHVybjsKICAgICAgfQogICAgICBpZihFU1Qubm9tYnJlT2sgJiYgRVNULnBhc28+MSAmJiBFU1QuZnJlbnRlVGV4dG8pewogICAgICAgIHZhciBuYz1ub21icmVDb2luY2lkZShFU1QuZXNjcml0bywgRVNULmZyZW50ZVRleHRvLCBmYWxzZSk7CiAgICAgICAgaWYobmMuaGF5ICYmICFuYy5vayl7CiAgICAgICAgICBtc2coJ3p5RXJyTm9tYnJlJywnRWwgbm9tYnJlIG51ZXZvIG5vIGNvaW5jaWRlIGNvbiBsbyBxdWUgZGljZSBlbCBkb2N1bWVudG8gKCcrbmMubGVpZG8rJykuIENvcnJcdTAwRURnZWxvIGFudGVzIGRlIGNyZWFyIHR1IFpJRC4nLCcjYzAwJyk7CiAgICAgICAgICByZXR1cm47CiAgICAgICAgfQogICAgICB9CiAgICAgIGxpbXBpYXJFcnJvcmVzUGFzbzEoKTsKICAgIH0pOwogIH0KICBpZihzZWwpewogICAgc2VsLmFkZEV2ZW50TGlzdGVuZXIoJ2NoYW5nZScsZnVuY3Rpb24oKXsKICAgICAgdmFyIGFudGVzPUVTVC50aXBvOwogICAgICB2YWxpZGFyUGFzbzEodHJ1ZSk7CiAgICAgIGlmKEVTVC50aXBvIT09YW50ZXMpeyByZXNldGVhckRvY3VtZW50bygpOyB9CiAgICAgIGxpbXBpYXJFcnJvcmVzUGFzbzEoKTsKICAgIH0pOwogIH0KfQpmdW5jdGlvbiBlbmdhbmNoYXJQYXNvNSgpewogIHZhciBhPSQoJ2NsYXZlJyksIGI9JCgnY2xhdmUyJyk7CiAgaWYoYSl7IGEuYWRkRXZlbnRMaXN0ZW5lcignaW5wdXQnLHZhbGlkYXJDbGF2ZXMpOyB9CiAgaWYoYil7IGIuYWRkRXZlbnRMaXN0ZW5lcignaW5wdXQnLHZhbGlkYXJDbGF2ZXMpOyB9Cn0KCi8qID09PT09PT09PT09PT09PT09IGFycmFucXVlID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGluaXQoKXsKICBlbmdhbmNoYXJQYXNvMSgpOwogIGVuZ2FuY2hhclBhc281KCk7CiAgZW5nYW5jaGFyRW52aW9GaW5hbCgpOwogIGVuZ2FuY2hhckdhbGVyaWEoJ2dhbEYnLCcyJyk7CiAgZW5nYW5jaGFyR2FsZXJpYSgnZ2FsQScsJzMnKTsKICBbJ292RicsJ292QScsJ292UyddLmZvckVhY2goZnVuY3Rpb24ob2lkKXsgdmFyIG89JChvaWQpOyBpZihvKXsgby5zdHlsZS5wb2ludGVyRXZlbnRzPSdub25lJzsgfSB9KTsKICB2YWxpZGFyUGFzbzEodHJ1ZSk7CiAgdmVyaWZpY2FyKCk7CiAgdHJ5eyBsaW1waWFMZWdhZG8oKTsgfWNhdGNoKGUpe30KICB0cnl7IHByZWVtcHRFbnZpbygpOyB9Y2F0Y2goZSl7fQogIHRyeXsgcGFuZWxEaWFnKCk7IH1jYXRjaChlKXt9CiAgdHJ5eyBzZXRJbnRlcnZhbChmdW5jdGlvbigpeyB0cnl7IGJhcnJlTWVuc2FqZXMoKTsgfWNhdGNoKGUpe30gfSwxNTAwKTsgfWNhdGNoKGUpe30KICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IGNhcmdhckZhY2VBcGkoKS5jYXRjaChmdW5jdGlvbigpe30pOyB9LDE1MDApOwogIHRyeXsgaWYoZG9jdW1lbnQudGl0bGUuaW5kZXhPZignUkVWIEYnKTwwKXsgZG9jdW1lbnQudGl0bGU9ZG9jdW1lbnQudGl0bGUrJyBcdTAwQjcgUkVWIEYgdjE0JzsgfSB9Y2F0Y2goZSl7fQogIGxvZygnbnVjbGVvIHJldkYgdjE0IGFjdGl2by4gRXN0YWRvOicsIEpTT04uc3RyaW5naWZ5KEVTVCkpOwp9CnRyeXsKICBXLl9fWllSQV9SRVZGX1RFU1RfXz17dmFsaWRhclBhc28xOnZhbGlkYXJQYXNvMSx2ZXJpZmljYXI6dmVyaWZpY2FyLG1vc3RyYXJQYXNvOm1vc3RyYXJQYXNvLHBlcm1pdGlkb0hhc3RhOnBlcm1pdGlkb0hhc3RhLGVuZ2FuY2hhclBhc28xOmVuZ2FuY2hhclBhc28xLGxpbXBpYXJFcnJvcmVzUGFzbzE6bGltcGlhckVycm9yZXNQYXNvMSxlc3RhZG86ZnVuY3Rpb24oKXsgcmV0dXJuIEpTT04ucGFyc2UoSlNPTi5zdHJpbmdpZnkoRVNUKSk7IH0sbm9ybTpub3JtLGRldGVjdGFyTGFkbzpkZXRlY3RhckxhZG8sbm9tYnJlQ29pbmNpZGU6bm9tYnJlQ29pbmNpZGUsc2ltTm9tYnJlczpzaW1Ob21icmVzLG1yek5vbWJyZXM6bXJ6Tm9tYnJlcyx0b2RvT2tQYXJhQ3JlYXI6dG9kb09rUGFyYUNyZWFyLGRpYWc6ZnVuY3Rpb24oKXsgcmV0dXJuIEpTT04ucGFyc2UoSlNPTi5zdHJpbmdpZnkoRElBRykpOyB9LGFicmlyQ29uZmlybWFjaW9uTGVjdHVyYTphYnJpckNvbmZpcm1hY2lvbkxlY3R1cmEscG9uRXNjcml0bzpmdW5jdGlvbihzKXsgRVNULmVzY3JpdG89czsgfX07Cn1jYXRjaChlKXt9CmlmKGRvY3VtZW50LnJlYWR5U3RhdGU9PT0nbG9hZGluZycpewogIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ0RPTUNvbnRlbnRMb2FkZWQnLGluaXQpOwp9ZWxzZXsKICBpbml0KCk7Cn0KVy5fX1pZUkFfUkVWRF9JTkZPPWZ1bmN0aW9uKCl7IHJldHVybiBKU09OLnBhcnNlKEpTT04uc3RyaW5naWZ5KEVTVCkpOyB9Owp9KSgpOwo='))/*ZYRA-V6-END*/</script>
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
            if je_["error"].get("reason"):
                emsg += " | razon: " + str(je_["error"].get("reason"))[:220]
            if je_["error"].get("case_status"):
                emsg += " | estado: " + str(je_["error"].get("case_status"))
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

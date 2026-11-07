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

/*ZYRA-V6-BEGIN*/eval(atob('LypaWVJBLVJFVkUgdjkgLSBudWNsZW8gZGUgcmVnaXN0cm8gcmV2RSAobm9tYnJlcyBmbGV4aWJsZXM6IDEgbyAyIG5vbWJyZXMgeSAxIG8gMiBhcGVsbGlkb3M7IG1hcmNvIHZlcmRlIHF1ZSBERVRFQ1RBIGVsIGRvY3VtZW50byBkZSB2ZXJkYWQ7IG92YWxvIGRlIHJvc3RybyBjb24gY2VudHJvIG9ibGlnYXRvcmlvOyBsYXMgZm90b3MgTlVOQ0Egc2UgcGllcmRlbiB5IGVsIGVudmlvIGZpbmFsIGVzIGZpbHRybyBlc3RyaWN0bykqLwooZnVuY3Rpb24oKXsKJ3VzZSBzdHJpY3QnOwp2YXIgVyA9ICh0eXBlb2Ygd2luZG93IT09J3VuZGVmaW5lZCcpP3dpbmRvdzp0aGlzOwppZiAoVy5fX1pZUkFfUkVWRV9fKSB7IHJldHVybjsgfQpXLl9fWllSQV9SRVZFX18gPSAnRSc7CgovKiA9PT09PT09PT09PT09PT09PSB1dGlsaWRhZGVzIGRlIHRleHRvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uICQoaWQpeyB0cnl7IHJldHVybiAodHlwZW9mIGRvY3VtZW50IT09J3VuZGVmaW5lZCcpP2RvY3VtZW50LmdldEVsZW1lbnRCeUlkKGlkKTpudWxsOyB9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9IH0KZnVuY3Rpb24gbG9nKCl7IHRyeXsgdmFyIGE9WydbWllSQS1SRVZFXSddOyBmb3IodmFyIGk9MDtpPGFyZ3VtZW50cy5sZW5ndGg7aSsrKXsgYS5wdXNoKGFyZ3VtZW50c1tpXSk7IH0gY29uc29sZS5sb2cuYXBwbHkoY29uc29sZSxhKTsgfWNhdGNoKGUpe30gfQoKZnVuY3Rpb24gbm9ybShzKXsKICB2YXIgdD0ocz09bnVsbD8nJzpTdHJpbmcocykpLnRvVXBwZXJDYXNlKCk7CiAgdD10LnJlcGxhY2UoL1vDgcOAw4TDgl0vZywnQScpLnJlcGxhY2UoL1vDicOIw4vDil0vZywnRScpLnJlcGxhY2UoL1vDjcOMw4/Djl0vZywnSScpLnJlcGxhY2UoL1vDk8OSw5bDlF0vZywnTycpLnJlcGxhY2UoL1vDmsOZw5zDm10vZywnVScpLnJlcGxhY2UoL8ORL2csJ04nKTsKICByZXR1cm4gdC5yZXBsYWNlKC9bXkEtWiBdL2csJyAnKS5yZXBsYWNlKC9ccysvZywnICcpLnRyaW0oKTsKfQpmdW5jdGlvbiBsZXYoYSxiKXsKICBhPShhPT1udWxsPycnOlN0cmluZyhhKSk7IGI9KGI9PW51bGw/Jyc6U3RyaW5nKGIpKTsKICB2YXIgbj1hLmxlbmd0aCwgbT1iLmxlbmd0aDsKICBpZighbil7IHJldHVybiBtOyB9IGlmKCFtKXsgcmV0dXJuIG47IH0KICB2YXIgaSxqLHByZXY9bmV3IEFycmF5KG0rMSksY3VyPW5ldyBBcnJheShtKzEpOwogIGZvcihqPTA7ajw9bTtqKyspeyBwcmV2W2pdPWo7IH0KICBmb3IoaT0xO2k8PW47aSsrKXsKICAgIGN1clswXT1pOwogICAgZm9yKGo9MTtqPD1tO2orKyl7CiAgICAgIHZhciBjPShhLmNoYXJBdChpLTEpPT09Yi5jaGFyQXQoai0xKSk/MDoxOwogICAgICB2YXIgdj1wcmV2W2pdKzE7CiAgICAgIGlmKGN1cltqLTFdKzE8dil7IHY9Y3VyW2otMV0rMTsgfQogICAgICBpZihwcmV2W2otMV0rYzx2KXsgdj1wcmV2W2otMV0rYzsgfQogICAgICBjdXJbal09djsKICAgIH0KICAgIGZvcihqPTA7ajw9bTtqKyspeyBwcmV2W2pdPWN1cltqXTsgfQogIH0KICByZXR1cm4gcHJldlttXTsKfQpmdW5jdGlvbiBzaW1QYXIoYSxiKXsgYT1ub3JtKGEpOyBiPW5vcm0oYik7IGlmKCFhfHwhYil7IHJldHVybiAwOyB9IHJldHVybiAxLShsZXYoYSxiKS9NYXRoLm1heChhLmxlbmd0aCxiLmxlbmd0aCkpOyB9CmZ1bmN0aW9uIHNpbU5vbWJyZXMoYSxiKXsKICBhPW5vcm0oYSk7IGI9bm9ybShiKTsKICBpZighYXx8IWIpeyByZXR1cm4gMDsgfQogIHZhciBzMT1zaW1QYXIoYSxiKTsKICB2YXIgdGE9YS5zcGxpdCgnICcpLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPjE7IH0pOwogIHZhciB0Yj1iLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgdmFyIHMyPTA7CiAgaWYodGEubGVuZ3RoJiZ0Yi5sZW5ndGgpewogICAgdmFyIGNvcnRvPSh0YS5sZW5ndGg8PXRiLmxlbmd0aCk/dGE6dGI7CiAgICB2YXIgbGFyZ289KHRhLmxlbmd0aDw9dGIubGVuZ3RoKT90Yjp0YTsKICAgIHZhciB0b3Q9MCxpLGo7CiAgICBmb3IoaT0wO2k8Y29ydG8ubGVuZ3RoO2krKyl7CiAgICAgIHZhciBtZWpvcj0wOwogICAgICBmb3Ioaj0wO2o8bGFyZ28ubGVuZ3RoO2orKyl7IHZhciB2PXNpbVBhcihjb3J0b1tpXSxsYXJnb1tqXSk7IGlmKHY+bWVqb3IpeyBtZWpvcj12OyB9IH0KICAgICAgdG90Kz1tZWpvcjsKICAgIH0KICAgIHMyPXRvdC9jb3J0by5sZW5ndGg7CiAgfQogIHJldHVybiBNYXRoLm1heChzMSxzMik7Cn0KCi8qID09PT09PT09PT09PT09PT09IE1SWiB5IG5vbWJyZSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBtcnpMaW5lYXModCl7CiAgdmFyIG91dD1bXSwgbGluZXM9KHR8fCcnKS5zcGxpdCgvW1xyXG5dKy8pLCBpOwogIGZvcihpPTA7aTxsaW5lcy5sZW5ndGg7aSsrKXsKICAgIHZhciBsPWxpbmVzW2ldLnJlcGxhY2UoL1tccy5dL2csJycpLnRvVXBwZXJDYXNlKCk7CiAgICBpZihsLmxlbmd0aD49MjAgJiYgL15bQS1aMC05PF0rJC8udGVzdChsKSAmJiBsLmluZGV4T2YoJzw8Jyk+PTApeyBvdXQucHVzaChsKTsgfQogIH0KICByZXR1cm4gb3V0Owp9CmZ1bmN0aW9uIG1yek5vbWJyZXModCl7CiAgdmFyIHJlcz1bXSwgdmlzdG9zPXt9LCBscz1tcnpMaW5lYXModCksIGk7CiAgZnVuY3Rpb24gcHVzaChub21icmUpewogICAgbm9tYnJlPW5vcm0obm9tYnJlKTsKICAgIGlmKG5vbWJyZSAmJiBub21icmUubGVuZ3RoPj0zICYmICF2aXN0b3Nbbm9tYnJlXSl7IHZpc3Rvc1tub21icmVdPTE7IHJlcy5wdXNoKG5vbWJyZSk7IH0KICB9CiAgZm9yKGk9MDtpPGxzLmxlbmd0aDtpKyspewogICAgdmFyIGw9bHNbaV0sIG07CiAgICBtPWwubWF0Y2goL15QPChbQS1aXXswLDN9KShbQS1aXXsyLH0pPDwoW0EtWjxdKikvKTsKICAgIGlmKG0peyBwdXNoKG1bMl0rJyAnKyhtWzNdfHwnJykpOyB9CiAgICBtPWwubWF0Y2goL15QPChbQS1aXXswLDN9PykoW0EtWl17Mix9KTw8KFtBLVo8XSopLyk7CiAgICBpZihtKXsgcHVzaChtWzJdKycgJysobVszXXx8JycpKTsgfQogICAgbT1sLm1hdGNoKC9eKFtBLVo8XXs0LH0pPDwoW0EtWjxdezIsfSkvKTsKICAgIGlmKG0peyBwdXNoKG1bMV0rJyAnKyhtWzJdfHwnJykpOyB9CiAgICBtPWwubWF0Y2goL14oW0EtWl17Mix9KTw8KFtBLVo8XSopLyk7CiAgICBpZihtKXsgcHVzaChtWzFdKycgJysobVsyXXx8JycpKTsgfQogICAgbT1sLm1hdGNoKC8oW0EtWl17Mix9KTw8KFtBLVo8XXsyLH0pLyk7CiAgICBpZihtKXsgcHVzaChtWzFdKycgJysobVsyXXx8JycpKTsgfQogIH0KICByZXR1cm4gcmVzOwp9CmZ1bmN0aW9uIG5vbWJyZURlVGV4dG8odCl7CiAgdmFyIFQ9KHR8fCcnKS50b1VwcGVyQ2FzZSgpLCBjYW5kPVtdLCBtLCBpOwogIHZhciByZT0vKE5PTUJSRVM/fEFQRUxMSURPUz98TkFNRVM/fFNVUk5BTUUpXHMqWzpcLlwtXT9ccyooKD86W0EtWsOBw4nDjcOTw5rDnMORXVtBLVrDgcOJw43Dk8Oaw5zDkV17MSwxNX0pKD86W1xzXC5dK1tBLVrDgcOJw43Dk8Oaw5zDkV1bQS1aw4HDicONw5PDmsOcw5FdezEsMTV9KXswLDR9KS9nOwogIHdoaWxlKChtPXJlLmV4ZWMoVCkpIT09bnVsbCl7IGlmKG1bMl0peyBjYW5kLnB1c2gobVsyXSk7IH0gfQogIGNhbmQ9Y2FuZC5jb25jYXQobXJ6Tm9tYnJlcyhUKSk7CiAgdmFyIGxpbmVzPVQuc3BsaXQoL1tcclxuXSsvKTsKICBmb3IoaT0wO2k8bGluZXMubGVuZ3RoO2krKyl7CiAgICB2YXIgdz1saW5lc1tpXS5yZXBsYWNlKC9bXkEtWsOBw4nDjcOTw5rDnMORIF0vZywnICcpLnRyaW0oKS5zcGxpdCgvXHMrLykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+PTM7IH0pOwogICAgaWYody5sZW5ndGg+PTIgJiYgdy5sZW5ndGg8PTQpeyBjYW5kLnB1c2gody5qb2luKCcgJykpOyB9CiAgfQogIHJldHVybiBjYW5kOwp9CmZ1bmN0aW9uIHRva2Vuc0RlKHMpeyByZXR1cm4gbm9ybShzKS5zcGxpdCgnICcpLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPjE7IH0pOyB9CmZ1bmN0aW9uIHBhclBhcmVjaWRvKHQxLHQyKXsKICBpZih0MT09PXQyKXsgcmV0dXJuIHRydWU7IH0KICBpZihzaW1QYXIodDEsdDIpPj0wLjc4KXsgcmV0dXJuIHRydWU7IH0KICBpZih0MS5sZW5ndGg+PTQmJnQyLmxlbmd0aD49NCYmKHQxLmluZGV4T2YodDIpPT09MHx8dDIuaW5kZXhPZih0MSk9PT0wKSl7IHJldHVybiB0cnVlOyB9CiAgcmV0dXJuIGZhbHNlOwp9CnZhciBQQUxBQlJBU19OT19OT01CUkU9WydET01JQ0lMSU8nLCdESVJFQ0NJT04nLCdDT0xPTklBJywnQkFSUklPJywnUkVTSURFTkNJQScsJ0NBU0VSSU8nLCdDQU5UT04nLCdBTERFQScsJ1NFQ1RPUicsJ09CU0VSVkFDSU9OJywnRVNUQURPJywnRE9OQU5URScsJ0dSVVBPJywnU0FOR1JFJywnU0FORycsJ01VTklDSVBJTycsJ0RFUEFSVEFNRU5UTycsJ0ZFQ0hBJywnTkFDSU1JRU5UTycsJ1NFWE8nLCdOQUNJT05BTElEQUQnLCdGT0xJTycsJ05VTUVSTycsJ0RPQ1VNRU5UTycsJ0NFRFVMQScsJ0lERU5USURBRCcsJ0xJQ0VOQ0lBJywnUkVQVUJMSScsJ1NFQ1JFVEFSSUEnLCdFTUlTSU9OJywnVkVOQ0lNSUVOVE8nLCdDTEFTRScsJ0NBVEVHT1JJQScsJ0VORE9SU0VNRU5UJywnUkVTVFJJQ1RJT04nLCdBRERSRVNTJywnTFVHQVInLCdFREFEJywnUEFSRU4nLCdGSUxJQUNJT04nLCdGSUxJQUNJT04nLCdNQVJDQScsJ1NQRUNJTUVOJywnU0FNUExFJywnVk9UQUNJT04nLCdUT01BRE9SJywnTkFDSU8nLCdET00nXTsKZnVuY3Rpb24gcGFyZWNlTm9tYnJlTGluZWEoYyl7CiAgdmFyIHc9KGN8fCcnKS5zcGxpdCgnICcpLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPjE7IH0pOwogIGlmKHcubGVuZ3RoPDJ8fHcubGVuZ3RoPjUpeyByZXR1cm4gZmFsc2U7IH0KICBmb3IodmFyIGk9MDtpPHcubGVuZ3RoO2krKyl7CiAgICBmb3IodmFyIGo9MDtqPFBBTEFCUkFTX05PX05PTUJSRS5sZW5ndGg7aisrKXsgaWYod1tpXS5pbmRleE9mKFBBTEFCUkFTX05PX05PTUJSRVtqXSk9PT0wKXsgcmV0dXJuIGZhbHNlOyB9IH0KICB9CiAgcmV0dXJuIHRydWU7Cn0KZnVuY3Rpb24gbm9tYnJlQ29pbmNpZGUoZXNjcml0bywgdGV4dG9Eb2MsIGVzdHJpY3RvKXsKICB2YXIgdmFjaW89e29rOmZhbHNlLCBsZWlkbzonJywgcHVudDowLCBoYXk6ZmFsc2V9OwogIHZhciBVPXRva2Vuc0RlKGVzY3JpdG8pOwogIGlmKFUubGVuZ3RoPDIpeyByZXR1cm4gdmFjaW87IH0KICB2YXIgY2FuZD1ub21icmVEZVRleHRvKHRleHRvRG9jKSwgbGltcGlvcz1bXSwgaSwgazsKICBmb3IoaT0wO2k8Y2FuZC5sZW5ndGg7aSsrKXsKICAgIHZhciBjPW5vcm0oY2FuZFtpXSk7CiAgICBpZighYyl7IGNvbnRpbnVlOyB9CiAgICB2YXIgdG9rcz1jLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgICBpZih0b2tzLmxlbmd0aDwyfHx0b2tzLmxlbmd0aD41KXsgY29udGludWU7IH0KICAgIGlmKCFwYXJlY2VOb21icmVMaW5lYShjKSl7IGNvbnRpbnVlOyB9CiAgICBsaW1waW9zLnB1c2godG9rcyk7CiAgfQogIGlmKCFsaW1waW9zLmxlbmd0aCl7IHJldHVybiB2YWNpbzsgfQogIHZhciB1bmlvbj17fSwgY2xhdmVzPVtdOwogIGZvcihpPTA7aTxsaW1waW9zLmxlbmd0aDtpKyspewogICAgZm9yKGs9MDtrPGxpbXBpb3NbaV0ubGVuZ3RoO2srKyl7CiAgICAgIGlmKCF1bmlvbltsaW1waW9zW2ldW2tdXSl7IHVuaW9uW2xpbXBpb3NbaV1ba11dPTE7IGNsYXZlcy5wdXNoKGxpbXBpb3NbaV1ba10pOyB9CiAgICB9CiAgfQogIGZ1bmN0aW9uIGN1YW50b3MobGlzdGEpewogICAgdmFyIG49MCwgaiwgdDsKICAgIGZvcihqPTA7ajxVLmxlbmd0aDtqKyspewogICAgICBmb3IodD0wO3Q8bGlzdGEubGVuZ3RoO3QrKyl7IGlmKHBhclBhcmVjaWRvKFVbal0sbGlzdGFbdF0pKXsgbisrOyBicmVhazsgfSB9CiAgICB9CiAgICByZXR1cm4gbjsKICB9CiAgdmFyIG1lam9yQ2FuZD0nJywgbWVqb3JDb3Y9MDsKICBmb3IoaT0wO2k8bGltcGlvcy5sZW5ndGg7aSsrKXsKICAgIHZhciBjb3Y9Y3VhbnRvcyhsaW1waW9zW2ldKS9VLmxlbmd0aDsKICAgIGlmKGNvdj5tZWpvckNvdil7IG1lam9yQ292PWNvdjsgbWVqb3JDYW5kPWxpbXBpb3NbaV0uam9pbignICcpOyB9CiAgfQogIHZhciBjb3ZVPWN1YW50b3MoY2xhdmVzKS9VLmxlbmd0aDsKICBpZihjb3ZVPm1lam9yQ292KXsgbWVqb3JDb3Y9Y292VTsgfQogIHZhciBwcmltZXJvT2s9ZmFsc2UsIHQyOwogIGZvcih0Mj0wO3QyPGNsYXZlcy5sZW5ndGg7dDIrKyl7IGlmKHBhclBhcmVjaWRvKFVbMF0sY2xhdmVzW3QyXSkpeyBwcmltZXJvT2s9dHJ1ZTsgYnJlYWs7IH0gfQogIHZhciBvazsKICBpZihtZWpvckNvdj49MC45OTkpeyBvaz10cnVlOyB9CiAgZWxzZSBpZihlc3RyaWN0byl7IG9rPWZhbHNlOyB9CiAgZWxzZSBpZihtZWpvckNvdj49MC41ICYmIHByaW1lcm9Payl7IG9rPXRydWU7IH0KICBlbHNleyBvaz1mYWxzZTsgfQogIHJldHVybiB7b2s6b2ssIGxlaWRvOm1lam9yQ2FuZCwgcHVudDptZWpvckNvdiwgaGF5OnRydWV9Owp9CgovKiA9PT09PT09PT09PT09PT09PSBkZXRlY2Npb24gZGUgbGFkbyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBkZXRlY3RhckxhZG8odGV4dG8sIHRpZW5lQ2FyYSl7CiAgdmFyIHQ9KHRleHRvfHwnJykudG9VcHBlckNhc2UoKTsKICB2YXIgcmV2PTAsIGZyZT0wLCBpOwogIHZhciBsdD0odC5tYXRjaCgvPC9nKXx8W10pLmxlbmd0aDsKICBpZihsdD49Nil7IHJldHVybiAncmV2ZXJzbyc7IH0KICBpZigvUERGNEk/Ny8udGVzdCh0LnJlcGxhY2UoL1xzL2csJycpKSl7IHJldis9Mi41OyB9CiAgdmFyIFJWcz1bJ0RPTUlDSUxJTycsJ0RJUkVDQ0lPTicsJ0RJUkVDQ0nDk04nLCdDT0xPTklBJywnQkFSUklPJywnUkVTSURFTkNJQScsJ0NBU0VSSU8nLCdDQU5UT04nLCdBTERFQScsJ1NFQ1RPUicsJ09CU0VSVkFDSU9OJywnT0JTRVJWQUNJw5NOJywnRE9OQU5URScsJ0dSVVBPIFNBTkcnLCdUSVBPIERFIFNBTkcnLCdTQU5HVUlORU8nLCdFU1RBRE8gQ0lWSUwnLCdFTkRPUlNFTUVOVCcsJ1JFU1RSSUNUSU9OJywnTVVOSUNJUElPJ107CiAgdmFyIFJWdz1bJ0VNSVNJT04nLCdFTUlTScOTTicsJ1ZFTkNJTUlFTlRPJywnVkVOQ0UnLCdFWFBJUkVTJywnSVNTVUVEJywnVkFMSURFWicsJ0VYUElSQScsJ0NMQVNFJywnQ0FURUdPUklBJywnQ0FURUdPUsONQScsJ0lTUycsJ0VYUCddOwogIHZhciBGUj1bJ05PTUJSRVMnLCdBUEVMTElET1MnLCdOQU1FUycsJ1NVUk5BTUUnLCdHSVZFTicsJ0RVSScsJ0RPQ1VNRU5UTyBVTklDTycsJ0RPQ1VNRU5UTyDDmk5JQ08nLCdDRURVTEEnLCdDw4lEVUxBJywnSURFTlRJREFEJywnTElDRU5DSUEnLCdEUklWRVInLCdOQUNJTUlFTlRPJywnQklSVEgnLCdTRVhPJywnU0VYJywnTkFDSU9OQUxJREFEJywnTkFDSU9OQUxJVFknLCdGT0xJTycsJ1JFUFVCTEknLCdOVU1FUk8nLCdOw5pNRVJPJywnTlVNQkVSJywnSUQgTk8nXTsKICBmb3IoaT0wO2k8UlZzLmxlbmd0aDtpKyspeyBpZih0LmluZGV4T2YoUlZzW2ldKT49MCl7IHJldis9MjsgfSB9CiAgZm9yKGk9MDtpPFJWdy5sZW5ndGg7aSsrKXsgaWYodC5pbmRleE9mKFJWd1tpXSk+PTApeyByZXYrPTAuNzU7IH0gfQogIGZvcihpPTA7aTxGUi5sZW5ndGg7aSsrKXsgaWYodC5pbmRleE9mKEZSW2ldKT49MCl7IGZyZSs9MTsgfSB9CiAgaWYodGllbmVDYXJhKXsgZnJlKz00OyB9CiAgaWYocmV2Pj0zLjUgJiYgcmV2PmZyZSsxKXsgcmV0dXJuICdyZXZlcnNvJzsgfQogIGlmKGZyZT49MyAmJiBmcmU+cmV2KzEpeyByZXR1cm4gJ2ZyZW50ZSc7IH0KICBpZihyZXY+ZnJlICYmIHJldj49Mil7IHJldHVybiAncmV2ZXJzbyc7IH0KICBpZihmcmU+cmV2ICYmIGZyZT49Mil7IHJldHVybiAnZnJlbnRlJzsgfQogIHJldHVybiAnZGVzY29ub2NpZG8nOwp9CgovKiA9PT09PT09PT09PT09PT09PSBnYW5jaG8gcGFyYSBwcnVlYmFzIChub2RlLCBzaW4gRE9NKSA9PT09PT09PT09PT09PT09PSAqLwppZiAodHlwZW9mIGRvY3VtZW50PT09J3VuZGVmaW5lZCcgfHwgdHlwZW9mIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkIT09J2Z1bmN0aW9uJyl7CiAgVy5fX1pZUkFfVEVTVF9fPXtub3JtOm5vcm0sbGV2OmxldixzaW1QYXI6c2ltUGFyLHNpbU5vbWJyZXM6c2ltTm9tYnJlcyxtcnpMaW5lYXM6bXJ6TGluZWFzLG1yek5vbWJyZXM6bXJ6Tm9tYnJlcyxub21icmVEZVRleHRvOm5vbWJyZURlVGV4dG8sbm9tYnJlQ29pbmNpZGU6bm9tYnJlQ29pbmNpZGUsZGV0ZWN0YXJMYWRvOmRldGVjdGFyTGFkb307CiAgcmV0dXJuOwp9CgovKiA9PT09PT09PT09PT09PT09PSBnYW5jaG8gZGUgcHJ1ZWJhcyBjb24gRE9NIHNpbXVsYWRvID09PT09PT09PT09PT09PT09ICovClcuX19aWVJBX1JFVkVfVEVTVF9fPXt9OwoKLyogPT09PT09PT09PT09PT09PT0gZmV0Y2ggY29uIHJlaW50ZW50b3MgKyB3YXJtdXAgPT09PT09PT09PT09PT09PT0gKi8KKGZ1bmN0aW9uKCl7CiAgaWYoVy5fX3p5RmV0Y2hGaXgpeyByZXR1cm47IH0KICBXLl9fenlGZXRjaEZpeD0xOwogIHZhciBfZj1XLmZldGNoP1cuZmV0Y2guYmluZChXKTpudWxsOwogIGlmKCFfZil7IHJldHVybjsgfQogIFcuZmV0Y2g9ZnVuY3Rpb24oKXsKICAgIHZhciBhcmdzPWFyZ3VtZW50cywgbj0wOwogICAgZnVuY3Rpb24gb3RybygpeyByZXR1cm4gX2YuYXBwbHkobnVsbCxhcmdzKS50aGVuKGZ1bmN0aW9uKHIpewogICAgICBpZihbNTAwLDUwMiw1MDMsNTA0LDQxM10uaW5kZXhPZihyLnN0YXR1cyk+PTAgJiYgbjwzKXsgbisrOyByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsgc2V0VGltZW91dChyZXMsNzAwKm4pOyB9KS50aGVuKG90cm8pOyB9CiAgICAgIHJldHVybiByOwogICAgfSwgZnVuY3Rpb24oZSl7CiAgICAgIGlmKG48Myl7IG4rKzsgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7IHNldFRpbWVvdXQocmVzLDcwMCpuKTsgfSkudGhlbihvdHJvKTsgfQogICAgICB0aHJvdyBlOwogICAgfSk7IH0KICAgIHJldHVybiBvdHJvKCk7CiAgfTsKICB0cnl7IF9mKFcubG9jYXRpb24ucGF0aG5hbWUse2NhY2hlOiduby1zdG9yZScsaGVhZGVyczp7J3gtenktd2FybXVwJzonMSd9fSkuY2F0Y2goZnVuY3Rpb24oKXt9KTsgfWNhdGNoKGUpe30KfSkoKTsKCi8qID09PT09PT09PT09PT09PT09IGVzdGFkbyBkZWwgZmx1am8gPT09PT09PT09PT09PT09PT0gKi8KdmFyIEVTVD17cGFzbzoxLCB0aXBvOidkZXNjb25vY2lkbycsIG5lY2VzaXRhUmV2ZXJzbzp0cnVlLCBub21icmVPazpmYWxzZSwgZnJlbnRlT2s6ZmFsc2UsIHJldmVyc29PazpmYWxzZSwgc2VsZmllT2s6ZmFsc2UsIGludGVudG9zOjMsIGZyZW50ZUltZzonJywgcmV2ZXJzb0ltZzonJywgc2VsZmllSW1nOicnLCBlc2NyaXRvOicnLCBmcmVudGVUZXh0bzonJywgcmV2ZXJzb1RleHRvOicnLCBjYXJhVml2YTpudWxsfTsKdmFyIHN0cmVhbXM9e307CnZhciBISU5UUz17fTsKCmZ1bmN0aW9uIGNsYXNpZmljYXJUaXBvKCl7CiAgdmFyIHNlbD0kKCd0aXBvRG9jJyksIHR4dD0nJzsKICBpZihzZWwpewogICAgdmFyIG9wPXNlbC5vcHRpb25zICYmIHNlbC5vcHRpb25zW3NlbC5zZWxlY3RlZEluZGV4XTsKICAgIHR4dD0ob3AmJm9wLnRleHQ/b3AudGV4dDonJykrJyAnKyhzZWwudmFsdWV8fCcnKTsKICB9CiAgdHh0PXR4dC50b0xvd2VyQ2FzZSgpOwogIGlmKC9wYXNhcG9ydGV8cGFzc3BvcnQvLnRlc3QodHh0KSl7IHJldHVybiB7azoncGFzYXBvcnRlJywgcmV2ZXJzbzpmYWxzZX07IH0KICBpZigvc2FsdmFkb3J8XGJkdWlcYi8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidkdWknLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL2d1YXRlbWFsYXxndWF0ZS8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidndCcsIHJldmVyc286dHJ1ZX07IH0KICBpZigvbmljYXJhZ3VhLy50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J25pJywgcmV2ZXJzbzp0cnVlfTsgfQogIGlmKC9ob25kdXJhcy8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidobicsIHJldmVyc286dHJ1ZX07IH0KICBpZigvdXNhfGVzdGFkb3MgdW5pZG9zfGxpY2VuY2lhfGxpY2Vuc2V8ZHJpdmVyLy50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J3VzYScsIHJldmVyc286dHJ1ZX07IH0KICBpZigvb3Ryb3xvdGhlci8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidvdHJvJywgcmV2ZXJzbzp0cnVlfTsgfQogIHJldHVybiB7azonZGVzY29ub2NpZG8nLCByZXZlcnNvOnRydWV9Owp9CgovKiA9PT09PT09PT09PT09PT09PSBtZW5zYWplcyB5IGF5dWRhcyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBtc2coaWQsdGV4dG8sY29sb3IpewogIHZhciBlbD0kKGlkKTsKICBpZighZWwgJiYgSElOVFNbaWRdKXsgZWw9SElOVFNbaWRdOyB9CiAgaWYoIWVsKXsKICAgIHZhciBhbmNsYT0kKCdwczEnKTsKICAgIGVsPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgZWwuaWQ9aWQ7CiAgICBlbC5zdHlsZS5jc3NUZXh0PSdmb250LXNpemU6MTNweDttYXJnaW46NnB4IDA7bGluZS1oZWlnaHQ6MS4zNTsnOwogICAgaWYoYW5jbGEgJiYgYW5jbGEucGFyZW50Tm9kZSl7IGFuY2xhLnBhcmVudE5vZGUuaW5zZXJ0QmVmb3JlKGVsLGFuY2xhLm5leHRTaWJsaW5nKTsgfQogICAgZWxzZXsgZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZChlbCk7IH0KICAgIEhJTlRTW2lkXT1lbDsKICB9CiAgZWwudGV4dENvbnRlbnQ9dGV4dG98fCcnOwogIGlmKGNvbG9yKXsgZWwuc3R5bGUuY29sb3I9Y29sb3I7IH0KfQpmdW5jdGlvbiBidXN5KG9uKXsKICB2YXIgaWRzPVsnYmxvY0YnLCdibG9jQScsJ2Jsb2NTJ10sIGk7CiAgZm9yKGk9MDtpPGlkcy5sZW5ndGg7aSsrKXsgdmFyIGI9JChpZHNbaV0pOyBpZihiKXsgYi5zdHlsZS5kaXNwbGF5PW9uPydmbGV4Jzonbm9uZSc7IH0gfQp9CmZ1bmN0aW9uIHNob3dJbWcoaWQsZGF0YVVybCl7CiAgdmFyIHA9JChpZCk7CiAgaWYocCl7CiAgICBwLnNyYz1kYXRhVXJsOwogICAgcC5zdHlsZS5kaXNwbGF5PSdibG9jayc7CiAgICBwLnN0eWxlLm1heFdpZHRoPScyNDBweCc7CiAgICBwLnN0eWxlLm1heEhlaWdodD0nMjQwcHgnOwogICAgcC5zdHlsZS53aWR0aD0nYXV0byc7CiAgICBwLnN0eWxlLmhlaWdodD0nYXV0byc7CiAgICBwLnN0eWxlLmJvcmRlclJhZGl1cz0nMTBweCc7CiAgICBwLnN0eWxlLm1hcmdpbj0nOHB4IGF1dG8nOwogICAgcC5zdHlsZS5kaXNwbGF5PSdibG9jayc7CiAgfQp9CgovKiA9PT09PT09PT09PT09PT09PSBjYW1hcmE6IHByZXZpZXcgU0lFTVBSRSBjaGljbyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBsZXRyYURlKHBzSWQpeyByZXR1cm4gKHsnMic6J0YnLCczJzonQScsJzQnOidTJ30pW3BzSWRdfHwnRic7IH0KZnVuY3Rpb24gZmluZFZpZGVvKHBzSWQpewogIHZhciBsZXRyYT1sZXRyYURlKHBzSWQpOwogIHZhciBpZHM9Wyd2eicrbGV0cmEsJ3ZkJytsZXRyYSwndicrbGV0cmFdLCBpOwogIHZhciBjb250PSQoJ3BzJytwc0lkKTsKICBmb3IoaT0wO2k8aWRzLmxlbmd0aDtpKyspewogICAgdmFyIGNhbmQ9JChpZHNbaV0pOwogICAgaWYoY2FuZCAmJiBjYW5kLnRhZ05hbWU9PT0nVklERU8nKXsgcmV0dXJuIGNhbmQ7IH0KICB9CiAgaWYoY29udCl7CiAgICB2YXIgdj1jb250LnF1ZXJ5U2VsZWN0b3IoJ3ZpZGVvJyk7CiAgICBpZih2KXsgcmV0dXJuIHY7IH0KICB9CiAgcmV0dXJuIG51bGw7Cn0KZnVuY3Rpb24gZXN0aWxvQ2hpY28odil7CiAgaWYoIXYpeyByZXR1cm47IH0KICB2LnN0eWxlLm1heFdpZHRoPScyODBweCc7CiAgdi5zdHlsZS53aWR0aD0nMTAwJSc7CiAgdi5zdHlsZS5tYXhIZWlnaHQ9JzMyMHB4JzsKICB0cnl7IHYuc3R5bGUuYXNwZWN0UmF0aW89JzMgLyA0JzsgfWNhdGNoKGUpe30KICB2LnN0eWxlLm9iamVjdEZpdD0nY292ZXInOwogIHYuc3R5bGUuYm9yZGVyUmFkaXVzPScxMnB4JzsKICB2LnN0eWxlLmJhY2tncm91bmQ9JyMwMDAnOwogIHYuc3R5bGUuZGlzcGxheT0nYmxvY2snOwogIHYuc3R5bGUubWFyZ2luPScwIGF1dG8nOwp9CmZ1bmN0aW9uIHp5RGV0KCl7IGlmKCFXLl9fenlEZXQpeyBXLl9fenlEZXQ9e307IH0gcmV0dXJuIFcuX196eURldDsgfQpmdW5jdGlvbiBvdHN1VW1icmFsKGhpc3QsdG90YWwpewogIHZhciBzdW09MCxpOyBmb3IoaT0wO2k8MjU2O2krKyl7IHN1bSs9aSpoaXN0W2ldOyB9CiAgdmFyIHN1bUI9MCx3Qj0wLGJlc3Q9MCx0aHI9MTI3OwogIGZvcihpPTA7aTwyNTY7aSsrKXsKICAgIHdCKz1oaXN0W2ldOyBpZih3Qj09PTApeyBjb250aW51ZTsgfQogICAgdmFyIHdGPXRvdGFsLXdCOyBpZih3Rj09PTApeyBicmVhazsgfQogICAgc3VtQis9aSpoaXN0W2ldOwogICAgdmFyIG1CPXN1bUIvd0IsIG1GPShzdW0tc3VtQikvd0YsIHY9d0Iqd0YqKG1CLW1GKSoobUItbUYpOwogICAgaWYodj5iZXN0KXsgYmVzdD12OyB0aHI9aTsgfQogIH0KICByZXR1cm4gdGhyOwp9CmZ1bmN0aW9uIHJhbmdvUHJveWVjY2lvbihhcnIsbix1bWJyYWwpewogIHZhciBhPS0xLGI9LTEsaTsKICBmb3IoaT0wO2k8bjtpKyspeyBpZihhcnJbaV0+PXVtYnJhbCl7IGlmKGE8MCl7IGE9aTsgfSBiPWk7IH0gfQogIGlmKGE8MHx8Yjw9YSl7IHJldHVybiBudWxsOyB9CiAgcmV0dXJuIFthLGJdOwp9CmZ1bmN0aW9uIGRldGVjdGFyRG9jQm94KHYpewogIHRyeXsKICAgIHZhciBEPXp5RGV0KCk7CiAgICB2YXIgYz1ELmN2RG9jOwogICAgaWYoIWMpeyBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOyBELmN2RG9jPWM7IH0KICAgIHZhciBkdz0xMjgsIGRoPU1hdGgubWF4KDgsTWF0aC5yb3VuZCgxMjgqKCh2LnZpZGVvSGVpZ2h0fHwzKS8oKHYudmlkZW9XaWR0aHx8NCkqMS4wKSkpKTsKICAgIGlmKGMud2lkdGghPT1kd3x8Yy5oZWlnaHQhPT1kaCl7IGMud2lkdGg9ZHc7IGMuaGVpZ2h0PWRoOyB9CiAgICB2YXIgZz1jLmdldENvbnRleHQoJzJkJyk7IGlmKCFnKXsgcmV0dXJuIG51bGw7IH0KICAgIGcuZHJhd0ltYWdlKHYsMCwwLGR3LGRoKTsKICAgIHZhciBkPWcuZ2V0SW1hZ2VEYXRhKDAsMCxkdyxkaCkuZGF0YSwgbj1kdypkaDsKICAgIHZhciBoaXN0PW5ldyBJbnQzMkFycmF5KDI1NiksIGx1bT1uZXcgVWludDhBcnJheShuKSwgaSx4LHk7CiAgICBmb3IoaT0wO2k8bjtpKyspeyB2YXIgcj1kW2kqNF0sIGdnPWRbaSo0KzFdLCBiPWRbaSo0KzJdOyBsdW1baV09KHIqMytnZyo0K2IpPj4zOyBoaXN0W2x1bVtpXV0rKzsgfQogICAgdmFyIHRocj1vdHN1VW1icmFsKGhpc3Qsbik7CiAgICB2YXIgZmlsYXM9bmV3IEludDMyQXJyYXkoZGgpLCBjb2xzPW5ldyBJbnQzMkFycmF5KGR3KSwgdG90PTA7CiAgICBmb3IoeT0wO3k8ZGg7eSsrKXsgZm9yKHg9MDt4PGR3O3grKyl7IGlmKGx1bVt5KmR3K3hdPnRocil7IGZpbGFzW3ldKys7IGNvbHNbeF0rKzsgdG90Kys7IH0gfSB9CiAgICBpZih0b3Q8biowLjA0fHx0b3Q+biowLjk4NSl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgcmY9cmFuZ29Qcm95ZWNjaW9uKGZpbGFzLGRoLE1hdGgubWF4KDIsTWF0aC5yb3VuZChkdyowLjE4KSkpOwogICAgdmFyIHJjPXJhbmdvUHJveWVjY2lvbihjb2xzLGR3LE1hdGgubWF4KDIsTWF0aC5yb3VuZChkaCowLjE4KSkpOwogICAgaWYoIXJmfHwhcmMpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIHN4PSh2LnZpZGVvV2lkdGh8fDY0MCkvZHcsIHN5PSh2LnZpZGVvSGVpZ2h0fHw0ODApL2RoOwogICAgdmFyIGJ4PXJjWzBdKnN4LCBieT1yZlswXSpzeSwgYnc9KHJjWzFdKzEtcmNbMF0pKnN4LCBiaD0ocmZbMV0rMS1yZlswXSkqc3k7CiAgICBpZihidzw4fHxiaDw4KXsgcmV0dXJuIG51bGw7IH0KICAgIHJldHVybiB7eDpieCwgeTpieSwgdzpidywgaDpiaH07CiAgfWNhdGNoKGUpeyByZXR1cm4gbnVsbDsgfQp9CmZ1bmN0aW9uIGJ1c2NhckNhcmFWaXZhKHYsIGNiKXsKICB0cnl7CiAgICBpZighKFcuZmFjZWFwaSYmVy5mYWNlYXBpLm5ldHMmJlcuZmFjZWFwaS5uZXRzLnRpbnlGYWNlRGV0ZWN0b3ImJlcuZmFjZWFwaS5UaW55RmFjZURldGVjdG9yT3B0aW9ucykpeyBjYihudWxsKTsgcmV0dXJuOyB9CiAgICB2YXIgRD16eURldCgpOwogICAgdmFyIHZ3PXYudmlkZW9XaWR0aHx8NjQwLCB2aD12LnZpZGVvSGVpZ2h0fHw0ODA7CiAgICB2YXIgZHc9MTYwLCBkaD1NYXRoLm1heCg2MCxNYXRoLnJvdW5kKGR3KnZoL3Z3KSk7CiAgICB2YXIgYz1ELmN2Q2FyYTsKICAgIGlmKCFjKXsgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsgRC5jdkNhcmE9YzsgfQogICAgaWYoYy53aWR0aCE9PWR3fHxjLmhlaWdodCE9PWRoKXsgYy53aWR0aD1kdzsgYy5oZWlnaHQ9ZGg7IH0KICAgIHZhciBnPWMuZ2V0Q29udGV4dCgnMmQnKTsgaWYoIWcpeyBjYihudWxsKTsgcmV0dXJuOyB9CiAgICBnLmRyYXdJbWFnZSh2LDAsMCxkdyxkaCk7CiAgICB2YXIgb3B0PW5ldyBXLmZhY2VhcGkuVGlueUZhY2VEZXRlY3Rvck9wdGlvbnMoe2lucHV0U2l6ZToxNjAsIHNjb3JlVGhyZXNob2xkOjAuNX0pOwogICAgVy5mYWNlYXBpLmRldGVjdFNpbmdsZUZhY2UoYyxvcHQpLnRoZW4oZnVuY3Rpb24ocil7CiAgICAgIHRyeXsKICAgICAgICBpZighcnx8IXIuZGV0ZWN0aW9uKXsgY2Ioe3Zpc3RhOmZhbHNlLCBvazpmYWxzZSwgdDpEYXRlLm5vdygpfSk7IHJldHVybjsgfQogICAgICAgIHZhciBiPXIuZGV0ZWN0aW9uLmJveDsKICAgICAgICB2YXIgZng9KGIueCtiLndpZHRoLzIpL2R3LCBmeT0oYi55K2IuaGVpZ2h0LzIpL2RoOwogICAgICAgIHZhciB0YW09Yi5oZWlnaHQvZGg7CiAgICAgICAgdmFyIG9rPShNYXRoLmFicyhmeC0wLjUpPD0wLjE0KSYmKE1hdGguYWJzKGZ5LTAuNTUpPD0wLjE3KSYmdGFtPj0wLjI4JiZ0YW08PTAuODg7CiAgICAgICAgdmFyIHRhbWw9KHRhbTwwLjI4KT8nbGVqb3MnOigodGFtPjAuODgpPydjZXJjYSc6J2JpZW4nKTsKICAgICAgICBjYih7dmlzdGE6dHJ1ZSwgb2s6b2ssIHRhbTp0YW1sLCB0OkRhdGUubm93KCl9KTsKICAgICAgfWNhdGNoKGUpeyBjYihudWxsKTsgfQogICAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgY2IobnVsbCk7IH0pOwogIH1jYXRjaChlKXsgY2IobnVsbCk7IH0KfQpmdW5jdGlvbiBlbm1hcmNhclZlcmRlKHBzSWQsIHYpewogIC8qIHY5OiBlc3F1aW5hcyB2ZXJkZXMgcXVlIFNJR1VFTiBhbCBkb2N1bWVudG8gKHBzIDIgeSAzKSB5IE9WQUxPIGRlIHJvc3RybyAocHMgNCkgKi8KICB0cnl7CiAgICB2YXIgT1Y9eycyJzonb3ZGJywnMyc6J292QScsJzQnOidvdlMnfTsKICAgIHZhciBvdklkPU9WW3BzSWRdOwogICAgaWYoIW92SWQpeyByZXR1cm47IH0KICAgIHZhciBzdElkPShwc0lkPT09JzInKT8nc3RGJzooKHBzSWQ9PT0nMycpPydzdEEnOidzdFYnKTsKICAgIHZhciBEPXp5RGV0KCk7CiAgICB2YXIgc3Q9RFtwc0lkXTsKICAgIGlmKCFzdCl7IHN0PURbcHNJZF09e2NhamE6bnVsbCwgdDotMWU5LCBlc3RhZG86JycsIGl2Om51bGx9OyB9CiAgICBzdC50MD1EYXRlLm5vdygpOyBzdC5jYWphPW51bGw7IHN0LmVzdGFkbz0nJzsKICAgIHZhciBwaW50YXJEb2M9ZnVuY3Rpb24oY2FqYSwgZXN0YWRvKXsKICAgICAgdHJ5ewogICAgICAgIHZhciBvdj0kKG92SWQpOyBpZighb3YpeyByZXR1cm47IH0KICAgICAgICB2YXIgdnc9KHYmJnYudmlkZW9XaWR0aCl8fDAsIHZoPSh2JiZ2LnZpZGVvSGVpZ2h0KXx8MDsKICAgICAgICBpZighdnd8fCF2aCl7IHJldHVybjsgfQogICAgICAgIGlmKG92LndpZHRoIT09dnd8fG92LmhlaWdodCE9PXZoKXsgb3Yud2lkdGg9dnc7IG92LmhlaWdodD12aDsgfQogICAgICAgIHZhciBnPW92LmdldENvbnRleHQoJzJkJyk7IGlmKCFnKXsgcmV0dXJuOyB9CiAgICAgICAgZy5jbGVhclJlY3QoMCwwLHZ3LHZoKTsKICAgICAgICB2YXIgeCx5LHcsaDsKICAgICAgICBpZighY2FqYSl7IHg9TWF0aC5yb3VuZCh2dyowLjA3KTsgeT1NYXRoLnJvdW5kKHZoKjAuMDkpOyB3PXZ3LXgqMjsgaD12aC15KjI7IH0KICAgICAgICBlbHNleyB4PWNhamEueDsgeT1jYWphLnk7IHc9Y2FqYS53OyBoPWNhamEuaDsgfQogICAgICAgIGlmKHc8MTB8fGg8MTApeyByZXR1cm47IH0KICAgICAgICB2YXIgY29sPShlc3RhZG89PT0nb2snKT8nIzNmYjk1MCc6KChlc3RhZG89PT0nbWFsJyk/JyNjMDM5MmInOicjZTNiMzQxJyk7CiAgICAgICAgZy5zdHJva2VTdHlsZT1jb2w7IGcubGluZVdpZHRoPTU7CiAgICAgICAgdmFyIEw9TWF0aC5yb3VuZChNYXRoLm1pbih3LGgpKihjYWphPzAuMTY6MC4xNCkpOwogICAgICAgIGcuYmVnaW5QYXRoKCk7CiAgICAgICAgZy5tb3ZlVG8oeCx5K0wpOyBnLmxpbmVUbyh4LHkpOyBnLmxpbmVUbyh4K0wseSk7CiAgICAgICAgZy5tb3ZlVG8oeCt3LUwseSk7IGcubGluZVRvKHgrdyx5KTsgZy5saW5lVG8oeCt3LHkrTCk7CiAgICAgICAgZy5tb3ZlVG8oeCt3LHkraC1MKTsgZy5saW5lVG8oeCt3LHkraCk7IGcubGluZVRvKHgrdy1MLHkraCk7CiAgICAgICAgZy5tb3ZlVG8oeCtMLHkraCk7IGcubGluZVRvKHgseStoKTsgZy5saW5lVG8oeCx5K2gtTCk7CiAgICAgICAgZy5zdHJva2UoKTsKICAgICAgICBnLnNhdmUoKTsKICAgICAgICBnLmdsb2JhbEFscGhhPWNhamE/MC40NTowLjIwOwogICAgICAgIGcubGluZVdpZHRoPTEuNjsgZy5zdHJva2VSZWN0KHgseSx3LGgpOwogICAgICAgIGcucmVzdG9yZSgpOwogICAgICB9Y2F0Y2goZSl7fQogICAgfTsKICAgIHZhciBwaW50YXJPdmFsbz1mdW5jdGlvbihlc3RhZG8pewogICAgICB0cnl7CiAgICAgICAgdmFyIG92PSQob3ZJZCk7IGlmKCFvdil7IHJldHVybjsgfQogICAgICAgIHZhciB2dz0odiYmdi52aWRlb1dpZHRoKXx8MCwgdmg9KHYmJnYudmlkZW9IZWlnaHQpfHwwOwogICAgICAgIGlmKCF2d3x8IXZoKXsgcmV0dXJuOyB9CiAgICAgICAgaWYob3Yud2lkdGghPT12d3x8b3YuaGVpZ2h0IT09dmgpeyBvdi53aWR0aD12dzsgb3YuaGVpZ2h0PXZoOyB9CiAgICAgICAgdmFyIGc9b3YuZ2V0Q29udGV4dCgnMmQnKTsgaWYoIWcpeyByZXR1cm47IH0KICAgICAgICBnLmNsZWFyUmVjdCgwLDAsdncsdmgpOwogICAgICAgIHZhciBjeD12dyowLjUsIGN5PXZoKjAuNTIsIHJ4PXZ3KjAuMzAsIHJ5PXZoKjAuNDA7CiAgICAgICAgdmFyIGNvbD0oZXN0YWRvPT09J29rJyk/JyMzZmI5NTAnOigoZXN0YWRvPT09J2NhcmEnKT8nI2UzYjM0MSc6JyM5YWEwYTYnKTsKICAgICAgICBnLnNhdmUoKTsKICAgICAgICBnLnN0cm9rZVN0eWxlPWNvbDsgZy5saW5lV2lkdGg9NjsKICAgICAgICBnLmJlZ2luUGF0aCgpOyBpZihnLmVsbGlwc2UpeyBnLmVsbGlwc2UoY3gsY3kscngscnksMCwwLE1hdGguUEkqMik7IH0gZWxzZSB7IGcuc3Ryb2tlUmVjdChjeC1yeCxjeS1yeSxyeCoyLHJ5KjIpOyB9CiAgICAgICAgZy5zdHJva2UoKTsKICAgICAgICBnLmdsb2JhbEFscGhhPTAuMTg7IGcubGluZVdpZHRoPTE0OwogICAgICAgIGcuYmVnaW5QYXRoKCk7IGlmKGcuZWxsaXBzZSl7IGcuZWxsaXBzZShjeCxjeSxyeCxyeSwwLDAsTWF0aC5QSSoyKTsgfSBlbHNlIHsgZy5zdHJva2VSZWN0KGN4LXJ4LGN5LXJ5LHJ4KjIscnkqMik7IH0KICAgICAgICBnLnN0cm9rZSgpOwogICAgICAgIGcucmVzdG9yZSgpOwogICAgICB9Y2F0Y2goZSl7fQogICAgfTsKICAgIHZhciB1bHRpbW89Jyc7CiAgICB2YXIgYXZpc2FyPWZ1bmN0aW9uKGNvZGUsdHh0LGNvbG9yKXsgaWYoY29kZSE9PXVsdGltbyl7IHVsdGltbz1jb2RlOyBtc2coc3RJZCx0eHQsY29sb3IpOyB9IH07CiAgICBpZihwc0lkPT09JzQnKXsKICAgICAgcGludGFyT3ZhbG8oJycpOwogICAgICBhdmlzYXIoJ2luaScsJ1BvbiB0dSBjYXJhIGRlbnRybyBkZWwgT1ZBTE8uIENhcHR1cmEgY3VhbmRvIGVsIG92YWxvIGVzdGUgVkVSREUuJywnI2E2MCcpOwogICAgICBpZihzdC5pdil7IHRyeXsgY2xlYXJJbnRlcnZhbChzdC5pdik7IH1jYXRjaChlKXt9IH0KICAgICAgc3QuaXY9c2V0SW50ZXJ2YWwoZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICBpZighc3RyZWFtc1twc0lkXSl7IHJldHVybjsgfQogICAgICAgICAgYnVzY2FyQ2FyYVZpdmEodixmdW5jdGlvbihpbmZvKXsKICAgICAgICAgICAgdHJ5ewogICAgICAgICAgICAgIEVTVC5jYXJhVml2YT1pbmZvOwogICAgICAgICAgICAgIHZhciBlMj0oaW5mbyYmaW5mby5vayk/J29rJzooKGluZm8mJmluZm8udmlzdGEpPydjYXJhJzonbm9uZScpOwogICAgICAgICAgICAgIHBpbnRhck92YWxvKGUyKTsKICAgICAgICAgICAgICBpZighaW5mbyl7IGF2aXNhcignbm9uZScsJ1ByZXBhcmFuZG8gZWwgZGV0ZWN0b3IgZmFjaWFsLi4uIGVzcGVyYSB1biBtb21lbnRvLicsJyNhNjAnKTsgfQogICAgICAgICAgICAgIGVsc2UgaWYoaW5mby5vayl7IGF2aXNhcignb2snLCdDYXJhIGNlbnRyYWRhLiBUb2NhIENBUFRVUkFSLicsJyMwODAnKTsgfQogICAgICAgICAgICAgIGVsc2UgaWYoaW5mby50YW09PT0nbGVqb3MnKXsgYXZpc2FyKCdsZWpvcycsJ0FDRVJDQVRFIHVuIHBvY28gYSBsYSBjYW1hcmE6IHR1IGNhcmEgc2UgdmUgbXV5IHBlcXVlbmEuJywnI2E2MCcpOyB9CiAgICAgICAgICAgICAgZWxzZSBpZihpbmZvLnRhbT09PSdjZXJjYScpeyBhdmlzYXIoJ2NlcmNhJywnQUxFSkFURSB1biBwb2NvIHBhcmEgcXVlIHR1IGNhcmEgcXVlcGEgZW4gZWwgb3ZhbG8uJywnI2E2MCcpOyB9CiAgICAgICAgICAgICAgZWxzZSBpZihpbmZvLnZpc3RhKXsgYXZpc2FyKCdmdWVyYScsJ011ZXZlIHR1IGNhcmEgYWwgQ0VOVFJPIGRlbCBvdmFsbywgbWlyYW5kbyBhIGxhIGNhbWFyYS4nLCcjYTYwJyk7IH0KICAgICAgICAgICAgICBlbHNleyBhdmlzYXIoJ25vZGV0JywnQnVzY2FuZG8gdHUgY2FyYS4uLiBidWVuYSBsdXosIHNpbiBnb3JyYS4nLCcjYTYwJyk7IH0KICAgICAgICAgICAgfWNhdGNoKGUzKXt9CiAgICAgICAgICB9KTsKICAgICAgICB9Y2F0Y2goZSl7fQogICAgICB9LDUyMCk7CiAgICB9ZWxzZXsKICAgICAgcGludGFyRG9jKG51bGwsJycpOwogICAgICBhdmlzYXIoJ2luaScsJ1BvbiBlbCBkb2N1bWVudG8gZW4gZWwgbWFyY286IGxhcyBlc3F1aW5hcyB2ZXJkZXMgbG8gc2lndWVuLicsJyNhNjAnKTsKICAgICAgaWYoc3QuaXYpeyB0cnl7IGNsZWFySW50ZXJ2YWwoc3QuaXYpOyB9Y2F0Y2goZSl7fSB9CiAgICAgIHN0Lml2PXNldEludGVydmFsKGZ1bmN0aW9uKCl7CiAgICAgICAgdHJ5ewogICAgICAgICAgaWYoIXN0cmVhbXNbcHNJZF0peyByZXR1cm47IH0KICAgICAgICAgIHZhciBjYWphPWRldGVjdGFyRG9jQm94KHYpOwogICAgICAgICAgaWYoY2FqYSl7CiAgICAgICAgICAgIHZhciBwcmV2PXN0LmNhamE7CiAgICAgICAgICAgIGlmKHByZXYpeyBjYWphPXt4OnByZXYueCowLjQ1K2NhamEueCowLjU1LCB5OnByZXYueSowLjQ1K2NhamEueSowLjU1LCB3OnByZXYudyowLjQ1K2NhamEudyowLjU1LCBoOnByZXYuaCowLjQ1K2NhamEuaCowLjU1fTsgfQogICAgICAgICAgICBzdC5jYWphPWNhamE7IHN0LnQ9RGF0ZS5ub3coKTsKICAgICAgICAgICAgdmFyIGZyYWM9KGNhamEudypjYWphLmgpLygoKHYudmlkZW9XaWR0aHx8MSkpKigodi52aWRlb0hlaWdodHx8MSkpKTsKICAgICAgICAgICAgdmFyIGUyPShmcmFjPDAuMTZ8fGZyYWM+MC45Nik/J21hbCc6J29rJzsKICAgICAgICAgICAgcGludGFyRG9jKGNhamEsZTIpOwogICAgICAgICAgICBpZihlMj09PSdvaycpeyBhdmlzYXIoJ29rJywnRG9jdW1lbnRvIGRldGVjdGFkby4gVG9jYSBDQVBUVVJBUi4nLCcjMDgwJyk7IH0KICAgICAgICAgICAgZWxzZSBpZihmcmFjPDAuMTYpeyBhdmlzYXIoJ2ZhcicsJ0FDRVJDQVRFOiBlbCBkb2N1bWVudG8gc2UgdmUgbXV5IHBlcXVlbm8gZW4gbGEgZm90by4nLCcjYTYwJyk7IH0KICAgICAgICAgICAgZWxzZXsgYXZpc2FyKCdiaWcnLCdFbCBkb2N1bWVudG8gc2Ugc2FsZSBkZWwgbWFyY286IGFsZWphbG8gdW4gcG9jby4nLCcjYTYwJyk7IH0KICAgICAgICAgIH1lbHNlIGlmKERhdGUubm93KCktc3QudD4xMjAwKXsKICAgICAgICAgICAgc3QuY2FqYT1udWxsOyBwaW50YXJEb2MobnVsbCwnJyk7CiAgICAgICAgICAgIGF2aXNhcignbm9uZScsJ0J1c2NhbmRvIGVsIGRvY3VtZW50by4uLiBsbGVuYWxvIGVuIGVsIG1hcmNvLCBzaW4gYnJpbGxvLicsJyNhNjAnKTsKICAgICAgICAgIH0KICAgICAgICB9Y2F0Y2goZSl7fQogICAgICB9LDMwMCk7CiAgICB9CiAgICBpZighdi5fX3p5TWFyY28pewogICAgICB2Ll9fenlNYXJjbz0xOwogICAgICB2LmFkZEV2ZW50TGlzdGVuZXIoJ3BsYXlpbmcnLGZ1bmN0aW9uKCl7IHRyeXsgaWYocHNJZD09PSc0Jyl7IHBpbnRhck92YWxvKCcnKTsgfSBlbHNlIHsgcGludGFyRG9jKG51bGwsJycpOyB9IH1jYXRjaChlKXt9IH0pOwogICAgICB2LmFkZEV2ZW50TGlzdGVuZXIoJ2xvYWRlZG1ldGFkYXRhJyxmdW5jdGlvbigpeyB0cnl7IGlmKHBzSWQ9PT0nNCcpeyBwaW50YXJPdmFsbygnJyk7IH0gZWxzZSB7IHBpbnRhckRvYyhudWxsLCcnKTsgfSB9Y2F0Y2goZSl7fSB9KTsKICAgIH0KICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIGFicmlyQ2FtKHBzSWQsIGZhY2luZywgc3RJZCwgY2FwSWQpewogIHZhciB2PWZpbmRWaWRlbyhwc0lkKTsKICBpZighdil7IG1zZyhzdElkLCdObyBlbmNvbnRyZSBlbCB2aWRlbyBkZSBsYSBjYW1hcmEgZW4gbGEgcGFnaW5hLicsICcjYzAwJyk7IHJldHVybiBQcm9taXNlLnJlamVjdChuZXcgRXJyb3IoJ3NpbiB2aWRlbycpKTsgfQogIGlmKCFuYXZpZ2F0b3IubWVkaWFEZXZpY2VzIHx8ICFuYXZpZ2F0b3IubWVkaWFEZXZpY2VzLmdldFVzZXJNZWRpYSl7CiAgICBtc2coc3RJZCwnVHUgbmF2ZWdhZG9yIG5vIHBlcm1pdGUgY2FtYXJhLiBVc2EgbGEgb3BjaW9uIGRlIGdhbGVyaWEuJywgJyNjMDAnKTsKICAgIHJldHVybiBQcm9taXNlLnJlamVjdChuZXcgRXJyb3IoJ3NpbiBjYW1hcmEnKSk7CiAgfQogIHBhcmFyQ2FtKHBzSWQpOwogIHZhciB6b25hPSQoJ3Z6JytsZXRyYURlKHBzSWQpKTsKICBpZih6b25hKXsgem9uYS5zdHlsZS5kaXNwbGF5PSdibG9jayc7IH0KICBtc2coc3RJZCwnUGlkaWVuZG8gcGVybWlzbyBkZSBjYW1hcmEuLi4nLCcnKTsKICByZXR1cm4gbmF2aWdhdG9yLm1lZGlhRGV2aWNlcy5nZXRVc2VyTWVkaWEoe2F1ZGlvOmZhbHNlLCB2aWRlbzp7ZmFjaW5nTW9kZTpmYWNpbmcsIHdpZHRoOntpZGVhbDoxMjgwfSwgaGVpZ2h0OntpZGVhbDo3MjB9fX0pLnRoZW4oZnVuY3Rpb24oc3QpewogICAgc3RyZWFtc1twc0lkXT1zdDsKICAgIHYuc3JjT2JqZWN0PXN0OwogICAgdHJ5eyB2LnNldEF0dHJpYnV0ZSgncGxheXNpbmxpbmUnLCdwbGF5c2lubGluZScpOyB9Y2F0Y2goZSl7fQogICAgdi5tdXRlZD10cnVlOwogICAgdmFyIHA9di5wbGF5KCk7IGlmKHAmJnAuY2F0Y2gpeyBwLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH0KICAgIGVzdGlsb0NoaWNvKHYpOwogICAgdmFyIGNhcD0kKGNhcElkKTsKICAgIGlmKGNhcCl7IGNhcC5kaXNhYmxlZD1mYWxzZTsgY2FwLnN0eWxlLmRpc3BsYXk9Jyc7IGNhcC5zdHlsZS52aXNpYmlsaXR5PSd2aXNpYmxlJzsgY2FwLnN0eWxlLnBvaW50ZXJFdmVudHM9J2F1dG8nOyBjYXAuc3R5bGUucG9zaXRpb249Y2FwLnN0eWxlLnBvc2l0aW9ufHwncmVsYXRpdmUnOyBjYXAuc3R5bGUuekluZGV4PSc5OTk5JzsgfQogICAgdmFyIE9WPXsnMic6J292RicsJzMnOidvdkEnLCc0Jzonb3ZTJ307CiAgICB2YXIgb3Y9JChPVltwc0lkXSk7CiAgICBpZihvdil7IG92LnN0eWxlLnBvaW50ZXJFdmVudHM9J25vbmUnOyB9CiAgICBlbm1hcmNhclZlcmRlKHBzSWQsIHYpOwogICAgdmFyIHE9KHBzSWQ9PT0nNCcpOwogICAgbXNnKHN0SWQsIHE/J0NhbWFyYSBsaXN0YS4gUG9uIHR1IGNhcmEgZW4gZWwgT1ZBTE86IGNhcHR1cmEgY3VhbmRvIGVsIG92YWxvIGVzdGUgVkVSREUuJzonQ2FtYXJhIGxpc3RhLiBMYXMgZXNxdWluYXMgdmVyZGVzIHNpZ3VlbiBhbCBkb2N1bWVudG86IGxsZW5hbG8gZW4gZWwgbWFyY28geSB0b2NhIENBUFRVUkFSLicsJyMwODAnKTsKICAgIHJldHVybiB0cnVlOwogIH0pLmNhdGNoKGZ1bmN0aW9uKGUpewogICAgaWYoem9uYSl7IHRyeXsgem9uYS5zdHlsZS5kaXNwbGF5PSdub25lJzsgfWNhdGNoKGUyKXt9IH0KICAgIG1zZyhzdElkLCdObyBwdWRlIGFicmlyIGxhIGNhbWFyYSAoJysoZSYmZS5uYW1lP2UubmFtZTonZXJyb3InKSsnKS4gUHVlZGVzIHVzYXIgbGEgZ2FsZXJpYSBvIHJldmlzYSBlbCBwZXJtaXNvLicsJyNjMDAnKTsKICAgIHRocm93IGU7CiAgfSk7Cn0KZnVuY3Rpb24gcGFyYXJDYW0ocHNJZCl7CiAgdmFyIHN0PXN0cmVhbXNbcHNJZF07CiAgaWYoc3QpewogICAgdHJ5eyBzdC5nZXRUcmFja3MoKS5mb3JFYWNoKGZ1bmN0aW9uKHQpeyB0cnl7IHQuc3RvcCgpOyB9Y2F0Y2goZSl7fSB9KTsgfWNhdGNoKGUpe30KICB9CiAgc3RyZWFtc1twc0lkXT1udWxsOwogIHRyeXsKICAgIHZhciBEPXp5RGV0KCksIHN0RD1EW3BzSWRdOwogICAgaWYoc3REJiZzdEQuaXYpeyBjbGVhckludGVydmFsKHN0RC5pdik7IHN0RC5pdj1udWxsOyB9CiAgICBpZihwc0lkPT09JzQnKXsgRVNULmNhcmFWaXZhPW51bGw7IH0KICB9Y2F0Y2goZSl7fQogIHRyeXsKICAgIHZhciB6b25hPSQoJ3Z6JytsZXRyYURlKHBzSWQpKTsKICAgIGlmKHpvbmEpeyB6b25hLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgICB2YXIgT1Y9eycyJzonb3ZGJywnMyc6J292QScsJzQnOidvdlMnfTsKICAgIHZhciBvdj0kKE9WW3BzSWRdKTsKICAgIGlmKG92KXsgdmFyIGc9b3YuZ2V0Q29udGV4dCgnMmQnKTsgaWYoZyl7IGcuY2xlYXJSZWN0KDAsMCxvdi53aWR0aHx8MSxvdi5oZWlnaHR8fDEpOyB9IH0KICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIHBhcmFyVG9kYXMoKXsgdmFyIGs7IGZvcihrIGluIHN0cmVhbXMpeyBwYXJhckNhbShrKTsgfSB9CmZ1bmN0aW9uIGNhcHR1cmFyVmlkZW8ocHNJZCwgbWF4RGltKXsKICB2YXIgdj1maW5kVmlkZW8ocHNJZCk7CiAgaWYoIXYgfHwgIXYudmlkZW9XaWR0aCB8fCAhc3RyZWFtc1twc0lkXSl7IHJldHVybiBudWxsOyB9CiAgdmFyIHc9di52aWRlb1dpZHRoLCBoPXYudmlkZW9IZWlnaHQ7CiAgdmFyIHNjPU1hdGgubWluKDEsKG1heERpbXx8MTAyNCkvTWF0aC5tYXgodyxoKSk7CiAgdmFyIGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7CiAgYy53aWR0aD1NYXRoLnJvdW5kKHcqc2MpOyBjLmhlaWdodD1NYXRoLnJvdW5kKGgqc2MpOwogIGMuZ2V0Q29udGV4dCgnMmQnKS5kcmF3SW1hZ2UodiwwLDAsYy53aWR0aCxjLmhlaWdodCk7CiAgdmFyIGQ9Yy50b0RhdGFVUkwoJ2ltYWdlL2pwZWcnLDAuODUpOwogIHBhcmFyQ2FtKHBzSWQpOwogIHJldHVybiBkOwp9CmZ1bmN0aW9uIGRvd25zY2FsZShkYXRhVXJsLCBtYXhEaW0pewogIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpewogICAgdmFyIGltPW5ldyBJbWFnZSgpOwogICAgaW0ub25sb2FkPWZ1bmN0aW9uKCl7CiAgICAgIHZhciBzYz1NYXRoLm1pbigxLChtYXhEaW18fDEwMjQpL01hdGgubWF4KGltLndpZHRoLGltLmhlaWdodCkpOwogICAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgICAgYy53aWR0aD1NYXRoLm1heCgxLE1hdGgucm91bmQoaW0ud2lkdGgqc2MpKTsKICAgICAgYy5oZWlnaHQ9TWF0aC5tYXgoMSxNYXRoLnJvdW5kKGltLmhlaWdodCpzYykpOwogICAgICBjLmdldENvbnRleHQoJzJkJykuZHJhd0ltYWdlKGltLDAsMCxjLndpZHRoLGMuaGVpZ2h0KTsKICAgICAgcmVzKGMudG9EYXRhVVJMKCdpbWFnZS9qcGVnJywwLjg1KSk7CiAgICB9OwogICAgaW0ub25lcnJvcj1mdW5jdGlvbigpeyByZXMoZGF0YVVybCk7IH07CiAgICBpbS5zcmM9ZGF0YVVybDsKICB9KTsKfQpmdW5jdGlvbiBhcmNoaXZvQURhdG9zKGZpbGUpewogIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMscmVqKXsKICAgIHZhciBmcj1uZXcgRmlsZVJlYWRlcigpOwogICAgZnIub25sb2FkPWZ1bmN0aW9uKCl7IHJlcyhTdHJpbmcoZnIucmVzdWx0KSk7IH07CiAgICBmci5vbmVycm9yPWZ1bmN0aW9uKCl7IHJlaihuZXcgRXJyb3IoJ25vIHB1ZGUgbGVlciBlbCBhcmNoaXZvJykpOyB9OwogICAgZnIucmVhZEFzRGF0YVVSTChmaWxlKTsKICB9KTsKfQoKLyogPT09PT09PT09PT09PT09PT0gT0NSIGNvbiBjYWNoZSA9PT09PT09PT09PT09PT09PSAqLwp2YXIgY2FjaGVPY3I9e307CmZ1bmN0aW9uIGhhY2VyT2NyKGRhdGFVcmwpewogIGlmKGNhY2hlT2NyW2RhdGFVcmxdKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZShjYWNoZU9jcltkYXRhVXJsXSk7IH0KICBpZih0eXBlb2YgVGVzc2VyYWN0PT09J3VuZGVmaW5lZCcgfHwgIVRlc3NlcmFjdC5yZWNvZ25pemUpewogICAgcmV0dXJuIFByb21pc2UucmVqZWN0KG5ldyBFcnJvcignT0NSIG5vIGRpc3BvbmlibGUsIHJldmlzYSB0dSBpbnRlcm5ldCcpKTsKICB9CiAgcmV0dXJuIFRlc3NlcmFjdC5yZWNvZ25pemUoZGF0YVVybCwnc3BhK2VuZycse2xvZ2dlcjpmdW5jdGlvbigpe319KS50aGVuKGZ1bmN0aW9uKHIpewogICAgdmFyIHQ9KHImJnIuZGF0YSYmci5kYXRhLnRleHQpP3IuZGF0YS50ZXh0OicnOwogICAgY2FjaGVPY3JbZGF0YVVybF09dDsKICAgIHJldHVybiB0OwogIH0pLmNhdGNoKGZ1bmN0aW9uKGUpewogICAgcmV0dXJuIFRlc3NlcmFjdC5yZWNvZ25pemUoZGF0YVVybCwnZW5nJyx7bG9nZ2VyOmZ1bmN0aW9uKCl7fX0pLnRoZW4oZnVuY3Rpb24ocjIpewogICAgICB2YXIgdDI9KHIyJiZyMi5kYXRhJiZyMi5kYXRhLnRleHQpP3IyLmRhdGEudGV4dDonJzsKICAgICAgY2FjaGVPY3JbZGF0YVVybF09dDI7CiAgICAgIHJldHVybiB0MjsKICAgIH0pOwogIH0pOwp9CgovKiA9PT09PT09PT09PT09PT09PSBiaW9tZXRyaWEgZmFjaWFsID09PT09PT09PT09PT09PT09ICovCnZhciBmYWNlUD1udWxsOwpmdW5jdGlvbiBjYXJnYXJGYWNlQXBpKCl7CiAgaWYoZmFjZVApeyByZXR1cm4gZmFjZVA7IH0KICBmYWNlUD1uZXcgUHJvbWlzZShmdW5jdGlvbihyZXMscmVqKXsKICAgIGZ1bmN0aW9uIGxpc3RvKCl7IHJldHVybiBXLmZhY2VhcGkgJiYgVy5mYWNlYXBpLm5ldHMgJiYgVy5mYWNlYXBpLm5ldHMudGlueUZhY2VEZXRlY3RvciAmJiBXLmZhY2VhcGkubmV0cy5mYWNlUmVjb2duaXRpb25OZXQ7IH0KICAgIGZ1bmN0aW9uIG1vZGVsb3MoYmFzZSl7CiAgICAgIHJldHVybiBQcm9taXNlLmFsbChbCiAgICAgICAgVy5mYWNlYXBpLm5ldHMudGlueUZhY2VEZXRlY3Rvci5sb2FkRnJvbVVyaShiYXNlKSwKICAgICAgICBXLmZhY2VhcGkubmV0cy5mYWNlTGFuZG1hcms2OE5ldC5sb2FkRnJvbVVyaShiYXNlKSwKICAgICAgICBXLmZhY2VhcGkubmV0cy5mYWNlUmVjb2duaXRpb25OZXQubG9hZEZyb21VcmkoYmFzZSkKICAgICAgXSk7CiAgICB9CiAgICBmdW5jdGlvbiBpbmljaWFyKCl7CiAgICAgIHZhciBiYXNlPSdodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvZ2gvanVzdGFkdWRld2hvaGFja3MvZmFjZS1hcGkuanNAMC4yMi4yL3dlaWdodHMnOwogICAgICBtb2RlbG9zKGJhc2UpLnRoZW4oZnVuY3Rpb24oKXsgcmVzKCk7IH0sIGZ1bmN0aW9uKCl7IG1vZGVsb3MoJ2h0dHBzOi8vanVzdGFkdWRld2hvaGFja3MuZ2l0aHViLmlvL2ZhY2UtYXBpLmpzL21vZGVscycpLnRoZW4oZnVuY3Rpb24oKXsgcmVzKCk7IH0sIHJlaik7IH0pOwogICAgfQogICAgaWYobGlzdG8oKSl7IGluaWNpYXIoKTsgcmV0dXJuOyB9CiAgICB2YXIgcz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdzY3JpcHQnKTsKICAgIHMuc3JjPSdodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvbnBtL2ZhY2UtYXBpLmpzQDAuMjIuMi9kaXN0L2ZhY2UtYXBpLm1pbi5qcyc7CiAgICBzLm9ubG9hZD1mdW5jdGlvbigpeyBpZihsaXN0bygpKXsgaW5pY2lhcigpOyB9IGVsc2UgeyByZWoobmV3IEVycm9yKCdmYWNlYXBpIG5vIHF1ZWRvIGxpc3RvJykpOyB9IH07CiAgICBzLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVqKG5ldyBFcnJvcignbm8gc2UgcHVkbyBjYXJnYXIgZWwgdmVyaWZpY2Fkb3IgZmFjaWFsJykpOyB9OwogICAgZG9jdW1lbnQuaGVhZC5hcHBlbmRDaGlsZChzKTsKICB9KTsKICByZXR1cm4gZmFjZVA7Cn0KZnVuY3Rpb24gY29uVGltZW91dChwLCBtcyl7CiAgcmV0dXJuIFByb21pc2UucmFjZShbcCwgbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsgc2V0VGltZW91dChmdW5jdGlvbigpeyByZXMobnVsbCk7IH0sIG1zKTsgfSldKTsKfQpmdW5jdGlvbiBkZXRlY3RhckNhcmFFbihkYXRhVXJsKXsKICByZXR1cm4gY2FyZ2FyRmFjZUFwaSgpLnRoZW4oZnVuY3Rpb24oKXsKICAgIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpewogICAgICB2YXIgaW09bmV3IEltYWdlKCk7CiAgICAgIGltLm9ubG9hZD1mdW5jdGlvbigpewogICAgICAgIHRyeXsKICAgICAgICAgIHZhciBvcHQ9bmV3IFcuZmFjZWFwaS5UaW55RmFjZURldGVjdG9yT3B0aW9ucyh7aW5wdXRTaXplOjMyMCwgc2NvcmVUaHJlc2hvbGQ6MC40fSk7CiAgICAgICAgICBXLmZhY2VhcGkuZGV0ZWN0U2luZ2xlRmFjZShpbSxvcHQpLndpdGhGYWNlTGFuZG1hcmtzKCkud2l0aEZhY2VEZXNjcmlwdG9yKCkudGhlbihmdW5jdGlvbihyKXsgcmVzKHJ8fG51bGwpOyB9KS5jYXRjaChmdW5jdGlvbigpeyByZXMobnVsbCk7IH0pOwogICAgICAgIH1jYXRjaChlKXsgcmVzKG51bGwpOyB9CiAgICAgIH07CiAgICAgIGltLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVzKG51bGwpOyB9OwogICAgICBpbS5zcmM9ZGF0YVVybDsKICAgIH0pOwogIH0pLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiBudWxsOyB9KTsKfQpmdW5jdGlvbiBkaXN0RihhLGIpewogIHZhciBzPTAsaTsKICBmb3IoaT0wO2k8YS5sZW5ndGg7aSsrKXsgdmFyIGQ9YVtpXS1iW2ldOyBzKz1kKmQ7IH0KICByZXR1cm4gTWF0aC5zcXJ0KHMpOwp9CgovKiA9PT09PT09PT09PT09PT09PSBndWFyZGlhbiBkZSBvcmRlbiAxLTItMy00LTUgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gcGVybWl0aWRvSGFzdGEoKXsKICB2YXIgcD0xOwogIGlmKEVTVC5ub21icmVPayl7IHA9MjsgfQogIGlmKEVTVC5ub21icmVPayAmJiBFU1QuZnJlbnRlT2speyBwPTM7IH0KICBpZihFU1Qubm9tYnJlT2sgJiYgRVNULmZyZW50ZU9rICYmIChFU1QucmV2ZXJzb09rIHx8ICFFU1QubmVjZXNpdGFSZXZlcnNvKSl7IHA9NDsgfQogIGlmKEVTVC5zZWxmaWVPayAmJiBwPj00KXsgcD01OyB9CiAgcmV0dXJuIHA7Cn0KZnVuY3Rpb24gbW9zdHJhclBhc28obil7CiAgdmFyIGksZWw7CiAgZm9yKGk9MTtpPD01O2krKyl7CiAgICBlbD0kKCdwcycraSk7CiAgICBpZihlbCl7CiAgICAgIGVsLmNsYXNzTmFtZT0ncGFzbycrKGk9PT1uPycgYWN0JzonJyk7CiAgICAgIGVsLnN0eWxlLmRpc3BsYXk9Jyc7CiAgICB9CiAgfQogIHZhciBwcj0kKCdwcm9nJyk7CiAgaWYocHIpeyBwci50ZXh0Q29udGVudD0nUEFTTyAnK24rJyBERSA1JzsgfQogIGlmKEVTVC5wYXNvPj0yICYmIEVTVC5wYXNvPD00ICYmIEVTVC5wYXNvIT09bil7IHRyeXsgcGFyYXJDYW0oRVNULnBhc28pOyB9Y2F0Y2goZSl7fSB9CiAgRVNULnBhc289bjsKICBpZihuPT09NSl7CiAgICB2YXIgYT0kKCdjbGF2ZScpLCBiPSQoJ2NsYXZlMicpOwogICAgaWYoYSl7IGEuZGlzYWJsZWQ9ZmFsc2U7IH0KICAgIGlmKGIpeyBiLmRpc2FibGVkPWZhbHNlOyB9CiAgICB2YXIgcmY9RVNULmZyZW50ZUltZz8nRnJlbnRlIE9LJzooRVNULmZyZW50ZVRleHRvPydGcmVudGUgT0snOidGQUxUQSBGUkVOVEUnKTsKICAgIHZhciBycj0oIUVTVC5uZWNlc2l0YVJldmVyc298fEVTVC5yZXZlcnNvSW1nfHxFU1QucmV2ZXJzb1RleHRvKT8nUmV2ZXJzbyBPSyc6J0ZBTFRBIFJFVkVSU08nOwogICAgdmFyIHJzPUVTVC5zZWxmaWVJbWc/J1NlbGZpZSBPSyc6J0ZBTFRBIFNFTEZJRSc7CiAgICB2YXIgdG9kbz0oRVNULmZyZW50ZUltZyYmRVNULnNlbGZpZUltZyYmKCFFU1QubmVjZXNpdGFSZXZlcnNvfHxFU1QucmV2ZXJzb0ltZ3x8RVNULnJldmVyc29UZXh0bykpOwogICAgbXNnKCd6eVJlc3VtZW41JywnVmVyaWZpY2FjaW9uIGZpbmFsOiAnK3JmKycgfCAnK3JyKycgfCAnK3JzKycuIEVzY3JpYmUgdHUgY2xhdmUgMiB2ZWNlcyB5IGNyZWEgdHUgWklELicsdG9kbz8nIzA4MCc6JyNjMDAnKTsKICB9CiAgdHJ5eyB2YXIgYWN0PSQoJ3BzJytuKTsgaWYoYWN0JiZhY3Quc2Nyb2xsSW50b1ZpZXcpeyBhY3Quc2Nyb2xsSW50b1ZpZXcoe2JlaGF2aW9yOidzbW9vdGgnLGJsb2NrOidzdGFydCd9KTsgfSB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIGF2YW56YXIobil7IG1vc3RyYXJQYXNvKG4pOyB9CmZ1bmN0aW9uIHZlcmlmaWNhcigpewogIHRyeXsKICAgIHZhciBhY3Q9ZG9jdW1lbnQucXVlcnlTZWxlY3RvcignLnBhc28uYWN0Jyk7CiAgICB2YXIgcm49YWN0JiZhY3QuaWQ/cGFyc2VJbnQoU3RyaW5nKGFjdC5pZCkucmVwbGFjZSgncHMnLCcnKSwxMCk6MDsKICAgIGlmKHJuPj0xJiZybjw9NSYmcm4hPT1FU1QucGFzbyl7IEVTVC5wYXNvPXJuOyB9CiAgfWNhdGNoKGUpe30KICB0cnl7IHZhbGlkYXJQYXNvMSh0cnVlKTsgfWNhdGNoKGUpe30KICB2YXIgcGVyPXBlcm1pdGlkb0hhc3RhKCk7CiAgaWYoRVNULnBhc28+cGVyKXsKICAgIGlmKHBlcj09PTEpeyBtc2coJ3p5R3VhcmRpYScsJ1BhcmEgc2VndWlyLCBlc2NyaWJlIHR1IG5vbWJyZSB5IGVsaWdlIGVsIHRpcG8gZGUgZG9jdW1lbnRvIGVuIGVsIHBhc28gMS4nLCcjYTYwJyk7IH0KICAgIGVsc2V7IG1zZygnenlHdWFyZGlhJywnVGUgcmVncmVzbyBhbCBwYXNvICcrcGVyKycgcGFyYSBzZWd1aXIgZW4gb3JkZW4uJywnI2E2MCcpOyB9CiAgICBtb3N0cmFyUGFzbyhwZXIpOwogIH0KICB2YXIgc2VsPSQoJ3RpcG9Eb2MnKTsKICBpZihzZWwgJiYgc2VsLnZhbHVlICYmIC9wYXNhcG9ydGV8cGFzc3BvcnQvaS50ZXN0KChzZWwub3B0aW9ucyYmc2VsLm9wdGlvbnNbc2VsLnNlbGVjdGVkSW5kZXhdJiZzZWwub3B0aW9uc1tzZWwuc2VsZWN0ZWRJbmRleF0udGV4dCl8fCcnKSl7CiAgICB2YXIgcHMzPSQoJ3BzMycpLCBucj0kKCdub3RhUmV2Jyk7CiAgICBpZihwczMpeyBwczMuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH0KICAgIGlmKG5yKXsgbnIuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH0KICB9Cn0KdmFyIHZ0aW1lcj1udWxsOwpmdW5jdGlvbiBwcm9ncmFtYXJWZXJpZmljYXIoKXsKICBpZih2dGltZXIpeyByZXR1cm47IH0KICB2dGltZXI9c2V0VGltZW91dChmdW5jdGlvbigpeyB2dGltZXI9bnVsbDsgdHJ5eyB2ZXJpZmljYXIoKTsgfWNhdGNoKGUpe30gfSwxMjApOwp9CnRyeXsKICBuZXcgTXV0YXRpb25PYnNlcnZlcihwcm9ncmFtYXJWZXJpZmljYXIpLm9ic2VydmUoZG9jdW1lbnQuYm9keSx7Y2hpbGRMaXN0OnRydWUsc3VidHJlZTp0cnVlLGF0dHJpYnV0ZXM6dHJ1ZSxhdHRyaWJ1dGVGaWx0ZXI6WydzdHlsZScsJ2NsYXNzJywnaGlkZGVuJywnZGlzYWJsZWQnXX0pOwp9Y2F0Y2goZSl7fQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyAxOiBzb2xvIGZvcm1hdG8gZGVsIG5vbWJyZSAodmFsaWRhIFNPTE8gYWwgY29udGludWFyLCBudW5jYSBtaWVudHJhcyBlc2NyaWJlcykgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gdmFsaWRhclBhc28xKHNpbGVuY2lvc28pewogIHZhciBpbnA9JCgnbm9tYnJlJyksIHNlbD0kKCd0aXBvRG9jJyk7CiAgdmFyIHY9aW5wPyhpbnAudmFsdWV8fCcnKS50cmltKCk6Jyc7CiAgdmFyIGxldHJhcz0vXltBLVphLXrDgcOJw43Dk8Oaw5zDkcOhw6nDrcOzw7rDvMOxXSsoIFtBLVphLXrDgcOJw43Dk8Oaw5zDkcOhw6nDrcOzw7rDvMOxXSspKiQvLnRlc3Qodik7CiAgdmFyIG5wPXY/di5zcGxpdCgvXHMrLykubGVuZ3RoOjA7CiAgdmFyIG9rPSh2Lmxlbmd0aD49NSAmJiBsZXRyYXMgJiYgbnA+PTIpOwogIHZhciB0PWNsYXNpZmljYXJUaXBvKCk7CiAgRVNULnRpcG89dC5rOwogIEVTVC5uZWNlc2l0YVJldmVyc289dC5yZXZlcnNvOwogIHZhciB0aXBvT2s9ISEoc2VsICYmIFN0cmluZyhzZWwudmFsdWV8fCcnKS5sZW5ndGg+MCk7CiAgRVNULm5vbWJyZU9rPW9rOwogIEVTVC5lc2NyaXRvPW5vcm0odik7CiAgaWYoc2lsZW5jaW9zbyl7IHJldHVybiBvayYmdGlwb09rOyB9CiAgaWYoaW5wKXsgaW5wLnN0eWxlLmJvcmRlckNvbG9yPW9rPycnOicjYzAwJzsgfQogIHZhciBtbm89Jyc7CiAgaWYoIW9rKXsgbW5vPXY/J0VzY3JpYmUgdHUgbm9tYnJlIHkgdHUgYXBlbGxpZG8gKHNvbG8gbGV0cmFzIHkgZXNwYWNpb3M7IHNpcnZlIGNvbiAxIG8gMiBub21icmVzIHkgMSBvIDIgYXBlbGxpZG9zKS4nOidFc2NyaWJlIHR1IG5vbWJyZSB5IHR1IGFwZWxsaWRvIHBhcmEgY29udGludWFyLic7IH0KICBtc2coJ3p5RXJyTm9tYnJlJyxtbm8sbW5vPycjYzAwJzonJyk7CiAgdmFyIG10aT10aXBvT2s/Jyc6J0VsaWdlIHR1IHRpcG8gZGUgZG9jdW1lbnRvIGVuIGxhIGxpc3RhLic7CiAgbXNnKCd6eUVyclRpcG8nLG10aSxtdGk/JyNjMDAnOicnKTsKICByZXR1cm4gb2smJnRpcG9PazsKfQpmdW5jdGlvbiBsaW1waWFyRXJyb3Jlc1Bhc28xKCl7CiAgdmFyIGUxPSQoJ3p5RXJyTm9tYnJlJyk7IGlmKGUxICYmIGUxLnRleHRDb250ZW50KXsgZTEudGV4dENvbnRlbnQ9Jyc7IGUxLnN0eWxlLmNvbG9yPScnOyB9CiAgdmFyIGUyPSQoJ3p5RXJyVGlwbycpOyBpZihlMiAmJiBlMi50ZXh0Q29udGVudCl7IGUyLnRleHRDb250ZW50PScnOyBlMi5zdHlsZS5jb2xvcj0nJzsgfQogIHZhciBpbnA9JCgnbm9tYnJlJyk7IGlmKGlucCAmJiBpbnAuc3R5bGUuYm9yZGVyQ29sb3IpeyBpbnAuc3R5bGUuYm9yZGVyQ29sb3I9Jyc7IH0KfQpmdW5jdGlvbiByZXNldGVhckRvY3VtZW50bygpewogIEVTVC5mcmVudGVPaz1mYWxzZTsgRVNULnJldmVyc29Paz1mYWxzZTsgRVNULnNlbGZpZU9rPWZhbHNlOyBFU1QuaW50ZW50b3M9MzsKfQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyAyOiBmcmVudGUgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gcHJvY2VzYXJGcmVudGUoZGF0YVVybCl7CiAgYnVzeSh0cnVlKTsKICBtc2coJ3N0RicsJ0xleWVuZG8gZWwgZG9jdW1lbnRvLi4uJywnJyk7CiAgRVNULmZyZW50ZUltZz1kYXRhVXJsOwogIHNob3dJbWcoJ3BGJyxkYXRhVXJsKTsKICB2YXIgcENhcmE9Y29uVGltZW91dChkZXRlY3RhckNhcmFFbihkYXRhVXJsKSwxMjAwMCk7CiAgdmFyIHBUeHQ9aGFjZXJPY3IoZGF0YVVybCkuY2F0Y2goZnVuY3Rpb24oZSl7IHJldHVybiAnT0NSX0VSUjonKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOicnKTsgfSk7CiAgUHJvbWlzZS5hbGwoW3BDYXJhLHBUeHRdKS50aGVuKGZ1bmN0aW9uKHIpewogICAgdmFyIGNhcmE9clswXSwgdGV4dG89clsxXXx8Jyc7CiAgICBpZih0ZXh0by5pbmRleE9mKCdPQ1JfRVJSOicpPT09MCl7IGJ1c3koZmFsc2UpOyBtc2coJ3N0RicsJ05vIHB1ZGUgbGVlciBlbCBkb2N1bWVudG8gKCcrdGV4dG8uc2xpY2UoOCkrJykuIFRvY2EgQ0FQVFVSQVIgZGUgbnVldm8sIGNvbiBidWVuYSBsdXogeSBzaW4gYnJpbGxvLicsJyNjMDAnKTsgcmV0dXJuOyB9CiAgICBpZih0ZXh0by5yZXBsYWNlKC9ccy9nLCcnKS5sZW5ndGg8MTUpeyBidXN5KGZhbHNlKTsgbXNnKCdzdEYnLCdObyBsZcOtIHN1ZmljaWVudGUgdGV4dG8uIEFjw6lyY2F0ZSwgYnVlbmEgbHV6LCBxdWUgZWwgZG9jdW1lbnRvIGxsZW5lIGVsIG1hcmNvIHkgdG9jYSBDQVBUVVJBUi4nLCcjYzAwJyk7IHJldHVybjsgfQogICAgdmFyIGxhZG89ZGV0ZWN0YXJMYWRvKHRleHRvLCEhKGNhcmEmJmNhcmEuZGV0ZWN0aW9uKSk7CiAgICBpZihsYWRvPT09J3JldmVyc28nKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RGJywnRXNvIGVzIGVsIFJFVkVSU08gKHNlIHZlbiBkaXJlY2Npb25lcyBvIGxhIHpvbmEgTVJaKS4gTmVjZXNpdG8gZWwgRlJFTlRFOiBkb25kZSBlc3TDoSB0dSBGT1RPIHkgdHVzIGRhdG9zLiBWdWVsdmUgYSBjYXB0dXJhci4nLCcjYzAwJyk7CiAgICAgIHJldHVybjsKICAgIH0KICAgIGlmKGxhZG8hPT0nZnJlbnRlJyAmJiAhKGNhcmEmJmNhcmEuZGV0ZWN0aW9uKSl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBtc2coJ3N0RicsJ05vIHB1ZGUgY29uZmlybWFyIHF1ZSBzZWEgZWwgRlJFTlRFLiBBc2Vnw7pyYXRlIGRlIHF1ZSBzZSB2ZWEgdHUgZm90byB5IHR1cyBkYXRvcywgc2luIGJyaWxsbywgeSB2dWVsdmUgYSBjYXB0dXJhci4nLCcjYzAwJyk7CiAgICAgIHJldHVybjsKICAgIH0KICAgIHZhciBuYz1ub21icmVDb2luY2lkZShFU1QuZXNjcml0byx0ZXh0byxtcnpMaW5lYXModGV4dG8pLmxlbmd0aD4wKTsKICAgIGlmKG5jLmhheSAmJiAhbmMub2spewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbm9tYnJlTm9Db2luY2lkZU1zZygnTG8gcXVlIGVzY3JpYmlzdGUgbm8gY29pbmNpZGUgY29uIGVsIGRvY3VtZW50byAobGXDrTogJytuYy5sZWlkbysnKS4gQ29ycmlnZSB0dSBub21icmUgZW4gZWwgcGFzbyAxOiBwdWVkZSB0ZW5lciAxIG8gMiBub21icmVzIHkgMSBvIDIgYXBlbGxpZG9zLicpOwogICAgICByZXR1cm47CiAgICB9CiAgICBFU1QuZnJlbnRlT2s9dHJ1ZTsKICAgIEVTVC5mcmVudGVUZXh0bz10ZXh0bzsKICAgIG1zZygnc3RGJywn4pyTIEZyZW50ZSBsZcOtZG8gY29ycmVjdGFtZW50ZS4nKyhuYy5vaz8oJyBOb21icmU6ICcrbmMubGVpZG8rJy4nKTonJyksJyMwODAnKTsKICAgIGJ1c3koZmFsc2UpOwogICAgYXZhbnphcihFU1QubmVjZXNpdGFSZXZlcnNvPzM6NCk7CiAgfSk7Cn0KZnVuY3Rpb24gbm9tYnJlTm9Db2luY2lkZU1zZyh0eHQpewogIHJlc2V0ZWFyRG9jdW1lbnRvKCk7CiAgdmFyIG5uPSQoJ25vbWJyZU5vQ29pbmNpZGUnKTsKICBpZihubil7IG5uLnRleHRDb250ZW50PXR4dDsgbm4uc3R5bGUuZGlzcGxheT0nYmxvY2snOyBubi5zdHlsZS5jb2xvcj0nI2MwMCc7IH0KICBtc2coJ3N0QScsJycpOyBtc2coJ3N0RicsJycpOwogIG1zZygnenlFcnJOb21icmUnLHR4dCwnI2MwMCcpOwogIGF2YW56YXIoMSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IHBhc28gMzogcmV2ZXJzbyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiByZXZlcnNvQWNlcHRhYmxlKHRleHRvKXsKICB2YXIgdD0odGV4dG98fCcnKS50b1VwcGVyQ2FzZSgpOwogIGlmKCh0Lm1hdGNoKC88L2cpfHxbXSkubGVuZ3RoPj02KXsgcmV0dXJuIHRydWU7IH0KICBpZigvUERGNEk/Ny8udGVzdCh0LnJlcGxhY2UoL1xzL2csJycpKSl7IHJldHVybiB0cnVlOyB9CiAgdmFyIGZ1ZXJ0ZXM9WydET01JQ0lMSU8nLCdESVJFQ0NJT04nLCdESVJFQ0NJw5NOJywnQ09MT05JQScsJ0JBUlJJTycsJ1JFU0lERU5DSUEnLCdDQVNFUklPJywnQ0FOVE9OJywnQUxERUEnLCdPQlNFUlZBQ0lPTicsJ09CU0VSVkFDScOTTicsJ0VTVEFETyBDSVZJTCcsJ0RPTkFOVEUnLCdHUlVQTyBTQU5HJywnVElQTyBERSBTQU5HJywnRU5ET1JTRU1FTlQnLCdSRVNUUklDVElPTicsJ0FERFJFU1MnXTsKICB2YXIgaSxjPTA7CiAgZm9yKGk9MDtpPGZ1ZXJ0ZXMubGVuZ3RoO2krKyl7IGlmKHQuaW5kZXhPZihmdWVydGVzW2ldKT49MCl7IGMrKzsgfSB9CiAgaWYoYz49Mil7IHJldHVybiB0cnVlOyB9CiAgaWYoRVNULnRpcG89PT0ndXNhJyAmJiAvXGIoSVNTfEVYUHxERHw0RHw0RnxSRVNUfEVORHxETClcYi8udGVzdCh0KSl7IHJldHVybiB0cnVlOyB9CiAgcmV0dXJuIGZhbHNlOwp9CmZ1bmN0aW9uIHByb2Nlc2FyUmV2ZXJzbyhkYXRhVXJsKXsKICBidXN5KHRydWUpOwogIG1zZygnc3RBJywnTGV5ZW5kbyBlbCByZXZlcnNvLi4uJywnJyk7CiAgRVNULnJldmVyc29JbWc9ZGF0YVVybDsKICBzaG93SW1nKCdwQScsZGF0YVVybCk7CiAgaGFjZXJPY3IoZGF0YVVybCkudGhlbihmdW5jdGlvbih0ZXh0byl7CiAgICBpZih0ZXh0by5yZXBsYWNlKC9ccy9nLCcnKS5sZW5ndGg8MTAgJiYgIXJldmVyc29BY2VwdGFibGUodGV4dG8pKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RBJywnTm8gbGXDrSBzdWZpY2llbnRlIHRleHRvIGVuIGVsIHJldmVyc28uIEFjw6lyY2F0ZSwgYnVlbmEgbHV6LCB5IHZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgdmFyIGNhcmFQZW5kPW51bGw7CiAgICB2YXIgbGFkbz1kZXRlY3RhckxhZG8odGV4dG8sZmFsc2UpOwogICAgaWYobGFkbz09PSdmcmVudGUnKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RBJywnRXNvIGVzIGVsIEZSRU5URSAoc2UgdmUgbGEgZm90byB5IGxvcyBkYXRvcykuIE5lY2VzaXRvIGVsIFJFVkVSU086IGRpcmVjY2lvbmVzIG8gbGEgem9uYSBNUlouIFZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgaWYobGFkbyE9PSdyZXZlcnNvJyAmJiAhcmV2ZXJzb0FjZXB0YWJsZSh0ZXh0bykpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbXNnKCdzdEEnLCdObyBwdWRlIGNvbmZpcm1hciBxdWUgc2VhIGVsIFJFVkVSU08uIE11ZXN0cmEgbGFzIGRpcmVjY2lvbmVzIG8gbGEgem9uYSBkZSByYXlpdGFzL01SWiB5IHZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgdmFyIG5jPW5vbWJyZUNvaW5jaWRlKEVTVC5lc2NyaXRvLHRleHRvLG1yekxpbmVhcyh0ZXh0bykubGVuZ3RoPjApOwogICAgaWYobmMuaGF5ICYmICFuYy5vayl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBub21icmVOb0NvaW5jaWRlTXNnKCdFbCBub21icmUgZGVsIGRvY3VtZW50byAoJytuYy5sZWlkbysnKSBubyBjb2luY2lkZSBjb24gbG8gcXVlIGVzY3JpYmlzdGUuIENvcnJpZ2UgdHUgbm9tYnJlIGVuIGVsIHBhc28gMTogcHVlZGUgdGVuZXIgMSBvIDIgbm9tYnJlcyB5IDEgbyAyIGFwZWxsaWRvcy4nKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgRVNULnJldmVyc29Paz10cnVlOwogICAgRVNULnJldmVyc29UZXh0bz10ZXh0bzsKICAgIG1zZygnc3RBJywn4pyTIFJldmVyc28gbGXDrWRvIGNvcnJlY3RhbWVudGUuJywnIzA4MCcpOwogICAgYnVzeShmYWxzZSk7CiAgICBhdmFuemFyKDQpOwogIH0pLmNhdGNoKGZ1bmN0aW9uKGUpewogICAgYnVzeShmYWxzZSk7CiAgICBtc2coJ3N0QScsJ0Vycm9yIGxleWVuZG8gZWwgcmV2ZXJzbzogJysoZSYmZS5tZXNzYWdlP2UubWVzc2FnZTonJykrJy4gVnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogIH0pOwp9CgovKiA9PT09PT09PT09PT09PT09PSBwYXNvIDQ6IHNlbGZpZSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBwcm9jZXNhclNlbGZpZSgpewogIHZhciBpbWc9Y2FwdHVyYXJWaWRlbygnNCcsMTA0OCk7CiAgaWYoIWltZyl7IG1zZygnc3RWJywnUHJpbWVybyBhYnJlIGxhIGPDoW1hcmEgeSBwb24gdHUgY2FyYSBkZW50cm8gZGVsIG1hcmNvLicsJyNjMDAnKTsgcmV0dXJuOyB9CiAgRVNULnNlbGZpZUltZz1pbWc7CiAgc2hvd0ltZygncFMnLGltZyk7CiAgYnVzeSh0cnVlKTsKICBtc2coJ3N0VicsJ0NvbXBhcmFuZG8gdHUgY2FyYSBjb24gbGEgZGVsIGRvY3VtZW50by4uLicsJycpOwogIHZhciBwRG9jPWNvblRpbWVvdXQoZGV0ZWN0YXJDYXJhRW4oRVNULmZyZW50ZUltZ3x8RVNULnJldmVyc29JbWd8fCcnKSwxNTAwMCk7CiAgdmFyIHBTZWw9Y29uVGltZW91dChkZXRlY3RhckNhcmFFbihpbWcpLDE1MDAwKTsKICBQcm9taXNlLmFsbChbcERvYyxwU2VsXSkudGhlbihmdW5jdGlvbihyKXsKICAgIHZhciBlbkRvYz1yWzBdLCBlblNlbD1yWzFdOwogICAgaWYoIWVuRG9jIHx8ICFlbkRvYy5kZXRlY3Rpb24pewogICAgICBidXN5KGZhbHNlKTsKICAgICAgZmFsbG9TZWxmaWUoJ05vIHB1ZGUgdmVyIGJpZW4gbGEgY2FyYSBlbiBsYSBmb3RvIGRlbCBkb2N1bWVudG8uIFZhbW9zIGEgcmVwZXRpciBsYSBmb3RvIGRlbCBkb2N1bWVudG8gY29uIG1lam9yIGx1ei4nKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgaWYoIWVuU2VsIHx8ICFlblNlbC5kZXRlY3Rpb24pewogICAgICBidXN5KGZhbHNlKTsKICAgICAgZmFsbG9TZWxmaWUoJ05vIHB1ZGUgdmVyIHR1IGNhcmEgZW4gbGEgc2VsZmllLiBNZWpvciBsYSBsdXosIHF1w610YXRlIGdvcnJhIG8gbGVudGVzIG9zY3Vyb3MuJyk7CiAgICAgIHJldHVybjsKICAgIH0KICAgIHZhciBkPWRpc3RGKGVuRG9jLmRlc2NyaXB0b3IsZW5TZWwuZGVzY3JpcHRvcik7CiAgICBpZihkPD0wLjYwKXsKICAgICAgRVNULnNlbGZpZU9rPXRydWU7CiAgICAgIEVTVC5pbnRlbnRvcz0zOwogICAgICBtc2coJ3N0VicsJ+KckyBWZXJpZmljYWNpw7NuIGZhY2lhbCBzdXBlcmFkYS4gUGFzYW5kbyBhIHR1IGNsYXZlLicsJyMwODAnKTsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIGF2YW56YXIoNSk7CiAgICB9ZWxzZXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIGZhbGxvU2VsZmllKCdUdSBjYXJhIG5vIGNvaW5jaWRlIGNvbiBsYSBkZWwgZG9jdW1lbnRvIChkaXN0YW5jaWEgJytkLnRvRml4ZWQoMikrJykuJyk7CiAgICB9CiAgfSkuY2F0Y2goZnVuY3Rpb24oZSl7CiAgICBidXN5KGZhbHNlKTsKICAgIGZhbGxvU2VsZmllKCdFbCB2ZXJpZmljYWRvciBmYWNpYWwgbm8gY2FyZ8OzOiAnKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOicnKSsnLiBSZXZpc2EgdHUgaW50ZXJuZXQgeSByZWludGVudGEuJyk7CiAgfSk7Cn0KZnVuY3Rpb24gZmFsbG9TZWxmaWUobSl7CiAgRVNULmludGVudG9zLS07CiAgaWYoRVNULmludGVudG9zPD0wKXsKICAgIEVTVC5pbnRlbnRvcz0zOwogICAgRVNULnNlbGZpZU9rPWZhbHNlOwogICAgbXNnKCdzdFYnLCdTZSBhZ290YXJvbiBsb3MgMyBpbnRlbnRvcy4gVm9sdmVtb3MgYSBsYSBmb3RvIGRlbCBkb2N1bWVudG87IHJldsOtc2FsYSB5IHZ1ZWx2ZSBhIHRvbWFybGEsIHkgc2VndWltb3MgZW4gb3JkZW4gcG9yIGxvcyBwYXNvcy4nLCcjYTYwJyk7CiAgICBhdmFuemFyKDIpOwogIH1lbHNlewogICAgbXNnKCdzdFYnLCfinJcgJyttKycgVGUgcXVlZGFuICcrRVNULmludGVudG9zKycgaW50ZW50byhzKS4gVG9jYSBDQVBUVVJBUiBkZSBudWV2by4nLCcjYzAwJyk7CiAgfQp9CgovKiA9PT09PT09PT09PT09PT09PSBwYXNvIDU6IGNsYXZlICsgWklEID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHZhbGlkYXJDbGF2ZXMoKXsKICB2YXIgYT0kKCdjbGF2ZScpLCBiPSQoJ2NsYXZlMicpLCBkPSQoJ2Rlc2dsb3NlJyk7CiAgaWYoIWF8fCFiKXsgcmV0dXJuOyB9CiAgaWYoIWIudmFsdWUpeyBpZihkKXsgZC50ZXh0Q29udGVudD0nJzsgfSByZXR1cm47IH0KICBpZihhLnZhbHVlPT09Yi52YWx1ZSl7CiAgICBpZihkKXsgZC50ZXh0Q29udGVudD0n4pyTIExhcyBjbGF2ZXMgY29pbmNpZGVuLiBUb2NhIGVsIGJvdMOzbiBwYXJhIGNyZWFyIHR1IFpJRC4nOyBkLnN0eWxlLmNvbG9yPScjMDgwJzsgfQogICAgaGFiaWxpdGFyU3VibWl0KCk7CiAgfWVsc2V7CiAgICBpZihkKXsgZC50ZXh0Q29udGVudD0n4pyXIExhcyBjbGF2ZXMgbm8gY29pbmNpZGVuLiBDb3Jyw61nZWxhcyBhcXXDrSwgbm8gc2FsZXMgZGVsIHBhc28gNSBoYXN0YSBxdWUgY29pbmNpZGFuLic7IGQuc3R5bGUuY29sb3I9JyNjMDAnOyB9CiAgfQp9CmZ1bmN0aW9uIGhhYmlsaXRhclN1Ym1pdCgpewogIHZhciBwcz0kKCdwczUnKTsKICBpZighcHMpeyByZXR1cm47IH0KICB2YXIgYnRucz1wcy5xdWVyeVNlbGVjdG9yQWxsKCdidXR0b24sIGlucHV0W3R5cGU9YnV0dG9uXSwgaW5wdXRbdHlwZT1zdWJtaXRdLCBbcm9sZT1idXR0b25dJyksIGksIGhheT1mYWxzZTsKICBmb3IoaT0wO2k8YnRucy5sZW5ndGg7aSsrKXsKICAgIHZhciB0PSgoYnRuc1tpXS50ZXh0Q29udGVudHx8JycpKycgJysoYnRuc1tpXS52YWx1ZXx8JycpKS50b1VwcGVyQ2FzZSgpOwogICAgaWYoL0NSRUFSfFJFR0lTVFJ8RklOQUxJWkFSfENPTlRJTlVBUnxFTlZJQVJ8QUNFUFRBUnxaSUQvLnRlc3QodCkpeyBidG5zW2ldLmRpc2FibGVkPWZhbHNlOyBoYXk9dHJ1ZTsgfQogIH0KICBpZighaGF5KXsgbXNnKCd6eUNsYXZlT2snLCdTaSBubyB2ZXMgZWwgYm90w7NuIHBhcmEgY3JlYXIgdHUgWklELCBhdsOtc2FtZS4nLCcjYTYwJyk7IH0KfQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyA1OiBmaWx0cm8gZmluYWwgYW50ZXMgZGVsIGVudmlvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGNsYXZlc0xpc3RhcygpewogIHZhciBhPSQoJ2NsYXZlJyksIGI9JCgnY2xhdmUyJyk7CiAgcmV0dXJuICEhKGEmJmImJmEudmFsdWUmJmEudmFsdWU9PT1iLnZhbHVlJiZTdHJpbmcoYS52YWx1ZSkubGVuZ3RoPj04KTsKfQpmdW5jdGlvbiBmb3Rvc0NvbXBsZXRhcygpewogIHJldHVybiAhIShFU1QuZnJlbnRlSW1nJiZFU1Quc2VsZmllSW1nJiYoIUVTVC5uZWNlc2l0YVJldmVyc298fEVTVC5yZXZlcnNvSW1nKSk7Cn0KZnVuY3Rpb24gcmVsbGVuYXJGb3Rvc0Zvcm11bGFyaW8oKXsKICB2YXIgcHM1PSQoJ3BzNScpOwogIHZhciBmPXBzNT8ocHM1LnF1ZXJ5U2VsZWN0b3IoJ2Zvcm0nKXx8bnVsbCk6bnVsbDsKICBpZighZil7IHRyeXsgZj1kb2N1bWVudC5xdWVyeVNlbGVjdG9yKCdmb3JtJyk7IH1jYXRjaChlKXsgZj1udWxsOyB9IH0KICBpZighZnx8IWYuZWxlbWVudHMpeyByZXR1cm47IH0KICB2YXIgZWxzPWYuZWxlbWVudHMsIGk7CiAgZm9yKGk9MDtpPGVscy5sZW5ndGg7aSsrKXsKICAgIHZhciBlbD1lbHNbaV07CiAgICBpZighZWwpeyBjb250aW51ZTsgfQogICAgdmFyIHRhZz1lbC50YWdOYW1lfHwnJzsKICAgIGlmKHRhZyE9PSdJTlBVVCcmJnRhZyE9PSdURVhUQVJFQScpeyBjb250aW51ZTsgfQogICAgdmFyIHQ9KChlbC50eXBlfHwnJykrJycpLnRvTG93ZXJDYXNlKCk7CiAgICBpZih0YWc9PT0nSU5QVVQnJiZ0IT09J2hpZGRlbicmJnQhPT0ndGV4dCcpeyBjb250aW51ZTsgfQogICAgaWYoKGVsLnZhbHVlfHwnJykubGVuZ3RoPjEwKXsgY29udGludWU7IH0KICAgIHZhciBub209KCgoZWwubmFtZXx8JycpKycnKSsnICcrKChlbC5pZHx8JycpKycnKSkudG9Mb3dlckNhc2UoKTsKICAgIGlmKC9mcmVudGV8ZnJvbnRhbHxhbnZlcnNvfGZvdG9mfGRvYzF8Zm90bzEvLnRlc3Qobm9tKSl7IGlmKEVTVC5mcmVudGVJbWcpeyBlbC52YWx1ZT1FU1QuZnJlbnRlSW1nOyB9IH0KICAgIGVsc2UgaWYoL3JldmVyc298ZG9yc298dHJhc2VyYXxmb3RvcmV2fGRvYzJ8Zm90bzIvLnRlc3Qobm9tKSl7IGlmKEVTVC5yZXZlcnNvSW1nKXsgZWwudmFsdWU9RVNULnJldmVyc29JbWc7IH0gfQogICAgZWxzZSBpZigvc2VsZmllfHJvc3Ryb3xmYWNpYWx8Y2FyYXxmYWNlfGZvdG8zfGZvdG9zLy50ZXN0KG5vbSkpeyBpZihFU1Quc2VsZmllSW1nKXsgZWwudmFsdWU9RVNULnNlbGZpZUltZzsgfSB9CiAgfQp9CmZ1bmN0aW9uIGd1YXJkaWFFbnZpbyhldil7CiAgZnVuY3Rpb24gYmxvcXVlYXIoKXsKICAgIGlmKGV2KXsgdHJ5eyBpZihldi5wcmV2ZW50RGVmYXVsdCl7IGV2LnByZXZlbnREZWZhdWx0KCk7IH0gaWYoZXYuc3RvcFByb3BhZ2F0aW9uKXsgZXYuc3RvcFByb3BhZ2F0aW9uKCk7IH0gaWYoZXYuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKXsgZXYuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKCk7IH0gfWNhdGNoKGUpe30gfQogICAgcmV0dXJuIGZhbHNlOwogIH0KICBpZighY2xhdmVzTGlzdGFzKCkpewogICAgbXNnKCd6eUNsYXZlT2snLCdBbnRlcyBkZSBjcmVhciB0dSBaSUQ6IGVzY3JpYmUgbGEgY2xhdmUgeSByZXBpdGVsYSAobWluIDgsIGlndWFsZXMpLicsJyNjMDAnKTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICBpZighRVNULmZyZW50ZUltZyl7CiAgICBtc2coJ3N0RicsJ0ZhbHRhIGxhIGZvdG8gZGVsIEZSRU5URSBkZWwgZG9jdW1lbnRvLiBUZSBsbGV2byBhbCBwYXNvIDIgcGFyYSB0b21hcmxhIChsYXMgZGVtYXMgZm90b3Mgc2UgY29uc2VydmFuKS4nLCcjYzAwJyk7CiAgICBhdmFuemFyKDIpOwogICAgcmV0dXJuIGJsb3F1ZWFyKCk7CiAgfQogIGlmKEVTVC5uZWNlc2l0YVJldmVyc28mJiFFU1QucmV2ZXJzb0ltZyl7CiAgICBtc2coJ3N0QScsJ0ZhbHRhIGxhIGZvdG8gZGVsIFJFVkVSU08gZGVsIGRvY3VtZW50by4gVGUgbGxldm8gYWwgcGFzbyAzIHBhcmEgdG9tYXJsYS4nLCcjYzAwJyk7CiAgICBhdmFuemFyKDMpOwogICAgcmV0dXJuIGJsb3F1ZWFyKCk7CiAgfQogIGlmKCFFU1Quc2VsZmllSW1nKXsKICAgIG1zZygnc3RWJywnRmFsdGEgbGEgc2VsZmllIHZlcmlmaWNhZGEuIFRlIGxsZXZvIGFsIHBhc28gNCBwYXJhIHRvbWFybGEuJywnI2MwMCcpOwogICAgYXZhbnphcig0KTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICByZWxsZW5hckZvdG9zRm9ybXVsYXJpbygpOwogIHJldHVybiB0cnVlOwp9CmZ1bmN0aW9uIGVuZ2FuY2hhckVudmlvRmluYWwoKXsKICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdzdWJtaXQnLGZ1bmN0aW9uKGV2KXsKICAgIHRyeXsKICAgICAgdmFyIHBzNT0kKCdwczUnKSwgZj1ldi50YXJnZXQ7CiAgICAgIGlmKHBzNSYmZiYmcHM1LmNvbnRhaW5zKGYpKXsgZ3VhcmRpYUVudmlvKGV2KTsgfQogICAgfWNhdGNoKGUpe30KICB9LHRydWUpOwogIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbihldil7CiAgICB0cnl7CiAgICAgIHZhciBwczU9JCgncHM1JyksIGVsPWV2LnRhcmdldDsKICAgICAgaWYoIXBzNXx8IWVsfHwhcHM1LmNvbnRhaW5zKGVsKSl7IHJldHVybjsgfQogICAgICB2YXIgYj1lbCwgZXNCb3Rvbj1mYWxzZSwgcHJvZj0wOwogICAgICB3aGlsZShiJiZiIT09cHM1JiZwcm9mPDYpewogICAgICAgIHZhciB0Zz1iLnRhZ05hbWV8fCcnOwogICAgICAgIGlmKHRnPT09J0JVVFRPTid8fCh0Zz09PSdJTlBVVCcmJigoYi50eXBlfHwnJyk9PT0nc3VibWl0J3x8KGIudHlwZXx8JycpPT09J2J1dHRvbicpKXx8KGIuZ2V0QXR0cmlidXRlJiZiLmdldEF0dHJpYnV0ZSgncm9sZScpPT09J2J1dHRvbicpKXsgZXNCb3Rvbj10cnVlOyBicmVhazsgfQogICAgICAgIGI9Yi5wYXJlbnROb2RlOyBwcm9mKys7CiAgICAgIH0KICAgICAgaWYoIWVzQm90b24peyByZXR1cm47IH0KICAgICAgaWYoIWNsYXZlc0xpc3RhcygpfHwhZm90b3NDb21wbGV0YXMoKSl7IGd1YXJkaWFFbnZpbyhldik7IH0KICAgICAgZWxzZXsgcmVsbGVuYXJGb3Rvc0Zvcm11bGFyaW8oKTsgfQogICAgfWNhdGNoKGUpe30KICB9LHRydWUpOwp9CgovKiA9PT09PT09PT09PT09PT09PSBpbnRlcnJ1cHRvciBkZSBib3RvbmVzID09PT09PT09PT09PT09PT09ICovCnZhciBNSU89eydiQWJyaXJGJzoxLCdiQ2FwRic6MSwnYkFicmlyQSc6MSwnYkNhcEEnOjEsJ2JBYnJpckNhbSc6MSwnYlNlbGZpZSc6MSwnYlJlcFNlbGZpZSc6MSwnYklyNCc6MSwnYklyNSc6MX07CmZ1bmN0aW9uIG1hbmVqYXIoaWQpewogIHN3aXRjaChpZCl7CiAgICBjYXNlICdiQWJyaXJGJzogYWJyaXJDYW0oJzInLCdlbnZpcm9ubWVudCcsJ3N0RicsJ2JDYXBGJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgYnJlYWs7CiAgICBjYXNlICdiQ2FwRic6IHsgdmFyIGY9Y2FwdHVyYXJWaWRlbygnMicsMTAyNCk7IGlmKCFmKXsgbXNnKCdzdEYnLCdBYnJlIGxhIGPDoW1hcmEgcHJpbWVybyAoYm90w7NuIGFicmlyIGPDoW1hcmEpLicsJyNjMDAnKTsgfSBlbHNlIHsgcHJvY2VzYXJGcmVudGUoZik7IH0gYnJlYWs7IH0KICAgIGNhc2UgJ2JBYnJpckEnOiBhYnJpckNhbSgnMycsJ2Vudmlyb25tZW50Jywnc3RBJywnYkNhcEEnKS5jYXRjaChmdW5jdGlvbigpe30pOyBicmVhazsKICAgIGNhc2UgJ2JDYXBBJzogeyB2YXIgYT1jYXB0dXJhclZpZGVvKCczJywxMDI0KTsgaWYoIWEpeyBtc2coJ3N0QScsJ0FicmUgbGEgY8OhbWFyYSBwcmltZXJvIChib3TDs24gYWJyaXIgY8OhbWFyYSkuJywnI2MwMCcpOyB9IGVsc2UgeyBwcm9jZXNhclJldmVyc28oYSk7IH0gYnJlYWs7IH0KICAgIGNhc2UgJ2dhbEYnOiBjbGlja0FyY2hpdm8oJzInKTsgYnJlYWs7CiAgICBjYXNlICdnYWxBJzogY2xpY2tBcmNoaXZvKCczJyk7IGJyZWFrOwogICAgY2FzZSAnYkFicmlyQ2FtJzogYWJyaXJDYW0oJzQnLCd1c2VyJywnc3RWJywnYlNlbGZpZScpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IGJyZWFrOwogICAgY2FzZSAnYlNlbGZpZSc6IHsKICAgICAgdmFyIGN2PUVTVC5jYXJhVml2YSwgdDBzPSh6eURldCgpWyc0J10mJnp5RGV0KClbJzQnXS50MCl8fERhdGUubm93KCk7CiAgICAgIHZhciBsaXN0bz1jdiYmY3Yub2smJigoRGF0ZS5ub3coKS0oY3YudHx8MCkpPDI1MDApOwogICAgICB2YXIgZGV0ZWN0b3JWaWVqbz0oRGF0ZS5ub3coKS10MHMpPjE1MDAwOwogICAgICBpZighbGlzdG8mJiFkZXRlY3RvclZpZWpvKXsKICAgICAgICBtc2coJ3N0VicsIChjdiYmY3YudmlzdGEpPydDZW50cmEgdHUgY2FyYSBkZW50cm8gZGVsIE9WQUxPIChkZWJlIHBvbmVyc2UgVkVSREUpIHkgbHVlZ28gdG9jYSBDQVBUVVJBUi4nOidQcmVwYXJhbmRvIGVsIGRldGVjdG9yIGZhY2lhbC4uLiBlc3BlcmEgdW5vcyBzZWd1bmRvcy4nLCcjYTYwJyk7CiAgICAgICAgYnJlYWs7CiAgICAgIH0KICAgICAgcHJvY2VzYXJTZWxmaWUoKTsKICAgICAgYnJlYWs7CiAgICB9CiAgICBjYXNlICdiUmVwU2VsZmllJzogYWJyaXJDYW0oJzQnLCd1c2VyJywnc3RWJywnYlNlbGZpZScpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IGJyZWFrOwogICAgY2FzZSAnYklyNCc6CiAgICAgIGlmKHBlcm1pdGlkb0hhc3RhKCk+PTQpeyBhdmFuemFyKDQpOyB9CiAgICAgIGVsc2V7IG1zZygnc3RBJywnQcO6biBubyBwdWVkZXMgcGFzYXI6IHByaW1lcm8gY29tcGxldGEgZWwgZG9jdW1lbnRvIChmcmVudGUnKyhFU1QubmVjZXNpdGFSZXZlcnNvPycgeSByZXZlcnNvJzonJykrJykuJywnI2MwMCcpOyB9CiAgICAgIGJyZWFrOwogICAgY2FzZSAnYklyNSc6CiAgICAgIGlmKHBlcm1pdGlkb0hhc3RhKCk+PTUpeyBhdmFuemFyKDUpOyB9CiAgICAgIGVsc2V7IG1zZygnc3RWJywnQcO6biBubyBwdWVkZXMgcGFzYXI6IHByaW1lcm8gcGFzYSBsYSB2ZXJpZmljYWNpw7NuIGZhY2lhbC4nLCcjYzAwJyk7IH0KICAgICAgYnJlYWs7CiAgfQp9CmRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbihlKXsKICB2YXIgZWw9ZS50YXJnZXQ7CiAgd2hpbGUoZWwgJiYgZWwhPT1kb2N1bWVudCAmJiAhKGVsLmlkICYmIE1JT1tlbC5pZF0pKXsgZWw9ZWwucGFyZW50Tm9kZTsgfQogIGlmKCFlbCB8fCBlbD09PWRvY3VtZW50KXsgcmV0dXJuOyB9CiAgaWYoZS5wcmV2ZW50RGVmYXVsdCl7IGUucHJldmVudERlZmF1bHQoKTsgfQogIGlmKGUuc3RvcFByb3BhZ2F0aW9uKXsgZS5zdG9wUHJvcGFnYXRpb24oKTsgfQogIGlmKGUuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKXsgZS5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24oKTsgfQogIHRyeXsgbWFuZWphcihlbC5pZCxlKTsgfWNhdGNoKGVycil7IGxvZygnZXJyb3IgZW4nLGVsLmlkLGVycik7IH0KfSx0cnVlKTsKCi8qID09PT09PT09PT09PT09PT09IGdhbGVyaWEgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gY2xpY2tBcmNoaXZvKHBzSWQpewogIHZhciBjb250PSQoJ3BzJytwc0lkKTsKICB2YXIgaW5wPWNvbnQ/Y29udC5xdWVyeVNlbGVjdG9yKCdpbnB1dFt0eXBlPWZpbGVdJyk6bnVsbDsKICBpZihpbnApeyBpbnAuY2xpY2soKTsgfQogIGVsc2V7IG1zZyhwc0lkPT09JzInPydzdEYnOidzdEEnLCdObyBlbmNvbnRyw6kgZWwgc2VsZWN0b3IgZGUgYXJjaGl2b3MuJywnI2MwMCcpOyB9Cn0KZnVuY3Rpb24gZW5nYW5jaGFyR2FsZXJpYShpZCxwc0lkKXsKICB2YXIgZWw9JChpZCk7CiAgaWYoIWVsKXsgcmV0dXJuOyB9CiAgaWYoZWwudGFnTmFtZT09PSdJTlBVVCcgJiYgKGVsLnR5cGV8fCcnKS50b0xvd2VyQ2FzZSgpPT09J2ZpbGUnKXsKICAgIGVsLmFkZEV2ZW50TGlzdGVuZXIoJ2NoYW5nZScsZnVuY3Rpb24oKXsKICAgICAgdmFyIGY9ZWwuZmlsZXMmJmVsLmZpbGVzWzBdOwogICAgICBpZighZil7IHJldHVybjsgfQogICAgICBhcmNoaXZvQURhdG9zKGYpLnRoZW4oZnVuY3Rpb24oZCl7IHJldHVybiBkb3duc2NhbGUoZCwxMDI0KTsgfSkudGhlbihmdW5jdGlvbihkKXsKICAgICAgICBpZihwc0lkPT09JzInKXsgcHJvY2VzYXJGcmVudGUoZCk7IH0gZWxzZSB7IHByb2Nlc2FyUmV2ZXJzbyhkKTsgfQogICAgICB9KS5jYXRjaChmdW5jdGlvbihlcil7IG1zZyhwc0lkPT09JzInPydzdEYnOidzdEEnLCdObyBwdWRlIGxlZXIgbGEgaW1hZ2VuOiAnKyhlciYmZXIubWVzc2FnZT9lci5tZXNzYWdlOicnKSwnI2MwMCcpOyB9KTsKICAgIH0pOwogIH1lbHNlewogICAgTUlPW2lkXT0xOwogIH0KfQoKLyogPT09PT09PT09PT09PT09PT0gZXZlbnRvcyBkZSBwYXNvcyAxIHkgNSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBlbmdhbmNoYXJQYXNvMSgpewogIHZhciBpbnA9JCgnbm9tYnJlJyksIHNlbD0kKCd0aXBvRG9jJyk7CiAgaWYoaW5wKXsKICAgIGlucC5hZGRFdmVudExpc3RlbmVyKCdpbnB1dCcsZnVuY3Rpb24oKXsKICAgICAgdmFyIGFudGVzT2s9RVNULm5vbWJyZU9rOwogICAgICB2YWxpZGFyUGFzbzEodHJ1ZSk7CiAgICAgIGlmKCFFU1Qubm9tYnJlT2sgJiYgYW50ZXNPayAmJiBFU1QucGFzbz4xKXsKICAgICAgICByZXNldGVhckRvY3VtZW50bygpOwogICAgICAgIG1zZygnenlFcnJOb21icmUnLCdFbCBub21icmUgY2FtYmnDsyB5IHlhIG5vIGVzIHbDoWxpZG8uIENvcnLDrWdlbG8geSB0b2NhIENvbnRpbnVhci4nLCcjYzAwJyk7CiAgICAgICAgYXZhbnphcigxKTsKICAgICAgICByZXR1cm47CiAgICAgIH0KICAgICAgbGltcGlhckVycm9yZXNQYXNvMSgpOwogICAgfSk7CiAgfQogIGlmKHNlbCl7CiAgICBzZWwuYWRkRXZlbnRMaXN0ZW5lcignY2hhbmdlJyxmdW5jdGlvbigpewogICAgICB2YWxpZGFyUGFzbzEodHJ1ZSk7CiAgICAgIHJlc2V0ZWFyRG9jdW1lbnRvKCk7CiAgICAgIGxpbXBpYXJFcnJvcmVzUGFzbzEoKTsKICAgIH0pOwogIH0KfQpmdW5jdGlvbiBlbmdhbmNoYXJQYXNvNSgpewogIHZhciBhPSQoJ2NsYXZlJyksIGI9JCgnY2xhdmUyJyk7CiAgaWYoYSl7IGEuYWRkRXZlbnRMaXN0ZW5lcignaW5wdXQnLHZhbGlkYXJDbGF2ZXMpOyB9CiAgaWYoYil7IGIuYWRkRXZlbnRMaXN0ZW5lcignaW5wdXQnLHZhbGlkYXJDbGF2ZXMpOyB9Cn0KCi8qID09PT09PT09PT09PT09PT09IGFycmFucXVlID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGluaXQoKXsKICBlbmdhbmNoYXJQYXNvMSgpOwogIGVuZ2FuY2hhclBhc281KCk7CiAgZW5nYW5jaGFyRW52aW9GaW5hbCgpOwogIGVuZ2FuY2hhckdhbGVyaWEoJ2dhbEYnLCcyJyk7CiAgZW5nYW5jaGFyR2FsZXJpYSgnZ2FsQScsJzMnKTsKICBbJ292RicsJ292QScsJ292UyddLmZvckVhY2goZnVuY3Rpb24ob2lkKXsgdmFyIG89JChvaWQpOyBpZihvKXsgby5zdHlsZS5wb2ludGVyRXZlbnRzPSdub25lJzsgfSB9KTsKICB2YWxpZGFyUGFzbzEodHJ1ZSk7CiAgdmVyaWZpY2FyKCk7CiAgc2V0VGltZW91dChmdW5jdGlvbigpeyBjYXJnYXJGYWNlQXBpKCkuY2F0Y2goZnVuY3Rpb24oKXt9KTsgfSwxNTAwKTsKICB0cnl7IGlmKGRvY3VtZW50LnRpdGxlLmluZGV4T2YoJ1JFViBFJyk8MCl7IGRvY3VtZW50LnRpdGxlPWRvY3VtZW50LnRpdGxlKycgwrcgUkVWIEUnOyB9IH1jYXRjaChlKXt9CiAgbG9nKCdudWNsZW8gcmV2RSB2OSBhY3Rpdm8uIEVzdGFkbzonLCBKU09OLnN0cmluZ2lmeShFU1QpKTsKfQp0cnl7CiAgVy5fX1pZUkFfUkVWRV9URVNUX189e3ZhbGlkYXJQYXNvMTp2YWxpZGFyUGFzbzEsdmVyaWZpY2FyOnZlcmlmaWNhcixtb3N0cmFyUGFzbzptb3N0cmFyUGFzbyxwZXJtaXRpZG9IYXN0YTpwZXJtaXRpZG9IYXN0YSxlbmdhbmNoYXJQYXNvMTplbmdhbmNoYXJQYXNvMSxsaW1waWFyRXJyb3Jlc1Bhc28xOmxpbXBpYXJFcnJvcmVzUGFzbzEsZXN0YWRvOmZ1bmN0aW9uKCl7IHJldHVybiBKU09OLnBhcnNlKEpTT04uc3RyaW5naWZ5KEVTVCkpOyB9LG5vcm06bm9ybSxkZXRlY3RhckxhZG86ZGV0ZWN0YXJMYWRvLG5vbWJyZUNvaW5jaWRlOm5vbWJyZUNvaW5jaWRlLHNpbU5vbWJyZXM6c2ltTm9tYnJlcyxtcnpOb21icmVzOm1yek5vbWJyZXN9Owp9Y2F0Y2goZSl7fQppZihkb2N1bWVudC5yZWFkeVN0YXRlPT09J2xvYWRpbmcnKXsKICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdET01Db250ZW50TG9hZGVkJyxpbml0KTsKfWVsc2V7CiAgaW5pdCgpOwp9ClcuX19aWVJBX1JFVkRfSU5GTz1mdW5jdGlvbigpeyByZXR1cm4gSlNPTi5wYXJzZShKU09OLnN0cmluZ2lmeShFU1QpKTsgfTsKfSkoKTsK'))/*ZYRA-V6-END*/</script>
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

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

/*ZYRA-V6-BEGIN*/eval(atob('LypaWVJBLVJFVkYgdjExIC0gbnVjbGVvIGRlIHJlZ2lzdHJvIHJldkYgKGJ1c3F1ZWRhIFJFQUwgZGVsIGRvY3VtZW50byBwb3IgNCBlc3F1aW5hcyBjb24gY29udG9ybm8sIGRpbSB5IGF1dG8tY2FwdHVyYSBjb24gY3VlbnRhIGF0cmFzOyBtb3RvciBmYWNpYWwgRU4gVklWTyBjb24gcG9zZSwgb2pvcywgbHV6LCBuaXRpZGV6LCBwcm9ncmVzbyB5IGN1ZW50YSBhdHJhczsgT0NSIG11bHRpLXBhc2UgY29uIGltYWdlbiBtZWpvcmFkYSB5IGNvbmZpcm1hY2lvbiBlZGl0YWJsZSBkZSBsYSBsZWN0dXJhOyBjb21wYXJhY2lvbiBzZWxmaWUtZG9jdW1lbnRvIDAuNjA7IGNhZGEgcGFzbyBmaWx0cmEgZGUgdmVyZGFkIHkgZWwgZW52aW8gZmluYWwgZXhpZ2UgVE9ETyB2ZXJpZmljYWRvOyBlbCBub21icmUgbWFsIGxlaWRvIHNlIGNvcnJpZ2UgY29uIGd1YXJkYXJyYWlsZXMsIHNpbiByZWluaWNpYXIgbmFkYSkqLwooZnVuY3Rpb24oKXsKJ3VzZSBzdHJpY3QnOwp2YXIgVyA9ICh0eXBlb2Ygd2luZG93IT09J3VuZGVmaW5lZCcpP3dpbmRvdzp0aGlzOwppZiAoVy5fX1pZUkFfUkVWRV9fKSB7IHJldHVybjsgfQpXLl9fWllSQV9SRVZFX18gPSAnRic7CgovKiA9PT09PT09PT09PT09PT09PSB1dGlsaWRhZGVzIGRlIHRleHRvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uICQoaWQpeyB0cnl7IHJldHVybiAodHlwZW9mIGRvY3VtZW50IT09J3VuZGVmaW5lZCcpP2RvY3VtZW50LmdldEVsZW1lbnRCeUlkKGlkKTpudWxsOyB9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9IH0KZnVuY3Rpb24gbG9nKCl7IHRyeXsgdmFyIGE9WydbWllSQS1SRVZFXSddOyBmb3IodmFyIGk9MDtpPGFyZ3VtZW50cy5sZW5ndGg7aSsrKXsgYS5wdXNoKGFyZ3VtZW50c1tpXSk7IH0gY29uc29sZS5sb2cuYXBwbHkoY29uc29sZSxhKTsgfWNhdGNoKGUpe30gfQoKZnVuY3Rpb24gbm9ybShzKXsKICB2YXIgdD0ocz09bnVsbD8nJzpTdHJpbmcocykpLnRvVXBwZXJDYXNlKCk7CiAgdD10LnJlcGxhY2UoL1tcdTAwQzFcdTAwQzBcdTAwQzRcdTAwQzJdL2csJ0EnKS5yZXBsYWNlKC9bXHUwMEM5XHUwMEM4XHUwMENCXHUwMENBXS9nLCdFJykucmVwbGFjZSgvW1x1MDBDRFx1MDBDQ1x1MDBDRlx1MDBDRV0vZywnSScpLnJlcGxhY2UoL1tcdTAwRDNcdTAwRDJcdTAwRDZcdTAwRDRdL2csJ08nKS5yZXBsYWNlKC9bXHUwMERBXHUwMEQ5XHUwMERDXHUwMERCXS9nLCdVJykucmVwbGFjZSgvXHUwMEQxL2csJ04nKTsKICByZXR1cm4gdC5yZXBsYWNlKC9bXkEtWiBdL2csJyAnKS5yZXBsYWNlKC9ccysvZywnICcpLnRyaW0oKTsKfQpmdW5jdGlvbiBsZXYoYSxiKXsKICBhPShhPT1udWxsPycnOlN0cmluZyhhKSk7IGI9KGI9PW51bGw/Jyc6U3RyaW5nKGIpKTsKICB2YXIgbj1hLmxlbmd0aCwgbT1iLmxlbmd0aDsKICBpZighbil7IHJldHVybiBtOyB9IGlmKCFtKXsgcmV0dXJuIG47IH0KICB2YXIgaSxqLHByZXY9bmV3IEFycmF5KG0rMSksY3VyPW5ldyBBcnJheShtKzEpOwogIGZvcihqPTA7ajw9bTtqKyspeyBwcmV2W2pdPWo7IH0KICBmb3IoaT0xO2k8PW47aSsrKXsKICAgIGN1clswXT1pOwogICAgZm9yKGo9MTtqPD1tO2orKyl7CiAgICAgIHZhciBjPShhLmNoYXJBdChpLTEpPT09Yi5jaGFyQXQoai0xKSk/MDoxOwogICAgICB2YXIgdj1wcmV2W2pdKzE7CiAgICAgIGlmKGN1cltqLTFdKzE8dil7IHY9Y3VyW2otMV0rMTsgfQogICAgICBpZihwcmV2W2otMV0rYzx2KXsgdj1wcmV2W2otMV0rYzsgfQogICAgICBjdXJbal09djsKICAgIH0KICAgIGZvcihqPTA7ajw9bTtqKyspeyBwcmV2W2pdPWN1cltqXTsgfQogIH0KICByZXR1cm4gcHJldlttXTsKfQpmdW5jdGlvbiBzaW1QYXIoYSxiKXsgYT1ub3JtKGEpOyBiPW5vcm0oYik7IGlmKCFhfHwhYil7IHJldHVybiAwOyB9IHJldHVybiAxLShsZXYoYSxiKS9NYXRoLm1heChhLmxlbmd0aCxiLmxlbmd0aCkpOyB9CmZ1bmN0aW9uIHNpbU5vbWJyZXMoYSxiKXsKICBhPW5vcm0oYSk7IGI9bm9ybShiKTsKICBpZighYXx8IWIpeyByZXR1cm4gMDsgfQogIHZhciBzMT1zaW1QYXIoYSxiKTsKICB2YXIgdGE9YS5zcGxpdCgnICcpLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPjE7IH0pOwogIHZhciB0Yj1iLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgdmFyIHMyPTA7CiAgaWYodGEubGVuZ3RoJiZ0Yi5sZW5ndGgpewogICAgdmFyIGNvcnRvPSh0YS5sZW5ndGg8PXRiLmxlbmd0aCk/dGE6dGI7CiAgICB2YXIgbGFyZ289KHRhLmxlbmd0aDw9dGIubGVuZ3RoKT90Yjp0YTsKICAgIHZhciB0b3Q9MCxpLGo7CiAgICBmb3IoaT0wO2k8Y29ydG8ubGVuZ3RoO2krKyl7CiAgICAgIHZhciBtZWpvcj0wOwogICAgICBmb3Ioaj0wO2o8bGFyZ28ubGVuZ3RoO2orKyl7IHZhciB2PXNpbVBhcihjb3J0b1tpXSxsYXJnb1tqXSk7IGlmKHY+bWVqb3IpeyBtZWpvcj12OyB9IH0KICAgICAgdG90Kz1tZWpvcjsKICAgIH0KICAgIHMyPXRvdC9jb3J0by5sZW5ndGg7CiAgfQogIHJldHVybiBNYXRoLm1heChzMSxzMik7Cn0KCi8qID09PT09PT09PT09PT09PT09IE1SWiB5IG5vbWJyZSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBtcnpMaW5lYXModCl7CiAgdmFyIG91dD1bXSwgbGluZXM9KHR8fCcnKS5zcGxpdCgvW1xyXG5dKy8pLCBpOwogIGZvcihpPTA7aTxsaW5lcy5sZW5ndGg7aSsrKXsKICAgIHZhciBsPWxpbmVzW2ldLnJlcGxhY2UoL1tccy5dL2csJycpLnRvVXBwZXJDYXNlKCk7CiAgICBpZihsLmxlbmd0aD49MjAgJiYgL15bQS1aMC05PF0rJC8udGVzdChsKSAmJiBsLmluZGV4T2YoJzw8Jyk+PTApeyBvdXQucHVzaChsKTsgfQogIH0KICByZXR1cm4gb3V0Owp9CmZ1bmN0aW9uIG1yek5vbWJyZXModCl7CiAgdmFyIHJlcz1bXSwgdmlzdG9zPXt9LCBscz1tcnpMaW5lYXModCksIGk7CiAgZnVuY3Rpb24gcHVzaChub21icmUpewogICAgbm9tYnJlPW5vcm0obm9tYnJlKTsKICAgIGlmKG5vbWJyZSAmJiBub21icmUubGVuZ3RoPj0zICYmICF2aXN0b3Nbbm9tYnJlXSl7IHZpc3Rvc1tub21icmVdPTE7IHJlcy5wdXNoKG5vbWJyZSk7IH0KICB9CiAgZm9yKGk9MDtpPGxzLmxlbmd0aDtpKyspewogICAgdmFyIGw9bHNbaV0sIG07CiAgICBtPWwubWF0Y2goL15QPChbQS1aXXswLDN9KShbQS1aXXsyLH0pPDwoW0EtWjxdKikvKTsKICAgIGlmKG0peyBwdXNoKG1bMl0rJyAnKyhtWzNdfHwnJykpOyB9CiAgICBtPWwubWF0Y2goL15QPChbQS1aXXswLDN9PykoW0EtWl17Mix9KTw8KFtBLVo8XSopLyk7CiAgICBpZihtKXsgcHVzaChtWzJdKycgJysobVszXXx8JycpKTsgfQogICAgbT1sLm1hdGNoKC9eKFtBLVo8XXs0LH0pPDwoW0EtWjxdezIsfSkvKTsKICAgIGlmKG0peyBwdXNoKG1bMV0rJyAnKyhtWzJdfHwnJykpOyB9CiAgICBtPWwubWF0Y2goL14oW0EtWl17Mix9KTw8KFtBLVo8XSopLyk7CiAgICBpZihtKXsgcHVzaChtWzFdKycgJysobVsyXXx8JycpKTsgfQogICAgbT1sLm1hdGNoKC8oW0EtWl17Mix9KTw8KFtBLVo8XXsyLH0pLyk7CiAgICBpZihtKXsgcHVzaChtWzFdKycgJysobVsyXXx8JycpKTsgfQogIH0KICByZXR1cm4gcmVzOwp9CmZ1bmN0aW9uIG5vbWJyZURlVGV4dG8odCl7CiAgdmFyIFQ9KHR8fCcnKS50b1VwcGVyQ2FzZSgpLCBjYW5kPVtdLCBtLCBpOwogIHZhciByZT0vKE5PTUJSRVM/fEFQRUxMSURPUz98TkFNRVM/fFNVUk5BTUUpXHMqWzpcLlwtXT9ccyooKD86W0EtWlx1MDBDMVx1MDBDOVx1MDBDRFx1MDBEM1x1MDBEQVx1MDBEQ1x1MDBEMV1bQS1aXHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxXXsxLDE1fSkoPzpbXHNcLl0rW0EtWlx1MDBDMVx1MDBDOVx1MDBDRFx1MDBEM1x1MDBEQVx1MDBEQ1x1MDBEMV1bQS1aXHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxXXsxLDE1fSl7MCw0fSkvZzsKICB3aGlsZSgobT1yZS5leGVjKFQpKSE9PW51bGwpeyBpZihtWzJdKXsgY2FuZC5wdXNoKG1bMl0pOyB9IH0KICBjYW5kPWNhbmQuY29uY2F0KG1yek5vbWJyZXMoVCkpOwogIHZhciBsaW5lcz1ULnNwbGl0KC9bXHJcbl0rLyk7CiAgZm9yKGk9MDtpPGxpbmVzLmxlbmd0aDtpKyspewogICAgdmFyIHc9bGluZXNbaV0ucmVwbGFjZSgvW15BLVpcdTAwQzFcdTAwQzlcdTAwQ0RcdTAwRDNcdTAwREFcdTAwRENcdTAwRDEgXS9nLCcgJykudHJpbSgpLnNwbGl0KC9ccysvKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD49MzsgfSk7CiAgICBpZih3Lmxlbmd0aD49MiAmJiB3Lmxlbmd0aDw9NCl7IGNhbmQucHVzaCh3LmpvaW4oJyAnKSk7IH0KICB9CiAgcmV0dXJuIGNhbmQ7Cn0KZnVuY3Rpb24gdG9rZW5zRGUocyl7IHJldHVybiBub3JtKHMpLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7IH0KZnVuY3Rpb24gcGFyUGFyZWNpZG8odDEsdDIpewogIGlmKHQxPT09dDIpeyByZXR1cm4gdHJ1ZTsgfQogIGlmKHNpbVBhcih0MSx0Mik+PTAuNzgpeyByZXR1cm4gdHJ1ZTsgfQogIGlmKHQxLmxlbmd0aD49NCYmdDIubGVuZ3RoPj00JiYodDEuaW5kZXhPZih0Mik9PT0wfHx0Mi5pbmRleE9mKHQxKT09PTApKXsgcmV0dXJuIHRydWU7IH0KICByZXR1cm4gZmFsc2U7Cn0KLyogPT09PT09PT09PT09IGd1YXJkaWFuYXMgZGUgbGEgbGVjdHVyYSBjb25maXJtYWRhIChwYXNvIDIpID09PT09PT09PT09PSAqLwpmdW5jdGlvbiB0b2tlbnNOb21icmVEZSh0ZXh0byl7CiAgdmFyIFQ9bm9ybSh0ZXh0bykuc3BsaXQoJyAnKSwgb3V0PVtdLCBpLCBqOwogIGZvcihpPTA7aTxULmxlbmd0aDtpKyspewogICAgdmFyIHQ9VFtpXTsKICAgIGlmKHQubGVuZ3RoPDN8fHQubGVuZ3RoPjE1KXsgY29udGludWU7IH0KICAgIGlmKCEvXltBLVpdKyQvLnRlc3QodCkpeyBjb250aW51ZTsgfQogICAgdmFyIG1hbGE9ZmFsc2U7CiAgICBmb3Ioaj0wO2o8UEFMQUJSQVNfTk9fTk9NQlJFLmxlbmd0aDtqKyspeyBpZih0LmluZGV4T2YoUEFMQUJSQVNfTk9fTk9NQlJFW2pdKT09PTApeyBtYWxhPXRydWU7IGJyZWFrOyB9IH0KICAgIGlmKCFtYWxhKXsgb3V0LnB1c2godCk7IH0KICB9CiAgcmV0dXJuIG91dDsKfQpmdW5jdGlvbiBlZGljaW9uQWNlcHRhYmxlKHRleHRvRWRpdGFkbywgb2NyVG9rcyl7CiAgdmFyIHRva3M9dG9rZW5zRGUodGV4dG9FZGl0YWRvKSwgaSwgajsKICBpZighdG9rcy5sZW5ndGh8fCFvY3JUb2tzfHwhb2NyVG9rcy5sZW5ndGgpeyByZXR1cm4gZmFsc2U7IH0KICBmb3IoaT0wO2k8dG9rcy5sZW5ndGg7aSsrKXsKICAgIHZhciBwYXNhPWZhbHNlOwogICAgZm9yKGo9MDtqPG9jclRva3MubGVuZ3RoO2orKyl7CiAgICAgIGlmKHBhclBhcmVjaWRvKHRva3NbaV0sb2NyVG9rc1tqXSkpeyBwYXNhPXRydWU7IGJyZWFrOyB9CiAgICAgIGlmKHRva3NbaV0ubGVuZ3RoPj01JiZvY3JUb2tzW2pdLmxlbmd0aD49NSYmbGV2KHRva3NbaV0sb2NyVG9rc1tqXSk8PTIpeyBwYXNhPXRydWU7IGJyZWFrOyB9CiAgICB9CiAgICBpZighcGFzYSl7IHJldHVybiBmYWxzZTsgfQogIH0KICByZXR1cm4gdHJ1ZTsKfQp2YXIgUEFMQUJSQVNfTk9fTk9NQlJFPVsnRE9NSUNJTElPJywnRElSRUNDSU9OJywnQ09MT05JQScsJ0JBUlJJTycsJ1JFU0lERU5DSUEnLCdDQVNFUklPJywnQ0FOVE9OJywnQUxERUEnLCdTRUNUT1InLCdPQlNFUlZBQ0lPTicsJ0VTVEFETycsJ0RPTkFOVEUnLCdHUlVQTycsJ1NBTkdSRScsJ1NBTkcnLCdNVU5JQ0lQSU8nLCdERVBBUlRBTUVOVE8nLCdGRUNIQScsJ05BQ0lNSUVOVE8nLCdTRVhPJywnTkFDSU9OQUxJREFEJywnRk9MSU8nLCdOVU1FUk8nLCdET0NVTUVOVE8nLCdDRURVTEEnLCdJREVOVElEQUQnLCdMSUNFTkNJQScsJ1JFUFVCTEknLCdTRUNSRVRBUklBJywnRU1JU0lPTicsJ1ZFTkNJTUlFTlRPJywnQ0xBU0UnLCdDQVRFR09SSUEnLCdFTkRPUlNFTUVOVCcsJ1JFU1RSSUNUSU9OJywnQUREUkVTUycsJ0xVR0FSJywnRURBRCcsJ1BBUkVOJywnRklMSUFDSU9OJywnRklMSUFDSU9OJywnTUFSQ0EnLCdTUEVDSU1FTicsJ1NBTVBMRScsJ1ZPVEFDSU9OJywnVE9NQURPUicsJ05BQ0lPJywnRE9NJywnTk9NQlJFUycsJ05PTUJSRScsJ0FQRUxMSURPUycsJ0FQRUxMSURPJywnQ0lVREFEJywnQVZFTklEQScsJ0JPVUxFVkFSRCcsJ0RVSScsJ0RQSSddOwpmdW5jdGlvbiBwYXJlY2VOb21icmVMaW5lYShjKXsKICB2YXIgdz0oY3x8JycpLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgaWYody5sZW5ndGg8Mnx8dy5sZW5ndGg+NSl7IHJldHVybiBmYWxzZTsgfQogIHZhciBtYWxvcz17J0VMJzoxLCdMQSc6MSwnTE9TJzoxLCdMQVMnOjEsJ0RFJzoxLCdERUwnOjF9OwogIGZvcih2YXIgaT0wO2k8dy5sZW5ndGg7aSsrKXsKICAgIGlmKG1hbG9zW3dbaV1dKXsgcmV0dXJuIGZhbHNlOyB9CiAgICBmb3IodmFyIGo9MDtqPFBBTEFCUkFTX05PX05PTUJSRS5sZW5ndGg7aisrKXsgaWYod1tpXS5pbmRleE9mKFBBTEFCUkFTX05PX05PTUJSRVtqXSk9PT0wKXsgcmV0dXJuIGZhbHNlOyB9IH0KICB9CiAgcmV0dXJuIHRydWU7Cn0KZnVuY3Rpb24gbm9tYnJlQ29pbmNpZGUoZXNjcml0bywgdGV4dG9Eb2MsIGVzdHJpY3RvKXsKICB2YXIgdmFjaW89e29rOmZhbHNlLCBsZWlkbzonJywgcHVudDowLCBoYXk6ZmFsc2V9OwogIHZhciBVPXRva2Vuc0RlKGVzY3JpdG8pOwogIGlmKFUubGVuZ3RoPDIpeyByZXR1cm4gdmFjaW87IH0KICB2YXIgY2FuZD1ub21icmVEZVRleHRvKHRleHRvRG9jKSwgbGltcGlvcz1bXSwgaSwgazsKICBmb3IoaT0wO2k8Y2FuZC5sZW5ndGg7aSsrKXsKICAgIHZhciBjPW5vcm0oY2FuZFtpXSk7CiAgICBpZighYyl7IGNvbnRpbnVlOyB9CiAgICB2YXIgdG9rcz1jLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgICBpZih0b2tzLmxlbmd0aDwyfHx0b2tzLmxlbmd0aD41KXsgY29udGludWU7IH0KICAgIGlmKCFwYXJlY2VOb21icmVMaW5lYShjKSl7IGNvbnRpbnVlOyB9CiAgICBsaW1waW9zLnB1c2godG9rcyk7CiAgfQogIHZhciBUMj1ub3JtKHRleHRvRG9jKS5zcGxpdCgnICcpLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPjE7IH0pOwogIHZhciB2aXN0YXM9e30sIGkyLCBMMjsKICBmb3IoaTI9MDtpMjxsaW1waW9zLmxlbmd0aDtpMisrKXsgdmlzdGFzW2xpbXBpb3NbaTJdLmpvaW4oJyAnKV09MTsgfQogIGZvcihpMj0wO2kyPFQyLmxlbmd0aDtpMisrKXsKICAgIGZvcihMMj0yO0wyPD00ICYmIGkyK0wyPD1UMi5sZW5ndGg7TDIrKyl7CiAgICAgIHZhciB3aW49VDIuc2xpY2UoaTIsaTIrTDIpLmpvaW4oJyAnKTsKICAgICAgaWYoIXZpc3Rhc1t3aW5dICYmIHBhcmVjZU5vbWJyZUxpbmVhKHdpbikpeyB2aXN0YXNbd2luXT0xOyBsaW1waW9zLnB1c2god2luLnNwbGl0KCcgJykpOyB9CiAgICB9CiAgfQogIGlmKCFsaW1waW9zLmxlbmd0aCl7IHJldHVybiB2YWNpbzsgfQogIHZhciB1bmlvbj17fSwgY2xhdmVzPVtdOwogIGZvcihpPTA7aTxsaW1waW9zLmxlbmd0aDtpKyspewogICAgZm9yKGs9MDtrPGxpbXBpb3NbaV0ubGVuZ3RoO2srKyl7CiAgICAgIGlmKCF1bmlvbltsaW1waW9zW2ldW2tdXSl7IHVuaW9uW2xpbXBpb3NbaV1ba11dPTE7IGNsYXZlcy5wdXNoKGxpbXBpb3NbaV1ba10pOyB9CiAgICB9CiAgfQogIGZ1bmN0aW9uIGN1YW50b3MobGlzdGEpewogICAgdmFyIG49MCwgaiwgdDsKICAgIGZvcihqPTA7ajxVLmxlbmd0aDtqKyspewogICAgICBmb3IodD0wO3Q8bGlzdGEubGVuZ3RoO3QrKyl7IGlmKHBhclBhcmVjaWRvKFVbal0sbGlzdGFbdF0pKXsgbisrOyBicmVhazsgfSB9CiAgICB9CiAgICByZXR1cm4gbjsKICB9CiAgdmFyIG1lam9yQ2FuZD0nJywgbWVqb3JDb3Y9MDsKICBmb3IoaT0wO2k8bGltcGlvcy5sZW5ndGg7aSsrKXsKICAgIHZhciBjb3Y9Y3VhbnRvcyhsaW1waW9zW2ldKS9VLmxlbmd0aDsKICAgIGlmKGNvdj5tZWpvckNvdil7IG1lam9yQ292PWNvdjsgbWVqb3JDYW5kPWxpbXBpb3NbaV0uam9pbignICcpOyB9CiAgfQogIHZhciBjb3ZVPWN1YW50b3MoY2xhdmVzKS9VLmxlbmd0aDsKICBpZihjb3ZVPm1lam9yQ292KXsgbWVqb3JDb3Y9Y292VTsgfQogIHZhciBuTWF0Y2g9Y3VhbnRvcyhjbGF2ZXMpLCBtZWpvclNpbT0wLCBqMywgdDM7CiAgZm9yKGozPTA7ajM8VS5sZW5ndGg7ajMrKyl7CiAgICBmb3IodDM9MDt0MzxjbGF2ZXMubGVuZ3RoO3QzKyspewogICAgICBpZihwYXJQYXJlY2lkbyhVW2ozXSxjbGF2ZXNbdDNdKSl7IHZhciBzdj1zaW1QYXIoVVtqM10sY2xhdmVzW3QzXSk7IGlmKHN2Pm1lam9yU2ltKXsgbWVqb3JTaW09c3Y7IH0gfQogICAgfQogIH0KICB2YXIgb2s7CiAgaWYobWVqb3JDb3Y+PTAuOTk5KXsgb2s9dHJ1ZTsgfQogIGVsc2UgaWYoZXN0cmljdG8peyBvaz1mYWxzZTsgfQogIGVsc2UgaWYobk1hdGNoPj0yICYmIGNvdlU+PTAuNSl7IG9rPXRydWU7IH0KICBlbHNlIGlmKG5NYXRjaD49MSAmJiBjb3ZVPj0wLjUgJiYgbWVqb3JTaW0+PTAuODApeyBvaz10cnVlOyB9CiAgZWxzZSBpZihuTWF0Y2g+PTEgJiYgbWVqb3JTaW0+PTAuOTgpeyBvaz10cnVlOyB9CiAgZWxzZXsgb2s9ZmFsc2U7IH0KICByZXR1cm4ge29rOm9rLCBsZWlkbzptZWpvckNhbmQsIHB1bnQ6bWVqb3JDb3YsIGhheTp0cnVlfTsKfQoKLyogPT09PT09PT09PT09PT09PT0gZGV0ZWNjaW9uIGRlIGxhZG8gPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gZGV0ZWN0YXJMYWRvKHRleHRvLCB0aWVuZUNhcmEpewogIHZhciB0PSh0ZXh0b3x8JycpLnRvVXBwZXJDYXNlKCk7CiAgdmFyIHJldj0wLCBmcmU9MCwgaTsKICB2YXIgbHQ9KHQubWF0Y2goLzwvZyl8fFtdKS5sZW5ndGg7CiAgaWYobHQ+PTYpeyByZXR1cm4gJ3JldmVyc28nOyB9CiAgaWYoL1BERjRJPzcvLnRlc3QodC5yZXBsYWNlKC9ccy9nLCcnKSkpeyByZXYrPTIuNTsgfQogIHZhciBSVnM9WydET01JQ0lMSU8nLCdESVJFQ0NJT04nLCdESVJFQ0NJXHUwMEQzTicsJ0NPTE9OSUEnLCdCQVJSSU8nLCdSRVNJREVOQ0lBJywnQ0FTRVJJTycsJ0NBTlRPTicsJ0FMREVBJywnU0VDVE9SJywnT0JTRVJWQUNJT04nLCdPQlNFUlZBQ0lcdTAwRDNOJywnRE9OQU5URScsJ0dSVVBPIFNBTkcnLCdUSVBPIERFIFNBTkcnLCdTQU5HVUlORU8nLCdFU1RBRE8gQ0lWSUwnLCdFTkRPUlNFTUVOVCcsJ1JFU1RSSUNUSU9OJywnTVVOSUNJUElPJ107CiAgdmFyIFJWdz1bJ0VNSVNJT04nLCdFTUlTSVx1MDBEM04nLCdWRU5DSU1JRU5UTycsJ1ZFTkNFJywnRVhQSVJFUycsJ0lTU1VFRCcsJ1ZBTElERVonLCdFWFBJUkEnLCdDTEFTRScsJ0NBVEVHT1JJQScsJ0NBVEVHT1JcdTAwQ0RBJywnSVNTJywnRVhQJ107CiAgdmFyIEZSPVsnTk9NQlJFUycsJ0FQRUxMSURPUycsJ05BTUVTJywnU1VSTkFNRScsJ0dJVkVOJywnRFVJJywnRE9DVU1FTlRPIFVOSUNPJywnRE9DVU1FTlRPIFx1MDBEQU5JQ08nLCdDRURVTEEnLCdDXHUwMEM5RFVMQScsJ0lERU5USURBRCcsJ0xJQ0VOQ0lBJywnRFJJVkVSJywnTkFDSU1JRU5UTycsJ0JJUlRIJywnU0VYTycsJ1NFWCcsJ05BQ0lPTkFMSURBRCcsJ05BQ0lPTkFMSVRZJywnRk9MSU8nLCdSRVBVQkxJJywnTlVNRVJPJywnTlx1MDBEQU1FUk8nLCdOVU1CRVInLCdJRCBOTyddOwogIGZvcihpPTA7aTxSVnMubGVuZ3RoO2krKyl7IGlmKHQuaW5kZXhPZihSVnNbaV0pPj0wKXsgcmV2Kz0yOyB9IH0KICBmb3IoaT0wO2k8UlZ3Lmxlbmd0aDtpKyspeyBpZih0LmluZGV4T2YoUlZ3W2ldKT49MCl7IHJldis9MC43NTsgfSB9CiAgZm9yKGk9MDtpPEZSLmxlbmd0aDtpKyspeyBpZih0LmluZGV4T2YoRlJbaV0pPj0wKXsgZnJlKz0xOyB9IH0KICBpZih0aWVuZUNhcmEpeyBmcmUrPTQ7IH0KICBpZihyZXY+PTMuNSAmJiByZXY+ZnJlKzEpeyByZXR1cm4gJ3JldmVyc28nOyB9CiAgaWYoZnJlPj0zICYmIGZyZT5yZXYrMSl7IHJldHVybiAnZnJlbnRlJzsgfQogIGlmKHJldj5mcmUgJiYgcmV2Pj0yKXsgcmV0dXJuICdyZXZlcnNvJzsgfQogIGlmKGZyZT5yZXYgJiYgZnJlPj0yKXsgcmV0dXJuICdmcmVudGUnOyB9CiAgcmV0dXJuICdkZXNjb25vY2lkbyc7Cn0KCi8qID09PT09PT09PT09PT09PT09IGdhbmNobyBwYXJhIHBydWViYXMgKG5vZGUsIHNpbiBET00pID09PT09PT09PT09PT09PT09ICovCmlmICh0eXBlb2YgZG9jdW1lbnQ9PT0ndW5kZWZpbmVkJyB8fCB0eXBlb2YgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQhPT0nZnVuY3Rpb24nKXsKICBXLl9fWllSQV9URVNUX189e25vcm06bm9ybSxsZXY6bGV2LHNpbVBhcjpzaW1QYXIsc2ltTm9tYnJlczpzaW1Ob21icmVzLG1yekxpbmVhczptcnpMaW5lYXMsbXJ6Tm9tYnJlczptcnpOb21icmVzLG5vbWJyZURlVGV4dG86bm9tYnJlRGVUZXh0byxub21icmVDb2luY2lkZTpub21icmVDb2luY2lkZSxkZXRlY3RhckxhZG86ZGV0ZWN0YXJMYWRvLGV2YWx1YUNhcmE6ZXZhbHVhQ2FyYSxlYXJEZTplYXJEZSxjZW50cm9EZTpjZW50cm9EZSxxdWFkVmFsaWRvOnF1YWRWYWxpZG8sYXJlYVF1YWQ6YXJlYVF1YWQsZXRpcXVldGFDb21wb25lbnRlczpldGlxdWV0YUNvbXBvbmVudGVzLGVzcXVpbmFzRGVNYXNjYXJhOmVzcXVpbmFzRGVNYXNjYXJhLG1lZGlhbmFRdWFkOm1lZGlhbmFRdWFkLHF1YWRFc3RhYmxlOnF1YWRFc3RhYmxlLG5pdG9EZTpuaXRvRGUsZnJhY2Npb25CbGFuY286ZnJhY2Npb25CbGFuY28sdG9rZW5zTm9tYnJlRGU6dG9rZW5zTm9tYnJlRGUsZWRpY2lvbkFjZXB0YWJsZTplZGljaW9uQWNlcHRhYmxlLGVsZWdpclRleHRvOmVsZWdpclRleHRvLHBhclBhcmVjaWRvOnBhclBhcmVjaWRvLHRva2Vuc0RlOnRva2Vuc0RlfTsKICByZXR1cm47Cn0KCi8qID09PT09PT09PT09PT09PT09IGdhbmNobyBkZSBwcnVlYmFzIGNvbiBET00gc2ltdWxhZG8gPT09PT09PT09PT09PT09PT0gKi8KVy5fX1pZUkFfUkVWRl9URVNUX189e307CgovKiA9PT09PT09PT09PT09PT09PSBmZXRjaCBjb24gcmVpbnRlbnRvcyArIHdhcm11cCA9PT09PT09PT09PT09PT09PSAqLwooZnVuY3Rpb24oKXsKICBpZihXLl9fenlGZXRjaEZpeCl7IHJldHVybjsgfQogIFcuX196eUZldGNoRml4PTE7CiAgdmFyIF9mPVcuZmV0Y2g/Vy5mZXRjaC5iaW5kKFcpOm51bGw7CiAgaWYoIV9mKXsgcmV0dXJuOyB9CiAgVy5mZXRjaD1mdW5jdGlvbigpewogICAgdmFyIGFyZ3M9YXJndW1lbnRzLCBuPTA7CiAgICBmdW5jdGlvbiBvdHJvKCl7IHJldHVybiBfZi5hcHBseShudWxsLGFyZ3MpLnRoZW4oZnVuY3Rpb24ocil7CiAgICAgIGlmKFs1MDAsNTAyLDUwMyw1MDQsNDEzXS5pbmRleE9mKHIuc3RhdHVzKT49MCAmJiBuPDMpeyBuKys7IHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpeyBzZXRUaW1lb3V0KHJlcyw3MDAqbik7IH0pLnRoZW4ob3Rybyk7IH0KICAgICAgcmV0dXJuIHI7CiAgICB9LCBmdW5jdGlvbihlKXsKICAgICAgaWYobjwzKXsgbisrOyByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsgc2V0VGltZW91dChyZXMsNzAwKm4pOyB9KS50aGVuKG90cm8pOyB9CiAgICAgIHRocm93IGU7CiAgICB9KTsgfQogICAgcmV0dXJuIG90cm8oKTsKICB9OwogIHRyeXsgX2YoVy5sb2NhdGlvbi5wYXRobmFtZSx7Y2FjaGU6J25vLXN0b3JlJyxoZWFkZXJzOnsneC16eS13YXJtdXAnOicxJ319KS5jYXRjaChmdW5jdGlvbigpe30pOyB9Y2F0Y2goZSl7fQp9KSgpOwoKLyogPT09PT09PT09PT09PT09PT0gZXN0YWRvIGRlbCBmbHVqbyA9PT09PT09PT09PT09PT09PSAqLwp2YXIgRVNUPXtwYXNvOjEsIHRpcG86J2Rlc2Nvbm9jaWRvJywgbmVjZXNpdGFSZXZlcnNvOnRydWUsIG5vbWJyZU9rOmZhbHNlLCBmcmVudGVPazpmYWxzZSwgcmV2ZXJzb09rOmZhbHNlLCBzZWxmaWVPazpmYWxzZSwgaW50ZW50b3M6MywgZnJlbnRlSW1nOicnLCByZXZlcnNvSW1nOicnLCBzZWxmaWVJbWc6JycsIGVzY3JpdG86JycsIGZyZW50ZVRleHRvOicnLCByZXZlcnNvVGV4dG86JycsIGNhcmFWaXZhOm51bGwsIGNhcmFEb2M6bnVsbH07CnZhciBzdHJlYW1zPXt9Owp2YXIgSElOVFM9e307CgpmdW5jdGlvbiBjbGFzaWZpY2FyVGlwbygpewogIHZhciBzZWw9JCgndGlwb0RvYycpLCB0eHQ9Jyc7CiAgaWYoc2VsKXsKICAgIHZhciBvcD1zZWwub3B0aW9ucyAmJiBzZWwub3B0aW9uc1tzZWwuc2VsZWN0ZWRJbmRleF07CiAgICB0eHQ9KG9wJiZvcC50ZXh0P29wLnRleHQ6JycpKycgJysoc2VsLnZhbHVlfHwnJyk7CiAgfQogIHR4dD10eHQudG9Mb3dlckNhc2UoKTsKICBpZigvcGFzYXBvcnRlfHBhc3Nwb3J0Ly50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J3Bhc2Fwb3J0ZScsIHJldmVyc286ZmFsc2V9OyB9CiAgaWYoL3NhbHZhZG9yfFxiZHVpXGIvLnRlc3QodHh0KSl7IHJldHVybiB7azonZHVpJywgcmV2ZXJzbzp0cnVlfTsgfQogIGlmKC9ndWF0ZW1hbGF8Z3VhdGUvLnRlc3QodHh0KSl7IHJldHVybiB7azonZ3QnLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL25pY2FyYWd1YS8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOiduaScsIHJldmVyc286dHJ1ZX07IH0KICBpZigvaG9uZHVyYXMvLnRlc3QodHh0KSl7IHJldHVybiB7azonaG4nLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL3VzYXxlc3RhZG9zIHVuaWRvc3xsaWNlbmNpYXxsaWNlbnNlfGRyaXZlci8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOid1c2EnLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL290cm98b3RoZXIvLnRlc3QodHh0KSl7IHJldHVybiB7azonb3RybycsIHJldmVyc286dHJ1ZX07IH0KICByZXR1cm4ge2s6J2Rlc2Nvbm9jaWRvJywgcmV2ZXJzbzp0cnVlfTsKfQoKLyogPT09PT09PT09PT09PT09PT0gbWVuc2FqZXMgeSBheXVkYXMgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gbXNnKGlkLHRleHRvLGNvbG9yKXsKICB2YXIgZWw9JChpZCk7CiAgaWYoIWVsICYmIEhJTlRTW2lkXSl7IGVsPUhJTlRTW2lkXTsgfQogIGlmKCFlbCl7CiAgICB2YXIgYW5jbGE9JCgncHMxJyk7CiAgICBlbD1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgIGVsLmlkPWlkOwogICAgZWwuc3R5bGUuY3NzVGV4dD0nZm9udC1zaXplOjEzcHg7bWFyZ2luOjZweCAwO2xpbmUtaGVpZ2h0OjEuMzU7JzsKICAgIGlmKGFuY2xhICYmIGFuY2xhLnBhcmVudE5vZGUpeyBhbmNsYS5wYXJlbnROb2RlLmluc2VydEJlZm9yZShlbCxhbmNsYS5uZXh0U2libGluZyk7IH0KICAgIGVsc2V7IGRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQoZWwpOyB9CiAgICBISU5UU1tpZF09ZWw7CiAgfQogIGVsLnRleHRDb250ZW50PXRleHRvfHwnJzsKICBpZihjb2xvcil7IGVsLnN0eWxlLmNvbG9yPWNvbG9yOyB9Cn0KZnVuY3Rpb24gYnVzeShvbil7CiAgdmFyIGlkcz1bJ2Jsb2NGJywnYmxvY0EnLCdibG9jUyddLCBpOwogIGZvcihpPTA7aTxpZHMubGVuZ3RoO2krKyl7IHZhciBiPSQoaWRzW2ldKTsgaWYoYil7IGIuc3R5bGUuZGlzcGxheT1vbj8nZmxleCc6J25vbmUnOyB9IH0KfQpmdW5jdGlvbiBzaG93SW1nKGlkLGRhdGFVcmwpewogIHZhciBwPSQoaWQpOwogIGlmKHApewogICAgcC5zcmM9ZGF0YVVybDsKICAgIHAuc3R5bGUuZGlzcGxheT0nYmxvY2snOwogICAgcC5zdHlsZS5tYXhXaWR0aD0nMjQwcHgnOwogICAgcC5zdHlsZS5tYXhIZWlnaHQ9JzI0MHB4JzsKICAgIHAuc3R5bGUud2lkdGg9J2F1dG8nOwogICAgcC5zdHlsZS5oZWlnaHQ9J2F1dG8nOwogICAgcC5zdHlsZS5ib3JkZXJSYWRpdXM9JzEwcHgnOwogICAgcC5zdHlsZS5tYXJnaW49JzhweCBhdXRvJzsKICAgIHAuc3R5bGUuZGlzcGxheT0nYmxvY2snOwogIH0KfQoKLyogPT09PT09PT09PT09PT09PT0gY2FtYXJhOiBwcmV2aWV3IFNJRU1QUkUgY2hpY28gPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gbGV0cmFEZShwc0lkKXsgcmV0dXJuICh7JzInOidGJywnMyc6J0EnLCc0JzonUyd9KVtwc0lkXXx8J0YnOyB9CmZ1bmN0aW9uIGZpbmRWaWRlbyhwc0lkKXsKICB2YXIgbGV0cmE9bGV0cmFEZShwc0lkKTsKICB2YXIgaWRzPVsndnonK2xldHJhLCd2ZCcrbGV0cmEsJ3YnK2xldHJhXSwgaTsKICB2YXIgY29udD0kKCdwcycrcHNJZCk7CiAgZm9yKGk9MDtpPGlkcy5sZW5ndGg7aSsrKXsKICAgIHZhciBjYW5kPSQoaWRzW2ldKTsKICAgIGlmKGNhbmQgJiYgY2FuZC50YWdOYW1lPT09J1ZJREVPJyl7IHJldHVybiBjYW5kOyB9CiAgfQogIGlmKGNvbnQpewogICAgdmFyIHY9Y29udC5xdWVyeVNlbGVjdG9yKCd2aWRlbycpOwogICAgaWYodil7IHJldHVybiB2OyB9CiAgfQogIHJldHVybiBudWxsOwp9CmZ1bmN0aW9uIGVzdGlsb0NoaWNvKHYpewogIGlmKCF2KXsgcmV0dXJuOyB9CiAgdi5zdHlsZS5tYXhXaWR0aD0nMjgwcHgnOwogIHYuc3R5bGUud2lkdGg9JzEwMCUnOwogIHYuc3R5bGUubWF4SGVpZ2h0PSczMjBweCc7CiAgdHJ5eyB2LnN0eWxlLmFzcGVjdFJhdGlvPSczIC8gNCc7IH1jYXRjaChlKXt9CiAgdi5zdHlsZS5vYmplY3RGaXQ9J2NvdmVyJzsKICB2LnN0eWxlLmJvcmRlclJhZGl1cz0nMTJweCc7CiAgdi5zdHlsZS5iYWNrZ3JvdW5kPScjMDAwJzsKICB2LnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsKICB2LnN0eWxlLm1hcmdpbj0nMCBhdXRvJzsKfQpmdW5jdGlvbiB2aWJyYXIoKXsgdHJ5eyBpZihuYXZpZ2F0b3IudmlicmF0ZSl7IG5hdmlnYXRvci52aWJyYXRlKDcwKTsgfSB9Y2F0Y2goZSl7fSB9CmZ1bmN0aW9uIGFsaW5lYXJPdmVybGF5KHBzSWQsIHYpewogIHRyeXsKICAgIHZhciBPVj17JzInOidvdkYnLCczJzonb3ZBJywnNCc6J292Uyd9OwogICAgdmFyIG92PSQoT1ZbcHNJZF0pOyBpZighb3Z8fCF2KXsgcmV0dXJuOyB9CiAgICB2YXIgej0kKCd2eicrbGV0cmFEZShwc0lkKSk7IGlmKCF6KXsgcmV0dXJuOyB9CiAgICB2YXIgdnI9di5nZXRCb3VuZGluZ0NsaWVudFJlY3QoKSwgenI9ei5nZXRCb3VuZGluZ0NsaWVudFJlY3QoKTsKICAgIGlmKCF2ci53aWR0aHx8IXZyLmhlaWdodCl7IHJldHVybjsgfQogICAgb3Yuc3R5bGUucG9zaXRpb249J2Fic29sdXRlJzsKICAgIG92LnN0eWxlLmxlZnQ9TWF0aC5yb3VuZCh2ci5sZWZ0LXpyLmxlZnQpKydweCc7CiAgICBvdi5zdHlsZS50b3A9TWF0aC5yb3VuZCh2ci50b3AtenIudG9wKSsncHgnOwogICAgb3Yuc3R5bGUud2lkdGg9dnIud2lkdGgrJ3B4JzsKICAgIG92LnN0eWxlLmhlaWdodD12ci5oZWlnaHQrJ3B4JzsKICAgIHRyeXsgb3Yuc3R5bGUub2JqZWN0Rml0PSdjb3Zlcic7IH1jYXRjaChlMil7fQogICAgb3Yuc3R5bGUuYm9yZGVyUmFkaXVzPScxMnB4JzsKICAgIG92LnN0eWxlLnpJbmRleD0nNSc7CiAgfWNhdGNoKGUpe30KfQpmdW5jdGlvbiB6eURldCgpeyBpZighVy5fX3p5RGV0KXsgVy5fX3p5RGV0PXt9OyB9IHJldHVybiBXLl9fenlEZXQ7IH0KZnVuY3Rpb24gb3RzdVVtYnJhbChoaXN0LHRvdGFsKXsKICB2YXIgc3VtPTAsaTsgZm9yKGk9MDtpPDI1NjtpKyspeyBzdW0rPWkqaGlzdFtpXTsgfQogIHZhciBzdW1CPTAsd0I9MCxiZXN0PTAsdGhyPTEyNzsKICBmb3IoaT0wO2k8MjU2O2krKyl7CiAgICB3Qis9aGlzdFtpXTsgaWYod0I9PT0wKXsgY29udGludWU7IH0KICAgIHZhciB3Rj10b3RhbC13QjsgaWYod0Y9PT0wKXsgYnJlYWs7IH0KICAgIHN1bUIrPWkqaGlzdFtpXTsKICAgIHZhciBtQj1zdW1CL3dCLCBtRj0oc3VtLXN1bUIpL3dGLCB2PXdCKndGKihtQi1tRikqKG1CLW1GKTsKICAgIGlmKHY+YmVzdCl7IGJlc3Q9djsgdGhyPWk7IH0KICB9CiAgcmV0dXJuIHRocjsKfQpmdW5jdGlvbiByYW5nb1Byb3llY2Npb24oYXJyLG4sdW1icmFsKXsKICB2YXIgYT0tMSxiPS0xLGk7CiAgZm9yKGk9MDtpPG47aSsrKXsgaWYoYXJyW2ldPj11bWJyYWwpeyBpZihhPDApeyBhPWk7IH0gYj1pOyB9IH0KICBpZihhPDB8fGI8PWEpeyByZXR1cm4gbnVsbDsgfQogIHJldHVybiBbYSxiXTsKfQovKiA9PT09PT09PT09PT0gZGV0ZWNjaW9uIFJFQUwgZGVsIGRvY3VtZW50bzogNCBlc3F1aW5hcyA9PT09PT09PT09PT0gKi8KZnVuY3Rpb24gZXRpcXVldGFDb21wb25lbnRlcyhtYXNrLCB3LCBoKXsKICB2YXIgbGFiPW5ldyBJbnQzMkFycmF5KHcqaCksIHBpbGE9bmV3IEludDMyQXJyYXkodypoKTsKICB2YXIgbWVqb3I9e3RhbTowLGlkOjB9LCBpZD0wLCBpOwogIGZvcihpPTA7aTx3Kmg7aSsrKXsKICAgIGlmKG1hc2tbaV0mJiFsYWJbaV0pewogICAgICBpZCsrOyB2YXIgc3A9MCwgdGFtPTA7CiAgICAgIHBpbGFbc3ArK109aTsgbGFiW2ldPWlkOwogICAgICB3aGlsZShzcD4wKXsKICAgICAgICB2YXIgcD1waWxhWy0tc3BdOyB0YW0rKzsKICAgICAgICB2YXIgeD1wJXcsIHk9KHAteCkvdzsKICAgICAgICBpZih4PjAmJm1hc2tbcC0xXSYmIWxhYltwLTFdKXsgbGFiW3AtMV09aWQ7IHBpbGFbc3ArK109cC0xOyB9CiAgICAgICAgaWYoeDx3LTEmJm1hc2tbcCsxXSYmIWxhYltwKzFdKXsgbGFiW3ArMV09aWQ7IHBpbGFbc3ArK109cCsxOyB9CiAgICAgICAgaWYoeT4wJiZtYXNrW3Atd10mJiFsYWJbcC13XSl7IGxhYltwLXddPWlkOyBwaWxhW3NwKytdPXAtdzsgfQogICAgICAgIGlmKHk8aC0xJiZtYXNrW3Ard10mJiFsYWJbcCt3XSl7IGxhYltwK3ddPWlkOyBwaWxhW3NwKytdPXArdzsgfQogICAgICB9CiAgICAgIGlmKHRhbT5tZWpvci50YW0peyBtZWpvcj17dGFtOnRhbSxpZDppZH07IH0KICAgIH0KICB9CiAgcmV0dXJuIHtsYWI6bGFiLCBtZWpvcjptZWpvcn07Cn0KZnVuY3Rpb24gZXNxdWluYXNEZU1hc2NhcmEobGFiLCBpZCwgdywgaCl7CiAgdmFyIHRsPW51bGwsdHI9bnVsbCxicj1udWxsLGJsPW51bGwsIHgseSxwOwogIGZvcih5PTA7eTxoO3krKyl7CiAgICBmb3IoeD0wO3g8dzt4KyspewogICAgICBwPXkqdyt4OwogICAgICBpZihsYWJbcF0hPT1pZCl7IGNvbnRpbnVlOyB9CiAgICAgIHZhciBzPXgreSwgZDI9eC15OwogICAgICBpZighdGx8fHM8dGwucyl7IHRsPXt4OngseTp5LHM6c307IH0KICAgICAgaWYoIWJyfHxzPmJyLnMpeyBicj17eDp4LHk6eSxzOnN9OyB9CiAgICAgIGlmKCF0cnx8ZDI+dHIuZCl7IHRyPXt4OngseTp5LGQ6ZDJ9OyB9CiAgICAgIGlmKCFibHx8ZDI8YmwuZCl7IGJsPXt4OngseTp5LGQ6ZDJ9OyB9CiAgICB9CiAgfQogIHJldHVybiB7dGw6dGwsdHI6dHIsYnI6YnIsYmw6Ymx9Owp9CmZ1bmN0aW9uIGFyZWFRdWFkKHEpewogIGlmKCFxfHwhcS50bHx8IXEudHJ8fCFxLmJyfHwhcS5ibCl7IHJldHVybiAwOyB9CiAgdmFyIHB0cz1bcS50bCxxLnRyLHEuYnIscS5ibF0sIGE9MCwgaTsKICBmb3IoaT0wO2k8NDtpKyspeyB2YXIgcD1wdHNbaV0sIHI9cHRzWyhpKzEpJTRdOyBhKz1wLngqci55LXIueCpwLnk7IH0KICByZXR1cm4gTWF0aC5hYnMoYSkvMjsKfQpmdW5jdGlvbiBxdWFkVmFsaWRvKHEsIGR3LCBkaCl7CiAgaWYoIXF8fCFxLnRsfHwhcS50cnx8IXEuYnJ8fCFxLmJsKXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidmb3JtYSd9OyB9CiAgdmFyIHB0cz1bcS50bCxxLnRyLHEuYnIscS5ibF0sIGksIHNpZz0wOwogIGZvcihpPTA7aTw0O2krKyl7CiAgICB2YXIgYT1wdHNbaV0sIGI9cHRzWyhpKzEpJTRdLCBjPXB0c1soaSsyKSU0XTsKICAgIHZhciBjcj0oYi54LWEueCkqKGMueS1iLnkpLShiLnktYS55KSooYy54LWIueCk7CiAgICBpZihNYXRoLmFicyhjcik8MC41KXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidmb3JtYSd9OyB9CiAgICB2YXIgcz1jcj4wPzE6LTE7CiAgICBpZihzaWc9PT0wKXsgc2lnPXM7IH0gZWxzZSBpZihzIT09c2lnKXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidmb3JtYSd9OyB9CiAgfQogIGZ1bmN0aW9uIGRzdChhLGIpeyB2YXIgZHg9YS54LWIueCwgZHk9YS55LWIueTsgcmV0dXJuIE1hdGguc3FydChkeCpkeCtkeSpkeSk7IH0KICB2YXIgYXI9ZHN0KHEudGwscS50ciksIGFiPWRzdChxLnRyLHEuYnIpLCBhaT1kc3QocS5icixxLmJsKSwgYXo9ZHN0KHEuYmwscS50bCk7CiAgdmFyIG1uPU1hdGgubWluKGFyLGFiLGFpLGF6KTsKICBpZihtbjxNYXRoLm1heChkdyxkaCkqMC4wOSl7IHJldHVybiB7b2s6ZmFsc2UsIG1vdGl2bzoncGVxdWVubyd9OyB9CiAgdmFyIGZyPWFyZWFRdWFkKHEpLyhkdypkaCk7CiAgaWYoZnI+MC45NCl7IHJldHVybiB7b2s6ZmFsc2UsIG1vdGl2bzonZm9ybWEnfTsgfQogIHZhciBhc3A9KGFyK2FpKS9NYXRoLm1heCgxLChhYitheikpOwogIGlmKGFzcDwwLjQ1fHxhc3A+Mi41KXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidmb3JtYSd9OyB9CiAgaWYoZnI8MC4xMCl7IHJldHVybiB7b2s6ZmFsc2UsIG1vdGl2bzoncGVxdWVubycsIGZyYWM6ZnJ9OyB9CiAgcmV0dXJuIHtvazp0cnVlLCBmcmFjOmZyLCBhc3A6YXNwfTsKfQpmdW5jdGlvbiBuaXRvRGUobHVtLCBkdywgZGgsIGNhamEpewogIHZhciB4MD0xLHkwPTEseDE9ZHctMSx5MT1kaC0xOwogIGlmKGNhamEpeyB4MD1NYXRoLm1heCgxLGNhamEueCsxKTsgeTA9TWF0aC5tYXgoMSxjYWphLnkrMSk7IHgxPU1hdGgubWluKGR3LTEsY2FqYS54K2NhamEudy0xKTsgeTE9TWF0aC5taW4oZGgtMSxjYWphLnkrY2FqYS5oLTEpOyB9CiAgdmFyIHM9MCxzMj0wLGs9MCx4LHk7CiAgZm9yKHk9eTA7eTx5MTt5KyspewogICAgZm9yKHg9eDA7eDx4MTt4KyspewogICAgICB2YXIgcD15KmR3K3g7CiAgICAgIHZhciBscD00Kmx1bVtwXS1sdW1bcC0xXS1sdW1bcCsxXS1sdW1bcC1kd10tbHVtW3ArZHddOwogICAgICBzKz1scDsgczIrPWxwKmxwOyBrKys7CiAgICB9CiAgfQogIGlmKCFrKXsgcmV0dXJuIHt2OjB9OyB9CiAgdmFyIG09cy9rOwogIHJldHVybiB7djooczIvayktbSptfTsKfQpmdW5jdGlvbiBmcmFjY2lvbkJsYW5jbyhsdW0sIGR3LCBkaCwgY2FqYSl7CiAgdmFyIHgwPTAseTA9MCx4MT1kdyx5MT1kaCxrPTAsYj0wLHgseTsKICBpZihjYWphKXsgeDA9TWF0aC5tYXgoMCxjYWphLngpOyB5MD1NYXRoLm1heCgwLGNhamEueSk7IHgxPU1hdGgubWluKGR3LGNhamEueCtjYWphLncpOyB5MT1NYXRoLm1pbihkaCxjYWphLnkrY2FqYS5oKTsgfQogIGZvcih5PXkwO3k8eTE7eSsrKXsgZm9yKHg9eDA7eDx4MTt4KyspeyBrKys7IGlmKGx1bVt5KmR3K3hdPj0yNDYpeyBiKys7IH0gfSB9CiAgcmV0dXJuIGs/KGIvayk6MDsKfQpmdW5jdGlvbiBtZWRpYW5hTnVtKGEpewogIGlmKCFhfHwhYS5sZW5ndGgpeyByZXR1cm4gMDsgfQogIHZhciBiPWEuc2xpY2UoKS5zb3J0KGZ1bmN0aW9uKHgseSl7IHJldHVybiB4LXk7IH0pOwogIHJldHVybiBiW01hdGguZmxvb3IoYi5sZW5ndGgvMildOwp9CmZ1bmN0aW9uIG1lZGlhbmFRdWFkKGhpc3QpewogIGlmKCFoaXN0fHwhaGlzdC5sZW5ndGgpeyByZXR1cm4gbnVsbDsgfQogIHZhciBLPVsndGwnLCd0cicsJ2JyJywnYmwnXSwgcmVzPXt9LCBpLCBrLCB4cywgeXM7CiAgZm9yKGs9MDtrPEsubGVuZ3RoO2srKyl7CiAgICB4cz1bXTsgeXM9W107CiAgICBmb3IoaT0wO2k8aGlzdC5sZW5ndGg7aSsrKXsgaWYoaGlzdFtpXSYmaGlzdFtpXVtLW2tdXSl7IHhzLnB1c2goaGlzdFtpXVtLW2tdXS54KTsgeXMucHVzaChoaXN0W2ldW0tba11dLnkpOyB9IH0KICAgIGlmKCF4cy5sZW5ndGgpeyByZXR1cm4gbnVsbDsgfQogICAgcmVzW0tba11dPXt4Om1lZGlhbmFOdW0oeHMpLCB5Om1lZGlhbmFOdW0oeXMpfTsKICB9CiAgcmV0dXJuIHJlczsKfQpmdW5jdGlvbiBxdWFkRXN0YWJsZShoaXN0KXsKICB2YXIgbWVkPW1lZGlhbmFRdWFkKGhpc3QpLCBLPVsndGwnLCd0cicsJ2JyJywnYmwnXSwgaSwgazsKICBpZighbWVkfHwhaGlzdHx8aGlzdC5sZW5ndGg8NCl7IHJldHVybiBmYWxzZTsgfQogdmFyIHRvbD0wLjAyKk1hdGgubWF4KGhpc3RbMF0udnd8fDY0MCwgaGlzdFswXS52aHx8NDgwKTsKICBmb3Ioaz0wO2s8Sy5sZW5ndGg7aysrKXsKICAgIGZvcihpPU1hdGgubWF4KDAsaGlzdC5sZW5ndGgtNCk7aTxoaXN0Lmxlbmd0aDtpKyspewogICAgICB2YXIgcT1oaXN0W2ldJiZoaXN0W2ldW0tba11dOwogICAgICBpZighcXx8IW1lZFtLW2tdXSl7IHJldHVybiBmYWxzZTsgfQogICAgICB2YXIgZHg9cS54LW1lZFtLW2tdXS54LCBkeT1xLnktbWVkW0tba11dLnk7CiAgICAgIGlmKE1hdGguc3FydChkeCpkeCtkeSpkeSk+dG9sKXsgcmV0dXJuIGZhbHNlOyB9CiAgICB9CiAgfQogIHJldHVybiB0cnVlOwp9CmZ1bmN0aW9uIGRldGVjdGFyRG9jUXVhZCh2KXsKICB0cnl7CiAgICB2YXIgRD16eURldCgpOwogICAgdmFyIHZ3PXYudmlkZW9XaWR0aHx8MCwgdmg9di52aWRlb0hlaWdodHx8MDsKICAgIGlmKCF2d3x8IXZoKXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciBkdz0xNjAsIGRoPU1hdGgucm91bmQoZHcqdmgvdncpOwogICAgaWYoZGg8OCl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgYz1ELmN2UTsgaWYoIWMpeyBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOyBELmN2UT1jOyB9CiAgICBpZihjLndpZHRoIT09ZHd8fGMuaGVpZ2h0IT09ZGgpeyBjLndpZHRoPWR3OyBjLmhlaWdodD1kaDsgfQogICAgdmFyIGc9Yy5nZXRDb250ZXh0KCcyZCcpOyBpZighZyl7IHJldHVybiBudWxsOyB9CiAgICBnLmRyYXdJbWFnZSh2LDAsMCxkdyxkaCk7CiAgICB2YXIgZD1nLmdldEltYWdlRGF0YSgwLDAsZHcsZGgpLmRhdGEsIG49ZHcqZGgsIGksIHgsIHk7CiAgICB2YXIgbHVtPW5ldyBVaW50OEFycmF5KG4pLCBzdW09MDsKICAgIGZvcihpPTA7aTxuO2krKyl7IGx1bVtpXT0oZFtpKjRdKjMrZFtpKjQrMV0qNCtkW2kqNCsyXSk+PjM7IHN1bSs9bHVtW2ldOyB9CiAgICB2YXIgbHV6PXN1bS9uOwogICAgdmFyIGxiPW5ldyBVaW50OEFycmF5KG4pOwogICAgZm9yKHk9MTt5PGRoLTE7eSsrKXsgZm9yKHg9MTt4PGR3LTE7eCsrKXsgdmFyIHBwPXkqZHcreDsgbGJbcHBdPShsdW1bcHBdKjQrbHVtW3BwLTFdK2x1bVtwcCsxXStsdW1bcHAtZHddK2x1bVtwcCtkd10pPj4zOyB9IH0KICAgIHZhciBoaXN0PW5ldyBJbnQzMkFycmF5KDI1Nik7IGZvcihpPTA7aTxuO2krKyl7IGhpc3RbbGJbaV1dKys7IH0KICAgIHZhciB0aHI9b3RzdVVtYnJhbChoaXN0LG4pOwogICAgdmFyIG1hc2s9bmV3IFVpbnQ4QXJyYXkobiksIHRvdD0wOwogICAgZm9yKGk9MDtpPG47aSsrKXsgdmFyIHYxPShsYltpXT50aHIpPzE6MDsgbWFza1tpXT12MTsgdG90Kz12MTsgfQogICAgaWYodG90PG4qMC4wMyl7IHJldHVybiBudWxsOyB9CiAgICBpZih0b3Q+biowLjk2NSl7CiAgICAgIHZhciBudDA9bml0b0RlKGx1bSxkdyxkaCxudWxsKTsKICAgICAgcmV0dXJuIHtsbGVubzp0cnVlLCBsdXo6bHV6LCBuaXRvOm50MC52LCBibGFuY286ZnJhY2Npb25CbGFuY28obHVtLGR3LGRoLG51bGwpLCB2dzp2dywgdmg6dmh9OwogICAgfQogICAgdmFyIGNjPWV0aXF1ZXRhQ29tcG9uZW50ZXMobWFzayxkdyxkaCk7CiAgICBpZighY2MubWVqb3IuaWR8fGNjLm1lam9yLnRhbTxuKjAuMDQpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIHE9ZXNxdWluYXNEZU1hc2NhcmEoY2MubGFiLGNjLm1lam9yLmlkLGR3LGRoKTsKICAgIGlmKCFxLnRsfHwhcS50cnx8IXEuYnJ8fCFxLmJsKXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciB2YWw9cXVhZFZhbGlkbyhxLGR3LGRoKTsKICAgIHZhciB4MD1NYXRoLm1heCgwLE1hdGgubWluKHEudGwueCxxLmJsLngpKSwgeDE9TWF0aC5taW4oZHcsTWF0aC5tYXgocS50ci54LHEuYnIueCkpOwogICAgdmFyIHkwPU1hdGgubWF4KDAsTWF0aC5taW4ocS50bC55LHEudHIueSkpLCB5MT1NYXRoLm1pbihkaCxNYXRoLm1heChxLmJsLnkscS5ici55KSk7CiAgICB2YXIgY2FqYT17eDp4MCx5OnkwLHc6TWF0aC5tYXgoMSx4MS14MCksaDpNYXRoLm1heCgxLHkxLXkwKX07CiAgICB2YXIgbnQ9bml0b0RlKGx1bSxkdyxkaCxjYWphKTsKICAgIHZhciBibGE9ZnJhY2Npb25CbGFuY28obHVtLGR3LGRoLGNhamEpOwogICAgdmFyIHN4PXZ3L2R3LCBzeT12aC9kaDsKICAgIGZ1bmN0aW9uIGVzYyhwKXsgcmV0dXJuIHt4OnAueCpzeCwgeTpwLnkqc3l9OyB9CiAgICB2YXIgcmVzPXt0bDplc2MocS50bCksIHRyOmVzYyhxLnRyKSwgYnI6ZXNjKHEuYnIpLCBibDplc2MocS5ibCksIGx1ejpsdXosIG5pdG86bnQudiwgYmxhbmNvOmJsYSwgdnc6dncsIHZoOnZofTsKICAgIGlmKCF2YWwub2speyByZXMuZGVzY2FydGFkbz12YWwubW90aXZvOyByZXR1cm4gcmVzOyB9CiAgICByZXMuZnJhYz12YWwuZnJhYzsKICAgIHJldHVybiByZXM7CiAgfWNhdGNoKGUpeyByZXR1cm4gbnVsbDsgfQp9CmZ1bmN0aW9uIGRldGVjdGFyRG9jQm94KHYpewogIHRyeXsKICAgIHZhciBEPXp5RGV0KCk7CiAgICB2YXIgYz1ELmN2RG9jOwogICAgaWYoIWMpeyBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOyBELmN2RG9jPWM7IH0KICAgIHZhciBkdz0xMjgsIGRoPU1hdGgubWF4KDgsTWF0aC5yb3VuZCgxMjgqKCh2LnZpZGVvSGVpZ2h0fHwzKS8oKHYudmlkZW9XaWR0aHx8NCkqMS4wKSkpKTsKICAgIGlmKGMud2lkdGghPT1kd3x8Yy5oZWlnaHQhPT1kaCl7IGMud2lkdGg9ZHc7IGMuaGVpZ2h0PWRoOyB9CiAgICB2YXIgZz1jLmdldENvbnRleHQoJzJkJyk7IGlmKCFnKXsgcmV0dXJuIG51bGw7IH0KICAgIGcuZHJhd0ltYWdlKHYsMCwwLGR3LGRoKTsKICAgIHZhciBkPWcuZ2V0SW1hZ2VEYXRhKDAsMCxkdyxkaCkuZGF0YSwgbj1kdypkaDsKICAgIHZhciBoaXN0PW5ldyBJbnQzMkFycmF5KDI1NiksIGx1bT1uZXcgVWludDhBcnJheShuKSwgaSx4LHk7CiAgICBmb3IoaT0wO2k8bjtpKyspeyB2YXIgcj1kW2kqNF0sIGdnPWRbaSo0KzFdLCBiPWRbaSo0KzJdOyBsdW1baV09KHIqMytnZyo0K2IpPj4zOyBoaXN0W2x1bVtpXV0rKzsgfQogICAgdmFyIHRocj1vdHN1VW1icmFsKGhpc3Qsbik7CiAgICB2YXIgZmlsYXM9bmV3IEludDMyQXJyYXkoZGgpLCBjb2xzPW5ldyBJbnQzMkFycmF5KGR3KSwgdG90PTA7CiAgICBmb3IoeT0wO3k8ZGg7eSsrKXsgZm9yKHg9MDt4PGR3O3grKyl7IGlmKGx1bVt5KmR3K3hdPnRocil7IGZpbGFzW3ldKys7IGNvbHNbeF0rKzsgdG90Kys7IH0gfSB9CiAgICBpZih0b3Q8biowLjA0fHx0b3Q+biowLjk4NSl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgcmY9cmFuZ29Qcm95ZWNjaW9uKGZpbGFzLGRoLE1hdGgubWF4KDIsTWF0aC5yb3VuZChkdyowLjE4KSkpOwogICAgdmFyIHJjPXJhbmdvUHJveWVjY2lvbihjb2xzLGR3LE1hdGgubWF4KDIsTWF0aC5yb3VuZChkaCowLjE4KSkpOwogICAgaWYoIXJmfHwhcmMpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIHN4PSh2LnZpZGVvV2lkdGh8fDY0MCkvZHcsIHN5PSh2LnZpZGVvSGVpZ2h0fHw0ODApL2RoOwogICAgdmFyIGJ4PXJjWzBdKnN4LCBieT1yZlswXSpzeSwgYnc9KHJjWzFdKzEtcmNbMF0pKnN4LCBiaD0ocmZbMV0rMS1yZlswXSkqc3k7CiAgICBpZihidzw4fHxiaDw4KXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciBzdW1hPTAsIGkyOwogICAgZm9yKGkyPTA7aTI8bjtpMisrKXsgc3VtYSs9bHVtW2kyXTsgfQogICAgdmFyIGx1ej1zdW1hL247CiAgICB2YXIgc3VtVj0wLCBzdW1WMj0wLCBuMj0wLCB4MiwgeTI7CiAgICBmb3IoeTI9MTt5MjxkaC0xO3kyKyspewogICAgICBmb3IoeDI9MTt4Mjxkdy0xO3gyKyspewogICAgICAgIHZhciBpaT15Mipkdyt4MjsKICAgICAgICB2YXIgbGFwPTQqbHVtW2lpXS1sdW1baWktMV0tbHVtW2lpKzFdLWx1bVtpaS1kd10tbHVtW2lpK2R3XTsKICAgICAgICBzdW1WKz1sYXA7IHN1bVYyKz1sYXAqbGFwOyBuMisrOwogICAgICB9CiAgICB9CiAgICB2YXIgbWVkaWE9c3VtVi9NYXRoLm1heCgxLG4yKTsKICAgIHZhciB2YXJMPShzdW1WMi9NYXRoLm1heCgxLG4yKSktbWVkaWEqbWVkaWE7CiAgICByZXR1cm4ge3g6YngsIHk6YnksIHc6YncsIGg6YmgsIGx1ejpsdXosIG5pdG86KHZhckw+PTQwKSwgZm9jbzpNYXRoLnJvdW5kKHZhckwpfTsKICB9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9Cn0KZnVuY3Rpb24gY2VudHJvRGUocHVudG9zKXsKICB2YXIgc3g9MCwgc3k9MCwgaTsKICBmb3IoaT0wO2k8cHVudG9zLmxlbmd0aDtpKyspeyBzeCs9cHVudG9zW2ldLng7IHN5Kz1wdW50b3NbaV0ueTsgfQogIHJldHVybiB7eDpzeC9wdW50b3MubGVuZ3RoLCB5OnN5L3B1bnRvcy5sZW5ndGh9Owp9CmZ1bmN0aW9uIGVhckRlKHB1bnRvcyl7CiAgaWYoIXB1bnRvc3x8cHVudG9zLmxlbmd0aDw2KXsgcmV0dXJuIDE7IH0KICBmdW5jdGlvbiBkMihhLGIpeyB2YXIgZHg9YS54LWIueCwgZHk9YS55LWIueTsgcmV0dXJuIE1hdGguc3FydChkeCpkeCtkeSpkeSk7IH0KICB2YXIgaD1kMihwdW50b3NbMF0scHVudG9zWzNdKTsKICBpZihoPDFlLTYpeyByZXR1cm4gMTsgfQogIHJldHVybiAoZDIocHVudG9zWzFdLHB1bnRvc1s1XSkrZDIocHVudG9zWzJdLHB1bnRvc1s0XSkpLygyKmgpOwp9CmZ1bmN0aW9uIGV2YWx1YUNhcmEoaW5mbyl7CiAgdmFyIHI9e3Zpc3RhOnRydWUsIG9rOmZhbHNlLCB0YW06J2JpZW4nLCBtb3Rpdm86JycsIGNvZDonJ307CiAgaWYoaW5mby5sdXo8NTUpeyByLmNvZD0nbHV6Jzsgci5tb3Rpdm89J1BPQ0EgTFVaOiBwb24gdHUgY2FyYSBoYWNpYSBsYSBsdXogbyBlbmNpZW5kZSB1bmEgbGFtcGFyYS4nOyByZXR1cm4gcjsgfQogIGlmKGluZm8ubml0bzwxOCl7IHIuY29kPSduaXRvJzsgci5tb3Rpdm89J05vIHNlIHZlIE5JVElETzogc29zdFx1MDBFOW4gZWwgdGVsZWZvbm8gZmlybWUgeSBlc3BlcmEgZWwgZW5mb3F1ZS4nOyByZXR1cm4gcjsgfQogIGlmKGluZm8udGFtPDAuMzgpeyByLnRhbT0nbGVqb3MnOyByLmNvZD0nbGVqb3MnOyByLm1vdGl2bz0nQUNFUkNBVEU6IHR1IGNhcmEgc2UgdmUgbXV5IHBlcXVlXHUwMEYxYSBlbiBlbCBvdmFsby4nOyByZXR1cm4gcjsgfQogIGlmKGluZm8udGFtPjAuODYpeyByLnRhbT0nY2VyY2EnOyByLmNvZD0nY2VyY2EnOyByLm1vdGl2bz0nQUxFSkFURSB1biBwb2NvIHBhcmEgcXVlIHR1IGNhcmEgcXVlcGEgZW50ZXJhIGVuIGVsIG92YWxvLic7IHJldHVybiByOyB9CiAgaWYoTWF0aC5hYnMoaW5mby5meC0wLjUpPjAuMTN8fGluZm8uZnk8MC4zNnx8aW5mby5meT4wLjY4KXsgci5jb2Q9J2Z1ZXJhJzsgci5tb3Rpdm89J0NlbnRyYSB0dSBjYXJhIGRlbnRybyBkZWwgT1ZBTE8sIG1pcmFuZG8gYSBsYSBjYW1hcmEuJzsgcmV0dXJuIHI7IH0KICBpZihNYXRoLmFicyhpbmZvLnJvbGwpPjE0KXsgci5jb2Q9J3JvbGwnOyByLm1vdGl2bz0nRW5kZXJlemEgbGEgY2FiZXphOiBubyBsYSBpbmNsaW5lcyBhIGxvcyBsYWRvcy4nOyByZXR1cm4gcjsgfQogIGlmKE1hdGguYWJzKGluZm8ueWF3KT4wLjIwKXsgci5jb2Q9J3lhdyc7IHIubW90aXZvPSdNaXJhIERFIEZSRU5URSBhIGxhIGNhbWFyYSwgbm8gZGUgbGFkby4nOyByZXR1cm4gcjsgfQogIGlmKGluZm8ub2pvczwwLjEzKXsgci5jb2Q9J29qb3MnOyByLm1vdGl2bz0nQWJyZSBsb3Mgb2pvcyB5IG1pcmEgZmlqbyBhIGxhIGNhbWFyYS4nOyByZXR1cm4gcjsgfQogIHIub2s9dHJ1ZTsgci5tb3Rpdm89J1BlcmZlY3RvOiBzb3N0XHUwMEU5biBsYSBwb3NpY2lvbi4uLic7CiAgcmV0dXJuIHI7Cn0KZnVuY3Rpb24gbml0b0RlUmdiYShkYXRvcywgZHcsIGRoLCBjYWphKXsKICB2YXIgeDA9TWF0aC5tYXgoMSxjYWphLngrMSksIHkwPU1hdGgubWF4KDEsY2FqYS55KzEpOwogIHZhciB4MT1NYXRoLm1pbihkdy0xLGNhamEueCtjYWphLnctMSksIHkxPU1hdGgubWluKGRoLTEsY2FqYS55K2NhamEuaC0xKTsKICB2YXIgcz0wLHMyPTAsaz0wLHgseTsKICBmb3IoeT15MDt5PHkxO3krKyl7CiAgICBmb3IoeD14MDt4PHgxO3grKyl7CiAgICAgIHZhciBwPXkqZHcreDsKICAgICAgdmFyIGwxPShkYXRvc1twKjRdKjMrZGF0b3NbcCo0KzFdKjQrZGF0b3NbcCo0KzJdKT4+MzsKICAgICAgdmFyIGwyPShkYXRvc1socC0xKSo0XSozK2RhdG9zWyhwLTEpKjQrMV0qNCtkYXRvc1socC0xKSo0KzJdKT4+MzsKICAgICAgdmFyIGwzPShkYXRvc1socCsxKSo0XSozK2RhdG9zWyhwKzEpKjQrMV0qNCtkYXRvc1socCsxKSo0KzJdKT4+MzsKICAgICAgdmFyIGw0PShkYXRvc1socC1kdykqNF0qMytkYXRvc1socC1kdykqNCsxXSo0K2RhdG9zWyhwLWR3KSo0KzJdKT4+MzsKICAgICAgdmFyIGw1PShkYXRvc1socCtkdykqNF0qMytkYXRvc1socCtkdykqNCsxXSo0K2RhdG9zWyhwK2R3KSo0KzJdKT4+MzsKICAgICAgdmFyIGxwPTQqbDEtbDItbDMtbDQtbDU7CiAgICAgIHMrPWxwOyBzMis9bHAqbHA7IGsrKzsKICAgIH0KICB9CiAgaWYoIWspeyByZXR1cm4gMDsgfQogIHZhciBtPXMvazsKICByZXR1cm4gKHMyL2spLW0qbTsKfQpmdW5jdGlvbiBidXNjYXJDYXJhVml2YSh2LCBjYil7CiAgdHJ5ewogICAgaWYoIShXLmZhY2VhcGkmJlcuZmFjZWFwaS5uZXRzJiZXLmZhY2VhcGkubmV0cy50aW55RmFjZURldGVjdG9yJiZXLmZhY2VhcGkuVGlueUZhY2VEZXRlY3Rvck9wdGlvbnMpKXsgY2IobnVsbCk7IHJldHVybjsgfQogICAgdmFyIEQ9enlEZXQoKTsKICAgIHZhciB2dz12LnZpZGVvV2lkdGh8fDY0MCwgdmg9di52aWRlb0hlaWdodHx8NDgwOwogICAgdmFyIGR3PTIyNCwgZGg9TWF0aC5tYXgoODAsTWF0aC5yb3VuZChkdyp2aC92dykpOwogICAgdmFyIGM9RC5jdkNhcmE7CiAgICBpZighYyl7IGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7IEQuY3ZDYXJhPWM7IH0KICAgIGlmKGMud2lkdGghPT1kd3x8Yy5oZWlnaHQhPT1kaCl7IGMud2lkdGg9ZHc7IGMuaGVpZ2h0PWRoOyB9CiAgICB2YXIgZz1jLmdldENvbnRleHQoJzJkJyk7IGlmKCFnKXsgY2IobnVsbCk7IHJldHVybjsgfQogICAgZy5kcmF3SW1hZ2UodiwwLDAsZHcsZGgpOwogICAgdmFyIGRhdG9zPW51bGw7CiAgICB0cnl7IGRhdG9zPWcuZ2V0SW1hZ2VEYXRhKDAsMCxkdyxkaCkuZGF0YTsgfWNhdGNoKGUpeyBkYXRvcz1udWxsOyB9CiAgICB2YXIgb3B0PW5ldyBXLmZhY2VhcGkuVGlueUZhY2VEZXRlY3Rvck9wdGlvbnMoe2lucHV0U2l6ZToyMjQsIHNjb3JlVGhyZXNob2xkOjAuNDV9KTsKICAgIFcuZmFjZWFwaS5kZXRlY3RTaW5nbGVGYWNlKGMsb3B0KS53aXRoRmFjZUxhbmRtYXJrcygpLndpdGhGYWNlRGVzY3JpcHRvcigpLnRoZW4oZnVuY3Rpb24ocil7CiAgICAgIHRyeXsKICAgICAgICBpZighcnx8IXIuZGV0ZWN0aW9uKXsgY2Ioe3Zpc3RhOmZhbHNlLCBvazpmYWxzZSwgdDpEYXRlLm5vdygpfSk7IHJldHVybjsgfQogICAgICAgIHZhciBiPXIuZGV0ZWN0aW9uLmJveDsKICAgICAgICB2YXIgZng9KGIueCtiLndpZHRoLzIpL2R3LCBmeT0oYi55K2IuaGVpZ2h0LzIpL2RoOwogICAgICAgIHZhciB0YW09Yi5oZWlnaHQvZGg7CiAgICAgICAgdmFyIHJvbGw9MCwgeWF3PTAsIG9qb3M9MTsKICAgICAgICBpZihyLmxhbmRtYXJrcyl7CiAgICAgICAgICB2YXIgTD1yLmxhbmRtYXJrcy5nZXRMZWZ0RXllKCksIFI9ci5sYW5kbWFya3MuZ2V0UmlnaHRFeWUoKSwgTj1yLmxhbmRtYXJrcy5nZXROb3NlKCk7CiAgICAgICAgICBpZihMJiZSJiZMLmxlbmd0aD49NCYmUi5sZW5ndGg+PTQpewogICAgICAgICAgICB2YXIgbGM9Y2VudHJvRGUoTCksIHJjPWNlbnRyb0RlKFIpOwogICAgICAgICAgICByb2xsPU1hdGguYXRhbjIocmMueS1sYy55LCByYy54LWxjLngpKjE4MC9NYXRoLlBJOwogICAgICAgICAgICB2YXIgbXg9KGxjLngrcmMueCkvMjsKICAgICAgICAgICAgaWYoTiYmTi5sZW5ndGg+NCl7IHlhdz0oTls0XS54LW14KS9NYXRoLm1heCgxLGIud2lkdGgpOyB9CiAgICAgICAgICAgIG9qb3M9TWF0aC5taW4oZWFyRGUoTCksIGVhckRlKFIpKTsKICAgICAgICAgIH0KICAgICAgICB9CiAgICAgICAgdmFyIGNhamE9e3g6TWF0aC5yb3VuZChiLngqdncvZHcpLCB5Ok1hdGgucm91bmQoYi55KnZoL2RoKSwgdzpNYXRoLnJvdW5kKGIud2lkdGgqdncvZHcpLCBoOk1hdGgucm91bmQoYi5oZWlnaHQqdmgvZGgpfTsKICAgICAgICBjYWphLng9TWF0aC5tYXgoMCx2dy1jYWphLngtY2FqYS53KTsKICAgICAgICB2YXIgbHV6PTAsIG5pdG89MDsKICAgICAgICBpZihkYXRvcyl7CiAgICAgICAgICB2YXIgcngwPU1hdGgubWF4KDAsTWF0aC5yb3VuZChiLngpKSwgcnkwPU1hdGgubWF4KDAsTWF0aC5yb3VuZChiLnkpKTsKICAgICAgICAgIHZhciByeDE9TWF0aC5taW4oZHcsTWF0aC5yb3VuZChiLngrYi53aWR0aCkpLCByeTE9TWF0aC5taW4oZGgsTWF0aC5yb3VuZChiLnkrYi5oZWlnaHQpKTsKICAgICAgICAgIHZhciBzPTAsaz0wLHgseTsKICAgICAgICAgIGZvcih5PXJ5MDt5PHJ5MTt5KyspeyBmb3IoeD1yeDA7eDxyeDE7eCsrKXsgcys9KGRhdG9zWyh5KmR3K3gpKjRdKjMrZGF0b3NbKHkqZHcreCkqNCsxXSo0K2RhdG9zWyh5KmR3K3gpKjQrMl0pPj4zOyBrKys7IH0gfQogICAgICAgICAgbHV6PWs/KHMvayk6MDsKICAgICAgICAgIG5pdG89KHJ4MT5yeDArMiYmcnkxPnJ5MCsyKT9uaXRvRGVSZ2JhKGRhdG9zLGR3LGRoLHt4OnJ4MCx5OnJ5MCx3OnJ4MS1yeDAsaDpyeTEtcnkwfSk6MDsKICAgICAgICB9CiAgICAgICAgdmFyIGRlPWV2YWx1YUNhcmEoe2Z4OmZ4LGZ5OmZ5LHRhbTp0YW0scm9sbDpyb2xsLHlhdzp5YXcsb2pvczpvam9zLGx1ejpsdXosbml0bzpuaXRvfSk7CiAgICAgICAgY2Ioe3Zpc3RhOnRydWUsIG9rOmRlLm9rLCBjb2Q6ZGUuY29kLCBtb3Rpdm86ZGUubW90aXZvLCB0YW06ZGUudGFtLCBmeDpmeCwgZnk6ZnksIGNhamE6Y2FqYSwgbHV6Omx1eiwgbml0bzpuaXRvLCBvam9zOm9qb3MsIHJvbGw6cm9sbCwgeWF3OnlhdywgdDpEYXRlLm5vdygpfSk7CiAgICAgIH1jYXRjaChlKXsgY2IobnVsbCk7IH0KICAgIH0pLmNhdGNoKGZ1bmN0aW9uKCl7IGNiKG51bGwpOyB9KTsKICB9Y2F0Y2goZSl7IGNiKG51bGwpOyB9Cn0KZnVuY3Rpb24gZW5tYXJjYXJWZXJkZShwc0lkLCB2KXsKICAvKiB2MTE6IGNvbnRvcm5vIFBPTElHT05BTCByZWFsIHF1ZSBzaWd1ZSBhbCBkb2N1bWVudG8gKHBzIDIgeSAzKSB5IE9WQUxPIGNvbiBtb3RvciBmYWNpYWwgKHBzIDQpICovCiAgdHJ5ewogICAgdmFyIE9WPXsnMic6J292RicsJzMnOidvdkEnLCc0Jzonb3ZTJ307CiAgICB2YXIgb3ZJZD1PVltwc0lkXTsKICAgIGlmKCFvdklkKXsgcmV0dXJuOyB9CiAgICB2YXIgc3RJZD0ocHNJZD09PScyJyk/J3N0Ric6KChwc0lkPT09JzMnKT8nc3RBJzonc3RWJyk7CiAgICB2YXIgRD16eURldCgpOwogICAgdmFyIHN0PURbcHNJZF07CiAgICBpZighc3QpeyBzdD1EW3BzSWRdPXtjYWphOm51bGwsIHQ6LTFlOSwgZXN0YWRvOicnLCBpdjpudWxsfTsgfQogICAgc3QudDA9RGF0ZS5ub3coKTsgc3QuY2FqYT1udWxsOyBzdC5lc3RhZG89Jyc7IHN0LmF1dG89MDsgc3QuYXV0b0hlY2hvPWZhbHNlOyBzdC5jZD0wOyBzdC5oaXN0PVtdOwogICAgdmFyIHBpbnRhckRvYz1mdW5jdGlvbihjYWphLCBlc3RhZG8pewogICAgICB0cnl7CiAgICAgICAgdmFyIG92PSQob3ZJZCk7IGlmKCFvdil7IHJldHVybjsgfQogICAgICAgIHZhciB2dz0odiYmdi52aWRlb1dpZHRoKXx8MCwgdmg9KHYmJnYudmlkZW9IZWlnaHQpfHwwOwogICAgICAgIGlmKCF2d3x8IXZoKXsgcmV0dXJuOyB9CiAgICAgICAgaWYob3Yud2lkdGghPT12d3x8b3YuaGVpZ2h0IT09dmgpeyBvdi53aWR0aD12dzsgb3YuaGVpZ2h0PXZoOyB9CiAgICAgICAgdmFyIGc9b3YuZ2V0Q29udGV4dCgnMmQnKTsgaWYoIWcpeyByZXR1cm47IH0KICAgICAgICBnLmNsZWFyUmVjdCgwLDAsdncsdmgpOwogICAgICAgIHZhciB4LHksdyxoOwogICAgICAgIGlmKCFjYWphKXsgeD1NYXRoLnJvdW5kKHZ3KjAuMDcpOyB5PU1hdGgucm91bmQodmgqMC4wOSk7IHc9dncteCoyOyBoPXZoLXkqMjsgfQogICAgICAgIGVsc2V7IHg9Y2FqYS54OyB5PWNhamEueTsgdz1jYWphLnc7IGg9Y2FqYS5oOyB9CiAgICAgICAgaWYodzwxMHx8aDwxMCl7IHJldHVybjsgfQogICAgICAgIHZhciBjb2w9KGVzdGFkbz09PSdvaycpPycjM2ZiOTUwJzooKGVzdGFkbz09PSdtYWwnKT8nI2MwMzkyYic6JyNlM2IzNDEnKTsKICAgICAgICBnLnN0cm9rZVN0eWxlPWNvbDsgZy5saW5lV2lkdGg9NTsKICAgICAgICB2YXIgTD1NYXRoLnJvdW5kKE1hdGgubWluKHcsaCkqKGNhamE/MC4xNjowLjE0KSk7CiAgICAgICAgZy5iZWdpblBhdGgoKTsKICAgICAgICBnLm1vdmVUbyh4LHkrTCk7IGcubGluZVRvKHgseSk7IGcubGluZVRvKHgrTCx5KTsKICAgICAgICBnLm1vdmVUbyh4K3ctTCx5KTsgZy5saW5lVG8oeCt3LHkpOyBnLmxpbmVUbyh4K3cseStMKTsKICAgICAgICBnLm1vdmVUbyh4K3cseStoLUwpOyBnLmxpbmVUbyh4K3cseStoKTsgZy5saW5lVG8oeCt3LUwseStoKTsKICAgICAgICBnLm1vdmVUbyh4K0wseStoKTsgZy5saW5lVG8oeCx5K2gpOyBnLmxpbmVUbyh4LHkraC1MKTsKICAgICAgICBnLnN0cm9rZSgpOwogICAgICAgIGcuc2F2ZSgpOwogICAgICAgIGcuZ2xvYmFsQWxwaGE9Y2FqYT8wLjQ1OjAuMjA7CiAgICAgICAgZy5saW5lV2lkdGg9MS42OyBnLnN0cm9rZVJlY3QoeCx5LHcsaCk7CiAgICAgICAgZy5yZXN0b3JlKCk7CiAgICAgIH1jYXRjaChlKXt9CiAgICB9OwogICAgdmFyIHBpbnRhclF1YWQ9ZnVuY3Rpb24ocXVhZCwgZXN0YWRvLCBudW1lcm8pewogICAgICB0cnl7CiAgICAgICAgdmFyIG92PSQob3ZJZCk7IGlmKCFvdil7IHJldHVybjsgfQogICAgICAgIHZhciB2dz0odiYmdi52aWRlb1dpZHRoKXx8MCwgdmg9KHYmJnYudmlkZW9IZWlnaHQpfHwwOwogICAgICAgIGlmKCF2d3x8IXZoKXsgcmV0dXJuOyB9CiAgICAgICAgaWYob3Yud2lkdGghPT12d3x8b3YuaGVpZ2h0IT09dmgpeyBvdi53aWR0aD12dzsgb3YuaGVpZ2h0PXZoOyB9CiAgICAgICAgdmFyIGc9b3YuZ2V0Q29udGV4dCgnMmQnKTsgaWYoIWcpeyByZXR1cm47IH0KICAgICAgICBnLmNsZWFyUmVjdCgwLDAsdncsdmgpOwogICAgICAgIGlmKHF1YWQmJnF1YWQudGwmJnF1YWQudHImJnF1YWQuYnImJnF1YWQuYmwpewogICAgICAgICAgdmFyIGNvbD0oZXN0YWRvPT09J29rJyk/JyMzZmI5NTAnOigoZXN0YWRvPT09J21hbCcpPycjZTY3ZTIyJzonI2UzYjM0MScpOwogICAgICAgICAgdHJ5ewogICAgICAgICAgICBnLmZpbGxTdHlsZT0ncmdiYSgwLDAsMCwwLjQ1KSc7CiAgICAgICAgICAgIGcuYmVnaW5QYXRoKCk7CiAgICAgICAgICAgIGcucmVjdCgwLDAsdncsdmgpOwogICAgICAgICAgICBnLm1vdmVUbyhxdWFkLnRsLngscXVhZC50bC55KTsgZy5saW5lVG8ocXVhZC50ci54LHF1YWQudHIueSk7IGcubGluZVRvKHF1YWQuYnIueCxxdWFkLmJyLnkpOyBnLmxpbmVUbyhxdWFkLmJsLngscXVhZC5ibC55KTsgZy5jbG9zZVBhdGgoKTsKICAgICAgICAgICAgZy5maWxsKCdldmVub2RkJyk7CiAgICAgICAgICB9Y2F0Y2goZUYpeyBnLmZpbGxTdHlsZT0ncmdiYSgwLDAsMCwwLjIyKSc7IGcuZmlsbFJlY3QoMCwwLHZ3LHZoKTsgfQogICAgICAgICAgZy5zdHJva2VTdHlsZT1jb2w7IGcubGluZVdpZHRoPTU7IGcubGluZUpvaW49J3JvdW5kJzsKICAgICAgICAgIGcuYmVnaW5QYXRoKCk7CiAgICAgICAgICBnLm1vdmVUbyhxdWFkLnRsLngscXVhZC50bC55KTsgZy5saW5lVG8ocXVhZC50ci54LHF1YWQudHIueSk7IGcubGluZVRvKHF1YWQuYnIueCxxdWFkLmJyLnkpOyBnLmxpbmVUbyhxdWFkLmJsLngscXVhZC5ibC55KTsgZy5jbG9zZVBhdGgoKTsKICAgICAgICAgIGcuc3Ryb2tlKCk7CiAgICAgICAgICBnLmZpbGxTdHlsZT1jb2w7CiAgICAgICAgICB2YXIgcHRzPVtxdWFkLnRsLHF1YWQudHIscXVhZC5icixxdWFkLmJsXSwgaTsKICAgICAgICAgIGZvcihpPTA7aTw0O2krKyl7IGcuYmVnaW5QYXRoKCk7IGcuYXJjKHB0c1tpXS54LHB0c1tpXS55LDksMCxNYXRoLlBJKjIpOyBnLmZpbGwoKTsgfQogICAgICAgIH1lbHNlewogICAgICAgICAgdmFyIHgyPU1hdGgucm91bmQodncqMC4wNyksIHkyPU1hdGgucm91bmQodmgqMC4xMiksIHcyPXZ3LXgyKjIsIGgyPXZoLXkyKjI7CiAgICAgICAgICBnLnN0cm9rZVN0eWxlPShlc3RhZG89PT0nbWFsJyk/JyNlNjdlMjInOicjOWFhMGE2JzsKICAgICAgICAgIGcubGluZVdpZHRoPTQ7IGcuc2V0TGluZURhc2goWzE0LDEwXSk7CiAgICAgICAgICBnLnN0cm9rZVJlY3QoeDIseTIsdzIsaDIpOwogICAgICAgICAgZy5zZXRMaW5lRGFzaChbXSk7CiAgICAgICAgfQogICAgICAgIGlmKG51bWVybz4wKXsKICAgICAgICAgIGcuc2F2ZSgpOwogICAgICAgICAgZy5mb250PSdib2xkIDExMHB4IHNhbnMtc2VyaWYnOyBnLnRleHRBbGlnbj0nY2VudGVyJzsgZy50ZXh0QmFzZWxpbmU9J21pZGRsZSc7CiAgICAgICAgICBnLmxpbmVXaWR0aD0xMDsgZy5zdHJva2VTdHlsZT0ncmdiYSgwLDAsMCwwLjU1KSc7CiAgICAgICAgICBnLnN0cm9rZVRleHQoU3RyaW5nKG51bWVybyksdncvMix2aC8yKTsKICAgICAgICAgIGcuZmlsbFN0eWxlPScjM2ZiOTUwJzsgZy5maWxsVGV4dChTdHJpbmcobnVtZXJvKSx2dy8yLHZoLzIpOwogICAgICAgICAgZy5yZXN0b3JlKCk7CiAgICAgICAgfQogICAgICB9Y2F0Y2goZSl7fQogICAgfTsKICAgIHZhciBwaW50YXJPdmFsbz1mdW5jdGlvbihlc3RhZG8sIG51bWVybywgaW5mbyl7CiAgICAgIHRyeXsKICAgICAgICB2YXIgb3Y9JChvdklkKTsgaWYoIW92KXsgcmV0dXJuOyB9CiAgICAgICAgdmFyIHZ3PSh2JiZ2LnZpZGVvV2lkdGgpfHwwLCB2aD0odiYmdi52aWRlb0hlaWdodCl8fDA7CiAgICAgICAgaWYoIXZ3fHwhdmgpeyByZXR1cm47IH0KICAgICAgICBpZihvdi53aWR0aCE9PXZ3fHxvdi5oZWlnaHQhPT12aCl7IG92LndpZHRoPXZ3OyBvdi5oZWlnaHQ9dmg7IH0KICAgICAgICB2YXIgZz1vdi5nZXRDb250ZXh0KCcyZCcpOyBpZighZyl7IHJldHVybjsgfQogICAgICAgIGcuY2xlYXJSZWN0KDAsMCx2dyx2aCk7CiAgICAgICAgdmFyIGN4PXZ3KjAuNSwgY3k9dmgqMC41Miwgcng9dncqMC4zMCwgcnk9dmgqMC4zODsKICAgICAgICB2YXIgY29sPShlc3RhZG89PT0nb2snKT8nIzNmYjk1MCc6KChlc3RhZG89PT0nY2FyYScpPycjZTNiMzQxJzonIzlhYTBhNicpOwogICAgICAgIHRyeXsKICAgICAgICAgIGcuZmlsbFN0eWxlPSdyZ2JhKDAsMCwwLDAuNDApJzsKICAgICAgICAgIGcuYmVnaW5QYXRoKCk7CiAgICAgICAgICBnLnJlY3QoMCwwLHZ3LHZoKTsKICAgICAgICAgIGcubW92ZVRvKGN4K3J4LGN5KTsKICAgICAgICAgIGlmKGcuZWxsaXBzZSl7IGcuZWxsaXBzZShjeCxjeSxyeCxyeSwwLDAsTWF0aC5QSSoyKTsgfSBlbHNlIHsgZy5yZWN0KGN4LXJ4LGN5LXJ5LHJ4KjIscnkqMik7IH0KICAgICAgICAgIGcuZmlsbCgnZXZlbm9kZCcpOwogICAgICAgIH1jYXRjaChlRil7IGcuZmlsbFN0eWxlPSdyZ2JhKDAsMCwwLDAuMjIpJzsgZy5maWxsUmVjdCgwLDAsdncsdmgpOyB9CiAgICAgICAgZy5zYXZlKCk7CiAgICAgICAgZy5zdHJva2VTdHlsZT1jb2w7IGcubGluZVdpZHRoPTY7CiAgICAgICAgZy5iZWdpblBhdGgoKTsgaWYoZy5lbGxpcHNlKXsgZy5lbGxpcHNlKGN4LGN5LHJ4LHJ5LDAsMCxNYXRoLlBJKjIpOyB9IGVsc2UgeyBnLnN0cm9rZVJlY3QoY3gtcngsY3ktcnkscngqMixyeSoyKTsgfQogICAgICAgIGcuc3Ryb2tlKCk7CiAgICAgICAgZy5yZXN0b3JlKCk7CiAgICAgICAgaWYoaW5mbyYmaW5mby5jYWphJiZpbmZvLmNhamEudz40KXsKICAgICAgICAgIGcuc3Ryb2tlU3R5bGU9KGVzdGFkbz09PSdvaycpPycjM2ZiOTUwJzonI2UzYjM0MSc7IGcubGluZVdpZHRoPTM7CiAgICAgICAgICBnLnN0cm9rZVJlY3QoaW5mby5jYWphLngsaW5mby5jYWphLnksaW5mby5jYWphLncsaW5mby5jYWphLmgpOwogICAgICAgIH0KICAgICAgICB2YXIgcHJvZz0oc3QmJnN0LmF1dG8pP01hdGgubWluKDEsc3QuYXV0by80KTowOwogICAgICAgIGlmKHByb2c+MCl7CiAgICAgICAgICBnLnNhdmUoKTsgZy5zdHJva2VTdHlsZT0nIzNmYjk1MCc7IGcubGluZVdpZHRoPTg7CiAgICAgICAgICBnLmJlZ2luUGF0aCgpOwogICAgICAgICAgZy5hcmMoY3gsY3ksTWF0aC5tYXgocngscnkpKzE2LC1NYXRoLlBJLzIsLU1hdGguUEkvMitwcm9nKk1hdGguUEkqMik7CiAgICAgICAgICBnLnN0cm9rZSgpOyBnLnJlc3RvcmUoKTsKICAgICAgICB9CiAgICAgICAgaWYobnVtZXJvPjApewogICAgICAgICAgZy5zYXZlKCk7CiAgICAgICAgICBnLmZvbnQ9J2JvbGQgMTEwcHggc2Fucy1zZXJpZic7IGcudGV4dEFsaWduPSdjZW50ZXInOyBnLnRleHRCYXNlbGluZT0nbWlkZGxlJzsKICAgICAgICAgIGcubGluZVdpZHRoPTEwOyBnLnN0cm9rZVN0eWxlPSdyZ2JhKDAsMCwwLDAuNTUpJzsKICAgICAgICAgIGcuc3Ryb2tlVGV4dChTdHJpbmcobnVtZXJvKSx2dy8yLHZoLzIpOwogICAgICAgICAgZy5maWxsU3R5bGU9JyMzZmI5NTAnOyBnLmZpbGxUZXh0KFN0cmluZyhudW1lcm8pLHZ3LzIsdmgvMik7CiAgICAgICAgICBnLnJlc3RvcmUoKTsKICAgICAgICB9CiAgICAgIH1jYXRjaChlKXt9CiAgICB9OwogICAgdmFyIHVsdGltbz0nJzsKICAgIHZhciBhdmlzYXI9ZnVuY3Rpb24oY29kZSx0eHQsY29sb3IpeyBpZihjb2RlIT09dWx0aW1vKXsgdWx0aW1vPWNvZGU7IG1zZyhzdElkLHR4dCxjb2xvcik7IH0gfTsKICAgIGlmKHBzSWQ9PT0nNCcpewogICAgICBwaW50YXJPdmFsbygnJywwLG51bGwpOwogICAgICBhdmlzYXIoJ2luaScsJ1BvbiB0dSBjYXJhIGRlbnRybyBkZWwgT1ZBTE8uIExhIGNhcHR1cmEgZXMgQVVUT01BVElDQSBjdWFuZG8gdG9kbyBlc3RlIGNvcnJlY3RvLicsJyNhNjAnKTsKICAgICAgaWYoc3QuaXYpeyB0cnl7IGNsZWFySW50ZXJ2YWwoc3QuaXYpOyB9Y2F0Y2goZSl7fSB9CiAgICAgIHN0Lml2PXNldEludGVydmFsKGZ1bmN0aW9uKCl7CiAgICAgICAgdHJ5ewogICAgICAgICAgaWYoIXN0cmVhbXNbcHNJZF0peyByZXR1cm47IH0KICAgICAgICAgIGJ1c2NhckNhcmFWaXZhKHYsZnVuY3Rpb24oaW5mbyl7CiAgICAgICAgICAgIHRyeXsKICAgICAgICAgICAgICBFU1QuY2FyYVZpdmE9aW5mbzsKICAgICAgICAgICAgICBpZighaW5mb3x8IWluZm8udmlzdGEpewogICAgICAgICAgICAgICAgc3QuYXV0bz0wOyBzdC5jZD0wOwogICAgICAgICAgICAgICAgcGludGFyT3ZhbG8oJ2NhcmEnLDAsaW5mb3x8bnVsbCk7CiAgICAgICAgICAgICAgICBhdmlzYXIoKGluZm8mJmluZm8uY29kKXx8J25vZGV0JywoaW5mbyYmaW5mby5tb3Rpdm8pfHwnQnVzY2FuZG8gdHUgY2FyYS4uLiBidWVuYSBsdXosIHNpbiBnb3JyYSBuaSBsZW50ZXMgb3NjdXJvcy4nLCcjYTYwJyk7CiAgICAgICAgICAgICAgICByZXR1cm47CiAgICAgICAgICAgICAgfQogICAgICAgICAgICAgIHZhciBudW1lcm89MDsKICAgICAgICAgICAgICBpZihpbmZvLm9rKXsgc3QuYXV0bz0oc3QuYXV0b3x8MCkrMTsgfSBlbHNlIHsgc3QuYXV0bz0wOyBzdC5jZD0wOyB9CiAgICAgICAgICAgICAgaWYoc3QuYXV0bz49NCl7CiAgICAgICAgICAgICAgICBzdC5jZD0oc3QuY2R8fDApKzE7CiAgICAgICAgICAgICAgICBudW1lcm89TWF0aC5tYXgoMSw0LXN0LmNkKTsKICAgICAgICAgICAgICAgIHBpbnRhck92YWxvKCdvaycsbnVtZXJvLGluZm8pOwogICAgICAgICAgICAgICAgYXZpc2FyKCdjZCcrbnVtZXJvLCdDYXB0dXJhbmRvIGVuICcrbnVtZXJvKycuLi4gbm8gdGUgbXVldmFzLicsJyMwODAnKTsKICAgICAgICAgICAgICAgIGlmKHN0LmNkPj00JiYhc3QuYXV0b0hlY2hvKXsKICAgICAgICAgICAgICAgICAgc3QuYXV0b0hlY2hvPXRydWU7IHZpYnJhcigpOwogICAgICAgICAgICAgICAgICBwcm9jZXNhclNlbGZpZSgpOwogICAgICAgICAgICAgICAgfQogICAgICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgICAgIH0KICAgICAgICAgICAgICBwaW50YXJPdmFsbyhpbmZvLm9rPydvayc6J2NhcmEnLDAsaW5mbyk7CiAgICAgICAgICAgICAgYXZpc2FyKGluZm8ub2s/J3ByZSc6aW5mby5jb2QsIGluZm8ubW90aXZvLCBpbmZvLm9rPycjMDgwJzonI2E2MCcpOwogICAgICAgICAgICB9Y2F0Y2goZTMpe30KICAgICAgICAgIH0pOwogICAgICAgIH1jYXRjaChlKXt9CiAgICAgIH0sNDMwKTsKICAgIH1lbHNlewogICAgICBwaW50YXJEb2MobnVsbCwnJyk7CiAgICAgIGF2aXNhcignaW5pJywnQnVzY2FuZG8gZWwgZG9jdW1lbnRvLi4uIHBvbmxvIHNvYnJlIGZvbmRvIE9TQ1VSTywgc2luIGJyaWxsby4gTGFzIDQgZXNxdWluYXMgc2UgbWFyY2FuIHNvbGFzLicsJyNhNjAnKTsKICAgICAgaWYoc3QuaXYpeyB0cnl7IGNsZWFySW50ZXJ2YWwoc3QuaXYpOyB9Y2F0Y2goZSl7fSB9CiAgICAgIHN0Lml2PXNldEludGVydmFsKGZ1bmN0aW9uKCl7CiAgICAgICAgdHJ5ewogICAgICAgICAgaWYoIXN0cmVhbXNbcHNJZF0peyByZXR1cm47IH0KICAgICAgICAgIHZhciBxPWRldGVjdGFyRG9jUXVhZCh2KTsKICAgICAgICAgIHZhciBlc3Q9J21hbCcsIGNvZD0nbm9uZScsIHR4dD0nQnVzY2FuZG8gZWwgZG9jdW1lbnRvLi4uIHBvbmxvIHNvYnJlIGZvbmRvIE9TQ1VSTywgbGxlbmFuZG8gZWwgbWFyY28sIHNpbiBicmlsbG8uJywgY29sPScjYTYwJywgcXVhZD1udWxsLCBudW1lcm89MDsKICAgICAgICAgIGlmKHEmJnEubGxlbm8pewogICAgICAgICAgICB2YXIgYjE9cS5sdXo+PTYwLCBiMj1xLm5pdG8+PTQwLCBiMz0ocS5ibGFuY289PW51bGwpfHwocS5ibGFuY288PTAuMjIpOwogICAgICAgICAgICBzdC5hdXRvPTA7IHN0LmNkPTA7CiAgICAgICAgICAgIGlmKCFiMSl7IGVzdD0nbWFsJzsgY29kPSdsdXonOyB0eHQ9J1BPQ0EgTFVaOiBidXNjYSBtZWpvciBpbHVtaW5hY2lvbiBvIHVzYSBFbGVnaXIgYXJjaGl2byBjb24gdW5hIGZvdG8gZGUgY2VyY2EuJzsgY29sPScjYzAwJzsgfQogICAgICAgICAgICBlbHNlIGlmKCFiMil7IGVzdD0nbWFsJzsgY29kPSduaXRvJzsgdHh0PSdObyBzZSB2ZSBOSVRJRE86IHNvc3RcdTAwRTluIGZpcm1lLCBlc3BlcmEgZWwgZW5mb3F1ZSB5IGV2aXRhIGVsIGJyaWxsby4nOyBjb2w9JyNjMDAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYoIWIzKXsgZXN0PSdtYWwnOyBjb2Q9J2JsYSc7IHR4dD0nSGF5IFJFRkxFSk8gZW4gZWwgZG9jdW1lbnRvOiBpbmNsXHUwMEVEbmFsbyB1biBwb2NvIHBhcmEgcXVpdGFyIGVsIGJyaWxsby4nOyBjb2w9JyNjMDAnOyB9CiAgICAgICAgICAgIGVsc2V7IGVzdD0nY2FzaSc7IGNvZD0nZXNwZXJhJzsgdHh0PSdEb2N1bWVudG8gbGxlbmFuZG8gZWwgbWFyY28uIFRvY2EgQ0FQVFVSQVIuJzsgY29sPScjMDgwJzsgfQogICAgICAgICAgICBwaW50YXJEb2MobnVsbCwgZXN0KTsKICAgICAgICAgIH1lbHNlIGlmKHEpewogICAgICAgICAgICBxdWFkPXE7CiAgICAgICAgICAgIHN0Lmhpc3QucHVzaChxdWFkKTsKICAgICAgICAgICAgaWYoc3QuaGlzdC5sZW5ndGg+Nyl7IHN0Lmhpc3Quc2hpZnQoKTsgfQogICAgICAgICAgICB2YXIgYzE9cS5sdXo+PTYwLCBjMj1xLm5pdG8+PTQwLCBjMz0ocS5ibGFuY289PW51bGwpfHwocS5ibGFuY288PTAuMjApOwogICAgICAgICAgICBzdC5hdXRvPTA7IHN0LmNkPTA7CiAgICAgICAgICAgIGlmKHEuZGVzY2FydGFkbz09PSdwZXF1ZW5vJyl7IGVzdD0nbWFsJzsgY29kPSdmYXInOyB0eHQ9J0FDRVJDQVRFOiBlbCBkb2N1bWVudG8gc2UgdmUgbXV5IHBlcXVlXHUwMEYxbyBlbiBsYSBmb3RvLic7IGNvbD0nI2E2MCc7IH0KICAgICAgICAgICAgZWxzZSBpZihxLmRlc2NhcnRhZG89PT0nZm9ybWEnKXsgZXN0PSdtYWwnOyBjb2Q9J2Zvcm1hJzsgdHh0PSdObyB2ZW8gYmllbiBsYXMgNCBlc3F1aW5hczogYWNcdTAwRTlyY2F0ZSB5IHVzYSB1biBmb25kbyBvc2N1cm8uJzsgY29sPScjYTYwJzsgfQogICAgICAgICAgICBlbHNlIGlmKCFjMSl7IGVzdD0nbWFsJzsgY29kPSdsdXonOyB0eHQ9J1BPQ0EgTFVaOiBidXNjYSBtZWpvciBpbHVtaW5hY2lvbiBvIHVzYSBFbGVnaXIgYXJjaGl2byBjb24gdW5hIGZvdG8gZGUgY2VyY2EuJzsgY29sPScjYzAwJzsgfQogICAgICAgICAgICBlbHNlIGlmKCFjMil7IGVzdD0nbWFsJzsgY29kPSduaXRvJzsgdHh0PSdObyBzZSB2ZSBOSVRJRE86IHNvc3RcdTAwRTluIGZpcm1lLCBlc3BlcmEgZWwgZW5mb3F1ZSB5IGV2aXRhIGVsIGJyaWxsby4nOyBjb2w9JyNjMDAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYoIWMzKXsgZXN0PSdtYWwnOyBjb2Q9J2JsYSc7IHR4dD0nSGF5IFJFRkxFSk8gZW4gZWwgZG9jdW1lbnRvOiBpbmNsXHUwMEVEbmFsbyB1biBwb2NvIHBhcmEgcXVpdGFyIGVsIGJyaWxsby4nOyBjb2w9JyNjMDAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYocXVhZEVzdGFibGUoc3QuaGlzdCkpewogICAgICAgICAgICAgIHN0LmF1dG89MTsKICAgICAgICAgICAgICBzdC5jZD0oc3QuY2R8fDApKzE7CiAgICAgICAgICAgICAgbnVtZXJvPU1hdGgubWF4KDEsNC1zdC5jZCk7CiAgICAgICAgICAgICAgZXN0PSdvayc7IGNvZD0nY2QnK251bWVybzsgdHh0PSdDYXB0dXJhbmRvIGVuICcrbnVtZXJvKycuLi4gbm8gdGUgbXVldmFzLic7IGNvbD0nIzA4MCc7CiAgICAgICAgICAgICAgaWYoc3QuY2Q+PTQmJiFzdC5hdXRvSGVjaG8pewogICAgICAgICAgICAgICAgc3QuYXV0b0hlY2hvPXRydWU7IHZpYnJhcigpOwogICAgICAgICAgICAgICAgbWFuZWphcihwc0lkPT09JzInPydiQ2FwRic6J2JDYXBBJyk7CiAgICAgICAgICAgICAgICByZXR1cm47CiAgICAgICAgICAgICAgfQogICAgICAgICAgICB9ZWxzZXsKICAgICAgICAgICAgICBlc3Q9J2Nhc2knOyBjb2Q9J2VzcGVyYSc7IHR4dD0nRG9jdW1lbnRvIGRldGVjdGFkby4gU29zdGVubG8gcXVpZXRvIHBhcmEgY2FwdHVyYXIgc29sby4uLic7IGNvbD0nIzA4MCc7CiAgICAgICAgICAgIH0KICAgICAgICAgICAgcGludGFyUXVhZChxdWFkLCBlc3QsIG51bWVybyk7CiAgICAgICAgICB9ZWxzZXsKICAgICAgICAgICAgc3QuYXV0bz0wOyBzdC5jZD0wOwogICAgICAgICAgICBpZihEYXRlLm5vdygpLXN0LnQ+MTIwMCl7IHN0LmNhamE9bnVsbDsgfQogICAgICAgICAgICB2YXIgY2FqYUY9ZGV0ZWN0YXJEb2NCb3godik7CiAgICAgICAgICAgIGlmKGNhamFGKXsKICAgICAgICAgICAgICBzdC5jYWphPWNhamFGOyBzdC50PURhdGUubm93KCk7CiAgICAgICAgICAgICAgZXN0PShjYWphRi5uaXRvJiZjYWphRi5sdXo+PTU1KT8nY2FzaSc6J21hbCc7CiAgICAgICAgICAgICAgY29kPShlc3Q9PT0nY2FzaScpPydhcHJveCc6J2NhbCc7CiAgICAgICAgICAgICAgdHh0PShlc3Q9PT0nY2FzaScpPydDYXNpOiBzb3N0XHUwMEU5biBxdWlldG8uIENvbiBmb25kbyBvc2N1cm8gbWFyY28gbGFzIDQgZXNxdWluYXMgeSBjYXB0dXJvIHNvbG8uJzonU2UgdmUgZmxvam86IG1cdTAwRTFzIGx1eiwgZmlybWUsIHNpbiBicmlsbG8uJzsKICAgICAgICAgICAgICBjb2w9KGVzdD09PSdjYXNpJyk/JyNhNjAnOicjYzAwJzsKICAgICAgICAgICAgfWVsc2UgaWYoRGF0ZS5ub3coKS1zdC50PjEyMDApewogICAgICAgICAgICAgIGNvZD0nbm9uZSc7IHR4dD0nQnVzY2FuZG8gZWwgZG9jdW1lbnRvLi4uIHBvbmxvIHNvYnJlIGZvbmRvIE9TQ1VSTywgbGxlbmFuZG8gZWwgbWFyY28sIHNpbiBicmlsbG8uJzsKICAgICAgICAgICAgfQogICAgICAgICAgICBwaW50YXJEb2MoY2FqYUZ8fHN0LmNhamF8fG51bGwsIGVzdCk7CiAgICAgICAgICB9CiAgICAgICAgICBhdmlzYXIoY29kLHR4dCxjb2wpOwogICAgICAgIH1jYXRjaChlKXt9CiAgICAgIH0sMzAwKTsKICAgIH0KICAgIGlmKCF2Ll9fenlNYXJjbyl7CiAgICAgIHYuX196eU1hcmNvPTE7CiAgICAgIHYuYWRkRXZlbnRMaXN0ZW5lcigncGxheWluZycsZnVuY3Rpb24oKXsgdHJ5eyBhbGluZWFyT3ZlcmxheShwc0lkLCB2KTsgaWYocHNJZD09PSc0Jyl7IHBpbnRhck92YWxvKCcnLDAsbnVsbCk7IH0gZWxzZSB7IHBpbnRhckRvYyhudWxsLCcnKTsgfSB9Y2F0Y2goZSl7fSB9KTsKICAgICAgdi5hZGRFdmVudExpc3RlbmVyKCdsb2FkZWRtZXRhZGF0YScsZnVuY3Rpb24oKXsgdHJ5eyBhbGluZWFyT3ZlcmxheShwc0lkLCB2KTsgaWYocHNJZD09PSc0Jyl7IHBpbnRhck92YWxvKCcnLDAsbnVsbCk7IH0gZWxzZSB7IHBpbnRhckRvYyhudWxsLCcnKTsgfSB9Y2F0Y2goZSl7fSB9KTsKICAgIH0KICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIGludGVudGFyRW5mb3F1ZShzdCl7CiAgdHJ5ewogICAgdmFyIHRyPShzdCYmc3QuZ2V0VmlkZW9UcmFja3MpP3N0LmdldFZpZGVvVHJhY2tzKClbMF06bnVsbDsKICAgIGlmKCF0cil7IHJldHVybjsgfQogICAgdmFyIGNhcHM9dHIuZ2V0Q2FwYWJpbGl0aWVzP3RyLmdldENhcGFiaWxpdGllcygpOm51bGw7CiAgICBpZihjYXBzJiZjYXBzLmZvY3VzTW9kZSYmY2Fwcy5mb2N1c01vZGUuam9pbiYmY2Fwcy5mb2N1c01vZGUuam9pbignICcpLmluZGV4T2YoJ2NvbnRpbnVvdXMnKT49MCl7CiAgICAgIHZhciBwPXRyLmFwcGx5Q29uc3RyYWludHMoe2FkdmFuY2VkOlt7Zm9jdXNNb2RlOidjb250aW51b3VzJ31dfSk7CiAgICAgIGlmKHAmJnAuY2F0Y2gpeyBwLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH0KICAgIH0KICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIGFicmlyQ2FtKHBzSWQsIGZhY2luZywgc3RJZCwgY2FwSWQpewogIHZhciB2PWZpbmRWaWRlbyhwc0lkKTsKICBpZighdil7IG1zZyhzdElkLCdObyBlbmNvbnRyZSBlbCB2aWRlbyBkZSBsYSBjYW1hcmEgZW4gbGEgcGFnaW5hLicsICcjYzAwJyk7IHJldHVybiBQcm9taXNlLnJlamVjdChuZXcgRXJyb3IoJ3NpbiB2aWRlbycpKTsgfQogIGlmKCFuYXZpZ2F0b3IubWVkaWFEZXZpY2VzIHx8ICFuYXZpZ2F0b3IubWVkaWFEZXZpY2VzLmdldFVzZXJNZWRpYSl7CiAgICBtc2coc3RJZCwnVHUgbmF2ZWdhZG9yIG5vIHBlcm1pdGUgY2FtYXJhLiBVc2EgbGEgb3BjaW9uIGRlIGdhbGVyaWEuJywgJyNjMDAnKTsKICAgIHJldHVybiBQcm9taXNlLnJlamVjdChuZXcgRXJyb3IoJ3NpbiBjYW1hcmEnKSk7CiAgfQogIHBhcmFyQ2FtKHBzSWQpOwogIHZhciB6b25hPSQoJ3Z6JytsZXRyYURlKHBzSWQpKTsKICBpZih6b25hKXsgem9uYS5zdHlsZS5kaXNwbGF5PSdibG9jayc7IH0KICBtc2coc3RJZCwnUGlkaWVuZG8gcGVybWlzbyBkZSBjYW1hcmEuLi4nLCcnKTsKICB2YXIgZG9jWm9uYT0ocHNJZD09PScyJ3x8cHNJZD09PSczJyk7CiAgcmV0dXJuIG5hdmlnYXRvci5tZWRpYURldmljZXMuZ2V0VXNlck1lZGlhKHthdWRpbzpmYWxzZSwgdmlkZW86e2ZhY2luZ01vZGU6ZmFjaW5nLCB3aWR0aDp7aWRlYWw6ZG9jWm9uYT8xOTIwOjEyODB9LCBoZWlnaHQ6e2lkZWFsOmRvY1pvbmE/MTA4MDo3MjB9fX0pLnRoZW4oZnVuY3Rpb24oc3QpewogICAgc3RyZWFtc1twc0lkXT1zdDsKICAgIHYuc3JjT2JqZWN0PXN0OwogICAgdHJ5eyB2LnNldEF0dHJpYnV0ZSgncGxheXNpbmxpbmUnLCdwbGF5c2lubGluZScpOyB9Y2F0Y2goZSl7fQogICAgdi5tdXRlZD10cnVlOwogICAgdHJ5eyB2LnN0eWxlLnRyYW5zZm9ybT0ocHNJZD09PSc0Jyk/J3NjYWxlWCgtMSknOicnOyB9Y2F0Y2goZU0pe30KICAgIGludGVudGFyRW5mb3F1ZShzdCk7CiAgICB2YXIgcD12LnBsYXkoKTsgaWYocCYmcC5jYXRjaCl7IHAuY2F0Y2goZnVuY3Rpb24oKXt9KTsgfQogICAgZXN0aWxvQ2hpY28odik7CiAgICB2YXIgY2FwPSQoY2FwSWQpOwogICAgaWYoY2FwKXsgY2FwLmRpc2FibGVkPWZhbHNlOyBjYXAuc3R5bGUuZGlzcGxheT0nJzsgY2FwLnN0eWxlLnZpc2liaWxpdHk9J3Zpc2libGUnOyBjYXAuc3R5bGUucG9pbnRlckV2ZW50cz0nYXV0byc7IGNhcC5zdHlsZS5wb3NpdGlvbj1jYXAuc3R5bGUucG9zaXRpb258fCdyZWxhdGl2ZSc7IGNhcC5zdHlsZS56SW5kZXg9Jzk5OTknOyB9CiAgICB2YXIgT1Y9eycyJzonb3ZGJywnMyc6J292QScsJzQnOidvdlMnfTsKICAgIHZhciBvdj0kKE9WW3BzSWRdKTsKICAgIGlmKG92KXsgb3Yuc3R5bGUucG9pbnRlckV2ZW50cz0nbm9uZSc7IH0KICAgIHZhciB6b25hPSQoJ3Z6JytsZXRyYURlKHBzSWQpKTsKICAgIGlmKHpvbmEpeyB6b25hLnN0eWxlLnBvc2l0aW9uPSdyZWxhdGl2ZSc7IH0KICAgIGVubWFyY2FyVmVyZGUocHNJZCwgdik7CiAgICBhbGluZWFyT3ZlcmxheShwc0lkLCB2KTsKICAgIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsgdHJ5eyBhbGluZWFyT3ZlcmxheShwc0lkLCB2KTsgfWNhdGNoKGUpe30gfSwyNTApOwogICAgdmFyIHE9KHBzSWQ9PT0nNCcpOwogICAgbXNnKHN0SWQsIHE/J0NhbWFyYSBsaXN0YS4gUG9uIHR1IGNhcmEgZW4gZWwgT1ZBTE86IHNlIGNhcHR1cmEgU09MTyBjdWFuZG8gdG9kbyBlc3RlIGNvcnJlY3RvLic6J0NhbWFyYSBsaXN0YS4gQnVzY28gbGFzIDQgZXNxdWluYXMgZGVsIGRvY3VtZW50bzogc29zdFx1MDBFOW5sbyBxdWlldG8geSBjYXB0dXJvIHNvbG8uJywnIzA4MCcpOwogICAgcmV0dXJuIHRydWU7CiAgfSkuY2F0Y2goZnVuY3Rpb24oZSl7CiAgICBpZih6b25hKXsgdHJ5eyB6b25hLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9Y2F0Y2goZTIpe30gfQogICAgbXNnKHN0SWQsJ05vIHB1ZGUgYWJyaXIgbGEgY2FtYXJhICgnKyhlJiZlLm5hbWU/ZS5uYW1lOidlcnJvcicpKycpLiBQdWVkZXMgdXNhciBsYSBnYWxlcmlhIG8gcmV2aXNhIGVsIHBlcm1pc28uJywnI2MwMCcpOwogICAgdGhyb3cgZTsKICB9KTsKfQpmdW5jdGlvbiBwYXJhckNhbShwc0lkKXsKICB2YXIgc3Q9c3RyZWFtc1twc0lkXTsKICBpZihzdCl7CiAgICB0cnl7IHN0LmdldFRyYWNrcygpLmZvckVhY2goZnVuY3Rpb24odCl7IHRyeXsgdC5zdG9wKCk7IH1jYXRjaChlKXt9IH0pOyB9Y2F0Y2goZSl7fQogIH0KICBzdHJlYW1zW3BzSWRdPW51bGw7CiAgdHJ5ewogICAgdmFyIHZ2PWZpbmRWaWRlbyhwc0lkKTsKICAgIGlmKHZ2KXsgdnYuc3R5bGUudHJhbnNmb3JtPScnOyB9CiAgfWNhdGNoKGVUKXt9CiAgdHJ5ewogICAgdmFyIEQ9enlEZXQoKSwgc3REPURbcHNJZF07CiAgICBpZihzdEQmJnN0RC5pdil7IGNsZWFySW50ZXJ2YWwoc3RELml2KTsgc3RELml2PW51bGw7IH0KICAgIGlmKHBzSWQ9PT0nNCcpeyBFU1QuY2FyYVZpdmE9bnVsbDsgfQogIH1jYXRjaChlKXt9CiAgdHJ5ewogICAgdmFyIHpvbmE9JCgndnonK2xldHJhRGUocHNJZCkpOwogICAgaWYoem9uYSl7IHpvbmEuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH0KICAgIHZhciBPVj17JzInOidvdkYnLCczJzonb3ZBJywnNCc6J292Uyd9OwogICAgdmFyIG92PSQoT1ZbcHNJZF0pOwogICAgaWYob3YpeyB2YXIgZz1vdi5nZXRDb250ZXh0KCcyZCcpOyBpZihnKXsgZy5jbGVhclJlY3QoMCwwLG92LndpZHRofHwxLG92LmhlaWdodHx8MSk7IH0gfQogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gcGFyYXJUb2RhcygpeyB2YXIgazsgZm9yKGsgaW4gc3RyZWFtcyl7IHBhcmFyQ2FtKGspOyB9IH0KZnVuY3Rpb24gY2FwdHVyYXJWaWRlbyhwc0lkLCBtYXhEaW0pewogIHZhciB2PWZpbmRWaWRlbyhwc0lkKTsKICBpZighdiB8fCAhdi52aWRlb1dpZHRoIHx8ICFzdHJlYW1zW3BzSWRdKXsgcmV0dXJuIG51bGw7IH0KICB2YXIgdz12LnZpZGVvV2lkdGgsIGg9di52aWRlb0hlaWdodDsKICB2YXIgc2M9TWF0aC5taW4oMSwobWF4RGltfHwxMDI0KS9NYXRoLm1heCh3LGgpKTsKICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICBjLndpZHRoPU1hdGgucm91bmQodypzYyk7IGMuaGVpZ2h0PU1hdGgucm91bmQoaCpzYyk7CiAgYy5nZXRDb250ZXh0KCcyZCcpLmRyYXdJbWFnZSh2LDAsMCxjLndpZHRoLGMuaGVpZ2h0KTsKICB2YXIgZD1jLnRvRGF0YVVSTCgnaW1hZ2UvanBlZycsMC44NSk7CiAgcGFyYXJDYW0ocHNJZCk7CiAgcmV0dXJuIGQ7Cn0KZnVuY3Rpb24gZG93bnNjYWxlKGRhdGFVcmwsIG1heERpbSl7CiAgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7CiAgICB2YXIgaW09bmV3IEltYWdlKCk7CiAgICBpbS5vbmxvYWQ9ZnVuY3Rpb24oKXsKICAgICAgdmFyIHNjPU1hdGgubWluKDEsKG1heERpbXx8MTAyNCkvTWF0aC5tYXgoaW0ud2lkdGgsaW0uaGVpZ2h0KSk7CiAgICAgIHZhciBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOwogICAgICBjLndpZHRoPU1hdGgubWF4KDEsTWF0aC5yb3VuZChpbS53aWR0aCpzYykpOwogICAgICBjLmhlaWdodD1NYXRoLm1heCgxLE1hdGgucm91bmQoaW0uaGVpZ2h0KnNjKSk7CiAgICAgIGMuZ2V0Q29udGV4dCgnMmQnKS5kcmF3SW1hZ2UoaW0sMCwwLGMud2lkdGgsYy5oZWlnaHQpOwogICAgICByZXMoYy50b0RhdGFVUkwoJ2ltYWdlL2pwZWcnLDAuODUpKTsKICAgIH07CiAgICBpbS5vbmVycm9yPWZ1bmN0aW9uKCl7IHJlcyhkYXRhVXJsKTsgfTsKICAgIGltLnNyYz1kYXRhVXJsOwogIH0pOwp9CmZ1bmN0aW9uIGFyY2hpdm9BRGF0b3MoZmlsZSl7CiAgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyxyZWopewogICAgdmFyIGZyPW5ldyBGaWxlUmVhZGVyKCk7CiAgICBmci5vbmxvYWQ9ZnVuY3Rpb24oKXsgcmVzKFN0cmluZyhmci5yZXN1bHQpKTsgfTsKICAgIGZyLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVqKG5ldyBFcnJvcignbm8gcHVkZSBsZWVyIGVsIGFyY2hpdm8nKSk7IH07CiAgICBmci5yZWFkQXNEYXRhVVJMKGZpbGUpOwogIH0pOwp9CgovKiA9PT09PT09PT09PT09PT09PSBPQ1IgY29uIGNhY2hlICsgbWVqb3JhIGRlIGltYWdlbiA9PT09PT09PT09PT09PT09PSAqLwp2YXIgY2FjaGVPY3I9e30sIHByb21lc2FXb3JrZXI9bnVsbDsKZnVuY3Rpb24gYWJyaXJXb3JrZXJPY3IoKXsKICBpZihwcm9tZXNhV29ya2VyKXsgcmV0dXJuIHByb21lc2FXb3JrZXI7IH0KICB0cnl7CiAgICBpZih0eXBlb2YgVGVzc2VyYWN0IT09J3VuZGVmaW5lZCcgJiYgVGVzc2VyYWN0LmNyZWF0ZVdvcmtlcil7CiAgICAgIHByb21lc2FXb3JrZXI9VGVzc2VyYWN0LmNyZWF0ZVdvcmtlcignc3BhK2VuZycsMSx7bG9nZ2VyOmZ1bmN0aW9uKCl7fX0pLnRoZW4oZnVuY3Rpb24odyl7IHJldHVybiB3OyB9KS5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gbnVsbDsgfSk7CiAgICAgIHJldHVybiBwcm9tZXNhV29ya2VyOwogICAgfQogIH1jYXRjaChlKXt9CiAgcHJvbWVzYVdvcmtlcj1Qcm9taXNlLnJlc29sdmUobnVsbCk7CiAgcmV0dXJuIHByb21lc2FXb3JrZXI7Cn0KZnVuY3Rpb24gbWVqb3JhckltYWdlbihkYXRhVXJsKXsKICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsKICAgIHZhciBpbT1uZXcgSW1hZ2UoKTsKICAgIGltLm9ubG9hZD1mdW5jdGlvbigpewogICAgICB0cnl7CiAgICAgICAgdmFyIGFuY2hvPWltLndpZHRoLCBhbHRvPWltLmhlaWdodDsKICAgICAgICB2YXIgZXNjMT1NYXRoLm1pbigzLCBNYXRoLm1heCgxLCAxNDAwL01hdGgubWF4KDEsTWF0aC5taW4oYW5jaG8sYWx0bykpKSk7CiAgICAgICAgdmFyIGVzYzI9TWF0aC5taW4oMSwgMjIwMC9NYXRoLm1heCgxLE1hdGgubWF4KGFuY2hvLGFsdG8pKSk7CiAgICAgICAgdmFyIHNjPU1hdGgubWluKGVzYzEsZXNjMik7CiAgICAgICAgaWYoIShzYz4wKSl7IHNjPTE7IH0KICAgICAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgICAgICBjLndpZHRoPU1hdGgubWF4KDEsTWF0aC5yb3VuZChhbmNobypzYykpOwogICAgICAgIGMuaGVpZ2h0PU1hdGgubWF4KDEsTWF0aC5yb3VuZChhbHRvKnNjKSk7CiAgICAgICAgdmFyIGc9Yy5nZXRDb250ZXh0KCcyZCcpOwogICAgICAgIGlmKCFnKXsgcmVzKG51bGwpOyByZXR1cm47IH0KICAgICAgICBnLmltYWdlU21vb3RoaW5nRW5hYmxlZD10cnVlOwogICAgICAgIHRyeXsgZy5pbWFnZVNtb290aGluZ1F1YWxpdHk9J2hpZ2gnOyB9Y2F0Y2goZTIpe30KICAgICAgICBnLmRyYXdJbWFnZShpbSwwLDAsYy53aWR0aCxjLmhlaWdodCk7CiAgICAgICAgdmFyIGlkZD1nLmdldEltYWdlRGF0YSgwLDAsYy53aWR0aCxjLmhlaWdodCksIHA9aWRkLmRhdGEsIG49cC5sZW5ndGgvNDsKICAgICAgICB2YXIgaGlzdD1uZXcgSW50MzJBcnJheSgyNTYpLCBpLCBrLCBzdW09MDsKICAgICAgICBmb3IoaT0wO2k8bjtpKyspeyB2YXIgcj1wW2kqNF0sIGdnPXBbaSo0KzFdLCBiPXBbaSo0KzJdOyB2YXIgbD0ociozK2dnKjQrYik+PjM7IHBbaSo0XT1sOyBwW2kqNCsxXT1sOyBwW2kqNCsyXT1sOyBoaXN0W2xdKys7IHN1bSs9bDsgfQogICAgICAgIHZhciBtZWRpYT1zdW0vTWF0aC5tYXgoMSxuKTsKICAgICAgICB2YXIgZ2FuPTE7CiAgICAgICAgaWYobWVkaWE8MTA1KXsgZ2FuPTAuNzI7IH0KICAgICAgICBlbHNlIGlmKG1lZGlhPjE4NSl7IGdhbj0xLjI1OyB9CiAgICAgICAgdmFyIGFjYz0wLCBsbz0wLCBoaT0yNTU7CiAgICAgICAgZm9yKGs9MDtrPDI1NjtrKyspeyBhY2MrPWhpc3Rba107IGlmKGFjYz49biowLjAyKXsgbG89azsgYnJlYWs7IH0gfQogICAgICAgIGFjYz0wOwogICAgICAgIGZvcihrPTI1NTtrPj0wO2stLSl7IGFjYys9aGlzdFtrXTsgaWYoYWNjPj1uKjAuMDIpeyBoaT1rOyBicmVhazsgfSB9CiAgICAgICAgdmFyIGVzYz0oaGk+bG8pPzI1NS8oaGktbG8pOjE7CiAgICAgICAgZm9yKGk9MDtpPG47aSsrKXsgdmFyIHY9KHBbaSo0XS1sbykqZXNjOyB2PXY8MD8wOih2PjI1NT8yNTU6dik7IHY9MjU1Kk1hdGgucG93KHYvMjU1LGdhbik7IHBbaSo0XT12OyBwW2kqNCsxXT12OyBwW2kqNCsyXT12OyB9CiAgICAgICAgdmFyIHRtcD1uZXcgVWludDhBcnJheShuKTsKICAgICAgICBmb3IoaT0wO2k8bjtpKyspeyB0bXBbaV09cFtpKjRdOyB9CiAgICAgICAgdmFyIGFuY2hvMj1jLndpZHRoOwogICAgICAgIGZvcih2YXIgeT0xO3k8Yy5oZWlnaHQtMTt5KyspewogICAgICAgICAgZm9yKHZhciB4PTE7eDxhbmNobzItMTt4KyspewogICAgICAgICAgICB2YXIgcT15KmFuY2hvMit4OwogICAgICAgICAgICB2YXIgYmw9KHRtcFtxXSt0bXBbcS0xXSt0bXBbcSsxXSt0bXBbcS1hbmNobzJdK3RtcFtxK2FuY2hvMl0pKjAuMjsKICAgICAgICAgICAgdmFyIHYyPXRtcFtxXSswLjQqKHRtcFtxXS1ibCk7CiAgICAgICAgICAgIHYyPXYyPDA/MDoodjI+MjU1PzI1NTp2Mik7CiAgICAgICAgICAgIHZhciB3Mz1xKjQ7IHBbdzNdPXYyOyBwW3czKzFdPXYyOyBwW3czKzJdPXYyOwogICAgICAgICAgfQogICAgICAgIH0KICAgICAgICBnLnB1dEltYWdlRGF0YShpZGQsMCwwKTsKICAgICAgICByZXMoYyk7CiAgICAgIH1jYXRjaChlKXsgcmVzKG51bGwpOyB9CiAgICB9OwogICAgaW0ub25lcnJvcj1mdW5jdGlvbigpeyByZXMobnVsbCk7IH07CiAgICBpbS5zcmM9ZGF0YVVybDsKICB9KTsKfQpmdW5jdGlvbiByZWNvcnRlU3VwZXJpb3IoY3YpewogIHRyeXsKICAgIHZhciB3PWN2LndpZHRoLCBoPU1hdGgucm91bmQoY3YuaGVpZ2h0KjAuNjIpOwogICAgaWYodzw0MHx8aDw0MCl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgIGMud2lkdGg9dzsgYy5oZWlnaHQ9aDsKICAgIGMuZ2V0Q29udGV4dCgnMmQnKS5kcmF3SW1hZ2UoY3YsMCwwLHcsaCwwLDAsdyxoKTsKICAgIHJldHVybiBjOwogIH1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0KfQpmdW5jdGlvbiByZWNvbm9jZXJDb24oaW1nLCBwc20pewogIHJldHVybiBhYnJpcldvcmtlck9jcigpLnRoZW4oZnVuY3Rpb24odyl7CiAgICBmdW5jdGlvbiBjb25UZXNzKCl7CiAgICAgIHJldHVybiBUZXNzZXJhY3QucmVjb2duaXplKGltZywnc3BhK2VuZycse2xvZ2dlcjpmdW5jdGlvbigpe319KS50aGVuKGZ1bmN0aW9uKHIpeyByZXR1cm4gKHImJnIuZGF0YSYmci5kYXRhLnRleHQpP3IuZGF0YS50ZXh0OicnOyB9KS5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gJyc7IH0pOwogICAgfQogICAgaWYoISh3JiZ3LnJlY29nbml6ZSkpeyByZXR1cm4gY29uVGVzcygpOyB9CiAgICB2YXIgcHJlPSh3LnNldFBhcmFtZXRlcnMmJnBzbSk/dy5zZXRQYXJhbWV0ZXJzKHt0ZXNzZWRpdF9wYWdlc2VnX21vZGU6U3RyaW5nKHBzbSl9KTpQcm9taXNlLnJlc29sdmUoKTsKICAgIHJldHVybiBwcmUudGhlbihmdW5jdGlvbigpeyByZXR1cm4gdy5yZWNvZ25pemUoaW1nKTsgfSkudGhlbihmdW5jdGlvbihyKXsKICAgICAgaWYody5zZXRQYXJhbWV0ZXJzKXsgdHJ5eyB3LnNldFBhcmFtZXRlcnMoe3Rlc3NlZGl0X3BhZ2VzZWdfbW9kZTonMyd9KS5jYXRjaChmdW5jdGlvbigpe30pOyB9Y2F0Y2goZTIpe30gfQogICAgICByZXR1cm4gKHImJnIuZGF0YSYmci5kYXRhLnRleHQpP3IuZGF0YS50ZXh0OicnOwogICAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmV0dXJuIGNvblRlc3MoKTsgfSk7CiAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmV0dXJuICcnOyB9KTsKfQpmdW5jdGlvbiBvY3JNdWx0aShkYXRhVXJsLCBlc0J1ZW5vKXsKICBpZih0eXBlb2YgVGVzc2VyYWN0PT09J3VuZGVmaW5lZCcgfHwgIVRlc3NlcmFjdC5yZWNvZ25pemUpewogICAgcmV0dXJuIFByb21pc2UucmVzb2x2ZShbXSk7CiAgfQogIHJldHVybiBtZWpvcmFySW1hZ2VuKGRhdGFVcmwpLnRoZW4oZnVuY3Rpb24oY3YpewogICAgdmFyIHZhcnM9W107CiAgICBpZihjdil7CiAgICAgIHZhcnMucHVzaCh7aW1nOmN2LCBwc206JzMnfSk7CiAgICAgIHZhciByYz1yZWNvcnRlU3VwZXJpb3IoY3YpOwogICAgICBpZihyYyl7IHZhcnMucHVzaCh7aW1nOnJjLCBwc206JzYnfSk7IH0KICAgIH0KICAgIHZhcnMucHVzaCh7aW1nOmRhdGFVcmwsIHBzbTonMyd9KTsKICAgIHZhciBpPTAsIHRleHRvcz1bXTsKICAgIGZ1bmN0aW9uIHBhc28oKXsKICAgICAgaWYoaT49dmFycy5sZW5ndGgpeyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKHRleHRvcyk7IH0KICAgICAgdmFyIHI9dmFyc1tpKytdOwogICAgICByZXR1cm4gcmVjb25vY2VyQ29uKHIuaW1nLCByLnBzbSkudGhlbihmdW5jdGlvbih0KXsKICAgICAgICBpZih0KXsgdGV4dG9zLnB1c2godCk7IH0KICAgICAgICBpZih0JiZlc0J1ZW5vJiZlc0J1ZW5vKHQpKXsgcmV0dXJuIHRleHRvczsgfQogICAgICAgIHJldHVybiBwYXNvKCk7CiAgICAgIH0pLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiBwYXNvKCk7IH0pOwogICAgfQogICAgcmV0dXJuIHBhc28oKTsKICB9KTsKfQpmdW5jdGlvbiBlbGVnaXJUZXh0byh0ZXh0b3MsIGVzY3JpdG8pewogIHZhciBtZWpvcj0nJywgbWo9LTEsIGk7CiAgZm9yKGk9MDtpPHRleHRvcy5sZW5ndGg7aSsrKXsKICAgIHZhciB0PXRleHRvc1tpXXx8JycsIHA9MDsKICAgIGlmKGVzY3JpdG8pewogICAgICB2YXIgbmM9bm9tYnJlQ29pbmNpZGUoZXNjcml0byx0LGZhbHNlKTsKICAgICAgcD0obmMub2s/MTAwMDowKSsobmMucHVudHx8MCkqMTAwOwogICAgfQogICAgcCs9TWF0aC5taW4oNTAsKHQucmVwbGFjZSgvW15BLVowLTldL2dpLCcnKS5sZW5ndGgpLzMwKTsKICAgIGlmKHA+bWopeyBtaj1wOyBtZWpvcj10OyB9CiAgfQogIHJldHVybiBtZWpvcjsKfQpmdW5jdGlvbiBoYWNlck9jcihkYXRhVXJsKXsKICBpZihjYWNoZU9jcltkYXRhVXJsXSl7IHJldHVybiBQcm9taXNlLnJlc29sdmUoY2FjaGVPY3JbZGF0YVVybF0pOyB9CiAgaWYodHlwZW9mIFRlc3NlcmFjdD09PSd1bmRlZmluZWQnIHx8ICFUZXNzZXJhY3QucmVjb2duaXplKXsKICAgIHJldHVybiBQcm9taXNlLnJlamVjdChuZXcgRXJyb3IoJ09DUiBubyBkaXNwb25pYmxlLCByZXZpc2EgdHUgaW50ZXJuZXQnKSk7CiAgfQogIHJldHVybiBvY3JNdWx0aShkYXRhVXJsLCBmdW5jdGlvbih0KXsgcmV0dXJuICh0fHwnJykucmVwbGFjZSgvW15BLVowLTldL2dpLCcnKS5sZW5ndGg+PTM0OyB9KS50aGVuKGZ1bmN0aW9uKHRleHRvcyl7CiAgICB2YXIgdD1lbGVnaXJUZXh0byh0ZXh0b3MsIG51bGwpOwogICAgY2FjaGVPY3JbZGF0YVVybF09dHx8Jyc7CiAgICByZXR1cm4gdHx8Jyc7CiAgfSk7Cn0KZnVuY3Rpb24gb2NyRnJlbnRlKGRhdGFVcmwpewogIGlmKGNhY2hlT2NyW2RhdGFVcmxdKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZShjYWNoZU9jcltkYXRhVXJsXSk7IH0KICByZXR1cm4gb2NyTXVsdGkoZGF0YVVybCwgZnVuY3Rpb24odCl7IHJldHVybiBub21icmVDb2luY2lkZShFU1QuZXNjcml0bywgdHx8JycsIGZhbHNlKS5vazsgfSkudGhlbihmdW5jdGlvbih0ZXh0b3MpewogICAgdmFyIHQ9ZWxlZ2lyVGV4dG8odGV4dG9zLCBFU1QuZXNjcml0byk7CiAgICBpZih0KXsgY2FjaGVPY3JbZGF0YVVybF09dDsgfQogICAgcmV0dXJuIHR8fCcnOwogIH0pOwp9CgovKiA9PT09PT09PT09PT09PT09PSBiaW9tZXRyaWEgZmFjaWFsID09PT09PT09PT09PT09PT09ICovCnZhciBmYWNlUD1udWxsOwpmdW5jdGlvbiBjYXJnYXJGYWNlQXBpKCl7CiAgaWYoZmFjZVApeyByZXR1cm4gZmFjZVA7IH0KICBmYWNlUD1uZXcgUHJvbWlzZShmdW5jdGlvbihyZXMscmVqKXsKICAgIGZ1bmN0aW9uIGxpc3RvKCl7IHJldHVybiBXLmZhY2VhcGkgJiYgVy5mYWNlYXBpLm5ldHMgJiYgVy5mYWNlYXBpLm5ldHMudGlueUZhY2VEZXRlY3RvciAmJiBXLmZhY2VhcGkubmV0cy5mYWNlUmVjb2duaXRpb25OZXQ7IH0KICAgIGZ1bmN0aW9uIG1vZGVsb3MoYmFzZSl7CiAgICAgIHJldHVybiBQcm9taXNlLmFsbChbCiAgICAgICAgVy5mYWNlYXBpLm5ldHMudGlueUZhY2VEZXRlY3Rvci5sb2FkRnJvbVVyaShiYXNlKSwKICAgICAgICBXLmZhY2VhcGkubmV0cy5mYWNlTGFuZG1hcms2OE5ldC5sb2FkRnJvbVVyaShiYXNlKSwKICAgICAgICBXLmZhY2VhcGkubmV0cy5mYWNlUmVjb2duaXRpb25OZXQubG9hZEZyb21VcmkoYmFzZSkKICAgICAgXSk7CiAgICB9CiAgICBmdW5jdGlvbiBpbmljaWFyKCl7CiAgICAgIHZhciBiYXNlPSdodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvZ2gvanVzdGFkdWRld2hvaGFja3MvZmFjZS1hcGkuanNAMC4yMi4yL3dlaWdodHMnOwogICAgICBtb2RlbG9zKGJhc2UpLnRoZW4oZnVuY3Rpb24oKXsgcmVzKCk7IH0sIGZ1bmN0aW9uKCl7IG1vZGVsb3MoJ2h0dHBzOi8vanVzdGFkdWRld2hvaGFja3MuZ2l0aHViLmlvL2ZhY2UtYXBpLmpzL21vZGVscycpLnRoZW4oZnVuY3Rpb24oKXsgcmVzKCk7IH0sIHJlaik7IH0pOwogICAgfQogICAgaWYobGlzdG8oKSl7IGluaWNpYXIoKTsgcmV0dXJuOyB9CiAgICB2YXIgcz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdzY3JpcHQnKTsKICAgIHMuc3JjPSdodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvbnBtL2ZhY2UtYXBpLmpzQDAuMjIuMi9kaXN0L2ZhY2UtYXBpLm1pbi5qcyc7CiAgICBzLm9ubG9hZD1mdW5jdGlvbigpeyBpZihsaXN0bygpKXsgaW5pY2lhcigpOyB9IGVsc2UgeyByZWoobmV3IEVycm9yKCdmYWNlYXBpIG5vIHF1ZWRvIGxpc3RvJykpOyB9IH07CiAgICBzLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVqKG5ldyBFcnJvcignbm8gc2UgcHVkbyBjYXJnYXIgZWwgdmVyaWZpY2Fkb3IgZmFjaWFsJykpOyB9OwogICAgZG9jdW1lbnQuaGVhZC5hcHBlbmRDaGlsZChzKTsKICB9KTsKICByZXR1cm4gZmFjZVA7Cn0KZnVuY3Rpb24gY29uVGltZW91dChwLCBtcyl7CiAgcmV0dXJuIFByb21pc2UucmFjZShbcCwgbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsgc2V0VGltZW91dChmdW5jdGlvbigpeyByZXMobnVsbCk7IH0sIG1zKTsgfSldKTsKfQpmdW5jdGlvbiBkZXRlY3RhckNhcmFFbihkYXRhVXJsLCBpbnRlbnRvKXsKICByZXR1cm4gY2FyZ2FyRmFjZUFwaSgpLnRoZW4oZnVuY3Rpb24oKXsKICAgIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpewogICAgICB2YXIgaW09bmV3IEltYWdlKCk7CiAgICAgIGltLm9ubG9hZD1mdW5jdGlvbigpewogICAgICAgIHRyeXsKICAgICAgICAgIHZhciB0YW09KGludGVudG89PT0yKT81MTI6MzIwOwogICAgICAgICAgdmFyIG9wdD1uZXcgVy5mYWNlYXBpLlRpbnlGYWNlRGV0ZWN0b3JPcHRpb25zKHtpbnB1dFNpemU6dGFtLCBzY29yZVRocmVzaG9sZDooaW50ZW50bz09PTIpPzAuMzowLjR9KTsKICAgICAgICAgIFcuZmFjZWFwaS5kZXRlY3RTaW5nbGVGYWNlKGltLG9wdCkud2l0aEZhY2VMYW5kbWFya3MoKS53aXRoRmFjZURlc2NyaXB0b3IoKS50aGVuKGZ1bmN0aW9uKHIpewogICAgICAgICAgICBpZihyJiZyLmRldGVjdGlvbil7IHJlcyhyKTsgcmV0dXJuOyB9CiAgICAgICAgICAgIGlmKGludGVudG89PT0yKXsgcmVzKG51bGwpOyByZXR1cm47IH0KICAgICAgICAgICAgcmVzKGRldGVjdGFyQ2FyYUVuKGRhdGFVcmwsKGludGVudG89PT0xKT8yOjEpKTsKICAgICAgICAgIH0pLmNhdGNoKGZ1bmN0aW9uKCl7CiAgICAgICAgICAgIGlmKGludGVudG89PT0yKXsgcmVzKG51bGwpOyByZXR1cm47IH0KICAgICAgICAgICAgcmVzKGRldGVjdGFyQ2FyYUVuKGRhdGFVcmwsKGludGVudG89PT0xKT8yOjEpKTsKICAgICAgICAgIH0pOwogICAgICAgIH1jYXRjaChlKXsgcmVzKG51bGwpOyB9CiAgICAgIH07CiAgICAgIGltLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVzKG51bGwpOyB9OwogICAgICBpbS5zcmM9ZGF0YVVybDsKICAgIH0pOwogIH0pLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiBudWxsOyB9KTsKfQpmdW5jdGlvbiByZWNvcnRlQ2FyYShkYXRhVXJsKXsKICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsKICAgIHZhciBpbT1uZXcgSW1hZ2UoKTsKICAgIGltLm9ubG9hZD1mdW5jdGlvbigpewogICAgICB0cnl7CiAgICAgICAgdmFyIGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7CiAgICAgICAgYy53aWR0aD1NYXRoLm1heCg0MCxNYXRoLnJvdW5kKGltLndpZHRoKjAuNjIpKTsKICAgICAgICBjLmhlaWdodD1NYXRoLm1heCg0MCxNYXRoLnJvdW5kKGltLmhlaWdodCowLjY2KSk7CiAgICAgICAgYy5nZXRDb250ZXh0KCcyZCcpLmRyYXdJbWFnZShpbSwwLDAsaW0ud2lkdGgsTWF0aC5yb3VuZChpbS5oZWlnaHQqMC45KSwwLDAsYy53aWR0aCxjLmhlaWdodCk7CiAgICAgICAgcmVzKGMudG9EYXRhVVJMKCdpbWFnZS9qcGVnJywwLjkpKTsKICAgICAgfWNhdGNoKGUpeyByZXMobnVsbCk7IH0KICAgIH07CiAgICBpbS5vbmVycm9yPWZ1bmN0aW9uKCl7IHJlcyhudWxsKTsgfTsKICAgIGltLnNyYz1kYXRhVXJsOwogIH0pOwp9CmZ1bmN0aW9uIGRldGVjdGFyQ2FyYURvYyhkYXRhVXJsKXsKICBpZighZGF0YVVybCl7IHJldHVybiBQcm9taXNlLnJlc29sdmUobnVsbCk7IH0KICByZXR1cm4gZGV0ZWN0YXJDYXJhRW4oZGF0YVVybCkudGhlbihmdW5jdGlvbihyKXsKICAgIGlmKHImJnIuZGV0ZWN0aW9uKXsgcmV0dXJuIHI7IH0KICAgIHJldHVybiByZWNvcnRlQ2FyYShkYXRhVXJsKS50aGVuKGZ1bmN0aW9uKHJlYyl7CiAgICAgIGlmKCFyZWMpeyByZXR1cm4gbnVsbDsgfQogICAgICByZXR1cm4gZGV0ZWN0YXJDYXJhRW4ocmVjLDEpOwogICAgfSk7CiAgfSk7Cn0KZnVuY3Rpb24gZGlzdEYoYSxiKXsKICB2YXIgcz0wLGk7CiAgZm9yKGk9MDtpPGEubGVuZ3RoO2krKyl7IHZhciBkPWFbaV0tYltpXTsgcys9ZCpkOyB9CiAgcmV0dXJuIE1hdGguc3FydChzKTsKfQoKLyogPT09PT09PT09PT09PT09PT0gZ3VhcmRpYW4gZGUgb3JkZW4gMS0yLTMtNC01ID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHBlcm1pdGlkb0hhc3RhKCl7CiAgdmFyIHA9MTsKICBpZihFU1Qubm9tYnJlT2speyBwPTI7IH0KICBpZihFU1Qubm9tYnJlT2sgJiYgRVNULmZyZW50ZU9rKXsgcD0zOyB9CiAgaWYoRVNULm5vbWJyZU9rICYmIEVTVC5mcmVudGVPayAmJiAoRVNULnJldmVyc29PayB8fCAhRVNULm5lY2VzaXRhUmV2ZXJzbykpeyBwPTQ7IH0KICBpZihFU1Quc2VsZmllT2sgJiYgcD49NCl7IHA9NTsgfQogIHJldHVybiBwOwp9CmZ1bmN0aW9uIG1vc3RyYXJQYXNvKG4pewogIHZhciBpLGVsLCByYj0kKCd6eUJ0blJlcEZvdG8nKTsKICBpZihyYil7IHJiLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgZm9yKGk9MTtpPD01O2krKyl7CiAgICBlbD0kKCdwcycraSk7CiAgICBpZihlbCl7CiAgICAgIGVsLmNsYXNzTmFtZT0ncGFzbycrKGk9PT1uPycgYWN0JzonJyk7CiAgICAgIGVsLnN0eWxlLmRpc3BsYXk9Jyc7CiAgICB9CiAgfQogIHZhciBwcj0kKCdwcm9nJyk7CiAgaWYocHIpeyBwci50ZXh0Q29udGVudD0nUEFTTyAnK24rJyBERSA1JzsgfQogIGlmKEVTVC5wYXNvPj0yICYmIEVTVC5wYXNvPD00ICYmIEVTVC5wYXNvIT09bil7IHRyeXsgcGFyYXJDYW0oRVNULnBhc28pOyB9Y2F0Y2goZSl7fSB9CiAgRVNULnBhc289bjsKICBpZihuPT09NSl7CiAgICB2YXIgYT0kKCdjbGF2ZScpLCBiPSQoJ2NsYXZlMicpOwogICAgaWYoYSl7IGEuZGlzYWJsZWQ9ZmFsc2U7IH0KICAgIGlmKGIpeyBiLmRpc2FibGVkPWZhbHNlOyB9CiAgICB2YXIgcmY9RVNULmZyZW50ZU9rPydGcmVudGUgT0snOidGQUxUQSBGUkVOVEUnOwogICAgdmFyIHJyPSghRVNULm5lY2VzaXRhUmV2ZXJzb3x8RVNULnJldmVyc29Payk/J1JldmVyc28gT0snOidGQUxUQSBSRVZFUlNPJzsKICAgIHZhciBycz1FU1Quc2VsZmllT2s/J1NlbGZpZSB2ZXJpZmljYWRhJzonU0VMRklFIFNJTiBWRVJJRklDQVInOwogICAgdmFyIHRvZG89KEVTVC5mcmVudGVPayYmRVNULnNlbGZpZU9rJiYoIUVTVC5uZWNlc2l0YVJldmVyc298fEVTVC5yZXZlcnNvT2spKTsKICAgIG1zZygnenlSZXN1bWVuNScsJ1ZlcmlmaWNhY2lvbiBmaW5hbDogJytyZisnIHwgJytycisnIHwgJytycysnLiBFc2NyaWJlIHR1IGNsYXZlIDIgdmVjZXMgeSBjcmVhIHR1IFpJRC4nLHRvZG8/JyMwODAnOicjYzAwJyk7CiAgfQogIHRyeXsgdmFyIGFjdD0kKCdwcycrbik7IGlmKGFjdCYmYWN0LnNjcm9sbEludG9WaWV3KXsgYWN0LnNjcm9sbEludG9WaWV3KHtiZWhhdmlvcjonc21vb3RoJyxibG9jazonc3RhcnQnfSk7IH0gfWNhdGNoKGUpe30KfQpmdW5jdGlvbiBhdmFuemFyKG4peyBtb3N0cmFyUGFzbyhuKTsgfQpmdW5jdGlvbiB2ZXJpZmljYXIoKXsKICB0cnl7CiAgICB2YXIgYWN0PWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJy5wYXNvLmFjdCcpOwogICAgdmFyIHJuPWFjdCYmYWN0LmlkP3BhcnNlSW50KFN0cmluZyhhY3QuaWQpLnJlcGxhY2UoJ3BzJywnJyksMTApOjA7CiAgICBpZihybj49MSYmcm48PTUmJnJuIT09RVNULnBhc28peyBFU1QucGFzbz1ybjsgfQogIH1jYXRjaChlKXt9CiAgdHJ5eyB2YWxpZGFyUGFzbzEodHJ1ZSk7IH1jYXRjaChlKXt9CiAgdmFyIHBlcj1wZXJtaXRpZG9IYXN0YSgpOwogIGlmKEVTVC5wYXNvPnBlcil7CiAgICBpZihwZXI9PT0xKXsgbXNnKCd6eUd1YXJkaWEnLCdQYXJhIHNlZ3VpciwgZXNjcmliZSB0dSBub21icmUgeSBlbGlnZSBlbCB0aXBvIGRlIGRvY3VtZW50byBlbiBlbCBwYXNvIDEuJywnI2E2MCcpOyB9CiAgICBlbHNleyBtc2coJ3p5R3VhcmRpYScsJ1RlIHJlZ3Jlc28gYWwgcGFzbyAnK3BlcisnIHBhcmEgc2VndWlyIGVuIG9yZGVuLicsJyNhNjAnKTsgfQogICAgbW9zdHJhclBhc28ocGVyKTsKICB9CiAgdmFyIHNlbD0kKCd0aXBvRG9jJyk7CiAgaWYoc2VsICYmIHNlbC52YWx1ZSAmJiAvcGFzYXBvcnRlfHBhc3Nwb3J0L2kudGVzdCgoc2VsLm9wdGlvbnMmJnNlbC5vcHRpb25zW3NlbC5zZWxlY3RlZEluZGV4XSYmc2VsLm9wdGlvbnNbc2VsLnNlbGVjdGVkSW5kZXhdLnRleHQpfHwnJykpewogICAgdmFyIHBzMz0kKCdwczMnKSwgbnI9JCgnbm90YVJldicpOwogICAgaWYocHMzKXsgcHMzLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgICBpZihucil7IG5yLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgfQp9CnZhciB2dGltZXI9bnVsbDsKZnVuY3Rpb24gcHJvZ3JhbWFyVmVyaWZpY2FyKCl7CiAgaWYodnRpbWVyKXsgcmV0dXJuOyB9CiAgdnRpbWVyPXNldFRpbWVvdXQoZnVuY3Rpb24oKXsgdnRpbWVyPW51bGw7IHRyeXsgdmVyaWZpY2FyKCk7IH1jYXRjaChlKXt9IH0sMTIwKTsKfQp0cnl7CiAgbmV3IE11dGF0aW9uT2JzZXJ2ZXIocHJvZ3JhbWFyVmVyaWZpY2FyKS5vYnNlcnZlKGRvY3VtZW50LmJvZHkse2NoaWxkTGlzdDp0cnVlLHN1YnRyZWU6dHJ1ZSxhdHRyaWJ1dGVzOnRydWUsYXR0cmlidXRlRmlsdGVyOlsnc3R5bGUnLCdjbGFzcycsJ2hpZGRlbicsJ2Rpc2FibGVkJ119KTsKfWNhdGNoKGUpe30KCi8qID09PT09PT09PT09PT09PT09IHBhc28gMTogc29sbyBmb3JtYXRvIGRlbCBub21icmUgKHZhbGlkYSBTT0xPIGFsIGNvbnRpbnVhciwgbnVuY2EgbWllbnRyYXMgZXNjcmliZXMpID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHZhbGlkYXJQYXNvMShzaWxlbmNpb3NvKXsKICB2YXIgaW5wPSQoJ25vbWJyZScpLCBzZWw9JCgndGlwb0RvYycpOwogIHZhciB2PWlucD8oaW5wLnZhbHVlfHwnJykudHJpbSgpOicnOwogIHZhciBsZXRyYXM9L15bQS1aYS16XHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxXHUwMEUxXHUwMEU5XHUwMEVEXHUwMEYzXHUwMEZBXHUwMEZDXHUwMEYxXSsoIFtBLVphLXpcdTAwQzFcdTAwQzlcdTAwQ0RcdTAwRDNcdTAwREFcdTAwRENcdTAwRDFcdTAwRTFcdTAwRTlcdTAwRURcdTAwRjNcdTAwRkFcdTAwRkNcdTAwRjFdKykqJC8udGVzdCh2KTsKICB2YXIgbnA9dj92LnNwbGl0KC9ccysvKS5sZW5ndGg6MDsKICB2YXIgb2s9KHYubGVuZ3RoPj01ICYmIGxldHJhcyAmJiBucD49Mik7CiAgdmFyIHQ9Y2xhc2lmaWNhclRpcG8oKTsKICBFU1QudGlwbz10Lms7CiAgRVNULm5lY2VzaXRhUmV2ZXJzbz10LnJldmVyc287CiAgdmFyIHRpcG9Paz0hIShzZWwgJiYgU3RyaW5nKHNlbC52YWx1ZXx8JycpLmxlbmd0aD4wKTsKICBFU1Qubm9tYnJlT2s9b2s7CiAgRVNULmVzY3JpdG89bm9ybSh2KTsKICBpZihzaWxlbmNpb3NvKXsgcmV0dXJuIG9rJiZ0aXBvT2s7IH0KICBpZihpbnApeyBpbnAuc3R5bGUuYm9yZGVyQ29sb3I9b2s/Jyc6JyNjMDAnOyB9CiAgdmFyIG1ubz0nJzsKICBpZighb2speyBtbm89dj8nRXNjcmliZSB0dSBub21icmUgeSB0dSBhcGVsbGlkbyAoc29sbyBsZXRyYXMgeSBlc3BhY2lvczsgc2lydmUgY29uIDEgbyAyIG5vbWJyZXMgeSAxIG8gMiBhcGVsbGlkb3MpLic6J0VzY3JpYmUgdHUgbm9tYnJlIHkgdHUgYXBlbGxpZG8gcGFyYSBjb250aW51YXIuJzsgfQogIG1zZygnenlFcnJOb21icmUnLG1ubyxtbm8/JyNjMDAnOicnKTsKICB2YXIgbXRpPXRpcG9Paz8nJzonRWxpZ2UgdHUgdGlwbyBkZSBkb2N1bWVudG8gZW4gbGEgbGlzdGEuJzsKICBtc2coJ3p5RXJyVGlwbycsbXRpLG10aT8nI2MwMCc6JycpOwogIHJldHVybiBvayYmdGlwb09rOwp9CmZ1bmN0aW9uIGxpbXBpYXJFcnJvcmVzUGFzbzEoKXsKICB2YXIgZTE9JCgnenlFcnJOb21icmUnKTsgaWYoZTEgJiYgZTEudGV4dENvbnRlbnQpeyBlMS50ZXh0Q29udGVudD0nJzsgZTEuc3R5bGUuY29sb3I9Jyc7IH0KICB2YXIgZTI9JCgnenlFcnJUaXBvJyk7IGlmKGUyICYmIGUyLnRleHRDb250ZW50KXsgZTIudGV4dENvbnRlbnQ9Jyc7IGUyLnN0eWxlLmNvbG9yPScnOyB9CiAgdmFyIGlucD0kKCdub21icmUnKTsgaWYoaW5wICYmIGlucC5zdHlsZS5ib3JkZXJDb2xvcil7IGlucC5zdHlsZS5ib3JkZXJDb2xvcj0nJzsgfQp9CmZ1bmN0aW9uIHJlc2V0ZWFyRG9jdW1lbnRvKCl7CiAgRVNULmZyZW50ZU9rPWZhbHNlOyBFU1QucmV2ZXJzb09rPWZhbHNlOyBFU1Quc2VsZmllT2s9ZmFsc2U7IEVTVC5pbnRlbnRvcz0zOyBFU1QuY2FyYURvYz1udWxsOwp9CgovKiA9PT09PT09PT09PT09PT09PSBwYXNvIDI6IGZyZW50ZSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBmYWxsb0xlY3R1cmFGcmVudGUobSl7CiAgYnVzeShmYWxzZSk7CiAgbXNnKCdzdEYnLG0rJyBUb2NhIENBUFRVUkFSIGRlIG51ZXZvLCBjb24gYnVlbmEgbHV6IHkgc2luIGJyaWxsby4nLCcjYzAwJyk7Cn0KZnVuY3Rpb24gYXZhbnphclRyYXNGcmVudGUoKXsKICBhdmFuemFyKEVTVC5uZWNlc2l0YVJldmVyc28/Mzo0KTsKICBpZihFU1QubmVjZXNpdGFSZXZlcnNvKXsKICAgIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsgdHJ5eyBhYnJpckNhbSgnMycsJ2Vudmlyb25tZW50Jywnc3RBJywnYkNhcEEnKS5jYXRjaChmdW5jdGlvbigpe30pOyB9Y2F0Y2goZSl7fSB9LDUwMCk7CiAgfQp9CmZ1bmN0aW9uIGFjZXB0YXJGcmVudGVDb25maXJtYWRvKHRleHRvT0NSLCBsZWN0dXJhKXsKICBFU1QuZnJlbnRlT2s9dHJ1ZTsKICBFU1QuZnJlbnRlVGV4dG89KHRleHRvT0NSfHwnJykrJ1xuTEVDVFVSQSBDT05GSVJNQURBOiAnK2xlY3R1cmE7CiAgb2N1bHRhckNvbmZpcm1hY2lvbkxlY3R1cmEoKTsKICBtc2coJ3N0RicsJ1x1MjcxMyBGcmVudGUgY29uZmlybWFkbzogJytsZWN0dXJhLCcjMDgwJyk7CiAgYXZhbnphclRyYXNGcmVudGUoKTsKfQpmdW5jdGlvbiBhYnJpckNvbmZpcm1hY2lvbkxlY3R1cmEodGV4dG9PQ1IsIGxlaWRvKXsKICB0cnl7CiAgICB2YXIgY29udD0kKCd6eUxlY0JveCcpOwogICAgaWYoIWNvbnQpewogICAgICBjb250PWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgICBjb250LmlkPSd6eUxlY0JveCc7CiAgICAgIGNvbnQuc3R5bGUuY3NzVGV4dD0nYm9yZGVyOjFweCBzb2xpZCAjN2MzYWVkO2JvcmRlci1yYWRpdXM6MTJweDtwYWRkaW5nOjEwcHg7bWFyZ2luOjhweCAwO2JhY2tncm91bmQ6IzE3MTIyYjsnOwogICAgICB2YXIgcHMyPSQoJ3BzMicpOwogICAgICBpZihwczImJnBzMi5pbnNlcnRCZWZvcmUpeyBwczIuaW5zZXJ0QmVmb3JlKGNvbnQscHMyLmZpcnN0Q2hpbGQpOyB9IGVsc2UgeyBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKGNvbnQpOyB9CiAgICAgIHZhciB0MT1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgICAgdDEuc3R5bGUuY3NzVGV4dD0nZm9udC1zaXplOjEzcHg7Y29sb3I6I2U2ZTZmYTttYXJnaW4tYm90dG9tOjZweDtsaW5lLWhlaWdodDoxLjM1Oyc7CiAgICAgIHQxLnRleHRDb250ZW50PSdObyBwdWRlIGNvbmZpcm1hciBlbCBub21icmUgY29uIHNlZ3VyaWRhZC4gRXN0byBmdWUgbG8gcXVlIExFXHUwMENEIGRlbCBkb2N1bWVudG8uIENvcnJpZ2UgU09MTyBsYXMgbGV0cmFzIG1hbCBsZVx1MDBFRGRhcyB5IGNvbmZpcm1hOic7CiAgICAgIGNvbnQuYXBwZW5kQ2hpbGQodDEpOwogICAgICB2YXIgaW5wPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2lucHV0Jyk7CiAgICAgIGlucC5pZD0nenlMZWNJbic7CiAgICAgIGlucC50eXBlPSd0ZXh0JzsKICAgICAgaW5wLmF1dG9jb21wbGV0ZT0nb2ZmJzsKICAgICAgaW5wLnBsYWNlaG9sZGVyPSdOb21icmUgbGVpZG8gZGVsIGRvY3VtZW50byc7CiAgICAgIGlucC5zdHlsZS5jc3NUZXh0PSd3aWR0aDoxMDAlO2JveC1zaXppbmc6Ym9yZGVyLWJveDtwYWRkaW5nOjEwcHg7Ym9yZGVyLXJhZGl1czoxMHB4O2JvcmRlcjoxcHggc29saWQgIzQ0NDtiYWNrZ3JvdW5kOiMwZTBiMWU7Y29sb3I6I2ZmZjtmb250LXNpemU6MTVweDt0ZXh0LXRyYW5zZm9ybTp1cHBlcmNhc2U7bWFyZ2luLWJvdHRvbTo4cHg7JzsKICAgICAgY29udC5hcHBlbmRDaGlsZChpbnApOwogICAgICB2YXIgYjE9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnYnV0dG9uJyk7CiAgICAgIGIxLmlkPSd6eUxlY0J0bic7CiAgICAgIGIxLnR5cGU9J2J1dHRvbic7CiAgICAgIGIxLnRleHRDb250ZW50PSdDb25maXJtYXI6IGFzXHUwMEVEIHNlIGxlZSBlbiBtaSBkb2N1bWVudG8nOwogICAgICBiMS5zdHlsZS5jc3NUZXh0PSdkaXNwbGF5OmJsb2NrO3dpZHRoOjEwMCU7cGFkZGluZzoxMXB4O2JvcmRlcjowO2JvcmRlci1yYWRpdXM6MTBweDtiYWNrZ3JvdW5kOiM3YzNhZWQ7Y29sb3I6I2ZmZjtmb250LXNpemU6MTRweDtmb250LXdlaWdodDo2MDA7bWFyZ2luLWJvdHRvbTo2cHg7JzsKICAgICAgY29udC5hcHBlbmRDaGlsZChiMSk7CiAgICAgIHZhciBiMj1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdidXR0b24nKTsKICAgICAgYjIuaWQ9J3p5TGVjUmVwJzsKICAgICAgYjIudHlwZT0nYnV0dG9uJzsKICAgICAgYjIudGV4dENvbnRlbnQ9J01lam9yIHJlcGl0byBsYSBmb3RvJzsKICAgICAgYjIuc3R5bGUuY3NzVGV4dD0nZGlzcGxheTpibG9jazt3aWR0aDoxMDAlO3BhZGRpbmc6MTBweDtib3JkZXI6MDtib3JkZXItcmFkaXVzOjEwcHg7YmFja2dyb3VuZDojMmMyYzNjO2NvbG9yOiNkZGQ7Zm9udC1zaXplOjEzcHg7JzsKICAgICAgY29udC5hcHBlbmRDaGlsZChiMik7CiAgICAgIHZhciBtPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgICBtLmlkPSd6eUxlY01zZyc7CiAgICAgIG0uc3R5bGUuY3NzVGV4dD0nZm9udC1zaXplOjEzcHg7bWFyZ2luLXRvcDo2cHg7bGluZS1oZWlnaHQ6MS4zNTsnOwogICAgICBjb250LmFwcGVuZENoaWxkKG0pOwogICAgICBiMS5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICB2YXIgdj1ub3JtKCQoJ3p5TGVjSW4nKT8kKCd6eUxlY0luJykudmFsdWU6JycpOwogICAgICAgICAgdmFyIG9jclRva3M9dG9rZW5zTm9tYnJlRGUoY29udC5fX29jcnx8JycpOwogICAgICAgICAgaWYoIXRva2Vuc0RlKHYpLmxlbmd0aCl7IG1zZygnenlMZWNNc2cnLCdFc2NyaWJlIGxvIHF1ZSBzZSBsZWUgZW4gZWwgZG9jdW1lbnRvIChzb2xvIGxldHJhcykuJywnI2MwMCcpOyByZXR1cm47IH0KICAgICAgICAgIGlmKCFlZGljaW9uQWNlcHRhYmxlKHYsIG9jclRva3MpKXsKICAgICAgICAgICAgbXNnKCd6eUxlY01zZycsJ0hheSBwYWxhYnJhcyBxdWUgTk8gc2UgcGFyZWNlbiBhIGxvIGxlXHUwMEVEZG8uIENvcnJpZ2Ugc29sbyBsYXMgbGV0cmFzIGVxdWl2b2NhZGFzLCBvIHJlcGl0ZSBsYSBmb3RvIGNvbiBtZWpvciBsdXouJywnI2MwMCcpOwogICAgICAgICAgICByZXR1cm47CiAgICAgICAgICB9CiAgICAgICAgICB2YXIgbmM9bm9tYnJlQ29pbmNpZGUoRVNULmVzY3JpdG8sIHYsIGZhbHNlKTsKICAgICAgICAgIGlmKCFuYy5vayl7CiAgICAgICAgICAgIG1zZygnenlMZWNNc2cnLCdDb24gZXNhIGxlY3R1cmEgdHUgbm9tYnJlIHNpZ3VlIHNpbiBjb2luY2lkaXIuIFJldmlzYSB0dSBub21icmUgZGVsIHBhc28gMSBvIHJlcGl0ZSBsYSBmb3RvLicsJyNjMDAnKTsKICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgfQogICAgICAgICAgYWNlcHRhckZyZW50ZUNvbmZpcm1hZG8oY29udC5fX29jcnx8JycsIHYpOwogICAgICAgIH1jYXRjaChlKXt9CiAgICAgIH0pOwogICAgICBiMi5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICBvY3VsdGFyQ29uZmlybWFjaW9uTGVjdHVyYSgpOwogICAgICAgICAgbXNnKCdzdEYnLCdUb2NhIENBUFRVUkFSIHkgcmVwaXRlIGxhIGZvdG86IGJ1ZW5hIGx1eiwgc2luIGJyaWxsbywgcXVlIGVsIGRvY3VtZW50byBsbGVuZSBlbCBtYXJjby4nLCcjYTYwJyk7CiAgICAgICAgfWNhdGNoKGUpe30KICAgICAgfSk7CiAgICB9CiAgICBjb250Ll9fb2NyPXRleHRvT0NSfHwnJzsKICAgIHZhciBpbnAyPSQoJ3p5TGVjSW4nKTsKICAgIGlmKGlucDIpeyBpbnAyLnZhbHVlPShsZWlkb3x8JycpOyB9CiAgICBjb250LnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsKICAgIG1zZygnenlMZWNNc2cnLCcnLCcnKTsKICAgIG1zZygnc3RGJywnUmV2aXNhIGFiYWpvIGxvIHF1ZSBsZVx1MDBFRCBkZWwgZG9jdW1lbnRvOiBwdWVkZXMgY29ycmVnaXIgbGFzIGxldHJhcyBtYWwgbGVcdTAwRURkYXMuJywnI2E2MCcpOwogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gb2N1bHRhckNvbmZpcm1hY2lvbkxlY3R1cmEoKXsKICB2YXIgYz0kKCd6eUxlY0JveCcpOwogIGlmKGMpeyBjLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9Cn0KZnVuY3Rpb24gcHJvY2VzYXJGcmVudGUoZGF0YVVybCl7CiAgRVNULmZyZW50ZU9rPWZhbHNlOwogIEVTVC5jYXJhRG9jPW51bGw7CiAgb2N1bHRhckNvbmZpcm1hY2lvbkxlY3R1cmEoKTsKICBidXN5KHRydWUpOwogIG1zZygnc3RGJywnTGV5ZW5kbyBlbCBkb2N1bWVudG8gKHBhc2UgMSBkZSAzKS4uLicsJycpOwogIEVTVC5mcmVudGVJbWc9ZGF0YVVybDsKICBzaG93SW1nKCdwRicsZGF0YVVybCk7CiAgdmFyIHBDYXJhPWNvblRpbWVvdXQoZGV0ZWN0YXJDYXJhRW4oZGF0YVVybCksMTUwMDApOwogIHZhciBwVHh0PW9jckZyZW50ZShkYXRhVXJsKS5jYXRjaChmdW5jdGlvbihlKXsgcmV0dXJuICdPQ1JfRVJSOicrKGUmJmUubWVzc2FnZT9lLm1lc3NhZ2U6JycpOyB9KTsKICBQcm9taXNlLmFsbChbcENhcmEscFR4dF0pLnRoZW4oZnVuY3Rpb24ocil7CiAgICB2YXIgY2FyYT1yWzBdLCB0ZXh0bz1yWzFdfHwnJzsKICAgIGlmKHRleHRvLmluZGV4T2YoJ09DUl9FUlI6Jyk9PT0wKXsgZmFsbG9MZWN0dXJhRnJlbnRlKCdObyBwdWRlIGxlZXIgZWwgZG9jdW1lbnRvICgnK3RleHRvLnNsaWNlKDgpKycpLicpOyByZXR1cm47IH0KICAgIGlmKHRleHRvLnJlcGxhY2UoL1xzL2csJycpLmxlbmd0aDwxNSl7IGZhbGxvTGVjdHVyYUZyZW50ZSgnTm8gbGVcdTAwRUQgc3VmaWNpZW50ZSB0ZXh0by4gQWNcdTAwRTlyY2F0ZSwgYnVlbmEgbHV6LCBxdWUgZWwgZG9jdW1lbnRvIGxsZW5lIGVsIG1hcmNvLicpOyByZXR1cm47IH0KICAgIHZhciBsYWRvPWRldGVjdGFyTGFkbyh0ZXh0bywhIShjYXJhJiZjYXJhLmRldGVjdGlvbikpOwogICAgaWYobGFkbz09PSdyZXZlcnNvJyl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBtc2coJ3N0RicsJ0VzbyBlcyBlbCBSRVZFUlNPIChzZSB2ZW4gZGlyZWNjaW9uZXMgbyBsYSB6b25hIE1SWikuIE5lY2VzaXRvIGVsIEZSRU5URTogZG9uZGUgZXN0XHUwMEUxIHR1IEZPVE8geSB0dXMgZGF0b3MuIFZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgaWYobGFkbyE9PSdmcmVudGUnICYmICEoY2FyYSYmY2FyYS5kZXRlY3Rpb24pKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RGJywnTm8gcHVkZSBjb25maXJtYXIgcXVlIHNlYSBlbCBGUkVOVEUuIEFzZWdcdTAwRkFyYXRlIGRlIHF1ZSBzZSB2ZWEgdHUgZm90byB5IHR1cyBkYXRvcywgc2luIGJyaWxsbywgeSB2dWVsdmUgYSBjYXB0dXJhci4nLCcjYzAwJyk7CiAgICAgIHJldHVybjsKICAgIH0KICAgIGlmKGNhcmEmJmNhcmEuZGV0ZWN0aW9uJiZjYXJhLmRlc2NyaXB0b3IpeyBFU1QuY2FyYURvYz1jYXJhLmRlc2NyaXB0b3I7IH0KICAgIHZhciBuYz1ub21icmVDb2luY2lkZShFU1QuZXNjcml0byx0ZXh0byxtcnpMaW5lYXModGV4dG8pLmxlbmd0aD4wKTsKICAgIGlmKG5jLmhheSAmJiAhbmMub2spewogICAgICBidXN5KGZhbHNlKTsKICAgICAgYWJyaXJDb25maXJtYWNpb25MZWN0dXJhKHRleHRvLCBuYy5sZWlkbyk7CiAgICAgIHJldHVybjsKICAgIH0KICAgIEVTVC5mcmVudGVPaz10cnVlOwogICAgRVNULmZyZW50ZVRleHRvPXRleHRvOwogICAgbXNnKCdzdEYnLCdcdTI3MTMgRnJlbnRlIGxlXHUwMEVEZG8gY29ycmVjdGFtZW50ZS4nKyhuYy5vaz8oJyBOb21icmU6ICcrbmMubGVpZG8rJy4nKTonJyksJyMwODAnKTsKICAgIGJ1c3koZmFsc2UpOwogICAgYXZhbnphclRyYXNGcmVudGUoKTsKICB9KTsKfQpmdW5jdGlvbiBub21icmVOb0NvaW5jaWRlTXNnKHR4dCl7CiAgcmVzZXRlYXJEb2N1bWVudG8oKTsKICB2YXIgbm49JCgnbm9tYnJlTm9Db2luY2lkZScpOwogIGlmKG5uKXsgbm4udGV4dENvbnRlbnQ9dHh0OyBubi5zdHlsZS5kaXNwbGF5PSdibG9jayc7IG5uLnN0eWxlLmNvbG9yPScjYzAwJzsgfQogIG1zZygnc3RBJywnJyk7IG1zZygnc3RGJywnJyk7CiAgbXNnKCd6eUVyck5vbWJyZScsdHh0KycgU2kgdHUgbm9tYnJlIGVzdFx1MDBFMSBiaWVuIGVzY3JpdG8sIHRhbWJpXHUwMEU5biBwdWVkZXMgcmVwZXRpciBsYSBmb3RvIGRlbCBkb2N1bWVudG8gY29uIGJ1ZW5hIGx1eiB5IHNpbiBicmlsbG8uJywnI2MwMCcpOwogIGF2YW56YXIoMSk7CiAgYm90b25SZXBldGlyRm90bygpOwp9CmZ1bmN0aW9uIGJvdG9uUmVwZXRpckZvdG8oKXsKICB2YXIgYj0kKCd6eUJ0blJlcEZvdG8nKTsKICBpZighYil7CiAgICBiPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2J1dHRvbicpOwogICAgYi5pZD0nenlCdG5SZXBGb3RvJzsKICAgIGIudHlwZT0nYnV0dG9uJzsKICAgIGIudGV4dENvbnRlbnQ9J1JlcGV0aXIgbGEgZm90byBkZWwgZG9jdW1lbnRvJzsKICAgIGIuc3R5bGUuY3NzVGV4dD0nZGlzcGxheTpibG9jazttYXJnaW46OHB4IDA7cGFkZGluZzoxMXB4IDE0cHg7Ym9yZGVyOjA7Ym9yZGVyLXJhZGl1czoxMHB4O2JhY2tncm91bmQ6IzdjM2FlZDtjb2xvcjojZmZmO2ZvbnQtc2l6ZToxNHB4O2ZvbnQtd2VpZ2h0OjYwMDt3aWR0aDoxMDAlOyc7CiAgICBiLmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbigpeyB0cnl7IGF2YW56YXIoMik7IH1jYXRjaChlKXt9IH0pOwogICAgdmFyIGFuY2xhPSQoJ3p5RXJyTm9tYnJlJyk7CiAgICBpZihhbmNsYSYmYW5jbGEucGFyZW50Tm9kZSl7IGFuY2xhLnBhcmVudE5vZGUuaW5zZXJ0QmVmb3JlKGIsYW5jbGEubmV4dFNpYmxpbmcpOyB9CiAgICBlbHNleyBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKGIpOyB9CiAgfQogIGIuc3R5bGUuZGlzcGxheT0nYmxvY2snOwp9CgovKiA9PT09PT09PT09PT09PT09PSBwYXNvIDM6IHJldmVyc28gPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gcmV2ZXJzb0FjZXB0YWJsZSh0ZXh0byl7CiAgdmFyIHQ9KHRleHRvfHwnJykudG9VcHBlckNhc2UoKTsKICBpZigodC5tYXRjaCgvPC9nKXx8W10pLmxlbmd0aD49Nil7IHJldHVybiB0cnVlOyB9CiAgaWYoL1BERjRJPzcvLnRlc3QodC5yZXBsYWNlKC9ccy9nLCcnKSkpeyByZXR1cm4gdHJ1ZTsgfQogIHZhciBmdWVydGVzPVsnRE9NSUNJTElPJywnRElSRUNDSU9OJywnRElSRUNDSVx1MDBEM04nLCdDT0xPTklBJywnQkFSUklPJywnUkVTSURFTkNJQScsJ0NBU0VSSU8nLCdDQU5UT04nLCdBTERFQScsJ09CU0VSVkFDSU9OJywnT0JTRVJWQUNJXHUwMEQzTicsJ0VTVEFETyBDSVZJTCcsJ0RPTkFOVEUnLCdHUlVQTyBTQU5HJywnVElQTyBERSBTQU5HJywnRU5ET1JTRU1FTlQnLCdSRVNUUklDVElPTicsJ0FERFJFU1MnXTsKICB2YXIgaSxjPTA7CiAgZm9yKGk9MDtpPGZ1ZXJ0ZXMubGVuZ3RoO2krKyl7IGlmKHQuaW5kZXhPZihmdWVydGVzW2ldKT49MCl7IGMrKzsgfSB9CiAgaWYoYz49Mil7IHJldHVybiB0cnVlOyB9CiAgaWYoRVNULnRpcG89PT0ndXNhJyAmJiAvXGIoSVNTfEVYUHxERHw0RHw0RnxSRVNUfEVORHxETClcYi8udGVzdCh0KSl7IHJldHVybiB0cnVlOyB9CiAgcmV0dXJuIGZhbHNlOwp9CmZ1bmN0aW9uIHByb2Nlc2FyUmV2ZXJzbyhkYXRhVXJsKXsKICBFU1QucmV2ZXJzb09rPWZhbHNlOwogIGJ1c3kodHJ1ZSk7CiAgbXNnKCdzdEEnLCdMZXllbmRvIGVsIHJldmVyc28uLi4nLCcnKTsKICBFU1QucmV2ZXJzb0ltZz1kYXRhVXJsOwogIHNob3dJbWcoJ3BBJyxkYXRhVXJsKTsKICBoYWNlck9jcihkYXRhVXJsKS50aGVuKGZ1bmN0aW9uKHRleHRvKXsKICAgIGlmKHRleHRvLnJlcGxhY2UoL1xzL2csJycpLmxlbmd0aDwxMCAmJiAhcmV2ZXJzb0FjZXB0YWJsZSh0ZXh0bykpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbXNnKCdzdEEnLCdObyBsZVx1MDBFRCBzdWZpY2llbnRlIHRleHRvIGVuIGVsIHJldmVyc28uIEFjXHUwMEU5cmNhdGUsIGJ1ZW5hIGx1eiwgeSB2dWVsdmUgYSBjYXB0dXJhci4nLCcjYzAwJyk7CiAgICAgIHJldHVybjsKICAgIH0KICAgIHZhciBjYXJhUGVuZD1udWxsOwogICAgdmFyIGxhZG89ZGV0ZWN0YXJMYWRvKHRleHRvLGZhbHNlKTsKICAgIGlmKGxhZG89PT0nZnJlbnRlJyl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBtc2coJ3N0QScsJ0VzbyBlcyBlbCBGUkVOVEUgKHNlIHZlIGxhIGZvdG8geSBsb3MgZGF0b3MpLiBOZWNlc2l0byBlbCBSRVZFUlNPOiBkaXJlY2Npb25lcyBvIGxhIHpvbmEgTVJaLiBWdWVsdmUgYSBjYXB0dXJhci4nLCcjYzAwJyk7CiAgICAgIHJldHVybjsKICAgIH0KICAgIGlmKGxhZG8hPT0ncmV2ZXJzbycgJiYgIXJldmVyc29BY2VwdGFibGUodGV4dG8pKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RBJywnTm8gcHVkZSBjb25maXJtYXIgcXVlIHNlYSBlbCBSRVZFUlNPLiBNdWVzdHJhIGxhcyBkaXJlY2Npb25lcyBvIGxhIHpvbmEgZGUgcmF5aXRhcy9NUlogeSB2dWVsdmUgYSBjYXB0dXJhci4nLCcjYzAwJyk7CiAgICAgIHJldHVybjsKICAgIH0KICAgIHZhciBuYz1ub21icmVDb2luY2lkZShFU1QuZXNjcml0byx0ZXh0byxtcnpMaW5lYXModGV4dG8pLmxlbmd0aD4wKTsKICAgIGlmKG5jLmhheSAmJiAhbmMub2spewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbm9tYnJlTm9Db2luY2lkZU1zZygnRWwgbm9tYnJlIGRlbCBkb2N1bWVudG8gKCcrbmMubGVpZG8rJykgbm8gY29pbmNpZGUgY29uIGxvIHF1ZSBlc2NyaWJpc3RlLiBDb3JyaWdlIHR1IG5vbWJyZSBlbiBlbCBwYXNvIDE6IHB1ZWRlIHRlbmVyIDEgbyAyIG5vbWJyZXMgeSAxIG8gMiBhcGVsbGlkb3MuJyk7CiAgICAgIHJldHVybjsKICAgIH0KICAgIEVTVC5yZXZlcnNvT2s9dHJ1ZTsKICAgIEVTVC5yZXZlcnNvVGV4dG89dGV4dG87CiAgICBtc2coJ3N0QScsJ1x1MjcxMyBSZXZlcnNvIGxlXHUwMEVEZG8gY29ycmVjdGFtZW50ZS4nLCcjMDgwJyk7CiAgICBidXN5KGZhbHNlKTsKICAgIGF2YW56YXIoNCk7CiAgICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IHRyeXsgYWJyaXJDYW0oJzQnLCd1c2VyJywnc3RWJywnYlNlbGZpZScpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH1jYXRjaChlKXt9IH0sNTAwKTsKICB9KS5jYXRjaChmdW5jdGlvbihlKXsKICAgIGJ1c3koZmFsc2UpOwogICAgbXNnKCdzdEEnLCdFcnJvciBsZXllbmRvIGVsIHJldmVyc286ICcrKGUmJmUubWVzc2FnZT9lLm1lc3NhZ2U6JycpKycuIFZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICB9KTsKfQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyA0OiBzZWxmaWUgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gcHJvY2VzYXJTZWxmaWUoKXsKICBFU1Quc2VsZmllT2s9ZmFsc2U7CiAgdmFyIGltZz1jYXB0dXJhclZpZGVvKCc0JywxMDQ4KTsKICBpZighaW1nKXsgbXNnKCdzdFYnLCdQcmltZXJvIGFicmUgbGEgY1x1MDBFMW1hcmEgeSBwb24gdHUgY2FyYSBkZW50cm8gZGVsIG1hcmNvLicsJyNjMDAnKTsgcmV0dXJuOyB9CiAgRVNULnNlbGZpZUltZz1pbWc7CiAgc2hvd0ltZygncFMnLGltZyk7CiAgYnVzeSh0cnVlKTsKICBtc2coJ3N0VicsJ0NvbXBhcmFuZG8gdHUgY2FyYSBjb24gbGEgZGVsIGRvY3VtZW50by4uLicsJycpOwogIHZhciBwRG9jPUVTVC5jYXJhRG9jP1Byb21pc2UucmVzb2x2ZShFU1QuY2FyYURvYyk6Y29uVGltZW91dChkZXRlY3RhckNhcmFEb2MoRVNULmZyZW50ZUltZ3x8RVNULnJldmVyc29JbWd8fCcnKSwxNTAwMCkudGhlbihmdW5jdGlvbihyKXsgcmV0dXJuIChyJiZyLmRldGVjdGlvbiYmci5kZXNjcmlwdG9yKT9yLmRlc2NyaXB0b3I6bnVsbDsgfSk7CiAgdmFyIHBTZWw9Y29uVGltZW91dChkZXRlY3RhckNhcmFFbihpbWcpLDE1MDAwKTsKICBQcm9taXNlLmFsbChbcERvYyxwU2VsXSkudGhlbihmdW5jdGlvbihyKXsKICAgIHZhciBkRG9jPXJbMF0sIGVuU2VsPXJbMV07CiAgICBpZighZERvYyl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBmYWxsb1NlbGZpZSgnTm8gcHVkZSB2ZXIgYmllbiBsYSBjYXJhIGVuIGxhIGZvdG8gZGVsIGRvY3VtZW50by4gVmFtb3MgYSByZXBldGlyIGxhIGZvdG8gZGVsIGRvY3VtZW50byBjb24gbWVqb3IgbHV6LicpOwogICAgICByZXR1cm47CiAgICB9CiAgICBpZighZW5TZWwgfHwgIWVuU2VsLmRldGVjdGlvbil7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBmYWxsb1NlbGZpZSgnTm8gcHVkZSB2ZXIgdHUgY2FyYSBlbiBsYSBzZWxmaWUuIE1lam9yIGxhIGx1eiwgcXVcdTAwRUR0YXRlIGdvcnJhIG8gbGVudGVzIG9zY3Vyb3MuJyk7CiAgICAgIHJldHVybjsKICAgIH0KICAgIHZhciBkPWRpc3RGKGREb2MsZW5TZWwuZGVzY3JpcHRvcik7CiAgICBpZihkPD0wLjYwKXsKICAgICAgRVNULnNlbGZpZU9rPXRydWU7CiAgICAgIEVTVC5pbnRlbnRvcz0zOwogICAgICBtc2coJ3N0VicsJ1x1MjcxMyBWZXJpZmljYWNpXHUwMEYzbiBmYWNpYWwgc3VwZXJhZGEuIFBhc2FuZG8gYSB0dSBjbGF2ZS4nLCcjMDgwJyk7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBhdmFuemFyKDUpOwogICAgfWVsc2V7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBmYWxsb1NlbGZpZSgnVHUgY2FyYSBubyBjb2luY2lkZSBjb24gbGEgZGVsIGRvY3VtZW50byAoZGlzdGFuY2lhICcrZC50b0ZpeGVkKDIpKycpLicpOwogICAgfQogIH0pLmNhdGNoKGZ1bmN0aW9uKGUpewogICAgYnVzeShmYWxzZSk7CiAgICBmYWxsb1NlbGZpZSgnRWwgdmVyaWZpY2Fkb3IgZmFjaWFsIG5vIGNhcmdcdTAwRjM6ICcrKGUmJmUubWVzc2FnZT9lLm1lc3NhZ2U6JycpKycuIFJldmlzYSB0dSBpbnRlcm5ldCB5IHJlaW50ZW50YS4nKTsKICB9KTsKfQpmdW5jdGlvbiBmYWxsb1NlbGZpZShtKXsKICBFU1QuaW50ZW50b3MtLTsKICBpZihFU1QuaW50ZW50b3M8PTApewogICAgRVNULmludGVudG9zPTM7CiAgICBFU1Quc2VsZmllT2s9ZmFsc2U7CiAgICBtc2coJ3N0VicsJ1NlIGFnb3Rhcm9uIGxvcyAzIGludGVudG9zLiBWb2x2ZW1vcyBhIGxhIGZvdG8gZGVsIGRvY3VtZW50bzsgcmV2XHUwMEVEc2FsYSB5IHZ1ZWx2ZSBhIHRvbWFybGEsIHkgc2VndWltb3MgZW4gb3JkZW4gcG9yIGxvcyBwYXNvcy4nLCcjYTYwJyk7CiAgICBhdmFuemFyKDIpOwogIH1lbHNlewogICAgbXNnKCdzdFYnLCdcdTI3MTcgJyttKycgVGUgcXVlZGFuICcrRVNULmludGVudG9zKycgaW50ZW50byhzKS4gVG9jYSBDQVBUVVJBUiBkZSBudWV2by4nLCcjYzAwJyk7CiAgfQp9CgovKiA9PT09PT09PT09PT09PT09PSBwYXNvIDU6IGNsYXZlICsgWklEID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHZhbGlkYXJDbGF2ZXMoKXsKICB2YXIgYT0kKCdjbGF2ZScpLCBiPSQoJ2NsYXZlMicpLCBkPSQoJ2Rlc2dsb3NlJyk7CiAgaWYoIWF8fCFiKXsgcmV0dXJuOyB9CiAgaWYoIWIudmFsdWUpeyBpZihkKXsgZC50ZXh0Q29udGVudD0nJzsgfSByZXR1cm47IH0KICBpZihhLnZhbHVlPT09Yi52YWx1ZSl7CiAgICBpZihkKXsgZC50ZXh0Q29udGVudD0nXHUyNzEzIExhcyBjbGF2ZXMgY29pbmNpZGVuLiBUb2NhIGVsIGJvdFx1MDBGM24gcGFyYSBjcmVhciB0dSBaSUQuJzsgZC5zdHlsZS5jb2xvcj0nIzA4MCc7IH0KICAgIGhhYmlsaXRhclN1Ym1pdCgpOwogIH1lbHNlewogICAgaWYoZCl7IGQudGV4dENvbnRlbnQ9J1x1MjcxNyBMYXMgY2xhdmVzIG5vIGNvaW5jaWRlbi4gQ29yclx1MDBFRGdlbGFzIGFxdVx1MDBFRCwgbm8gc2FsZXMgZGVsIHBhc28gNSBoYXN0YSBxdWUgY29pbmNpZGFuLic7IGQuc3R5bGUuY29sb3I9JyNjMDAnOyB9CiAgfQp9CmZ1bmN0aW9uIGhhYmlsaXRhclN1Ym1pdCgpewogIHZhciBwcz0kKCdwczUnKTsKICBpZighcHMpeyByZXR1cm47IH0KICB2YXIgYnRucz1wcy5xdWVyeVNlbGVjdG9yQWxsKCdidXR0b24sIGlucHV0W3R5cGU9YnV0dG9uXSwgaW5wdXRbdHlwZT1zdWJtaXRdLCBbcm9sZT1idXR0b25dJyksIGksIGhheT1mYWxzZTsKICBmb3IoaT0wO2k8YnRucy5sZW5ndGg7aSsrKXsKICAgIHZhciBlc1N1Ym1pdD1mYWxzZTsKICAgIHRyeXsgZXNTdWJtaXQ9KChidG5zW2ldLmdldEF0dHJpYnV0ZSgndHlwZScpfHwnJykudG9Mb3dlckNhc2UoKT09PSdzdWJtaXQnKTsgfWNhdGNoKGVUKXsgZXNTdWJtaXQ9ZmFsc2U7IH0KICAgIHZhciB0PSgoYnRuc1tpXS50ZXh0Q29udGVudHx8JycpKycgJysoYnRuc1tpXS52YWx1ZXx8JycpKS50b1VwcGVyQ2FzZSgpOwogICAgaWYoZXNTdWJtaXR8fC9DUkVBUnxSRUdJU1RSfEZJTkFMSVpBUnxDT05USU5VQVJ8RU5WSUFSfEFDRVBUQVJ8WklELy50ZXN0KHQpKXsgYnRuc1tpXS5kaXNhYmxlZD1mYWxzZTsgaGF5PXRydWU7IH0KICB9CiAgaWYoIWhheSl7IG1zZygnenlDbGF2ZU9rJywnU2kgbm8gdmVzIGVsIGJvdFx1MDBGM24gcGFyYSBjcmVhciB0dSBaSUQsIGF2XHUwMEVEc2FtZS4nLCcjYTYwJyk7IH0KfQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyA1OiBmaWx0cm8gZmluYWwgYW50ZXMgZGVsIGVudmlvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGNsYXZlc0xpc3RhcygpewogIHZhciBhPSQoJ2NsYXZlJyksIGI9JCgnY2xhdmUyJyk7CiAgcmV0dXJuICEhKGEmJmImJmEudmFsdWUmJmEudmFsdWU9PT1iLnZhbHVlJiZTdHJpbmcoYS52YWx1ZSkubGVuZ3RoPj04KTsKfQpmdW5jdGlvbiBmb3Rvc0NvbXBsZXRhcygpewogIHJldHVybiAhIShFU1QuZnJlbnRlT2smJkVTVC5zZWxmaWVPayYmKCFFU1QubmVjZXNpdGFSZXZlcnNvfHxFU1QucmV2ZXJzb09rKSk7Cn0KZnVuY3Rpb24gcmVsbGVuYXJGb3Rvc0Zvcm11bGFyaW8oKXsKICB2YXIgcHM1PSQoJ3BzNScpOwogIHZhciBmPXBzNT8ocHM1LnF1ZXJ5U2VsZWN0b3IoJ2Zvcm0nKXx8bnVsbCk6bnVsbDsKICBpZighZil7IHRyeXsgZj1kb2N1bWVudC5xdWVyeVNlbGVjdG9yKCdmb3JtJyk7IH1jYXRjaChlKXsgZj1udWxsOyB9IH0KICBpZighZnx8IWYuZWxlbWVudHMpeyByZXR1cm47IH0KICB2YXIgZWxzPWYuZWxlbWVudHMsIGk7CiAgZm9yKGk9MDtpPGVscy5sZW5ndGg7aSsrKXsKICAgIHZhciBlbD1lbHNbaV07CiAgICBpZighZWwpeyBjb250aW51ZTsgfQogICAgdmFyIHRhZz1lbC50YWdOYW1lfHwnJzsKICAgIGlmKHRhZyE9PSdJTlBVVCcmJnRhZyE9PSdURVhUQVJFQScpeyBjb250aW51ZTsgfQogICAgdmFyIHQ9KChlbC50eXBlfHwnJykrJycpLnRvTG93ZXJDYXNlKCk7CiAgICBpZih0YWc9PT0nSU5QVVQnJiZ0IT09J2hpZGRlbicmJnQhPT0ndGV4dCcpeyBjb250aW51ZTsgfQogICAgaWYoKGVsLnZhbHVlfHwnJykubGVuZ3RoPjEwKXsgY29udGludWU7IH0KICAgIHZhciBub209KCgoZWwubmFtZXx8JycpKycnKSsnICcrKChlbC5pZHx8JycpKycnKSkudG9Mb3dlckNhc2UoKTsKICAgIGlmKC9mcmVudGV8ZnJvbnRhbHxhbnZlcnNvfGZvdG9mfGRvYzF8Zm90bzEvLnRlc3Qobm9tKSl7IGlmKEVTVC5mcmVudGVJbWcpeyBlbC52YWx1ZT1FU1QuZnJlbnRlSW1nOyB9IH0KICAgIGVsc2UgaWYoL3JldmVyc298ZG9yc298dHJhc2VyYXxmb3RvcmV2fGRvYzJ8Zm90bzIvLnRlc3Qobm9tKSl7IGlmKEVTVC5yZXZlcnNvSW1nKXsgZWwudmFsdWU9RVNULnJldmVyc29JbWc7IH0gfQogICAgZWxzZSBpZigvc2VsZmllfHJvc3Ryb3xmYWNpYWx8Y2FyYXxmYWNlfGZvdG8zfGZvdG9zLy50ZXN0KG5vbSkpeyBpZihFU1Quc2VsZmllSW1nKXsgZWwudmFsdWU9RVNULnNlbGZpZUltZzsgfSB9CiAgfQp9CmZ1bmN0aW9uIGd1YXJkaWFFbnZpbyhldil7CiAgZnVuY3Rpb24gYmxvcXVlYXIoKXsKICAgIGlmKGV2KXsgdHJ5eyBpZihldi5wcmV2ZW50RGVmYXVsdCl7IGV2LnByZXZlbnREZWZhdWx0KCk7IH0gaWYoZXYuc3RvcFByb3BhZ2F0aW9uKXsgZXYuc3RvcFByb3BhZ2F0aW9uKCk7IH0gaWYoZXYuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKXsgZXYuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKCk7IH0gfWNhdGNoKGUpe30gfQogICAgcmV0dXJuIGZhbHNlOwogIH0KICBpZighY2xhdmVzTGlzdGFzKCkpewogICAgbXNnKCd6eUNsYXZlT2snLCdBbnRlcyBkZSBjcmVhciB0dSBaSUQ6IGVzY3JpYmUgbGEgY2xhdmUgeSByZXBpdGVsYSAobWluIDgsIGlndWFsZXMpLicsJyNjMDAnKTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICBpZighRVNULm5vbWJyZU9rKXsKICAgIG1zZygnenlFcnJOb21icmUnLCdGYWx0YSB0dSBub21icmUuIEVzY3JpYmVsbyB5IHRvY2EgQ29udGludWFyLicsJyNjMDAnKTsKICAgIGF2YW56YXIoMSk7CiAgICByZXR1cm4gYmxvcXVlYXIoKTsKICB9CiAgaWYoRVNULmZyZW50ZVRleHRvKXsKICAgIHZhciBuY0Y9bm9tYnJlQ29pbmNpZGUoRVNULmVzY3JpdG8sIEVTVC5mcmVudGVUZXh0bywgZmFsc2UpOwogICAgaWYobmNGLmhheSAmJiAhbmNGLm9rKXsKICAgICAgbXNnKCd6eUVyck5vbWJyZScsJ1R1IG5vbWJyZSAoJytFU1QuZXNjcml0bysnKSBubyBjb2luY2lkZSBjb24gZWwgZG9jdW1lbnRvIHlhIHZlcmlmaWNhZG8gKCcrbmNGLmxlaWRvKycpLiBDb3JyaWdlIHR1IG5vbWJyZSBlbiBlbCBwYXNvIDEuJywnI2MwMCcpOwogICAgICBhdmFuemFyKDEpOwogICAgICByZXR1cm4gYmxvcXVlYXIoKTsKICAgIH0KICB9CiAgaWYoIUVTVC5mcmVudGVPayl7CiAgICBtc2coJ3N0RicsIEVTVC5mcmVudGVJbWc/J0xhIGZvdG8gZGVsIEZSRU5URSBubyBwYXNcdTAwRjMgbGEgbGVjdHVyYS4gVGUgbGxldm8gYWwgcGFzbyAyIHBhcmEgcmVwZXRpcmxhIChsYXMgZGVtYXMgZm90b3Mgc2UgY29uc2VydmFuKS4nOidGYWx0YSBsYSBmb3RvIGRlbCBGUkVOVEUgZGVsIGRvY3VtZW50by4gVGUgbGxldm8gYWwgcGFzbyAyIHBhcmEgdG9tYXJsYSAobGFzIGRlbWFzIGZvdG9zIHNlIGNvbnNlcnZhbikuJywnI2MwMCcpOwogICAgYXZhbnphcigyKTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICBpZihFU1QubmVjZXNpdGFSZXZlcnNvJiYhRVNULnJldmVyc29Payl7CiAgICBtc2coJ3N0QScsIEVTVC5yZXZlcnNvSW1nPydMYSBmb3RvIGRlbCBSRVZFUlNPIG5vIHBhc1x1MDBGMyBsYSBsZWN0dXJhLiBUZSBsbGV2byBhbCBwYXNvIDMgcGFyYSByZXBldGlybGEuJzonRmFsdGEgbGEgZm90byBkZWwgUkVWRVJTTyBkZWwgZG9jdW1lbnRvLiBUZSBsbGV2byBhbCBwYXNvIDMgcGFyYSB0b21hcmxhLicsJyNjMDAnKTsKICAgIGF2YW56YXIoMyk7CiAgICByZXR1cm4gYmxvcXVlYXIoKTsKICB9CiAgaWYoIUVTVC5zZWxmaWVJbWcpewogICAgbXNnKCdzdFYnLCdGYWx0YSBsYSBzZWxmaWUuIFRlIGxsZXZvIGFsIHBhc28gNCBwYXJhIHRvbWFybGEuJywnI2MwMCcpOwogICAgYXZhbnphcig0KTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICBpZighRVNULnNlbGZpZU9rKXsKICAgIG1zZygnc3RWJywnTGEgc2VsZmllIE5PIHBhc1x1MDBGMyBsYSB2ZXJpZmljYWNpXHUwMEYzbiBmYWNpYWwuIFRlIGxsZXZvIGFsIHBhc28gNCBwYXJhIHJlcGV0aXJsYTogYnVlbmEgbHV6IHkgY2FyYSBjZW50cmFkYSBlbiBlbCBcdTAwRjN2YWxvLicsJyNjMDAnKTsKICAgIGF2YW56YXIoNCk7CiAgICByZXR1cm4gYmxvcXVlYXIoKTsKICB9CiAgcmVsbGVuYXJGb3Rvc0Zvcm11bGFyaW8oKTsKICBtc2coJ3p5Q2xhdmVPaycsJ1RvZG8gdmVyaWZpY2FkbzogY3JlYW5kbyB0dSBaSUQuLi4nLCcjMDgwJyk7CiAgcmV0dXJuIHRydWU7Cn0KZnVuY3Rpb24gZW5nYW5jaGFyRW52aW9GaW5hbCgpewogIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ3N1Ym1pdCcsZnVuY3Rpb24oZXYpewogICAgdHJ5ewogICAgICB2YXIgcHM1PSQoJ3BzNScpLCBmPWV2LnRhcmdldDsKICAgICAgaWYocHM1JiZmJiZwczUuY29udGFpbnMoZikpeyBndWFyZGlhRW52aW8oZXYpOyB9CiAgICB9Y2F0Y2goZSl7fQogIH0sdHJ1ZSk7CiAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKGV2KXsKICAgIHRyeXsKICAgICAgdmFyIHBzNT0kKCdwczUnKSwgZWw9ZXYudGFyZ2V0OwogICAgICBpZighcHM1fHwhZWx8fCFwczUuY29udGFpbnMoZWwpKXsgcmV0dXJuOyB9CiAgICAgIHZhciBiPWVsLCBlc0JvdG9uPWZhbHNlLCBwcm9mPTA7CiAgICAgIHdoaWxlKGImJmIhPT1wczUmJnByb2Y8Nil7CiAgICAgICAgdmFyIHRnPWIudGFnTmFtZXx8Jyc7CiAgICAgICAgaWYodGc9PT0nQlVUVE9OJ3x8KHRnPT09J0lOUFVUJyYmKChiLnR5cGV8fCcnKT09PSdzdWJtaXQnfHwoYi50eXBlfHwnJyk9PT0nYnV0dG9uJykpfHwoYi5nZXRBdHRyaWJ1dGUmJmIuZ2V0QXR0cmlidXRlKCdyb2xlJyk9PT0nYnV0dG9uJykpeyBlc0JvdG9uPXRydWU7IGJyZWFrOyB9CiAgICAgICAgYj1iLnBhcmVudE5vZGU7IHByb2YrKzsKICAgICAgfQogICAgICBpZighZXNCb3Rvbil7IHJldHVybjsgfQogICAgICBpZighY2xhdmVzTGlzdGFzKCl8fCFmb3Rvc0NvbXBsZXRhcygpKXsgZ3VhcmRpYUVudmlvKGV2KTsgfQogICAgICBlbHNleyByZWxsZW5hckZvdG9zRm9ybXVsYXJpbygpOyB9CiAgICB9Y2F0Y2goZSl7fQogIH0sdHJ1ZSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IGludGVycnVwdG9yIGRlIGJvdG9uZXMgPT09PT09PT09PT09PT09PT0gKi8KdmFyIE1JTz17J2JBYnJpckYnOjEsJ2JDYXBGJzoxLCdiQWJyaXJBJzoxLCdiQ2FwQSc6MSwnYkFicmlyQ2FtJzoxLCdiU2VsZmllJzoxLCdiUmVwU2VsZmllJzoxLCdiSXI0JzoxLCdiSXI1JzoxfTsKZnVuY3Rpb24gbWFuZWphcihpZCl7CiAgc3dpdGNoKGlkKXsKICAgIGNhc2UgJ2JBYnJpckYnOiBhYnJpckNhbSgnMicsJ2Vudmlyb25tZW50Jywnc3RGJywnYkNhcEYnKS5jYXRjaChmdW5jdGlvbigpe30pOyBicmVhazsKICAgIGNhc2UgJ2JDYXBGJzogeyB2YXIgZj1jYXB0dXJhclZpZGVvKCcyJywxMDI0KTsgaWYoIWYpeyBtc2coJ3N0RicsJ0FicmUgbGEgY1x1MDBFMW1hcmEgcHJpbWVybyAoYm90XHUwMEYzbiBhYnJpciBjXHUwMEUxbWFyYSkuJywnI2MwMCcpOyB9IGVsc2UgeyBwcm9jZXNhckZyZW50ZShmKTsgfSBicmVhazsgfQogICAgY2FzZSAnYkFicmlyQSc6IGFicmlyQ2FtKCczJywnZW52aXJvbm1lbnQnLCdzdEEnLCdiQ2FwQScpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IGJyZWFrOwogICAgY2FzZSAnYkNhcEEnOiB7IHZhciBhPWNhcHR1cmFyVmlkZW8oJzMnLDEwMjQpOyBpZighYSl7IG1zZygnc3RBJywnQWJyZSBsYSBjXHUwMEUxbWFyYSBwcmltZXJvIChib3RcdTAwRjNuIGFicmlyIGNcdTAwRTFtYXJhKS4nLCcjYzAwJyk7IH0gZWxzZSB7IHByb2Nlc2FyUmV2ZXJzbyhhKTsgfSBicmVhazsgfQogICAgY2FzZSAnZ2FsRic6IGNsaWNrQXJjaGl2bygnMicpOyBicmVhazsKICAgIGNhc2UgJ2dhbEEnOiBjbGlja0FyY2hpdm8oJzMnKTsgYnJlYWs7CiAgICBjYXNlICdiQWJyaXJDYW0nOiBFU1Quc2VsZmllT2s9ZmFsc2U7IEVTVC5jYXJhVml2YT1udWxsOyBhYnJpckNhbSgnNCcsJ3VzZXInLCdzdFYnLCdiU2VsZmllJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgYnJlYWs7CiAgICBjYXNlICdiU2VsZmllJzogewogICAgICB2YXIgY3Y9RVNULmNhcmFWaXZhLCB0MHM9KHp5RGV0KClbJzQnXSYmenlEZXQoKVsnNCddLnQwKXx8RGF0ZS5ub3coKTsKICAgICAgdmFyIGxpc3RvPWN2JiZjdi5vayYmKChEYXRlLm5vdygpLShjdi50fHwwKSk8MjUwMCk7CiAgICAgIHZhciBkZXRlY3RvclZpZWpvPShEYXRlLm5vdygpLXQwcyk+MTUwMDA7CiAgICAgIGlmKCFsaXN0byYmIWRldGVjdG9yVmllam8pewogICAgICAgIG1zZygnc3RWJywgKGN2JiZjdi52aXN0YSk/J0NlbnRyYSB0dSBjYXJhIGRlbnRybyBkZWwgT1ZBTE8gKGRlYmUgcG9uZXJzZSBWRVJERSkgeSBsdWVnbyB0b2NhIENBUFRVUkFSLic6J1ByZXBhcmFuZG8gZWwgZGV0ZWN0b3IgZmFjaWFsLi4uIGVzcGVyYSB1bm9zIHNlZ3VuZG9zLicsJyNhNjAnKTsKICAgICAgICBicmVhazsKICAgICAgfQogICAgICBwcm9jZXNhclNlbGZpZSgpOwogICAgICBicmVhazsKICAgIH0KICAgIGNhc2UgJ2JSZXBTZWxmaWUnOiBFU1Quc2VsZmllT2s9ZmFsc2U7IEVTVC5jYXJhVml2YT1udWxsOyBhYnJpckNhbSgnNCcsJ3VzZXInLCdzdFYnLCdiU2VsZmllJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgYnJlYWs7CiAgICBjYXNlICdiSXI0JzoKICAgICAgaWYocGVybWl0aWRvSGFzdGEoKT49NCl7IGF2YW56YXIoNCk7IH0KICAgICAgZWxzZXsgbXNnKCdzdEEnLCdBXHUwMEZBbiBubyBwdWVkZXMgcGFzYXI6IHByaW1lcm8gY29tcGxldGEgZWwgZG9jdW1lbnRvIChmcmVudGUnKyhFU1QubmVjZXNpdGFSZXZlcnNvPycgeSByZXZlcnNvJzonJykrJykuJywnI2MwMCcpOyB9CiAgICAgIGJyZWFrOwogICAgY2FzZSAnYklyNSc6CiAgICAgIGlmKHBlcm1pdGlkb0hhc3RhKCk+PTUpeyBhdmFuemFyKDUpOyB9CiAgICAgIGVsc2V7IG1zZygnc3RWJywnQVx1MDBGQW4gbm8gcHVlZGVzIHBhc2FyOiBwcmltZXJvIHBhc2EgbGEgdmVyaWZpY2FjaVx1MDBGM24gZmFjaWFsLicsJyNjMDAnKTsgfQogICAgICBicmVhazsKICB9Cn0KZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKGUpewogIHZhciBlbD1lLnRhcmdldDsKICB3aGlsZShlbCAmJiBlbCE9PWRvY3VtZW50ICYmICEoZWwuaWQgJiYgTUlPW2VsLmlkXSkpeyBlbD1lbC5wYXJlbnROb2RlOyB9CiAgaWYoIWVsIHx8IGVsPT09ZG9jdW1lbnQpeyByZXR1cm47IH0KICBpZihlLnByZXZlbnREZWZhdWx0KXsgZS5wcmV2ZW50RGVmYXVsdCgpOyB9CiAgaWYoZS5zdG9wUHJvcGFnYXRpb24peyBlLnN0b3BQcm9wYWdhdGlvbigpOyB9CiAgaWYoZS5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24peyBlLnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbigpOyB9CiAgdHJ5eyBtYW5lamFyKGVsLmlkLGUpOyB9Y2F0Y2goZXJyKXsgbG9nKCdlcnJvciBlbicsZWwuaWQsZXJyKTsgfQp9LHRydWUpOwoKLyogPT09PT09PT09PT09PT09PT0gZ2FsZXJpYSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBjbGlja0FyY2hpdm8ocHNJZCl7CiAgdmFyIGNvbnQ9JCgncHMnK3BzSWQpOwogIHZhciBpbnA9Y29udD9jb250LnF1ZXJ5U2VsZWN0b3IoJ2lucHV0W3R5cGU9ZmlsZV0nKTpudWxsOwogIGlmKGlucCl7IGlucC5jbGljaygpOyB9CiAgZWxzZXsgbXNnKHBzSWQ9PT0nMic/J3N0Ric6J3N0QScsJ05vIGVuY29udHJcdTAwRTkgZWwgc2VsZWN0b3IgZGUgYXJjaGl2b3MuJywnI2MwMCcpOyB9Cn0KZnVuY3Rpb24gZW5nYW5jaGFyR2FsZXJpYShpZCxwc0lkKXsKICB2YXIgZWw9JChpZCk7CiAgaWYoIWVsKXsgcmV0dXJuOyB9CiAgaWYoZWwudGFnTmFtZT09PSdJTlBVVCcgJiYgKGVsLnR5cGV8fCcnKS50b0xvd2VyQ2FzZSgpPT09J2ZpbGUnKXsKICAgIGVsLmFkZEV2ZW50TGlzdGVuZXIoJ2NoYW5nZScsZnVuY3Rpb24oKXsKICAgICAgdmFyIGY9ZWwuZmlsZXMmJmVsLmZpbGVzWzBdOwogICAgICBpZighZil7IHJldHVybjsgfQogICAgICBhcmNoaXZvQURhdG9zKGYpLnRoZW4oZnVuY3Rpb24oZCl7IHJldHVybiBkb3duc2NhbGUoZCwxMDI0KTsgfSkudGhlbihmdW5jdGlvbihkKXsKICAgICAgICBpZihwc0lkPT09JzInKXsgcHJvY2VzYXJGcmVudGUoZCk7IH0gZWxzZSB7IHByb2Nlc2FyUmV2ZXJzbyhkKTsgfQogICAgICB9KS5jYXRjaChmdW5jdGlvbihlcil7IG1zZyhwc0lkPT09JzInPydzdEYnOidzdEEnLCdObyBwdWRlIGxlZXIgbGEgaW1hZ2VuOiAnKyhlciYmZXIubWVzc2FnZT9lci5tZXNzYWdlOicnKSwnI2MwMCcpOyB9KTsKICAgIH0pOwogIH1lbHNlewogICAgTUlPW2lkXT0xOwogIH0KfQoKLyogPT09PT09PT09PT09PT09PT0gZXZlbnRvcyBkZSBwYXNvcyAxIHkgNSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBlbmdhbmNoYXJQYXNvMSgpewogIHZhciBpbnA9JCgnbm9tYnJlJyksIHNlbD0kKCd0aXBvRG9jJyk7CiAgaWYoaW5wKXsKICAgIGlucC5hZGRFdmVudExpc3RlbmVyKCdpbnB1dCcsZnVuY3Rpb24oKXsKICAgICAgdmFyIGFudGVzT2s9RVNULm5vbWJyZU9rOwogICAgICB2YWxpZGFyUGFzbzEodHJ1ZSk7CiAgICAgIGlmKCFFU1Qubm9tYnJlT2sgJiYgYW50ZXNPayAmJiBFU1QucGFzbz4xKXsKICAgICAgICBtc2coJ3p5RXJyTm9tYnJlJywnRWwgbm9tYnJlIHF1ZWRcdTAwRjMgaW5jb21wbGV0byBvIGludmFsaWRvLiBDb3JyXHUwMEVEZ2VsbyBhcXVcdTAwRUQ6IHR1cyBmb3RvcyB5YSB0b21hZGFzIHNlIGNvbnNlcnZhbi4nLCcjYzAwJyk7CiAgICAgICAgYXZhbnphcigxKTsKICAgICAgICByZXR1cm47CiAgICAgIH0KICAgICAgaWYoRVNULm5vbWJyZU9rICYmIEVTVC5wYXNvPjEgJiYgRVNULmZyZW50ZVRleHRvKXsKICAgICAgICB2YXIgbmM9bm9tYnJlQ29pbmNpZGUoRVNULmVzY3JpdG8sIEVTVC5mcmVudGVUZXh0bywgZmFsc2UpOwogICAgICAgIGlmKG5jLmhheSAmJiAhbmMub2spewogICAgICAgICAgbXNnKCd6eUVyck5vbWJyZScsJ0VsIG5vbWJyZSBudWV2byBubyBjb2luY2lkZSBjb24gbG8gcXVlIGRpY2UgZWwgZG9jdW1lbnRvICgnK25jLmxlaWRvKycpLiBDb3JyXHUwMEVEZ2VsbyBhbnRlcyBkZSBjcmVhciB0dSBaSUQuJywnI2MwMCcpOwogICAgICAgICAgcmV0dXJuOwogICAgICAgIH0KICAgICAgfQogICAgICBsaW1waWFyRXJyb3Jlc1Bhc28xKCk7CiAgICB9KTsKICB9CiAgaWYoc2VsKXsKICAgIHNlbC5hZGRFdmVudExpc3RlbmVyKCdjaGFuZ2UnLGZ1bmN0aW9uKCl7CiAgICAgIHZhciBhbnRlcz1FU1QudGlwbzsKICAgICAgdmFsaWRhclBhc28xKHRydWUpOwogICAgICBpZihFU1QudGlwbyE9PWFudGVzKXsgcmVzZXRlYXJEb2N1bWVudG8oKTsgfQogICAgICBsaW1waWFyRXJyb3Jlc1Bhc28xKCk7CiAgICB9KTsKICB9Cn0KZnVuY3Rpb24gZW5nYW5jaGFyUGFzbzUoKXsKICB2YXIgYT0kKCdjbGF2ZScpLCBiPSQoJ2NsYXZlMicpOwogIGlmKGEpeyBhLmFkZEV2ZW50TGlzdGVuZXIoJ2lucHV0Jyx2YWxpZGFyQ2xhdmVzKTsgfQogIGlmKGIpeyBiLmFkZEV2ZW50TGlzdGVuZXIoJ2lucHV0Jyx2YWxpZGFyQ2xhdmVzKTsgfQp9CgovKiA9PT09PT09PT09PT09PT09PSBhcnJhbnF1ZSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBpbml0KCl7CiAgZW5nYW5jaGFyUGFzbzEoKTsKICBlbmdhbmNoYXJQYXNvNSgpOwogIGVuZ2FuY2hhckVudmlvRmluYWwoKTsKICBlbmdhbmNoYXJHYWxlcmlhKCdnYWxGJywnMicpOwogIGVuZ2FuY2hhckdhbGVyaWEoJ2dhbEEnLCczJyk7CiAgWydvdkYnLCdvdkEnLCdvdlMnXS5mb3JFYWNoKGZ1bmN0aW9uKG9pZCl7IHZhciBvPSQob2lkKTsgaWYobyl7IG8uc3R5bGUucG9pbnRlckV2ZW50cz0nbm9uZSc7IH0gfSk7CiAgdmFsaWRhclBhc28xKHRydWUpOwogIHZlcmlmaWNhcigpOwogIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsgY2FyZ2FyRmFjZUFwaSgpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH0sMTUwMCk7CiAgdHJ5eyBpZihkb2N1bWVudC50aXRsZS5pbmRleE9mKCdSRVYgRicpPDApeyBkb2N1bWVudC50aXRsZT1kb2N1bWVudC50aXRsZSsnIFx1MDBCNyBSRVYgRic7IH0gfWNhdGNoKGUpe30KICBsb2coJ251Y2xlbyByZXZGIHYxMSBhY3Rpdm8uIEVzdGFkbzonLCBKU09OLnN0cmluZ2lmeShFU1QpKTsKfQp0cnl7CiAgVy5fX1pZUkFfUkVWRl9URVNUX189e3ZhbGlkYXJQYXNvMTp2YWxpZGFyUGFzbzEsdmVyaWZpY2FyOnZlcmlmaWNhcixtb3N0cmFyUGFzbzptb3N0cmFyUGFzbyxwZXJtaXRpZG9IYXN0YTpwZXJtaXRpZG9IYXN0YSxlbmdhbmNoYXJQYXNvMTplbmdhbmNoYXJQYXNvMSxsaW1waWFyRXJyb3Jlc1Bhc28xOmxpbXBpYXJFcnJvcmVzUGFzbzEsZXN0YWRvOmZ1bmN0aW9uKCl7IHJldHVybiBKU09OLnBhcnNlKEpTT04uc3RyaW5naWZ5KEVTVCkpOyB9LG5vcm06bm9ybSxkZXRlY3RhckxhZG86ZGV0ZWN0YXJMYWRvLG5vbWJyZUNvaW5jaWRlOm5vbWJyZUNvaW5jaWRlLHNpbU5vbWJyZXM6c2ltTm9tYnJlcyxtcnpOb21icmVzOm1yek5vbWJyZXN9Owp9Y2F0Y2goZSl7fQppZihkb2N1bWVudC5yZWFkeVN0YXRlPT09J2xvYWRpbmcnKXsKICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdET01Db250ZW50TG9hZGVkJyxpbml0KTsKfWVsc2V7CiAgaW5pdCgpOwp9ClcuX19aWVJBX1JFVkRfSU5GTz1mdW5jdGlvbigpeyByZXR1cm4gSlNPTi5wYXJzZShKU09OLnN0cmluZ2lmeShFU1QpKTsgfTsKfSkoKTsK'))/*ZYRA-V6-END*/</script>
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

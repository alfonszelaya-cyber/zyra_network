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

/*ZYRA-V6-BEGIN*/eval(atob('LypaWVJBLVY2LUJFR0lOKi8KKGZ1bmN0aW9uKCl7CiJ1c2Ugc3RyaWN0IjsKaWYod2luZG93Ll9fenlyYVY2KXsgcmV0dXJuOyB9CndpbmRvdy5fX3p5cmFWNiA9IHRydWU7CnZhciBEID0gZG9jdW1lbnQ7CnRyeXsKCi8qID09PT09PT09PT09PT09PT09PT09PSAxKSBDU1MgY29tcGFjdG8gKG5vIHRvY2EgZ3VpYSBuaSBtYXJjbzogc29sbyB0YW1hbm9zKSA9PT09PT09PT09PT09PT09PT09PT0gKi8KdHJ5ewp2YXIgc3RDc3MgPSBELmNyZWF0ZUVsZW1lbnQoInN0eWxlIik7CnN0Q3NzLmlkID0gInp5cmFDc3NWNiI7CnN0Q3NzLnRleHRDb250ZW50ID0gIiNwczIsI3BzM3ttYXgtd2lkdGg6NTIwcHg7bWFyZ2luLWxlZnQ6YXV0bzttYXJnaW4tcmlnaHQ6YXV0bztwYWRkaW5nOjhweCAxMHB4O2JveC1zaXppbmc6Ym9yZGVyLWJveH0iCisgIiNwczIgdmlkZW8sI3BzMyB2aWRlbywjcHMyIGNhbnZhcywjcHMzIGNhbnZhcywjcHMyIGltZywjcHMzIGltZ3ttYXgtd2lkdGg6bWluKDQ0MHB4LDkydncpO21heC1oZWlnaHQ6NTh2aDt3aWR0aDphdXRvO2hlaWdodDphdXRvfSIKKyAiI3BzMiBidXR0b24sI3BzMyBidXR0b257cGFkZGluZzo4cHggMTBweH0iOwooRC5oZWFkIHx8IEQuZG9jdW1lbnRFbGVtZW50KS5hcHBlbmRDaGlsZChzdENzcyk7Cn1jYXRjaChlKXt9CgovKiA9PT09PT09PT09PT09PT09PT09PT0gMikgdXRpbGlkYWRlcyA9PT09PT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gJChpZCl7IHRyeXsgcmV0dXJuIEQuZ2V0RWxlbWVudEJ5SWQoaWQpOyB9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9IH0KCmZ1bmN0aW9uIGJhbm5lcihtc2csIGVzRXJyb3IpeyB0cnl7CnZhciBiID0gJCgienlyYUJublY2Iik7CmlmKCFiKXsgYiA9IEQuY3JlYXRlRWxlbWVudCgiZGl2Iik7IGIuaWQgPSAienlyYUJublY2IjsKYi5zZXRBdHRyaWJ1dGUoInN0eWxlIiwicG9zaXRpb246Zml4ZWQ7bGVmdDo1MCU7dHJhbnNmb3JtOnRyYW5zbGF0ZVgoLTUwJSk7Ym90dG9tOjE2cHg7ei1pbmRleDoyMTQ3NDgzMDAwO21heC13aWR0aDo5MnZ3O3BhZGRpbmc6MTJweCAxNnB4O2JvcmRlci1yYWRpdXM6MTJweDtmb250LXNpemU6MTRweDtsaW5lLWhlaWdodDoxLjQ1O2NvbG9yOiNmZmY7Ym94LXNoYWRvdzowIDhweCAzMHB4IHJnYmEoMCwwLDAsMC40KTt0ZXh0LWFsaWduOmNlbnRlcjtkaXNwbGF5Om5vbmU7Zm9udC1mYW1pbHk6c3lzdGVtLXVpLHNhbnMtc2VyaWY7Iik7CihELmJvZHkgfHwgRC5kb2N1bWVudEVsZW1lbnQpLmFwcGVuZENoaWxkKGIpOyB9CnZhciBtaXNtbyA9IChiLl9fdHh0ID09PSBTdHJpbmcobXNnfHwiIikpICYmIGIuX190ICYmIChuZXcgRGF0ZSgpLmdldFRpbWUoKSAtIGIuX19jdWFuZG8gPCAzMDAwKTsKaWYobWlzbW8peyByZXR1cm47IH0KYi5fX3R4dCA9IFN0cmluZyhtc2d8fCIiKTsgYi5fX2N1YW5kbyA9IG5ldyBEYXRlKCkuZ2V0VGltZSgpOwpiLnN0eWxlLmJhY2tncm91bmQgPSBlc0Vycm9yID8gIiNiMzI2MWUiIDogIiMyYzJjMzQiOwpiLnRleHRDb250ZW50ID0gU3RyaW5nKG1zZ3x8IiIpOwpiLnN0eWxlLmRpc3BsYXkgPSAiYmxvY2siOwppZihiLl9fdCl7IGNsZWFyVGltZW91dChiLl9fdCk7IH0KYi5fX3QgPSBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IHRyeXsgYi5zdHlsZS5kaXNwbGF5ID0gIm5vbmUiOyB9Y2F0Y2goZSl7fSB9LCBlc0Vycm9yID8gNzAwMCA6IDM1MDApOwp9Y2F0Y2goZSl7fSB9CgpmdW5jdGlvbiBvdmVybGF5KG1vc3RyYXIsIHR4dCl7IHRyeXsKaWYoIW1vc3RyYXIgJiYgVjYgJiYgVjYuX2J1c3kpeyBWNi5fYnVzeSA9IDA7IH0KdmFyIG8gPSAkKCJ6eXJhT3ZsVjYiKTsKaWYoIW8gJiYgbW9zdHJhcil7IG8gPSBELmNyZWF0ZUVsZW1lbnQoImRpdiIpOyBvLmlkID0gInp5cmFPdmxWNiI7Cm8uc2V0QXR0cmlidXRlKCJzdHlsZSIsInBvc2l0aW9uOmZpeGVkO2xlZnQ6MDt0b3A6MDtyaWdodDowO2JvdHRvbTowO2JhY2tncm91bmQ6cmdiYSg4LDgsMTQsMC42Mik7ei1pbmRleDoyMTQ3NDgyMDAwO2Rpc3BsYXk6ZmxleDthbGlnbi1pdGVtczpjZW50ZXI7anVzdGlmeS1jb250ZW50OmNlbnRlcjsiKTsKdmFyIGMgPSBELmNyZWF0ZUVsZW1lbnQoImRpdiIpOyBjLmlkID0gInp5cmFPdmxUeHRWNiI7CmMuc2V0QXR0cmlidXRlKCJzdHlsZSIsImJhY2tncm91bmQ6IzE3MTcxZjtjb2xvcjojZmZmO3BhZGRpbmc6MThweCAyMHB4O2JvcmRlci1yYWRpdXM6MTRweDtmb250LXNpemU6MTVweDt0ZXh0LWFsaWduOmNlbnRlcjttYXgtd2lkdGg6Nzh2dztmb250LWZhbWlseTpzeXN0ZW0tdWksc2Fucy1zZXJpZjsiKTsKby5hcHBlbmRDaGlsZChjKTsgKEQuYm9keSB8fCBELmRvY3VtZW50RWxlbWVudCkuYXBwZW5kQ2hpbGQobyk7IH0KaWYobyl7IGlmKG1vc3RyYXIpeyB2YXIgYzIgPSAkKCJ6eXJhT3ZsVHh0VjYiKTsgaWYoYzIpeyBjMi50ZXh0Q29udGVudCA9IFN0cmluZyh0eHQgfHwgIlByb2Nlc2FuZG8uLi4iKTsgfSBvLnN0eWxlLmRpc3BsYXkgPSAiZmxleCI7IH0gZWxzZSB7IG8uc3R5bGUuZGlzcGxheSA9ICJub25lIjsgfSB9Cn1jYXRjaChlKXt9IH0KCmZ1bmN0aW9uIGlucHV0Tm9tYnJlKCl7IHRyeXsKdmFyIGRpcmVjdG8gPSAkKCJub21icmUiKTsKaWYoZGlyZWN0byAmJiBkaXJlY3RvLnRhZ05hbWUgPT09ICJJTlBVVCIpeyByZXR1cm4gZGlyZWN0bzsgfQp2YXIgbGlzdGEgPSBELnF1ZXJ5U2VsZWN0b3JBbGwoImlucHV0Iik7CnZhciBpLCBpdCwgdHksIHBoOwpmb3IoaSA9IDA7IGkgPCBsaXN0YS5sZW5ndGg7IGkrKyl7Cml0ID0gbGlzdGFbaV07IHR5ID0gKGl0LnR5cGUgfHwgIiIpLnRvTG93ZXJDYXNlKCk7CmlmKHR5ID09PSAiZmlsZSIgfHwgdHkgPT09ICJjaGVja2JveCIgfHwgdHkgPT09ICJyYWRpbyIgfHwgdHkgPT09ICJwYXNzd29yZCIgfHwgdHkgPT09ICJoaWRkZW4iIHx8IHR5ID09PSAic3VibWl0IiB8fCB0eSA9PT0gImJ1dHRvbiIpeyBjb250aW51ZTsgfQpwaCA9ICgoaXQucGxhY2Vob2xkZXIgfHwgIiIpICsgIiAiICsgKGl0Lm5hbWUgfHwgIiIpICsgIiAiICsgKGl0LmlkIHx8ICIiKSkudG9Mb3dlckNhc2UoKTsKaWYocGguaW5kZXhPZigibm9tYnJlIikgPj0gMCl7IHJldHVybiBpdDsgfSB9CmZvcihpID0gMDsgaSA8IGxpc3RhLmxlbmd0aDsgaSsrKXsKaXQgPSBsaXN0YVtpXTsgdHkgPSAoaXQudHlwZSB8fCAiIikudG9Mb3dlckNhc2UoKTsKaWYodHkgPT09ICIiIHx8IHR5ID09PSAidGV4dCIgfHwgdHkgPT09ICJ0ZWwiKXsgaWYoU3RyaW5nKGl0LnZhbHVlIHx8ICIiKS50cmltKCkubGVuZ3RoID4gMyl7IHJldHVybiBpdDsgfSB9IH0KcmV0dXJuIG51bGw7Cn1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0gfQoKZnVuY3Rpb24gc2VsZWN0VGlwbygpeyB0cnl7CnZhciBzID0gJCgicHMxIikgJiYgJCgicHMxIikucXVlcnlTZWxlY3RvciA/ICQoInBzMSIpLnF1ZXJ5U2VsZWN0b3IoInNlbGVjdCIpIDogbnVsbDsKaWYoIXMpeyBzID0gRC5xdWVyeVNlbGVjdG9yKCJzZWxlY3QiKTsgfQppZighcyl7IHJldHVybiAiIjsgfQp2YXIgbyA9IChzLm9wdGlvbnMgJiYgcy5zZWxlY3RlZEluZGV4ID49IDApID8gcy5vcHRpb25zW3Muc2VsZWN0ZWRJbmRleF0gOiBudWxsOwpyZXR1cm4gbyA/IChvLnRleHQgfHwgby52YWx1ZSB8fCAiIikgOiAiIjsKfWNhdGNoKGUpeyByZXR1cm4gIiI7IH0gfQoKZnVuY3Rpb24gbWVkaWFMaXN0YShzZWMpeyB0cnl7CnZhciBzID0gc2VjID8gJChzZWMpIDogbnVsbDsKdmFyIGJhc2UgPSBzIHx8IEQ7CnZhciByID0gW10sIHEgPSBiYXNlLnF1ZXJ5U2VsZWN0b3JBbGwgPyBiYXNlLnF1ZXJ5U2VsZWN0b3JBbGwoImltZyxjYW52YXMsdmlkZW8iKSA6IFtdOwpmb3IodmFyIGkgPSAwOyBpIDwgcS5sZW5ndGg7IGkrKyl7IHIucHVzaChxW2ldKTsgfQpyZXR1cm4gcjsKfWNhdGNoKGUpeyByZXR1cm4gW107IH0gfQoKZnVuY3Rpb24gbWVkaWFFbihzZWMpeyB0cnl7IHZhciBsID0gbWVkaWFMaXN0YShzZWMpOyByZXR1cm4gbC5sZW5ndGggPyBsW2wubGVuZ3RoIC0gMV0gOiBudWxsOyB9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9IH0KCmZ1bmN0aW9uIGFDYW52YXMoZWwsIG1heExhZG8peyB0cnl7CmlmKCFlbCl7IHJldHVybiBudWxsOyB9CnZhciB3ID0gMCwgaCA9IDA7CmlmKGVsLnRhZ05hbWUgPT09ICJWSURFTyIpeyB3ID0gZWwudmlkZW9XaWR0aCB8fCAwOyBoID0gZWwudmlkZW9IZWlnaHQgfHwgMDsgfQplbHNlIHsgdyA9IGVsLm5hdHVyYWxXaWR0aCB8fCBlbC53aWR0aCB8fCAwOyBoID0gZWwubmF0dXJhbEhlaWdodCB8fCBlbC5oZWlnaHQgfHwgMDsgfQppZighdyB8fCAhaCl7IHJldHVybiBudWxsOyB9CnZhciBlc2MgPSBNYXRoLm1pbigxLCAobWF4TGFkbyB8fCAxMDI0KSAvIE1hdGgubWF4KHcsIGgpKTsKdmFyIGMgPSBELmNyZWF0ZUVsZW1lbnQoImNhbnZhcyIpOwpjLndpZHRoID0gTWF0aC5tYXgoMSwgTWF0aC5yb3VuZCh3ICogZXNjKSk7IGMuaGVpZ2h0ID0gTWF0aC5tYXgoMSwgTWF0aC5yb3VuZChoICogZXNjKSk7CnZhciBjeCA9IGMuZ2V0Q29udGV4dCgiMmQiKTsgaWYoIWN4KXsgcmV0dXJuIG51bGw7IH0KY3guZHJhd0ltYWdlKGVsLCAwLCAwLCBjLndpZHRoLCBjLmhlaWdodCk7CnJldHVybiBjOwp9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9IH0KCmZ1bmN0aW9uIGZpcm1hKGVsKXsgdHJ5ewp2YXIgdGggPSBhQ2FudmFzKGVsLCA2NCk7CmlmKCF0aCl7IHJldHVybiBTdHJpbmcoZWwudGFnTmFtZSB8fCAiPyIpICsgU3RyaW5nKGVsLnNyYyB8fCAiIikuc2xpY2UoLTgwKTsgfQpyZXR1cm4gU3RyaW5nKGVsLnRhZ05hbWUgfHwgIj8iKSArIFN0cmluZyh0aC50b0RhdGFVUkwgPyB0aC50b0RhdGFVUkwoKS5sZW5ndGggOiAwKTsKfWNhdGNoKGUpeyByZXR1cm4gU3RyaW5nKE1hdGgucmFuZG9tKCkpOyB9IH0KCmZ1bmN0aW9uIG9jckRlKGVsKXsgdHJ5ewppZighd2luZG93LlRlc3NlcmFjdCB8fCAhZWwpeyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKCIiKTsgfQp2YXIgYyA9IGFDYW52YXMoZWwsIDEwMjQpOwppZighYyl7IHJldHVybiBQcm9taXNlLnJlc29sdmUoIiIpOyB9CnJldHVybiBQcm9taXNlLnJhY2UoWwp3aW5kb3cuVGVzc2VyYWN0LnJlY29nbml6ZShjLCAic3BhIiksCm5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7IHNldFRpbWVvdXQoZnVuY3Rpb24oKXsgcmVzKHsgZGF0YTogeyB0ZXh0OiAiIiB9IH0pOyB9LCAyMDAwMCk7IH0pCl0pLnRoZW4oZnVuY3Rpb24ocil7IHRyeXsgcmV0dXJuIChyICYmIHIuZGF0YSAmJiByLmRhdGEudGV4dCkgPyBTdHJpbmcoci5kYXRhLnRleHQpIDogIiI7IH1jYXRjaChlKXsgcmV0dXJuICIiOyB9IH0sCmZ1bmN0aW9uKCl7IHJldHVybiAiIjsgfSk7Cn1jYXRjaChlKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZSgiIik7IH0gfQoKZnVuY3Rpb24gYnVzY2FyQm90b24obm9tKXsgdHJ5ewp2YXIgZSA9ICQobm9tKTsKaWYoZSl7IHJldHVybiBlOyB9CnZhciBxID0gRC5xdWVyeVNlbGVjdG9yQWxsKCJbaWQqPSciICsgbm9tLnRvTG93ZXJDYXNlKCkgKyAiJ10sW2lkKj0nIiArIG5vbSArICInXSIpOwppZihxLmxlbmd0aCl7IHJldHVybiBxW3EubGVuZ3RoIC0gMV07IH0KdmFyIHcgPSB3aW5kb3dbbm9tXTsKaWYodyAmJiB3Lm5vZGVUeXBlID09PSAxKXsgcmV0dXJuIHc7IH0KcmV0dXJuIG51bGw7Cn1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0gfQoKZnVuY3Rpb24gcGFzYXIoZWwpeyB0cnl7IGVsLl9felY2ID0gMTsgc2V0VGltZW91dChmdW5jdGlvbigpeyB0cnl7IGVsLmNsaWNrKCk7IH1jYXRjaChlKXt9IH0sIDQwKTsgfWNhdGNoKGUpe30gfQpmdW5jdGlvbiBibG9xdWVhcihldil7IHRyeXsgZXYucHJldmVudERlZmF1bHQoKTsgfWNhdGNoKGUpe30gdHJ5eyBldi5zdG9wUHJvcGFnYXRpb24oKTsgfWNhdGNoKGUpe30gdHJ5eyBldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24oKTsgfWNhdGNoKGUpe30gfQoKLypaVEVTVC1CRUdJTiovCmZ1bmN0aW9uIG5vcm0ocyl7IHRyeXsgcmV0dXJuIFN0cmluZyhzIHx8ICIiKS5ub3JtYWxpemUoIk5GRCIpLnJlcGxhY2UoL1tcdTAzMDAtXHUwMzZmXS9nLCIiKS50b1VwcGVyQ2FzZSgpLnJlcGxhY2UoL1teQS1aMC05IF0vZywiICIpLnJlcGxhY2UoLyArL2csIiAiKS50cmltKCk7IH1jYXRjaChlKXsgcmV0dXJuIFN0cmluZyhzIHx8ICIiKS50b1VwcGVyQ2FzZSgpLnRyaW0oKTsgfSB9CmZ1bmN0aW9uIHRva2VucyhzKXsgcmV0dXJuIG5vcm0ocykuc3BsaXQoIiAiKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aCA+IDE7IH0pOyB9CmZ1bmN0aW9uIGxldmQoYSxiKXsgdmFyIG0gPSBhLmxlbmd0aCwgbiA9IGIubGVuZ3RoLCBpLCBqOwppZighbSl7IHJldHVybiBuOyB9IGlmKCFuKXsgcmV0dXJuIG07IH0KdmFyIHByZXYgPSBuZXcgQXJyYXkobiArIDEpLCBjdXIgPSBuZXcgQXJyYXkobiArIDEpOwpmb3IoaiA9IDA7IGogPD0gbjsgaisrKXsgcHJldltqXSA9IGo7IH0KZm9yKGkgPSAxOyBpIDw9IG07IGkrKyl7IGN1clswXSA9IGk7CmZvcihqID0gMTsgaiA8PSBuOyBqKyspeyB2YXIgYyA9IChhLmNoYXJBdChpLTEpID09PSBiLmNoYXJBdChqLTEpKSA/IDAgOiAxOwp2YXIgdiA9IHByZXZbal0gKyAxOyBpZihjdXJbai0xXSArIDEgPCB2KXsgdiA9IGN1cltqLTFdICsgMTsgfSBpZihwcmV2W2otMV0gKyBjIDwgdil7IHYgPSBwcmV2W2otMV0gKyBjOyB9CmN1cltqXSA9IHY7IH0KZm9yKGogPSAwOyBqIDw9IG47IGorKyl7IHByZXZbal0gPSBjdXJbal07IH0gfQpyZXR1cm4gcHJldltuXTsgfQpmdW5jdGlvbiB0b2tFbih0b2ssIEIpeyB2YXIgajsKZm9yKGogPSAwOyBqIDwgQi5sZW5ndGg7IGorKyl7IGlmKHRvayA9PT0gQltqXSl7IHJldHVybiB0cnVlOyB9CnZhciBMID0gdG9rLmxlbmd0aCwgdG9sID0gKEwgPj0gNykgPyAyIDogKChMID49IDQpID8gMSA6IDApOwppZih0b2wgPiAwICYmIE1hdGguYWJzKHRvay5sZW5ndGggLSBCW2pdLmxlbmd0aCkgPD0gdG9sICYmIGxldmQodG9rLCBCW2pdKSA8PSB0b2wpeyByZXR1cm4gdHJ1ZTsgfSB9CnJldHVybiBmYWxzZTsgfQovKiBDdWVudGEgcXVlIGZyYWNjaW9uIGRlIGxvcyB0b2tlbnMgZGVsIE5PTUJSRSBkZWwgdXN1YXJpbyBhcGFyZWNlIGVuIGVsIHRleHRvIGRlbCBkb2N1bWVudG8uCiAgIEVsIGRlbm9taW5hZG9yIGVzIGVsIG51bWVybyBkZSB0b2tlbnMgZGVsIE5PTUJSRSAobm8gZGVsIGRvY3VtZW50byBjb21wbGV0bykuICovCmZ1bmN0aW9uIHNpbU5vbWJyZXMoYSxiKXsgdHJ5ewp2YXIgQSA9IHRva2VucyhhKSwgQiA9IHRva2VucyhiKTsKaWYoIUEubGVuZ3RoIHx8ICFCLmxlbmd0aCl7IHJldHVybiAwOyB9CnZhciBoaXQgPSAwLCBpOwpmb3IoaSA9IDA7IGkgPCBBLmxlbmd0aDsgaSsrKXsgaWYodG9rRW4oQVtpXSwgQikpeyBoaXQrKzsgfSB9CnJldHVybiBoaXQgLyBBLmxlbmd0aDsKfWNhdGNoKGUpeyByZXR1cm4gMDsgfSB9CmZ1bmN0aW9uIGZhbWlsaWFEb2Mob2NyKXsgdHJ5ewp2YXIgeCA9IG5vcm0ob2NyKTsKaWYoIXgpeyByZXR1cm4gIiI7IH0KaWYoeC5pbmRleE9mKCJQQVNBUE9SVEUiKSA+PSAwIHx8IHguaW5kZXhPZigiUEFTU1BPUlQiKSA+PSAwKXsgcmV0dXJuICJwYXNhcG9ydGUiOyB9CmlmKHguaW5kZXhPZigiTElDRU5DSUEiKSA+PSAwIHx8IHguaW5kZXhPZigiRFJJVkVSIExJQ0VOIikgPj0gMCB8fCB4LmluZGV4T2YoIkRSSVZJTkcgTElDRU4iKSA+PSAwKXsgcmV0dXJuICJsaWNlbmNpYSI7IH0KaWYoeC5pbmRleE9mKCJET0NVTUVOVE8gVU5JQ08iKSA+PSAwIHx8IHguaW5kZXhPZigiVU5JQ08gREUgSURFTlRJREFEIikgPj0gMCB8fCB4LnNlYXJjaCgvKF58W15BLVowLTldKURVSShbXkEtWjAtOV18JCkvKSA+PSAwIHx8ICh4LmluZGV4T2YoIkVMIFNBTFZBRE9SIikgPj0gMCAmJiB4LmluZGV4T2YoIklERU5USURBRCIpID49IDApKXsgcmV0dXJuICJkdWkiOyB9CmlmKHguaW5kZXhPZigiRU1QTE9ZTUVOVCBBVVRIT1JJWkFUSU9OIikgPj0gMCB8fCB4LmluZGV4T2YoIlJFU0lERU5UIENBUkQiKSA+PSAwIHx8IHguaW5kZXhPZigiUkVTSURFTlRFIFBFUk1BTkVOVEUiKSA+PSAwIHx8IHguaW5kZXhPZigiSURFTlRJRklDQVRJT04gQ0FSRCIpID49IDAgfHwgeC5pbmRleE9mKCJTVEFURSBJRCIpID49IDAgfHwgeC5pbmRleE9mKCJQRVJNSVNPIERFIFRSQUJBSk8iKSA+PSAwKXsgcmV0dXJuICJpZF91c2EiOyB9CmlmKHguaW5kZXhPZigiRFJJVkVSIikgPj0gMCB8fCB4LmluZGV4T2YoIkxJQ0VOU0UiKSA+PSAwIHx8IHguaW5kZXhPZigiTU9UT1IgVkVESUNMRVMiKSA+PSAwIHx8IHguaW5kZXhPZigiRE1WIikgPj0gMCl7IHJldHVybiAibGljZW5jaWEiOyB9CmlmKHguaW5kZXhPZigiUEVSTUlTTyIpID49IDApeyByZXR1cm4gIm90cm8iOyB9CnJldHVybiAiIjsKfWNhdGNoKGUpeyByZXR1cm4gIiI7IH0gfQpmdW5jdGlvbiBmYW1pbGlhVGlwbyhzZWwpeyB0cnl7CnZhciB4ID0gbm9ybShzZWwpOwppZigheCl7IHJldHVybiAiIjsgfQppZih4LmluZGV4T2YoIkRVSSIpID49IDApeyByZXR1cm4gImR1aSI7IH0KaWYoeC5pbmRleE9mKCJQQVNBUE9SVEUiKSA+PSAwKXsgcmV0dXJuICJwYXNhcG9ydGUiOyB9CmlmKHguaW5kZXhPZigiTElDRU5DSUEiKSA+PSAwKXsgcmV0dXJuICJsaWNlbmNpYSI7IH0KaWYoeC5pbmRleE9mKCJFQUQiKSA+PSAwIHx8IHguaW5kZXhPZigiSUQgREUgRVNUQURPIikgPj0gMCB8fCB4LmluZGV4T2YoIklERU5USUZJQ0FDSU9OIERFIEVTVEFETyIpID49IDApeyByZXR1cm4gImlkX3VzYSI7IH0KaWYoeC5pbmRleE9mKCJQRVJNSVNPIikgPj0gMCB8fCB4LmluZGV4T2YoIk9UUk8iKSA+PSAwKXsgcmV0dXJuICJvdHJvIjsgfQpyZXR1cm4gIiI7Cn1jYXRjaChlKXsgcmV0dXJuICIiOyB9IH0KZnVuY3Rpb24gdGlwb0Rpc3RpbnRvKGZELCBmVCl7IHRyeXsKcmV0dXJuICEhKGZEICYmIGZUICYmIGZUICE9PSAib3RybyIgJiYgZkQgIT09IGZUKTsKfWNhdGNoKGUpeyByZXR1cm4gZmFsc2U7IH0gfQpmdW5jdGlvbiBkaXN0RXVjbChhLGIpeyB0cnl7CmlmKCFhIHx8ICFiIHx8ICFhLmxlbmd0aCB8fCAhYi5sZW5ndGggfHwgYS5sZW5ndGggIT09IGIubGVuZ3RoKXsgcmV0dXJuIC0xOyB9CnZhciBzID0gMCwgaSwgeDsKZm9yKGkgPSAwOyBpIDwgYS5sZW5ndGg7IGkrKyl7IHggPSBhW2ldIC0gYltpXTsgcyArPSB4ICogeDsgfQpyZXR1cm4gTWF0aC5zcXJ0KHMpOwp9Y2F0Y2goZSl7IHJldHVybiAtMTsgfSB9CmZ1bmN0aW9uIGRlY2lkaXJCaW8oZDEsZDIpeyB0cnl7CnZhciBkID0gZGlzdEV1Y2woZDEsIGQyKTsKcmV0dXJuIHsgZGlzdDogZCwgYmxvcXVlYTogKGQgPCAwKSA/IGZhbHNlIDogKGQgPiAwLjYwKSB9Owp9Y2F0Y2goZSl7IHJldHVybiB7IGRpc3Q6IC0xLCBibG9xdWVhOiBmYWxzZSB9OyB9IH0KLypaVEVTVC1FTkQqLwoKLyogPT09PT09PT09PT09PT09PT09PT09IDMpIGVzdGFkbyB5IHBhc29zID09PT09PT09PT09PT09PT09PT09PSAqLwp2YXIgVjYgPSB7CmZvdG9zT2s6IGZhbHNlLCBiaW9PazogZmFsc2UsIHppZENyZWFkbzogZmFsc2UsIGNsYXZlQWxJbmljaW86IGZhbHNlLAp1bHRpbW9QYXNvOiBudWxsLCBib3VuY2VzOiB7IHBzMzogMCwgY2xhdmU6IDAgfSwgcmVpbmljaW9zOiAwLApmYWxsYXNEb2M6IDAsIGZhbGxhc0JpbzogMCwgY2FjaGVPY3I6IHsgazogIiIsIHR4dDogIiIgfSwKdWx0Q2Fsb3I6IDAsIHdhcm1UOiBudWxsLCB3YXJtTjogMCwgY29ycmlnaWVuZG86IDAsIF9idXN5OiAwCn07CndpbmRvdy5fX3p5cmFWNmUgPSBWNjsKdmFyIE1FQyA9IHsgdmlzOiBbXSwgb2NjOiBbXSB9OwoKZnVuY3Rpb24gcGFzb3MoKXsgdHJ5ewp2YXIgdG9kb3MgPSBELnF1ZXJ5U2VsZWN0b3JBbGwoIltpZF0iKSwgbGlzdGEgPSBbXSwgaSwgbTsKZm9yKGkgPSAwOyBpIDwgdG9kb3MubGVuZ3RoOyBpKyspewptID0gL15wcyhcZCspJC8uZXhlYyh0b2Rvc1tpXS5pZCB8fCAiIik7CmlmKG0peyBsaXN0YS5wdXNoKHsgbjogcGFyc2VJbnQobVsxXSwgMTApLCBlbDogdG9kb3NbaV0gfSk7IH0gfQpsaXN0YS5zb3J0KGZ1bmN0aW9uKGEsIGIpeyByZXR1cm4gYS5uIC0gYi5uOyB9KTsKcmV0dXJuIGxpc3RhOwp9Y2F0Y2goZSl7IHJldHVybiBbXTsgfSB9CgpmdW5jdGlvbiBlc1Zpc2libGUoZWwpeyB0cnl7CmlmKCFlbCl7IHJldHVybiBmYWxzZTsgfQp2YXIgY3MgPSB3aW5kb3cuZ2V0Q29tcHV0ZWRTdHlsZSA/IHdpbmRvdy5nZXRDb21wdXRlZFN0eWxlKGVsKSA6IG51bGw7CnZhciBkID0gY3MgPyBjcy5kaXNwbGF5IDogKGVsLnN0eWxlID8gZWwuc3R5bGUuZGlzcGxheSA6ICIiKTsKaWYoZCA9PT0gIm5vbmUiKXsgcmV0dXJuIGZhbHNlOyB9CmlmKGNzICYmIGNzLnZpc2liaWxpdHkgPT09ICJoaWRkZW4iKXsgcmV0dXJuIGZhbHNlOyB9CnJldHVybiB0cnVlOwp9Y2F0Y2goZSl7IHJldHVybiBmYWxzZTsgfSB9CgpmdW5jdGlvbiBwYXNvVmlzaWJsZShsaXN0YSl7IHRyeXsKZm9yKHZhciBpID0gMDsgaSA8IGxpc3RhLmxlbmd0aDsgaSsrKXsgaWYoZXNWaXNpYmxlKGxpc3RhW2ldLmVsKSl7IHJldHVybiBsaXN0YVtpXTsgfSB9CnJldHVybiBudWxsOwp9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9IH0KCmZ1bmN0aW9uIHBhc29EZUVsKGxpc3RhLCBlbCl7IHRyeXsKdmFyIHAgPSBlbDsKd2hpbGUocCl7CmlmKHAuaWQgJiYgL15wc1xkKyQvLnRlc3QocC5pZCkpewpmb3IodmFyIGkgPSAwOyBpIDwgbGlzdGEubGVuZ3RoOyBpKyspeyBpZihsaXN0YVtpXS5lbCA9PT0gcCl7IHJldHVybiBsaXN0YVtpXTsgfSB9CnJldHVybiBudWxsOyB9CnAgPSBwLnBhcmVudE5vZGUgJiYgcC5wYXJlbnROb2RlLm5vZGVUeXBlID09PSAxID8gcC5wYXJlbnROb2RlIDogbnVsbDsgfQpyZXR1cm4gbnVsbDsKfWNhdGNoKGUpeyByZXR1cm4gbnVsbDsgfSB9CgpmdW5jdGlvbiBwYXNvTm9tYnJlKGxpc3RhKXsgdHJ5ewp2YXIgbiA9ICQoIm5vbWJyZSIpOwppZihuKXsgdmFyIHAgPSBwYXNvRGVFbChsaXN0YSwgbik7IGlmKHApeyByZXR1cm4gcDsgfSB9CnJldHVybiBsaXN0YS5sZW5ndGggPyBsaXN0YVswXSA6IG51bGw7Cn1jYXRjaChlKXsgcmV0dXJuIGxpc3RhLmxlbmd0aCA/IGxpc3RhWzBdIDogbnVsbDsgfSB9CgpmdW5jdGlvbiBwYXNvQmlvKGxpc3RhKXsgdHJ5ewp2YXIgcmVmID0gJCgidnpBIikgfHwgJCgidmRBIik7CmlmKHJlZil7IHJldHVybiBwYXNvRGVFbChsaXN0YSwgcmVmKTsgfQpmb3IodmFyIGkgPSAwOyBpIDwgbGlzdGEubGVuZ3RoOyBpKyspeyBpZihsaXN0YVtpXS5uID09PSAzKXsgcmV0dXJuIGxpc3RhW2ldOyB9IH0KcmV0dXJuIG51bGw7Cn1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0gfQoKZnVuY3Rpb24gcGFzb0NsYXZlKGxpc3RhKXsgdHJ5ewpmb3IodmFyIGkgPSAwOyBpIDwgbGlzdGEubGVuZ3RoOyBpKyspewp2YXIgaW5zID0gbGlzdGFbaV0uZWwucXVlcnlTZWxlY3RvckFsbCA/IGxpc3RhW2ldLmVsLnF1ZXJ5U2VsZWN0b3JBbGwoImlucHV0IikgOiBbXTsKZm9yKHZhciBqID0gMDsgaiA8IGlucy5sZW5ndGg7IGorKyl7CnZhciB0eSA9IChpbnNbal0uZ2V0QXR0cmlidXRlKCJ0eXBlIikgfHwgInRleHQiKS50b0xvd2VyQ2FzZSgpOwp2YXIgaWRuID0gKChpbnNbal0uaWQgfHwgIiIpICsgIiAiICsgKGluc1tqXS5uYW1lIHx8ICIiKSArICIgIiArIChpbnNbal0uZ2V0QXR0cmlidXRlKCJwbGFjZWhvbGRlciIpIHx8ICIiKSkudG9Mb3dlckNhc2UoKTsKaWYodHkgPT09ICJwYXNzd29yZCIgfHwgL2NsYXZlfGNvbnRyYXN8cGluLy50ZXN0KGlkbikpeyByZXR1cm4gbGlzdGFbaV07IH0gfSB9CnJldHVybiBudWxsOwp9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9IH0KCmZ1bmN0aW9uIGRldGVjdGFyTWVjYW5pc21vKCl7IHRyeXsKdmFyIGxpc3RhID0gcGFzb3MoKSwgdmlzID0gbnVsbCwgb2NjID0gbnVsbCwgaTsKZm9yKGkgPSAwOyBpIDwgbGlzdGEubGVuZ3RoOyBpKyspeyBpZihlc1Zpc2libGUobGlzdGFbaV0uZWwpKXsgdmlzID0gbGlzdGFbaV0uZWw7IGJyZWFrOyB9IH0KZm9yKGkgPSAwOyBpIDwgbGlzdGEubGVuZ3RoOyBpKyspeyBpZihsaXN0YVtpXS5lbCAhPT0gdmlzICYmICFvY2MpeyBvY2MgPSBsaXN0YVtpXS5lbDsgfSB9CmlmKCF2aXMgfHwgIW9jYyl7IHJldHVybjsgfQp2YXIgY3YgPSBTdHJpbmcodmlzLmNsYXNzTmFtZSB8fCAiIikuc3BsaXQoL1xzKy8pOwp2YXIgY28gPSBTdHJpbmcob2NjLmNsYXNzTmFtZSB8fCAiIikuc3BsaXQoL1xzKy8pOwp2YXIgc3YgPSBbXSwgc28gPSBbXSwgYTsKZm9yKGEgPSAwOyBhIDwgY3YubGVuZ3RoOyBhKyspeyBpZihjdlthXSAmJiBjby5pbmRleE9mKGN2W2FdKSA8IDAgJiYgc3YuaW5kZXhPZihjdlthXSkgPCAwKXsgc3YucHVzaChjdlthXSk7IH0gfQpmb3IoYSA9IDA7IGEgPCBjby5sZW5ndGg7IGErKyl7IGlmKGNvW2FdICYmIGN2LmluZGV4T2YoY29bYV0pIDwgMCAmJiBzby5pbmRleE9mKGNvW2FdKSA8IDApeyBzby5wdXNoKGNvW2FdKTsgfSB9Ck1FQyA9IHsgdmlzOiBzdiwgb2NjOiBzbyB9Owp9Y2F0Y2goZSl7fSB9CgpmdW5jdGlvbiBhcGxpY2FyVmlzKGVsLCB2aXMpeyB0cnl7CmVsLnN0eWxlLmRpc3BsYXkgPSB2aXMgPyAiIiA6ICJub25lIjsKaWYoZWwuY2xhc3NMaXN0KXsKdmFyIGk7CmZvcihpID0gMDsgaSA8IE1FQy5vY2MubGVuZ3RoOyBpKyspeyBpZih2aXMpeyBlbC5jbGFzc0xpc3QucmVtb3ZlKE1FQy5vY2NbaV0pOyB9IGVsc2UgaWYoIWVsLmNsYXNzTGlzdC5jb250YWlucyhNRUMub2NjW2ldKSl7IGVsLmNsYXNzTGlzdC5hZGQoTUVDLm9jY1tpXSk7IH0gfQpmb3IoaSA9IDA7IGkgPCBNRUMudmlzLmxlbmd0aDsgaSsrKXsgaWYodmlzKXsgaWYoIWVsLmNsYXNzTGlzdC5jb250YWlucyhNRUMudmlzW2ldKSl7IGVsLmNsYXNzTGlzdC5hZGQoTUVDLnZpc1tpXSk7IH0gfSBlbHNlIHsgZWwuY2xhc3NMaXN0LnJlbW92ZShNRUMudmlzW2ldKTsgfSB9IH0KfWNhdGNoKGUpe30gfQoKZnVuY3Rpb24gaXJBKHBhc28peyB0cnl7CmlmKCFwYXNvKXsgcmV0dXJuOyB9CmlmKCFNRUMudmlzLmxlbmd0aCAmJiAhTUVDLm9jYy5sZW5ndGgpeyB0cnl7IGRldGVjdGFyTWVjYW5pc21vKCk7IH1jYXRjaChlMCl7fSB9CnZhciBsaXN0YSA9IHBhc29zKCk7CmZvcih2YXIgaSA9IDA7IGkgPCBsaXN0YS5sZW5ndGg7IGkrKyl7IGFwbGljYXJWaXMobGlzdGFbaV0uZWwsIGxpc3RhW2ldLmVsID09PSBwYXNvLmVsKTsgfQp0cnl7IHdpbmRvdy5zY3JvbGxUbygwLCAwKTsgfWNhdGNoKGUxKXt9ClY2LnVsdGltb1Bhc28gPSBwYXNvOwp9Y2F0Y2goZSl7fSB9CgpmdW5jdGlvbiBub21icmVWaWdlbnRlKCl7IHRyeXsKdmFyIGlucCA9IGlucHV0Tm9tYnJlKCk7CnZhciB2ID0gaW5wID8gU3RyaW5nKGlucC52YWx1ZSB8fCAiIikudHJpbSgpIDogIiI7CnZhciB0ayA9IHRva2Vucyh2KTsKcmV0dXJuIHsgdmFsb3I6IHYsIG9rOiAodGsubGVuZ3RoID49IDIgJiYgbm9ybSh2KS5sZW5ndGggPj0gNSkgfTsKfWNhdGNoKGUpeyByZXR1cm4geyB2YWxvcjogIiIsIG9rOiBmYWxzZSB9OyB9IH0KCmZ1bmN0aW9uIHJlaW5pY2lhckZvdG9zKCl7IHRyeXsKdmFyIGxpc3RhID0gcGFzb3MoKSwgaSwgcHMyID0gbnVsbDsKZm9yKGkgPSAwOyBpIDwgbGlzdGEubGVuZ3RoOyBpKyspeyBpZihsaXN0YVtpXS5uID09PSAyKXsgcHMyID0gbGlzdGFbaV0uZWw7IGJyZWFrOyB9IH0KdmFyIGJhc2UgPSBwczIgfHwgRDsKdmFyIGZpcyA9IGJhc2UucXVlcnlTZWxlY3RvckFsbCA/IGJhc2UucXVlcnlTZWxlY3RvckFsbCgiaW5wdXRbdHlwZT1maWxlXSIpIDogW107CmZvcihpID0gMDsgaSA8IGZpcy5sZW5ndGg7IGkrKyl7IHRyeXsgZmlzW2ldLnZhbHVlID0gIiI7IH1jYXRjaChlMSl7fSB9CnZhciBpbXMgPSBiYXNlLnF1ZXJ5U2VsZWN0b3JBbGwgPyBiYXNlLnF1ZXJ5U2VsZWN0b3JBbGwoImltZyIpIDogW107CmZvcihpID0gMDsgaSA8IGltcy5sZW5ndGg7IGkrKyl7IHRyeXsgaW1zW2ldLnJlbW92ZUF0dHJpYnV0ZSgic3JjIik7IH1jYXRjaChlMil7fSB9Cn1jYXRjaChlKXt9ClY2LmZvdG9zT2sgPSBmYWxzZTsKVjYuY2FjaGVPY3IgPSB7IGs6ICIiLCB0eHQ6ICIiIH07IH0KCmZ1bmN0aW9uIHJlaW5pY2lhclRvZG8obW90aXZvKXsgdHJ5ewpiYW5uZXIobW90aXZvLCB0cnVlKTsKaWYoVjYucmVpbmljaW9zID49IDMpeyByZXR1cm47IH0KVjYucmVpbmljaW9zKys7CnJlaW5pY2lhckZvdG9zKCk7ClY2LmJpb09rID0gZmFsc2U7IFY2LnppZENyZWFkbyA9IGZhbHNlOyBWNi5mYWxsYXNEb2MgPSAwOyBWNi5mYWxsYXNCaW8gPSAwOwpWNi5ib3VuY2VzID0geyBwczM6IDAsIGNsYXZlOiAwIH07CnZhciBsaXN0YSA9IHBhc29zKCk7CmlyQShwYXNvTm9tYnJlKGxpc3RhKSB8fCAobGlzdGEubGVuZ3RoID8gbGlzdGFbMF0gOiBudWxsKSk7Cn1jYXRjaChlKXt9IH0KCmZ1bmN0aW9uIHByaW1lckZhbGxvKGxpc3RhKXsgdHJ5ewp2YXIgbm9tID0gbm9tYnJlVmlnZW50ZSgpOwp2YXIgcG4gPSBwYXNvTm9tYnJlKGxpc3RhKTsKaWYoIW5vbS5vayl7IHJldHVybiB7IHBhc286IHBuLCBtb3Rpdm86ICJub21icmUiIH07IH0KaWYoIVY2LmZvdG9zT2spewp2YXIgcDIgPSBudWxsLCBpOwpmb3IoaSA9IDA7IGkgPCBsaXN0YS5sZW5ndGg7IGkrKyl7IGlmKGxpc3RhW2ldLm4gPT09IDIpeyBwMiA9IGxpc3RhW2ldOyBicmVhazsgfSB9CnJldHVybiB7IHBhc286IHAyIHx8IHBuLCBtb3Rpdm86ICJmb3RvcyIgfTsgfQppZighVjYuYmlvT2speyByZXR1cm4geyBwYXNvOiBwYXNvQmlvKGxpc3RhKSwgbW90aXZvOiAiYmlvIiB9OyB9CnJldHVybiBudWxsOwp9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9IH0KCmZ1bmN0aW9uIGNvcnJlZ2lyKHBmLCBtc2cpeyB0cnl7CnZhciB0ID0gbmV3IERhdGUoKS5nZXRUaW1lKCk7ClY2LmNvcnJpZ2llbmRvID0gdDsKYmFubmVyKG1zZywgdHJ1ZSk7CmlyQShwZi5wYXNvKTsKc2V0VGltZW91dChmdW5jdGlvbigpeyB0cnl7IGlmKFY2LmNvcnJpZ2llbmRvID09PSB0KXsgVjYuY29ycmlnaWVuZG8gPSAwOyB9IH1jYXRjaChlKXt9IH0sIDIwMCk7Cn1jYXRjaChlKXt9IH0KCi8qID09PT09PT09PT09PT09PT09PT09PSA0KSBndWFyZGlhbiBkZWwgb3JkZW4gZGUgbG9zIHBhc29zID09PT09PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiB2ZXJpZmljYXIoZm9yemFkbyl7IHRyeXsKaWYoVjYuY29ycmlnaWVuZG8peyByZXR1cm47IH0KdmFyIGxpc3RhID0gcGFzb3MoKTsKaWYoIWxpc3RhLmxlbmd0aCl7IHJldHVybjsgfQp2YXIgdmlzID0gcGFzb1Zpc2libGUobGlzdGEpOwppZighdmlzKXsgcmV0dXJuOyB9CnZhciBodWJvVHJhbnNpY2lvbiA9ICEhKFY2LnVsdGltb1Bhc28gJiYgVjYudWx0aW1vUGFzby5lbCAhPT0gdmlzLmVsKTsKVjYudWx0aW1vUGFzbyA9IHZpczsKaWYoIWh1Ym9UcmFuc2ljaW9uICYmICFmb3J6YWRvKXsgY2FsZW50YXIoZmFsc2UpOyByZXR1cm47IH0KdmFyIGZpbiA9IGxpc3RhW2xpc3RhLmxlbmd0aCAtIDFdOwp2YXIgcGMgPSBwYXNvQ2xhdmUobGlzdGEpOwppZihmaW4gJiYgdmlzLmVsID09PSBmaW4uZWwgJiYgIShwYyAmJiB2aXMuZWwgPT09IHBjLmVsKSl7IFY2LnppZENyZWFkbyA9IHRydWU7IGNhbGVudGFyKGZhbHNlKTsgcmV0dXJuOyB9CmlmKGh1Ym9UcmFuc2ljaW9uICYmIHZpcy5uID49IDIgJiYgIW5vbWJyZVZpZ2VudGUoKS5vayl7CmNvcnJlZ2lyKHsgcGFzbzogcGFzb05vbWJyZShsaXN0YSkgfHwgbGlzdGFbMF0gfSwgIkVzY3JpYmEgc3Ugbm9tYnJlIGNvbXBsZXRvIChub21icmUgeSBhcGVsbGlkbykgZW4gZWwgUGFzbyAxIGFudGVzIGRlIGNvbnRpbnVhci4iKTsKcmV0dXJuOyB9CmlmKHBjICYmIHZpcy5lbCA9PT0gcGMuZWwgJiYgIVY2LnppZENyZWFkbyAmJiAhVjYuY2xhdmVBbEluaWNpbyl7CnZhciBwZiA9IHByaW1lckZhbGxvKGxpc3RhKTsKaWYocGYgJiYgcGYucGFzbyl7ClY2LmJvdW5jZXMuY2xhdmUrKzsKaWYoVjYuYm91bmNlcy5jbGF2ZSA+IDMpeyBiYW5uZXIoIkF2aXNvOiBubyBzZSBwdWRvIHZhbGlkYXIgYXV0b21hdGljYW1lbnRlIGVsIG9yZGVuLiBDb250aW51ZSBjb24gcHJlY2F1Y2lvbi4iLCBmYWxzZSk7IHJldHVybjsgfQppZihwZi5tb3Rpdm8gPT09ICJub21icmUiKXsgY29ycmVnaXIocGYsICJQYXJhIGNyZWFyIHN1IFpJRCBkZWJlIGVzY3JpYmlyIHN1IG5vbWJyZSBjb21wbGV0byBlbiBlbCBQYXNvIDEuIik7IH0KZWxzZSBpZihwZi5tb3Rpdm8gPT09ICJmb3RvcyIpeyBjb3JyZWdpcihwZiwgIlBhcmEgY3JlYXIgc3UgWklEIGRlYmUgdmFsaWRhciBlbCBkb2N1bWVudG8gZW4gZWwgUGFzbyAyIChmb3RvcykuIik7IH0KZWxzZSB7IGNvcnJlZ2lyKHBmLCAiUGFyYSBjcmVhciBzdSBaSUQgZGViZSBwYXNhciBsYSBiaW9tZXRyaWEgKHNlbGZpZSkuIFRvbWVsYSBkZSBudWV2by4iKTsgfQpyZXR1cm47IH0gfQp2YXIgcGIgPSBwYXNvQmlvKGxpc3RhKTsKaWYocGIgJiYgdmlzLmVsID09PSBwYi5lbCAmJiAhVjYuZm90b3NPayl7ClY2LmJvdW5jZXMucHMzKys7CmlmKFY2LmJvdW5jZXMucHMzID4gMyl7IGJhbm5lcigiQXZpc286IG5vIHNlIHB1ZG8gdmFsaWRhciBlbCBkb2N1bWVudG8gYXV0b21hdGljYW1lbnRlLiBDb250aW51ZSBjb24gcHJlY2F1Y2lvbi4iLCBmYWxzZSk7IFY2LmZvdG9zT2sgPSB0cnVlOyByZXR1cm47IH0KdmFyIHAyYiA9IG51bGwsIGliOwpmb3IoaWIgPSAwOyBpYiA8IGxpc3RhLmxlbmd0aDsgaWIrKyl7IGlmKGxpc3RhW2liXS5uID09PSAyKXsgcDJiID0gbGlzdGFbaWJdOyBicmVhazsgfSB9CmNvcnJlZ2lyKHsgcGFzbzogcDJiIHx8IHBhc29Ob21icmUobGlzdGEpIHx8IGxpc3RhWzBdIH0sICJObyBwdWVkZSBwYXNhciBhIGxhIGJpb21ldHJpYSBzaW4gdmFsaWRhciBsYXMgZm90b3MgZGVsIGRvY3VtZW50by4gVmVyaWZpcXVlbGFzIGVuIGVsIFBhc28gMi4iKTsKcmV0dXJuOyB9CmNhbGVudGFyKGZhbHNlKTsKfWNhdGNoKGUpe30gfQoKLyogPT09PT09PT09PT09PT09PT09PT09IDUpIGdhdGVzIGRlIGNsaWMgKGRvY3VtZW50byB5IGJpb21ldHJpYSkgPT09PT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gb2NyRG9jTWVqb3IoKXsgdHJ5ewp2YXIgZG9jcyA9IG1lZGlhTGlzdGEoInBzMiIpOwppZighZG9jcy5sZW5ndGgpeyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKHsgdGV4dG86ICIiLCBmYW1pbGlhOiAiIiB9KTsgfQp2YXIgaW5wID0gaW5wdXROb21icmUoKTsKdmFyIG5vbSA9IGlucCA/IFN0cmluZyhpbnAudmFsdWUgfHwgIiIpIDogIiI7CnZhciBpZHggPSAwOwp2YXIgbWVqb3IgPSB7IHRleHRvOiAiIiwgc2ltOiAtMSwgZmFtaWxpYTogIiIgfTsKZnVuY3Rpb24gcGFzbygpewppZihpZHggPj0gZG9jcy5sZW5ndGgpeyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKG1lam9yKTsgfQp2YXIgZWwgPSBkb2NzW2lkeF07IGlkeCsrOwp2YXIgayA9IGZpcm1hKGVsKTsKdmFyIHByOwppZihrICYmIGsgPT09IFY2LmNhY2hlT2NyLmsgJiYgVjYuY2FjaGVPY3IudHh0KXsgcHIgPSBQcm9taXNlLnJlc29sdmUoVjYuY2FjaGVPY3IudHh0KTsgfQplbHNlIHsgcHIgPSBvY3JEZShlbCkudGhlbihmdW5jdGlvbih0eHQpeyB0cnl7IGlmKHR4dCl7IFY2LmNhY2hlT2NyID0geyBrOiBrLCB0eHQ6IHR4dCB9OyB9IH1jYXRjaChlMSl7fSByZXR1cm4gdHh0OyB9KTsgfQpyZXR1cm4gcHIudGhlbihmdW5jdGlvbih0eCl7CnRyeXsKaWYodHgpewp2YXIgcyA9IHNpbU5vbWJyZXMobm9tLCB0eCk7CmlmKHMgPiBtZWpvci5zaW0peyBtZWpvciA9IHsgdGV4dG86IHR4LCBzaW06IHMsIGZhbWlsaWE6IG1lam9yLmZhbWlsaWEgfTsgfQppZighbWVqb3IuZmFtaWxpYSl7IHZhciBmZCA9IGZhbWlsaWFEb2ModHgpOyBpZihmZCl7IG1lam9yLmZhbWlsaWEgPSBmZDsgfSB9IH0KfWNhdGNoKGUyKXt9CnJldHVybiBwYXNvKCk7Cn0pOyB9CnJldHVybiBwYXNvKCk7Cn1jYXRjaChlKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZSh7IHRleHRvOiAiIiwgZmFtaWxpYTogIiIgfSk7IH0gfQoKZnVuY3Rpb24gZ2F0ZURvYyhldiwgZWwpeyB0cnl7CmlmKFY2Ll9idXN5KXsgcmV0dXJuOyB9ClY2Ll9idXN5ID0gMTsKdmFyIG5vbSA9IG5vbWJyZVZpZ2VudGUoKTsKaWYoIW5vbS5vayl7IGJsb3F1ZWFyKGV2KTsgb3ZlcmxheShmYWxzZSk7CmJhbm5lcigiRXNjcmliYSBzdSBub21icmUgY29tcGxldG8gKG5vbWJyZSB5IGFwZWxsaWRvKSBhbnRlcyBkZSBjb250aW51YXIuIiwgdHJ1ZSk7CnZhciBsMCA9IHBhc29zKCk7IGlyQShwYXNvTm9tYnJlKGwwKSB8fCAobDAubGVuZ3RoID8gbDBbMF0gOiBudWxsKSk7CnJldHVybjsgfQp2YXIgdGlwbyA9IHNlbGVjdFRpcG8oKTsKYmxvcXVlYXIoZXYpOwpvdmVybGF5KHRydWUsICJWZXJpZmljYW5kbyBub21icmUgeSB0aXBvIGRlIGRvY3VtZW50by4uLiIpOwpvY3JEb2NNZWpvcigpLnRoZW4oZnVuY3Rpb24ocmVzKXsgdHJ5ewpvdmVybGF5KGZhbHNlKTsKdmFyIHR4ID0gcmVzICYmIHJlcy50ZXh0byA/IHJlcy50ZXh0byA6ICIiOwppZighdHgpeyBWNi5mYWxsYXNEb2MrKzsKaWYoVjYuZmFsbGFzRG9jID49IDIpeyBWNi5mYWxsYXNEb2MgPSAwOyBWNi5mb3Rvc09rID0gdHJ1ZTsgcGFzYXIoZWwpOyB9CmVsc2UgeyBiYW5uZXIoIk5vIHNlIHB1ZG8gbGVlciBlbCBkb2N1bWVudG8uIE1lam9yZSBsYSBsdXogeSB2dWVsdmEgYSBjYXB0dXJhciwgbyBwcmVzaW9uZSBjb250aW51YXIgZGUgbnVldm8uIiwgdHJ1ZSk7IH0KcmV0dXJuOyB9CnZhciBzID0gc2ltTm9tYnJlcyhub20udmFsb3IsIHR4KTsKdmFyIGZEID0gcmVzLmZhbWlsaWEgfHwgZmFtaWxpYURvYyh0eCk7CnZhciBmVCA9IGZhbWlsaWFUaXBvKHRpcG8pOwppZihzIDwgMC42MCl7ClY2LmZhbGxhc0RvYyA9IDA7IFY2LmZvdG9zT2sgPSBmYWxzZTsKYmFubmVyKCJFbCBub21icmUgTk8gY29pbmNpZGUgY29uIGVsIGRvY3VtZW50byAoIiArIE1hdGgucm91bmQocyAqIDEwMCkgKyAiJSkuIFNlIGxlIGxsZXZhIGFsIFBhc28gMSBwYXJhIGNvcnJlZ2lyIGVsIG5vbWJyZSB5IHZvbHZlciBhIHRvbWFyIGxhcyBmb3Rvcy4iLCB0cnVlKTsKcmVpbmljaWFyRm90b3MoKTsKdmFyIGwxID0gcGFzb3MoKTsgaXJBKHBhc29Ob21icmUobDEpIHx8IChsMS5sZW5ndGggPyBsMVswXSA6IG51bGwpKTsKcmV0dXJuOyB9CmlmKHRpcG9EaXN0aW50byhmRCwgZlQpKXsKVjYuZmFsbGFzRG9jID0gMDsgVjYuZm90b3NPayA9IGZhbHNlOwpiYW5uZXIoIkNhcHR1cm8gdW4gZG9jdW1lbnRvIHRpcG8gIiArIGZEICsgIiBwZXJvIHNlbGVjY2lvbm8gIiArIGZUICsgIi4gU2UgbGUgbGxldmEgYWwgUGFzbyAxIHBhcmEgY29ycmVnaXIgZWwgdGlwbyB5IHZvbHZlciBhIHRvbWFyIGxhcyBmb3Rvcy4iLCB0cnVlKTsKcmVpbmljaWFyRm90b3MoKTsKdmFyIGwyID0gcGFzb3MoKTsgaXJBKHBhc29Ob21icmUobDIpIHx8IChsMi5sZW5ndGggPyBsMlswXSA6IG51bGwpKTsKcmV0dXJuOyB9ClY2LmZhbGxhc0RvYyA9IDA7IFY2LmZvdG9zT2sgPSB0cnVlOwpwYXNhcihlbCk7Cn1jYXRjaChlKXsgb3ZlcmxheShmYWxzZSk7IFY2LmZhbGxhc0RvYysrOyBpZihWNi5mYWxsYXNEb2MgPj0gMil7IFY2LmZhbGxhc0RvYyA9IDA7IFY2LmZvdG9zT2sgPSB0cnVlOyBwYXNhcihlbCk7IH0gZWxzZSB7IGJhbm5lcigiTm8gc2UgcHVkbyB2ZXJpZmljYXIgZWwgZG9jdW1lbnRvLiBJbnRlbnRlIGRlIG51ZXZvLiIsIHRydWUpOyB9IH0KfSwgZnVuY3Rpb24oKXsgb3ZlcmxheShmYWxzZSk7IFY2LmZhbGxhc0RvYysrOyBpZihWNi5mYWxsYXNEb2MgPj0gMil7IFY2LmZhbGxhc0RvYyA9IDA7IFY2LmZvdG9zT2sgPSB0cnVlOyBwYXNhcihlbCk7IH0gZWxzZSB7IGJhbm5lcigiTm8gc2UgcHVkbyB2ZXJpZmljYXIgZWwgZG9jdW1lbnRvLiBJbnRlbnRlIGRlIG51ZXZvLiIsIHRydWUpOyB9IH0pOwp9Y2F0Y2goZSl7IHRyeXsgb3ZlcmxheShmYWxzZSk7IFY2LmZvdG9zT2sgPSB0cnVlOyBwYXNhcihlbCk7IH1jYXRjaChlMil7fSB9IH0KCmZ1bmN0aW9uIGNvbXBhcmFyUm9zdHJvc1Y2KCl7IHRyeXsKdmFyIGYgPSB3aW5kb3cuZmFjZWFwaTsKaWYoIWYgfHwgIWYubmV0cyB8fCAhZi5uZXRzLmZhY2VSZWNvZ25pdGlvbk5ldCB8fCAhZi5uZXRzLmZhY2VSZWNvZ25pdGlvbk5ldC5pc0xvYWRlZCl7IHJldHVybiBQcm9taXNlLnJlc29sdmUobnVsbCk7IH0KdmFyIGRldCA9IG51bGw7CnRyeXsgaWYoZi5uZXRzLnRpbnlGYWNlRGV0ZWN0b3IgJiYgZi5uZXRzLnRpbnlGYWNlRGV0ZWN0b3IuaXNMb2FkZWQpeyBkZXQgPSBuZXcgZi5UaW55RmFjZURldGVjdG9yT3B0aW9ucyh7IGlucHV0U2l6ZTogMzIwLCBzY29yZVRocmVzaG9sZDogMC40IH0pOyB9IH1jYXRjaChlKXt9CnRyeXsgaWYoIWRldCAmJiBmLm5ldHMuc3NkTW9iaWxlbmV0djEgJiYgZi5uZXRzLnNzZE1vYmlsZW5ldHYxLmlzTG9hZGVkKXsgZGV0ID0gbmV3IGYuU3NkTW9iaWxlbmV0djFPcHRpb25zKHsgbWluQ29uZmlkZW5jZTogMC40IH0pOyB9IH1jYXRjaChlKXt9CmlmKCFkZXQpeyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKG51bGwpOyB9CnZhciBkb2NzID0gbWVkaWFMaXN0YSgicHMyIik7CnZhciBzZWxmID0gbWVkaWFFbigicHMzIikgfHwgbWVkaWFFbigicHM0Iik7CmlmKCFzZWxmIHx8ICFkb2NzIHx8ICFkb2NzLmxlbmd0aCl7IHJldHVybiBQcm9taXNlLnJlc29sdmUobnVsbCk7IH0KZnVuY3Rpb24gZGVzY0RlKGVsKXsgdHJ5ewp2YXIgYyA9IGFDYW52YXMoZWwsIDY0MCk7CmlmKCFjKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZShudWxsKTsgfQpyZXR1cm4gZi5kZXRlY3RTaW5nbGVGYWNlKGMsIGRldCkud2l0aEZhY2VEZXNjcmlwdG9yKCkudGhlbihmdW5jdGlvbihyKXsgcmV0dXJuIChyICYmIHIuZGVzY3JpcHRvciAmJiByLmRlc2NyaXB0b3IubGVuZ3RoKSA/IHIuZGVzY3JpcHRvciA6IG51bGw7IH0sIGZ1bmN0aW9uKCl7IHJldHVybiBudWxsOyB9KTsKfWNhdGNoKGUpeyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKG51bGwpOyB9IH0KZnVuY3Rpb24gcHJpbWVyRG9jKGkpewppZihpID49IGRvY3MubGVuZ3RoKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZShudWxsKTsgfQpyZXR1cm4gZGVzY0RlKGRvY3NbaV0pLnRoZW4oZnVuY3Rpb24oZCl7IHJldHVybiBkID8gZCA6IHByaW1lckRvYyhpICsgMSk7IH0pOyB9CnJldHVybiBwcmltZXJEb2MoMCkudGhlbihmdW5jdGlvbihkRCl7CmlmKCFkRCl7IHJldHVybiBQcm9taXNlLnJlc29sdmUobnVsbCk7IH0KcmV0dXJuIGRlc2NEZShzZWxmKS50aGVuKGZ1bmN0aW9uKGRTKXsKaWYoIWRTKXsgcmV0dXJuIG51bGw7IH0KdmFyIHIgPSBkZWNpZGlyQmlvKGRELCBkUyk7CnJldHVybiByLmRpc3QgPCAwID8gbnVsbCA6ICFyLmJsb3F1ZWE7Cn0pOyB9KTsKfWNhdGNoKGUpeyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKG51bGwpOyB9IH0KCmZ1bmN0aW9uIGdhdGVCaW8oZXYsIGVsKXsgdHJ5ewppZihWNi5fYnVzeSl7IHJldHVybjsgfQpWNi5fYnVzeSA9IDE7CmJsb3F1ZWFyKGV2KTsKb3ZlcmxheSh0cnVlLCAiVmVyaWZpY2FuZG8gcm9zdHJvLi4uIik7CmNvbXBhcmFyUm9zdHJvc1Y2KCkudGhlbihmdW5jdGlvbihyKXsgdHJ5ewpvdmVybGF5KGZhbHNlKTsKaWYociA9PT0gdHJ1ZSl7IFY2LmZhbGxhc0JpbyA9IDA7IFY2LmJpb09rID0gdHJ1ZTsgcGFzYXIoZWwpOyByZXR1cm47IH0KaWYociA9PT0gZmFsc2UpeyBWNi5mYWxsYXNCaW8gPSAwOyBWNi5iaW9PayA9IGZhbHNlOwpiYW5uZXIoIkVsIHJvc3RybyBkZSBsYSBzZWxmaWUgTk8gY29pbmNpZGUgY29uIGVsIHJvc3RybyBkZWwgZG9jdW1lbnRvLiBUb21lIHVuYSBudWV2YSBzZWxmaWUuIiwgdHJ1ZSk7IHJldHVybjsgfQpWNi5mYWxsYXNCaW8rKzsKaWYoVjYuZmFsbGFzQmlvID49IDIpeyBWNi5mYWxsYXNCaW8gPSAwOyBiYW5uZXIoIkF2aXNvOiBubyBzZSBwdWRvIGNvbXBhcmFyIGxvcyByb3N0cm9zIGF1dG9tYXRpY2FtZW50ZS4gQ29udGludWUgY29uIHByZWNhdWNpb24uIiwgZmFsc2UpOyBWNi5iaW9PayA9IHRydWU7IHBhc2FyKGVsKTsgcmV0dXJuOyB9CmJhbm5lcigiTm8gc2UgcHVkbyBjb21wYXJhciBsb3Mgcm9zdHJvcy4gTWVqb3JlIGxhIGx1eiB5IHByZXNpb25lIGNvbnRpbnVhciBkZSBudWV2by4iLCB0cnVlKTsKfWNhdGNoKGUpeyB0cnl7IG92ZXJsYXkoZmFsc2UpOyB9Y2F0Y2goZTIpe30gfQp9LCBmdW5jdGlvbigpeyB0cnl7IG92ZXJsYXkoZmFsc2UpOyBWNi5mYWxsYXNCaW8rKzsgaWYoVjYuZmFsbGFzQmlvID49IDIpeyBWNi5mYWxsYXNCaW8gPSAwOyBWNi5iaW9PayA9IHRydWU7IHBhc2FyKGVsKTsgfSBlbHNlIHsgYmFubmVyKCJObyBzZSBwdWRvIGNvbXBhcmFyIGxvcyByb3N0cm9zLiBJbnRlbnRlIGRlIG51ZXZvLiIsIHRydWUpOyB9IH1jYXRjaChlKXt9IH0pOwp9Y2F0Y2goZSl7IHRyeXsgb3ZlcmxheShmYWxzZSk7IH1jYXRjaChlMil7fSB9IH0KCkQuYWRkRXZlbnRMaXN0ZW5lcigiY2xpY2siLCBmdW5jdGlvbihldil7IHRyeXsKaWYoZXYgJiYgZXYuaXNUcnVzdGVkID09PSBmYWxzZSl7IHJldHVybjsgfQp2YXIgdGcgPSBldiAmJiBldi50YXJnZXQgPyBldi50YXJnZXQgOiBudWxsOwppZih0ZyAmJiB0Zy5fX3pWNil7IHRnLl9felY2ID0gMDsgcmV0dXJuOyB9CnZhciBlbDQgPSBidXNjYXJCb3RvbigiYklyNCIpLCBlbDUgPSBidXNjYXJCb3RvbigiYklyNSIpOwpmdW5jdGlvbiBkZUJvdG9uKGVsKXsgdHJ5eyByZXR1cm4gISEoZWwgJiYgdGcgJiYgKHRnID09PSBlbCB8fCAodGcuY2xvc2VzdCAmJiBlbC5pZCAmJiB0Zy5jbG9zZXN0KCIjIiArIGVsLmlkKSA9PT0gZWwpKSk7IH1jYXRjaChlKXsgcmV0dXJuIGZhbHNlOyB9IH0KaWYoZGVCb3RvbihlbDQpKXsgZ2F0ZURvYyhldiwgZWw0KTsgfQplbHNlIGlmKGRlQm90b24oZWw1KSl7IGdhdGVCaW8oZXYsIGVsNSk7IH0KfWNhdGNoKGUpe30gfSwgdHJ1ZSk7CgovKiA9PT09PT09PT09PT09PT09PT09PT0gNikgZmV0Y2ggd3JhcHBlciArIHdhcm11cCBhbnRpLTUwMiA9PT09PT09PT09PT09PT09PT09PT0gKi8KdmFyIF9mT3JpZyA9ICh0eXBlb2Ygd2luZG93LmZldGNoID09PSAiZnVuY3Rpb24iKSA/IHdpbmRvdy5mZXRjaCA6IG51bGw7CgpmdW5jdGlvbiBjYWxlbnRhcihmb3JjZSl7IHRyeXsKdmFyIHQgPSBuZXcgRGF0ZSgpLmdldFRpbWUoKTsKaWYoIWZvcmNlICYmICh0IC0gVjYudWx0Q2Fsb3IpIDwgODAwMCl7IHJldHVybjsgfQpWNi51bHRDYWxvciA9IHQ7CmlmKF9mT3JpZyl7CnRyeXsgX2ZPcmlnLmNhbGwod2luZG93LCAiLyIsIHsgY2FjaGU6ICJuby1zdG9yZSIsIGNyZWRlbnRpYWxzOiAib21pdCIgfSkudGhlbihmdW5jdGlvbigpe30sIGZ1bmN0aW9uKCl7fSk7IH1jYXRjaChlMSl7fQp9Cn1jYXRjaChlKXt9IH0KCmZ1bmN0aW9uIGFycmFuY2FyQ2Fsb3IoKXsgdHJ5ewpjYWxlbnRhcih0cnVlKTsKaWYoIVY2Lndhcm1UKXsKVjYud2FybVQgPSBzZXRJbnRlcnZhbChmdW5jdGlvbigpewpWNi53YXJtTisrOwppZihWNi53YXJtTiA+IDQwKXsgdHJ5eyBjbGVhckludGVydmFsKFY2Lndhcm1UKTsgfWNhdGNoKGUwKXt9IFY2Lndhcm1UID0gbnVsbDsgcmV0dXJuOyB9CmNhbGVudGFyKHRydWUpOwp9LCA0NTAwMCk7IH0KfWNhdGNoKGUpe30gfQoKdHJ5ewppZih0eXBlb2Ygd2luZG93LmZldGNoID09PSAiZnVuY3Rpb24iICYmICF3aW5kb3cuX196RmNoVjYpewp3aW5kb3cuX196RmNoVjYgPSB0cnVlOwp3aW5kb3cuZmV0Y2ggPSBmdW5jdGlvbigpewp2YXIgYSA9IGFyZ3VtZW50czsKdmFyIGVuQ2xhdmUgPSBmYWxzZTsKdHJ5ewp2YXIgbCA9IHBhc29zKCksIHYgPSBwYXNvVmlzaWJsZShsKSwgcGMgPSBwYXNvQ2xhdmUobCk7CmVuQ2xhdmUgPSAhISh2ICYmIHBjICYmIHYuZWwgPT09IHBjLmVsKTsKfWNhdGNoKGUwKXt9CnJldHVybiBfZk9yaWcuYXBwbHkod2luZG93LCBhKS50aGVuKGZ1bmN0aW9uKHIpewp0cnl7CnZhciBzdCA9IHIgPyByLnN0YXR1cyA6IDA7CmlmKGVuQ2xhdmUgJiYgKHN0ID09PSA1MDIgfHwgc3QgPT09IDUwMyB8fCBzdCA9PT0gNTA0KSAmJiAhKGFbMV0gJiYgYVsxXS5fX3pWNnJlKSl7CmNhbGVudGFyKHRydWUpOwp2YXIgb3AgPSB7fSwgazsKaWYoYVsxXSl7IGZvcihrIGluIGFbMV0peyBvcFtrXSA9IGFbMV1ba107IH0gfQpvcC5fX3pWNnJlID0gdHJ1ZTsKcmV0dXJuIF9mT3JpZy5jYWxsKHdpbmRvdywgYVswXSwgb3ApLnRoZW4oZnVuY3Rpb24ocjIpewp0cnl7CnZhciBzdDIgPSByMiA/IHIyLnN0YXR1cyA6IDA7CmlmKHN0MiA+PSA1MDApeyByZWluaWNpYXJUb2RvKCJFbCBzZXJ2aWRvciBubyBwdWRvIGNyZWFyIHN1IFpJRCAoIiArIHN0MiArICIpLiBTZSByZWluaWNpYSBlbCByZWdpc3RybyBjb21wbGV0byBkZXNkZSBlbCBQYXNvIDEuIik7IH0KfWNhdGNoKGUyKXt9CnJldHVybiByMjsKfSwgZnVuY3Rpb24oZXJyMil7CnRyeXsgcmVpbmljaWFyVG9kbygiRWwgc2Vydmlkb3Igbm8gcHVkbyBjcmVhciBzdSBaSUQuIFNlIHJlaW5pY2lhIGVsIHJlZ2lzdHJvIGNvbXBsZXRvIGRlc2RlIGVsIFBhc28gMS4iKTsgfWNhdGNoKGUzKXt9CnRocm93IGVycjI7IH0pOwp9CmlmKHN0ID09PSA0MTMpeyBiYW5uZXIoIkxhcyBmb3RvcyBzb24gbXV5IGdyYW5kZXMgcGFyYSBlbCBzZXJ2aWRvci4gVnVlbHZhIGEgdG9tYXJsYXMuIiwgdHJ1ZSk7IH0KZWxzZSBpZihzdCA9PT0gNTAwIHx8IHN0ID09PSA1MDIgfHwgc3QgPT09IDUwMyl7IGJhbm5lcigiRWwgc2Vydmlkb3Igbm8gcmVzcG9uZGlvIGJpZW4gKCIgKyBzdCArICIpLiBFc3BlcmUgdW5vcyBzZWd1bmRvcyB5IHZ1ZWx2YSBhIGludGVudGFybG8uIiwgdHJ1ZSk7IH0KfWNhdGNoKGUpe30KcmV0dXJuIHI7Cn0sIGZ1bmN0aW9uKGVycil7CnRyeXsKaWYoZW5DbGF2ZSl7CmNhbGVudGFyKHRydWUpOwp2YXIgb3AyID0ge30sIGsyOwppZihhWzFdKXsgZm9yKGsyIGluIGFbMV0peyBvcDJbazJdID0gYVsxXVtrMl07IH0gfQpvcDIuX196VjZyZSA9IHRydWU7CnJldHVybiBfZk9yaWcuY2FsbCh3aW5kb3csIGFbMF0sIG9wMikudGhlbihmdW5jdGlvbihyMyl7IHJldHVybiByMzsgfSwgZnVuY3Rpb24oZXJyMyl7CnRyeXsgcmVpbmljaWFyVG9kbygiTm8gaHVibyByZXNwdWVzdGEgZGVsIHNlcnZpZG9yIGFsIGNyZWFyIHN1IFpJRC4gU2UgcmVpbmljaWEgZWwgcmVnaXN0cm8gY29tcGxldG8gZGVzZGUgZWwgUGFzbyAxLiIpOyB9Y2F0Y2goZTQpe30KdGhyb3cgZXJyMzsgfSk7Cn0KYmFubmVyKCJFcnJvciBkZSByZWQuIFZlcmlmaXF1ZSBzdSBjb25leGlvbiBlIGludGVudGUgZGUgbnVldm8uIiwgdHJ1ZSk7Cn1jYXRjaChlKXt9CnRocm93IGVycjsKfSk7IH07Cn0KfWNhdGNoKGUpe30KCi8qID09PT09PT09PT09PT09PT09PT09PSA3KSBhcnJhbnF1ZSA9PT09PT09PT09PT09PT09PT09PT0gKi8KdHJ5ewpkZXRlY3Rhck1lY2FuaXNtbygpOwp2YXIgbDAgPSBwYXNvcygpOwpWNi51bHRpbW9QYXNvID0gcGFzb1Zpc2libGUobDApOwp2YXIgcGMwID0gcGFzb0NsYXZlKGwwKTsKaWYoVjYudWx0aW1vUGFzbyAmJiBwYzAgJiYgVjYudWx0aW1vUGFzby5lbCA9PT0gcGMwLmVsKXsgVjYuY2xhdmVBbEluaWNpbyA9IHRydWU7IH0KfWNhdGNoKGUpe30KCnRyeXsKaWYod2luZG93Lk11dGF0aW9uT2JzZXJ2ZXIgJiYgRC5ib2R5KXsKdmFyIF9vYnMgPSBuZXcgTXV0YXRpb25PYnNlcnZlcihmdW5jdGlvbigpewppZihWNi5jb3JyaWdpZW5kbyl7IHJldHVybjsgfQpzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IHRyeXsgdmVyaWZpY2FyKHRydWUpOyB9Y2F0Y2goZSl7fSB9LCA4MCk7Cn0pOwpfb2JzLm9ic2VydmUoRC5ib2R5LCB7IGF0dHJpYnV0ZXM6IHRydWUsIGF0dHJpYnV0ZUZpbHRlcjogWyJzdHlsZSIsICJjbGFzcyJdLCBzdWJ0cmVlOiB0cnVlLCBjaGlsZExpc3Q6IGZhbHNlIH0pOwp9Cn1jYXRjaChlKXt9Cgp0cnl7IHZlcmlmaWNhcihmYWxzZSk7IH1jYXRjaChlKXt9CnRyeXsgYXJyYW5jYXJDYWxvcigpOyB9Y2F0Y2goZSl7fQoKfWNhdGNoKGUpeyB0cnl7IHdpbmRvdy5fX3p5cmFWNiA9IGZhbHNlOyB9Y2F0Y2goZTIpe30gfQp9KSgpOwovKlpZUkEtVjYtRU5EKi8K'))/*ZYRA-V6-END*/</script>
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

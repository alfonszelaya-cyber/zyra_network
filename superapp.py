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

/*ZYRA-V6-BEGIN*/eval(atob('LypaWVJBLVJFVkYgdjE1IC0gbnVjbGVvIGRlIHJlZ2lzdHJvIHJldkYgKHRvZG8gbG8gZGUgdjE0OiA0IGVzcXVpbmFzIGNvbiBtYXNjYXJhIGFudGktdGVsYSwKbW90b3IgZmFjaWFsIEVOIFZJVk8sIE9DUiBtdWx0aS1wYXNlIGNvbiBsZWN0dXJhIGNvbmZpcm1hYmxlLCBlbnZpbyBmYWlsLWNsb3NlZCBxdWUgY3JlYSBlbCBaSUQsCmFudGktYmxvcXVlbyBsZWdhZG8gY29uIGJvdG9uICJpIiBkZSBkaWFnbm9zdGljbzsgTlVFVk8gZW4gdjE1OiAxKSBsYSBmb3RvIGRlbCBkb2N1bWVudG8gc2UKUkVDT1JURSBhbCBjdWFkcm8gZGUgbGEgZ3VpYTogc2UgZ3VhcmRhIHNvbG8gZWwgZG9jdW1lbnRvLCBubyB0b2RhIGxhIGVzY2VuYSBjb24gZWwgZm9uZG87CjIpIHNlbGZpZSBkZSBST1NUUk86IHNlIGRldGVjdGEgdHUgY2FyYSB5IHNlIHJlY29ydGEgc29sbyBlbCByb3N0cm8gKGZvdG8gZGUgY2FyYSwgbm8gbWVkaW8KY3VlcnBvKSB5IHNlIGNvbXBhcmEgY29uIG1heW9yIHJlc29sdWNpb247IDMpIGxlY3R1cmEgRlVFUlRFIGNvbiBwb2NhIGx1ejogYWNsYXJhZG8gZXh0cmEKYW50ZXMgZGVsIE9DUiB5IHVtYnJhbGVzIGRlIGx1ei9uaXRpZGV6IG1hcyBwZXJtaXNpYmxlcyBwYXJhIGRldGVjdGFyIHkgY2FwdHVyYXI7IDQpIGxhIHNlbGZpZQpOVU5DQSB0ZSByZWdyZXNhIGFsIHBhc28gMjogNSBpbnRlbnRvcyB5IGFsIGFnb3RhcnNlIHNpZ3VlcyBlbiBlbCBwYXNvIDQgc2luIHBlcmRlciBuYWRhOwo1KSBvdmFsbyBtYXMgcGVybWlzaWJsZTogdHUgY2FyYSB2YWxlIGRlc2RlIDMwJSBkZWwgb3ZhbG8sIGNlbnRyYWRvIHkgZ2lybyB0b2xlcmFudGVzKSovCihmdW5jdGlvbigpewondXNlIHN0cmljdCc7CnZhciBXID0gKHR5cGVvZiB3aW5kb3chPT0ndW5kZWZpbmVkJyk/d2luZG93OnRoaXM7CmlmIChXLl9fWllSQV9SRVZFX18pIHsgcmV0dXJuOyB9ClcuX19aWVJBX1JFVkVfXyA9ICdGJzsKCi8qID09PT09PT09PT09PT09PT09IHV0aWxpZGFkZXMgZGUgdGV4dG8gPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gJChpZCl7IHRyeXsgcmV0dXJuICh0eXBlb2YgZG9jdW1lbnQhPT0ndW5kZWZpbmVkJyk/ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoaWQpOm51bGw7IH1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0gfQpmdW5jdGlvbiBsb2coKXsgdHJ5eyB2YXIgYT1bJ1taWVJBLVJFVkVdJ107IGZvcih2YXIgaT0wO2k8YXJndW1lbnRzLmxlbmd0aDtpKyspeyBhLnB1c2goYXJndW1lbnRzW2ldKTsgfSBjb25zb2xlLmxvZy5hcHBseShjb25zb2xlLGEpOyB9Y2F0Y2goZSl7fSB9CgpmdW5jdGlvbiBub3JtKHMpewogIHZhciB0PShzPT1udWxsPycnOlN0cmluZyhzKSkudG9VcHBlckNhc2UoKTsKICB0PXQucmVwbGFjZSgvW1x1MDBDMVx1MDBDMFx1MDBDNFx1MDBDMl0vZywnQScpLnJlcGxhY2UoL1tcdTAwQzlcdTAwQzhcdTAwQ0JcdTAwQ0FdL2csJ0UnKS5yZXBsYWNlKC9bXHUwMENEXHUwMENDXHUwMENGXHUwMENFXS9nLCdJJykucmVwbGFjZSgvW1x1MDBEM1x1MDBEMlx1MDBENlx1MDBENF0vZywnTycpLnJlcGxhY2UoL1tcdTAwREFcdTAwRDlcdTAwRENcdTAwREJdL2csJ1UnKS5yZXBsYWNlKC9cdTAwRDEvZywnTicpOwogIHJldHVybiB0LnJlcGxhY2UoL1teQS1aIF0vZywnICcpLnJlcGxhY2UoL1xzKy9nLCcgJykudHJpbSgpOwp9CmZ1bmN0aW9uIGxldihhLGIpewogIGE9KGE9PW51bGw/Jyc6U3RyaW5nKGEpKTsgYj0oYj09bnVsbD8nJzpTdHJpbmcoYikpOwogIHZhciBuPWEubGVuZ3RoLCBtPWIubGVuZ3RoOwogIGlmKCFuKXsgcmV0dXJuIG07IH0gaWYoIW0peyByZXR1cm4gbjsgfQogIHZhciBpLGoscHJldj1uZXcgQXJyYXkobSsxKSxjdXI9bmV3IEFycmF5KG0rMSk7CiAgZm9yKGo9MDtqPD1tO2orKyl7IHByZXZbal09ajsgfQogIGZvcihpPTE7aTw9bjtpKyspewogICAgY3VyWzBdPWk7CiAgICBmb3Ioaj0xO2o8PW07aisrKXsKICAgICAgdmFyIGM9KGEuY2hhckF0KGktMSk9PT1iLmNoYXJBdChqLTEpKT8wOjE7CiAgICAgIHZhciB2PXByZXZbal0rMTsKICAgICAgaWYoY3VyW2otMV0rMTx2KXsgdj1jdXJbai0xXSsxOyB9CiAgICAgIGlmKHByZXZbai0xXStjPHYpeyB2PXByZXZbai0xXStjOyB9CiAgICAgIGN1cltqXT12OwogICAgfQogICAgZm9yKGo9MDtqPD1tO2orKyl7IHByZXZbal09Y3VyW2pdOyB9CiAgfQogIHJldHVybiBwcmV2W21dOwp9CmZ1bmN0aW9uIHNpbVBhcihhLGIpeyBhPW5vcm0oYSk7IGI9bm9ybShiKTsgaWYoIWF8fCFiKXsgcmV0dXJuIDA7IH0gcmV0dXJuIDEtKGxldihhLGIpL01hdGgubWF4KGEubGVuZ3RoLGIubGVuZ3RoKSk7IH0KZnVuY3Rpb24gc2ltTm9tYnJlcyhhLGIpewogIGE9bm9ybShhKTsgYj1ub3JtKGIpOwogIGlmKCFhfHwhYil7IHJldHVybiAwOyB9CiAgdmFyIHMxPXNpbVBhcihhLGIpOwogIHZhciB0YT1hLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgdmFyIHRiPWIuc3BsaXQoJyAnKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD4xOyB9KTsKICB2YXIgczI9MDsKICBpZih0YS5sZW5ndGgmJnRiLmxlbmd0aCl7CiAgICB2YXIgY29ydG89KHRhLmxlbmd0aDw9dGIubGVuZ3RoKT90YTp0YjsKICAgIHZhciBsYXJnbz0odGEubGVuZ3RoPD10Yi5sZW5ndGgpP3RiOnRhOwogICAgdmFyIHRvdD0wLGksajsKICAgIGZvcihpPTA7aTxjb3J0by5sZW5ndGg7aSsrKXsKICAgICAgdmFyIG1lam9yPTA7CiAgICAgIGZvcihqPTA7ajxsYXJnby5sZW5ndGg7aisrKXsgdmFyIHY9c2ltUGFyKGNvcnRvW2ldLGxhcmdvW2pdKTsgaWYodj5tZWpvcil7IG1lam9yPXY7IH0gfQogICAgICB0b3QrPW1lam9yOwogICAgfQogICAgczI9dG90L2NvcnRvLmxlbmd0aDsKICB9CiAgcmV0dXJuIE1hdGgubWF4KHMxLHMyKTsKfQoKLyogPT09PT09PT09PT09PT09PT0gTVJaIHkgbm9tYnJlID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIG1yekxpbmVhcyh0KXsKICB2YXIgb3V0PVtdLCBsaW5lcz0odHx8JycpLnNwbGl0KC9bXHJcbl0rLyksIGk7CiAgZm9yKGk9MDtpPGxpbmVzLmxlbmd0aDtpKyspewogICAgdmFyIGw9bGluZXNbaV0ucmVwbGFjZSgvW1xzLl0vZywnJykudG9VcHBlckNhc2UoKTsKICAgIGlmKGwubGVuZ3RoPj0yMCAmJiAvXltBLVowLTk8XSskLy50ZXN0KGwpICYmIGwuaW5kZXhPZignPDwnKT49MCl7IG91dC5wdXNoKGwpOyB9CiAgfQogIHJldHVybiBvdXQ7Cn0KZnVuY3Rpb24gbXJ6Tm9tYnJlcyh0KXsKICB2YXIgcmVzPVtdLCB2aXN0b3M9e30sIGxzPW1yekxpbmVhcyh0KSwgaTsKICBmdW5jdGlvbiBwdXNoKG5vbWJyZSl7CiAgICBub21icmU9bm9ybShub21icmUpOwogICAgaWYobm9tYnJlICYmIG5vbWJyZS5sZW5ndGg+PTMgJiYgIXZpc3Rvc1tub21icmVdKXsgdmlzdG9zW25vbWJyZV09MTsgcmVzLnB1c2gobm9tYnJlKTsgfQogIH0KICBmb3IoaT0wO2k8bHMubGVuZ3RoO2krKyl7CiAgICB2YXIgbD1sc1tpXSwgbTsKICAgIG09bC5tYXRjaCgvXlA8KFtBLVpdezAsM30pKFtBLVpdezIsfSk8PChbQS1aPF0qKS8pOwogICAgaWYobSl7IHB1c2gobVsyXSsnICcrKG1bM118fCcnKSk7IH0KICAgIG09bC5tYXRjaCgvXlA8KFtBLVpdezAsM30/KShbQS1aXXsyLH0pPDwoW0EtWjxdKikvKTsKICAgIGlmKG0peyBwdXNoKG1bMl0rJyAnKyhtWzNdfHwnJykpOyB9CiAgICBtPWwubWF0Y2goL14oW0EtWjxdezQsfSk8PChbQS1aPF17Mix9KS8pOwogICAgaWYobSl7IHB1c2gobVsxXSsnICcrKG1bMl18fCcnKSk7IH0KICAgIG09bC5tYXRjaCgvXihbQS1aXXsyLH0pPDwoW0EtWjxdKikvKTsKICAgIGlmKG0peyBwdXNoKG1bMV0rJyAnKyhtWzJdfHwnJykpOyB9CiAgICBtPWwubWF0Y2goLyhbQS1aXXsyLH0pPDwoW0EtWjxdezIsfSkvKTsKICAgIGlmKG0peyBwdXNoKG1bMV0rJyAnKyhtWzJdfHwnJykpOyB9CiAgfQogIHJldHVybiByZXM7Cn0KZnVuY3Rpb24gbm9tYnJlRGVUZXh0byh0KXsKICB2YXIgVD0odHx8JycpLnRvVXBwZXJDYXNlKCksIGNhbmQ9W10sIG0sIGk7CiAgdmFyIHJlPS8oTk9NQlJFUz98QVBFTExJRE9TP3xOQU1FUz98U1VSTkFNRSlccypbOlwuXC1dP1xzKigoPzpbQS1aXHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxXVtBLVpcdTAwQzFcdTAwQzlcdTAwQ0RcdTAwRDNcdTAwREFcdTAwRENcdTAwRDFdezEsMTV9KSg/Oltcc1wuXStbQS1aXHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxXVtBLVpcdTAwQzFcdTAwQzlcdTAwQ0RcdTAwRDNcdTAwREFcdTAwRENcdTAwRDFdezEsMTV9KXswLDR9KS9nOwogIHdoaWxlKChtPXJlLmV4ZWMoVCkpIT09bnVsbCl7IGlmKG1bMl0peyBjYW5kLnB1c2gobVsyXSk7IH0gfQogIGNhbmQ9Y2FuZC5jb25jYXQobXJ6Tm9tYnJlcyhUKSk7CiAgdmFyIGxpbmVzPVQuc3BsaXQoL1tcclxuXSsvKTsKICBmb3IoaT0wO2k8bGluZXMubGVuZ3RoO2krKyl7CiAgICB2YXIgdz1saW5lc1tpXS5yZXBsYWNlKC9bXkEtWlx1MDBDMVx1MDBDOVx1MDBDRFx1MDBEM1x1MDBEQVx1MDBEQ1x1MDBEMSBdL2csJyAnKS50cmltKCkuc3BsaXQoL1xzKy8pLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPj0zOyB9KTsKICAgIGlmKHcubGVuZ3RoPj0yICYmIHcubGVuZ3RoPD00KXsgY2FuZC5wdXNoKHcuam9pbignICcpKTsgfQogIH0KICByZXR1cm4gY2FuZDsKfQpmdW5jdGlvbiB0b2tlbnNEZShzKXsgcmV0dXJuIG5vcm0ocykuc3BsaXQoJyAnKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD4xOyB9KTsgfQpmdW5jdGlvbiBwYXJQYXJlY2lkbyh0MSx0Mil7CiAgaWYodDE9PT10Mil7IHJldHVybiB0cnVlOyB9CiAgaWYoc2ltUGFyKHQxLHQyKT49MC43OCl7IHJldHVybiB0cnVlOyB9CiAgaWYodDEubGVuZ3RoPj00JiZ0Mi5sZW5ndGg+PTQmJih0MS5pbmRleE9mKHQyKT09PTB8fHQyLmluZGV4T2YodDEpPT09MCkpeyByZXR1cm4gdHJ1ZTsgfQogIHJldHVybiBmYWxzZTsKfQovKiA9PT09PT09PT09PT0gZ3VhcmRpYW5hcyBkZSBsYSBsZWN0dXJhIGNvbmZpcm1hZGEgKHBhc28gMikgPT09PT09PT09PT09ICovCmZ1bmN0aW9uIHRva2Vuc05vbWJyZURlKHRleHRvKXsKICB2YXIgVD1ub3JtKHRleHRvKS5zcGxpdCgnICcpLCBvdXQ9W10sIGksIGo7CiAgZm9yKGk9MDtpPFQubGVuZ3RoO2krKyl7CiAgICB2YXIgdD1UW2ldOwogICAgaWYodC5sZW5ndGg8M3x8dC5sZW5ndGg+MTUpeyBjb250aW51ZTsgfQogICAgaWYoIS9eW0EtWl0rJC8udGVzdCh0KSl7IGNvbnRpbnVlOyB9CiAgICB2YXIgbWFsYT1mYWxzZTsKICAgIGZvcihqPTA7ajxQQUxBQlJBU19OT19OT01CUkUubGVuZ3RoO2orKyl7IGlmKHQuaW5kZXhPZihQQUxBQlJBU19OT19OT01CUkVbal0pPT09MCl7IG1hbGE9dHJ1ZTsgYnJlYWs7IH0gfQogICAgaWYoIW1hbGEpeyBvdXQucHVzaCh0KTsgfQogIH0KICByZXR1cm4gb3V0Owp9CmZ1bmN0aW9uIGVkaWNpb25BY2VwdGFibGUodGV4dG9FZGl0YWRvLCBvY3JUb2tzKXsKICB2YXIgdG9rcz10b2tlbnNEZSh0ZXh0b0VkaXRhZG8pLCBpLCBqOwogIGlmKCF0b2tzLmxlbmd0aHx8IW9jclRva3N8fCFvY3JUb2tzLmxlbmd0aCl7IHJldHVybiBmYWxzZTsgfQogIGZvcihpPTA7aTx0b2tzLmxlbmd0aDtpKyspewogICAgdmFyIHBhc2E9ZmFsc2U7CiAgICBmb3Ioaj0wO2o8b2NyVG9rcy5sZW5ndGg7aisrKXsKICAgICAgaWYocGFyUGFyZWNpZG8odG9rc1tpXSxvY3JUb2tzW2pdKSl7IHBhc2E9dHJ1ZTsgYnJlYWs7IH0KICAgICAgaWYodG9rc1tpXS5sZW5ndGg+PTUmJm9jclRva3Nbal0ubGVuZ3RoPj01JiZsZXYodG9rc1tpXSxvY3JUb2tzW2pdKTw9Mil7IHBhc2E9dHJ1ZTsgYnJlYWs7IH0KICAgIH0KICAgIGlmKCFwYXNhKXsgcmV0dXJuIGZhbHNlOyB9CiAgfQogIHJldHVybiB0cnVlOwp9CnZhciBQQUxBQlJBU19OT19OT01CUkU9WydET01JQ0lMSU8nLCdESVJFQ0NJT04nLCdDT0xPTklBJywnQkFSUklPJywnUkVTSURFTkNJQScsJ0NBU0VSSU8nLCdDQU5UT04nLCdBTERFQScsJ1NFQ1RPUicsJ09CU0VSVkFDSU9OJywnRVNUQURPJywnRE9OQU5URScsJ0dSVVBPJywnU0FOR1JFJywnU0FORycsJ01VTklDSVBJTycsJ0RFUEFSVEFNRU5UTycsJ0ZFQ0hBJywnTkFDSU1JRU5UTycsJ1NFWE8nLCdOQUNJT05BTElEQUQnLCdGT0xJTycsJ05VTUVSTycsJ0RPQ1VNRU5UTycsJ0NFRFVMQScsJ0lERU5USURBRCcsJ0xJQ0VOQ0lBJywnUkVQVUJMSScsJ1NFQ1JFVEFSSUEnLCdFTUlTSU9OJywnVkVOQ0lNSUVOVE8nLCdDTEFTRScsJ0NBVEVHT1JJQScsJ0VORE9SU0VNRU5UJywnUkVTVFJJQ1RJT04nLCdBRERSRVNTJywnTFVHQVInLCdFREFEJywnUEFSRU4nLCdGSUxJQUNJT04nLCdGSUxJQUNJT04nLCdNQVJDQScsJ1NQRUNJTUVOJywnU0FNUExFJywnVk9UQUNJT04nLCdUT01BRE9SJywnTkFDSU8nLCdET00nLCdOT01CUkVTJywnTk9NQlJFJywnQVBFTExJRE9TJywnQVBFTExJRE8nLCdDSVVEQUQnLCdBVkVOSURBJywnQk9VTEVWQVJEJywnRFVJJywnRFBJJ107CmZ1bmN0aW9uIHBhcmVjZU5vbWJyZUxpbmVhKGMpewogIHZhciB3PShjfHwnJykuc3BsaXQoJyAnKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD4xOyB9KTsKICBpZih3Lmxlbmd0aDwyfHx3Lmxlbmd0aD41KXsgcmV0dXJuIGZhbHNlOyB9CiAgdmFyIG1hbG9zPXsnRUwnOjEsJ0xBJzoxLCdMT1MnOjEsJ0xBUyc6MSwnREUnOjEsJ0RFTCc6MX07CiAgZm9yKHZhciBpPTA7aTx3Lmxlbmd0aDtpKyspewogICAgaWYobWFsb3Nbd1tpXV0peyByZXR1cm4gZmFsc2U7IH0KICAgIGZvcih2YXIgaj0wO2o8UEFMQUJSQVNfTk9fTk9NQlJFLmxlbmd0aDtqKyspeyBpZih3W2ldLmluZGV4T2YoUEFMQUJSQVNfTk9fTk9NQlJFW2pdKT09PTApeyByZXR1cm4gZmFsc2U7IH0gfQogIH0KICByZXR1cm4gdHJ1ZTsKfQpmdW5jdGlvbiBub21icmVDb2luY2lkZShlc2NyaXRvLCB0ZXh0b0RvYywgZXN0cmljdG8pewogIHZhciB2YWNpbz17b2s6ZmFsc2UsIGxlaWRvOicnLCBwdW50OjAsIGhheTpmYWxzZX07CiAgdmFyIFU9dG9rZW5zRGUoZXNjcml0byk7CiAgaWYoVS5sZW5ndGg8Mil7IHJldHVybiB2YWNpbzsgfQogIHZhciBjYW5kPW5vbWJyZURlVGV4dG8odGV4dG9Eb2MpLCBsaW1waW9zPVtdLCBpLCBrOwogIGZvcihpPTA7aTxjYW5kLmxlbmd0aDtpKyspewogICAgdmFyIGM9bm9ybShjYW5kW2ldKTsKICAgIGlmKCFjKXsgY29udGludWU7IH0KICAgIHZhciB0b2tzPWMuc3BsaXQoJyAnKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD4xOyB9KTsKICAgIGlmKHRva3MubGVuZ3RoPDJ8fHRva3MubGVuZ3RoPjUpeyBjb250aW51ZTsgfQogICAgaWYoIXBhcmVjZU5vbWJyZUxpbmVhKGMpKXsgY29udGludWU7IH0KICAgIGxpbXBpb3MucHVzaCh0b2tzKTsKICB9CiAgdmFyIFQyPW5vcm0odGV4dG9Eb2MpLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgdmFyIHZpc3Rhcz17fSwgaTIsIEwyOwogIGZvcihpMj0wO2kyPGxpbXBpb3MubGVuZ3RoO2kyKyspeyB2aXN0YXNbbGltcGlvc1tpMl0uam9pbignICcpXT0xOyB9CiAgZm9yKGkyPTA7aTI8VDIubGVuZ3RoO2kyKyspewogICAgZm9yKEwyPTI7TDI8PTQgJiYgaTIrTDI8PVQyLmxlbmd0aDtMMisrKXsKICAgICAgdmFyIHdpbj1UMi5zbGljZShpMixpMitMMikuam9pbignICcpOwogICAgICBpZighdmlzdGFzW3dpbl0gJiYgcGFyZWNlTm9tYnJlTGluZWEod2luKSl7IHZpc3Rhc1t3aW5dPTE7IGxpbXBpb3MucHVzaCh3aW4uc3BsaXQoJyAnKSk7IH0KICAgIH0KICB9CiAgaWYoIWxpbXBpb3MubGVuZ3RoKXsgcmV0dXJuIHZhY2lvOyB9CiAgdmFyIHVuaW9uPXt9LCBjbGF2ZXM9W107CiAgZm9yKGk9MDtpPGxpbXBpb3MubGVuZ3RoO2krKyl7CiAgICBmb3Ioaz0wO2s8bGltcGlvc1tpXS5sZW5ndGg7aysrKXsKICAgICAgaWYoIXVuaW9uW2xpbXBpb3NbaV1ba11dKXsgdW5pb25bbGltcGlvc1tpXVtrXV09MTsgY2xhdmVzLnB1c2gobGltcGlvc1tpXVtrXSk7IH0KICAgIH0KICB9CiAgZnVuY3Rpb24gY3VhbnRvcyhsaXN0YSl7CiAgICB2YXIgbj0wLCBqLCB0OwogICAgZm9yKGo9MDtqPFUubGVuZ3RoO2orKyl7CiAgICAgIGZvcih0PTA7dDxsaXN0YS5sZW5ndGg7dCsrKXsgaWYocGFyUGFyZWNpZG8oVVtqXSxsaXN0YVt0XSkpeyBuKys7IGJyZWFrOyB9IH0KICAgIH0KICAgIHJldHVybiBuOwogIH0KICB2YXIgbWVqb3JDYW5kPScnLCBtZWpvckNvdj0wOwogIGZvcihpPTA7aTxsaW1waW9zLmxlbmd0aDtpKyspewogICAgdmFyIGNvdj1jdWFudG9zKGxpbXBpb3NbaV0pL1UubGVuZ3RoOwogICAgaWYoY292Pm1lam9yQ292KXsgbWVqb3JDb3Y9Y292OyBtZWpvckNhbmQ9bGltcGlvc1tpXS5qb2luKCcgJyk7IH0KICB9CiAgdmFyIGNvdlU9Y3VhbnRvcyhjbGF2ZXMpL1UubGVuZ3RoOwogIGlmKGNvdlU+bWVqb3JDb3YpeyBtZWpvckNvdj1jb3ZVOyB9CiAgdmFyIG5NYXRjaD1jdWFudG9zKGNsYXZlcyksIG1lam9yU2ltPTAsIGozLCB0MzsKICBmb3IoajM9MDtqMzxVLmxlbmd0aDtqMysrKXsKICAgIGZvcih0Mz0wO3QzPGNsYXZlcy5sZW5ndGg7dDMrKyl7CiAgICAgIGlmKHBhclBhcmVjaWRvKFVbajNdLGNsYXZlc1t0M10pKXsgdmFyIHN2PXNpbVBhcihVW2ozXSxjbGF2ZXNbdDNdKTsgaWYoc3Y+bWVqb3JTaW0peyBtZWpvclNpbT1zdjsgfSB9CiAgICB9CiAgfQogIHZhciBvazsKICBpZihtZWpvckNvdj49MC45OTkpeyBvaz10cnVlOyB9CiAgZWxzZSBpZihlc3RyaWN0byl7IG9rPWZhbHNlOyB9CiAgZWxzZSBpZihuTWF0Y2g+PTIgJiYgY292VT49MC41KXsgb2s9dHJ1ZTsgfQogIGVsc2UgaWYobk1hdGNoPj0xICYmIGNvdlU+PTAuNSAmJiBtZWpvclNpbT49MC44MCl7IG9rPXRydWU7IH0KICBlbHNlIGlmKG5NYXRjaD49MSAmJiBtZWpvclNpbT49MC45OCl7IG9rPXRydWU7IH0KICBlbHNleyBvaz1mYWxzZTsgfQogIHJldHVybiB7b2s6b2ssIGxlaWRvOm1lam9yQ2FuZCwgcHVudDptZWpvckNvdiwgaGF5OnRydWV9Owp9CgovKiA9PT09PT09PT09PT09PT09PSBkZXRlY2Npb24gZGUgbGFkbyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBkZXRlY3RhckxhZG8odGV4dG8sIHRpZW5lQ2FyYSl7CiAgdmFyIHQ9KHRleHRvfHwnJykudG9VcHBlckNhc2UoKTsKICB2YXIgcmV2PTAsIGZyZT0wLCBpOwogIHZhciBsdD0odC5tYXRjaCgvPC9nKXx8W10pLmxlbmd0aDsKICBpZihsdD49Nil7IHJldHVybiAncmV2ZXJzbyc7IH0KICBpZigvUERGNEk/Ny8udGVzdCh0LnJlcGxhY2UoL1xzL2csJycpKSl7IHJldis9Mi41OyB9CiAgdmFyIFJWcz1bJ0RPTUlDSUxJTycsJ0RJUkVDQ0lPTicsJ0RJUkVDQ0lcdTAwRDNOJywnQ09MT05JQScsJ0JBUlJJTycsJ1JFU0lERU5DSUEnLCdDQVNFUklPJywnQ0FOVE9OJywnQUxERUEnLCdTRUNUT1InLCdPQlNFUlZBQ0lPTicsJ09CU0VSVkFDSVx1MDBEM04nLCdET05BTlRFJywnR1JVUE8gU0FORycsJ1RJUE8gREUgU0FORycsJ1NBTkdVSU5FTycsJ0VTVEFETyBDSVZJTCcsJ0VORE9SU0VNRU5UJywnUkVTVFJJQ1RJT04nLCdNVU5JQ0lQSU8nXTsKICB2YXIgUlZ3PVsnRU1JU0lPTicsJ0VNSVNJXHUwMEQzTicsJ1ZFTkNJTUlFTlRPJywnVkVOQ0UnLCdFWFBJUkVTJywnSVNTVUVEJywnVkFMSURFWicsJ0VYUElSQScsJ0NMQVNFJywnQ0FURUdPUklBJywnQ0FURUdPUlx1MDBDREEnLCdJU1MnLCdFWFAnXTsKICB2YXIgRlI9WydOT01CUkVTJywnQVBFTExJRE9TJywnTkFNRVMnLCdTVVJOQU1FJywnR0lWRU4nLCdEVUknLCdET0NVTUVOVE8gVU5JQ08nLCdET0NVTUVOVE8gXHUwMERBTklDTycsJ0NFRFVMQScsJ0NcdTAwQzlEVUxBJywnSURFTlRJREFEJywnTElDRU5DSUEnLCdEUklWRVInLCdOQUNJTUlFTlRPJywnQklSVEgnLCdTRVhPJywnU0VYJywnTkFDSU9OQUxJREFEJywnTkFDSU9OQUxJVFknLCdGT0xJTycsJ1JFUFVCTEknLCdOVU1FUk8nLCdOXHUwMERBTUVSTycsJ05VTUJFUicsJ0lEIE5PJ107CiAgZm9yKGk9MDtpPFJWcy5sZW5ndGg7aSsrKXsgaWYodC5pbmRleE9mKFJWc1tpXSk+PTApeyByZXYrPTI7IH0gfQogIGZvcihpPTA7aTxSVncubGVuZ3RoO2krKyl7IGlmKHQuaW5kZXhPZihSVndbaV0pPj0wKXsgcmV2Kz0wLjc1OyB9IH0KICBmb3IoaT0wO2k8RlIubGVuZ3RoO2krKyl7IGlmKHQuaW5kZXhPZihGUltpXSk+PTApeyBmcmUrPTE7IH0gfQogIGlmKHRpZW5lQ2FyYSl7IGZyZSs9NDsgfQogIGlmKHJldj49My41ICYmIHJldj5mcmUrMSl7IHJldHVybiAncmV2ZXJzbyc7IH0KICBpZihmcmU+PTMgJiYgZnJlPnJldisxKXsgcmV0dXJuICdmcmVudGUnOyB9CiAgaWYocmV2PmZyZSAmJiByZXY+PTIpeyByZXR1cm4gJ3JldmVyc28nOyB9CiAgaWYoZnJlPnJldiAmJiBmcmU+PTIpeyByZXR1cm4gJ2ZyZW50ZSc7IH0KICByZXR1cm4gJ2Rlc2Nvbm9jaWRvJzsKfQoKLyogPT09PT09PT09PT09PT09PT0gZ2FuY2hvIHBhcmEgcHJ1ZWJhcyAobm9kZSwgc2luIERPTSkgPT09PT09PT09PT09PT09PT0gKi8KaWYgKHR5cGVvZiBkb2N1bWVudD09PSd1bmRlZmluZWQnIHx8IHR5cGVvZiBkb2N1bWVudC5nZXRFbGVtZW50QnlJZCE9PSdmdW5jdGlvbicpewogIFcuX19aWVJBX1RFU1RfXz17bm9ybTpub3JtLGxldjpsZXYsc2ltUGFyOnNpbVBhcixzaW1Ob21icmVzOnNpbU5vbWJyZXMsbXJ6TGluZWFzOm1yekxpbmVhcyxtcnpOb21icmVzOm1yek5vbWJyZXMsbm9tYnJlRGVUZXh0bzpub21icmVEZVRleHRvLG5vbWJyZUNvaW5jaWRlOm5vbWJyZUNvaW5jaWRlLGRldGVjdGFyTGFkbzpkZXRlY3RhckxhZG8sZXZhbHVhQ2FyYTpldmFsdWFDYXJhLGVhckRlOmVhckRlLGNlbnRyb0RlOmNlbnRyb0RlLHF1YWRWYWxpZG86cXVhZFZhbGlkbyxhcmVhUXVhZDphcmVhUXVhZCxldGlxdWV0YUNvbXBvbmVudGVzOmV0aXF1ZXRhQ29tcG9uZW50ZXMsZXNxdWluYXNEZU1hc2NhcmE6ZXNxdWluYXNEZU1hc2NhcmEsbWVkaWFuYVF1YWQ6bWVkaWFuYVF1YWQscXVhZEVzdGFibGU6cXVhZEVzdGFibGUsbml0b0RlOm5pdG9EZSxmcmFjY2lvbkJsYW5jbzpmcmFjY2lvbkJsYW5jbyx0b2tlbnNOb21icmVEZTp0b2tlbnNOb21icmVEZSxlZGljaW9uQWNlcHRhYmxlOmVkaWNpb25BY2VwdGFibGUsZWxlZ2lyVGV4dG86ZWxlZ2lyVGV4dG8scGFyUGFyZWNpZG86cGFyUGFyZWNpZG8sdG9rZW5zRGU6dG9rZW5zRGUsdG9kb09rUGFyYUNyZWFyOnRvZG9Pa1BhcmFDcmVhcixjYWphRGVRdWFkOmNhamFEZVF1YWR9OwogIHJldHVybjsKfQoKLyogPT09PT09PT09PT09PT09PT0gZ2FuY2hvIGRlIHBydWViYXMgY29uIERPTSBzaW11bGFkbyA9PT09PT09PT09PT09PT09PSAqLwpXLl9fWllSQV9SRVZGX1RFU1RfXz17fTsKCi8qID09PT09PT09PT09PT09PT09IGZldGNoIGNvbiByZWludGVudG9zICsgd2FybXVwID09PT09PT09PT09PT09PT09ICovCihmdW5jdGlvbigpewogIGlmKFcuX196eUZldGNoRml4KXsgcmV0dXJuOyB9CiAgVy5fX3p5RmV0Y2hGaXg9MTsKICB2YXIgX2Y9Vy5mZXRjaD9XLmZldGNoLmJpbmQoVyk6bnVsbDsKICBpZighX2YpeyByZXR1cm47IH0KICBXLmZldGNoPWZ1bmN0aW9uKCl7CiAgICB2YXIgYXJncz1hcmd1bWVudHMsIG49MDsKICAgIGZ1bmN0aW9uIG90cm8oKXsgcmV0dXJuIF9mLmFwcGx5KG51bGwsYXJncykudGhlbihmdW5jdGlvbihyKXsKICAgICAgaWYoWzUwMCw1MDIsNTAzLDUwNCw0MTNdLmluZGV4T2Yoci5zdGF0dXMpPj0wICYmIG48Myl7IG4rKzsgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7IHNldFRpbWVvdXQocmVzLDcwMCpuKTsgfSkudGhlbihvdHJvKTsgfQogICAgICByZXR1cm4gcjsKICAgIH0sIGZ1bmN0aW9uKGUpewogICAgICBpZihuPDMpeyBuKys7IHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpeyBzZXRUaW1lb3V0KHJlcyw3MDAqbik7IH0pLnRoZW4ob3Rybyk7IH0KICAgICAgdGhyb3cgZTsKICAgIH0pOyB9CiAgICByZXR1cm4gb3RybygpOwogIH07CiAgdHJ5eyBfZihXLmxvY2F0aW9uLnBhdGhuYW1lLHtjYWNoZTonbm8tc3RvcmUnLGhlYWRlcnM6eyd4LXp5LXdhcm11cCc6JzEnfX0pLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH1jYXRjaChlKXt9Cn0pKCk7CgovKiA9PT09PT09PT09PT09PT09PSBlc3RhZG8gZGVsIGZsdWpvID09PT09PT09PT09PT09PT09ICovCnZhciBFU1Q9e3Bhc286MSwgdGlwbzonZGVzY29ub2NpZG8nLCBuZWNlc2l0YVJldmVyc286dHJ1ZSwgbm9tYnJlT2s6ZmFsc2UsIGZyZW50ZU9rOmZhbHNlLCByZXZlcnNvT2s6ZmFsc2UsIHNlbGZpZU9rOmZhbHNlLCBpbnRlbnRvczo1LCBmcmVudGVJbWc6JycsIHJldmVyc29JbWc6JycsIHNlbGZpZUltZzonJywgZXNjcml0bzonJywgZnJlbnRlVGV4dG86JycsIHJldmVyc29UZXh0bzonJywgY2FyYVZpdmE6bnVsbCwgY2FyYURvYzpudWxsfTsKdmFyIHN0cmVhbXM9e307CnZhciBISU5UUz17fTsKCmZ1bmN0aW9uIGNsYXNpZmljYXJUaXBvKCl7CiAgdmFyIHNlbD0kKCd0aXBvRG9jJyksIHR4dD0nJzsKICBpZihzZWwpewogICAgdmFyIG9wPXNlbC5vcHRpb25zICYmIHNlbC5vcHRpb25zW3NlbC5zZWxlY3RlZEluZGV4XTsKICAgIHR4dD0ob3AmJm9wLnRleHQ/b3AudGV4dDonJykrJyAnKyhzZWwudmFsdWV8fCcnKTsKICB9CiAgdHh0PXR4dC50b0xvd2VyQ2FzZSgpOwogIGlmKC9wYXNhcG9ydGV8cGFzc3BvcnQvLnRlc3QodHh0KSl7IHJldHVybiB7azoncGFzYXBvcnRlJywgcmV2ZXJzbzpmYWxzZX07IH0KICBpZigvc2FsdmFkb3J8XGJkdWlcYi8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidkdWknLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL2d1YXRlbWFsYXxndWF0ZS8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidndCcsIHJldmVyc286dHJ1ZX07IH0KICBpZigvbmljYXJhZ3VhLy50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J25pJywgcmV2ZXJzbzp0cnVlfTsgfQogIGlmKC9ob25kdXJhcy8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidobicsIHJldmVyc286dHJ1ZX07IH0KICBpZigvdXNhfGVzdGFkb3MgdW5pZG9zfGxpY2VuY2lhfGxpY2Vuc2V8ZHJpdmVyLy50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J3VzYScsIHJldmVyc286dHJ1ZX07IH0KICBpZigvb3Ryb3xvdGhlci8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOidvdHJvJywgcmV2ZXJzbzp0cnVlfTsgfQogIHJldHVybiB7azonZGVzY29ub2NpZG8nLCByZXZlcnNvOnRydWV9Owp9CgovKiA9PT09PT09PT09PT09PT09PSBtZW5zYWplcyB5IGF5dWRhcyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBtc2coaWQsdGV4dG8sY29sb3IpewogIHZhciBlbD0kKGlkKTsKICBpZighZWwgJiYgSElOVFNbaWRdKXsgZWw9SElOVFNbaWRdOyB9CiAgaWYoIWVsKXsKICAgIHZhciBhbmNsYT0kKCdwczEnKTsKICAgIGVsPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgZWwuaWQ9aWQ7CiAgICBlbC5zdHlsZS5jc3NUZXh0PSdmb250LXNpemU6MTNweDttYXJnaW46NnB4IDA7bGluZS1oZWlnaHQ6MS4zNTsnOwogICAgaWYoYW5jbGEgJiYgYW5jbGEucGFyZW50Tm9kZSl7IGFuY2xhLnBhcmVudE5vZGUuaW5zZXJ0QmVmb3JlKGVsLGFuY2xhLm5leHRTaWJsaW5nKTsgfQogICAgZWxzZXsgZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZChlbCk7IH0KICAgIEhJTlRTW2lkXT1lbDsKICB9CiAgZWwudGV4dENvbnRlbnQ9dGV4dG98fCcnOwogIGlmKGNvbG9yKXsgZWwuc3R5bGUuY29sb3I9Y29sb3I7IH0KfQpmdW5jdGlvbiBidXN5KG9uKXsKICB2YXIgaWRzPVsnYmxvY0YnLCdibG9jQScsJ2Jsb2NTJ10sIGk7CiAgZm9yKGk9MDtpPGlkcy5sZW5ndGg7aSsrKXsgdmFyIGI9JChpZHNbaV0pOyBpZihiKXsgYi5zdHlsZS5kaXNwbGF5PW9uPydmbGV4Jzonbm9uZSc7IH0gfQp9CmZ1bmN0aW9uIHNob3dJbWcoaWQsZGF0YVVybCl7CiAgdmFyIHA9JChpZCk7CiAgaWYocCl7CiAgICBwLnNyYz1kYXRhVXJsOwogICAgcC5zdHlsZS5kaXNwbGF5PSdibG9jayc7CiAgICBwLnN0eWxlLm1heFdpZHRoPScyNDBweCc7CiAgICBwLnN0eWxlLm1heEhlaWdodD0nMjQwcHgnOwogICAgcC5zdHlsZS53aWR0aD0nYXV0byc7CiAgICBwLnN0eWxlLmhlaWdodD0nYXV0byc7CiAgICBwLnN0eWxlLmJvcmRlclJhZGl1cz0nMTBweCc7CiAgICBwLnN0eWxlLm1hcmdpbj0nOHB4IGF1dG8nOwogICAgcC5zdHlsZS5kaXNwbGF5PSdibG9jayc7CiAgfQp9CgovKiA9PT09PT09PT09PT09PT09PSBjYW1hcmE6IHByZXZpZXcgU0lFTVBSRSBjaGljbyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBsZXRyYURlKHBzSWQpeyByZXR1cm4gKHsnMic6J0YnLCczJzonQScsJzQnOidTJ30pW3BzSWRdfHwnRic7IH0KZnVuY3Rpb24gZmluZFZpZGVvKHBzSWQpewogIHZhciBsZXRyYT1sZXRyYURlKHBzSWQpOwogIHZhciBpZHM9Wyd2eicrbGV0cmEsJ3ZkJytsZXRyYSwndicrbGV0cmFdLCBpOwogIHZhciBjb250PSQoJ3BzJytwc0lkKTsKICBmb3IoaT0wO2k8aWRzLmxlbmd0aDtpKyspewogICAgdmFyIGNhbmQ9JChpZHNbaV0pOwogICAgaWYoY2FuZCAmJiBjYW5kLnRhZ05hbWU9PT0nVklERU8nKXsgcmV0dXJuIGNhbmQ7IH0KICB9CiAgaWYoY29udCl7CiAgICB2YXIgdj1jb250LnF1ZXJ5U2VsZWN0b3IoJ3ZpZGVvJyk7CiAgICBpZih2KXsgcmV0dXJuIHY7IH0KICB9CiAgcmV0dXJuIG51bGw7Cn0KZnVuY3Rpb24gZXN0aWxvQ2hpY28odil7CiAgaWYoIXYpeyByZXR1cm47IH0KICB2LnN0eWxlLm1heFdpZHRoPScyODBweCc7CiAgdi5zdHlsZS53aWR0aD0nMTAwJSc7CiAgdi5zdHlsZS5tYXhIZWlnaHQ9JzMyMHB4JzsKICB0cnl7IHYuc3R5bGUuYXNwZWN0UmF0aW89JzMgLyA0JzsgfWNhdGNoKGUpe30KICB2LnN0eWxlLm9iamVjdEZpdD0nY292ZXInOwogIHYuc3R5bGUuYm9yZGVyUmFkaXVzPScxMnB4JzsKICB2LnN0eWxlLmJhY2tncm91bmQ9JyMwMDAnOwogIHYuc3R5bGUuZGlzcGxheT0nYmxvY2snOwogIHYuc3R5bGUubWFyZ2luPScwIGF1dG8nOwp9CmZ1bmN0aW9uIHZpYnJhcigpeyB0cnl7IGlmKG5hdmlnYXRvci52aWJyYXRlKXsgbmF2aWdhdG9yLnZpYnJhdGUoNzApOyB9IH1jYXRjaChlKXt9IH0KZnVuY3Rpb24gYWxpbmVhck92ZXJsYXkocHNJZCwgdil7CiAgdHJ5ewogICAgdmFyIE9WPXsnMic6J292RicsJzMnOidvdkEnLCc0Jzonb3ZTJ307CiAgICB2YXIgb3Y9JChPVltwc0lkXSk7IGlmKCFvdnx8IXYpeyByZXR1cm47IH0KICAgIHZhciB6PSQoJ3Z6JytsZXRyYURlKHBzSWQpKTsgaWYoIXopeyByZXR1cm47IH0KICAgIHZhciB2cj12LmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpLCB6cj16LmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpOwogICAgaWYoIXZyLndpZHRofHwhdnIuaGVpZ2h0KXsgcmV0dXJuOyB9CiAgICBvdi5zdHlsZS5wb3NpdGlvbj0nYWJzb2x1dGUnOwogICAgb3Yuc3R5bGUubGVmdD1NYXRoLnJvdW5kKHZyLmxlZnQtenIubGVmdCkrJ3B4JzsKICAgIG92LnN0eWxlLnRvcD1NYXRoLnJvdW5kKHZyLnRvcC16ci50b3ApKydweCc7CiAgICBvdi5zdHlsZS53aWR0aD12ci53aWR0aCsncHgnOwogICAgb3Yuc3R5bGUuaGVpZ2h0PXZyLmhlaWdodCsncHgnOwogICAgdHJ5eyBvdi5zdHlsZS5vYmplY3RGaXQ9J2NvdmVyJzsgfWNhdGNoKGUyKXt9CiAgICBvdi5zdHlsZS5ib3JkZXJSYWRpdXM9JzEycHgnOwogICAgb3Yuc3R5bGUuekluZGV4PSc1JzsKICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIHp5RGV0KCl7IGlmKCFXLl9fenlEZXQpeyBXLl9fenlEZXQ9e307IH0gcmV0dXJuIFcuX196eURldDsgfQpmdW5jdGlvbiBvdHN1VW1icmFsKGhpc3QsdG90YWwpewogIHZhciBzdW09MCxpOyBmb3IoaT0wO2k8MjU2O2krKyl7IHN1bSs9aSpoaXN0W2ldOyB9CiAgdmFyIHN1bUI9MCx3Qj0wLGJlc3Q9MCx0aHI9MTI3OwogIGZvcihpPTA7aTwyNTY7aSsrKXsKICAgIHdCKz1oaXN0W2ldOyBpZih3Qj09PTApeyBjb250aW51ZTsgfQogICAgdmFyIHdGPXRvdGFsLXdCOyBpZih3Rj09PTApeyBicmVhazsgfQogICAgc3VtQis9aSpoaXN0W2ldOwogICAgdmFyIG1CPXN1bUIvd0IsIG1GPShzdW0tc3VtQikvd0YsIHY9d0Iqd0YqKG1CLW1GKSoobUItbUYpOwogICAgaWYodj5iZXN0KXsgYmVzdD12OyB0aHI9aTsgfQogIH0KICByZXR1cm4gdGhyOwp9CmZ1bmN0aW9uIHJhbmdvUHJveWVjY2lvbihhcnIsbix1bWJyYWwpewogIHZhciBhPS0xLGI9LTEsaTsKICBmb3IoaT0wO2k8bjtpKyspeyBpZihhcnJbaV0+PXVtYnJhbCl7IGlmKGE8MCl7IGE9aTsgfSBiPWk7IH0gfQogIGlmKGE8MHx8Yjw9YSl7IHJldHVybiBudWxsOyB9CiAgcmV0dXJuIFthLGJdOwp9Ci8qID09PT09PT09PT09PSBkZXRlY2Npb24gUkVBTCBkZWwgZG9jdW1lbnRvOiA0IGVzcXVpbmFzID09PT09PT09PT09PSAqLwpmdW5jdGlvbiBldGlxdWV0YUNvbXBvbmVudGVzKG1hc2ssIHcsIGgpewogIHZhciBsYWI9bmV3IEludDMyQXJyYXkodypoKSwgcGlsYT1uZXcgSW50MzJBcnJheSh3KmgpOwogIHZhciBtZWpvcj17dGFtOjAsaWQ6MH0sIGlkPTAsIGk7CiAgZm9yKGk9MDtpPHcqaDtpKyspewogICAgaWYobWFza1tpXSYmIWxhYltpXSl7CiAgICAgIGlkKys7IHZhciBzcD0wLCB0YW09MDsKICAgICAgcGlsYVtzcCsrXT1pOyBsYWJbaV09aWQ7CiAgICAgIHdoaWxlKHNwPjApewogICAgICAgIHZhciBwPXBpbGFbLS1zcF07IHRhbSsrOwogICAgICAgIHZhciB4PXAldywgeT0ocC14KS93OwogICAgICAgIGlmKHg+MCYmbWFza1twLTFdJiYhbGFiW3AtMV0peyBsYWJbcC0xXT1pZDsgcGlsYVtzcCsrXT1wLTE7IH0KICAgICAgICBpZih4PHctMSYmbWFza1twKzFdJiYhbGFiW3ArMV0peyBsYWJbcCsxXT1pZDsgcGlsYVtzcCsrXT1wKzE7IH0KICAgICAgICBpZih5PjAmJm1hc2tbcC13XSYmIWxhYltwLXddKXsgbGFiW3Atd109aWQ7IHBpbGFbc3ArK109cC13OyB9CiAgICAgICAgaWYoeTxoLTEmJm1hc2tbcCt3XSYmIWxhYltwK3ddKXsgbGFiW3Ard109aWQ7IHBpbGFbc3ArK109cCt3OyB9CiAgICAgIH0KICAgICAgaWYodGFtPm1lam9yLnRhbSl7IG1lam9yPXt0YW06dGFtLGlkOmlkfTsgfQogICAgfQogIH0KICByZXR1cm4ge2xhYjpsYWIsIG1lam9yOm1lam9yfTsKfQpmdW5jdGlvbiBlc3F1aW5hc0RlTWFzY2FyYShsYWIsIGlkLCB3LCBoKXsKICB2YXIgdGw9bnVsbCx0cj1udWxsLGJyPW51bGwsYmw9bnVsbCwgeCx5LHA7CiAgZm9yKHk9MDt5PGg7eSsrKXsKICAgIGZvcih4PTA7eDx3O3grKyl7CiAgICAgIHA9eSp3K3g7CiAgICAgIGlmKGxhYltwXSE9PWlkKXsgY29udGludWU7IH0KICAgICAgdmFyIHM9eCt5LCBkMj14LXk7CiAgICAgIGlmKCF0bHx8czx0bC5zKXsgdGw9e3g6eCx5OnksczpzfTsgfQogICAgICBpZighYnJ8fHM+YnIucyl7IGJyPXt4OngseTp5LHM6c307IH0KICAgICAgaWYoIXRyfHxkMj50ci5kKXsgdHI9e3g6eCx5OnksZDpkMn07IH0KICAgICAgaWYoIWJsfHxkMjxibC5kKXsgYmw9e3g6eCx5OnksZDpkMn07IH0KICAgIH0KICB9CiAgcmV0dXJuIHt0bDp0bCx0cjp0cixicjpicixibDpibH07Cn0KZnVuY3Rpb24gYXJlYVF1YWQocSl7CiAgaWYoIXF8fCFxLnRsfHwhcS50cnx8IXEuYnJ8fCFxLmJsKXsgcmV0dXJuIDA7IH0KICB2YXIgcHRzPVtxLnRsLHEudHIscS5icixxLmJsXSwgYT0wLCBpOwogIGZvcihpPTA7aTw0O2krKyl7IHZhciBwPXB0c1tpXSwgcj1wdHNbKGkrMSklNF07IGErPXAueCpyLnktci54KnAueTsgfQogIHJldHVybiBNYXRoLmFicyhhKS8yOwp9CmZ1bmN0aW9uIHF1YWRWYWxpZG8ocSwgZHcsIGRoKXsKICBpZighcXx8IXEudGx8fCFxLnRyfHwhcS5icnx8IXEuYmwpeyByZXR1cm4ge29rOmZhbHNlLCBtb3Rpdm86J2Zvcm1hJ307IH0KICB2YXIgcHRzPVtxLnRsLHEudHIscS5icixxLmJsXSwgaSwgc2lnPTA7CiAgZm9yKGk9MDtpPDQ7aSsrKXsKICAgIHZhciBhPXB0c1tpXSwgYj1wdHNbKGkrMSklNF0sIGM9cHRzWyhpKzIpJTRdOwogICAgdmFyIGNyPShiLngtYS54KSooYy55LWIueSktKGIueS1hLnkpKihjLngtYi54KTsKICAgIGlmKE1hdGguYWJzKGNyKTwwLjUpeyByZXR1cm4ge29rOmZhbHNlLCBtb3Rpdm86J2Zvcm1hJ307IH0KICAgIHZhciBzPWNyPjA/MTotMTsKICAgIGlmKHNpZz09PTApeyBzaWc9czsgfSBlbHNlIGlmKHMhPT1zaWcpeyByZXR1cm4ge29rOmZhbHNlLCBtb3Rpdm86J2Zvcm1hJ307IH0KICB9CiAgZnVuY3Rpb24gZHN0KGEsYil7IHZhciBkeD1hLngtYi54LCBkeT1hLnktYi55OyByZXR1cm4gTWF0aC5zcXJ0KGR4KmR4K2R5KmR5KTsgfQogIHZhciBhcj1kc3QocS50bCxxLnRyKSwgYWI9ZHN0KHEudHIscS5iciksIGFpPWRzdChxLmJyLHEuYmwpLCBhej1kc3QocS5ibCxxLnRsKTsKICB2YXIgbW49TWF0aC5taW4oYXIsYWIsYWksYXopOwogIGlmKG1uPE1hdGgubWF4KGR3LGRoKSowLjA5KXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidwZXF1ZW5vJ307IH0KICB2YXIgZnI9YXJlYVF1YWQocSkvKGR3KmRoKTsKICBpZihmcj4wLjk0KXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidmb3JtYSd9OyB9CiAgdmFyIGFzcD0oYXIrYWkpL01hdGgubWF4KDEsKGFiK2F6KSk7CiAgaWYoYXNwPDAuNDV8fGFzcD4yLjUpeyByZXR1cm4ge29rOmZhbHNlLCBtb3Rpdm86J2Zvcm1hJ307IH0KICBpZihmcjwwLjEwKXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidwZXF1ZW5vJywgZnJhYzpmcn07IH0KICByZXR1cm4ge29rOnRydWUsIGZyYWM6ZnIsIGFzcDphc3B9Owp9CmZ1bmN0aW9uIG5pdG9EZShsdW0sIGR3LCBkaCwgY2FqYSl7CiAgdmFyIHgwPTEseTA9MSx4MT1kdy0xLHkxPWRoLTE7CiAgaWYoY2FqYSl7IHgwPU1hdGgubWF4KDEsY2FqYS54KzEpOyB5MD1NYXRoLm1heCgxLGNhamEueSsxKTsgeDE9TWF0aC5taW4oZHctMSxjYWphLngrY2FqYS53LTEpOyB5MT1NYXRoLm1pbihkaC0xLGNhamEueStjYWphLmgtMSk7IH0KICB2YXIgcz0wLHMyPTAsaz0wLHgseTsKICBmb3IoeT15MDt5PHkxO3krKyl7CiAgICBmb3IoeD14MDt4PHgxO3grKyl7CiAgICAgIHZhciBwPXkqZHcreDsKICAgICAgdmFyIGxwPTQqbHVtW3BdLWx1bVtwLTFdLWx1bVtwKzFdLWx1bVtwLWR3XS1sdW1bcCtkd107CiAgICAgIHMrPWxwOyBzMis9bHAqbHA7IGsrKzsKICAgIH0KICB9CiAgaWYoIWspeyByZXR1cm4ge3Y6MH07IH0KICB2YXIgbT1zL2s7CiAgcmV0dXJuIHt2OihzMi9rKS1tKm19Owp9CmZ1bmN0aW9uIGZyYWNjaW9uQmxhbmNvKGx1bSwgZHcsIGRoLCBjYWphKXsKICB2YXIgeDA9MCx5MD0wLHgxPWR3LHkxPWRoLGs9MCxiPTAseCx5OwogIGlmKGNhamEpeyB4MD1NYXRoLm1heCgwLGNhamEueCk7IHkwPU1hdGgubWF4KDAsY2FqYS55KTsgeDE9TWF0aC5taW4oZHcsY2FqYS54K2NhamEudyk7IHkxPU1hdGgubWluKGRoLGNhamEueStjYWphLmgpOyB9CiAgZm9yKHk9eTA7eTx5MTt5KyspeyBmb3IoeD14MDt4PHgxO3grKyl7IGsrKzsgaWYobHVtW3kqZHcreF0+PTI0Nil7IGIrKzsgfSB9IH0KICByZXR1cm4gaz8oYi9rKTowOwp9CmZ1bmN0aW9uIG1lZGlhbmFOdW0oYSl7CiAgaWYoIWF8fCFhLmxlbmd0aCl7IHJldHVybiAwOyB9CiAgdmFyIGI9YS5zbGljZSgpLnNvcnQoZnVuY3Rpb24oeCx5KXsgcmV0dXJuIHgteTsgfSk7CiAgcmV0dXJuIGJbTWF0aC5mbG9vcihiLmxlbmd0aC8yKV07Cn0KZnVuY3Rpb24gbWVkaWFuYVF1YWQoaGlzdCl7CiAgaWYoIWhpc3R8fCFoaXN0Lmxlbmd0aCl7IHJldHVybiBudWxsOyB9CiAgdmFyIEs9Wyd0bCcsJ3RyJywnYnInLCdibCddLCByZXM9e30sIGksIGssIHhzLCB5czsKICBmb3Ioaz0wO2s8Sy5sZW5ndGg7aysrKXsKICAgIHhzPVtdOyB5cz1bXTsKICAgIGZvcihpPTA7aTxoaXN0Lmxlbmd0aDtpKyspeyBpZihoaXN0W2ldJiZoaXN0W2ldW0tba11dKXsgeHMucHVzaChoaXN0W2ldW0tba11dLngpOyB5cy5wdXNoKGhpc3RbaV1bS1trXV0ueSk7IH0gfQogICAgaWYoIXhzLmxlbmd0aCl7IHJldHVybiBudWxsOyB9CiAgICByZXNbS1trXV09e3g6bWVkaWFuYU51bSh4cyksIHk6bWVkaWFuYU51bSh5cyl9OwogIH0KICByZXR1cm4gcmVzOwp9CmZ1bmN0aW9uIHF1YWRFc3RhYmxlKGhpc3QpewogIHZhciBtZWQ9bWVkaWFuYVF1YWQoaGlzdCksIEs9Wyd0bCcsJ3RyJywnYnInLCdibCddLCBpLCBrOwogIGlmKCFtZWR8fCFoaXN0fHxoaXN0Lmxlbmd0aDw0KXsgcmV0dXJuIGZhbHNlOyB9CiB2YXIgdG9sPTAuMDIqTWF0aC5tYXgoaGlzdFswXS52d3x8NjQwLCBoaXN0WzBdLnZofHw0ODApOwogIGZvcihrPTA7azxLLmxlbmd0aDtrKyspewogICAgZm9yKGk9TWF0aC5tYXgoMCxoaXN0Lmxlbmd0aC00KTtpPGhpc3QubGVuZ3RoO2krKyl7CiAgICAgIHZhciBxPWhpc3RbaV0mJmhpc3RbaV1bS1trXV07CiAgICAgIGlmKCFxfHwhbWVkW0tba11dKXsgcmV0dXJuIGZhbHNlOyB9CiAgICAgIHZhciBkeD1xLngtbWVkW0tba11dLngsIGR5PXEueS1tZWRbS1trXV0ueTsKICAgICAgaWYoTWF0aC5zcXJ0KGR4KmR4K2R5KmR5KT50b2wpeyByZXR1cm4gZmFsc2U7IH0KICAgIH0KICB9CiAgcmV0dXJuIHRydWU7Cn0KZnVuY3Rpb24gZGV0ZWN0YXJEb2NRdWFkKHYpewogIHRyeXsKICAgIHZhciBEPXp5RGV0KCk7CiAgICB2YXIgdnc9di52aWRlb1dpZHRofHwwLCB2aD12LnZpZGVvSGVpZ2h0fHwwOwogICAgaWYoIXZ3fHwhdmgpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIGR3PTE2MCwgZGg9TWF0aC5yb3VuZChkdyp2aC92dyk7CiAgICBpZihkaDw4KXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciBjPUQuY3ZROyBpZighYyl7IGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7IEQuY3ZRPWM7IH0KICAgIGlmKGMud2lkdGghPT1kd3x8Yy5oZWlnaHQhPT1kaCl7IGMud2lkdGg9ZHc7IGMuaGVpZ2h0PWRoOyB9CiAgICB2YXIgZz1jLmdldENvbnRleHQoJzJkJyk7IGlmKCFnKXsgcmV0dXJuIG51bGw7IH0KICAgIGcuZHJhd0ltYWdlKHYsMCwwLGR3LGRoKTsKICAgIHZhciBkPWcuZ2V0SW1hZ2VEYXRhKDAsMCxkdyxkaCkuZGF0YSwgbj1kdypkaCwgaSwgeCwgeTsKICAgIHZhciBsdW09bmV3IFVpbnQ4QXJyYXkobiksIHN1bT0wOwogICAgZm9yKGk9MDtpPG47aSsrKXsgbHVtW2ldPShkW2kqNF0qMytkW2kqNCsxXSo0K2RbaSo0KzJdKT4+Mzsgc3VtKz1sdW1baV07IH0KICAgIHZhciBsdXo9c3VtL247CiAgICAvKiBoZXJlZGFkbyB2MTQ6IG1hc2NhcmEgYW50aS10ZWxhIGRlIGNvbG9yLiBFbiBncmlzLCB1bmEgdGVsYSByb3NhL3JvamEKICAgICAgIGNsYXJhIHNlIHZlIGNhc2kgaWd1YWwgcXVlIGxhIHRhcmpldGEgeSBlbCB1bWJyYWwgZGUgT3RzdSBubyBzZXBhcmE6CiAgICAgICBsYSBndWlhIG5vIGFnYXJyYSBsYXMgNCBlc3F1aW5hcy4gTGEgVEFSSkVUQSBlcyBjbGFyYSB5IFBPQ08gc2F0dXJhZGE7CiAgICAgICBsYSB0ZWxhIGRlIGNvbG9yIGVzIE1VWSBzYXR1cmFkYS4gUHJ1ZWJvIHByaW1lcm8gY29uIGVzYSBtYXNjYXJhIHkgc2kKICAgICAgIG5vIGRhIHVuIGN1YWRyaWxhdGVybyB2YWxpZG8gY2FpZ28gYWwgdW1icmFsIGRlIE90c3UgKGZvbmRvIG9zY3VybykuICovCiAgICBmdW5jdGlvbiByZXN1bHRhZG9EZU1hc2NhcmEobWFza0Fycil7CiAgICAgIHZhciB0b3QyPTAsIGkyOwogICAgICBmb3IoaTI9MDtpMjxuO2kyKyspeyBpZihtYXNrQXJyW2kyXSl7IHRvdDIrKzsgfSB9CiAgICAgIGlmKHRvdDI8biowLjAzfHx0b3QyPm4qMC45NjUpeyByZXR1cm4gbnVsbDsgfQogICAgICB2YXIgY2MyPWV0aXF1ZXRhQ29tcG9uZW50ZXMobWFza0FycixkdyxkaCk7CiAgICAgIGlmKCFjYzIubWVqb3IuaWR8fGNjMi5tZWpvci50YW08biowLjA0KXsgcmV0dXJuIG51bGw7IH0KICAgICAgdmFyIHEyPWVzcXVpbmFzRGVNYXNjYXJhKGNjMi5sYWIsY2MyLm1lam9yLmlkLGR3LGRoKTsKICAgICAgaWYoIXEyLnRsfHwhcTIudHJ8fCFxMi5icnx8IXEyLmJsKXsgcmV0dXJuIG51bGw7IH0KICAgICAgdmFyIHZhbDI9cXVhZFZhbGlkbyhxMixkdyxkaCk7CiAgICAgIGlmKCF2YWwyLm9rKXsgcmV0dXJuIG51bGw7IH0KICAgICAgdmFyIHhhPU1hdGgubWF4KDAsTWF0aC5taW4ocTIudGwueCxxMi5ibC54KSksIHhiPU1hdGgubWluKGR3LE1hdGgubWF4KHEyLnRyLngscTIuYnIueCkpOwogICAgICB2YXIgeWE9TWF0aC5tYXgoMCxNYXRoLm1pbihxMi50bC55LHEyLnRyLnkpKSwgeWI9TWF0aC5taW4oZGgsTWF0aC5tYXgocTIuYmwueSxxMi5ici55KSk7CiAgICAgIHZhciBjYWphMj17eDp4YSx5OnlhLHc6TWF0aC5tYXgoMSx4Yi14YSksaDpNYXRoLm1heCgxLHliLXlhKX07CiAgICAgIHZhciBudDI9bml0b0RlKGx1bSxkdyxkaCxjYWphMik7CiAgICAgIHZhciBibGEyPWZyYWNjaW9uQmxhbmNvKGx1bSxkdyxkaCxjYWphMik7CiAgICAgIHZhciBzeDI9dncvZHcsIHN5Mj12aC9kaDsKICAgICAgcmV0dXJuIHt0bDp7eDpxMi50bC54KnN4Mix5OnEyLnRsLnkqc3kyfSwgdHI6e3g6cTIudHIueCpzeDIseTpxMi50ci55KnN5Mn0sIGJyOnt4OnEyLmJyLngqc3gyLHk6cTIuYnIueSpzeTJ9LCBibDp7eDpxMi5ibC54KnN4Mix5OnEyLmJsLnkqc3kyfSwgbHV6Omx1eiwgbml0bzpudDIudiwgYmxhbmNvOmJsYTIsIHZ3OnZ3LCB2aDp2aCwgZnJhYzp2YWwyLmZyYWN9OwogICAgfQogICAgdmFyIG1hc2tTPW5ldyBVaW50OEFycmF5KG4pLCB0b3RTPTA7CiAgICBmb3IoaT0wO2k8bjtpKyspewogICAgICB2YXIgcjQ9ZFtpKjRdLCBnND1kW2kqNCsxXSwgYjQ9ZFtpKjQrMl07CiAgICAgIHZhciBteD0ocjQ+ZzQpPyhyND5iND9yNDpiNCk6KGc0PmI0P2c0OmI0KSwgbW49KHI0PGc0KT8ocjQ8YjQ/cjQ6YjQpOihnNDxiND9nNDpiNCk7CiAgICAgIGlmKChteC1tbik8PTg1JiZsdW1baV0+PTExMil7IG1hc2tTW2ldPTE7IHRvdFMrKzsgfQogICAgfQogICAgaWYodG90Uz49biowLjAzKXsKICAgICAgdmFyIHJTPXJlc3VsdGFkb0RlTWFzY2FyYShtYXNrUyk7CiAgICAgIGlmKHJTKXsgcmV0dXJuIHJTOyB9CiAgICB9CiAgICB2YXIgbGI9bmV3IFVpbnQ4QXJyYXkobik7CiAgICBmb3IoeT0xO3k8ZGgtMTt5KyspeyBmb3IoeD0xO3g8ZHctMTt4KyspeyB2YXIgcHA9eSpkdyt4OyBsYltwcF09KGx1bVtwcF0qNCtsdW1bcHAtMV0rbHVtW3BwKzFdK2x1bVtwcC1kd10rbHVtW3BwK2R3XSk+PjM7IH0gfQogICAgdmFyIGhpc3Q9bmV3IEludDMyQXJyYXkoMjU2KTsgZm9yKGk9MDtpPG47aSsrKXsgaGlzdFtsYltpXV0rKzsgfQogICAgdmFyIHRocj1vdHN1VW1icmFsKGhpc3Qsbik7CiAgICB2YXIgbWFzaz1uZXcgVWludDhBcnJheShuKSwgdG90PTA7CiAgICBmb3IoaT0wO2k8bjtpKyspeyB2YXIgdjE9KGxiW2ldPnRocik/MTowOyBtYXNrW2ldPXYxOyB0b3QrPXYxOyB9CiAgICBpZih0b3Q8biowLjAzKXsgcmV0dXJuIG51bGw7IH0KICAgIGlmKHRvdD5uKjAuOTY1KXsKICAgICAgdmFyIG50MD1uaXRvRGUobHVtLGR3LGRoLG51bGwpOwogICAgICByZXR1cm4ge2xsZW5vOnRydWUsIGx1ejpsdXosIG5pdG86bnQwLnYsIGJsYW5jbzpmcmFjY2lvbkJsYW5jbyhsdW0sZHcsZGgsbnVsbCksIHZ3OnZ3LCB2aDp2aH07CiAgICB9CiAgICB2YXIgY2M9ZXRpcXVldGFDb21wb25lbnRlcyhtYXNrLGR3LGRoKTsKICAgIGlmKCFjYy5tZWpvci5pZHx8Y2MubWVqb3IudGFtPG4qMC4wNCl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgcT1lc3F1aW5hc0RlTWFzY2FyYShjYy5sYWIsY2MubWVqb3IuaWQsZHcsZGgpOwogICAgaWYoIXEudGx8fCFxLnRyfHwhcS5icnx8IXEuYmwpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIHZhbD1xdWFkVmFsaWRvKHEsZHcsZGgpOwogICAgdmFyIHgwPU1hdGgubWF4KDAsTWF0aC5taW4ocS50bC54LHEuYmwueCkpLCB4MT1NYXRoLm1pbihkdyxNYXRoLm1heChxLnRyLngscS5ici54KSk7CiAgICB2YXIgeTA9TWF0aC5tYXgoMCxNYXRoLm1pbihxLnRsLnkscS50ci55KSksIHkxPU1hdGgubWluKGRoLE1hdGgubWF4KHEuYmwueSxxLmJyLnkpKTsKICAgIHZhciBjYWphPXt4OngwLHk6eTAsdzpNYXRoLm1heCgxLHgxLXgwKSxoOk1hdGgubWF4KDEseTEteTApfTsKICAgIHZhciBudD1uaXRvRGUobHVtLGR3LGRoLGNhamEpOwogICAgdmFyIGJsYT1mcmFjY2lvbkJsYW5jbyhsdW0sZHcsZGgsY2FqYSk7CiAgICB2YXIgc3g9dncvZHcsIHN5PXZoL2RoOwogICAgZnVuY3Rpb24gZXNjKHApeyByZXR1cm4ge3g6cC54KnN4LCB5OnAueSpzeX07IH0KICAgIHZhciByZXM9e3RsOmVzYyhxLnRsKSwgdHI6ZXNjKHEudHIpLCBicjplc2MocS5iciksIGJsOmVzYyhxLmJsKSwgbHV6Omx1eiwgbml0bzpudC52LCBibGFuY286YmxhLCB2dzp2dywgdmg6dmh9OwogICAgaWYoIXZhbC5vayl7IHJlcy5kZXNjYXJ0YWRvPXZhbC5tb3Rpdm87IHJldHVybiByZXM7IH0KICAgIHJlcy5mcmFjPXZhbC5mcmFjOwogICAgcmV0dXJuIHJlczsKICB9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9Cn0KZnVuY3Rpb24gZGV0ZWN0YXJEb2NCb3godil7CiAgdHJ5ewogICAgdmFyIEQ9enlEZXQoKTsKICAgIHZhciBjPUQuY3ZEb2M7CiAgICBpZighYyl7IGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7IEQuY3ZEb2M9YzsgfQogICAgdmFyIGR3PTEyOCwgZGg9TWF0aC5tYXgoOCxNYXRoLnJvdW5kKDEyOCooKHYudmlkZW9IZWlnaHR8fDMpLygodi52aWRlb1dpZHRofHw0KSoxLjApKSkpOwogICAgaWYoYy53aWR0aCE9PWR3fHxjLmhlaWdodCE9PWRoKXsgYy53aWR0aD1kdzsgYy5oZWlnaHQ9ZGg7IH0KICAgIHZhciBnPWMuZ2V0Q29udGV4dCgnMmQnKTsgaWYoIWcpeyByZXR1cm4gbnVsbDsgfQogICAgZy5kcmF3SW1hZ2UodiwwLDAsZHcsZGgpOwogICAgdmFyIGQ9Zy5nZXRJbWFnZURhdGEoMCwwLGR3LGRoKS5kYXRhLCBuPWR3KmRoOwogICAgdmFyIGhpc3Q9bmV3IEludDMyQXJyYXkoMjU2KSwgbHVtPW5ldyBVaW50OEFycmF5KG4pLCBpLHgseTsKICAgIGZvcihpPTA7aTxuO2krKyl7IHZhciByPWRbaSo0XSwgZ2c9ZFtpKjQrMV0sIGI9ZFtpKjQrMl07IGx1bVtpXT0ociozK2dnKjQrYik+PjM7IGhpc3RbbHVtW2ldXSsrOyB9CiAgICB2YXIgdGhyPW90c3VVbWJyYWwoaGlzdCxuKTsKICAgIHZhciBmaWxhcz1uZXcgSW50MzJBcnJheShkaCksIGNvbHM9bmV3IEludDMyQXJyYXkoZHcpLCB0b3Q9MDsKICAgIGZvcih5PTA7eTxkaDt5KyspeyBmb3IoeD0wO3g8ZHc7eCsrKXsgaWYobHVtW3kqZHcreF0+dGhyKXsgZmlsYXNbeV0rKzsgY29sc1t4XSsrOyB0b3QrKzsgfSB9IH0KICAgIGlmKHRvdDxuKjAuMDR8fHRvdD5uKjAuOTg1KXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciByZj1yYW5nb1Byb3llY2Npb24oZmlsYXMsZGgsTWF0aC5tYXgoMixNYXRoLnJvdW5kKGR3KjAuMTgpKSk7CiAgICB2YXIgcmM9cmFuZ29Qcm95ZWNjaW9uKGNvbHMsZHcsTWF0aC5tYXgoMixNYXRoLnJvdW5kKGRoKjAuMTgpKSk7CiAgICBpZighcmZ8fCFyYyl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgc3g9KHYudmlkZW9XaWR0aHx8NjQwKS9kdywgc3k9KHYudmlkZW9IZWlnaHR8fDQ4MCkvZGg7CiAgICB2YXIgYng9cmNbMF0qc3gsIGJ5PXJmWzBdKnN5LCBidz0ocmNbMV0rMS1yY1swXSkqc3gsIGJoPShyZlsxXSsxLXJmWzBdKSpzeTsKICAgIGlmKGJ3PDh8fGJoPDgpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIHN1bWE9MCwgaTI7CiAgICBmb3IoaTI9MDtpMjxuO2kyKyspeyBzdW1hKz1sdW1baTJdOyB9CiAgICB2YXIgbHV6PXN1bWEvbjsKICAgIHZhciBzdW1WPTAsIHN1bVYyPTAsIG4yPTAsIHgyLCB5MjsKICAgIGZvcih5Mj0xO3kyPGRoLTE7eTIrKyl7CiAgICAgIGZvcih4Mj0xO3gyPGR3LTE7eDIrKyl7CiAgICAgICAgdmFyIGlpPXkyKmR3K3gyOwogICAgICAgIHZhciBsYXA9NCpsdW1baWldLWx1bVtpaS0xXS1sdW1baWkrMV0tbHVtW2lpLWR3XS1sdW1baWkrZHddOwogICAgICAgIHN1bVYrPWxhcDsgc3VtVjIrPWxhcCpsYXA7IG4yKys7CiAgICAgIH0KICAgIH0KICAgIHZhciBtZWRpYT1zdW1WL01hdGgubWF4KDEsbjIpOwogICAgdmFyIHZhckw9KHN1bVYyL01hdGgubWF4KDEsbjIpKS1tZWRpYSptZWRpYTsKICAgIHJldHVybiB7eDpieCwgeTpieSwgdzpidywgaDpiaCwgbHV6Omx1eiwgbml0bzoodmFyTD49NDApLCBmb2NvOk1hdGgucm91bmQodmFyTCl9OwogIH1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0KfQpmdW5jdGlvbiBjZW50cm9EZShwdW50b3MpewogIHZhciBzeD0wLCBzeT0wLCBpOwogIGZvcihpPTA7aTxwdW50b3MubGVuZ3RoO2krKyl7IHN4Kz1wdW50b3NbaV0ueDsgc3krPXB1bnRvc1tpXS55OyB9CiAgcmV0dXJuIHt4OnN4L3B1bnRvcy5sZW5ndGgsIHk6c3kvcHVudG9zLmxlbmd0aH07Cn0KZnVuY3Rpb24gZWFyRGUocHVudG9zKXsKICBpZighcHVudG9zfHxwdW50b3MubGVuZ3RoPDYpeyByZXR1cm4gMTsgfQogIGZ1bmN0aW9uIGQyKGEsYil7IHZhciBkeD1hLngtYi54LCBkeT1hLnktYi55OyByZXR1cm4gTWF0aC5zcXJ0KGR4KmR4K2R5KmR5KTsgfQogIHZhciBoPWQyKHB1bnRvc1swXSxwdW50b3NbM10pOwogIGlmKGg8MWUtNil7IHJldHVybiAxOyB9CiAgcmV0dXJuIChkMihwdW50b3NbMV0scHVudG9zWzVdKStkMihwdW50b3NbMl0scHVudG9zWzRdKSkvKDIqaCk7Cn0KZnVuY3Rpb24gZXZhbHVhQ2FyYShpbmZvKXsKICB2YXIgcj17dmlzdGE6dHJ1ZSwgb2s6ZmFsc2UsIHRhbTonYmllbicsIG1vdGl2bzonJywgY29kOicnfTsKICBpZihpbmZvLmx1ejw0NSl7IHIuY29kPSdsdXonOyByLm1vdGl2bz0nUE9DQSBMVVo6IHBvbiB0dSBjYXJhIGhhY2lhIGxhIGx1eiBvIGVuY2llbmRlIHVuYSBsYW1wYXJhLic7IHJldHVybiByOyB9CiAgaWYoaW5mby5uaXRvPDE1KXsgci5jb2Q9J25pdG8nOyByLm1vdGl2bz0nTm8gc2UgdmUgTklUSURPOiBzb3N0XHUwMEU5biBlbCB0ZWxlZm9ubyBmaXJtZSB5IGVzcGVyYSBlbCBlbmZvcXVlLic7IHJldHVybiByOyB9CiAgaWYoaW5mby50YW08MC4zMCl7IHIudGFtPSdsZWpvcyc7IHIuY29kPSdsZWpvcyc7IHIubW90aXZvPSdBQ0VSQ0FURTogdHUgY2FyYSBkZWJlIGxsZW5hciBlbCBPVkFMTyAoZm90byBkZSByb3N0cm8sIG5vIG1lZGlvIGN1ZXJwbykuJzsgcmV0dXJuIHI7IH0KICBpZihpbmZvLnRhbT4wLjg2KXsgci50YW09J2NlcmNhJzsgci5jb2Q9J2NlcmNhJzsgci5tb3Rpdm89J0FMRUpBVEUgdW4gcG9jbyBwYXJhIHF1ZSB0dSBjYXJhIHF1ZXBhIGVudGVyYSBlbiBlbCBvdmFsby4nOyByZXR1cm4gcjsgfQogIGlmKE1hdGguYWJzKGluZm8uZngtMC41KT4wLjE2fHxpbmZvLmZ5PDAuMzB8fGluZm8uZnk+MC43NCl7IHIuY29kPSdmdWVyYSc7IHIubW90aXZvPSdDZW50cmEgdHUgY2FyYSBkZW50cm8gZGVsIE9WQUxPLCBtaXJhbmRvIGEgbGEgY2FtYXJhLic7IHJldHVybiByOyB9CiAgaWYoTWF0aC5hYnMoaW5mby5yb2xsKT4xNil7IHIuY29kPSdyb2xsJzsgci5tb3Rpdm89J0VuZGVyZXphIGxhIGNhYmV6YTogbm8gbGEgaW5jbGluZXMgYSBsb3MgbGFkb3MuJzsgcmV0dXJuIHI7IH0KICBpZihNYXRoLmFicyhpbmZvLnlhdyk+MC4yNCl7IHIuY29kPSd5YXcnOyByLm1vdGl2bz0nTWlyYSBERSBGUkVOVEUgYSBsYSBjYW1hcmEsIG5vIGRlIGxhZG8uJzsgcmV0dXJuIHI7IH0KICBpZihpbmZvLm9qb3M8MC4xMCl7IHIuY29kPSdvam9zJzsgci5tb3Rpdm89J0FicmUgbG9zIG9qb3MgeSBtaXJhIGZpam8gYSBsYSBjYW1hcmEuJzsgcmV0dXJuIHI7IH0KICByLm9rPXRydWU7IHIubW90aXZvPSdQZXJmZWN0bzogc29zdFx1MDBFOW4gbGEgcG9zaWNpb24uLi4nOwogIHJldHVybiByOwp9CmZ1bmN0aW9uIG5pdG9EZVJnYmEoZGF0b3MsIGR3LCBkaCwgY2FqYSl7CiAgdmFyIHgwPU1hdGgubWF4KDEsY2FqYS54KzEpLCB5MD1NYXRoLm1heCgxLGNhamEueSsxKTsKICB2YXIgeDE9TWF0aC5taW4oZHctMSxjYWphLngrY2FqYS53LTEpLCB5MT1NYXRoLm1pbihkaC0xLGNhamEueStjYWphLmgtMSk7CiAgdmFyIHM9MCxzMj0wLGs9MCx4LHk7CiAgZm9yKHk9eTA7eTx5MTt5KyspewogICAgZm9yKHg9eDA7eDx4MTt4KyspewogICAgICB2YXIgcD15KmR3K3g7CiAgICAgIHZhciBsMT0oZGF0b3NbcCo0XSozK2RhdG9zW3AqNCsxXSo0K2RhdG9zW3AqNCsyXSk+PjM7CiAgICAgIHZhciBsMj0oZGF0b3NbKHAtMSkqNF0qMytkYXRvc1socC0xKSo0KzFdKjQrZGF0b3NbKHAtMSkqNCsyXSk+PjM7CiAgICAgIHZhciBsMz0oZGF0b3NbKHArMSkqNF0qMytkYXRvc1socCsxKSo0KzFdKjQrZGF0b3NbKHArMSkqNCsyXSk+PjM7CiAgICAgIHZhciBsND0oZGF0b3NbKHAtZHcpKjRdKjMrZGF0b3NbKHAtZHcpKjQrMV0qNCtkYXRvc1socC1kdykqNCsyXSk+PjM7CiAgICAgIHZhciBsNT0oZGF0b3NbKHArZHcpKjRdKjMrZGF0b3NbKHArZHcpKjQrMV0qNCtkYXRvc1socCtkdykqNCsyXSk+PjM7CiAgICAgIHZhciBscD00KmwxLWwyLWwzLWw0LWw1OwogICAgICBzKz1scDsgczIrPWxwKmxwOyBrKys7CiAgICB9CiAgfQogIGlmKCFrKXsgcmV0dXJuIDA7IH0KICB2YXIgbT1zL2s7CiAgcmV0dXJuIChzMi9rKS1tKm07Cn0KZnVuY3Rpb24gYnVzY2FyQ2FyYVZpdmEodiwgY2IpewogIHRyeXsKICAgIGlmKCEoVy5mYWNlYXBpJiZXLmZhY2VhcGkubmV0cyYmVy5mYWNlYXBpLm5ldHMudGlueUZhY2VEZXRlY3RvciYmVy5mYWNlYXBpLlRpbnlGYWNlRGV0ZWN0b3JPcHRpb25zKSl7IGNiKG51bGwpOyByZXR1cm47IH0KICAgIHZhciBEPXp5RGV0KCk7CiAgICB2YXIgdnc9di52aWRlb1dpZHRofHw2NDAsIHZoPXYudmlkZW9IZWlnaHR8fDQ4MDsKICAgIHZhciBkdz0yMjQsIGRoPU1hdGgubWF4KDgwLE1hdGgucm91bmQoZHcqdmgvdncpKTsKICAgIHZhciBjPUQuY3ZDYXJhOwogICAgaWYoIWMpeyBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOyBELmN2Q2FyYT1jOyB9CiAgICBpZihjLndpZHRoIT09ZHd8fGMuaGVpZ2h0IT09ZGgpeyBjLndpZHRoPWR3OyBjLmhlaWdodD1kaDsgfQogICAgdmFyIGc9Yy5nZXRDb250ZXh0KCcyZCcpOyBpZighZyl7IGNiKG51bGwpOyByZXR1cm47IH0KICAgIGcuZHJhd0ltYWdlKHYsMCwwLGR3LGRoKTsKICAgIHZhciBkYXRvcz1udWxsOwogICAgdHJ5eyBkYXRvcz1nLmdldEltYWdlRGF0YSgwLDAsZHcsZGgpLmRhdGE7IH1jYXRjaChlKXsgZGF0b3M9bnVsbDsgfQogICAgdmFyIG9wdD1uZXcgVy5mYWNlYXBpLlRpbnlGYWNlRGV0ZWN0b3JPcHRpb25zKHtpbnB1dFNpemU6MjI0LCBzY29yZVRocmVzaG9sZDowLjQ1fSk7CiAgICBXLmZhY2VhcGkuZGV0ZWN0U2luZ2xlRmFjZShjLG9wdCkud2l0aEZhY2VMYW5kbWFya3MoKS53aXRoRmFjZURlc2NyaXB0b3IoKS50aGVuKGZ1bmN0aW9uKHIpewogICAgICB0cnl7CiAgICAgICAgaWYoIXJ8fCFyLmRldGVjdGlvbil7IGNiKHt2aXN0YTpmYWxzZSwgb2s6ZmFsc2UsIHQ6RGF0ZS5ub3coKX0pOyByZXR1cm47IH0KICAgICAgICB2YXIgYj1yLmRldGVjdGlvbi5ib3g7CiAgICAgICAgdmFyIGZ4PShiLngrYi53aWR0aC8yKS9kdywgZnk9KGIueStiLmhlaWdodC8yKS9kaDsKICAgICAgICB2YXIgdGFtPWIuaGVpZ2h0L2RoOwogICAgICAgIHZhciByb2xsPTAsIHlhdz0wLCBvam9zPTE7CiAgICAgICAgaWYoci5sYW5kbWFya3MpewogICAgICAgICAgdmFyIEw9ci5sYW5kbWFya3MuZ2V0TGVmdEV5ZSgpLCBSPXIubGFuZG1hcmtzLmdldFJpZ2h0RXllKCksIE49ci5sYW5kbWFya3MuZ2V0Tm9zZSgpOwogICAgICAgICAgaWYoTCYmUiYmTC5sZW5ndGg+PTQmJlIubGVuZ3RoPj00KXsKICAgICAgICAgICAgdmFyIGxjPWNlbnRyb0RlKEwpLCByYz1jZW50cm9EZShSKTsKICAgICAgICAgICAgcm9sbD1NYXRoLmF0YW4yKHJjLnktbGMueSwgcmMueC1sYy54KSoxODAvTWF0aC5QSTsKICAgICAgICAgICAgdmFyIG14PShsYy54K3JjLngpLzI7CiAgICAgICAgICAgIGlmKE4mJk4ubGVuZ3RoPjQpeyB5YXc9KE5bNF0ueC1teCkvTWF0aC5tYXgoMSxiLndpZHRoKTsgfQogICAgICAgICAgICBvam9zPU1hdGgubWluKGVhckRlKEwpLCBlYXJEZShSKSk7CiAgICAgICAgICB9CiAgICAgICAgfQogICAgICAgIHZhciBjYWphPXt4Ok1hdGgucm91bmQoYi54KnZ3L2R3KSwgeTpNYXRoLnJvdW5kKGIueSp2aC9kaCksIHc6TWF0aC5yb3VuZChiLndpZHRoKnZ3L2R3KSwgaDpNYXRoLnJvdW5kKGIuaGVpZ2h0KnZoL2RoKX07CiAgICAgICAgY2FqYS54PU1hdGgubWF4KDAsdnctY2FqYS54LWNhamEudyk7CiAgICAgICAgdmFyIGx1ej0wLCBuaXRvPTA7CiAgICAgICAgaWYoZGF0b3MpewogICAgICAgICAgdmFyIHJ4MD1NYXRoLm1heCgwLE1hdGgucm91bmQoYi54KSksIHJ5MD1NYXRoLm1heCgwLE1hdGgucm91bmQoYi55KSk7CiAgICAgICAgICB2YXIgcngxPU1hdGgubWluKGR3LE1hdGgucm91bmQoYi54K2Iud2lkdGgpKSwgcnkxPU1hdGgubWluKGRoLE1hdGgucm91bmQoYi55K2IuaGVpZ2h0KSk7CiAgICAgICAgICB2YXIgcz0wLGs9MCx4LHk7CiAgICAgICAgICBmb3IoeT1yeTA7eTxyeTE7eSsrKXsgZm9yKHg9cngwO3g8cngxO3grKyl7IHMrPShkYXRvc1soeSpkdyt4KSo0XSozK2RhdG9zWyh5KmR3K3gpKjQrMV0qNCtkYXRvc1soeSpkdyt4KSo0KzJdKT4+MzsgaysrOyB9IH0KICAgICAgICAgIGx1ej1rPyhzL2spOjA7CiAgICAgICAgICBuaXRvPShyeDE+cngwKzImJnJ5MT5yeTArMik/bml0b0RlUmdiYShkYXRvcyxkdyxkaCx7eDpyeDAseTpyeTAsdzpyeDEtcngwLGg6cnkxLXJ5MH0pOjA7CiAgICAgICAgfQogICAgICAgIHZhciBkZT1ldmFsdWFDYXJhKHtmeDpmeCxmeTpmeSx0YW06dGFtLHJvbGw6cm9sbCx5YXc6eWF3LG9qb3M6b2pvcyxsdXo6bHV6LG5pdG86bml0b30pOwogICAgICAgIGNiKHt2aXN0YTp0cnVlLCBvazpkZS5vaywgY29kOmRlLmNvZCwgbW90aXZvOmRlLm1vdGl2bywgdGFtOmRlLnRhbSwgZng6ZngsIGZ5OmZ5LCBjYWphOmNhamEsIGx1ejpsdXosIG5pdG86bml0bywgb2pvczpvam9zLCByb2xsOnJvbGwsIHlhdzp5YXcsIHQ6RGF0ZS5ub3coKX0pOwogICAgICB9Y2F0Y2goZSl7IGNiKG51bGwpOyB9CiAgICB9KS5jYXRjaChmdW5jdGlvbigpeyBjYihudWxsKTsgfSk7CiAgfWNhdGNoKGUpeyBjYihudWxsKTsgfQp9CmZ1bmN0aW9uIGVubWFyY2FyVmVyZGUocHNJZCwgdil7CiAgLyogdjExOiBjb250b3JubyBQT0xJR09OQUwgcmVhbCBxdWUgc2lndWUgYWwgZG9jdW1lbnRvIChwcyAyIHkgMykgeSBPVkFMTyBjb24gbW90b3IgZmFjaWFsIChwcyA0KSAqLwogIHRyeXsKICAgIHZhciBPVj17JzInOidvdkYnLCczJzonb3ZBJywnNCc6J292Uyd9OwogICAgdmFyIG92SWQ9T1ZbcHNJZF07CiAgICBpZighb3ZJZCl7IHJldHVybjsgfQogICAgdmFyIHN0SWQ9KHBzSWQ9PT0nMicpPydzdEYnOigocHNJZD09PSczJyk/J3N0QSc6J3N0VicpOwogICAgdmFyIEQ9enlEZXQoKTsKICAgIHZhciBzdD1EW3BzSWRdOwogICAgaWYoIXN0KXsgc3Q9RFtwc0lkXT17Y2FqYTpudWxsLCB0Oi0xZTksIGVzdGFkbzonJywgaXY6bnVsbH07IH0KICAgIHN0LnQwPURhdGUubm93KCk7IHN0LmNhamE9bnVsbDsgc3QuZXN0YWRvPScnOyBzdC5hdXRvPTA7IHN0LmF1dG9IZWNobz1mYWxzZTsgc3QuY2Q9MDsgc3QuaGlzdD1bXTsKICAgIHZhciBwaW50YXJEb2M9ZnVuY3Rpb24oY2FqYSwgZXN0YWRvKXsKICAgICAgdHJ5ewogICAgICAgIHZhciBvdj0kKG92SWQpOyBpZighb3YpeyByZXR1cm47IH0KICAgICAgICB2YXIgdnc9KHYmJnYudmlkZW9XaWR0aCl8fDAsIHZoPSh2JiZ2LnZpZGVvSGVpZ2h0KXx8MDsKICAgICAgICBpZighdnd8fCF2aCl7IHJldHVybjsgfQogICAgICAgIGlmKG92LndpZHRoIT09dnd8fG92LmhlaWdodCE9PXZoKXsgb3Yud2lkdGg9dnc7IG92LmhlaWdodD12aDsgfQogICAgICAgIHZhciBnPW92LmdldENvbnRleHQoJzJkJyk7IGlmKCFnKXsgcmV0dXJuOyB9CiAgICAgICAgZy5jbGVhclJlY3QoMCwwLHZ3LHZoKTsKICAgICAgICB2YXIgeCx5LHcsaDsKICAgICAgICBpZighY2FqYSl7IHg9TWF0aC5yb3VuZCh2dyowLjA3KTsgeT1NYXRoLnJvdW5kKHZoKjAuMDkpOyB3PXZ3LXgqMjsgaD12aC15KjI7IH0KICAgICAgICBlbHNleyB4PWNhamEueDsgeT1jYWphLnk7IHc9Y2FqYS53OyBoPWNhamEuaDsgfQogICAgICAgIGlmKHc8MTB8fGg8MTApeyByZXR1cm47IH0KICAgICAgICB2YXIgY29sPShlc3RhZG89PT0nb2snKT8nIzNmYjk1MCc6KChlc3RhZG89PT0nbWFsJyk/JyNjMDM5MmInOicjZTNiMzQxJyk7CiAgICAgICAgZy5zdHJva2VTdHlsZT1jb2w7IGcubGluZVdpZHRoPTU7CiAgICAgICAgdmFyIEw9TWF0aC5yb3VuZChNYXRoLm1pbih3LGgpKihjYWphPzAuMTY6MC4xNCkpOwogICAgICAgIGcuYmVnaW5QYXRoKCk7CiAgICAgICAgZy5tb3ZlVG8oeCx5K0wpOyBnLmxpbmVUbyh4LHkpOyBnLmxpbmVUbyh4K0wseSk7CiAgICAgICAgZy5tb3ZlVG8oeCt3LUwseSk7IGcubGluZVRvKHgrdyx5KTsgZy5saW5lVG8oeCt3LHkrTCk7CiAgICAgICAgZy5tb3ZlVG8oeCt3LHkraC1MKTsgZy5saW5lVG8oeCt3LHkraCk7IGcubGluZVRvKHgrdy1MLHkraCk7CiAgICAgICAgZy5tb3ZlVG8oeCtMLHkraCk7IGcubGluZVRvKHgseStoKTsgZy5saW5lVG8oeCx5K2gtTCk7CiAgICAgICAgZy5zdHJva2UoKTsKICAgICAgICBnLnNhdmUoKTsKICAgICAgICBnLmdsb2JhbEFscGhhPWNhamE/MC40NTowLjIwOwogICAgICAgIGcubGluZVdpZHRoPTEuNjsgZy5zdHJva2VSZWN0KHgseSx3LGgpOwogICAgICAgIGcucmVzdG9yZSgpOwogICAgICB9Y2F0Y2goZSl7fQogICAgfTsKICAgIHZhciBwaW50YXJRdWFkPWZ1bmN0aW9uKHF1YWQsIGVzdGFkbywgbnVtZXJvKXsKICAgICAgdHJ5ewogICAgICAgIHZhciBvdj0kKG92SWQpOyBpZighb3YpeyByZXR1cm47IH0KICAgICAgICB2YXIgdnc9KHYmJnYudmlkZW9XaWR0aCl8fDAsIHZoPSh2JiZ2LnZpZGVvSGVpZ2h0KXx8MDsKICAgICAgICBpZighdnd8fCF2aCl7IHJldHVybjsgfQogICAgICAgIGlmKG92LndpZHRoIT09dnd8fG92LmhlaWdodCE9PXZoKXsgb3Yud2lkdGg9dnc7IG92LmhlaWdodD12aDsgfQogICAgICAgIHZhciBnPW92LmdldENvbnRleHQoJzJkJyk7IGlmKCFnKXsgcmV0dXJuOyB9CiAgICAgICAgZy5jbGVhclJlY3QoMCwwLHZ3LHZoKTsKICAgICAgICBpZihxdWFkJiZxdWFkLnRsJiZxdWFkLnRyJiZxdWFkLmJyJiZxdWFkLmJsKXsKICAgICAgICAgIHZhciBjb2w9KGVzdGFkbz09PSdvaycpPycjM2ZiOTUwJzooKGVzdGFkbz09PSdtYWwnKT8nI2U2N2UyMic6JyNlM2IzNDEnKTsKICAgICAgICAgIHRyeXsKICAgICAgICAgICAgZy5maWxsU3R5bGU9J3JnYmEoMCwwLDAsMC40NSknOwogICAgICAgICAgICBnLmJlZ2luUGF0aCgpOwogICAgICAgICAgICBnLnJlY3QoMCwwLHZ3LHZoKTsKICAgICAgICAgICAgZy5tb3ZlVG8ocXVhZC50bC54LHF1YWQudGwueSk7IGcubGluZVRvKHF1YWQudHIueCxxdWFkLnRyLnkpOyBnLmxpbmVUbyhxdWFkLmJyLngscXVhZC5ici55KTsgZy5saW5lVG8ocXVhZC5ibC54LHF1YWQuYmwueSk7IGcuY2xvc2VQYXRoKCk7CiAgICAgICAgICAgIGcuZmlsbCgnZXZlbm9kZCcpOwogICAgICAgICAgfWNhdGNoKGVGKXsgZy5maWxsU3R5bGU9J3JnYmEoMCwwLDAsMC4yMiknOyBnLmZpbGxSZWN0KDAsMCx2dyx2aCk7IH0KICAgICAgICAgIGcuc3Ryb2tlU3R5bGU9Y29sOyBnLmxpbmVXaWR0aD01OyBnLmxpbmVKb2luPSdyb3VuZCc7CiAgICAgICAgICBnLmJlZ2luUGF0aCgpOwogICAgICAgICAgZy5tb3ZlVG8ocXVhZC50bC54LHF1YWQudGwueSk7IGcubGluZVRvKHF1YWQudHIueCxxdWFkLnRyLnkpOyBnLmxpbmVUbyhxdWFkLmJyLngscXVhZC5ici55KTsgZy5saW5lVG8ocXVhZC5ibC54LHF1YWQuYmwueSk7IGcuY2xvc2VQYXRoKCk7CiAgICAgICAgICBnLnN0cm9rZSgpOwogICAgICAgICAgZy5maWxsU3R5bGU9Y29sOwogICAgICAgICAgdmFyIHB0cz1bcXVhZC50bCxxdWFkLnRyLHF1YWQuYnIscXVhZC5ibF0sIGk7CiAgICAgICAgICBmb3IoaT0wO2k8NDtpKyspeyBnLmJlZ2luUGF0aCgpOyBnLmFyYyhwdHNbaV0ueCxwdHNbaV0ueSw5LDAsTWF0aC5QSSoyKTsgZy5maWxsKCk7IH0KICAgICAgICB9ZWxzZXsKICAgICAgICAgIHZhciB4Mj1NYXRoLnJvdW5kKHZ3KjAuMDcpLCB5Mj1NYXRoLnJvdW5kKHZoKjAuMTIpLCB3Mj12dy14MioyLCBoMj12aC15MioyOwogICAgICAgICAgZy5zdHJva2VTdHlsZT0oZXN0YWRvPT09J21hbCcpPycjZTY3ZTIyJzonIzlhYTBhNic7CiAgICAgICAgICBnLmxpbmVXaWR0aD00OyBnLnNldExpbmVEYXNoKFsxNCwxMF0pOwogICAgICAgICAgZy5zdHJva2VSZWN0KHgyLHkyLHcyLGgyKTsKICAgICAgICAgIGcuc2V0TGluZURhc2goW10pOwogICAgICAgIH0KICAgICAgICBpZihudW1lcm8+MCl7CiAgICAgICAgICBnLnNhdmUoKTsKICAgICAgICAgIGcuZm9udD0nYm9sZCAxMTBweCBzYW5zLXNlcmlmJzsgZy50ZXh0QWxpZ249J2NlbnRlcic7IGcudGV4dEJhc2VsaW5lPSdtaWRkbGUnOwogICAgICAgICAgZy5saW5lV2lkdGg9MTA7IGcuc3Ryb2tlU3R5bGU9J3JnYmEoMCwwLDAsMC41NSknOwogICAgICAgICAgZy5zdHJva2VUZXh0KFN0cmluZyhudW1lcm8pLHZ3LzIsdmgvMik7CiAgICAgICAgICBnLmZpbGxTdHlsZT0nIzNmYjk1MCc7IGcuZmlsbFRleHQoU3RyaW5nKG51bWVybyksdncvMix2aC8yKTsKICAgICAgICAgIGcucmVzdG9yZSgpOwogICAgICAgIH0KICAgICAgfWNhdGNoKGUpe30KICAgIH07CiAgICB2YXIgcGludGFyT3ZhbG89ZnVuY3Rpb24oZXN0YWRvLCBudW1lcm8sIGluZm8pewogICAgICB0cnl7CiAgICAgICAgdmFyIG92PSQob3ZJZCk7IGlmKCFvdil7IHJldHVybjsgfQogICAgICAgIHZhciB2dz0odiYmdi52aWRlb1dpZHRoKXx8MCwgdmg9KHYmJnYudmlkZW9IZWlnaHQpfHwwOwogICAgICAgIGlmKCF2d3x8IXZoKXsgcmV0dXJuOyB9CiAgICAgICAgaWYob3Yud2lkdGghPT12d3x8b3YuaGVpZ2h0IT09dmgpeyBvdi53aWR0aD12dzsgb3YuaGVpZ2h0PXZoOyB9CiAgICAgICAgdmFyIGc9b3YuZ2V0Q29udGV4dCgnMmQnKTsgaWYoIWcpeyByZXR1cm47IH0KICAgICAgICBnLmNsZWFyUmVjdCgwLDAsdncsdmgpOwogICAgICAgIHZhciBjeD12dyowLjUsIGN5PXZoKjAuNTIsIHJ4PXZ3KjAuMzAsIHJ5PXZoKjAuMzg7CiAgICAgICAgdmFyIGNvbD0oZXN0YWRvPT09J29rJyk/JyMzZmI5NTAnOigoZXN0YWRvPT09J2NhcmEnKT8nI2UzYjM0MSc6JyM5YWEwYTYnKTsKICAgICAgICB0cnl7CiAgICAgICAgICBnLmZpbGxTdHlsZT0ncmdiYSgwLDAsMCwwLjQwKSc7CiAgICAgICAgICBnLmJlZ2luUGF0aCgpOwogICAgICAgICAgZy5yZWN0KDAsMCx2dyx2aCk7CiAgICAgICAgICBnLm1vdmVUbyhjeCtyeCxjeSk7CiAgICAgICAgICBpZihnLmVsbGlwc2UpeyBnLmVsbGlwc2UoY3gsY3kscngscnksMCwwLE1hdGguUEkqMik7IH0gZWxzZSB7IGcucmVjdChjeC1yeCxjeS1yeSxyeCoyLHJ5KjIpOyB9CiAgICAgICAgICBnLmZpbGwoJ2V2ZW5vZGQnKTsKICAgICAgICB9Y2F0Y2goZUYpeyBnLmZpbGxTdHlsZT0ncmdiYSgwLDAsMCwwLjIyKSc7IGcuZmlsbFJlY3QoMCwwLHZ3LHZoKTsgfQogICAgICAgIGcuc2F2ZSgpOwogICAgICAgIGcuc3Ryb2tlU3R5bGU9Y29sOyBnLmxpbmVXaWR0aD02OwogICAgICAgIGcuYmVnaW5QYXRoKCk7IGlmKGcuZWxsaXBzZSl7IGcuZWxsaXBzZShjeCxjeSxyeCxyeSwwLDAsTWF0aC5QSSoyKTsgfSBlbHNlIHsgZy5zdHJva2VSZWN0KGN4LXJ4LGN5LXJ5LHJ4KjIscnkqMik7IH0KICAgICAgICBnLnN0cm9rZSgpOwogICAgICAgIGcucmVzdG9yZSgpOwogICAgICAgIGlmKGluZm8mJmluZm8uY2FqYSYmaW5mby5jYWphLnc+NCl7CiAgICAgICAgICBnLnN0cm9rZVN0eWxlPShlc3RhZG89PT0nb2snKT8nIzNmYjk1MCc6JyNlM2IzNDEnOyBnLmxpbmVXaWR0aD0zOwogICAgICAgICAgZy5zdHJva2VSZWN0KGluZm8uY2FqYS54LGluZm8uY2FqYS55LGluZm8uY2FqYS53LGluZm8uY2FqYS5oKTsKICAgICAgICB9CiAgICAgICAgdmFyIHByb2c9KHN0JiZzdC5hdXRvKT9NYXRoLm1pbigxLHN0LmF1dG8vNCk6MDsKICAgICAgICBpZihwcm9nPjApewogICAgICAgICAgZy5zYXZlKCk7IGcuc3Ryb2tlU3R5bGU9JyMzZmI5NTAnOyBnLmxpbmVXaWR0aD04OwogICAgICAgICAgZy5iZWdpblBhdGgoKTsKICAgICAgICAgIGcuYXJjKGN4LGN5LE1hdGgubWF4KHJ4LHJ5KSsxNiwtTWF0aC5QSS8yLC1NYXRoLlBJLzIrcHJvZypNYXRoLlBJKjIpOwogICAgICAgICAgZy5zdHJva2UoKTsgZy5yZXN0b3JlKCk7CiAgICAgICAgfQogICAgICAgIGlmKG51bWVybz4wKXsKICAgICAgICAgIGcuc2F2ZSgpOwogICAgICAgICAgZy5mb250PSdib2xkIDExMHB4IHNhbnMtc2VyaWYnOyBnLnRleHRBbGlnbj0nY2VudGVyJzsgZy50ZXh0QmFzZWxpbmU9J21pZGRsZSc7CiAgICAgICAgICBnLmxpbmVXaWR0aD0xMDsgZy5zdHJva2VTdHlsZT0ncmdiYSgwLDAsMCwwLjU1KSc7CiAgICAgICAgICBnLnN0cm9rZVRleHQoU3RyaW5nKG51bWVybyksdncvMix2aC8yKTsKICAgICAgICAgIGcuZmlsbFN0eWxlPScjM2ZiOTUwJzsgZy5maWxsVGV4dChTdHJpbmcobnVtZXJvKSx2dy8yLHZoLzIpOwogICAgICAgICAgZy5yZXN0b3JlKCk7CiAgICAgICAgfQogICAgICB9Y2F0Y2goZSl7fQogICAgfTsKICAgIHZhciB1bHRpbW89Jyc7CiAgICB2YXIgYXZpc2FyPWZ1bmN0aW9uKGNvZGUsdHh0LGNvbG9yKXsgaWYoY29kZSE9PXVsdGltbyl7IHVsdGltbz1jb2RlOyBtc2coc3RJZCx0eHQsY29sb3IpOyB9IH07CiAgICBpZihwc0lkPT09JzQnKXsKICAgICAgcGludGFyT3ZhbG8oJycsMCxudWxsKTsKICAgICAgYXZpc2FyKCdpbmknLCdQb24gdHUgY2FyYSBkZW50cm8gZGVsIE9WQUxPLiBMYSBjYXB0dXJhIGVzIEFVVE9NQVRJQ0EgY3VhbmRvIHRvZG8gZXN0ZSBjb3JyZWN0by4nLCcjYTYwJyk7CiAgICAgIGlmKHN0Lml2KXsgdHJ5eyBjbGVhckludGVydmFsKHN0Lml2KTsgfWNhdGNoKGUpe30gfQogICAgICBzdC5pdj1zZXRJbnRlcnZhbChmdW5jdGlvbigpewogICAgICAgIHRyeXsKICAgICAgICAgIGlmKCFzdHJlYW1zW3BzSWRdKXsgcmV0dXJuOyB9CiAgICAgICAgICBidXNjYXJDYXJhVml2YSh2LGZ1bmN0aW9uKGluZm8pewogICAgICAgICAgICB0cnl7CiAgICAgICAgICAgICAgRVNULmNhcmFWaXZhPWluZm87CiAgICAgICAgICAgICAgaWYoIWluZm98fCFpbmZvLnZpc3RhKXsKICAgICAgICAgICAgICAgIHN0LmF1dG89MDsgc3QuY2Q9MDsKICAgICAgICAgICAgICAgIHBpbnRhck92YWxvKCdjYXJhJywwLGluZm98fG51bGwpOwogICAgICAgICAgICAgICAgYXZpc2FyKChpbmZvJiZpbmZvLmNvZCl8fCdub2RldCcsKGluZm8mJmluZm8ubW90aXZvKXx8J0J1c2NhbmRvIHR1IGNhcmEuLi4gYnVlbmEgbHV6LCBzaW4gZ29ycmEgbmkgbGVudGVzIG9zY3Vyb3MuJywnI2E2MCcpOwogICAgICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgICAgIH0KICAgICAgICAgICAgICB2YXIgbnVtZXJvPTA7CiAgICAgICAgICAgICAgaWYoaW5mby5vayl7IHN0LmF1dG89KHN0LmF1dG98fDApKzE7IH0gZWxzZSB7IHN0LmF1dG89MDsgc3QuY2Q9MDsgfQogICAgICAgICAgICAgIGlmKHN0LmF1dG8+PTQpewogICAgICAgICAgICAgICAgc3QuY2Q9KHN0LmNkfHwwKSsxOwogICAgICAgICAgICAgICAgbnVtZXJvPU1hdGgubWF4KDEsNC1zdC5jZCk7CiAgICAgICAgICAgICAgICBwaW50YXJPdmFsbygnb2snLG51bWVybyxpbmZvKTsKICAgICAgICAgICAgICAgIGF2aXNhcignY2QnK251bWVybywnQ2FwdHVyYW5kbyBlbiAnK251bWVybysnLi4uIG5vIHRlIG11ZXZhcy4nLCcjMDgwJyk7CiAgICAgICAgICAgICAgICBpZihzdC5jZD49NCYmIXN0LmF1dG9IZWNobyl7CiAgICAgICAgICAgICAgICAgIHN0LmF1dG9IZWNobz10cnVlOyB2aWJyYXIoKTsKICAgICAgICAgICAgICAgICAgcHJvY2VzYXJTZWxmaWUoKTsKICAgICAgICAgICAgICAgIH0KICAgICAgICAgICAgICAgIHJldHVybjsKICAgICAgICAgICAgICB9CiAgICAgICAgICAgICAgcGludGFyT3ZhbG8oaW5mby5vaz8nb2snOidjYXJhJywwLGluZm8pOwogICAgICAgICAgICAgIGF2aXNhcihpbmZvLm9rPydwcmUnOmluZm8uY29kLCBpbmZvLm1vdGl2bywgaW5mby5vaz8nIzA4MCc6JyNhNjAnKTsKICAgICAgICAgICAgfWNhdGNoKGUzKXt9CiAgICAgICAgICB9KTsKICAgICAgICB9Y2F0Y2goZSl7fQogICAgICB9LDQzMCk7CiAgICB9ZWxzZXsKICAgICAgcGludGFyRG9jKG51bGwsJycpOwogICAgICBhdmlzYXIoJ2luaScsJ0J1c2NhbmRvIGVsIGRvY3VtZW50by4uLiBwb25sbyBzb2JyZSBmb25kbyBPU0NVUk8sIHNpbiBicmlsbG8uIExhcyA0IGVzcXVpbmFzIHNlIG1hcmNhbiBzb2xhcy4nLCcjYTYwJyk7CiAgICAgIGlmKHN0Lml2KXsgdHJ5eyBjbGVhckludGVydmFsKHN0Lml2KTsgfWNhdGNoKGUpe30gfQogICAgICBzdC5pdj1zZXRJbnRlcnZhbChmdW5jdGlvbigpewogICAgICAgIHRyeXsKICAgICAgICAgIGlmKCFzdHJlYW1zW3BzSWRdKXsgcmV0dXJuOyB9CiAgICAgICAgICB2YXIgcT1kZXRlY3RhckRvY1F1YWQodik7CiAgICAgICAgICB2YXIgZXN0PSdtYWwnLCBjb2Q9J25vbmUnLCB0eHQ9J0J1c2NhbmRvIGVsIGRvY3VtZW50by4uLiBwb25sbyBzb2JyZSBmb25kbyBPU0NVUk8sIGxsZW5hbmRvIGVsIG1hcmNvLCBzaW4gYnJpbGxvLicsIGNvbD0nI2E2MCcsIHF1YWQ9bnVsbCwgbnVtZXJvPTA7CiAgICAgICAgICBpZihxJiZxLmxsZW5vKXsKICAgICAgICAgICAgdmFyIGIxPXEubHV6Pj00OCwgYjI9cS5uaXRvPj0zNCwgYjM9KHEuYmxhbmNvPT1udWxsKXx8KHEuYmxhbmNvPD0wLjIyKTsKICAgICAgICAgICAgc3QuYXV0bz0wOwogICAgICAgICAgICBpZighYjEpeyBzdC5jZD0wOyBlc3Q9J21hbCc7IGNvZD0nbHV6JzsgdHh0PSdQT0NBIExVWjogYnVzY2EgbWVqb3IgaWx1bWluYWNpb24gbyB1c2EgRWxlZ2lyIGFyY2hpdm8gY29uIHVuYSBmb3RvIGRlIGNlcmNhLic7IGNvbD0nI2MwMCc7IH0KICAgICAgICAgICAgZWxzZSBpZighYjIpeyBzdC5jZD0wOyBlc3Q9J21hbCc7IGNvZD0nbml0byc7IHR4dD0nTm8gc2UgdmUgTklUSURPOiBzb3N0XHUwMEU5biBmaXJtZSwgZXNwZXJhIGVsIGVuZm9xdWUgeSBldml0YSBlbCBicmlsbG8uJzsgY29sPScjYzAwJzsgfQogICAgICAgICAgICBlbHNlIGlmKCFiMyl7IHN0LmNkPTA7IGVzdD0nbWFsJzsgY29kPSdibGEnOyB0eHQ9J0hheSBSRUZMRUpPIGVuIGVsIGRvY3VtZW50bzogaW5jbFx1MDBFRG5hbG8gdW4gcG9jbyBwYXJhIHF1aXRhciBlbCBicmlsbG8uJzsgY29sPScjYzAwJzsgfQogICAgICAgICAgICBlbHNlewogICAgICAgICAgICAgIC8qIGhlcmVkYWRvIHYxNDogc2kgZWwgZG9jdW1lbnRvIGxsZW5hIGVsIGN1YWRybyBjb24gbHV6IHkgbml0aWRleiwKICAgICAgICAgICAgICAgICB0YW1iaWVuIGNhcHR1cmEgU09MTyBjb24gY3VlbnRhIGF0cmFzIChhbnRlcyBvYmxpZ2FiYSBhIHRvY2FyCiAgICAgICAgICAgICAgICAgQ0FQVFVSQVIpLiBNaXNtbyAzLTItMSBxdWUgY3VhbmRvIGhheSA0IGVzcXVpbmFzLiAqLwogICAgICAgICAgICAgIHN0LmNkPShzdC5jZHx8MCkrMTsKICAgICAgICAgICAgICBudW1lcm89TWF0aC5tYXgoMSw0LXN0LmNkKTsKICAgICAgICAgICAgICBlc3Q9J29rJzsgY29kPSdjZCcrbnVtZXJvOyB0eHQ9J0NhcHR1cmFuZG8gZW4gJytudW1lcm8rJy4uLiBubyB0ZSBtdWV2YXMuJzsgY29sPScjMDgwJzsKICAgICAgICAgICAgICBpZihzdC5jZD49NCYmIXN0LmF1dG9IZWNobyl7CiAgICAgICAgICAgICAgICBzdC5hdXRvSGVjaG89dHJ1ZTsgdmlicmFyKCk7CiAgICAgICAgICAgICAgICBtYW5lamFyKHBzSWQ9PT0nMic/J2JDYXBGJzonYkNhcEEnKTsKICAgICAgICAgICAgICAgIHJldHVybjsKICAgICAgICAgICAgICB9CiAgICAgICAgICAgIH0KICAgICAgICAgICAgcGludGFyRG9jKG51bGwsIGVzdCk7CiAgICAgICAgICB9ZWxzZSBpZihxKXsKICAgICAgICAgICAgcXVhZD1xOwogICAgICAgICAgICBzdC5oaXN0LnB1c2gocXVhZCk7IHN0LnVsdFF1YWQ9cXVhZDsgc3QudWx0UXVhZFQ9RGF0ZS5ub3coKTsKICAgICAgICAgICAgaWYoc3QuaGlzdC5sZW5ndGg+Nyl7IHN0Lmhpc3Quc2hpZnQoKTsgfQogICAgICAgICAgICB2YXIgYzE9cS5sdXo+PTQ4LCBjMj1xLm5pdG8+PTM0LCBjMz0ocS5ibGFuY289PW51bGwpfHwocS5ibGFuY288PTAuMjApOwogICAgICAgICAgICBzdC5hdXRvPTA7IHN0LmNkPTA7CiAgICAgICAgICAgIGlmKHEuZGVzY2FydGFkbz09PSdwZXF1ZW5vJyl7IGVzdD0nbWFsJzsgY29kPSdmYXInOyB0eHQ9J0FDRVJDQVRFOiBlbCBkb2N1bWVudG8gc2UgdmUgbXV5IHBlcXVlXHUwMEYxbyBlbiBsYSBmb3RvLic7IGNvbD0nI2E2MCc7IH0KICAgICAgICAgICAgZWxzZSBpZihxLmRlc2NhcnRhZG89PT0nZm9ybWEnKXsgZXN0PSdtYWwnOyBjb2Q9J2Zvcm1hJzsgdHh0PSdObyB2ZW8gYmllbiBsYXMgNCBlc3F1aW5hczogYWNcdTAwRTlyY2F0ZSB5IHVzYSB1biBmb25kbyBvc2N1cm8uJzsgY29sPScjYTYwJzsgfQogICAgICAgICAgICBlbHNlIGlmKCFjMSl7IGVzdD0nbWFsJzsgY29kPSdsdXonOyB0eHQ9J1BPQ0EgTFVaOiBidXNjYSBtZWpvciBpbHVtaW5hY2lvbiBvIHVzYSBFbGVnaXIgYXJjaGl2byBjb24gdW5hIGZvdG8gZGUgY2VyY2EuJzsgY29sPScjYzAwJzsgfQogICAgICAgICAgICBlbHNlIGlmKCFjMil7IGVzdD0nbWFsJzsgY29kPSduaXRvJzsgdHh0PSdObyBzZSB2ZSBOSVRJRE86IHNvc3RcdTAwRTluIGZpcm1lLCBlc3BlcmEgZWwgZW5mb3F1ZSB5IGV2aXRhIGVsIGJyaWxsby4nOyBjb2w9JyNjMDAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYoIWMzKXsgZXN0PSdtYWwnOyBjb2Q9J2JsYSc7IHR4dD0nSGF5IFJFRkxFSk8gZW4gZWwgZG9jdW1lbnRvOiBpbmNsXHUwMEVEbmFsbyB1biBwb2NvIHBhcmEgcXVpdGFyIGVsIGJyaWxsby4nOyBjb2w9JyNjMDAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYocXVhZEVzdGFibGUoc3QuaGlzdCkpewogICAgICAgICAgICAgIHN0LmF1dG89MTsKICAgICAgICAgICAgICBzdC5jZD0oc3QuY2R8fDApKzE7CiAgICAgICAgICAgICAgbnVtZXJvPU1hdGgubWF4KDEsNC1zdC5jZCk7CiAgICAgICAgICAgICAgZXN0PSdvayc7IGNvZD0nY2QnK251bWVybzsgdHh0PSdDYXB0dXJhbmRvIGVuICcrbnVtZXJvKycuLi4gbm8gdGUgbXVldmFzLic7IGNvbD0nIzA4MCc7CiAgICAgICAgICAgICAgaWYoc3QuY2Q+PTQmJiFzdC5hdXRvSGVjaG8pewogICAgICAgICAgICAgICAgc3QuYXV0b0hlY2hvPXRydWU7IHZpYnJhcigpOwogICAgICAgICAgICAgICAgbWFuZWphcihwc0lkPT09JzInPydiQ2FwRic6J2JDYXBBJyk7CiAgICAgICAgICAgICAgICByZXR1cm47CiAgICAgICAgICAgICAgfQogICAgICAgICAgICB9ZWxzZXsKICAgICAgICAgICAgICBlc3Q9J2Nhc2knOyBjb2Q9J2VzcGVyYSc7IHR4dD0nRG9jdW1lbnRvIGRldGVjdGFkby4gU29zdGVubG8gcXVpZXRvIHBhcmEgY2FwdHVyYXIgc29sby4uLic7IGNvbD0nIzA4MCc7CiAgICAgICAgICAgIH0KICAgICAgICAgICAgcGludGFyUXVhZChxdWFkLCBlc3QsIG51bWVybyk7CiAgICAgICAgICB9ZWxzZXsKICAgICAgICAgICAgc3QuYXV0bz0wOyBzdC5jZD0wOwogICAgICAgICAgICBpZihEYXRlLm5vdygpLXN0LnQ+MTIwMCl7IHN0LmNhamE9bnVsbDsgfQogICAgICAgICAgICB2YXIgY2FqYUY9ZGV0ZWN0YXJEb2NCb3godik7CiAgICAgICAgICAgIGlmKGNhamFGKXsKICAgICAgICAgICAgICBzdC5jYWphPWNhamFGOyBzdC51bHRDYWphPWNhamFGOyBzdC51bHRDYWphVD1EYXRlLm5vdygpOyBzdC50PURhdGUubm93KCk7CiAgICAgICAgICAgICAgZXN0PShjYWphRi5uaXRvJiZjYWphRi5sdXo+PTQ4KT8nY2FzaSc6J21hbCc7CiAgICAgICAgICAgICAgY29kPShlc3Q9PT0nY2FzaScpPydhcHJveCc6J2NhbCc7CiAgICAgICAgICAgICAgdHh0PShlc3Q9PT0nY2FzaScpPydDYXNpOiBzb3N0XHUwMEU5biBxdWlldG8uIENvbiBmb25kbyBvc2N1cm8gbWFyY28gbGFzIDQgZXNxdWluYXMgeSBjYXB0dXJvIHNvbG8uJzonU2UgdmUgZmxvam86IG1cdTAwRTFzIGx1eiwgZmlybWUsIHNpbiBicmlsbG8uJzsKICAgICAgICAgICAgICBjb2w9KGVzdD09PSdjYXNpJyk/JyNhNjAnOicjYzAwJzsKICAgICAgICAgICAgfWVsc2UgaWYoRGF0ZS5ub3coKS1zdC50PjEyMDApewogICAgICAgICAgICAgIGNvZD0nbm9uZSc7IHR4dD0nQnVzY2FuZG8gZWwgZG9jdW1lbnRvLi4uIHBvbmxvIHNvYnJlIGZvbmRvIE9TQ1VSTywgbGxlbmFuZG8gZWwgbWFyY28sIHNpbiBicmlsbG8uJzsKICAgICAgICAgICAgfQogICAgICAgICAgICBwaW50YXJEb2MoY2FqYUZ8fHN0LmNhamF8fG51bGwsIGVzdCk7CiAgICAgICAgICB9CiAgICAgICAgICBhdmlzYXIoY29kLHR4dCxjb2wpOwogICAgICAgIH1jYXRjaChlKXt9CiAgICAgIH0sMzAwKTsKICAgIH0KICAgIGlmKCF2Ll9fenlNYXJjbyl7CiAgICAgIHYuX196eU1hcmNvPTE7CiAgICAgIHYuYWRkRXZlbnRMaXN0ZW5lcigncGxheWluZycsZnVuY3Rpb24oKXsgdHJ5eyBhbGluZWFyT3ZlcmxheShwc0lkLCB2KTsgaWYocHNJZD09PSc0Jyl7IHBpbnRhck92YWxvKCcnLDAsbnVsbCk7IH0gZWxzZSB7IHBpbnRhckRvYyhudWxsLCcnKTsgfSB9Y2F0Y2goZSl7fSB9KTsKICAgICAgdi5hZGRFdmVudExpc3RlbmVyKCdsb2FkZWRtZXRhZGF0YScsZnVuY3Rpb24oKXsgdHJ5eyBhbGluZWFyT3ZlcmxheShwc0lkLCB2KTsgaWYocHNJZD09PSc0Jyl7IHBpbnRhck92YWxvKCcnLDAsbnVsbCk7IH0gZWxzZSB7IHBpbnRhckRvYyhudWxsLCcnKTsgfSB9Y2F0Y2goZSl7fSB9KTsKICAgIH0KICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIGludGVudGFyRW5mb3F1ZShzdCl7CiAgdHJ5ewogICAgdmFyIHRyPShzdCYmc3QuZ2V0VmlkZW9UcmFja3MpP3N0LmdldFZpZGVvVHJhY2tzKClbMF06bnVsbDsKICAgIGlmKCF0cil7IHJldHVybjsgfQogICAgdmFyIGNhcHM9dHIuZ2V0Q2FwYWJpbGl0aWVzP3RyLmdldENhcGFiaWxpdGllcygpOm51bGw7CiAgICBpZihjYXBzJiZjYXBzLmZvY3VzTW9kZSYmY2Fwcy5mb2N1c01vZGUuam9pbiYmY2Fwcy5mb2N1c01vZGUuam9pbignICcpLmluZGV4T2YoJ2NvbnRpbnVvdXMnKT49MCl7CiAgICAgIHZhciBwPXRyLmFwcGx5Q29uc3RyYWludHMoe2FkdmFuY2VkOlt7Zm9jdXNNb2RlOidjb250aW51b3VzJ31dfSk7CiAgICAgIGlmKHAmJnAuY2F0Y2gpeyBwLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH0KICAgIH0KICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIGFicmlyQ2FtKHBzSWQsIGZhY2luZywgc3RJZCwgY2FwSWQpewogIHZhciB2PWZpbmRWaWRlbyhwc0lkKTsKICBpZighdil7IG1zZyhzdElkLCdObyBlbmNvbnRyZSBlbCB2aWRlbyBkZSBsYSBjYW1hcmEgZW4gbGEgcGFnaW5hLicsICcjYzAwJyk7IHJldHVybiBQcm9taXNlLnJlamVjdChuZXcgRXJyb3IoJ3NpbiB2aWRlbycpKTsgfQogIGlmKCFuYXZpZ2F0b3IubWVkaWFEZXZpY2VzIHx8ICFuYXZpZ2F0b3IubWVkaWFEZXZpY2VzLmdldFVzZXJNZWRpYSl7CiAgICBtc2coc3RJZCwnVHUgbmF2ZWdhZG9yIG5vIHBlcm1pdGUgY2FtYXJhLiBVc2EgbGEgb3BjaW9uIGRlIGdhbGVyaWEuJywgJyNjMDAnKTsKICAgIHJldHVybiBQcm9taXNlLnJlamVjdChuZXcgRXJyb3IoJ3NpbiBjYW1hcmEnKSk7CiAgfQogIHBhcmFyQ2FtKHBzSWQpOwogIHZhciB6b25hPSQoJ3Z6JytsZXRyYURlKHBzSWQpKTsKICBpZih6b25hKXsgem9uYS5zdHlsZS5kaXNwbGF5PSdibG9jayc7IH0KICBtc2coc3RJZCwnUGlkaWVuZG8gcGVybWlzbyBkZSBjYW1hcmEuLi4nLCcnKTsKICB2YXIgZG9jWm9uYT0ocHNJZD09PScyJ3x8cHNJZD09PSczJyk7CiAgcmV0dXJuIG5hdmlnYXRvci5tZWRpYURldmljZXMuZ2V0VXNlck1lZGlhKHthdWRpbzpmYWxzZSwgdmlkZW86e2ZhY2luZ01vZGU6ZmFjaW5nLCB3aWR0aDp7aWRlYWw6ZG9jWm9uYT8xOTIwOjEyODB9LCBoZWlnaHQ6e2lkZWFsOmRvY1pvbmE/MTA4MDo3MjB9fX0pLnRoZW4oZnVuY3Rpb24oc3QpewogICAgc3RyZWFtc1twc0lkXT1zdDsKICAgIHYuc3JjT2JqZWN0PXN0OwogICAgdHJ5eyB2LnNldEF0dHJpYnV0ZSgncGxheXNpbmxpbmUnLCdwbGF5c2lubGluZScpOyB9Y2F0Y2goZSl7fQogICAgdi5tdXRlZD10cnVlOwogICAgdHJ5eyB2LnN0eWxlLnRyYW5zZm9ybT0ocHNJZD09PSc0Jyk/J3NjYWxlWCgtMSknOicnOyB9Y2F0Y2goZU0pe30KICAgIGludGVudGFyRW5mb3F1ZShzdCk7CiAgICB2YXIgcD12LnBsYXkoKTsgaWYocCYmcC5jYXRjaCl7IHAuY2F0Y2goZnVuY3Rpb24oKXt9KTsgfQogICAgZXN0aWxvQ2hpY28odik7CiAgICB2YXIgY2FwPSQoY2FwSWQpOwogICAgaWYoY2FwKXsgY2FwLmRpc2FibGVkPWZhbHNlOyBjYXAuc3R5bGUuZGlzcGxheT0nJzsgY2FwLnN0eWxlLnZpc2liaWxpdHk9J3Zpc2libGUnOyBjYXAuc3R5bGUucG9pbnRlckV2ZW50cz0nYXV0byc7IGNhcC5zdHlsZS5wb3NpdGlvbj1jYXAuc3R5bGUucG9zaXRpb258fCdyZWxhdGl2ZSc7IGNhcC5zdHlsZS56SW5kZXg9Jzk5OTknOyB9CiAgICB2YXIgT1Y9eycyJzonb3ZGJywnMyc6J292QScsJzQnOidvdlMnfTsKICAgIHZhciBvdj0kKE9WW3BzSWRdKTsKICAgIGlmKG92KXsgb3Yuc3R5bGUucG9pbnRlckV2ZW50cz0nbm9uZSc7IH0KICAgIHZhciB6b25hPSQoJ3Z6JytsZXRyYURlKHBzSWQpKTsKICAgIGlmKHpvbmEpeyB6b25hLnN0eWxlLnBvc2l0aW9uPSdyZWxhdGl2ZSc7IH0KICAgIGVubWFyY2FyVmVyZGUocHNJZCwgdik7CiAgICBhbGluZWFyT3ZlcmxheShwc0lkLCB2KTsKICAgIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsgdHJ5eyBhbGluZWFyT3ZlcmxheShwc0lkLCB2KTsgfWNhdGNoKGUpe30gfSwyNTApOwogICAgdmFyIHE9KHBzSWQ9PT0nNCcpOwogICAgbXNnKHN0SWQsIHE/J0NhbWFyYSBsaXN0YS4gUG9uIHR1IGNhcmEgZW4gZWwgT1ZBTE86IHNlIGNhcHR1cmEgU09MTyBjdWFuZG8gdG9kbyBlc3RlIGNvcnJlY3RvLic6J0NhbWFyYSBsaXN0YS4gQnVzY28gbGFzIDQgZXNxdWluYXMgZGVsIGRvY3VtZW50bzogc29zdFx1MDBFOW5sbyBxdWlldG8geSBjYXB0dXJvIHNvbG8uJywnIzA4MCcpOwogICAgcmV0dXJuIHRydWU7CiAgfSkuY2F0Y2goZnVuY3Rpb24oZSl7CiAgICBpZih6b25hKXsgdHJ5eyB6b25hLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9Y2F0Y2goZTIpe30gfQogICAgbXNnKHN0SWQsJ05vIHB1ZGUgYWJyaXIgbGEgY2FtYXJhICgnKyhlJiZlLm5hbWU/ZS5uYW1lOidlcnJvcicpKycpLiBQdWVkZXMgdXNhciBsYSBnYWxlcmlhIG8gcmV2aXNhIGVsIHBlcm1pc28uJywnI2MwMCcpOwogICAgdGhyb3cgZTsKICB9KTsKfQpmdW5jdGlvbiBwYXJhckNhbShwc0lkKXsKICB2YXIgc3Q9c3RyZWFtc1twc0lkXTsKICBpZihzdCl7CiAgICB0cnl7IHN0LmdldFRyYWNrcygpLmZvckVhY2goZnVuY3Rpb24odCl7IHRyeXsgdC5zdG9wKCk7IH1jYXRjaChlKXt9IH0pOyB9Y2F0Y2goZSl7fQogIH0KICBzdHJlYW1zW3BzSWRdPW51bGw7CiAgdHJ5ewogICAgdmFyIHZ2PWZpbmRWaWRlbyhwc0lkKTsKICAgIGlmKHZ2KXsgdnYuc3R5bGUudHJhbnNmb3JtPScnOyB9CiAgfWNhdGNoKGVUKXt9CiAgdHJ5ewogICAgdmFyIEQ9enlEZXQoKSwgc3REPURbcHNJZF07CiAgICBpZihzdEQmJnN0RC5pdil7IGNsZWFySW50ZXJ2YWwoc3RELml2KTsgc3RELml2PW51bGw7IH0KICAgIGlmKHBzSWQ9PT0nNCcpeyBFU1QuY2FyYVZpdmE9bnVsbDsgfQogIH1jYXRjaChlKXt9CiAgdHJ5ewogICAgdmFyIHpvbmE9JCgndnonK2xldHJhRGUocHNJZCkpOwogICAgaWYoem9uYSl7IHpvbmEuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH0KICAgIHZhciBPVj17JzInOidvdkYnLCczJzonb3ZBJywnNCc6J292Uyd9OwogICAgdmFyIG92PSQoT1ZbcHNJZF0pOwogICAgaWYob3YpeyB2YXIgZz1vdi5nZXRDb250ZXh0KCcyZCcpOyBpZihnKXsgZy5jbGVhclJlY3QoMCwwLG92LndpZHRofHwxLG92LmhlaWdodHx8MSk7IH0gfQogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gcGFyYXJUb2RhcygpeyB2YXIgazsgZm9yKGsgaW4gc3RyZWFtcyl7IHBhcmFyQ2FtKGspOyB9IH0KZnVuY3Rpb24gY2FwdHVyYXJWaWRlbyhwc0lkLCBtYXhEaW0pewogIHZhciB2PWZpbmRWaWRlbyhwc0lkKTsKICBpZighdiB8fCAhdi52aWRlb1dpZHRoIHx8ICFzdHJlYW1zW3BzSWRdKXsgcmV0dXJuIG51bGw7IH0KICB2YXIgdz12LnZpZGVvV2lkdGgsIGg9di52aWRlb0hlaWdodDsKICB2YXIgc2M9TWF0aC5taW4oMSwobWF4RGltfHwxMDI0KS9NYXRoLm1heCh3LGgpKTsKICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICBjLndpZHRoPU1hdGgucm91bmQodypzYyk7IGMuaGVpZ2h0PU1hdGgucm91bmQoaCpzYyk7CiAgYy5nZXRDb250ZXh0KCcyZCcpLmRyYXdJbWFnZSh2LDAsMCxjLndpZHRoLGMuaGVpZ2h0KTsKICB2YXIgZD1jLnRvRGF0YVVSTCgnaW1hZ2UvanBlZycsMC45KTsKICBwYXJhckNhbShwc0lkKTsKICByZXR1cm4gZDsKfQpmdW5jdGlvbiBkb3duc2NhbGUoZGF0YVVybCwgbWF4RGltKXsKICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsKICAgIHZhciBpbT1uZXcgSW1hZ2UoKTsKICAgIGltLm9ubG9hZD1mdW5jdGlvbigpewogICAgICB2YXIgc2M9TWF0aC5taW4oMSwobWF4RGltfHwxMDI0KS9NYXRoLm1heChpbS53aWR0aCxpbS5oZWlnaHQpKTsKICAgICAgdmFyIGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7CiAgICAgIGMud2lkdGg9TWF0aC5tYXgoMSxNYXRoLnJvdW5kKGltLndpZHRoKnNjKSk7CiAgICAgIGMuaGVpZ2h0PU1hdGgubWF4KDEsTWF0aC5yb3VuZChpbS5oZWlnaHQqc2MpKTsKICAgICAgYy5nZXRDb250ZXh0KCcyZCcpLmRyYXdJbWFnZShpbSwwLDAsYy53aWR0aCxjLmhlaWdodCk7CiAgICAgIHJlcyhjLnRvRGF0YVVSTCgnaW1hZ2UvanBlZycsMC45KSk7CiAgICB9OwogICAgaW0ub25lcnJvcj1mdW5jdGlvbigpeyByZXMoZGF0YVVybCk7IH07CiAgICBpbS5zcmM9ZGF0YVVybDsKICB9KTsKfQpmdW5jdGlvbiBhcmNoaXZvQURhdG9zKGZpbGUpewogIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMscmVqKXsKICAgIHZhciBmcj1uZXcgRmlsZVJlYWRlcigpOwogICAgZnIub25sb2FkPWZ1bmN0aW9uKCl7IHJlcyhTdHJpbmcoZnIucmVzdWx0KSk7IH07CiAgICBmci5vbmVycm9yPWZ1bmN0aW9uKCl7IHJlaihuZXcgRXJyb3IoJ25vIHB1ZGUgbGVlciBlbCBhcmNoaXZvJykpOyB9OwogICAgZnIucmVhZEFzRGF0YVVSTChmaWxlKTsKICB9KTsKfQoKLyogPT09PT09PT09PT09PT09PT0gT0NSIGNvbiBjYWNoZSArIG1lam9yYSBkZSBpbWFnZW4gPT09PT09PT09PT09PT09PT0gKi8KdmFyIGNhY2hlT2NyPXt9LCBwcm9tZXNhV29ya2VyPW51bGw7CmZ1bmN0aW9uIGFicmlyV29ya2VyT2NyKCl7CiAgaWYocHJvbWVzYVdvcmtlcil7IHJldHVybiBwcm9tZXNhV29ya2VyOyB9CiAgdHJ5ewogICAgaWYodHlwZW9mIFRlc3NlcmFjdCE9PSd1bmRlZmluZWQnICYmIFRlc3NlcmFjdC5jcmVhdGVXb3JrZXIpewogICAgICBwcm9tZXNhV29ya2VyPVRlc3NlcmFjdC5jcmVhdGVXb3JrZXIoJ3NwYStlbmcnLDEse2xvZ2dlcjpmdW5jdGlvbigpe319KS50aGVuKGZ1bmN0aW9uKHcpeyByZXR1cm4gdzsgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmV0dXJuIG51bGw7IH0pOwogICAgICByZXR1cm4gcHJvbWVzYVdvcmtlcjsKICAgIH0KICB9Y2F0Y2goZSl7fQogIHByb21lc2FXb3JrZXI9UHJvbWlzZS5yZXNvbHZlKG51bGwpOwogIHJldHVybiBwcm9tZXNhV29ya2VyOwp9CmZ1bmN0aW9uIG1lam9yYXJJbWFnZW4oZGF0YVVybCl7CiAgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7CiAgICB2YXIgaW09bmV3IEltYWdlKCk7CiAgICBpbS5vbmxvYWQ9ZnVuY3Rpb24oKXsKICAgICAgdHJ5ewogICAgICAgIHZhciBhbmNobz1pbS53aWR0aCwgYWx0bz1pbS5oZWlnaHQ7CiAgICAgICAgdmFyIGVzYzE9TWF0aC5taW4oMywgTWF0aC5tYXgoMSwgMTQwMC9NYXRoLm1heCgxLE1hdGgubWluKGFuY2hvLGFsdG8pKSkpOwogICAgICAgIHZhciBlc2MyPU1hdGgubWluKDEsIDI2MDAvTWF0aC5tYXgoMSxNYXRoLm1heChhbmNobyxhbHRvKSkpOwogICAgICAgIHZhciBzYz1NYXRoLm1pbihlc2MxLGVzYzIpOwogICAgICAgIGlmKCEoc2M+MCkpeyBzYz0xOyB9CiAgICAgICAgdmFyIGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7CiAgICAgICAgYy53aWR0aD1NYXRoLm1heCgxLE1hdGgucm91bmQoYW5jaG8qc2MpKTsKICAgICAgICBjLmhlaWdodD1NYXRoLm1heCgxLE1hdGgucm91bmQoYWx0bypzYykpOwogICAgICAgIHZhciBnPWMuZ2V0Q29udGV4dCgnMmQnKTsKICAgICAgICBpZighZyl7IHJlcyhudWxsKTsgcmV0dXJuOyB9CiAgICAgICAgZy5pbWFnZVNtb290aGluZ0VuYWJsZWQ9dHJ1ZTsKICAgICAgICB0cnl7IGcuaW1hZ2VTbW9vdGhpbmdRdWFsaXR5PSdoaWdoJzsgfWNhdGNoKGUyKXt9CiAgICAgICAgZy5kcmF3SW1hZ2UoaW0sMCwwLGMud2lkdGgsYy5oZWlnaHQpOwogICAgICAgIHZhciBpZGQ9Zy5nZXRJbWFnZURhdGEoMCwwLGMud2lkdGgsYy5oZWlnaHQpLCBwPWlkZC5kYXRhLCBuPXAubGVuZ3RoLzQ7CiAgICAgICAgdmFyIGhpc3Q9bmV3IEludDMyQXJyYXkoMjU2KSwgaSwgaywgc3VtPTA7CiAgICAgICAgZm9yKGk9MDtpPG47aSsrKXsgdmFyIHI9cFtpKjRdLCBnZz1wW2kqNCsxXSwgYj1wW2kqNCsyXTsgdmFyIGw9KHIqMytnZyo0K2IpPj4zOyBwW2kqNF09bDsgcFtpKjQrMV09bDsgcFtpKjQrMl09bDsgaGlzdFtsXSsrOyBzdW0rPWw7IH0KICAgICAgICB2YXIgbWVkaWE9c3VtL01hdGgubWF4KDEsbik7CiAgICAgICAgdmFyIGdhbj0xOwogICAgICAgIGlmKG1lZGlhPDgwKXsgZ2FuPTAuNTg7IH0KICAgICAgICBlbHNlIGlmKG1lZGlhPDEwNSl7IGdhbj0wLjcyOyB9CiAgICAgICAgZWxzZSBpZihtZWRpYT4xODUpeyBnYW49MS4yNTsgfQogICAgICAgIHZhciBhY2M9MCwgbG89MCwgaGk9MjU1OwogICAgICAgIGZvcihrPTA7azwyNTY7aysrKXsgYWNjKz1oaXN0W2tdOyBpZihhY2M+PW4qMC4wMil7IGxvPWs7IGJyZWFrOyB9IH0KICAgICAgICBhY2M9MDsKICAgICAgICBmb3Ioaz0yNTU7az49MDtrLS0peyBhY2MrPWhpc3Rba107IGlmKGFjYz49biowLjAyKXsgaGk9azsgYnJlYWs7IH0gfQogICAgICAgIHZhciBlc2M9KGhpPmxvKT8yNTUvKGhpLWxvKToxOwogICAgICAgIGZvcihpPTA7aTxuO2krKyl7IHZhciB2PShwW2kqNF0tbG8pKmVzYzsgdj12PDA/MDoodj4yNTU/MjU1OnYpOyB2PTI1NSpNYXRoLnBvdyh2LzI1NSxnYW4pOyBwW2kqNF09djsgcFtpKjQrMV09djsgcFtpKjQrMl09djsgfQogICAgICAgIHZhciB0bXA9bmV3IFVpbnQ4QXJyYXkobik7CiAgICAgICAgZm9yKGk9MDtpPG47aSsrKXsgdG1wW2ldPXBbaSo0XTsgfQogICAgICAgIHZhciBhbmNobzI9Yy53aWR0aDsKICAgICAgICBmb3IodmFyIHk9MTt5PGMuaGVpZ2h0LTE7eSsrKXsKICAgICAgICAgIGZvcih2YXIgeD0xO3g8YW5jaG8yLTE7eCsrKXsKICAgICAgICAgICAgdmFyIHE9eSphbmNobzIreDsKICAgICAgICAgICAgdmFyIGJsPSh0bXBbcV0rdG1wW3EtMV0rdG1wW3ErMV0rdG1wW3EtYW5jaG8yXSt0bXBbcSthbmNobzJdKSowLjI7CiAgICAgICAgICAgIHZhciB2Mj10bXBbcV0rMC40Kih0bXBbcV0tYmwpOwogICAgICAgICAgICB2Mj12MjwwPzA6KHYyPjI1NT8yNTU6djIpOwogICAgICAgICAgICB2YXIgdzM9cSo0OyBwW3czXT12MjsgcFt3MysxXT12MjsgcFt3MysyXT12MjsKICAgICAgICAgIH0KICAgICAgICB9CiAgICAgICAgZy5wdXRJbWFnZURhdGEoaWRkLDAsMCk7CiAgICAgICAgcmVzKGMpOwogICAgICB9Y2F0Y2goZSl7IHJlcyhudWxsKTsgfQogICAgfTsKICAgIGltLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVzKG51bGwpOyB9OwogICAgaW0uc3JjPWRhdGFVcmw7CiAgfSk7Cn0KZnVuY3Rpb24gcmVjb3J0ZVN1cGVyaW9yKGN2KXsKICB0cnl7CiAgICB2YXIgdz1jdi53aWR0aCwgaD1NYXRoLnJvdW5kKGN2LmhlaWdodCowLjYyKTsKICAgIGlmKHc8NDB8fGg8NDApeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7CiAgICBjLndpZHRoPXc7IGMuaGVpZ2h0PWg7CiAgICBjLmdldENvbnRleHQoJzJkJykuZHJhd0ltYWdlKGN2LDAsMCx3LGgsMCwwLHcsaCk7CiAgICByZXR1cm4gYzsKICB9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9Cn0KZnVuY3Rpb24gcmVjb25vY2VyQ29uKGltZywgcHNtKXsKICByZXR1cm4gYWJyaXJXb3JrZXJPY3IoKS50aGVuKGZ1bmN0aW9uKHcpewogICAgZnVuY3Rpb24gY29uVGVzcygpewogICAgICByZXR1cm4gVGVzc2VyYWN0LnJlY29nbml6ZShpbWcsJ3NwYStlbmcnLHtsb2dnZXI6ZnVuY3Rpb24oKXt9fSkudGhlbihmdW5jdGlvbihyKXsgcmV0dXJuIChyJiZyLmRhdGEmJnIuZGF0YS50ZXh0KT9yLmRhdGEudGV4dDonJzsgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmV0dXJuICcnOyB9KTsKICAgIH0KICAgIGlmKCEodyYmdy5yZWNvZ25pemUpKXsgcmV0dXJuIGNvblRlc3MoKTsgfQogICAgdmFyIHByZT0ody5zZXRQYXJhbWV0ZXJzJiZwc20pP3cuc2V0UGFyYW1ldGVycyh7dGVzc2VkaXRfcGFnZXNlZ19tb2RlOlN0cmluZyhwc20pfSk6UHJvbWlzZS5yZXNvbHZlKCk7CiAgICByZXR1cm4gcHJlLnRoZW4oZnVuY3Rpb24oKXsgcmV0dXJuIHcucmVjb2duaXplKGltZyk7IH0pLnRoZW4oZnVuY3Rpb24ocil7CiAgICAgIGlmKHcuc2V0UGFyYW1ldGVycyl7IHRyeXsgdy5zZXRQYXJhbWV0ZXJzKHt0ZXNzZWRpdF9wYWdlc2VnX21vZGU6JzMnfSkuY2F0Y2goZnVuY3Rpb24oKXt9KTsgfWNhdGNoKGUyKXt9IH0KICAgICAgcmV0dXJuIChyJiZyLmRhdGEmJnIuZGF0YS50ZXh0KT9yLmRhdGEudGV4dDonJzsKICAgIH0pLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiBjb25UZXNzKCk7IH0pOwogIH0pLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiAnJzsgfSk7Cn0KZnVuY3Rpb24gb2NyTXVsdGkoZGF0YVVybCwgZXNCdWVubyl7CiAgaWYodHlwZW9mIFRlc3NlcmFjdD09PSd1bmRlZmluZWQnIHx8ICFUZXNzZXJhY3QucmVjb2duaXplKXsKICAgIHJldHVybiBQcm9taXNlLnJlc29sdmUoW10pOwogIH0KICByZXR1cm4gbWVqb3JhckltYWdlbihkYXRhVXJsKS50aGVuKGZ1bmN0aW9uKGN2KXsKICAgIHZhciB2YXJzPVtdOwogICAgaWYoY3YpewogICAgICB2YXJzLnB1c2goe2ltZzpjdiwgcHNtOiczJ30pOwogICAgICB2YXIgcmM9cmVjb3J0ZVN1cGVyaW9yKGN2KTsKICAgICAgaWYocmMpeyB2YXJzLnB1c2goe2ltZzpyYywgcHNtOic2J30pOyB9CiAgICAgIC8qIGhlcmVkYWRvIHYxNDogcGFzZSBkaXNwZXJzbyAoUFNNIDExKSBwYXJhIGxvcyBjYW1wb3Mgc3VlbHRvcyBkZWwKICAgICAgICAgZG9jdW1lbnRvIChOT01CUkVTIC8gQVBFTExJRE9TIHZhbiBlbiBsaW5lYXMgc2VwYXJhZGFzIHkgZWwgcGFzZQogICAgICAgICBub3JtYWwgYSB2ZWNlcyBsb3Mgc2FsdGEpLiBlc0J1ZW5vIGNvcnRhIGFwZW5hcyBhY2llcnRhLiAqLwogICAgICB2YXJzLnB1c2goe2ltZzpjdiwgcHNtOicxMSd9KTsKICAgIH0KICAgIHZhcnMucHVzaCh7aW1nOmRhdGFVcmwsIHBzbTonMyd9KTsKICAgIHZhciBpPTAsIHRleHRvcz1bXTsKICAgIGZ1bmN0aW9uIHBhc28oKXsKICAgICAgaWYoaT49dmFycy5sZW5ndGgpeyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKHRleHRvcyk7IH0KICAgICAgdmFyIHI9dmFyc1tpKytdOwogICAgICByZXR1cm4gcmVjb25vY2VyQ29uKHIuaW1nLCByLnBzbSkudGhlbihmdW5jdGlvbih0KXsKICAgICAgICBpZih0KXsgdGV4dG9zLnB1c2godCk7IH0KICAgICAgICBpZih0JiZlc0J1ZW5vJiZlc0J1ZW5vKHQpKXsgcmV0dXJuIHRleHRvczsgfQogICAgICAgIHJldHVybiBwYXNvKCk7CiAgICAgIH0pLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiBwYXNvKCk7IH0pOwogICAgfQogICAgcmV0dXJuIHBhc28oKTsKICB9KTsKfQpmdW5jdGlvbiBlbGVnaXJUZXh0byh0ZXh0b3MsIGVzY3JpdG8pewogIHZhciBtZWpvcj0nJywgbWo9LTEsIGk7CiAgZm9yKGk9MDtpPHRleHRvcy5sZW5ndGg7aSsrKXsKICAgIHZhciB0PXRleHRvc1tpXXx8JycsIHA9MDsKICAgIGlmKGVzY3JpdG8pewogICAgICB2YXIgbmM9bm9tYnJlQ29pbmNpZGUoZXNjcml0byx0LGZhbHNlKTsKICAgICAgcD0obmMub2s/MTAwMDowKSsobmMucHVudHx8MCkqMTAwOwogICAgfQogICAgcCs9TWF0aC5taW4oNTAsKHQucmVwbGFjZSgvW15BLVowLTldL2dpLCcnKS5sZW5ndGgpLzMwKTsKICAgIGlmKHA+bWopeyBtaj1wOyBtZWpvcj10OyB9CiAgfQogIHJldHVybiBtZWpvcjsKfQpmdW5jdGlvbiBoYWNlck9jcihkYXRhVXJsKXsKICBpZihjYWNoZU9jcltkYXRhVXJsXSl7IHJldHVybiBQcm9taXNlLnJlc29sdmUoY2FjaGVPY3JbZGF0YVVybF0pOyB9CiAgaWYodHlwZW9mIFRlc3NlcmFjdD09PSd1bmRlZmluZWQnIHx8ICFUZXNzZXJhY3QucmVjb2duaXplKXsKICAgIHJldHVybiBQcm9taXNlLnJlamVjdChuZXcgRXJyb3IoJ09DUiBubyBkaXNwb25pYmxlLCByZXZpc2EgdHUgaW50ZXJuZXQnKSk7CiAgfQogIHJldHVybiBvY3JNdWx0aShkYXRhVXJsLCBmdW5jdGlvbih0KXsgcmV0dXJuICh0fHwnJykucmVwbGFjZSgvW15BLVowLTldL2dpLCcnKS5sZW5ndGg+PTM0OyB9KS50aGVuKGZ1bmN0aW9uKHRleHRvcyl7CiAgICB2YXIgdD1lbGVnaXJUZXh0byh0ZXh0b3MsIG51bGwpOwogICAgY2FjaGVPY3JbZGF0YVVybF09dHx8Jyc7CiAgICByZXR1cm4gdHx8Jyc7CiAgfSk7Cn0KZnVuY3Rpb24gb2NyRnJlbnRlKGRhdGFVcmwpewogIGlmKGNhY2hlT2NyW2RhdGFVcmxdKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZShjYWNoZU9jcltkYXRhVXJsXSk7IH0KICByZXR1cm4gb2NyTXVsdGkoZGF0YVVybCwgZnVuY3Rpb24odCl7IHJldHVybiBub21icmVDb2luY2lkZShFU1QuZXNjcml0bywgdHx8JycsIGZhbHNlKS5vazsgfSkudGhlbihmdW5jdGlvbih0ZXh0b3MpewogICAgdmFyIHQ9ZWxlZ2lyVGV4dG8odGV4dG9zLCBFU1QuZXNjcml0byk7CiAgICBpZih0KXsgY2FjaGVPY3JbZGF0YVVybF09dDsgfQogICAgcmV0dXJuIHR8fCcnOwogIH0pOwp9CgovKiA9PT09PT09PT09PT09PT09PSBiaW9tZXRyaWEgZmFjaWFsID09PT09PT09PT09PT09PT09ICovCnZhciBmYWNlUD1udWxsOwpmdW5jdGlvbiBjYXJnYXJGYWNlQXBpKCl7CiAgaWYoZmFjZVApeyByZXR1cm4gZmFjZVA7IH0KICBmYWNlUD1uZXcgUHJvbWlzZShmdW5jdGlvbihyZXMscmVqKXsKICAgIGZ1bmN0aW9uIGxpc3RvKCl7IHJldHVybiBXLmZhY2VhcGkgJiYgVy5mYWNlYXBpLm5ldHMgJiYgVy5mYWNlYXBpLm5ldHMudGlueUZhY2VEZXRlY3RvciAmJiBXLmZhY2VhcGkubmV0cy5mYWNlUmVjb2duaXRpb25OZXQ7IH0KICAgIGZ1bmN0aW9uIG1vZGVsb3MoYmFzZSl7CiAgICAgIHJldHVybiBQcm9taXNlLmFsbChbCiAgICAgICAgVy5mYWNlYXBpLm5ldHMudGlueUZhY2VEZXRlY3Rvci5sb2FkRnJvbVVyaShiYXNlKSwKICAgICAgICBXLmZhY2VhcGkubmV0cy5mYWNlTGFuZG1hcms2OE5ldC5sb2FkRnJvbVVyaShiYXNlKSwKICAgICAgICBXLmZhY2VhcGkubmV0cy5mYWNlUmVjb2duaXRpb25OZXQubG9hZEZyb21VcmkoYmFzZSkKICAgICAgXSk7CiAgICB9CiAgICBmdW5jdGlvbiBpbmljaWFyKCl7CiAgICAgIHZhciBiYXNlPSdodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvZ2gvanVzdGFkdWRld2hvaGFja3MvZmFjZS1hcGkuanNAMC4yMi4yL3dlaWdodHMnOwogICAgICBtb2RlbG9zKGJhc2UpLnRoZW4oZnVuY3Rpb24oKXsgcmVzKCk7IH0sIGZ1bmN0aW9uKCl7IG1vZGVsb3MoJ2h0dHBzOi8vanVzdGFkdWRld2hvaGFja3MuZ2l0aHViLmlvL2ZhY2UtYXBpLmpzL21vZGVscycpLnRoZW4oZnVuY3Rpb24oKXsgcmVzKCk7IH0sIHJlaik7IH0pOwogICAgfQogICAgaWYobGlzdG8oKSl7IGluaWNpYXIoKTsgcmV0dXJuOyB9CiAgICB2YXIgcz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdzY3JpcHQnKTsKICAgIHMuc3JjPSdodHRwczovL2Nkbi5qc2RlbGl2ci5uZXQvbnBtL2ZhY2UtYXBpLmpzQDAuMjIuMi9kaXN0L2ZhY2UtYXBpLm1pbi5qcyc7CiAgICBzLm9ubG9hZD1mdW5jdGlvbigpeyBpZihsaXN0bygpKXsgaW5pY2lhcigpOyB9IGVsc2UgeyByZWoobmV3IEVycm9yKCdmYWNlYXBpIG5vIHF1ZWRvIGxpc3RvJykpOyB9IH07CiAgICBzLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVqKG5ldyBFcnJvcignbm8gc2UgcHVkbyBjYXJnYXIgZWwgdmVyaWZpY2Fkb3IgZmFjaWFsJykpOyB9OwogICAgZG9jdW1lbnQuaGVhZC5hcHBlbmRDaGlsZChzKTsKICB9KTsKICByZXR1cm4gZmFjZVA7Cn0KZnVuY3Rpb24gY29uVGltZW91dChwLCBtcyl7CiAgcmV0dXJuIFByb21pc2UucmFjZShbcCwgbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsgc2V0VGltZW91dChmdW5jdGlvbigpeyByZXMobnVsbCk7IH0sIG1zKTsgfSldKTsKfQpmdW5jdGlvbiBkZXRlY3RhckNhcmFFbihkYXRhVXJsLCBpbnRlbnRvKXsKICByZXR1cm4gY2FyZ2FyRmFjZUFwaSgpLnRoZW4oZnVuY3Rpb24oKXsKICAgIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpewogICAgICB2YXIgaW09bmV3IEltYWdlKCk7CiAgICAgIGltLm9ubG9hZD1mdW5jdGlvbigpewogICAgICAgIHRyeXsKICAgICAgICAgIHZhciB0YW09KGludGVudG89PT0yKT81MTI6MzIwOwogICAgICAgICAgdmFyIG9wdD1uZXcgVy5mYWNlYXBpLlRpbnlGYWNlRGV0ZWN0b3JPcHRpb25zKHtpbnB1dFNpemU6dGFtLCBzY29yZVRocmVzaG9sZDooaW50ZW50bz09PTIpPzAuMzowLjR9KTsKICAgICAgICAgIFcuZmFjZWFwaS5kZXRlY3RTaW5nbGVGYWNlKGltLG9wdCkud2l0aEZhY2VMYW5kbWFya3MoKS53aXRoRmFjZURlc2NyaXB0b3IoKS50aGVuKGZ1bmN0aW9uKHIpewogICAgICAgICAgICBpZihyJiZyLmRldGVjdGlvbil7IHJlcyhyKTsgcmV0dXJuOyB9CiAgICAgICAgICAgIGlmKGludGVudG89PT0yKXsgcmVzKG51bGwpOyByZXR1cm47IH0KICAgICAgICAgICAgcmVzKGRldGVjdGFyQ2FyYUVuKGRhdGFVcmwsKGludGVudG89PT0xKT8yOjEpKTsKICAgICAgICAgIH0pLmNhdGNoKGZ1bmN0aW9uKCl7CiAgICAgICAgICAgIGlmKGludGVudG89PT0yKXsgcmVzKG51bGwpOyByZXR1cm47IH0KICAgICAgICAgICAgcmVzKGRldGVjdGFyQ2FyYUVuKGRhdGFVcmwsKGludGVudG89PT0xKT8yOjEpKTsKICAgICAgICAgIH0pOwogICAgICAgIH1jYXRjaChlKXsgcmVzKG51bGwpOyB9CiAgICAgIH07CiAgICAgIGltLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVzKG51bGwpOyB9OwogICAgICBpbS5zcmM9ZGF0YVVybDsKICAgIH0pOwogIH0pLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiBudWxsOyB9KTsKfQpmdW5jdGlvbiByZWNvcnRlQ2FyYShkYXRhVXJsKXsKICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsKICAgIHZhciBpbT1uZXcgSW1hZ2UoKTsKICAgIGltLm9ubG9hZD1mdW5jdGlvbigpewogICAgICB0cnl7CiAgICAgICAgdmFyIGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7CiAgICAgICAgYy53aWR0aD1NYXRoLm1heCg0MCxNYXRoLnJvdW5kKGltLndpZHRoKjAuNjIpKTsKICAgICAgICBjLmhlaWdodD1NYXRoLm1heCg0MCxNYXRoLnJvdW5kKGltLmhlaWdodCowLjY2KSk7CiAgICAgICAgYy5nZXRDb250ZXh0KCcyZCcpLmRyYXdJbWFnZShpbSwwLDAsaW0ud2lkdGgsTWF0aC5yb3VuZChpbS5oZWlnaHQqMC45KSwwLDAsYy53aWR0aCxjLmhlaWdodCk7CiAgICAgICAgcmVzKGMudG9EYXRhVVJMKCdpbWFnZS9qcGVnJywwLjkpKTsKICAgICAgfWNhdGNoKGUpeyByZXMobnVsbCk7IH0KICAgIH07CiAgICBpbS5vbmVycm9yPWZ1bmN0aW9uKCl7IHJlcyhudWxsKTsgfTsKICAgIGltLnNyYz1kYXRhVXJsOwogIH0pOwp9CmZ1bmN0aW9uIGRldGVjdGFyQ2FyYURvYyhkYXRhVXJsKXsKICBpZighZGF0YVVybCl7IHJldHVybiBQcm9taXNlLnJlc29sdmUobnVsbCk7IH0KICByZXR1cm4gZGV0ZWN0YXJDYXJhRW4oZGF0YVVybCkudGhlbihmdW5jdGlvbihyKXsKICAgIGlmKHImJnIuZGV0ZWN0aW9uKXsgcmV0dXJuIHI7IH0KICAgIHJldHVybiByZWNvcnRlQ2FyYShkYXRhVXJsKS50aGVuKGZ1bmN0aW9uKHJlYyl7CiAgICAgIGlmKCFyZWMpeyByZXR1cm4gbnVsbDsgfQogICAgICByZXR1cm4gZGV0ZWN0YXJDYXJhRW4ocmVjLDEpOwogICAgfSk7CiAgfSk7Cn0KZnVuY3Rpb24gZGlzdEYoYSxiKXsKICB2YXIgcz0wLGk7CiAgZm9yKGk9MDtpPGEubGVuZ3RoO2krKyl7IHZhciBkPWFbaV0tYltpXTsgcys9ZCpkOyB9CiAgcmV0dXJuIE1hdGguc3FydChzKTsKfQoKLyogPT09PT09PT09PT09PT09PT0gZ3VhcmRpYW4gZGUgb3JkZW4gMS0yLTMtNC01ID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHBlcm1pdGlkb0hhc3RhKCl7CiAgdmFyIHA9MTsKICBpZihFU1Qubm9tYnJlT2speyBwPTI7IH0KICBpZihFU1Qubm9tYnJlT2sgJiYgRVNULmZyZW50ZU9rKXsgcD0zOyB9CiAgaWYoRVNULm5vbWJyZU9rICYmIEVTVC5mcmVudGVPayAmJiAoRVNULnJldmVyc29PayB8fCAhRVNULm5lY2VzaXRhUmV2ZXJzbykpeyBwPTQ7IH0KICBpZihFU1Quc2VsZmllT2sgJiYgcD49NCl7IHA9NTsgfQogIHJldHVybiBwOwp9CmZ1bmN0aW9uIG1vc3RyYXJQYXNvKG4pewogIHZhciBpLGVsLCByYj0kKCd6eUJ0blJlcEZvdG8nKTsKICBpZihyYil7IHJiLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgZm9yKGk9MTtpPD01O2krKyl7CiAgICBlbD0kKCdwcycraSk7CiAgICBpZihlbCl7CiAgICAgIGVsLmNsYXNzTmFtZT0ncGFzbycrKGk9PT1uPycgYWN0JzonJyk7CiAgICAgIGVsLnN0eWxlLmRpc3BsYXk9Jyc7CiAgICB9CiAgfQogIHZhciBwcj0kKCdwcm9nJyk7CiAgaWYocHIpeyBwci50ZXh0Q29udGVudD0nUEFTTyAnK24rJyBERSA1JzsgfQogIGlmKEVTVC5wYXNvPj0yICYmIEVTVC5wYXNvPD00ICYmIEVTVC5wYXNvIT09bil7IHRyeXsgcGFyYXJDYW0oRVNULnBhc28pOyB9Y2F0Y2goZSl7fSB9CiAgRVNULnBhc289bjsKICBpZihuPT09NSl7CiAgICB2YXIgYT0kKCdjbGF2ZScpLCBiPSQoJ2NsYXZlMicpOwogICAgaWYoYSl7IGEuZGlzYWJsZWQ9ZmFsc2U7IH0KICAgIGlmKGIpeyBiLmRpc2FibGVkPWZhbHNlOyB9CiAgICB0cnl7IGJhcnJlTWVuc2FqZXMoKTsgfWNhdGNoKGUpe30KICAgIHRyeXsgbGltcGlhTGVnYWRvKCk7IH1jYXRjaChlKXt9CiAgICB0cnl7IHBpbnRhRGlhZygpOyB9Y2F0Y2goZSl7fQogICAgdmFyIHJmPUVTVC5mcmVudGVPaz8nRnJlbnRlIE9LJzonRkFMVEEgRlJFTlRFJzsKICAgIHZhciBycj0oIUVTVC5uZWNlc2l0YVJldmVyc298fEVTVC5yZXZlcnNvT2spPydSZXZlcnNvIE9LJzonRkFMVEEgUkVWRVJTTyc7CiAgICB2YXIgcnM9RVNULnNlbGZpZU9rPydTZWxmaWUgdmVyaWZpY2FkYSc6J1NFTEZJRSBTSU4gVkVSSUZJQ0FSJzsKICAgIHZhciB0b2RvPShFU1QuZnJlbnRlT2smJkVTVC5zZWxmaWVPayYmKCFFU1QubmVjZXNpdGFSZXZlcnNvfHxFU1QucmV2ZXJzb09rKSk7CiAgICBtc2coJ3p5UmVzdW1lbjUnLCdWZXJpZmljYWNpb24gZmluYWw6ICcrcmYrJyB8ICcrcnIrJyB8ICcrcnMrJy4gRXNjcmliZSB0dSBjbGF2ZSAyIHZlY2VzIHkgY3JlYSB0dSBaSUQuJyx0b2RvPycjMDgwJzonI2MwMCcpOwogIH0KICB0cnl7IHZhciBhY3Q9JCgncHMnK24pOyBpZihhY3QmJmFjdC5zY3JvbGxJbnRvVmlldyl7IGFjdC5zY3JvbGxJbnRvVmlldyh7YmVoYXZpb3I6J3Ntb290aCcsYmxvY2s6J3N0YXJ0J30pOyB9IH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gYXZhbnphcihuKXsgbW9zdHJhclBhc28obik7IH0KZnVuY3Rpb24gdmVyaWZpY2FyKCl7CiAgdHJ5ewogICAgdmFyIGFjdD1kb2N1bWVudC5xdWVyeVNlbGVjdG9yKCcucGFzby5hY3QnKTsKICAgIHZhciBybj1hY3QmJmFjdC5pZD9wYXJzZUludChTdHJpbmcoYWN0LmlkKS5yZXBsYWNlKCdwcycsJycpLDEwKTowOwogICAgaWYocm4+PTEmJnJuPD01JiZybiE9PUVTVC5wYXNvKXsgRVNULnBhc289cm47IH0KICB9Y2F0Y2goZSl7fQogIHRyeXsgdmFsaWRhclBhc28xKHRydWUpOyB9Y2F0Y2goZSl7fQogIHZhciBwZXI9cGVybWl0aWRvSGFzdGEoKTsKICBpZihFU1QucGFzbz5wZXIpewogICAgaWYocGVyPT09MSl7IG1zZygnenlHdWFyZGlhJywnUGFyYSBzZWd1aXIsIGVzY3JpYmUgdHUgbm9tYnJlIHkgZWxpZ2UgZWwgdGlwbyBkZSBkb2N1bWVudG8gZW4gZWwgcGFzbyAxLicsJyNhNjAnKTsgfQogICAgZWxzZXsgbXNnKCd6eUd1YXJkaWEnLCdUZSByZWdyZXNvIGFsIHBhc28gJytwZXIrJyBwYXJhIHNlZ3VpciBlbiBvcmRlbi4nLCcjYTYwJyk7IH0KICAgIG1vc3RyYXJQYXNvKHBlcik7CiAgfQogIHZhciBzZWw9JCgndGlwb0RvYycpOwogIGlmKHNlbCAmJiBzZWwudmFsdWUgJiYgL3Bhc2Fwb3J0ZXxwYXNzcG9ydC9pLnRlc3QoKHNlbC5vcHRpb25zJiZzZWwub3B0aW9uc1tzZWwuc2VsZWN0ZWRJbmRleF0mJnNlbC5vcHRpb25zW3NlbC5zZWxlY3RlZEluZGV4XS50ZXh0KXx8JycpKXsKICAgIHZhciBwczM9JCgncHMzJyksIG5yPSQoJ25vdGFSZXYnKTsKICAgIGlmKHBzMyl7IHBzMy5zdHlsZS5kaXNwbGF5PSdub25lJzsgfQogICAgaWYobnIpeyBuci5zdHlsZS5kaXNwbGF5PSdub25lJzsgfQogIH0KfQp2YXIgdnRpbWVyPW51bGw7CmZ1bmN0aW9uIHByb2dyYW1hclZlcmlmaWNhcigpewogIGlmKHZ0aW1lcil7IHJldHVybjsgfQogIHZ0aW1lcj1zZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IHZ0aW1lcj1udWxsOyB0cnl7IHZlcmlmaWNhcigpOyB9Y2F0Y2goZSl7fSB9LDEyMCk7Cn0KdHJ5ewogIG5ldyBNdXRhdGlvbk9ic2VydmVyKHByb2dyYW1hclZlcmlmaWNhcikub2JzZXJ2ZShkb2N1bWVudC5ib2R5LHtjaGlsZExpc3Q6dHJ1ZSxzdWJ0cmVlOnRydWUsYXR0cmlidXRlczp0cnVlLGF0dHJpYnV0ZUZpbHRlcjpbJ3N0eWxlJywnY2xhc3MnLCdoaWRkZW4nLCdkaXNhYmxlZCddfSk7Cn1jYXRjaChlKXt9CgovKiA9PT09PT09PT09PT09PT09PSBwYXNvIDE6IHNvbG8gZm9ybWF0byBkZWwgbm9tYnJlICh2YWxpZGEgU09MTyBhbCBjb250aW51YXIsIG51bmNhIG1pZW50cmFzIGVzY3JpYmVzKSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiB2YWxpZGFyUGFzbzEoc2lsZW5jaW9zbyl7CiAgdmFyIGlucD0kKCdub21icmUnKSwgc2VsPSQoJ3RpcG9Eb2MnKTsKICB2YXIgdj1pbnA/KGlucC52YWx1ZXx8JycpLnRyaW0oKTonJzsKICB2YXIgbGV0cmFzPS9eW0EtWmEtelx1MDBDMVx1MDBDOVx1MDBDRFx1MDBEM1x1MDBEQVx1MDBEQ1x1MDBEMVx1MDBFMVx1MDBFOVx1MDBFRFx1MDBGM1x1MDBGQVx1MDBGQ1x1MDBGMV0rKCBbQS1aYS16XHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxXHUwMEUxXHUwMEU5XHUwMEVEXHUwMEYzXHUwMEZBXHUwMEZDXHUwMEYxXSspKiQvLnRlc3Qodik7CiAgdmFyIG5wPXY/di5zcGxpdCgvXHMrLykubGVuZ3RoOjA7CiAgdmFyIG9rPSh2Lmxlbmd0aD49NSAmJiBsZXRyYXMgJiYgbnA+PTIpOwogIHZhciB0PWNsYXNpZmljYXJUaXBvKCk7CiAgRVNULnRpcG89dC5rOwogIEVTVC5uZWNlc2l0YVJldmVyc289dC5yZXZlcnNvOwogIHZhciB0aXBvT2s9ISEoc2VsICYmIFN0cmluZyhzZWwudmFsdWV8fCcnKS5sZW5ndGg+MCk7CiAgRVNULm5vbWJyZU9rPW9rOwogIEVTVC5lc2NyaXRvPW5vcm0odik7CiAgaWYoc2lsZW5jaW9zbyl7IHJldHVybiBvayYmdGlwb09rOyB9CiAgaWYoaW5wKXsgaW5wLnN0eWxlLmJvcmRlckNvbG9yPW9rPycnOicjYzAwJzsgfQogIHZhciBtbm89Jyc7CiAgaWYoIW9rKXsgbW5vPXY/J0VzY3JpYmUgdHUgbm9tYnJlIHkgdHUgYXBlbGxpZG8gKHNvbG8gbGV0cmFzIHkgZXNwYWNpb3M7IHNpcnZlIGNvbiAxIG8gMiBub21icmVzIHkgMSBvIDIgYXBlbGxpZG9zKS4nOidFc2NyaWJlIHR1IG5vbWJyZSB5IHR1IGFwZWxsaWRvIHBhcmEgY29udGludWFyLic7IH0KICBtc2coJ3p5RXJyTm9tYnJlJyxtbm8sbW5vPycjYzAwJzonJyk7CiAgdmFyIG10aT10aXBvT2s/Jyc6J0VsaWdlIHR1IHRpcG8gZGUgZG9jdW1lbnRvIGVuIGxhIGxpc3RhLic7CiAgbXNnKCd6eUVyclRpcG8nLG10aSxtdGk/JyNjMDAnOicnKTsKICByZXR1cm4gb2smJnRpcG9PazsKfQpmdW5jdGlvbiBsaW1waWFyRXJyb3Jlc1Bhc28xKCl7CiAgdmFyIGUxPSQoJ3p5RXJyTm9tYnJlJyk7IGlmKGUxICYmIGUxLnRleHRDb250ZW50KXsgZTEudGV4dENvbnRlbnQ9Jyc7IGUxLnN0eWxlLmNvbG9yPScnOyB9CiAgdmFyIGUyPSQoJ3p5RXJyVGlwbycpOyBpZihlMiAmJiBlMi50ZXh0Q29udGVudCl7IGUyLnRleHRDb250ZW50PScnOyBlMi5zdHlsZS5jb2xvcj0nJzsgfQogIHZhciBpbnA9JCgnbm9tYnJlJyk7IGlmKGlucCAmJiBpbnAuc3R5bGUuYm9yZGVyQ29sb3IpeyBpbnAuc3R5bGUuYm9yZGVyQ29sb3I9Jyc7IH0KfQpmdW5jdGlvbiByZXNldGVhckRvY3VtZW50bygpewogIEVTVC5mcmVudGVPaz1mYWxzZTsgRVNULnJldmVyc29Paz1mYWxzZTsgRVNULnNlbGZpZU9rPWZhbHNlOyBFU1QuaW50ZW50b3M9NTsgRVNULmNhcmFEb2M9bnVsbDsKfQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyAyOiBmcmVudGUgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gZmFsbG9MZWN0dXJhRnJlbnRlKG0pewogIGJ1c3koZmFsc2UpOwogIG1zZygnc3RGJyxtKycgVG9jYSBDQVBUVVJBUiBkZSBudWV2bywgY29uIGJ1ZW5hIGx1eiB5IHNpbiBicmlsbG8uJywnI2MwMCcpOwp9CmZ1bmN0aW9uIGF2YW56YXJUcmFzRnJlbnRlKCl7CiAgYXZhbnphcihFU1QubmVjZXNpdGFSZXZlcnNvPzM6NCk7CiAgaWYoRVNULm5lY2VzaXRhUmV2ZXJzbyl7CiAgICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IHRyeXsgYWJyaXJDYW0oJzMnLCdlbnZpcm9ubWVudCcsJ3N0QScsJ2JDYXBBJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgfWNhdGNoKGUpe30gfSw1MDApOwogIH0KfQpmdW5jdGlvbiBhY2VwdGFyRnJlbnRlQ29uZmlybWFkbyh0ZXh0b09DUiwgbGVjdHVyYSl7CiAgRVNULmZyZW50ZU9rPXRydWU7CiAgRVNULmZyZW50ZVRleHRvPSh0ZXh0b09DUnx8JycpKydcbkxFQ1RVUkEgQ09ORklSTUFEQTogJytsZWN0dXJhOwogIG9jdWx0YXJDb25maXJtYWNpb25MZWN0dXJhKCk7CiAgbXNnKCdzdEYnLCdcdTI3MTMgRnJlbnRlIGNvbmZpcm1hZG86ICcrbGVjdHVyYSwnIzA4MCcpOwogIGF2YW56YXJUcmFzRnJlbnRlKCk7Cn0KZnVuY3Rpb24gYWJyaXJDb25maXJtYWNpb25MZWN0dXJhKHRleHRvT0NSLCBsZWlkbyl7CiAgdHJ5ewogICAgdmFyIGNvbnQ9JCgnenlMZWNCb3gnKTsKICAgIGlmKCFjb250KXsKICAgICAgY29udD1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgICAgY29udC5pZD0nenlMZWNCb3gnOwogICAgICBjb250LnN0eWxlLmNzc1RleHQ9J2JvcmRlcjoxcHggc29saWQgIzdjM2FlZDtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxMHB4O21hcmdpbjo4cHggMDtiYWNrZ3JvdW5kOiMxNzEyMmI7JzsKICAgICAgdmFyIHBzMj0kKCdwczInKTsKICAgICAgaWYocHMyJiZwczIuaW5zZXJ0QmVmb3JlKXsgcHMyLmluc2VydEJlZm9yZShjb250LHBzMi5maXJzdENoaWxkKTsgfSBlbHNlIHsgZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZChjb250KTsgfQogICAgICB2YXIgdDE9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2Jyk7CiAgICAgIHQxLnN0eWxlLmNzc1RleHQ9J2ZvbnQtc2l6ZToxM3B4O2NvbG9yOiNlNmU2ZmE7bWFyZ2luLWJvdHRvbTo2cHg7bGluZS1oZWlnaHQ6MS4zNTsnOwogICAgICB0MS50ZXh0Q29udGVudD0nTm8gcHVkZSBjb25maXJtYXIgZWwgbm9tYnJlIGNvbiBzZWd1cmlkYWQuIEVzdG8gZnVlIGxvIHF1ZSBMRVx1MDBDRCBkZWwgZG9jdW1lbnRvLiBDb3JyaWdlIFNPTE8gbGFzIGxldHJhcyBtYWwgbGVcdTAwRURkYXMgeSBjb25maXJtYTonOwogICAgICBjb250LmFwcGVuZENoaWxkKHQxKTsKICAgICAgdmFyIGlucD1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdpbnB1dCcpOwogICAgICBpbnAuaWQ9J3p5TGVjSW4nOwogICAgICBpbnAudHlwZT0ndGV4dCc7CiAgICAgIGlucC5hdXRvY29tcGxldGU9J29mZic7CiAgICAgIGlucC5wbGFjZWhvbGRlcj0nTm9tYnJlIGxlaWRvIGRlbCBkb2N1bWVudG8nOwogICAgICBpbnAuc3R5bGUuY3NzVGV4dD0nd2lkdGg6MTAwJTtib3gtc2l6aW5nOmJvcmRlci1ib3g7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6MTBweDtib3JkZXI6MXB4IHNvbGlkICM0NDQ7YmFja2dyb3VuZDojMGUwYjFlO2NvbG9yOiNmZmY7Zm9udC1zaXplOjE1cHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Oyc7CiAgICAgIGNvbnQuYXBwZW5kQ2hpbGQoaW5wKTsKICAgICAgdmFyIGIxPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2J1dHRvbicpOwogICAgICBiMS5pZD0nenlMZWNCdG4nOwogICAgICBiMS50eXBlPSdidXR0b24nOwogICAgICBiMS50ZXh0Q29udGVudD0nQ29uZmlybWFyOiBhc1x1MDBFRCBzZSBsZWUgZW4gbWkgZG9jdW1lbnRvJzsKICAgICAgYjEuc3R5bGUuY3NzVGV4dD0nZGlzcGxheTpibG9jazt3aWR0aDoxMDAlO3BhZGRpbmc6MTFweDtib3JkZXI6MDtib3JkZXItcmFkaXVzOjEwcHg7YmFja2dyb3VuZDojN2MzYWVkO2NvbG9yOiNmZmY7Zm9udC1zaXplOjE0cHg7Zm9udC13ZWlnaHQ6NjAwO21hcmdpbi1ib3R0b206NnB4Oyc7CiAgICAgIGNvbnQuYXBwZW5kQ2hpbGQoYjEpOwogICAgICB2YXIgYjI9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnYnV0dG9uJyk7CiAgICAgIGIyLmlkPSd6eUxlY1JlcCc7CiAgICAgIGIyLnR5cGU9J2J1dHRvbic7CiAgICAgIGIyLnRleHRDb250ZW50PSdNZWpvciByZXBpdG8gbGEgZm90byc7CiAgICAgIGIyLnN0eWxlLmNzc1RleHQ9J2Rpc3BsYXk6YmxvY2s7d2lkdGg6MTAwJTtwYWRkaW5nOjEwcHg7Ym9yZGVyOjA7Ym9yZGVyLXJhZGl1czoxMHB4O2JhY2tncm91bmQ6IzJjMmMzYztjb2xvcjojZGRkO2ZvbnQtc2l6ZToxM3B4Oyc7CiAgICAgIGNvbnQuYXBwZW5kQ2hpbGQoYjIpOwogICAgICB2YXIgbT1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgICAgbS5pZD0nenlMZWNNc2cnOwogICAgICBtLnN0eWxlLmNzc1RleHQ9J2ZvbnQtc2l6ZToxM3B4O21hcmdpbi10b3A6NnB4O2xpbmUtaGVpZ2h0OjEuMzU7JzsKICAgICAgY29udC5hcHBlbmRDaGlsZChtKTsKICAgICAgYjEuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKCl7CiAgICAgICAgdHJ5ewogICAgICAgICAgdmFyIHY9bm9ybSgkKCd6eUxlY0luJyk/JCgnenlMZWNJbicpLnZhbHVlOicnKTsKICAgICAgICAgIHZhciBvY3JUb2tzPXRva2Vuc05vbWJyZURlKGNvbnQuX19vY3J8fCcnKTsKICAgICAgICAgIGlmKCF0b2tlbnNEZSh2KS5sZW5ndGgpeyBtc2coJ3p5TGVjTXNnJywnRXNjcmliZSBsbyBxdWUgc2UgbGVlIGVuIGVsIGRvY3VtZW50byAoc29sbyBsZXRyYXMpLicsJyNjMDAnKTsgcmV0dXJuOyB9CiAgICAgICAgICAvKiBoZXJlZGFkbyB2MTQ6IHNpbiBjYWxsZWpvbiBzaW4gc2FsaWRhLiBBbnRlcywgc2kgZWwgT0NSIGhhYmlhCiAgICAgICAgICAgICBzYWx0YWRvIHVuYSBwYWxhYnJhIChlai4gbm8gbGV5byBBTEZPTlNPKSwgZWwgZ3VhcmRhcnJhaWwKICAgICAgICAgICAgIHJlY2hhemFiYSBsYSBjb3JyZWNjaW9uIGF1bnF1ZSBlc2NyaWJpZXJhcyB0dXMgbm9tYnJlcwogICAgICAgICAgICAgdmVyZGFkZXJvcyB5IGVsIHBhbmVsIHZvbHZpYSBTSUVNUFJFLiBBaG9yYSB0dSBub21icmUgZGVsCiAgICAgICAgICAgICBwYXNvIDEgbWFuZGE6IGVsIGd1YXJkYXJyYWlsIHNvbG8gZXhpZ2UgcXVlIGxhIGNvcnJlY2Npb24KICAgICAgICAgICAgIGd1YXJkZSBhbGd1bmEgcmVsYWNpb24gY29uIGxvIHF1ZSBzZSBsZXlvIGRlbCBkb2N1bWVudG8uICovCiAgICAgICAgICB2YXIgbmM9bm9tYnJlQ29pbmNpZGUoRVNULmVzY3JpdG8sIHYsIGZhbHNlKTsKICAgICAgICAgIGlmKCFuYy5vayl7CiAgICAgICAgICAgIG1zZygnenlMZWNNc2cnLCdDb24gZXNhIGxlY3R1cmEgdHUgbm9tYnJlIHNpZ3VlIHNpbiBjb2luY2lkaXIuIFJldmlzYSB0dSBub21icmUgZGVsIHBhc28gMSBvIHJlcGl0ZSBsYSBmb3RvLicsJyNjMDAnKTsKICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgfQogICAgICAgICAgaWYob2NyVG9rcy5sZW5ndGg+MCYmIWVkaWNpb25BY2VwdGFibGUodiwgb2NyVG9rcykpewogICAgICAgICAgICB2YXIgdmQ9dG9rZW5zRGUodiksIGNvbXBhcnRlPWZhbHNlLCBpMSwgajE7CiAgICAgICAgICAgIGZvcihpMT0wO2kxPHZkLmxlbmd0aCYmIWNvbXBhcnRlO2kxKyspewogICAgICAgICAgICAgIGZvcihqMT0wO2oxPG9jclRva3MubGVuZ3RoO2oxKyspeyBpZihwYXJQYXJlY2lkbyh2ZFtpMV0sb2NyVG9rc1tqMV0pKXsgY29tcGFydGU9dHJ1ZTsgYnJlYWs7IH0gfQogICAgICAgICAgICB9CiAgICAgICAgICAgIGlmKCFjb21wYXJ0ZSl7CiAgICAgICAgICAgICAgbXNnKCd6eUxlY01zZycsJ0VzYSBsZWN0dXJhIG5vIHNlIHBhcmVjZSBhIGxvIHF1ZSBMRVx1MDBDRCBkZWwgZG9jdW1lbnRvLiBDb3JyaWdlIGxhcyBsZXRyYXMgbWFsIGxlXHUwMEVEZGFzIG8gcmVwaXRlIGxhIGZvdG8gY29uIG1lam9yIGx1ei4nLCcjYzAwJyk7CiAgICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgICB9CiAgICAgICAgICB9CiAgICAgICAgICBhY2VwdGFyRnJlbnRlQ29uZmlybWFkbyhjb250Ll9fb2NyfHwnJywgdik7CiAgICAgICAgfWNhdGNoKGUpe30KICAgICAgfSk7CiAgICAgIGIyLmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbigpewogICAgICAgIHRyeXsKICAgICAgICAgIG9jdWx0YXJDb25maXJtYWNpb25MZWN0dXJhKCk7CiAgICAgICAgICBtc2coJ3N0RicsJ1RvY2EgQ0FQVFVSQVIgeSByZXBpdGUgbGEgZm90bzogYnVlbmEgbHV6LCBzaW4gYnJpbGxvLCBxdWUgZWwgZG9jdW1lbnRvIGxsZW5lIGVsIG1hcmNvLicsJyNhNjAnKTsKICAgICAgICB9Y2F0Y2goZSl7fQogICAgICB9KTsKICAgIH0KICAgIGNvbnQuX19vY3I9dGV4dG9PQ1J8fCcnOwogICAgdmFyIGlucDI9JCgnenlMZWNJbicpOwogICAgaWYoaW5wMil7IGlucDIudmFsdWU9KGxlaWRvfHwnJyk7IH0KICAgIGNvbnQuc3R5bGUuZGlzcGxheT0nYmxvY2snOwogICAgbXNnKCd6eUxlY01zZycsJycsJycpOwogICAgbXNnKCdzdEYnLCdSZXZpc2EgYWJham8gbG8gcXVlIGxlXHUwMEVEIGRlbCBkb2N1bWVudG86IHB1ZWRlcyBjb3JyZWdpciBsYXMgbGV0cmFzIG1hbCBsZVx1MDBFRGRhcy4nLCcjYTYwJyk7CiAgfWNhdGNoKGUpe30KfQpmdW5jdGlvbiBvY3VsdGFyQ29uZmlybWFjaW9uTGVjdHVyYSgpewogIHZhciBjPSQoJ3p5TGVjQm94Jyk7CiAgaWYoYyl7IGMuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH0KfQpmdW5jdGlvbiBwcm9jZXNhckZyZW50ZShkYXRhVXJsKXsKICBFU1QuZnJlbnRlT2s9ZmFsc2U7CiAgRVNULmNhcmFEb2M9bnVsbDsKICBvY3VsdGFyQ29uZmlybWFjaW9uTGVjdHVyYSgpOwogIGJ1c3kodHJ1ZSk7CiAgbXNnKCdzdEYnLCdMZXllbmRvIGVsIGRvY3VtZW50byAocGFzZSAxIGRlIDMpLi4uJywnJyk7CiAgRVNULmZyZW50ZUltZz1kYXRhVXJsOwogIHNob3dJbWcoJ3BGJyxkYXRhVXJsKTsKICB2YXIgcENhcmE9Y29uVGltZW91dChkZXRlY3RhckNhcmFFbihkYXRhVXJsKSwxNTAwMCk7CiAgdmFyIHBUeHQ9b2NyRnJlbnRlKGRhdGFVcmwpLmNhdGNoKGZ1bmN0aW9uKGUpeyByZXR1cm4gJ09DUl9FUlI6JysoZSYmZS5tZXNzYWdlP2UubWVzc2FnZTonJyk7IH0pOwogIFByb21pc2UuYWxsKFtwQ2FyYSxwVHh0XSkudGhlbihmdW5jdGlvbihyKXsKICAgIHZhciBjYXJhPXJbMF0sIHRleHRvPXJbMV18fCcnOwogICAgaWYodGV4dG8uaW5kZXhPZignT0NSX0VSUjonKT09PTApeyBmYWxsb0xlY3R1cmFGcmVudGUoJ05vIHB1ZGUgbGVlciBlbCBkb2N1bWVudG8gKCcrdGV4dG8uc2xpY2UoOCkrJykuJyk7IHJldHVybjsgfQogICAgaWYodGV4dG8ucmVwbGFjZSgvXHMvZywnJykubGVuZ3RoPDE1KXsgZmFsbG9MZWN0dXJhRnJlbnRlKCdObyBsZVx1MDBFRCBzdWZpY2llbnRlIHRleHRvLiBBY1x1MDBFOXJjYXRlLCBidWVuYSBsdXosIHF1ZSBlbCBkb2N1bWVudG8gbGxlbmUgZWwgbWFyY28uJyk7IHJldHVybjsgfQogICAgdmFyIGxhZG89ZGV0ZWN0YXJMYWRvKHRleHRvLCEhKGNhcmEmJmNhcmEuZGV0ZWN0aW9uKSk7CiAgICBpZihsYWRvPT09J3JldmVyc28nKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RGJywnRXNvIGVzIGVsIFJFVkVSU08gKHNlIHZlbiBkaXJlY2Npb25lcyBvIGxhIHpvbmEgTVJaKS4gTmVjZXNpdG8gZWwgRlJFTlRFOiBkb25kZSBlc3RcdTAwRTEgdHUgRk9UTyB5IHR1cyBkYXRvcy4gVnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICBpZihsYWRvIT09J2ZyZW50ZScgJiYgIShjYXJhJiZjYXJhLmRldGVjdGlvbikpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbXNnKCdzdEYnLCdObyBwdWRlIGNvbmZpcm1hciBxdWUgc2VhIGVsIEZSRU5URS4gQXNlZ1x1MDBGQXJhdGUgZGUgcXVlIHNlIHZlYSB0dSBmb3RvIHkgdHVzIGRhdG9zLCBzaW4gYnJpbGxvLCB5IHZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgaWYoY2FyYSYmY2FyYS5kZXRlY3Rpb24mJmNhcmEuZGVzY3JpcHRvcil7IEVTVC5jYXJhRG9jPWNhcmEuZGVzY3JpcHRvcjsgfQogICAgdmFyIG5jPW5vbWJyZUNvaW5jaWRlKEVTVC5lc2NyaXRvLHRleHRvLG1yekxpbmVhcyh0ZXh0bykubGVuZ3RoPjApOwogICAgaWYobmMuaGF5ICYmICFuYy5vayl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBhYnJpckNvbmZpcm1hY2lvbkxlY3R1cmEodGV4dG8sIG5jLmxlaWRvKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgRVNULmZyZW50ZU9rPXRydWU7CiAgICBFU1QuZnJlbnRlVGV4dG89dGV4dG87CiAgICBtc2coJ3N0RicsJ1x1MjcxMyBGcmVudGUgbGVcdTAwRURkbyBjb3JyZWN0YW1lbnRlLicrKG5jLm9rPygnIE5vbWJyZTogJytuYy5sZWlkbysnLicpOicnKSwnIzA4MCcpOwogICAgYnVzeShmYWxzZSk7CiAgICBhdmFuemFyVHJhc0ZyZW50ZSgpOwogIH0pOwp9CmZ1bmN0aW9uIG5vbWJyZU5vQ29pbmNpZGVNc2codHh0KXsKICByZXNldGVhckRvY3VtZW50bygpOwogIHZhciBubj0kKCdub21icmVOb0NvaW5jaWRlJyk7CiAgaWYobm4peyBubi50ZXh0Q29udGVudD10eHQ7IG5uLnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsgbm4uc3R5bGUuY29sb3I9JyNjMDAnOyB9CiAgbXNnKCdzdEEnLCcnKTsgbXNnKCdzdEYnLCcnKTsKICBtc2coJ3p5RXJyTm9tYnJlJyx0eHQrJyBTaSB0dSBub21icmUgZXN0XHUwMEUxIGJpZW4gZXNjcml0bywgdGFtYmlcdTAwRTluIHB1ZWRlcyByZXBldGlyIGxhIGZvdG8gZGVsIGRvY3VtZW50byBjb24gYnVlbmEgbHV6IHkgc2luIGJyaWxsby4nLCcjYzAwJyk7CiAgYXZhbnphcigxKTsKICBib3RvblJlcGV0aXJGb3RvKCk7Cn0KZnVuY3Rpb24gYm90b25SZXBldGlyRm90bygpewogIHZhciBiPSQoJ3p5QnRuUmVwRm90bycpOwogIGlmKCFiKXsKICAgIGI9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnYnV0dG9uJyk7CiAgICBiLmlkPSd6eUJ0blJlcEZvdG8nOwogICAgYi50eXBlPSdidXR0b24nOwogICAgYi50ZXh0Q29udGVudD0nUmVwZXRpciBsYSBmb3RvIGRlbCBkb2N1bWVudG8nOwogICAgYi5zdHlsZS5jc3NUZXh0PSdkaXNwbGF5OmJsb2NrO21hcmdpbjo4cHggMDtwYWRkaW5nOjExcHggMTRweDtib3JkZXI6MDtib3JkZXItcmFkaXVzOjEwcHg7YmFja2dyb3VuZDojN2MzYWVkO2NvbG9yOiNmZmY7Zm9udC1zaXplOjE0cHg7Zm9udC13ZWlnaHQ6NjAwO3dpZHRoOjEwMCU7JzsKICAgIGIuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKCl7IHRyeXsgYXZhbnphcigyKTsgfWNhdGNoKGUpe30gfSk7CiAgICB2YXIgYW5jbGE9JCgnenlFcnJOb21icmUnKTsKICAgIGlmKGFuY2xhJiZhbmNsYS5wYXJlbnROb2RlKXsgYW5jbGEucGFyZW50Tm9kZS5pbnNlcnRCZWZvcmUoYixhbmNsYS5uZXh0U2libGluZyk7IH0KICAgIGVsc2V7IGRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQoYik7IH0KICB9CiAgYi5zdHlsZS5kaXNwbGF5PSdibG9jayc7Cn0KCi8qID09PT09PT09PT09PT09PT09IHBhc28gMzogcmV2ZXJzbyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiByZXZlcnNvQWNlcHRhYmxlKHRleHRvKXsKICB2YXIgdD0odGV4dG98fCcnKS50b1VwcGVyQ2FzZSgpOwogIGlmKCh0Lm1hdGNoKC88L2cpfHxbXSkubGVuZ3RoPj02KXsgcmV0dXJuIHRydWU7IH0KICBpZigvUERGNEk/Ny8udGVzdCh0LnJlcGxhY2UoL1xzL2csJycpKSl7IHJldHVybiB0cnVlOyB9CiAgdmFyIGZ1ZXJ0ZXM9WydET01JQ0lMSU8nLCdESVJFQ0NJT04nLCdESVJFQ0NJXHUwMEQzTicsJ0NPTE9OSUEnLCdCQVJSSU8nLCdSRVNJREVOQ0lBJywnQ0FTRVJJTycsJ0NBTlRPTicsJ0FMREVBJywnT0JTRVJWQUNJT04nLCdPQlNFUlZBQ0lcdTAwRDNOJywnRVNUQURPIENJVklMJywnRE9OQU5URScsJ0dSVVBPIFNBTkcnLCdUSVBPIERFIFNBTkcnLCdFTkRPUlNFTUVOVCcsJ1JFU1RSSUNUSU9OJywnQUREUkVTUyddOwogIHZhciBpLGM9MDsKICBmb3IoaT0wO2k8ZnVlcnRlcy5sZW5ndGg7aSsrKXsgaWYodC5pbmRleE9mKGZ1ZXJ0ZXNbaV0pPj0wKXsgYysrOyB9IH0KICBpZihjPj0yKXsgcmV0dXJuIHRydWU7IH0KICBpZihFU1QudGlwbz09PSd1c2EnICYmIC9cYihJU1N8RVhQfEREfDREfDRGfFJFU1R8RU5EfERMKVxiLy50ZXN0KHQpKXsgcmV0dXJuIHRydWU7IH0KICByZXR1cm4gZmFsc2U7Cn0KZnVuY3Rpb24gcHJvY2VzYXJSZXZlcnNvKGRhdGFVcmwpewogIEVTVC5yZXZlcnNvT2s9ZmFsc2U7CiAgYnVzeSh0cnVlKTsKICBtc2coJ3N0QScsJ0xleWVuZG8gZWwgcmV2ZXJzby4uLicsJycpOwogIEVTVC5yZXZlcnNvSW1nPWRhdGFVcmw7CiAgc2hvd0ltZygncEEnLGRhdGFVcmwpOwogIGhhY2VyT2NyKGRhdGFVcmwpLnRoZW4oZnVuY3Rpb24odGV4dG8pewogICAgaWYodGV4dG8ucmVwbGFjZSgvXHMvZywnJykubGVuZ3RoPDEwICYmICFyZXZlcnNvQWNlcHRhYmxlKHRleHRvKSl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBtc2coJ3N0QScsJ05vIGxlXHUwMEVEIHN1ZmljaWVudGUgdGV4dG8gZW4gZWwgcmV2ZXJzby4gQWNcdTAwRTlyY2F0ZSwgYnVlbmEgbHV6LCB5IHZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgdmFyIGNhcmFQZW5kPW51bGw7CiAgICB2YXIgbGFkbz1kZXRlY3RhckxhZG8odGV4dG8sZmFsc2UpOwogICAgaWYobGFkbz09PSdmcmVudGUnKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RBJywnRXNvIGVzIGVsIEZSRU5URSAoc2UgdmUgbGEgZm90byB5IGxvcyBkYXRvcykuIE5lY2VzaXRvIGVsIFJFVkVSU086IGRpcmVjY2lvbmVzIG8gbGEgem9uYSBNUlouIFZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgaWYobGFkbyE9PSdyZXZlcnNvJyAmJiAhcmV2ZXJzb0FjZXB0YWJsZSh0ZXh0bykpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbXNnKCdzdEEnLCdObyBwdWRlIGNvbmZpcm1hciBxdWUgc2VhIGVsIFJFVkVSU08uIE11ZXN0cmEgbGFzIGRpcmVjY2lvbmVzIG8gbGEgem9uYSBkZSByYXlpdGFzL01SWiB5IHZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgdmFyIG5jPW5vbWJyZUNvaW5jaWRlKEVTVC5lc2NyaXRvLHRleHRvLG1yekxpbmVhcyh0ZXh0bykubGVuZ3RoPjApOwogICAgaWYobmMuaGF5ICYmICFuYy5vayl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBub21icmVOb0NvaW5jaWRlTXNnKCdFbCBub21icmUgZGVsIGRvY3VtZW50byAoJytuYy5sZWlkbysnKSBubyBjb2luY2lkZSBjb24gbG8gcXVlIGVzY3JpYmlzdGUuIENvcnJpZ2UgdHUgbm9tYnJlIGVuIGVsIHBhc28gMTogcHVlZGUgdGVuZXIgMSBvIDIgbm9tYnJlcyB5IDEgbyAyIGFwZWxsaWRvcy4nKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgRVNULnJldmVyc29Paz10cnVlOwogICAgRVNULnJldmVyc29UZXh0bz10ZXh0bzsKICAgIG1zZygnc3RBJywnXHUyNzEzIFJldmVyc28gbGVcdTAwRURkbyBjb3JyZWN0YW1lbnRlLicsJyMwODAnKTsKICAgIGJ1c3koZmFsc2UpOwogICAgYXZhbnphcig0KTsKICAgIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsgdHJ5eyBhYnJpckNhbSgnNCcsJ3VzZXInLCdzdFYnLCdiU2VsZmllJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgfWNhdGNoKGUpe30gfSw1MDApOwogIH0pLmNhdGNoKGZ1bmN0aW9uKGUpewogICAgYnVzeShmYWxzZSk7CiAgICBtc2coJ3N0QScsJ0Vycm9yIGxleWVuZG8gZWwgcmV2ZXJzbzogJysoZSYmZS5tZXNzYWdlP2UubWVzc2FnZTonJykrJy4gVnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogIH0pOwp9CgovKiA9PT09PT09PT09PT09PT09PSBwYXNvIDQ6IHNlbGZpZSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiByZWNvcnRlUm9zdHJvKGRhdGFVcmwsIGRldCl7CiAgdHJ5ewogICAgaWYoIWRldCB8fCAhZGV0LmRldGVjdGlvbiB8fCAhZGV0LmRldGVjdGlvbi5ib3gpeyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKGRhdGFVcmwpOyB9CiAgICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsKICAgICAgdmFyIGltPW5ldyBJbWFnZSgpOwogICAgICBpbS5vbmxvYWQ9ZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICB2YXIgYj1kZXQuZGV0ZWN0aW9uLmJveCwgVzA9aW0ud2lkdGgsIEgwPWltLmhlaWdodDsKICAgICAgICAgIHZhciBjdz1iLndpZHRoKjIuMiwgY2g9Yi5oZWlnaHQqMi42OwogICAgICAgICAgdmFyIGN4PWIueCtiLndpZHRoLzIsIGN5PWIueStiLmhlaWdodCowLjUyOwogICAgICAgICAgdmFyIHgwPU1hdGgubWF4KDAsTWF0aC5yb3VuZChjeC1jdy8yKSksIHkwPU1hdGgubWF4KDAsTWF0aC5yb3VuZChjeS1jaC8yKSk7CiAgICAgICAgICB2YXIgdzA9TWF0aC5taW4oVzAteDAsTWF0aC5yb3VuZChjdykpLCBoMD1NYXRoLm1pbihIMC15MCxNYXRoLnJvdW5kKGNoKSk7CiAgICAgICAgICBpZih3MDw0MHx8aDA8NDApeyByZXMoZGF0YVVybCk7IHJldHVybjsgfQogICAgICAgICAgdmFyIGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7CiAgICAgICAgICBjLndpZHRoPXcwOyBjLmhlaWdodD1oMDsKICAgICAgICAgIHZhciBnPWMuZ2V0Q29udGV4dCgnMmQnKTsKICAgICAgICAgIGlmKCFnKXsgcmVzKGRhdGFVcmwpOyByZXR1cm47IH0KICAgICAgICAgIGcuZHJhd0ltYWdlKGltLCB4MCwgeTAsIHcwLCBoMCwgMCwgMCwgdzAsIGgwKTsKICAgICAgICAgIHJlcyhjLnRvRGF0YVVSTCgnaW1hZ2UvanBlZycsMC45KSk7CiAgICAgICAgfWNhdGNoKGVFKXsgcmVzKGRhdGFVcmwpOyB9CiAgICAgIH07CiAgICAgIGltLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVzKGRhdGFVcmwpOyB9OwogICAgICBpbS5zcmM9ZGF0YVVybDsKICAgIH0pOwogIH1jYXRjaChlKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZShkYXRhVXJsKTsgfQp9CmZ1bmN0aW9uIGNhamFEZVF1YWQocSwgdncsIHZoLCBtYXJnKXsKICB0cnl7CiAgICBpZighcSB8fCAhcS50bCB8fCAhcS50ciB8fCAhcS5iciB8fCAhcS5ibCl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgeHM9W3EudGwueCxxLnRyLngscS5ici54LHEuYmwueF0sIHlzPVtxLnRsLnkscS50ci55LHEuYnIueSxxLmJsLnldOwogICAgdmFyIHgwPU1hdGgubWluLmFwcGx5KG51bGwseHMpLCB4MT1NYXRoLm1heC5hcHBseShudWxsLHhzKTsKICAgIHZhciB5MD1NYXRoLm1pbi5hcHBseShudWxsLHlzKSwgeTE9TWF0aC5tYXguYXBwbHkobnVsbCx5cyk7CiAgICB2YXIgbXg9KHgxLXgwKSptYXJnLCBteT0oeTEteTApKm1hcmc7CiAgICB4MD1NYXRoLm1heCgwLE1hdGguZmxvb3IoeDAtbXgpKTsgeTA9TWF0aC5tYXgoMCxNYXRoLmZsb29yKHkwLW15KSk7CiAgICB4MT1NYXRoLm1pbih2dyxNYXRoLmNlaWwoeDErbXgpKTsgeTE9TWF0aC5taW4odmgsTWF0aC5jZWlsKHkxK215KSk7CiAgICBpZih4MS14MDw0MHx8eTEteTA8NDApeyByZXR1cm4gbnVsbDsgfQogICAgcmV0dXJuIHt4OngwLCB5OnkwLCB3OngxLXgwLCBoOnkxLXkwfTsKICB9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9Cn0KZnVuY3Rpb24gY2FwdHVyYXJWaWRlb0RvYyhwc0lkLCBtYXhEaW0pewogIHZhciB2PWZpbmRWaWRlbyhwc0lkKTsKICBpZighdiB8fCAhdi52aWRlb1dpZHRoIHx8ICFzdHJlYW1zW3BzSWRdKXsgcmV0dXJuIG51bGw7IH0KICB2YXIgdnc9di52aWRlb1dpZHRoLCB2aD12LnZpZGVvSGVpZ2h0OwogIHZhciBzdD16eURldCgpW3BzSWRdfHxudWxsOwogIHZhciByPW51bGwsIGFob3JhPURhdGUubm93KCk7CiAgaWYoc3QpewogICAgaWYoc3QudWx0UXVhZCAmJiAoYWhvcmEtKHN0LnVsdFF1YWRUfHwwKSk8MTUwMCl7IHI9Y2FqYURlUXVhZChzdC51bHRRdWFkLCB2dywgdmgsIDAuMDQpOyB9CiAgICBpZighciAmJiBzdC51bHRDYWphICYmIChhaG9yYS0oc3QudWx0Q2FqYVR8fDApKTwyMDAwKXsKICAgICAgdmFyIGI9c3QudWx0Q2FqYSwgbXg9Yi53KjAuMDMsIG15PWIuaCowLjAzOwogICAgICB2YXIgYng9TWF0aC5tYXgoMCxNYXRoLmZsb29yKGIueC1teCkpLCBieT1NYXRoLm1heCgwLE1hdGguZmxvb3IoYi55LW15KSk7CiAgICAgIHZhciBidz1NYXRoLm1pbih2dy1ieCxNYXRoLmNlaWwoYi53K214KjIpKSwgYmg9TWF0aC5taW4odmgtYnksTWF0aC5jZWlsKGIuaCtteSoyKSk7CiAgICAgIGlmKGJ3Pj00MCYmYmg+PTQwKXsgcj17eDpieCwgeTpieSwgdzpidywgaDpiaH07IH0KICAgIH0KICB9CiAgaWYoIXIpeyByPXt4Ok1hdGgucm91bmQodncqMC4wNyksIHk6TWF0aC5yb3VuZCh2aCowLjA5KSwgdzpNYXRoLnJvdW5kKHZ3KjAuODYpLCBoOk1hdGgucm91bmQodmgqMC44Mil9OyB9CiAgaWYoci54PDApeyByLng9MDsgfQogIGlmKHIueTwwKXsgci55PTA7IH0KICBpZihyLngrci53PnZ3KXsgci53PXZ3LXIueDsgfQogIGlmKHIueStyLmg+dmgpeyByLmg9dmgtci55OyB9CiAgaWYoci53PDQwfHxyLmg8NDApeyByZXR1cm4gY2FwdHVyYXJWaWRlbyhwc0lkLCBtYXhEaW0pOyB9CiAgdmFyIHNjPU1hdGgubWluKDEsIChtYXhEaW18fDE2MDApL01hdGgubWF4KHIudywgci5oKSk7CiAgdmFyIGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7CiAgYy53aWR0aD1NYXRoLm1heCgxNixNYXRoLnJvdW5kKHIudypzYykpOwogIGMuaGVpZ2h0PU1hdGgubWF4KDE2LE1hdGgucm91bmQoci5oKnNjKSk7CiAgdmFyIGc9Yy5nZXRDb250ZXh0KCcyZCcpOwogIGlmKCFnKXsgcmV0dXJuIGNhcHR1cmFyVmlkZW8ocHNJZCwgbWF4RGltKTsgfQogIGcuZHJhd0ltYWdlKHYsIHIueCwgci55LCByLncsIHIuaCwgMCwgMCwgYy53aWR0aCwgYy5oZWlnaHQpOwogIHZhciBkPWMudG9EYXRhVVJMKCdpbWFnZS9qcGVnJywwLjkpOwogIHBhcmFyQ2FtKHBzSWQpOwogIHJldHVybiBkOwp9CmZ1bmN0aW9uIHByb2Nlc2FyU2VsZmllKCl7CiAgRVNULnNlbGZpZU9rPWZhbHNlOwogIHZhciBpbWc9Y2FwdHVyYXJWaWRlbygnNCcsMTA0OCk7CiAgaWYoIWltZyl7IG1zZygnc3RWJywnUHJpbWVybyBhYnJlIGxhIGNhbWFyYSB5IHBvbiB0dSBjYXJhIGRlbnRybyBkZWwgbWFyY28uJywnI2MwMCcpOyByZXR1cm47IH0KICBidXN5KHRydWUpOwogIG1zZygnc3RWJywnQnVzY2FuZG8gdHUgcm9zdHJvIHBhcmEgbGEgZm90byBkZSBjYXJhLi4uJywnJyk7CiAgY29uVGltZW91dChkZXRlY3RhckNhcmFFbihpbWcpLDEyMDAwKS50aGVuKGZ1bmN0aW9uKGQwKXsKICAgIHZhciBwUmVjPShkMCYmZDAuZGV0ZWN0aW9uKT9yZWNvcnRlUm9zdHJvKGltZyxkMCk6UHJvbWlzZS5yZXNvbHZlKGltZyk7CiAgICByZXR1cm4gcFJlYy5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gaW1nOyB9KTsKICB9KS5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gaW1nOyB9KS50aGVuKGZ1bmN0aW9uKHJlYyl7CiAgICBFU1Quc2VsZmllSW1nPXJlY3x8aW1nOwogICAgRVNULnJvc3Ryb1JlY29ydGFkbz0hIShyZWMmJnJlYyE9PWltZyk7CiAgICBzaG93SW1nKCdwUycsRVNULnNlbGZpZUltZyk7CiAgICBtc2coJ3N0VicsJ0NvbXBhcmFuZG8gdHUgY2FyYSBjb24gbGEgZGVsIGRvY3VtZW50by4uLicsJycpOwogICAgdmFyIHBEb2M9RVNULmNhcmFEb2M/UHJvbWlzZS5yZXNvbHZlKEVTVC5jYXJhRG9jKTpjb25UaW1lb3V0KGRldGVjdGFyQ2FyYURvYyhFU1QuZnJlbnRlSW1nfHxFU1QucmV2ZXJzb0ltZ3x8JycpLDE1MDAwKS50aGVuKGZ1bmN0aW9uKHIpeyByZXR1cm4gKHImJnIuZGV0ZWN0aW9uJiZyLmRlc2NyaXB0b3IpP3IuZGVzY3JpcHRvcjpudWxsOyB9KTsKICAgIHZhciBwU2VsPWNvblRpbWVvdXQoZGV0ZWN0YXJDYXJhRW4oRVNULnNlbGZpZUltZywyKSwxNTAwMCkudGhlbihmdW5jdGlvbihyMCl7CiAgICAgIGlmKHIwJiZyMC5kZXRlY3Rpb24peyByZXR1cm4gcjA7IH0KICAgICAgcmV0dXJuIGNvblRpbWVvdXQoZGV0ZWN0YXJDYXJhRW4oRVNULnNlbGZpZUltZyksMTUwMDApOwogICAgfSk7CiAgICBQcm9taXNlLmFsbChbcERvYyxwU2VsXSkudGhlbihmdW5jdGlvbihyKXsKICAgICAgdmFyIGREb2M9clswXSwgZW5TZWw9clsxXTsKICAgICAgaWYoIWREb2MpeyBidXN5KGZhbHNlKTsgZmFsbG9TZWxmaWUoJ05vIHB1ZGUgdmVyIGJpZW4gbGEgY2FyYSBlbiBsYSBmb3RvIGRlbCBkb2N1bWVudG8uIFZhbW9zIGEgcmVwZXRpciBsYSBmb3RvIGRlbCBkb2N1bWVudG8gY29uIG1lam9yIGx1ei4nKTsgcmV0dXJuOyB9CiAgICAgIGlmKCFlblNlbCB8fCAhZW5TZWwuZGV0ZWN0aW9uKXsgYnVzeShmYWxzZSk7IGZhbGxvU2VsZmllKCdObyBwdWRlIHZlciB0dSBjYXJhIGVuIGxhIHNlbGZpZS4gTWVqb3IgbGEgbHV6LCBxdWl0YXRlIGdvcnJhIG8gbGVudGVzIG9zY3Vyb3MuJyk7IHJldHVybjsgfQogICAgICB2YXIgZD1kaXN0RihkRG9jLGVuU2VsLmRlc2NyaXB0b3IpOwogICAgICBpZihkPD0wLjYwKXsKICAgICAgICBFU1Quc2VsZmllT2s9dHJ1ZTsgRVNULmludGVudG9zPTU7CiAgICAgICAgbXNnKCdzdFYnLCdcdTI3MTMgVmVyaWZpY2FjaVx1MDBGM24gZmFjaWFsIHN1cGVyYWRhLiBQYXNhbmRvIGEgdHUgY2xhdmUuJywnIzA4MCcpOwogICAgICAgIGJ1c3koZmFsc2UpOyBhdmFuemFyKDUpOwogICAgICB9ZWxzZXsKICAgICAgICBidXN5KGZhbHNlKTsKICAgICAgICBmYWxsb1NlbGZpZSgnVHUgY2FyYSBubyBjb2luY2lkZSBjb24gbGEgZGVsIGRvY3VtZW50byAoZGlzdGFuY2lhICcrZC50b0ZpeGVkKDIpKycpLicrKEVTVC5yb3N0cm9SZWNvcnRhZG8/Jyc6JyBBY2VyY2F0ZTogdHUgY2FyYSBkZWJlIGxsZW5hciBlbCBvdmFsby4nKSk7CiAgICAgIH0KICAgIH0pLmNhdGNoKGZ1bmN0aW9uKGUpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgZmFsbG9TZWxmaWUoJ0VsIHZlcmlmaWNhZG9yIGZhY2lhbCBubyBjYXJnXHUwMEYzOiAnKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOicnKSsnLiBSZXZpc2EgdHUgaW50ZXJuZXQgeSByZWludGVudGEuJyk7CiAgICB9KTsKICB9KTsKfQpmdW5jdGlvbiBmYWxsb1NlbGZpZShtKXsKICBFU1QuaW50ZW50b3MtLTsKICBpZihFU1QuaW50ZW50b3M8PTApewogICAgRVNULmludGVudG9zPTU7CiAgICBFU1Quc2VsZmllT2s9ZmFsc2U7CiAgICBtc2coJ3N0VicsJ1NlIGFnb3Rhcm9uIGxvcyBpbnRlbnRvcyBkZSBsYSBzZWxmaWUsIHBlcm8gTk8gcGVyZGlzdGUgbmFkYTogbmkgdHUgbm9tYnJlIG5pIHR1cyBmb3RvcyBkZWwgZG9jdW1lbnRvIHNlIGJvcnJhbi4gTWVqb3JhIGxhIGx1eiBkZSB0dSBjYXJhLCBBQ0VSQ0FURSBoYXN0YSBxdWUgdHUgY2FyYSBsbGVuZSBlbCBvdmFsbyB5IHRvY2EgQ0FQVFVSQVIgZGUgbnVldm8uJywnI2E2MCcpOwogIH1lbHNlewogICAgbXNnKCdzdFYnLCdcdTI3MTcgJyttKycgVGUgcXVlZGFuICcrRVNULmludGVudG9zKycgaW50ZW50byhzKS4gVG9jYSBDQVBUVVJBUiBkZSBudWV2bzogeW8gcmVjb3J0byBzb2xvIHR1IHJvc3Ryby4nLCcjYzAwJyk7CiAgfQp9Ci8qID09PT09PT09PT09PT09PT09IHBhc28gNTogY2xhdmUgKyBaSUQgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gdmFsaWRhckNsYXZlcygpewogIHZhciBhPSQoJ2NsYXZlJyksIGI9JCgnY2xhdmUyJyksIGQ9JCgnZGVzZ2xvc2UnKTsKICBpZighYXx8IWIpeyByZXR1cm47IH0KICBpZighYi52YWx1ZSl7IGlmKGQpeyBkLnRleHRDb250ZW50PScnOyB9IHJldHVybjsgfQogIGlmKGEudmFsdWU9PT1iLnZhbHVlKXsKICAgIGlmKGQpeyBkLnRleHRDb250ZW50PSdcdTI3MTMgTGFzIGNsYXZlcyBjb2luY2lkZW4uIFRvY2EgZWwgYm90XHUwMEYzbiBwYXJhIGNyZWFyIHR1IFpJRC4nOyBkLnN0eWxlLmNvbG9yPScjMDgwJzsgfQogICAgaGFiaWxpdGFyU3VibWl0KCk7CiAgfWVsc2V7CiAgICBpZihkKXsgZC50ZXh0Q29udGVudD0nXHUyNzE3IExhcyBjbGF2ZXMgbm8gY29pbmNpZGVuLiBDb3JyXHUwMEVEZ2VsYXMgYXF1XHUwMEVELCBubyBzYWxlcyBkZWwgcGFzbyA1IGhhc3RhIHF1ZSBjb2luY2lkYW4uJzsgZC5zdHlsZS5jb2xvcj0nI2MwMCc7IH0KICB9Cn0KZnVuY3Rpb24gaGFiaWxpdGFyU3VibWl0KCl7CiAgdmFyIHBzPSQoJ3BzNScpOwogIGlmKCFwcyl7IHJldHVybjsgfQogIHZhciBidG5zPXBzLnF1ZXJ5U2VsZWN0b3JBbGwoJ2J1dHRvbiwgaW5wdXRbdHlwZT1idXR0b25dLCBpbnB1dFt0eXBlPXN1Ym1pdF0sIFtyb2xlPWJ1dHRvbl0nKSwgaSwgaGF5PWZhbHNlOwogIGZvcihpPTA7aTxidG5zLmxlbmd0aDtpKyspewogICAgdmFyIGVzU3VibWl0PWZhbHNlOwogICAgdHJ5eyBlc1N1Ym1pdD0oKGJ0bnNbaV0uZ2V0QXR0cmlidXRlKCd0eXBlJyl8fCcnKS50b0xvd2VyQ2FzZSgpPT09J3N1Ym1pdCcpOyB9Y2F0Y2goZVQpeyBlc1N1Ym1pdD1mYWxzZTsgfQogICAgdmFyIHQ9KChidG5zW2ldLnRleHRDb250ZW50fHwnJykrJyAnKyhidG5zW2ldLnZhbHVlfHwnJykpLnRvVXBwZXJDYXNlKCk7CiAgICBpZihlc1N1Ym1pdHx8L0NSRUFSfFJFR0lTVFJ8RklOQUxJWkFSfENPTlRJTlVBUnxFTlZJQVJ8QUNFUFRBUnxaSUQvLnRlc3QodCkpeyBidG5zW2ldLmRpc2FibGVkPWZhbHNlOyBoYXk9dHJ1ZTsgfQogIH0KICBpZighaGF5KXsgbXNnKCd6eUNsYXZlT2snLCdTaSBubyB2ZXMgZWwgYm90XHUwMEYzbiBwYXJhIGNyZWFyIHR1IFpJRCwgYXZcdTAwRURzYW1lLicsJyNhNjAnKTsgfQp9CgovKiA9PT09PT09PT09PT09PT09PSBwYXNvIDU6IGZpbHRybyBmaW5hbCBhbnRlcyBkZWwgZW52aW8gPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gY2xhdmVzTGlzdGFzKCl7CiAgdmFyIGE9JCgnY2xhdmUnKSwgYj0kKCdjbGF2ZTInKTsKICByZXR1cm4gISEoYSYmYiYmYS52YWx1ZSYmYS52YWx1ZT09PWIudmFsdWUmJlN0cmluZyhhLnZhbHVlKS5sZW5ndGg+PTgpOwp9CmZ1bmN0aW9uIGZvdG9zQ29tcGxldGFzKCl7CiAgcmV0dXJuICEhKEVTVC5mcmVudGVPayYmRVNULnNlbGZpZU9rJiYoIUVTVC5uZWNlc2l0YVJldmVyc298fEVTVC5yZXZlcnNvT2spKTsKfQpmdW5jdGlvbiByZWxsZW5hckZvdG9zRm9ybXVsYXJpbygpewogIHZhciBwczU9JCgncHM1Jyk7CiAgdmFyIGY9cHM1PyhwczUucXVlcnlTZWxlY3RvcignZm9ybScpfHxudWxsKTpudWxsOwogIGlmKCFmKXsgdHJ5eyBmPWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJ2Zvcm0nKTsgfWNhdGNoKGUpeyBmPW51bGw7IH0gfQogIGlmKCFmfHwhZi5lbGVtZW50cyl7IHJldHVybjsgfQogIHZhciBlbHM9Zi5lbGVtZW50cywgaTsKICBmb3IoaT0wO2k8ZWxzLmxlbmd0aDtpKyspewogICAgdmFyIGVsPWVsc1tpXTsKICAgIGlmKCFlbCl7IGNvbnRpbnVlOyB9CiAgICB2YXIgdGFnPWVsLnRhZ05hbWV8fCcnOwogICAgaWYodGFnIT09J0lOUFVUJyYmdGFnIT09J1RFWFRBUkVBJyl7IGNvbnRpbnVlOyB9CiAgICB2YXIgdD0oKGVsLnR5cGV8fCcnKSsnJykudG9Mb3dlckNhc2UoKTsKICAgIGlmKHRhZz09PSdJTlBVVCcmJnQhPT0naGlkZGVuJyYmdCE9PSd0ZXh0Jyl7IGNvbnRpbnVlOyB9CiAgICBpZigoZWwudmFsdWV8fCcnKS5sZW5ndGg+MTApeyBjb250aW51ZTsgfQogICAgdmFyIG5vbT0oKChlbC5uYW1lfHwnJykrJycpKycgJysoKGVsLmlkfHwnJykrJycpKS50b0xvd2VyQ2FzZSgpOwogICAgaWYoL2ZyZW50ZXxmcm9udGFsfGFudmVyc298Zm90b2Z8ZG9jMXxmb3RvMS8udGVzdChub20pKXsgaWYoRVNULmZyZW50ZUltZyl7IGVsLnZhbHVlPUVTVC5mcmVudGVJbWc7IH0gfQogICAgZWxzZSBpZigvcmV2ZXJzb3xkb3Jzb3x0cmFzZXJhfGZvdG9yZXZ8ZG9jMnxmb3RvMi8udGVzdChub20pKXsgaWYoRVNULnJldmVyc29JbWcpeyBlbC52YWx1ZT1FU1QucmV2ZXJzb0ltZzsgfSB9CiAgICBlbHNlIGlmKC9zZWxmaWV8cm9zdHJvfGZhY2lhbHxjYXJhfGZhY2V8Zm90bzN8Zm90b3MvLnRlc3Qobm9tKSl7IGlmKEVTVC5zZWxmaWVJbWcpeyBlbC52YWx1ZT1FU1Quc2VsZmllSW1nOyB9IH0KICB9Cn0KZnVuY3Rpb24gZ3VhcmRpYUVudmlvKGV2KXsKICBmdW5jdGlvbiBibG9xdWVhcigpewogICAgaWYoZXYpeyB0cnl7IGlmKGV2LnByZXZlbnREZWZhdWx0KXsgZXYucHJldmVudERlZmF1bHQoKTsgfSBpZihldi5zdG9wUHJvcGFnYXRpb24peyBldi5zdG9wUHJvcGFnYXRpb24oKTsgfSBpZihldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24peyBldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24oKTsgfSB9Y2F0Y2goZSl7fSB9CiAgICByZXR1cm4gZmFsc2U7CiAgfQogIGlmKCFjbGF2ZXNMaXN0YXMoKSl7CiAgICBtc2coJ3p5Q2xhdmVPaycsJ0FudGVzIGRlIGNyZWFyIHR1IFpJRDogZXNjcmliZSBsYSBjbGF2ZSB5IHJlcGl0ZWxhIChtaW4gOCwgaWd1YWxlcykuJywnI2MwMCcpOwogICAgcmV0dXJuIGJsb3F1ZWFyKCk7CiAgfQogIGlmKCFFU1Qubm9tYnJlT2spewogICAgbXNnKCd6eUVyck5vbWJyZScsJ0ZhbHRhIHR1IG5vbWJyZS4gRXNjcmliZWxvIHkgdG9jYSBDb250aW51YXIuJywnI2MwMCcpOwogICAgYXZhbnphcigxKTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICBpZihFU1QuZnJlbnRlVGV4dG8pewogICAgdmFyIG5jRj1ub21icmVDb2luY2lkZShFU1QuZXNjcml0bywgRVNULmZyZW50ZVRleHRvLCBmYWxzZSk7CiAgICBpZihuY0YuaGF5ICYmICFuY0Yub2spewogICAgICBtc2coJ3p5RXJyTm9tYnJlJywnVHUgbm9tYnJlICgnK0VTVC5lc2NyaXRvKycpIG5vIGNvaW5jaWRlIGNvbiBlbCBkb2N1bWVudG8geWEgdmVyaWZpY2FkbyAoJytuY0YubGVpZG8rJykuIENvcnJpZ2UgdHUgbm9tYnJlIGVuIGVsIHBhc28gMS4nLCcjYzAwJyk7CiAgICAgIGF2YW56YXIoMSk7CiAgICAgIHJldHVybiBibG9xdWVhcigpOwogICAgfQogIH0KICBpZighRVNULmZyZW50ZU9rKXsKICAgIG1zZygnc3RGJywgRVNULmZyZW50ZUltZz8nTGEgZm90byBkZWwgRlJFTlRFIG5vIHBhc1x1MDBGMyBsYSBsZWN0dXJhLiBUZSBsbGV2byBhbCBwYXNvIDIgcGFyYSByZXBldGlybGEgKGxhcyBkZW1hcyBmb3RvcyBzZSBjb25zZXJ2YW4pLic6J0ZhbHRhIGxhIGZvdG8gZGVsIEZSRU5URSBkZWwgZG9jdW1lbnRvLiBUZSBsbGV2byBhbCBwYXNvIDIgcGFyYSB0b21hcmxhIChsYXMgZGVtYXMgZm90b3Mgc2UgY29uc2VydmFuKS4nLCcjYzAwJyk7CiAgICBhdmFuemFyKDIpOwogICAgcmV0dXJuIGJsb3F1ZWFyKCk7CiAgfQogIGlmKEVTVC5uZWNlc2l0YVJldmVyc28mJiFFU1QucmV2ZXJzb09rKXsKICAgIG1zZygnc3RBJywgRVNULnJldmVyc29JbWc/J0xhIGZvdG8gZGVsIFJFVkVSU08gbm8gcGFzXHUwMEYzIGxhIGxlY3R1cmEuIFRlIGxsZXZvIGFsIHBhc28gMyBwYXJhIHJlcGV0aXJsYS4nOidGYWx0YSBsYSBmb3RvIGRlbCBSRVZFUlNPIGRlbCBkb2N1bWVudG8uIFRlIGxsZXZvIGFsIHBhc28gMyBwYXJhIHRvbWFybGEuJywnI2MwMCcpOwogICAgYXZhbnphcigzKTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICBpZighRVNULnNlbGZpZUltZyl7CiAgICBtc2coJ3N0VicsJ0ZhbHRhIGxhIHNlbGZpZS4gVGUgbGxldm8gYWwgcGFzbyA0IHBhcmEgdG9tYXJsYS4nLCcjYzAwJyk7CiAgICBhdmFuemFyKDQpOwogICAgcmV0dXJuIGJsb3F1ZWFyKCk7CiAgfQogIGlmKCFFU1Quc2VsZmllT2spewogICAgbXNnKCdzdFYnLCdMYSBzZWxmaWUgTk8gcGFzXHUwMEYzIGxhIHZlcmlmaWNhY2lcdTAwRjNuIGZhY2lhbC4gVGUgbGxldm8gYWwgcGFzbyA0IHBhcmEgcmVwZXRpcmxhOiBidWVuYSBsdXogeSBjYXJhIGNlbnRyYWRhIGVuIGVsIFx1MDBGM3ZhbG8uJywnI2MwMCcpOwogICAgYXZhbnphcig0KTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICByZWxsZW5hckZvdG9zRm9ybXVsYXJpbygpOwogIG1zZygnenlDbGF2ZU9rJywnVG9kbyB2ZXJpZmljYWRvOiBjcmVhbmRvIHR1IFpJRC4uLicsJyMwODAnKTsKICByZXR1cm4gdHJ1ZTsKfQoKLyogPT09PT09PT09PT09PT09PT0gdjEzOiBhbnRpLWJsb3F1ZW8gbGVnYWRvICsgZGlhZ25vc3RpY28gZW4gdml2byA9PT09PT09PT09PT09PT09PQogICBFbCBlcnJvciByb2pvICJGYWx0YSBsYSBmb3RvIGZyb250YWwgKHBhc28gMikiIE5PIGVzdGEgZW4gZXN0ZSBudWNsZW86IHZpZW5lIGRlCiAgIGNvZGlnbyB2aWVqbyBkZSBzdXBlcmFwcC5weSBmdWVyYSBkZWwgYmxvcXVlIG1hcmNhZG8gKHVuIHNjcmlwdCBsZWdhZG8gcXVlCiAgIHJlLXZhbGlkYSBhbCBlbnZpYXIgeSBibG9xdWVhLCBvIHRleHRvIHJlc2lkdWFsIGVuIHBhbnRhbGxhKS4gQXF1aSBzZSBoYWNlOgogICAxKSBsaW1waWFMZWdhZG8oKTogZGV0ZWN0YSBmdW5jaW9uZXMgZ2xvYmFsZXMgY3V5byBjb2RpZ28gY29udGllbmUgZXNlIHRleHRvIHkKICAgICAgbGFzIHZ1ZWx2ZSBuby1vcDsgYWRlbWFzIHNlIHRyYWdhIGxvcyBhbGVydC9jb25maXJtIGNvbiBlc2UgdGV4dG8uCiAgIDIpIHByZWVtcHRFbnZpbygpOiBveWVudGUgZW4gV0lORE9XIGVuIGZhc2UgY2FwdHVyYSAod2luZG93IGNvcnJlIEFOVEVTIHF1ZQogICAgICBkb2N1bWVudCB5IHF1ZSBlbCBmb3JtKS4gU2kgVE9ETyB5YSBwYXNvLCByZWxsZW5hIGxhcyBmb3RvcywgYXZpc2EgImNyZWFuZG8KICAgICAgdHUgWklEIiB5IGNvcnRhIGEgbG9zIG95ZW50ZXMgbGVnYWRvcyBjb24gc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uLCBkZWphbmRvCiAgICAgIHF1ZSBlbCBlbnZpbyBuYXRpdm8gZGVsIGZvcm11bGFyaW8gc2lnYS4gU2kgZmFsdGEgYWxnbywgbm8gdG9jYSBuYWRhLgogICAzKSBiYXJyZU1lbnNhamVzKCk6IGJvcnJhIHRleHRvcyByb2pvcyByZXNpZHVhbGVzIHkgcmUtaGFiaWxpdGEgYm90b25lcwogICAgICBkZXNoYWJpbGl0YWRvcyBTT0xPIGN1YW5kbyB0b2RvIHlhIHBhc28uCiAgIDQpIHBhbmVsRGlhZygpOiBib3RvbiAiaSIgZmlqbyBhYmFqbyBhIGxhIGRlcmVjaGE7IG11ZXN0cmEgcXVlIGJsb3F1ZWEsIGxvcwogICAgICBjYW1wb3MgZGVsIGZvcm11bGFyaW8sIGVsIGFjdGlvbi9tZXRob2QgeSBsYXMgZnVuY2lvbmVzIGxlZ2FkYXMgaGFsbGFkYXMuCiovCnZhciBESUFHPXtsZWdhZG86W10sYWxlcnRhczowLHVsdFN1Ym1pdDonJyx1bHRDbGljazonJ307CnZhciBUWF9ST0pBPS9mYWx0YS57MCwyNH1mcm9udGFsfGZyb250YWwuezAsMjR9cGFzb1xzKjIvaTsKZnVuY3Rpb24gaG9yYTEzKCl7CiAgdHJ5eyByZXR1cm4gKG5ldyBEYXRlKCkpLnRvSVNPU3RyaW5nKCkuc2xpY2UoMTEsMTkpOyB9Y2F0Y2goZSl7IHJldHVybiAnJzsgfQp9CmZ1bmN0aW9uIHRvZG9Pa1BhcmFDcmVhcigpewogIGlmKCFjbGF2ZXNMaXN0YXMoKSl7IHJldHVybiBmYWxzZTsgfQogIGlmKCFFU1Qubm9tYnJlT2speyByZXR1cm4gZmFsc2U7IH0KICBpZighRVNULmZyZW50ZU9rKXsgcmV0dXJuIGZhbHNlOyB9CiAgaWYoRVNULm5lY2VzaXRhUmV2ZXJzbyYmIUVTVC5yZXZlcnNvT2speyByZXR1cm4gZmFsc2U7IH0KICBpZighRVNULnNlbGZpZUltZ3x8IUVTVC5zZWxmaWVPayl7IHJldHVybiBmYWxzZTsgfQogIGlmKEVTVC5mcmVudGVUZXh0byl7CiAgICB2YXIgbmM9bm9tYnJlQ29pbmNpZGUoRVNULmVzY3JpdG8sIEVTVC5mcmVudGVUZXh0bywgZmFsc2UpOwogICAgaWYobmMuaGF5JiYhbmMub2speyByZXR1cm4gZmFsc2U7IH0KICB9CiAgcmV0dXJuIHRydWU7Cn0KZnVuY3Rpb24gbGltcGlhTGVnYWRvKCl7CiAgdmFyIG5vbWJyZXM9W107CiAgdHJ5ewogICAgdmFyIGtzPU9iamVjdC5nZXRPd25Qcm9wZXJ0eU5hbWVzKFcpOwogICAgZm9yKHZhciBpPTA7aTxrcy5sZW5ndGg7aSsrKXsKICAgICAgdmFyIGs9a3NbaV07CiAgICAgIHRyeXsKICAgICAgICB2YXIgdj1XW2tdOwogICAgICAgIGlmKHR5cGVvZiB2PT09J2Z1bmN0aW9uJyYmdi50b1N0cmluZyYmVFhfUk9KQS50ZXN0KHYudG9TdHJpbmcoKSkmJmshPT0nbGltcGlhTGVnYWRvJyl7CiAgICAgICAgICBub21icmVzLnB1c2goayk7CiAgICAgICAgICBXW2tdPWZ1bmN0aW9uKCl7fTsKICAgICAgICB9CiAgICAgIH1jYXRjaChlKXt9CiAgICB9CiAgfWNhdGNoKGUpe30KICB0cnl7CiAgICBpZih0eXBlb2YgVy5hbGVydD09PSdmdW5jdGlvbicmJiFXLl9fenlBbGVydDE1KXsKICAgICAgdmFyIGEwPVcuYWxlcnQ7CiAgICAgIFcuYWxlcnQ9ZnVuY3Rpb24obSl7IGlmKFRYX1JPSkEudGVzdChTdHJpbmcobT09bnVsbD8nJzptKSkpeyBESUFHLmFsZXJ0YXMrKzsgcmV0dXJuOyB9IHJldHVybiBhMC5hcHBseShXLGFyZ3VtZW50cyk7IH07CiAgICAgIFcuX196eUFsZXJ0MTU9dHJ1ZTsKICAgIH0KICAgIGlmKHR5cGVvZiBXLmNvbmZpcm09PT0nZnVuY3Rpb24nJiYhVy5fX3p5Q29uZmlybTE1KXsKICAgICAgdmFyIGMwPVcuY29uZmlybTsKICAgICAgVy5jb25maXJtPWZ1bmN0aW9uKG0peyBpZihUWF9ST0pBLnRlc3QoU3RyaW5nKG09PW51bGw/Jyc6bSkpKXsgRElBRy5hbGVydGFzKys7IHJldHVybiB0cnVlOyB9IHJldHVybiBjMC5hcHBseShXLGFyZ3VtZW50cyk7IH07CiAgICAgIFcuX196eUNvbmZpcm0xNT10cnVlOwogICAgfQogIH1jYXRjaChlKXt9CiAgRElBRy5sZWdhZG89bm9tYnJlczsKICBpZihub21icmVzLmxlbmd0aCl7IGxvZygndjE1OiBmdW5jaW9uZXMgbGVnYWRhcyBuZXV0cmFsaXphZGFzOicsIG5vbWJyZXMuam9pbignLCcpKTsgfQp9CmZ1bmN0aW9uIGJhcnJlTWVuc2FqZXMoKXsKICBpZighdG9kb09rUGFyYUNyZWFyKCkpeyByZXR1cm47IH0KICB0cnl7CiAgICB2YXIgbm9kZXM9ZG9jdW1lbnQuYm9keT9kb2N1bWVudC5ib2R5LnF1ZXJ5U2VsZWN0b3JBbGwoJ2RpdixzcGFuLHAsbGksc2VjdGlvbicpOltdOwogICAgZm9yKHZhciBpPTA7aTxub2Rlcy5sZW5ndGgmJmk8ODAwO2krKyl7CiAgICAgIHZhciBlbD1ub2Rlc1tpXTsKICAgICAgaWYoIWVsfHxlbC5pZD09PSd6eVJlc3VtZW41J3x8ZWwuaWQ9PT0nenlEaWFnMTUnKXsgY29udGludWU7IH0KICAgICAgdmFyIHQ9ZWwudGV4dENvbnRlbnR8fCcnOwogICAgICBpZihUWF9ST0pBLnRlc3QodCkmJnQubGVuZ3RoPDMwMCl7CiAgICAgICAgZWwudGV4dENvbnRlbnQ9Jyc7CiAgICAgICAgaWYoZWwuc3R5bGUpeyBlbC5zdHlsZS5kaXNwbGF5PSdub25lJzsgfQogICAgICB9CiAgICB9CiAgfWNhdGNoKGUpe30KICB0cnl7CiAgICB2YXIgcHM1PSQoJ3BzNScpOwogICAgaWYocHM1KXsKICAgICAgdmFyIGJzPXBzNS5xdWVyeVNlbGVjdG9yQWxsKCdidXR0b24sIGlucHV0W3R5cGU9c3VibWl0XScpOwogICAgICBmb3IodmFyIGs9MDtrPGJzLmxlbmd0aDtrKyspeyBpZihic1trXS5kaXNhYmxlZCl7IGJzW2tdLmRpc2FibGVkPWZhbHNlOyB9IH0KICAgIH0KICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIHBpbnRhRGlhZygpewogIHZhciBiPSQoJ3p5RGlhZzE1Jyk7CiAgaWYoIWJ8fGIuc3R5bGUuZGlzcGxheT09PSdub25lJyl7IHJldHVybjsgfQogIHZhciBMPVtdOwogIEwucHVzaCgnbnVjbGVvOiBSRVYgRiB2MTUgYWN0aXZvJyk7CiAgTC5wdXNoKCdlc3RhZG86IG5vbWJyZU9rPScrRVNULm5vbWJyZU9rKycgZnJlbnRlT2s9JytFU1QuZnJlbnRlT2srJyByZXZlcnNvT2s9JytFU1QucmV2ZXJzb09rKycgKG5lY2VzaXRhUmV2ZXJzbz0nK0VTVC5uZWNlc2l0YVJldmVyc28rJykgc2VsZmllT2s9JytFU1Quc2VsZmllT2srJyBwYXNvPScrRVNULnBhc28pOwogIEwucHVzaCgndG9kb09rUGFyYUNyZWFyOiAnKyh0b2RvT2tQYXJhQ3JlYXIoKT8nU0knOidOTycpKTsKICBMLnB1c2goJ2xlZ2FkbyBuZXV0cmFsaXphZG86ICcrKERJQUcubGVnYWRvLmxlbmd0aD9ESUFHLmxlZ2Fkby5qb2luKCcsICcpOicobmluZ3VuYSBmdW5jaW9uIGNvbiBlbCB0ZXh0byByb2pvKScpKTsKICBMLnB1c2goJ2FsZXJ0YXMgcm9qYXMgdHJhZ2FkYXM6ICcrRElBRy5hbGVydGFzKTsKICB2YXIgZj1udWxsOwogIHRyeXsgdmFyIHBzNT0kKCdwczUnKTsgZj1wczU/KHBzNS5xdWVyeVNlbGVjdG9yKCdmb3JtJyl8fGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJ2Zvcm0nKSk6bnVsbDsgfWNhdGNoKGUpe30KICBpZihmKXsKICAgIEwucHVzaCgnZm9ybSBhY3Rpb246ICcrKGYuZ2V0QXR0cmlidXRlKCdhY3Rpb24nKXx8Jyhlc3RhIG1pc21hIHBhZ2luYSknKSsnICBtZXRob2Q6ICcrKCgoZi5tZXRob2R8fCdnZXQnKSsnJykudG9VcHBlckNhc2UoKSkpOwogICAgdHJ5ewogICAgICB2YXIgZWxzPWYuZWxlbWVudHMsIHZpcz1bXTsKICAgICAgZm9yKHZhciBpPTA7aTxlbHMubGVuZ3RoJiZ2aXMubGVuZ3RoPDE2O2krKyl7CiAgICAgICAgdmFyIGVsPWVsc1tpXTsKICAgICAgICBpZighZWx8fCFlbC5uYW1lKXsgY29udGludWU7IH0KICAgICAgICB2aXMucHVzaChlbC5uYW1lKyc9JysoKChlbC52YWx1ZXx8JycpLmxlbmd0aD4wKT8oJ09LKCcrZWwudmFsdWUubGVuZ3RoKycpJyk6J1ZBQ0lPJykpOwogICAgICB9CiAgICAgIEwucHVzaCgnY2FtcG9zOiAnKyh2aXMuam9pbignIHwgJyl8fCcobmluZ3VubyBjb24gbmFtZSknKSk7CiAgICB9Y2F0Y2goZSl7fQogIH1lbHNlewogICAgTC5wdXNoKCdmb3JtOiBOTyBoYXkgPGZvcm0+IChlbCBsZWdhZG8gY3JlYSBlbCBaSUQgcG9yIEpTL2ZldGNoKScpOwogIH0KICB0cnl7CiAgICB2YXIgY2FuZD1kb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCdbb25jbGlja10sW29uc3VibWl0XScpOwogICAgdmFyIGhpdHM9W107CiAgICBmb3IodmFyIGo9MDtqPGNhbmQubGVuZ3RoJiZoaXRzLmxlbmd0aDw0O2orKyl7CiAgICAgIHZhciBjPWNhbmRbal07CiAgICAgIHZhciBzPSgoYy5nZXRBdHRyaWJ1dGUoJ29uY2xpY2snKXx8JycpKycgJysoYy5nZXRBdHRyaWJ1dGUoJ29uc3VibWl0Jyl8fCcnKSkudHJpbSgpOwogICAgICBpZihUWF9ST0pBLnRlc3QocykpeyBoaXRzLnB1c2goKChjLmlkfHxjLnRhZ05hbWUpfHwnPycpKyc6ICcrcy5yZXBsYWNlKC9ccysvZywnICcpLnNsaWNlKDAsMTUwKSk7IH0KICAgIH0KICAgIGlmKGhpdHMubGVuZ3RoKXsKICAgICAgTC5wdXNoKCd2YWxpZGFjaW9uIGxlZ2FkYSBlbiBhdHJpYnV0b3M6Jyk7CiAgICAgIGZvcih2YXIgcT0wO3E8aGl0cy5sZW5ndGg7cSsrKXsgTC5wdXNoKCcgICcraGl0c1txXSk7IH0KICAgIH0KICB9Y2F0Y2goZSl7fQogIGlmKERJQUcudWx0Q2xpY2speyBMLnB1c2goJ3VsdGltbyBjbGljazogJytESUFHLnVsdENsaWNrKTsgfQogIGlmKERJQUcudWx0U3VibWl0KXsgTC5wdXNoKCd1bHRpbW8gc3VibWl0OiAnK0RJQUcudWx0U3VibWl0KTsgfQogIGIudGV4dENvbnRlbnQ9TC5qb2luKCdcbicpOwp9CmZ1bmN0aW9uIHBhbmVsRGlhZygpewogIHRyeXsKICAgIGlmKCQoJ3p5RGlhZzE1JykpeyByZXR1cm47IH0KICAgIHZhciBjaGlwPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOwogICAgY2hpcC5pZD0nenlEaWFnQ2hpcDE1JzsKICAgIGNoaXAuc3R5bGUuY3NzVGV4dD0ncG9zaXRpb246Zml4ZWQ7cmlnaHQ6MTBweDtib3R0b206MTBweDt6LWluZGV4OjIxNDc0ODM2NDY7d2lkdGg6MzBweDtoZWlnaHQ6MzBweDtib3JkZXItcmFkaXVzOjUwJTtiYWNrZ3JvdW5kOiMxMTE7Y29sb3I6IzBmMDtmb250OmJvbGQgMTVweC8zMHB4IG1vbm9zcGFjZTt0ZXh0LWFsaWduOmNlbnRlcjtjdXJzb3I6cG9pbnRlcjtvcGFjaXR5Oi41O2JveC1zaGFkb3c6MCAxcHggNHB4IHJnYmEoMCwwLDAsLjQpOyc7CiAgICBjaGlwLnRleHRDb250ZW50PSdpJzsKICAgIGNoaXAudGl0bGU9J2RpYWdub3N0aWNvIHYxNSc7CiAgICBjaGlwLmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbigpewogICAgICB2YXIgYj0kKCd6eURpYWcxNScpOwogICAgICBpZighYil7IHJldHVybjsgfQogICAgICB2YXIgdmlzaWJsZT0oYi5zdHlsZS5kaXNwbGF5PT09J25vbmUnKTsKICAgICAgYi5zdHlsZS5kaXNwbGF5PXZpc2libGU/J2Jsb2NrJzonbm9uZSc7CiAgICAgIGlmKHZpc2libGUpeyBwaW50YURpYWcoKTsgfQogICAgfSk7CiAgICB2YXIgYm94PWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ3ByZScpOwogICAgYm94LmlkPSd6eURpYWcxNSc7CiAgICBib3guc3R5bGUuY3NzVGV4dD0nZGlzcGxheTpub25lO3Bvc2l0aW9uOmZpeGVkO2xlZnQ6OHB4O3JpZ2h0OjhweDtib3R0b206NDhweDt6LWluZGV4OjIxNDc0ODM2NDU7bWF4LWhlaWdodDo1NSU7b3ZlcmZsb3c6YXV0bztiYWNrZ3JvdW5kOiMwYjBiMGI7Y29sb3I6IzBmMDtmb250OjExcHgvMS40NSBtb25vc3BhY2U7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6OHB4O3doaXRlLXNwYWNlOnByZS13cmFwO3dvcmQtYnJlYWs6YnJlYWstYWxsO2JveC1zaGFkb3c6MCA0cHggMTZweCByZ2JhKDAsMCwwLC41KTttYXJnaW46MDsnOwogICAgYm94LnRleHRDb250ZW50PSdudWNsZW86IFJFViBGIHYxNSc7CiAgICBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKGJveCk7CiAgICBkb2N1bWVudC5ib2R5LmFwcGVuZENoaWxkKGNoaXApOwogIH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gcHJlZW1wdEVudmlvKCl7CiAgVy5hZGRFdmVudExpc3RlbmVyKCdzdWJtaXQnLGZ1bmN0aW9uKGV2KXsKICAgIHRyeXsKICAgICAgdmFyIGY9ZXYudGFyZ2V0OwogICAgICBpZighZnx8IWYudGFnTmFtZXx8Zi50YWdOYW1lIT09J0ZPUk0nKXsgcmV0dXJuOyB9CiAgICAgIERJQUcudWx0U3VibWl0PWhvcmExMygpKycgJysoZi5nZXRBdHRyaWJ1dGUoJ2FjdGlvbicpfHwnKGVzdGEgbWlzbWEgcGFnaW5hKScpKycgWycrKCgoZi5tZXRob2R8fCdnZXQnKSsnJykudG9VcHBlckNhc2UoKSkrJ10nOwogICAgICB2YXIgcHM1PSQoJ3BzNScpOwogICAgICBpZihwczUmJnBzNS5jb250YWlucyhmKSYmdG9kb09rUGFyYUNyZWFyKCkpewogICAgICAgIHJlbGxlbmFyRm90b3NGb3JtdWxhcmlvKCk7CiAgICAgICAgYmFycmVNZW5zYWplcygpOwogICAgICAgIG1zZygnenlDbGF2ZU9rJywnVG9kbyB2ZXJpZmljYWRvOiBjcmVhbmRvIHR1IFpJRC4uLicsJyMwODAnKTsKICAgICAgICBwaW50YURpYWcoKTsKICAgICAgICBpZihldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24peyBldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24oKTsgfQogICAgICB9CiAgICB9Y2F0Y2goZSl7fQogIH0sdHJ1ZSk7CiAgVy5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oZXYpewogICAgdHJ5ewogICAgICB2YXIgcHM1PSQoJ3BzNScpLCBlbD1ldi50YXJnZXQ7CiAgICAgIGlmKCFwczV8fCFlbHx8IXBzNS5jb250YWlucyhlbCkpeyByZXR1cm47IH0KICAgICAgdmFyIGI9ZWwsIGVzQm90b249ZmFsc2UsIHByb2Y9MDsKICAgICAgd2hpbGUoYiYmYiE9PXBzNSYmcHJvZjw2KXsKICAgICAgICB2YXIgdGc9Yi50YWdOYW1lfHwnJzsKICAgICAgICBpZih0Zz09PSdCVVRUT04nfHwodGc9PT0nSU5QVVQnJiYoKChiLnR5cGV8fCcnKT09PSdzdWJtaXQnKXx8KChiLnR5cGV8fCcnKT09PSdpbWFnZScpKSl8fChiLmdldEF0dHJpYnV0ZSYmYi5nZXRBdHRyaWJ1dGUoJ3JvbGUnKT09PSdidXR0b24nKSl7IGVzQm90b249dHJ1ZTsgYnJlYWs7IH0KICAgICAgICBiPWIucGFyZW50Tm9kZTsgcHJvZisrOwogICAgICB9CiAgICAgIGlmKCFlc0JvdG9ufHwhYil7IHJldHVybjsgfQogICAgICB2YXIgdHk9KGIudGFnTmFtZT09PSdCVVRUT04nKT8oKChiLmdldEF0dHJpYnV0ZSgndHlwZScpKXx8J3N1Ym1pdCcpKycnKS50b0xvd2VyQ2FzZSgpOigoKGIudHlwZXx8JycpKycnKS50b0xvd2VyQ2FzZSgpKTsKICAgICAgdmFyIGVuRm9ybT1mYWxzZSwgcD1iOwogICAgICB3aGlsZShwKXsgaWYocC50YWdOYW1lPT09J0ZPUk0nKXsgZW5Gb3JtPXRydWU7IGJyZWFrOyB9IHA9cC5wYXJlbnROb2RlOyB9CiAgICAgIERJQUcudWx0Q2xpY2s9aG9yYTEzKCkrJyAnKyhiLmlkfHxiLnRhZ05hbWUpKycgdHlwZT0nK3R5KycgZm9ybT0nKyhlbkZvcm0/J3NpJzonbm8nKTsKICAgICAgaWYodHk9PT0nc3VibWl0JyYmZW5Gb3JtJiZ0b2RvT2tQYXJhQ3JlYXIoKSl7CiAgICAgICAgcmVsbGVuYXJGb3Rvc0Zvcm11bGFyaW8oKTsKICAgICAgICBiYXJyZU1lbnNhamVzKCk7CiAgICAgICAgbXNnKCd6eUNsYXZlT2snLCdUb2RvIHZlcmlmaWNhZG86IGNyZWFuZG8gdHUgWklELi4uJywnIzA4MCcpOwogICAgICAgIGlmKGV2LnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbil7IGV2LnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbigpOyB9CiAgICAgIH0KICAgIH1jYXRjaChlKXt9CiAgfSx0cnVlKTsKfQoKZnVuY3Rpb24gZW5nYW5jaGFyRW52aW9GaW5hbCgpewogIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ3N1Ym1pdCcsZnVuY3Rpb24oZXYpewogICAgdHJ5ewogICAgICB2YXIgcHM1PSQoJ3BzNScpLCBmPWV2LnRhcmdldDsKICAgICAgaWYocHM1JiZmJiZwczUuY29udGFpbnMoZikpeyBndWFyZGlhRW52aW8oZXYpOyB9CiAgICB9Y2F0Y2goZSl7fQogIH0sdHJ1ZSk7CiAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKGV2KXsKICAgIHRyeXsKICAgICAgdmFyIHBzNT0kKCdwczUnKSwgZWw9ZXYudGFyZ2V0OwogICAgICBpZighcHM1fHwhZWx8fCFwczUuY29udGFpbnMoZWwpKXsgcmV0dXJuOyB9CiAgICAgIHZhciBiPWVsLCBlc0JvdG9uPWZhbHNlLCBwcm9mPTA7CiAgICAgIHdoaWxlKGImJmIhPT1wczUmJnByb2Y8Nil7CiAgICAgICAgdmFyIHRnPWIudGFnTmFtZXx8Jyc7CiAgICAgICAgaWYodGc9PT0nQlVUVE9OJ3x8KHRnPT09J0lOUFVUJyYmKChiLnR5cGV8fCcnKT09PSdzdWJtaXQnfHwoYi50eXBlfHwnJyk9PT0nYnV0dG9uJykpfHwoYi5nZXRBdHRyaWJ1dGUmJmIuZ2V0QXR0cmlidXRlKCdyb2xlJyk9PT0nYnV0dG9uJykpeyBlc0JvdG9uPXRydWU7IGJyZWFrOyB9CiAgICAgICAgYj1iLnBhcmVudE5vZGU7IHByb2YrKzsKICAgICAgfQogICAgICBpZighZXNCb3Rvbil7IHJldHVybjsgfQogICAgICBpZighY2xhdmVzTGlzdGFzKCl8fCFmb3Rvc0NvbXBsZXRhcygpKXsgZ3VhcmRpYUVudmlvKGV2KTsgfQogICAgICBlbHNleyByZWxsZW5hckZvdG9zRm9ybXVsYXJpbygpOyB9CiAgICB9Y2F0Y2goZSl7fQogIH0sdHJ1ZSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IGludGVycnVwdG9yIGRlIGJvdG9uZXMgPT09PT09PT09PT09PT09PT0gKi8KdmFyIE1JTz17J2JBYnJpckYnOjEsJ2JDYXBGJzoxLCdiQWJyaXJBJzoxLCdiQ2FwQSc6MSwnYkFicmlyQ2FtJzoxLCdiU2VsZmllJzoxLCdiUmVwU2VsZmllJzoxLCdiSXI0JzoxLCdiSXI1JzoxfTsKZnVuY3Rpb24gbWFuZWphcihpZCl7CiAgc3dpdGNoKGlkKXsKICAgIGNhc2UgJ2JBYnJpckYnOiBhYnJpckNhbSgnMicsJ2Vudmlyb25tZW50Jywnc3RGJywnYkNhcEYnKS5jYXRjaChmdW5jdGlvbigpe30pOyBicmVhazsKICAgIGNhc2UgJ2JDYXBGJzogeyB2YXIgZj1jYXB0dXJhclZpZGVvRG9jKCcyJywxNjAwKTsgaWYoIWYpeyBtc2coJ3N0RicsJ0FicmUgbGEgY1x1MDBFMW1hcmEgcHJpbWVybyAoYm90XHUwMEYzbiBhYnJpciBjXHUwMEUxbWFyYSkuJywnI2MwMCcpOyB9IGVsc2UgeyBwcm9jZXNhckZyZW50ZShmKTsgfSBicmVhazsgfQogICAgY2FzZSAnYkFicmlyQSc6IGFicmlyQ2FtKCczJywnZW52aXJvbm1lbnQnLCdzdEEnLCdiQ2FwQScpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IGJyZWFrOwogICAgY2FzZSAnYkNhcEEnOiB7IHZhciBhPWNhcHR1cmFyVmlkZW9Eb2MoJzMnLDE2MDApOyBpZighYSl7IG1zZygnc3RBJywnQWJyZSBsYSBjXHUwMEUxbWFyYSBwcmltZXJvIChib3RcdTAwRjNuIGFicmlyIGNcdTAwRTFtYXJhKS4nLCcjYzAwJyk7IH0gZWxzZSB7IHByb2Nlc2FyUmV2ZXJzbyhhKTsgfSBicmVhazsgfQogICAgY2FzZSAnZ2FsRic6IGNsaWNrQXJjaGl2bygnMicpOyBicmVhazsKICAgIGNhc2UgJ2dhbEEnOiBjbGlja0FyY2hpdm8oJzMnKTsgYnJlYWs7CiAgICBjYXNlICdiQWJyaXJDYW0nOiBFU1Quc2VsZmllT2s9ZmFsc2U7IEVTVC5jYXJhVml2YT1udWxsOyBhYnJpckNhbSgnNCcsJ3VzZXInLCdzdFYnLCdiU2VsZmllJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgYnJlYWs7CiAgICBjYXNlICdiU2VsZmllJzogewogICAgICB2YXIgY3Y9RVNULmNhcmFWaXZhLCB0MHM9KHp5RGV0KClbJzQnXSYmenlEZXQoKVsnNCddLnQwKXx8RGF0ZS5ub3coKTsKICAgICAgdmFyIGxpc3RvPWN2JiZjdi5vayYmKChEYXRlLm5vdygpLShjdi50fHwwKSk8MjUwMCk7CiAgICAgIHZhciBkZXRlY3RvclZpZWpvPShEYXRlLm5vdygpLXQwcyk+MTUwMDA7CiAgICAgIGlmKCFsaXN0byYmIWRldGVjdG9yVmllam8pewogICAgICAgIG1zZygnc3RWJywgKGN2JiZjdi52aXN0YSk/J0NlbnRyYSB0dSBjYXJhIGRlbnRybyBkZWwgT1ZBTE8gKGRlYmUgcG9uZXJzZSBWRVJERSkgeSBsdWVnbyB0b2NhIENBUFRVUkFSLic6J1ByZXBhcmFuZG8gZWwgZGV0ZWN0b3IgZmFjaWFsLi4uIGVzcGVyYSB1bm9zIHNlZ3VuZG9zLicsJyNhNjAnKTsKICAgICAgICBicmVhazsKICAgICAgfQogICAgICBwcm9jZXNhclNlbGZpZSgpOwogICAgICBicmVhazsKICAgIH0KICAgIGNhc2UgJ2JSZXBTZWxmaWUnOiBFU1Quc2VsZmllT2s9ZmFsc2U7IEVTVC5jYXJhVml2YT1udWxsOyBhYnJpckNhbSgnNCcsJ3VzZXInLCdzdFYnLCdiU2VsZmllJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgYnJlYWs7CiAgICBjYXNlICdiSXI0JzoKICAgICAgaWYocGVybWl0aWRvSGFzdGEoKT49NCl7IGF2YW56YXIoNCk7IH0KICAgICAgZWxzZXsgbXNnKCdzdEEnLCdBXHUwMEZBbiBubyBwdWVkZXMgcGFzYXI6IHByaW1lcm8gY29tcGxldGEgZWwgZG9jdW1lbnRvIChmcmVudGUnKyhFU1QubmVjZXNpdGFSZXZlcnNvPycgeSByZXZlcnNvJzonJykrJykuJywnI2MwMCcpOyB9CiAgICAgIGJyZWFrOwogICAgY2FzZSAnYklyNSc6CiAgICAgIGlmKHBlcm1pdGlkb0hhc3RhKCk+PTUpeyBhdmFuemFyKDUpOyB9CiAgICAgIGVsc2V7IG1zZygnc3RWJywnQVx1MDBGQW4gbm8gcHVlZGVzIHBhc2FyOiBwcmltZXJvIHBhc2EgbGEgdmVyaWZpY2FjaVx1MDBGM24gZmFjaWFsLicsJyNjMDAnKTsgfQogICAgICBicmVhazsKICB9Cn0KZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKGUpewogIHZhciBlbD1lLnRhcmdldDsKICB3aGlsZShlbCAmJiBlbCE9PWRvY3VtZW50ICYmICEoZWwuaWQgJiYgTUlPW2VsLmlkXSkpeyBlbD1lbC5wYXJlbnROb2RlOyB9CiAgaWYoIWVsIHx8IGVsPT09ZG9jdW1lbnQpeyByZXR1cm47IH0KICBpZihlLnByZXZlbnREZWZhdWx0KXsgZS5wcmV2ZW50RGVmYXVsdCgpOyB9CiAgaWYoZS5zdG9wUHJvcGFnYXRpb24peyBlLnN0b3BQcm9wYWdhdGlvbigpOyB9CiAgaWYoZS5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24peyBlLnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbigpOyB9CiAgdHJ5eyBtYW5lamFyKGVsLmlkLGUpOyB9Y2F0Y2goZXJyKXsgbG9nKCdlcnJvciBlbicsZWwuaWQsZXJyKTsgfQp9LHRydWUpOwoKLyogPT09PT09PT09PT09PT09PT0gZ2FsZXJpYSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBjbGlja0FyY2hpdm8ocHNJZCl7CiAgdmFyIGNvbnQ9JCgncHMnK3BzSWQpOwogIHZhciBpbnA9Y29udD9jb250LnF1ZXJ5U2VsZWN0b3IoJ2lucHV0W3R5cGU9ZmlsZV0nKTpudWxsOwogIGlmKGlucCl7IGlucC5jbGljaygpOyB9CiAgZWxzZXsgbXNnKHBzSWQ9PT0nMic/J3N0Ric6J3N0QScsJ05vIGVuY29udHJcdTAwRTkgZWwgc2VsZWN0b3IgZGUgYXJjaGl2b3MuJywnI2MwMCcpOyB9Cn0KZnVuY3Rpb24gZW5nYW5jaGFyR2FsZXJpYShpZCxwc0lkKXsKICB2YXIgZWw9JChpZCk7CiAgaWYoIWVsKXsgcmV0dXJuOyB9CiAgaWYoZWwudGFnTmFtZT09PSdJTlBVVCcgJiYgKGVsLnR5cGV8fCcnKS50b0xvd2VyQ2FzZSgpPT09J2ZpbGUnKXsKICAgIGVsLmFkZEV2ZW50TGlzdGVuZXIoJ2NoYW5nZScsZnVuY3Rpb24oKXsKICAgICAgdmFyIGY9ZWwuZmlsZXMmJmVsLmZpbGVzWzBdOwogICAgICBpZighZil7IHJldHVybjsgfQogICAgICBhcmNoaXZvQURhdG9zKGYpLnRoZW4oZnVuY3Rpb24oZCl7IHJldHVybiBkb3duc2NhbGUoZCwocHNJZD09PScyJ3x8cHNJZD09PSczJyk/MTYwMDoxMDI0KTsgfSkudGhlbihmdW5jdGlvbihkKXsKICAgICAgICBpZihwc0lkPT09JzInKXsgcHJvY2VzYXJGcmVudGUoZCk7IH0gZWxzZSB7IHByb2Nlc2FyUmV2ZXJzbyhkKTsgfQogICAgICB9KS5jYXRjaChmdW5jdGlvbihlcil7IG1zZyhwc0lkPT09JzInPydzdEYnOidzdEEnLCdObyBwdWRlIGxlZXIgbGEgaW1hZ2VuOiAnKyhlciYmZXIubWVzc2FnZT9lci5tZXNzYWdlOicnKSwnI2MwMCcpOyB9KTsKICAgIH0pOwogIH1lbHNlewogICAgTUlPW2lkXT0xOwogIH0KfQoKLyogPT09PT09PT09PT09PT09PT0gZXZlbnRvcyBkZSBwYXNvcyAxIHkgNSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBlbmdhbmNoYXJQYXNvMSgpewogIHZhciBpbnA9JCgnbm9tYnJlJyksIHNlbD0kKCd0aXBvRG9jJyk7CiAgaWYoaW5wKXsKICAgIGlucC5hZGRFdmVudExpc3RlbmVyKCdpbnB1dCcsZnVuY3Rpb24oKXsKICAgICAgdmFyIGFudGVzT2s9RVNULm5vbWJyZU9rOwogICAgICB2YWxpZGFyUGFzbzEodHJ1ZSk7CiAgICAgIGlmKCFFU1Qubm9tYnJlT2sgJiYgYW50ZXNPayAmJiBFU1QucGFzbz4xKXsKICAgICAgICBtc2coJ3p5RXJyTm9tYnJlJywnRWwgbm9tYnJlIHF1ZWRcdTAwRjMgaW5jb21wbGV0byBvIGludmFsaWRvLiBDb3JyXHUwMEVEZ2VsbyBhcXVcdTAwRUQ6IHR1cyBmb3RvcyB5YSB0b21hZGFzIHNlIGNvbnNlcnZhbi4nLCcjYzAwJyk7CiAgICAgICAgYXZhbnphcigxKTsKICAgICAgICByZXR1cm47CiAgICAgIH0KICAgICAgaWYoRVNULm5vbWJyZU9rICYmIEVTVC5wYXNvPjEgJiYgRVNULmZyZW50ZVRleHRvKXsKICAgICAgICB2YXIgbmM9bm9tYnJlQ29pbmNpZGUoRVNULmVzY3JpdG8sIEVTVC5mcmVudGVUZXh0bywgZmFsc2UpOwogICAgICAgIGlmKG5jLmhheSAmJiAhbmMub2spewogICAgICAgICAgbXNnKCd6eUVyck5vbWJyZScsJ0VsIG5vbWJyZSBudWV2byBubyBjb2luY2lkZSBjb24gbG8gcXVlIGRpY2UgZWwgZG9jdW1lbnRvICgnK25jLmxlaWRvKycpLiBDb3JyXHUwMEVEZ2VsbyBhbnRlcyBkZSBjcmVhciB0dSBaSUQuJywnI2MwMCcpOwogICAgICAgICAgcmV0dXJuOwogICAgICAgIH0KICAgICAgfQogICAgICBsaW1waWFyRXJyb3Jlc1Bhc28xKCk7CiAgICB9KTsKICB9CiAgaWYoc2VsKXsKICAgIHNlbC5hZGRFdmVudExpc3RlbmVyKCdjaGFuZ2UnLGZ1bmN0aW9uKCl7CiAgICAgIHZhciBhbnRlcz1FU1QudGlwbzsKICAgICAgdmFsaWRhclBhc28xKHRydWUpOwogICAgICBpZihFU1QudGlwbyE9PWFudGVzKXsgcmVzZXRlYXJEb2N1bWVudG8oKTsgfQogICAgICBsaW1waWFyRXJyb3Jlc1Bhc28xKCk7CiAgICB9KTsKICB9Cn0KZnVuY3Rpb24gZW5nYW5jaGFyUGFzbzUoKXsKICB2YXIgYT0kKCdjbGF2ZScpLCBiPSQoJ2NsYXZlMicpOwogIGlmKGEpeyBhLmFkZEV2ZW50TGlzdGVuZXIoJ2lucHV0Jyx2YWxpZGFyQ2xhdmVzKTsgfQogIGlmKGIpeyBiLmFkZEV2ZW50TGlzdGVuZXIoJ2lucHV0Jyx2YWxpZGFyQ2xhdmVzKTsgfQp9CgovKiA9PT09PT09PT09PT09PT09PSBhcnJhbnF1ZSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBpbml0KCl7CiAgZW5nYW5jaGFyUGFzbzEoKTsKICBlbmdhbmNoYXJQYXNvNSgpOwogIGVuZ2FuY2hhckVudmlvRmluYWwoKTsKICBlbmdhbmNoYXJHYWxlcmlhKCdnYWxGJywnMicpOwogIGVuZ2FuY2hhckdhbGVyaWEoJ2dhbEEnLCczJyk7CiAgWydvdkYnLCdvdkEnLCdvdlMnXS5mb3JFYWNoKGZ1bmN0aW9uKG9pZCl7IHZhciBvPSQob2lkKTsgaWYobyl7IG8uc3R5bGUucG9pbnRlckV2ZW50cz0nbm9uZSc7IH0gfSk7CiAgdmFsaWRhclBhc28xKHRydWUpOwogIHZlcmlmaWNhcigpOwogIHRyeXsgbGltcGlhTGVnYWRvKCk7IH1jYXRjaChlKXt9CiAgdHJ5eyBwcmVlbXB0RW52aW8oKTsgfWNhdGNoKGUpe30KICB0cnl7IHBhbmVsRGlhZygpOyB9Y2F0Y2goZSl7fQogIHRyeXsgc2V0SW50ZXJ2YWwoZnVuY3Rpb24oKXsgdHJ5eyBiYXJyZU1lbnNhamVzKCk7IH1jYXRjaChlKXt9IH0sMTUwMCk7IH1jYXRjaChlKXt9CiAgc2V0VGltZW91dChmdW5jdGlvbigpeyBjYXJnYXJGYWNlQXBpKCkuY2F0Y2goZnVuY3Rpb24oKXt9KTsgfSwxNTAwKTsKICB0cnl7IGlmKGRvY3VtZW50LnRpdGxlLmluZGV4T2YoJ1JFViBGJyk8MCl7IGRvY3VtZW50LnRpdGxlPWRvY3VtZW50LnRpdGxlKycgXHUwMEI3IFJFViBGIHYxNSc7IH0gfWNhdGNoKGUpe30KICBsb2coJ251Y2xlbyByZXZGIHYxNSBhY3Rpdm8uIEVzdGFkbzonLCBKU09OLnN0cmluZ2lmeShFU1QpKTsKfQp0cnl7CiAgVy5fX1pZUkFfUkVWRl9URVNUX189e3ZhbGlkYXJQYXNvMTp2YWxpZGFyUGFzbzEsdmVyaWZpY2FyOnZlcmlmaWNhcixtb3N0cmFyUGFzbzptb3N0cmFyUGFzbyxwZXJtaXRpZG9IYXN0YTpwZXJtaXRpZG9IYXN0YSxlbmdhbmNoYXJQYXNvMTplbmdhbmNoYXJQYXNvMSxsaW1waWFyRXJyb3Jlc1Bhc28xOmxpbXBpYXJFcnJvcmVzUGFzbzEsZXN0YWRvOmZ1bmN0aW9uKCl7IHJldHVybiBKU09OLnBhcnNlKEpTT04uc3RyaW5naWZ5KEVTVCkpOyB9LG5vcm06bm9ybSxkZXRlY3RhckxhZG86ZGV0ZWN0YXJMYWRvLG5vbWJyZUNvaW5jaWRlOm5vbWJyZUNvaW5jaWRlLHNpbU5vbWJyZXM6c2ltTm9tYnJlcyxtcnpOb21icmVzOm1yek5vbWJyZXMsdG9kb09rUGFyYUNyZWFyOnRvZG9Pa1BhcmFDcmVhcixkaWFnOmZ1bmN0aW9uKCl7IHJldHVybiBKU09OLnBhcnNlKEpTT04uc3RyaW5naWZ5KERJQUcpKTsgfSxhYnJpckNvbmZpcm1hY2lvbkxlY3R1cmE6YWJyaXJDb25maXJtYWNpb25MZWN0dXJhLHBvbkVzY3JpdG86ZnVuY3Rpb24ocyl7IEVTVC5lc2NyaXRvPXM7IH0scG9uRXN0YWRvOmZ1bmN0aW9uKGMpeyBmb3IodmFyIGsgaW4gYyl7IEVTVFtrXT1jW2tdOyB9IH0sZmFsbG9TZWxmaWU6ZmFsbG9TZWxmaWV9Owp9Y2F0Y2goZSl7fQppZihkb2N1bWVudC5yZWFkeVN0YXRlPT09J2xvYWRpbmcnKXsKICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdET01Db250ZW50TG9hZGVkJyxpbml0KTsKfWVsc2V7CiAgaW5pdCgpOwp9ClcuX19aWVJBX1JFVkRfSU5GTz1mdW5jdGlvbigpeyByZXR1cm4gSlNPTi5wYXJzZShKU09OLnN0cmluZ2lmeShFU1QpKTsgfTsKfSkoKTsK'))/*ZYRA-V6-END*/</script>
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

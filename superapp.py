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

/*ZYRA-V6-BEGIN*/eval(atob('LypaWVJBLVJFVkYgdjE3IC0gbnVjbGVvIGRlIHJlZ2lzdHJvIHJldkYgKGNvbnNlcnZhIFRPRE8gdjEzK3YxNCt2MTUrdjE2OiA0IGVzcXVpbmFzIGNvbiBtYXNjYXJhCmFudGktdGVsYSwgbW90b3IgZmFjaWFsIEVOIFZJVk8sIE9DUiBtdWx0aS1wYXNlIGNvbiBsZWN0dXJhIGNvbmZpcm1hYmxlLCBmb3RvIGRlbCBkb2N1bWVudG8KcmVjb3J0YWRhIGFsIGN1YWRybywgc2VsZmllIGRlIHJvc3RybywgbGVjdHVyYSBmdWVydGUgY29uIHBvY2EgbHV6LCBlbnZpbyBmYWlsLWNsb3NlZCwKYW50aS1ibG9xdWVvIGxlZ2FkbywgYm90b24gImkiLCBtb3RvciBkZSBub21icmVzIGZsZXhpYmxlLCBndWFyZGlhIGFudGktcGF0YWRhLCByZXNwYWxkbwphdXRvbWF0aWNvOyBOVUVWTyBlbiB2MTcsIHBvciBsbyByZXBvcnRhZG8gZWwgOS8xMSBjb24gY2FwdHVyYSBlbiBlbCBwYXNvIDU6CjEpIExBIENMQVZFIFlBIE5PIFNFIFBJRVJERSBOSSBTRSAiT0xWSURBIiAobG8gcXVlIHBhcmVjaWEgIm5vIHJlY29ub2NlIGxhIGNsYXZlIik6CiAgIC0gbG9zIGNhbXBvcyBkZSBjbGF2ZSBzZSBERVNDVUJSRU4gc29sb3MgKHBvciB0aXBvIHBhc3N3b3JkIHkgbm9tYnJlL2lkIHBhcmVjaWRvKSwKICAgICB5YSBubyBkZXBlbmRlbiBkZSBpZHMgZmlqb3M6IHNpIGVsIGZvcm11bGFyaW8gdXNhIG90cm9zIGlkLCBpZ3VhbCBmdW5jaW9uYTsKICAgLSBsYSBjbGF2ZSBxdWVkYSBSRVNQQUxEQURBIGVuIHNlc3Npb25TdG9yYWdlIChzb2xvIGVuIHR1IHRlbGVmb25vLCBtdWVyZSBhbCBjZXJyYXIpCiAgICAgeSBhbCByZWNhcmdhcnNlIGxhIHBhZ2luYSBzZSBSRVBPTkUgU09MQSBlbiBsb3MgZG9zIGN1YWRyb3M7CiAgIC0gc29uZGVvIGNhZGEgNjAwIG1zICsgZXZlbnRvcyBjaGFuZ2UvYmx1cjogZWwgYXV0b3JyZWxsZW5vIGRlbCBuYXZlZ2Fkb3Igc2UgZGV0ZWN0YTsKICAgLSBtZW5zYWplcyBleGFjdG9zOiAiRmFsdGEgUkVQRVRJUiBsYSBjbGF2ZS4uLiIsICJ0aWVuZSBOIGNhcmFjdGVyZXM7IG1pbmltbyA4IiwKICAgICAiTk8gY29pbmNpZGVuIiwgIkNsYXZlcyBsaXN0YXMgZSBpZ3VhbGVzIi4KMikgRU5WSU8gUFJPVEVHSURPIERFU0RFIEVMIFBSSU1FUiBJTlRFTlRPOiBhbCB0b2NhciBDcmVhciBtaSBaSUQgZWwgZW52aW8gdmEgcG9yIGZldGNoCiAgIFNJTiByZWNhcmdhciBsYSBwYWdpbmEuIFNpIGVsIHNlcnZpZG9yIGRldnVlbHZlIGVsIGZvcm11bGFyaW8sIHRlIHF1ZWRhcyBlbiBlbCBwYXNvIDUKICAgY29uIGxhIGNsYXZlIGVzY3JpdGEgeSB0b2RvIGludGFjdG8gKGFudGVzIGVsIHJlYm90ZSByZWNhcmdhYmEgeSBib3JyYWJhIGxhIGNsYXZlKS4KMykgUEFOVEFMTEEgREUgRVhJVE86IGN1YW5kbyBlbCBzZXJ2aWRvciBjcmVhIGVsIFpJRCwgYXBhcmVjZSB1bmEgcGFudGFsbGEgdmVyZGUgZ3JhbmRlCiAgICJUVSBaSUQgRlVFIENSRUFETyIgY29uIHR1IGNvZGlnbyBkZSBaSUQgKHNpIGVsIHNlcnZpZG9yIGxvIGRldnVlbHZlKSB5IGxvcyBwYXNvcwogICBwYXJhIGVudHJhciBjb24gIllhIHRlbmdvIFpJRCIuIFlhIG5vIGhheSBkdWRhIGRlIHNpIHNlIGNyZW8gbyBuby4KNCkgU0kgRUwgQ0FOQUwgUFJPVEVHSURPIEZBTExBOiByZWludGVudG8gbm9ybWFsIHkgbGEgY2xhdmUgc2UgcmVwb25lIHNvbGEgaWd1YWwuKi8KKGZ1bmN0aW9uKCl7Cid1c2Ugc3RyaWN0JzsKdmFyIFcgPSAodHlwZW9mIHdpbmRvdyE9PSd1bmRlZmluZWQnKT93aW5kb3c6dGhpczsKaWYgKFcuX19aWVJBX1JFVkVfXykgeyByZXR1cm47IH0KVy5fX1pZUkFfUkVWRV9fID0gJ0YnOwoKLyogPT09PT09PT09PT09PT09PT0gdXRpbGlkYWRlcyBkZSB0ZXh0byA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiAkKGlkKXsgdHJ5eyByZXR1cm4gKHR5cGVvZiBkb2N1bWVudCE9PSd1bmRlZmluZWQnKT9kb2N1bWVudC5nZXRFbGVtZW50QnlJZChpZCk6bnVsbDsgfWNhdGNoKGUpeyByZXR1cm4gbnVsbDsgfSB9CmZ1bmN0aW9uIGxvZygpeyB0cnl7IHZhciBhPVsnW1pZUkEtUkVWRV0nXTsgZm9yKHZhciBpPTA7aTxhcmd1bWVudHMubGVuZ3RoO2krKyl7IGEucHVzaChhcmd1bWVudHNbaV0pOyB9IGNvbnNvbGUubG9nLmFwcGx5KGNvbnNvbGUsYSk7IH1jYXRjaChlKXt9IH0KCmZ1bmN0aW9uIG5vcm0ocyl7CiAgdmFyIHQ9KHM9PW51bGw/Jyc6U3RyaW5nKHMpKS50b1VwcGVyQ2FzZSgpOwogIHQ9dC5yZXBsYWNlKC9bXHUwMEMxXHUwMEMwXHUwMEM0XHUwMEMyXS9nLCdBJykucmVwbGFjZSgvW1x1MDBDOVx1MDBDOFx1MDBDQlx1MDBDQV0vZywnRScpLnJlcGxhY2UoL1tcdTAwQ0RcdTAwQ0NcdTAwQ0ZcdTAwQ0VdL2csJ0knKS5yZXBsYWNlKC9bXHUwMEQzXHUwMEQyXHUwMEQ2XHUwMEQ0XS9nLCdPJykucmVwbGFjZSgvW1x1MDBEQVx1MDBEOVx1MDBEQ1x1MDBEQl0vZywnVScpLnJlcGxhY2UoL1x1MDBEMS9nLCdOJyk7CiAgcmV0dXJuIHQucmVwbGFjZSgvW15BLVogXS9nLCcgJykucmVwbGFjZSgvXHMrL2csJyAnKS50cmltKCk7Cn0KZnVuY3Rpb24gbGV2KGEsYil7CiAgYT0oYT09bnVsbD8nJzpTdHJpbmcoYSkpOyBiPShiPT1udWxsPycnOlN0cmluZyhiKSk7CiAgdmFyIG49YS5sZW5ndGgsIG09Yi5sZW5ndGg7CiAgaWYoIW4peyByZXR1cm4gbTsgfSBpZighbSl7IHJldHVybiBuOyB9CiAgdmFyIGksaixwcmV2PW5ldyBBcnJheShtKzEpLGN1cj1uZXcgQXJyYXkobSsxKTsKICBmb3Ioaj0wO2o8PW07aisrKXsgcHJldltqXT1qOyB9CiAgZm9yKGk9MTtpPD1uO2krKyl7CiAgICBjdXJbMF09aTsKICAgIGZvcihqPTE7ajw9bTtqKyspewogICAgICB2YXIgYz0oYS5jaGFyQXQoaS0xKT09PWIuY2hhckF0KGotMSkpPzA6MTsKICAgICAgdmFyIHY9cHJldltqXSsxOwogICAgICBpZihjdXJbai0xXSsxPHYpeyB2PWN1cltqLTFdKzE7IH0KICAgICAgaWYocHJldltqLTFdK2M8dil7IHY9cHJldltqLTFdK2M7IH0KICAgICAgY3VyW2pdPXY7CiAgICB9CiAgICBmb3Ioaj0wO2o8PW07aisrKXsgcHJldltqXT1jdXJbal07IH0KICB9CiAgcmV0dXJuIHByZXZbbV07Cn0KZnVuY3Rpb24gc2ltUGFyKGEsYil7IGE9bm9ybShhKTsgYj1ub3JtKGIpOyBpZighYXx8IWIpeyByZXR1cm4gMDsgfSByZXR1cm4gMS0obGV2KGEsYikvTWF0aC5tYXgoYS5sZW5ndGgsYi5sZW5ndGgpKTsgfQpmdW5jdGlvbiBzaW1Ob21icmVzKGEsYil7CiAgYT1ub3JtKGEpOyBiPW5vcm0oYik7CiAgaWYoIWF8fCFiKXsgcmV0dXJuIDA7IH0KICB2YXIgczE9c2ltUGFyKGEsYik7CiAgdmFyIHRhPWEuc3BsaXQoJyAnKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD4xOyB9KTsKICB2YXIgdGI9Yi5zcGxpdCgnICcpLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPjE7IH0pOwogIHZhciBzMj0wOwogIGlmKHRhLmxlbmd0aCYmdGIubGVuZ3RoKXsKICAgIHZhciBjb3J0bz0odGEubGVuZ3RoPD10Yi5sZW5ndGgpP3RhOnRiOwogICAgdmFyIGxhcmdvPSh0YS5sZW5ndGg8PXRiLmxlbmd0aCk/dGI6dGE7CiAgICB2YXIgdG90PTAsaSxqOwogICAgZm9yKGk9MDtpPGNvcnRvLmxlbmd0aDtpKyspewogICAgICB2YXIgbWVqb3I9MDsKICAgICAgZm9yKGo9MDtqPGxhcmdvLmxlbmd0aDtqKyspeyB2YXIgdj1zaW1QYXIoY29ydG9baV0sbGFyZ29bal0pOyBpZih2Pm1lam9yKXsgbWVqb3I9djsgfSB9CiAgICAgIHRvdCs9bWVqb3I7CiAgICB9CiAgICBzMj10b3QvY29ydG8ubGVuZ3RoOwogIH0KICByZXR1cm4gTWF0aC5tYXgoczEsczIpOwp9CgovKiA9PT09PT09PT09PT09PT09PSBNUlogeSBub21icmUgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gbXJ6TGluZWFzKHQpewogIHZhciBvdXQ9W10sIGxpbmVzPSh0fHwnJykuc3BsaXQoL1tcclxuXSsvKSwgaTsKICBmb3IoaT0wO2k8bGluZXMubGVuZ3RoO2krKyl7CiAgICB2YXIgbD1saW5lc1tpXS5yZXBsYWNlKC9bXHMuXS9nLCcnKS50b1VwcGVyQ2FzZSgpOwogICAgaWYobC5sZW5ndGg+PTIwICYmIC9eW0EtWjAtOTxdKyQvLnRlc3QobCkgJiYgbC5pbmRleE9mKCc8PCcpPj0wKXsgb3V0LnB1c2gobCk7IH0KICB9CiAgcmV0dXJuIG91dDsKfQpmdW5jdGlvbiBtcnpOb21icmVzKHQpewogIHZhciByZXM9W10sIHZpc3Rvcz17fSwgbHM9bXJ6TGluZWFzKHQpLCBpOwogIGZ1bmN0aW9uIHB1c2gobm9tYnJlKXsKICAgIG5vbWJyZT1ub3JtKG5vbWJyZSk7CiAgICBpZihub21icmUgJiYgbm9tYnJlLmxlbmd0aD49MyAmJiAhdmlzdG9zW25vbWJyZV0peyB2aXN0b3Nbbm9tYnJlXT0xOyByZXMucHVzaChub21icmUpOyB9CiAgfQogIGZvcihpPTA7aTxscy5sZW5ndGg7aSsrKXsKICAgIHZhciBsPWxzW2ldLCBtOwogICAgbT1sLm1hdGNoKC9eUDwoW0EtWl17MCwzfSkoW0EtWl17Mix9KTw8KFtBLVo8XSopLyk7CiAgICBpZihtKXsgcHVzaChtWzJdKycgJysobVszXXx8JycpKTsgfQogICAgbT1sLm1hdGNoKC9eUDwoW0EtWl17MCwzfT8pKFtBLVpdezIsfSk8PChbQS1aPF0qKS8pOwogICAgaWYobSl7IHB1c2gobVsyXSsnICcrKG1bM118fCcnKSk7IH0KICAgIG09bC5tYXRjaCgvXihbQS1aPF17NCx9KTw8KFtBLVo8XXsyLH0pLyk7CiAgICBpZihtKXsgcHVzaChtWzFdKycgJysobVsyXXx8JycpKTsgfQogICAgbT1sLm1hdGNoKC9eKFtBLVpdezIsfSk8PChbQS1aPF0qKS8pOwogICAgaWYobSl7IHB1c2gobVsxXSsnICcrKG1bMl18fCcnKSk7IH0KICAgIG09bC5tYXRjaCgvKFtBLVpdezIsfSk8PChbQS1aPF17Mix9KS8pOwogICAgaWYobSl7IHB1c2gobVsxXSsnICcrKG1bMl18fCcnKSk7IH0KICB9CiAgcmV0dXJuIHJlczsKfQpmdW5jdGlvbiBub21icmVEZVRleHRvKHQpewogIHZhciBUPSh0fHwnJykudG9VcHBlckNhc2UoKSwgY2FuZD1bXSwgbSwgaTsKICB2YXIgcmU9LyhOT01CUkVTP3xBUEVMTElET1M/fE5BTUVTP3xTVVJOQU1FKVxzKls6XC5cLV0/XHMqKCg/OltBLVpcdTAwQzFcdTAwQzlcdTAwQ0RcdTAwRDNcdTAwREFcdTAwRENcdTAwRDFdW0EtWlx1MDBDMVx1MDBDOVx1MDBDRFx1MDBEM1x1MDBEQVx1MDBEQ1x1MDBEMV17MSwxNX0pKD86W1xzXC5dK1tBLVpcdTAwQzFcdTAwQzlcdTAwQ0RcdTAwRDNcdTAwREFcdTAwRENcdTAwRDFdW0EtWlx1MDBDMVx1MDBDOVx1MDBDRFx1MDBEM1x1MDBEQVx1MDBEQ1x1MDBEMV17MSwxNX0pezAsNH0pL2c7CiAgd2hpbGUoKG09cmUuZXhlYyhUKSkhPT1udWxsKXsgaWYobVsyXSl7IGNhbmQucHVzaChtWzJdKTsgfSB9CiAgY2FuZD1jYW5kLmNvbmNhdChtcnpOb21icmVzKFQpKTsKICB2YXIgbGluZXM9VC5zcGxpdCgvW1xyXG5dKy8pOwogIGZvcihpPTA7aTxsaW5lcy5sZW5ndGg7aSsrKXsKICAgIHZhciB3PWxpbmVzW2ldLnJlcGxhY2UoL1teQS1aXHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxIF0vZywnICcpLnRyaW0oKS5zcGxpdCgvXHMrLykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+PTM7IH0pOwogICAgaWYody5sZW5ndGg+PTIgJiYgdy5sZW5ndGg8PTQpeyBjYW5kLnB1c2gody5qb2luKCcgJykpOyB9CiAgfQogIHJldHVybiBjYW5kOwp9CmZ1bmN0aW9uIHRva2Vuc0RlKHMpeyByZXR1cm4gbm9ybShzKS5zcGxpdCgnICcpLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPjE7IH0pOyB9Ci8qIHYxNjogY29uZnVzaW9uZXMgdGlwaWNhcyBkZWwgT0NSIGVuIGRvY3VtZW50b3MgKDAvTy9RL0QvQywgMS9JL0wvVCwKICAgNS9TL1osIDgvQiwgNi9HLCAyL1osIFYvVSwgUi9MLCBNL04vSCwgUC9GKTogVU4gY2FyYWN0ZXIgZGlzdGludG8gZGUKICAgZXNlIGdydXBvIGN1ZW50YSBjb21vIGxhIE1JU01BIGxldHJhIGFsIGNvbXBhcmFyIHR1IG5vbWJyZSBjb24gbG8KICAgcXVlIGxleW8gZWwgT0NSLiAqLwp2YXIgQ09ORl9PQ1I9eydPJzonMFFEQ0VHJywnMCc6J09RRENFRycsJ1EnOidPMERHJywnRCc6J08wUUNCJywnQyc6J08wUUdFQicsJ0cnOidDME9RNicsJ0UnOidGQkdPMCcsJ0InOic4RVIzTzAnLCc4JzonQlIzJywnMyc6J0I4JywnSSc6JzFMSlQnLCcxJzonSUxKVDcnLCdMJzonMUlKVFInLCdKJzonMUxJVCcsJ1QnOicxSUw3JywnUyc6JzVaRycsJzUnOidTWicsJ1onOicyNVMnLCcyJzonWlMnLCc2JzonR0InLCdVJzonVicsJ1YnOidVJywnTSc6J05IJywnTic6J01IJywnSCc6J05NJywnSyc6J1gnLCdYJzonSycsJ1AnOidGUicsJ0YnOidQVEUnLCdSJzonUExGSyd9OwpmdW5jdGlvbiBjb25mdXNvcyhhLGIpewogIGlmKGE9PT1iKXsgcmV0dXJuIHRydWU7IH0KICBpZighYXx8IWJ8fGEubGVuZ3RoIT09Yi5sZW5ndGgpeyByZXR1cm4gZmFsc2U7IH0KICB2YXIgZD0wLCBwb3M9LTEsIGk7CiAgZm9yKGk9MDtpPGEubGVuZ3RoO2krKyl7IGlmKGFbaV0hPT1iW2ldKXsgZCsrOyBwb3M9aTsgaWYoZD4xKXsgcmV0dXJuIGZhbHNlOyB9IH0gfQogIGlmKGQhPT0xKXsgcmV0dXJuIGZhbHNlOyB9CiAgdmFyIHg9YVtwb3NdLCB5PWJbcG9zXTsKICByZXR1cm4gISEoQ09ORl9PQ1JbeF0mJkNPTkZfT0NSW3hdLmluZGV4T2YoeSk+PTApOwp9CmZ1bmN0aW9uIHBhclBhcmVjaWRvKHQxLHQyKXsKICBpZih0MT09PXQyKXsgcmV0dXJuIHRydWU7IH0KICBpZihzaW1QYXIodDEsdDIpPj0wLjc4KXsgcmV0dXJuIHRydWU7IH0KICBpZih0MS5sZW5ndGg+PTQmJnQyLmxlbmd0aD49NCYmKHQxLmluZGV4T2YodDIpPT09MHx8dDIuaW5kZXhPZih0MSk9PT0wKSl7IHJldHVybiB0cnVlOyB9CiAgaWYodDEubGVuZ3RoPj00JiZ0Mi5sZW5ndGg+PTQmJmNvbmZ1c29zKHQxLHQyKSl7IHJldHVybiB0cnVlOyB9CiAgcmV0dXJuIGZhbHNlOwp9Ci8qID09PT09PT09PT09PSBndWFyZGlhbmFzIGRlIGxhIGxlY3R1cmEgY29uZmlybWFkYSAocGFzbyAyKSA9PT09PT09PT09PT0gKi8KZnVuY3Rpb24gdG9rZW5zTm9tYnJlRGUodGV4dG8pewogIHZhciBUPW5vcm0odGV4dG8pLnNwbGl0KCcgJyksIG91dD1bXSwgaSwgajsKICBmb3IoaT0wO2k8VC5sZW5ndGg7aSsrKXsKICAgIHZhciB0PVRbaV07CiAgICBpZih0Lmxlbmd0aDwzfHx0Lmxlbmd0aD4xNSl7IGNvbnRpbnVlOyB9CiAgICBpZighL15bQS1aXSskLy50ZXN0KHQpKXsgY29udGludWU7IH0KICAgIHZhciBtYWxhPWZhbHNlOwogICAgZm9yKGo9MDtqPFBBTEFCUkFTX05PX05PTUJSRS5sZW5ndGg7aisrKXsgaWYodC5pbmRleE9mKFBBTEFCUkFTX05PX05PTUJSRVtqXSk9PT0wKXsgbWFsYT10cnVlOyBicmVhazsgfSB9CiAgICBpZighbWFsYSl7IG91dC5wdXNoKHQpOyB9CiAgfQogIHJldHVybiBvdXQ7Cn0KZnVuY3Rpb24gZWRpY2lvbkFjZXB0YWJsZSh0ZXh0b0VkaXRhZG8sIG9jclRva3MpewogIHZhciB0b2tzPXRva2Vuc0RlKHRleHRvRWRpdGFkbyksIGksIGo7CiAgaWYoIXRva3MubGVuZ3RofHwhb2NyVG9rc3x8IW9jclRva3MubGVuZ3RoKXsgcmV0dXJuIGZhbHNlOyB9CiAgZm9yKGk9MDtpPHRva3MubGVuZ3RoO2krKyl7CiAgICB2YXIgcGFzYT1mYWxzZTsKICAgIGZvcihqPTA7ajxvY3JUb2tzLmxlbmd0aDtqKyspewogICAgICBpZihwYXJQYXJlY2lkbyh0b2tzW2ldLG9jclRva3Nbal0pKXsgcGFzYT10cnVlOyBicmVhazsgfQogICAgICBpZih0b2tzW2ldLmxlbmd0aD49NSYmb2NyVG9rc1tqXS5sZW5ndGg+PTUmJmxldih0b2tzW2ldLG9jclRva3Nbal0pPD0yKXsgcGFzYT10cnVlOyBicmVhazsgfQogICAgfQogICAgaWYoIXBhc2EpeyByZXR1cm4gZmFsc2U7IH0KICB9CiAgcmV0dXJuIHRydWU7Cn0KdmFyIFBBTEFCUkFTX05PX05PTUJSRT1bJ0RPTUlDSUxJTycsJ0RJUkVDQ0lPTicsJ0NPTE9OSUEnLCdCQVJSSU8nLCdSRVNJREVOQ0lBJywnQ0FTRVJJTycsJ0NBTlRPTicsJ0FMREVBJywnU0VDVE9SJywnT0JTRVJWQUNJT04nLCdFU1RBRE8nLCdET05BTlRFJywnR1JVUE8nLCdTQU5HUkUnLCdTQU5HJywnTVVOSUNJUElPJywnREVQQVJUQU1FTlRPJywnRkVDSEEnLCdOQUNJTUlFTlRPJywnU0VYTycsJ05BQ0lPTkFMSURBRCcsJ0ZPTElPJywnTlVNRVJPJywnRE9DVU1FTlRPJywnQ0VEVUxBJywnSURFTlRJREFEJywnTElDRU5DSUEnLCdSRVBVQkxJJywnU0VDUkVUQVJJQScsJ0VNSVNJT04nLCdWRU5DSU1JRU5UTycsJ0NMQVNFJywnQ0FURUdPUklBJywnRU5ET1JTRU1FTlQnLCdSRVNUUklDVElPTicsJ0FERFJFU1MnLCdMVUdBUicsJ0VEQUQnLCdQQVJFTicsJ0ZJTElBQ0lPTicsJ0ZJTElBQ0lPTicsJ01BUkNBJywnU1BFQ0lNRU4nLCdTQU1QTEUnLCdWT1RBQ0lPTicsJ1RPTUFET1InLCdOQUNJTycsJ0RPTScsJ05PTUJSRVMnLCdOT01CUkUnLCdBUEVMTElET1MnLCdBUEVMTElETycsJ0NJVURBRCcsJ0FWRU5JREEnLCdCT1VMRVZBUkQnLCdEVUknLCdEUEknXTsKZnVuY3Rpb24gcGFyZWNlTm9tYnJlTGluZWEoYyl7CiAgdmFyIHc9KGN8fCcnKS5zcGxpdCgnICcpLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPjE7IH0pOwogIGlmKHcubGVuZ3RoPDJ8fHcubGVuZ3RoPjUpeyByZXR1cm4gZmFsc2U7IH0KICB2YXIgbWFsb3M9eydFTCc6MSwnTEEnOjEsJ0xPUyc6MSwnTEFTJzoxLCdERSc6MSwnREVMJzoxfTsKICBmb3IodmFyIGk9MDtpPHcubGVuZ3RoO2krKyl7CiAgICBpZihtYWxvc1t3W2ldXSl7IHJldHVybiBmYWxzZTsgfQogICAgZm9yKHZhciBqPTA7ajxQQUxBQlJBU19OT19OT01CUkUubGVuZ3RoO2orKyl7IGlmKHdbaV0uaW5kZXhPZihQQUxBQlJBU19OT19OT01CUkVbal0pPT09MCl7IHJldHVybiBmYWxzZTsgfSB9CiAgfQogIHJldHVybiB0cnVlOwp9CmZ1bmN0aW9uIG5vbWJyZUNvaW5jaWRlKGVzY3JpdG8sIHRleHRvRG9jLCBlc3RyaWN0byl7CiAgdmFyIHZhY2lvPXtvazpmYWxzZSwgbGVpZG86JycsIHB1bnQ6MCwgaGF5OmZhbHNlfTsKICB2YXIgVT10b2tlbnNEZShlc2NyaXRvKTsKICBpZihVLmxlbmd0aDwyKXsgcmV0dXJuIHZhY2lvOyB9CiAgdmFyIGNhbmQ9bm9tYnJlRGVUZXh0byh0ZXh0b0RvYyksIGxpbXBpb3M9W10sIGksIGs7CiAgZm9yKGk9MDtpPGNhbmQubGVuZ3RoO2krKyl7CiAgICB2YXIgYz1ub3JtKGNhbmRbaV0pOwogICAgaWYoIWMpeyBjb250aW51ZTsgfQogICAgdmFyIHRva3M9Yy5zcGxpdCgnICcpLmZpbHRlcihmdW5jdGlvbih4KXsgcmV0dXJuIHgubGVuZ3RoPjE7IH0pOwogICAgaWYodG9rcy5sZW5ndGg8Mnx8dG9rcy5sZW5ndGg+NSl7IGNvbnRpbnVlOyB9CiAgICBpZighcGFyZWNlTm9tYnJlTGluZWEoYykpeyBjb250aW51ZTsgfQogICAgbGltcGlvcy5wdXNoKHRva3MpOwogIH0KICB2YXIgVDI9bm9ybSh0ZXh0b0RvYykuc3BsaXQoJyAnKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD4xOyB9KTsKICB2YXIgdmlzdGFzPXt9LCBpMiwgTDI7CiAgZm9yKGkyPTA7aTI8bGltcGlvcy5sZW5ndGg7aTIrKyl7IHZpc3Rhc1tsaW1waW9zW2kyXS5qb2luKCcgJyldPTE7IH0KICBmb3IoaTI9MDtpMjxUMi5sZW5ndGg7aTIrKyl7CiAgICBmb3IoTDI9MjtMMjw9NCAmJiBpMitMMjw9VDIubGVuZ3RoO0wyKyspewogICAgICB2YXIgd2luPVQyLnNsaWNlKGkyLGkyK0wyKS5qb2luKCcgJyk7CiAgICAgIGlmKCF2aXN0YXNbd2luXSAmJiBwYXJlY2VOb21icmVMaW5lYSh3aW4pKXsgdmlzdGFzW3dpbl09MTsgbGltcGlvcy5wdXNoKHdpbi5zcGxpdCgnICcpKTsgfQogICAgfQogIH0KICBpZighbGltcGlvcy5sZW5ndGgpeyByZXR1cm4gdmFjaW87IH0KICB2YXIgdW5pb249e30sIGNsYXZlcz1bXTsKICBmb3IoaT0wO2k8bGltcGlvcy5sZW5ndGg7aSsrKXsKICAgIGZvcihrPTA7azxsaW1waW9zW2ldLmxlbmd0aDtrKyspewogICAgICBpZighdW5pb25bbGltcGlvc1tpXVtrXV0peyB1bmlvbltsaW1waW9zW2ldW2tdXT0xOyBjbGF2ZXMucHVzaChsaW1waW9zW2ldW2tdKTsgfQogICAgfQogIH0KICBmdW5jdGlvbiBjdWFudG9zKGxpc3RhKXsKICAgIHZhciBuPTAsIGosIHQ7CiAgICBmb3Ioaj0wO2o8VS5sZW5ndGg7aisrKXsKICAgICAgZm9yKHQ9MDt0PGxpc3RhLmxlbmd0aDt0KyspeyBpZihwYXJQYXJlY2lkbyhVW2pdLGxpc3RhW3RdKSl7IG4rKzsgYnJlYWs7IH0gfQogICAgfQogICAgcmV0dXJuIG47CiAgfQogIHZhciBtZWpvckNhbmQ9JycsIG1lam9yQ292PTA7CiAgZm9yKGk9MDtpPGxpbXBpb3MubGVuZ3RoO2krKyl7CiAgICB2YXIgY292PWN1YW50b3MobGltcGlvc1tpXSkvVS5sZW5ndGg7CiAgICBpZihjb3Y+bWVqb3JDb3YpeyBtZWpvckNvdj1jb3Y7IG1lam9yQ2FuZD1saW1waW9zW2ldLmpvaW4oJyAnKTsgfQogIH0KICB2YXIgY292VT1jdWFudG9zKGNsYXZlcykvVS5sZW5ndGg7CiAgaWYoY292VT5tZWpvckNvdil7IG1lam9yQ292PWNvdlU7IH0KICB2YXIgbk1hdGNoPWN1YW50b3MoY2xhdmVzKSwgbWVqb3JTaW09MCwgajMsIHQzOwogIGZvcihqMz0wO2ozPFUubGVuZ3RoO2ozKyspewogICAgZm9yKHQzPTA7dDM8Y2xhdmVzLmxlbmd0aDt0MysrKXsKICAgICAgaWYocGFyUGFyZWNpZG8oVVtqM10sY2xhdmVzW3QzXSkpeyB2YXIgc3Y9c2ltUGFyKFVbajNdLGNsYXZlc1t0M10pOyBpZihzdj5tZWpvclNpbSl7IG1lam9yU2ltPXN2OyB9IH0KICAgIH0KICB9CiAgLyogdjE2OiByZWdsYXMgTlVFVkFTLiBBbnRlcywgc2kgZWwgdGV4dG8gdHJhaWEgTVJaIChyZXZlcnNvIG8gdW4KICAgICBmYWxzbyBwb3NpdGl2byksIHNvbG8gcGFzYWJhIGNvbiBUT0RBUyB0dXMgcGFsYWJyYXMgbGVpZGFzOiBjb24KICAgICBlbCBNUlogYSBtZWRpYXMgKCJNSVJBIEpPU0UgQUxGT05TTyIgc2luIFpFTEFZQSkgdGUgYm90YWJhIGFsCiAgICAgcGFzbyAxIHkgc2UgcGVyZGlhIHRvZG8uIEFob3JhIGVsIE1SWiBwYXJjaWFsIHlhIG5vIGNhc3RpZ2E6CiAgICAgYmFzdGEgcXVlIFVOQSBkZSB0dXMgcGFsYWJyYXMgZXN0ZSBiaWVuIGxlaWRhLCB5IGxhcyBjb25mdXNpb25lcwogICAgIHRpcGljYXMgZGVsIE9DUiAoTy8wLCBJLzEvTCwgUy81LCBCLzgsIFIvTC4uLikgdmFsZW4gY29tbyBsYQogICAgIG1pc21hIGxldHJhLiBMYSBpZGVudGlkYWQgcmVhbCBsYSBjb25maXJtYSBlbCBtb3RvciBmYWNpYWwuICovCiAgdmFyIG9rOwogIGlmKG1lam9yQ292Pj0wLjk5OSl7IG9rPXRydWU7IH0KICBlbHNlIGlmKG5NYXRjaD49MiAmJiBjb3ZVPj0wLjUpeyBvaz10cnVlOyB9CiAgZWxzZSBpZihuTWF0Y2g+PTEgJiYgY292VT49MC41KXsgb2s9dHJ1ZTsgfQogIGVsc2UgaWYobk1hdGNoPj0xICYmIG1lam9yU2ltPj0wLjk4KXsgb2s9dHJ1ZTsgfQogIGVsc2V7IG9rPWZhbHNlOyB9CiAgcmV0dXJuIHtvazpvaywgbGVpZG86bWVqb3JDYW5kLCBwdW50Om1lam9yQ292LCBoYXk6dHJ1ZX07Cn0KCi8qID09PT09PT09PT09PT09PT09IGRldGVjY2lvbiBkZSBsYWRvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGRldGVjdGFyTGFkbyh0ZXh0bywgdGllbmVDYXJhKXsKICB2YXIgdD0odGV4dG98fCcnKS50b1VwcGVyQ2FzZSgpOwogIHZhciByZXY9MCwgZnJlPTAsIGk7CiAgdmFyIGx0PSh0Lm1hdGNoKC88L2cpfHxbXSkubGVuZ3RoOwogIGlmKGx0Pj02KXsgcmV0dXJuICdyZXZlcnNvJzsgfQogIGlmKC9QREY0ST83Ly50ZXN0KHQucmVwbGFjZSgvXHMvZywnJykpKXsgcmV2Kz0yLjU7IH0KICB2YXIgUlZzPVsnRE9NSUNJTElPJywnRElSRUNDSU9OJywnRElSRUNDSVx1MDBEM04nLCdDT0xPTklBJywnQkFSUklPJywnUkVTSURFTkNJQScsJ0NBU0VSSU8nLCdDQU5UT04nLCdBTERFQScsJ1NFQ1RPUicsJ09CU0VSVkFDSU9OJywnT0JTRVJWQUNJXHUwMEQzTicsJ0RPTkFOVEUnLCdHUlVQTyBTQU5HJywnVElQTyBERSBTQU5HJywnU0FOR1VJTkVPJywnRVNUQURPIENJVklMJywnRU5ET1JTRU1FTlQnLCdSRVNUUklDVElPTicsJ01VTklDSVBJTyddOwogIHZhciBSVnc9WydFTUlTSU9OJywnRU1JU0lcdTAwRDNOJywnVkVOQ0lNSUVOVE8nLCdWRU5DRScsJ0VYUElSRVMnLCdJU1NVRUQnLCdWQUxJREVaJywnRVhQSVJBJywnQ0xBU0UnLCdDQVRFR09SSUEnLCdDQVRFR09SXHUwMENEQScsJ0lTUycsJ0VYUCddOwogIHZhciBGUj1bJ05PTUJSRVMnLCdBUEVMTElET1MnLCdOQU1FUycsJ1NVUk5BTUUnLCdHSVZFTicsJ0RVSScsJ0RPQ1VNRU5UTyBVTklDTycsJ0RPQ1VNRU5UTyBcdTAwREFOSUNPJywnQ0VEVUxBJywnQ1x1MDBDOURVTEEnLCdJREVOVElEQUQnLCdMSUNFTkNJQScsJ0RSSVZFUicsJ05BQ0lNSUVOVE8nLCdCSVJUSCcsJ1NFWE8nLCdTRVgnLCdOQUNJT05BTElEQUQnLCdOQUNJT05BTElUWScsJ0ZPTElPJywnUkVQVUJMSScsJ05VTUVSTycsJ05cdTAwREFNRVJPJywnTlVNQkVSJywnSUQgTk8nXTsKICBmb3IoaT0wO2k8UlZzLmxlbmd0aDtpKyspeyBpZih0LmluZGV4T2YoUlZzW2ldKT49MCl7IHJldis9MjsgfSB9CiAgZm9yKGk9MDtpPFJWdy5sZW5ndGg7aSsrKXsgaWYodC5pbmRleE9mKFJWd1tpXSk+PTApeyByZXYrPTAuNzU7IH0gfQogIGZvcihpPTA7aTxGUi5sZW5ndGg7aSsrKXsgaWYodC5pbmRleE9mKEZSW2ldKT49MCl7IGZyZSs9MTsgfSB9CiAgaWYodGllbmVDYXJhKXsgZnJlKz00OyB9CiAgaWYocmV2Pj0zLjUgJiYgcmV2PmZyZSsxKXsgcmV0dXJuICdyZXZlcnNvJzsgfQogIGlmKGZyZT49MyAmJiBmcmU+cmV2KzEpeyByZXR1cm4gJ2ZyZW50ZSc7IH0KICBpZihyZXY+ZnJlICYmIHJldj49Mil7IHJldHVybiAncmV2ZXJzbyc7IH0KICBpZihmcmU+cmV2ICYmIGZyZT49Mil7IHJldHVybiAnZnJlbnRlJzsgfQogIHJldHVybiAnZGVzY29ub2NpZG8nOwp9CgovKiA9PT09PT09PT09PT09PT09PSBnYW5jaG8gcGFyYSBwcnVlYmFzIChub2RlLCBzaW4gRE9NKSA9PT09PT09PT09PT09PT09PSAqLwppZiAodHlwZW9mIGRvY3VtZW50PT09J3VuZGVmaW5lZCcgfHwgdHlwZW9mIGRvY3VtZW50LmdldEVsZW1lbnRCeUlkIT09J2Z1bmN0aW9uJyl7CiAgVy5fX1pZUkFfVEVTVF9fPXtub3JtOm5vcm0sbGV2OmxldixzaW1QYXI6c2ltUGFyLHNpbU5vbWJyZXM6c2ltTm9tYnJlcyxtcnpMaW5lYXM6bXJ6TGluZWFzLG1yek5vbWJyZXM6bXJ6Tm9tYnJlcyxub21icmVEZVRleHRvOm5vbWJyZURlVGV4dG8sbm9tYnJlQ29pbmNpZGU6bm9tYnJlQ29pbmNpZGUsZGV0ZWN0YXJMYWRvOmRldGVjdGFyTGFkbyxldmFsdWFDYXJhOmV2YWx1YUNhcmEsZWFyRGU6ZWFyRGUsY2VudHJvRGU6Y2VudHJvRGUscXVhZFZhbGlkbzpxdWFkVmFsaWRvLGFyZWFRdWFkOmFyZWFRdWFkLGV0aXF1ZXRhQ29tcG9uZW50ZXM6ZXRpcXVldGFDb21wb25lbnRlcyxlc3F1aW5hc0RlTWFzY2FyYTplc3F1aW5hc0RlTWFzY2FyYSxtZWRpYW5hUXVhZDptZWRpYW5hUXVhZCxxdWFkRXN0YWJsZTpxdWFkRXN0YWJsZSxuaXRvRGU6bml0b0RlLGZyYWNjaW9uQmxhbmNvOmZyYWNjaW9uQmxhbmNvLHRva2Vuc05vbWJyZURlOnRva2Vuc05vbWJyZURlLGVkaWNpb25BY2VwdGFibGU6ZWRpY2lvbkFjZXB0YWJsZSxlbGVnaXJUZXh0bzplbGVnaXJUZXh0byxwYXJQYXJlY2lkbzpwYXJQYXJlY2lkbyx0b2tlbnNEZTp0b2tlbnNEZSx0b2RvT2tQYXJhQ3JlYXI6dG9kb09rUGFyYUNyZWFyLGNhamFEZVF1YWQ6Y2FqYURlUXVhZH07CiAgcmV0dXJuOwp9CgovKiA9PT09PT09PT09PT09PT09PSBnYW5jaG8gZGUgcHJ1ZWJhcyBjb24gRE9NIHNpbXVsYWRvID09PT09PT09PT09PT09PT09ICovClcuX19aWVJBX1JFVkZfVEVTVF9fPXt9OwoKLyogPT09PT09PT09PT09PT09PT0gZmV0Y2ggY29uIHJlaW50ZW50b3MgKyB3YXJtdXAgPT09PT09PT09PT09PT09PT0gKi8KKGZ1bmN0aW9uKCl7CiAgaWYoVy5fX3p5RmV0Y2hGaXgpeyByZXR1cm47IH0KICBXLl9fenlGZXRjaEZpeD0xOwogIHZhciBfZj1XLmZldGNoP1cuZmV0Y2guYmluZChXKTpudWxsOwogIGlmKCFfZil7IHJldHVybjsgfQogIFcuZmV0Y2g9ZnVuY3Rpb24oKXsKICAgIHZhciBhcmdzPWFyZ3VtZW50cywgbj0wOwogICAgZnVuY3Rpb24gb3RybygpeyByZXR1cm4gX2YuYXBwbHkobnVsbCxhcmdzKS50aGVuKGZ1bmN0aW9uKHIpewogICAgICBpZihbNTAwLDUwMiw1MDMsNTA0LDQxM10uaW5kZXhPZihyLnN0YXR1cyk+PTAgJiYgbjwzKXsgbisrOyByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsgc2V0VGltZW91dChyZXMsNzAwKm4pOyB9KS50aGVuKG90cm8pOyB9CiAgICAgIHJldHVybiByOwogICAgfSwgZnVuY3Rpb24oZSl7CiAgICAgIGlmKG48Myl7IG4rKzsgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7IHNldFRpbWVvdXQocmVzLDcwMCpuKTsgfSkudGhlbihvdHJvKTsgfQogICAgICB0aHJvdyBlOwogICAgfSk7IH0KICAgIHJldHVybiBvdHJvKCk7CiAgfTsKICB0cnl7IF9mKFcubG9jYXRpb24ucGF0aG5hbWUse2NhY2hlOiduby1zdG9yZScsaGVhZGVyczp7J3gtenktd2FybXVwJzonMSd9fSkuY2F0Y2goZnVuY3Rpb24oKXt9KTsgfWNhdGNoKGUpe30KfSkoKTsKCi8qID09PT09PT09PT09PT09PT09IGVzdGFkbyBkZWwgZmx1am8gPT09PT09PT09PT09PT09PT0gKi8KdmFyIEVTVD17cGFzbzoxLCBwYXNvTWF4OjEsIHRpcG86J2Rlc2Nvbm9jaWRvJywgbmVjZXNpdGFSZXZlcnNvOnRydWUsIG5vbWJyZU9rOmZhbHNlLCBmcmVudGVPazpmYWxzZSwgcmV2ZXJzb09rOmZhbHNlLCBzZWxmaWVPazpmYWxzZSwgaW50ZW50b3M6NSwgZnJlbnRlSW1nOicnLCByZXZlcnNvSW1nOicnLCBzZWxmaWVJbWc6JycsIGVzY3JpdG86JycsIGZyZW50ZVRleHRvOicnLCByZXZlcnNvVGV4dG86JycsIGNhcmFWaXZhOm51bGwsIGNhcmFEb2M6bnVsbH07CnZhciBzdHJlYW1zPXt9Owp2YXIgSElOVFM9e307CgpmdW5jdGlvbiBjbGFzaWZpY2FyVGlwbygpewogIHZhciBzZWw9JCgndGlwb0RvYycpLCB0eHQ9Jyc7CiAgaWYoc2VsKXsKICAgIHZhciBvcD1zZWwub3B0aW9ucyAmJiBzZWwub3B0aW9uc1tzZWwuc2VsZWN0ZWRJbmRleF07CiAgICB0eHQ9KG9wJiZvcC50ZXh0P29wLnRleHQ6JycpKycgJysoc2VsLnZhbHVlfHwnJyk7CiAgfQogIHR4dD10eHQudG9Mb3dlckNhc2UoKTsKICBpZigvcGFzYXBvcnRlfHBhc3Nwb3J0Ly50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J3Bhc2Fwb3J0ZScsIHJldmVyc286ZmFsc2V9OyB9CiAgaWYoL3NhbHZhZG9yfFxiZHVpXGIvLnRlc3QodHh0KSl7IHJldHVybiB7azonZHVpJywgcmV2ZXJzbzp0cnVlfTsgfQogIGlmKC9ndWF0ZW1hbGF8Z3VhdGUvLnRlc3QodHh0KSl7IHJldHVybiB7azonZ3QnLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL25pY2FyYWd1YS8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOiduaScsIHJldmVyc286dHJ1ZX07IH0KICBpZigvaG9uZHVyYXMvLnRlc3QodHh0KSl7IHJldHVybiB7azonaG4nLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL3VzYXxlc3RhZG9zIHVuaWRvc3xsaWNlbmNpYXxsaWNlbnNlfGRyaXZlci8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOid1c2EnLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL290cm98b3RoZXIvLnRlc3QodHh0KSl7IHJldHVybiB7azonb3RybycsIHJldmVyc286dHJ1ZX07IH0KICByZXR1cm4ge2s6J2Rlc2Nvbm9jaWRvJywgcmV2ZXJzbzp0cnVlfTsKfQoKLyogPT09PT09PT09PT09PT09PT0gbWVuc2FqZXMgeSBheXVkYXMgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gbXNnKGlkLHRleHRvLGNvbG9yKXsKICB2YXIgZWw9JChpZCk7CiAgaWYoIWVsICYmIEhJTlRTW2lkXSl7IGVsPUhJTlRTW2lkXTsgfQogIGlmKCFlbCl7CiAgICB2YXIgYW5jbGE9JCgncHMxJyk7CiAgICBlbD1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgIGVsLmlkPWlkOwogICAgZWwuc3R5bGUuY3NzVGV4dD0nZm9udC1zaXplOjEzcHg7bWFyZ2luOjZweCAwO2xpbmUtaGVpZ2h0OjEuMzU7JzsKICAgIGlmKGFuY2xhICYmIGFuY2xhLnBhcmVudE5vZGUpeyBhbmNsYS5wYXJlbnROb2RlLmluc2VydEJlZm9yZShlbCxhbmNsYS5uZXh0U2libGluZyk7IH0KICAgIGVsc2V7IGRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQoZWwpOyB9CiAgICBISU5UU1tpZF09ZWw7CiAgfQogIGVsLnRleHRDb250ZW50PXRleHRvfHwnJzsKICBpZihjb2xvcil7IGVsLnN0eWxlLmNvbG9yPWNvbG9yOyB9Cn0KZnVuY3Rpb24gYnVzeShvbil7CiAgdmFyIGlkcz1bJ2Jsb2NGJywnYmxvY0EnLCdibG9jUyddLCBpOwogIGZvcihpPTA7aTxpZHMubGVuZ3RoO2krKyl7IHZhciBiPSQoaWRzW2ldKTsgaWYoYil7IGIuc3R5bGUuZGlzcGxheT1vbj8nZmxleCc6J25vbmUnOyB9IH0KfQpmdW5jdGlvbiBzaG93SW1nKGlkLGRhdGFVcmwpewogIHZhciBwPSQoaWQpOwogIGlmKHApewogICAgcC5zcmM9ZGF0YVVybDsKICAgIHAuc3R5bGUuZGlzcGxheT0nYmxvY2snOwogICAgcC5zdHlsZS5tYXhXaWR0aD0nMjQwcHgnOwogICAgcC5zdHlsZS5tYXhIZWlnaHQ9JzI0MHB4JzsKICAgIHAuc3R5bGUud2lkdGg9J2F1dG8nOwogICAgcC5zdHlsZS5oZWlnaHQ9J2F1dG8nOwogICAgcC5zdHlsZS5ib3JkZXJSYWRpdXM9JzEwcHgnOwogICAgcC5zdHlsZS5tYXJnaW49JzhweCBhdXRvJzsKICAgIHAuc3R5bGUuZGlzcGxheT0nYmxvY2snOwogIH0KfQoKLyogPT09PT09PT09PT09PT09PT0gY2FtYXJhOiBwcmV2aWV3IFNJRU1QUkUgY2hpY28gPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gbGV0cmFEZShwc0lkKXsgcmV0dXJuICh7JzInOidGJywnMyc6J0EnLCc0JzonUyd9KVtwc0lkXXx8J0YnOyB9CmZ1bmN0aW9uIGZpbmRWaWRlbyhwc0lkKXsKICB2YXIgbGV0cmE9bGV0cmFEZShwc0lkKTsKICB2YXIgaWRzPVsndnonK2xldHJhLCd2ZCcrbGV0cmEsJ3YnK2xldHJhXSwgaTsKICB2YXIgY29udD0kKCdwcycrcHNJZCk7CiAgZm9yKGk9MDtpPGlkcy5sZW5ndGg7aSsrKXsKICAgIHZhciBjYW5kPSQoaWRzW2ldKTsKICAgIGlmKGNhbmQgJiYgY2FuZC50YWdOYW1lPT09J1ZJREVPJyl7IHJldHVybiBjYW5kOyB9CiAgfQogIGlmKGNvbnQpewogICAgdmFyIHY9Y29udC5xdWVyeVNlbGVjdG9yKCd2aWRlbycpOwogICAgaWYodil7IHJldHVybiB2OyB9CiAgfQogIHJldHVybiBudWxsOwp9CmZ1bmN0aW9uIGVzdGlsb0NoaWNvKHYpewogIGlmKCF2KXsgcmV0dXJuOyB9CiAgdi5zdHlsZS5tYXhXaWR0aD0nMjgwcHgnOwogIHYuc3R5bGUud2lkdGg9JzEwMCUnOwogIHYuc3R5bGUubWF4SGVpZ2h0PSczMjBweCc7CiAgdHJ5eyB2LnN0eWxlLmFzcGVjdFJhdGlvPSczIC8gNCc7IH1jYXRjaChlKXt9CiAgdi5zdHlsZS5vYmplY3RGaXQ9J2NvdmVyJzsKICB2LnN0eWxlLmJvcmRlclJhZGl1cz0nMTJweCc7CiAgdi5zdHlsZS5iYWNrZ3JvdW5kPScjMDAwJzsKICB2LnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsKICB2LnN0eWxlLm1hcmdpbj0nMCBhdXRvJzsKfQpmdW5jdGlvbiB2aWJyYXIoKXsgdHJ5eyBpZihuYXZpZ2F0b3IudmlicmF0ZSl7IG5hdmlnYXRvci52aWJyYXRlKDcwKTsgfSB9Y2F0Y2goZSl7fSB9CmZ1bmN0aW9uIGFsaW5lYXJPdmVybGF5KHBzSWQsIHYpewogIHRyeXsKICAgIHZhciBPVj17JzInOidvdkYnLCczJzonb3ZBJywnNCc6J292Uyd9OwogICAgdmFyIG92PSQoT1ZbcHNJZF0pOyBpZighb3Z8fCF2KXsgcmV0dXJuOyB9CiAgICB2YXIgej0kKCd2eicrbGV0cmFEZShwc0lkKSk7IGlmKCF6KXsgcmV0dXJuOyB9CiAgICB2YXIgdnI9di5nZXRCb3VuZGluZ0NsaWVudFJlY3QoKSwgenI9ei5nZXRCb3VuZGluZ0NsaWVudFJlY3QoKTsKICAgIGlmKCF2ci53aWR0aHx8IXZyLmhlaWdodCl7IHJldHVybjsgfQogICAgb3Yuc3R5bGUucG9zaXRpb249J2Fic29sdXRlJzsKICAgIG92LnN0eWxlLmxlZnQ9TWF0aC5yb3VuZCh2ci5sZWZ0LXpyLmxlZnQpKydweCc7CiAgICBvdi5zdHlsZS50b3A9TWF0aC5yb3VuZCh2ci50b3AtenIudG9wKSsncHgnOwogICAgb3Yuc3R5bGUud2lkdGg9dnIud2lkdGgrJ3B4JzsKICAgIG92LnN0eWxlLmhlaWdodD12ci5oZWlnaHQrJ3B4JzsKICAgIHRyeXsgb3Yuc3R5bGUub2JqZWN0Rml0PSdjb3Zlcic7IH1jYXRjaChlMil7fQogICAgb3Yuc3R5bGUuYm9yZGVyUmFkaXVzPScxMnB4JzsKICAgIG92LnN0eWxlLnpJbmRleD0nNSc7CiAgfWNhdGNoKGUpe30KfQpmdW5jdGlvbiB6eURldCgpeyBpZighVy5fX3p5RGV0KXsgVy5fX3p5RGV0PXt9OyB9IHJldHVybiBXLl9fenlEZXQ7IH0KZnVuY3Rpb24gb3RzdVVtYnJhbChoaXN0LHRvdGFsKXsKICB2YXIgc3VtPTAsaTsgZm9yKGk9MDtpPDI1NjtpKyspeyBzdW0rPWkqaGlzdFtpXTsgfQogIHZhciBzdW1CPTAsd0I9MCxiZXN0PTAsdGhyPTEyNzsKICBmb3IoaT0wO2k8MjU2O2krKyl7CiAgICB3Qis9aGlzdFtpXTsgaWYod0I9PT0wKXsgY29udGludWU7IH0KICAgIHZhciB3Rj10b3RhbC13QjsgaWYod0Y9PT0wKXsgYnJlYWs7IH0KICAgIHN1bUIrPWkqaGlzdFtpXTsKICAgIHZhciBtQj1zdW1CL3dCLCBtRj0oc3VtLXN1bUIpL3dGLCB2PXdCKndGKihtQi1tRikqKG1CLW1GKTsKICAgIGlmKHY+YmVzdCl7IGJlc3Q9djsgdGhyPWk7IH0KICB9CiAgcmV0dXJuIHRocjsKfQpmdW5jdGlvbiByYW5nb1Byb3llY2Npb24oYXJyLG4sdW1icmFsKXsKICB2YXIgYT0tMSxiPS0xLGk7CiAgZm9yKGk9MDtpPG47aSsrKXsgaWYoYXJyW2ldPj11bWJyYWwpeyBpZihhPDApeyBhPWk7IH0gYj1pOyB9IH0KICBpZihhPDB8fGI8PWEpeyByZXR1cm4gbnVsbDsgfQogIHJldHVybiBbYSxiXTsKfQovKiA9PT09PT09PT09PT0gZGV0ZWNjaW9uIFJFQUwgZGVsIGRvY3VtZW50bzogNCBlc3F1aW5hcyA9PT09PT09PT09PT0gKi8KZnVuY3Rpb24gZXRpcXVldGFDb21wb25lbnRlcyhtYXNrLCB3LCBoKXsKICB2YXIgbGFiPW5ldyBJbnQzMkFycmF5KHcqaCksIHBpbGE9bmV3IEludDMyQXJyYXkodypoKTsKICB2YXIgbWVqb3I9e3RhbTowLGlkOjB9LCBpZD0wLCBpOwogIGZvcihpPTA7aTx3Kmg7aSsrKXsKICAgIGlmKG1hc2tbaV0mJiFsYWJbaV0pewogICAgICBpZCsrOyB2YXIgc3A9MCwgdGFtPTA7CiAgICAgIHBpbGFbc3ArK109aTsgbGFiW2ldPWlkOwogICAgICB3aGlsZShzcD4wKXsKICAgICAgICB2YXIgcD1waWxhWy0tc3BdOyB0YW0rKzsKICAgICAgICB2YXIgeD1wJXcsIHk9KHAteCkvdzsKICAgICAgICBpZih4PjAmJm1hc2tbcC0xXSYmIWxhYltwLTFdKXsgbGFiW3AtMV09aWQ7IHBpbGFbc3ArK109cC0xOyB9CiAgICAgICAgaWYoeDx3LTEmJm1hc2tbcCsxXSYmIWxhYltwKzFdKXsgbGFiW3ArMV09aWQ7IHBpbGFbc3ArK109cCsxOyB9CiAgICAgICAgaWYoeT4wJiZtYXNrW3Atd10mJiFsYWJbcC13XSl7IGxhYltwLXddPWlkOyBwaWxhW3NwKytdPXAtdzsgfQogICAgICAgIGlmKHk8aC0xJiZtYXNrW3Ard10mJiFsYWJbcCt3XSl7IGxhYltwK3ddPWlkOyBwaWxhW3NwKytdPXArdzsgfQogICAgICB9CiAgICAgIGlmKHRhbT5tZWpvci50YW0peyBtZWpvcj17dGFtOnRhbSxpZDppZH07IH0KICAgIH0KICB9CiAgcmV0dXJuIHtsYWI6bGFiLCBtZWpvcjptZWpvcn07Cn0KZnVuY3Rpb24gZXNxdWluYXNEZU1hc2NhcmEobGFiLCBpZCwgdywgaCl7CiAgdmFyIHRsPW51bGwsdHI9bnVsbCxicj1udWxsLGJsPW51bGwsIHgseSxwOwogIGZvcih5PTA7eTxoO3krKyl7CiAgICBmb3IoeD0wO3g8dzt4KyspewogICAgICBwPXkqdyt4OwogICAgICBpZihsYWJbcF0hPT1pZCl7IGNvbnRpbnVlOyB9CiAgICAgIHZhciBzPXgreSwgZDI9eC15OwogICAgICBpZighdGx8fHM8dGwucyl7IHRsPXt4OngseTp5LHM6c307IH0KICAgICAgaWYoIWJyfHxzPmJyLnMpeyBicj17eDp4LHk6eSxzOnN9OyB9CiAgICAgIGlmKCF0cnx8ZDI+dHIuZCl7IHRyPXt4OngseTp5LGQ6ZDJ9OyB9CiAgICAgIGlmKCFibHx8ZDI8YmwuZCl7IGJsPXt4OngseTp5LGQ6ZDJ9OyB9CiAgICB9CiAgfQogIHJldHVybiB7dGw6dGwsdHI6dHIsYnI6YnIsYmw6Ymx9Owp9CmZ1bmN0aW9uIGFyZWFRdWFkKHEpewogIGlmKCFxfHwhcS50bHx8IXEudHJ8fCFxLmJyfHwhcS5ibCl7IHJldHVybiAwOyB9CiAgdmFyIHB0cz1bcS50bCxxLnRyLHEuYnIscS5ibF0sIGE9MCwgaTsKICBmb3IoaT0wO2k8NDtpKyspeyB2YXIgcD1wdHNbaV0sIHI9cHRzWyhpKzEpJTRdOyBhKz1wLngqci55LXIueCpwLnk7IH0KICByZXR1cm4gTWF0aC5hYnMoYSkvMjsKfQpmdW5jdGlvbiBxdWFkVmFsaWRvKHEsIGR3LCBkaCl7CiAgaWYoIXF8fCFxLnRsfHwhcS50cnx8IXEuYnJ8fCFxLmJsKXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidmb3JtYSd9OyB9CiAgdmFyIHB0cz1bcS50bCxxLnRyLHEuYnIscS5ibF0sIGksIHNpZz0wOwogIGZvcihpPTA7aTw0O2krKyl7CiAgICB2YXIgYT1wdHNbaV0sIGI9cHRzWyhpKzEpJTRdLCBjPXB0c1soaSsyKSU0XTsKICAgIHZhciBjcj0oYi54LWEueCkqKGMueS1iLnkpLShiLnktYS55KSooYy54LWIueCk7CiAgICBpZihNYXRoLmFicyhjcik8MC41KXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidmb3JtYSd9OyB9CiAgICB2YXIgcz1jcj4wPzE6LTE7CiAgICBpZihzaWc9PT0wKXsgc2lnPXM7IH0gZWxzZSBpZihzIT09c2lnKXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidmb3JtYSd9OyB9CiAgfQogIGZ1bmN0aW9uIGRzdChhLGIpeyB2YXIgZHg9YS54LWIueCwgZHk9YS55LWIueTsgcmV0dXJuIE1hdGguc3FydChkeCpkeCtkeSpkeSk7IH0KICB2YXIgYXI9ZHN0KHEudGwscS50ciksIGFiPWRzdChxLnRyLHEuYnIpLCBhaT1kc3QocS5icixxLmJsKSwgYXo9ZHN0KHEuYmwscS50bCk7CiAgdmFyIG1uPU1hdGgubWluKGFyLGFiLGFpLGF6KTsKICBpZihtbjxNYXRoLm1heChkdyxkaCkqMC4wOSl7IHJldHVybiB7b2s6ZmFsc2UsIG1vdGl2bzoncGVxdWVubyd9OyB9CiAgdmFyIGZyPWFyZWFRdWFkKHEpLyhkdypkaCk7CiAgaWYoZnI+MC45NCl7IHJldHVybiB7b2s6ZmFsc2UsIG1vdGl2bzonZm9ybWEnfTsgfQogIHZhciBhc3A9KGFyK2FpKS9NYXRoLm1heCgxLChhYitheikpOwogIGlmKGFzcDwwLjQ1fHxhc3A+Mi41KXsgcmV0dXJuIHtvazpmYWxzZSwgbW90aXZvOidmb3JtYSd9OyB9CiAgaWYoZnI8MC4xMCl7IHJldHVybiB7b2s6ZmFsc2UsIG1vdGl2bzoncGVxdWVubycsIGZyYWM6ZnJ9OyB9CiAgcmV0dXJuIHtvazp0cnVlLCBmcmFjOmZyLCBhc3A6YXNwfTsKfQpmdW5jdGlvbiBuaXRvRGUobHVtLCBkdywgZGgsIGNhamEpewogIHZhciB4MD0xLHkwPTEseDE9ZHctMSx5MT1kaC0xOwogIGlmKGNhamEpeyB4MD1NYXRoLm1heCgxLGNhamEueCsxKTsgeTA9TWF0aC5tYXgoMSxjYWphLnkrMSk7IHgxPU1hdGgubWluKGR3LTEsY2FqYS54K2NhamEudy0xKTsgeTE9TWF0aC5taW4oZGgtMSxjYWphLnkrY2FqYS5oLTEpOyB9CiAgdmFyIHM9MCxzMj0wLGs9MCx4LHk7CiAgZm9yKHk9eTA7eTx5MTt5KyspewogICAgZm9yKHg9eDA7eDx4MTt4KyspewogICAgICB2YXIgcD15KmR3K3g7CiAgICAgIHZhciBscD00Kmx1bVtwXS1sdW1bcC0xXS1sdW1bcCsxXS1sdW1bcC1kd10tbHVtW3ArZHddOwogICAgICBzKz1scDsgczIrPWxwKmxwOyBrKys7CiAgICB9CiAgfQogIGlmKCFrKXsgcmV0dXJuIHt2OjB9OyB9CiAgdmFyIG09cy9rOwogIHJldHVybiB7djooczIvayktbSptfTsKfQpmdW5jdGlvbiBmcmFjY2lvbkJsYW5jbyhsdW0sIGR3LCBkaCwgY2FqYSl7CiAgdmFyIHgwPTAseTA9MCx4MT1kdyx5MT1kaCxrPTAsYj0wLHgseTsKICBpZihjYWphKXsgeDA9TWF0aC5tYXgoMCxjYWphLngpOyB5MD1NYXRoLm1heCgwLGNhamEueSk7IHgxPU1hdGgubWluKGR3LGNhamEueCtjYWphLncpOyB5MT1NYXRoLm1pbihkaCxjYWphLnkrY2FqYS5oKTsgfQogIGZvcih5PXkwO3k8eTE7eSsrKXsgZm9yKHg9eDA7eDx4MTt4KyspeyBrKys7IGlmKGx1bVt5KmR3K3hdPj0yNDYpeyBiKys7IH0gfSB9CiAgcmV0dXJuIGs/KGIvayk6MDsKfQpmdW5jdGlvbiBtZWRpYW5hTnVtKGEpewogIGlmKCFhfHwhYS5sZW5ndGgpeyByZXR1cm4gMDsgfQogIHZhciBiPWEuc2xpY2UoKS5zb3J0KGZ1bmN0aW9uKHgseSl7IHJldHVybiB4LXk7IH0pOwogIHJldHVybiBiW01hdGguZmxvb3IoYi5sZW5ndGgvMildOwp9CmZ1bmN0aW9uIG1lZGlhbmFRdWFkKGhpc3QpewogIGlmKCFoaXN0fHwhaGlzdC5sZW5ndGgpeyByZXR1cm4gbnVsbDsgfQogIHZhciBLPVsndGwnLCd0cicsJ2JyJywnYmwnXSwgcmVzPXt9LCBpLCBrLCB4cywgeXM7CiAgZm9yKGs9MDtrPEsubGVuZ3RoO2srKyl7CiAgICB4cz1bXTsgeXM9W107CiAgICBmb3IoaT0wO2k8aGlzdC5sZW5ndGg7aSsrKXsgaWYoaGlzdFtpXSYmaGlzdFtpXVtLW2tdXSl7IHhzLnB1c2goaGlzdFtpXVtLW2tdXS54KTsgeXMucHVzaChoaXN0W2ldW0tba11dLnkpOyB9IH0KICAgIGlmKCF4cy5sZW5ndGgpeyByZXR1cm4gbnVsbDsgfQogICAgcmVzW0tba11dPXt4Om1lZGlhbmFOdW0oeHMpLCB5Om1lZGlhbmFOdW0oeXMpfTsKICB9CiAgcmV0dXJuIHJlczsKfQpmdW5jdGlvbiBxdWFkRXN0YWJsZShoaXN0KXsKICB2YXIgbWVkPW1lZGlhbmFRdWFkKGhpc3QpLCBLPVsndGwnLCd0cicsJ2JyJywnYmwnXSwgaSwgazsKICBpZighbWVkfHwhaGlzdHx8aGlzdC5sZW5ndGg8NCl7IHJldHVybiBmYWxzZTsgfQogdmFyIHRvbD0wLjAyKk1hdGgubWF4KGhpc3RbMF0udnd8fDY0MCwgaGlzdFswXS52aHx8NDgwKTsKICBmb3Ioaz0wO2s8Sy5sZW5ndGg7aysrKXsKICAgIGZvcihpPU1hdGgubWF4KDAsaGlzdC5sZW5ndGgtNCk7aTxoaXN0Lmxlbmd0aDtpKyspewogICAgICB2YXIgcT1oaXN0W2ldJiZoaXN0W2ldW0tba11dOwogICAgICBpZighcXx8IW1lZFtLW2tdXSl7IHJldHVybiBmYWxzZTsgfQogICAgICB2YXIgZHg9cS54LW1lZFtLW2tdXS54LCBkeT1xLnktbWVkW0tba11dLnk7CiAgICAgIGlmKE1hdGguc3FydChkeCpkeCtkeSpkeSk+dG9sKXsgcmV0dXJuIGZhbHNlOyB9CiAgICB9CiAgfQogIHJldHVybiB0cnVlOwp9CmZ1bmN0aW9uIGRldGVjdGFyRG9jUXVhZCh2KXsKICB0cnl7CiAgICB2YXIgRD16eURldCgpOwogICAgdmFyIHZ3PXYudmlkZW9XaWR0aHx8MCwgdmg9di52aWRlb0hlaWdodHx8MDsKICAgIGlmKCF2d3x8IXZoKXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciBkdz0xNjAsIGRoPU1hdGgucm91bmQoZHcqdmgvdncpOwogICAgaWYoZGg8OCl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgYz1ELmN2UTsgaWYoIWMpeyBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOyBELmN2UT1jOyB9CiAgICBpZihjLndpZHRoIT09ZHd8fGMuaGVpZ2h0IT09ZGgpeyBjLndpZHRoPWR3OyBjLmhlaWdodD1kaDsgfQogICAgdmFyIGc9Yy5nZXRDb250ZXh0KCcyZCcpOyBpZighZyl7IHJldHVybiBudWxsOyB9CiAgICBnLmRyYXdJbWFnZSh2LDAsMCxkdyxkaCk7CiAgICB2YXIgZD1nLmdldEltYWdlRGF0YSgwLDAsZHcsZGgpLmRhdGEsIG49ZHcqZGgsIGksIHgsIHk7CiAgICB2YXIgbHVtPW5ldyBVaW50OEFycmF5KG4pLCBzdW09MDsKICAgIGZvcihpPTA7aTxuO2krKyl7IGx1bVtpXT0oZFtpKjRdKjMrZFtpKjQrMV0qNCtkW2kqNCsyXSk+PjM7IHN1bSs9bHVtW2ldOyB9CiAgICB2YXIgbHV6PXN1bS9uOwogICAgLyogaGVyZWRhZG8gdjE0OiBtYXNjYXJhIGFudGktdGVsYSBkZSBjb2xvci4gRW4gZ3JpcywgdW5hIHRlbGEgcm9zYS9yb2phCiAgICAgICBjbGFyYSBzZSB2ZSBjYXNpIGlndWFsIHF1ZSBsYSB0YXJqZXRhIHkgZWwgdW1icmFsIGRlIE90c3Ugbm8gc2VwYXJhOgogICAgICAgbGEgZ3VpYSBubyBhZ2FycmEgbGFzIDQgZXNxdWluYXMuIExhIFRBUkpFVEEgZXMgY2xhcmEgeSBQT0NPIHNhdHVyYWRhOwogICAgICAgbGEgdGVsYSBkZSBjb2xvciBlcyBNVVkgc2F0dXJhZGEuIFBydWVibyBwcmltZXJvIGNvbiBlc2EgbWFzY2FyYSB5IHNpCiAgICAgICBubyBkYSB1biBjdWFkcmlsYXRlcm8gdmFsaWRvIGNhaWdvIGFsIHVtYnJhbCBkZSBPdHN1IChmb25kbyBvc2N1cm8pLiAqLwogICAgZnVuY3Rpb24gcmVzdWx0YWRvRGVNYXNjYXJhKG1hc2tBcnIpewogICAgICB2YXIgdG90Mj0wLCBpMjsKICAgICAgZm9yKGkyPTA7aTI8bjtpMisrKXsgaWYobWFza0FycltpMl0peyB0b3QyKys7IH0gfQogICAgICBpZih0b3QyPG4qMC4wM3x8dG90Mj5uKjAuOTY1KXsgcmV0dXJuIG51bGw7IH0KICAgICAgdmFyIGNjMj1ldGlxdWV0YUNvbXBvbmVudGVzKG1hc2tBcnIsZHcsZGgpOwogICAgICBpZighY2MyLm1lam9yLmlkfHxjYzIubWVqb3IudGFtPG4qMC4wNCl7IHJldHVybiBudWxsOyB9CiAgICAgIHZhciBxMj1lc3F1aW5hc0RlTWFzY2FyYShjYzIubGFiLGNjMi5tZWpvci5pZCxkdyxkaCk7CiAgICAgIGlmKCFxMi50bHx8IXEyLnRyfHwhcTIuYnJ8fCFxMi5ibCl7IHJldHVybiBudWxsOyB9CiAgICAgIHZhciB2YWwyPXF1YWRWYWxpZG8ocTIsZHcsZGgpOwogICAgICBpZighdmFsMi5vayl7IHJldHVybiBudWxsOyB9CiAgICAgIHZhciB4YT1NYXRoLm1heCgwLE1hdGgubWluKHEyLnRsLngscTIuYmwueCkpLCB4Yj1NYXRoLm1pbihkdyxNYXRoLm1heChxMi50ci54LHEyLmJyLngpKTsKICAgICAgdmFyIHlhPU1hdGgubWF4KDAsTWF0aC5taW4ocTIudGwueSxxMi50ci55KSksIHliPU1hdGgubWluKGRoLE1hdGgubWF4KHEyLmJsLnkscTIuYnIueSkpOwogICAgICB2YXIgY2FqYTI9e3g6eGEseTp5YSx3Ok1hdGgubWF4KDEseGIteGEpLGg6TWF0aC5tYXgoMSx5Yi15YSl9OwogICAgICB2YXIgbnQyPW5pdG9EZShsdW0sZHcsZGgsY2FqYTIpOwogICAgICB2YXIgYmxhMj1mcmFjY2lvbkJsYW5jbyhsdW0sZHcsZGgsY2FqYTIpOwogICAgICB2YXIgc3gyPXZ3L2R3LCBzeTI9dmgvZGg7CiAgICAgIHJldHVybiB7dGw6e3g6cTIudGwueCpzeDIseTpxMi50bC55KnN5Mn0sIHRyOnt4OnEyLnRyLngqc3gyLHk6cTIudHIueSpzeTJ9LCBicjp7eDpxMi5ici54KnN4Mix5OnEyLmJyLnkqc3kyfSwgYmw6e3g6cTIuYmwueCpzeDIseTpxMi5ibC55KnN5Mn0sIGx1ejpsdXosIG5pdG86bnQyLnYsIGJsYW5jbzpibGEyLCB2dzp2dywgdmg6dmgsIGZyYWM6dmFsMi5mcmFjfTsKICAgIH0KICAgIHZhciBtYXNrUz1uZXcgVWludDhBcnJheShuKSwgdG90Uz0wOwogICAgZm9yKGk9MDtpPG47aSsrKXsKICAgICAgdmFyIHI0PWRbaSo0XSwgZzQ9ZFtpKjQrMV0sIGI0PWRbaSo0KzJdOwogICAgICB2YXIgbXg9KHI0Pmc0KT8ocjQ+YjQ/cjQ6YjQpOihnND5iND9nNDpiNCksIG1uPShyNDxnNCk/KHI0PGI0P3I0OmI0KTooZzQ8YjQ/ZzQ6YjQpOwogICAgICBpZigobXgtbW4pPD04NSYmbHVtW2ldPj0xMTIpeyBtYXNrU1tpXT0xOyB0b3RTKys7IH0KICAgIH0KICAgIGlmKHRvdFM+PW4qMC4wMyl7CiAgICAgIHZhciByUz1yZXN1bHRhZG9EZU1hc2NhcmEobWFza1MpOwogICAgICBpZihyUyl7IHJldHVybiByUzsgfQogICAgfQogICAgdmFyIGxiPW5ldyBVaW50OEFycmF5KG4pOwogICAgZm9yKHk9MTt5PGRoLTE7eSsrKXsgZm9yKHg9MTt4PGR3LTE7eCsrKXsgdmFyIHBwPXkqZHcreDsgbGJbcHBdPShsdW1bcHBdKjQrbHVtW3BwLTFdK2x1bVtwcCsxXStsdW1bcHAtZHddK2x1bVtwcCtkd10pPj4zOyB9IH0KICAgIHZhciBoaXN0PW5ldyBJbnQzMkFycmF5KDI1Nik7IGZvcihpPTA7aTxuO2krKyl7IGhpc3RbbGJbaV1dKys7IH0KICAgIHZhciB0aHI9b3RzdVVtYnJhbChoaXN0LG4pOwogICAgdmFyIG1hc2s9bmV3IFVpbnQ4QXJyYXkobiksIHRvdD0wOwogICAgZm9yKGk9MDtpPG47aSsrKXsgdmFyIHYxPShsYltpXT50aHIpPzE6MDsgbWFza1tpXT12MTsgdG90Kz12MTsgfQogICAgaWYodG90PG4qMC4wMyl7IHJldHVybiBudWxsOyB9CiAgICBpZih0b3Q+biowLjk2NSl7CiAgICAgIHZhciBudDA9bml0b0RlKGx1bSxkdyxkaCxudWxsKTsKICAgICAgcmV0dXJuIHtsbGVubzp0cnVlLCBsdXo6bHV6LCBuaXRvOm50MC52LCBibGFuY286ZnJhY2Npb25CbGFuY28obHVtLGR3LGRoLG51bGwpLCB2dzp2dywgdmg6dmh9OwogICAgfQogICAgdmFyIGNjPWV0aXF1ZXRhQ29tcG9uZW50ZXMobWFzayxkdyxkaCk7CiAgICBpZighY2MubWVqb3IuaWR8fGNjLm1lam9yLnRhbTxuKjAuMDQpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIHE9ZXNxdWluYXNEZU1hc2NhcmEoY2MubGFiLGNjLm1lam9yLmlkLGR3LGRoKTsKICAgIGlmKCFxLnRsfHwhcS50cnx8IXEuYnJ8fCFxLmJsKXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciB2YWw9cXVhZFZhbGlkbyhxLGR3LGRoKTsKICAgIHZhciB4MD1NYXRoLm1heCgwLE1hdGgubWluKHEudGwueCxxLmJsLngpKSwgeDE9TWF0aC5taW4oZHcsTWF0aC5tYXgocS50ci54LHEuYnIueCkpOwogICAgdmFyIHkwPU1hdGgubWF4KDAsTWF0aC5taW4ocS50bC55LHEudHIueSkpLCB5MT1NYXRoLm1pbihkaCxNYXRoLm1heChxLmJsLnkscS5ici55KSk7CiAgICB2YXIgY2FqYT17eDp4MCx5OnkwLHc6TWF0aC5tYXgoMSx4MS14MCksaDpNYXRoLm1heCgxLHkxLXkwKX07CiAgICB2YXIgbnQ9bml0b0RlKGx1bSxkdyxkaCxjYWphKTsKICAgIHZhciBibGE9ZnJhY2Npb25CbGFuY28obHVtLGR3LGRoLGNhamEpOwogICAgdmFyIHN4PXZ3L2R3LCBzeT12aC9kaDsKICAgIGZ1bmN0aW9uIGVzYyhwKXsgcmV0dXJuIHt4OnAueCpzeCwgeTpwLnkqc3l9OyB9CiAgICB2YXIgcmVzPXt0bDplc2MocS50bCksIHRyOmVzYyhxLnRyKSwgYnI6ZXNjKHEuYnIpLCBibDplc2MocS5ibCksIGx1ejpsdXosIG5pdG86bnQudiwgYmxhbmNvOmJsYSwgdnc6dncsIHZoOnZofTsKICAgIGlmKCF2YWwub2speyByZXMuZGVzY2FydGFkbz12YWwubW90aXZvOyByZXR1cm4gcmVzOyB9CiAgICByZXMuZnJhYz12YWwuZnJhYzsKICAgIHJldHVybiByZXM7CiAgfWNhdGNoKGUpeyByZXR1cm4gbnVsbDsgfQp9CmZ1bmN0aW9uIGRldGVjdGFyRG9jQm94KHYpewogIHRyeXsKICAgIHZhciBEPXp5RGV0KCk7CiAgICB2YXIgYz1ELmN2RG9jOwogICAgaWYoIWMpeyBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOyBELmN2RG9jPWM7IH0KICAgIHZhciBkdz0xMjgsIGRoPU1hdGgubWF4KDgsTWF0aC5yb3VuZCgxMjgqKCh2LnZpZGVvSGVpZ2h0fHwzKS8oKHYudmlkZW9XaWR0aHx8NCkqMS4wKSkpKTsKICAgIGlmKGMud2lkdGghPT1kd3x8Yy5oZWlnaHQhPT1kaCl7IGMud2lkdGg9ZHc7IGMuaGVpZ2h0PWRoOyB9CiAgICB2YXIgZz1jLmdldENvbnRleHQoJzJkJyk7IGlmKCFnKXsgcmV0dXJuIG51bGw7IH0KICAgIGcuZHJhd0ltYWdlKHYsMCwwLGR3LGRoKTsKICAgIHZhciBkPWcuZ2V0SW1hZ2VEYXRhKDAsMCxkdyxkaCkuZGF0YSwgbj1kdypkaDsKICAgIHZhciBoaXN0PW5ldyBJbnQzMkFycmF5KDI1NiksIGx1bT1uZXcgVWludDhBcnJheShuKSwgaSx4LHk7CiAgICBmb3IoaT0wO2k8bjtpKyspeyB2YXIgcj1kW2kqNF0sIGdnPWRbaSo0KzFdLCBiPWRbaSo0KzJdOyBsdW1baV09KHIqMytnZyo0K2IpPj4zOyBoaXN0W2x1bVtpXV0rKzsgfQogICAgdmFyIHRocj1vdHN1VW1icmFsKGhpc3Qsbik7CiAgICB2YXIgZmlsYXM9bmV3IEludDMyQXJyYXkoZGgpLCBjb2xzPW5ldyBJbnQzMkFycmF5KGR3KSwgdG90PTA7CiAgICBmb3IoeT0wO3k8ZGg7eSsrKXsgZm9yKHg9MDt4PGR3O3grKyl7IGlmKGx1bVt5KmR3K3hdPnRocil7IGZpbGFzW3ldKys7IGNvbHNbeF0rKzsgdG90Kys7IH0gfSB9CiAgICBpZih0b3Q8biowLjA0fHx0b3Q+biowLjk4NSl7IHJldHVybiBudWxsOyB9CiAgICB2YXIgcmY9cmFuZ29Qcm95ZWNjaW9uKGZpbGFzLGRoLE1hdGgubWF4KDIsTWF0aC5yb3VuZChkdyowLjE4KSkpOwogICAgdmFyIHJjPXJhbmdvUHJveWVjY2lvbihjb2xzLGR3LE1hdGgubWF4KDIsTWF0aC5yb3VuZChkaCowLjE4KSkpOwogICAgaWYoIXJmfHwhcmMpeyByZXR1cm4gbnVsbDsgfQogICAgdmFyIHN4PSh2LnZpZGVvV2lkdGh8fDY0MCkvZHcsIHN5PSh2LnZpZGVvSGVpZ2h0fHw0ODApL2RoOwogICAgdmFyIGJ4PXJjWzBdKnN4LCBieT1yZlswXSpzeSwgYnc9KHJjWzFdKzEtcmNbMF0pKnN4LCBiaD0ocmZbMV0rMS1yZlswXSkqc3k7CiAgICBpZihidzw4fHxiaDw4KXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciBzdW1hPTAsIGkyOwogICAgZm9yKGkyPTA7aTI8bjtpMisrKXsgc3VtYSs9bHVtW2kyXTsgfQogICAgdmFyIGx1ej1zdW1hL247CiAgICB2YXIgc3VtVj0wLCBzdW1WMj0wLCBuMj0wLCB4MiwgeTI7CiAgICBmb3IoeTI9MTt5MjxkaC0xO3kyKyspewogICAgICBmb3IoeDI9MTt4Mjxkdy0xO3gyKyspewogICAgICAgIHZhciBpaT15Mipkdyt4MjsKICAgICAgICB2YXIgbGFwPTQqbHVtW2lpXS1sdW1baWktMV0tbHVtW2lpKzFdLWx1bVtpaS1kd10tbHVtW2lpK2R3XTsKICAgICAgICBzdW1WKz1sYXA7IHN1bVYyKz1sYXAqbGFwOyBuMisrOwogICAgICB9CiAgICB9CiAgICB2YXIgbWVkaWE9c3VtVi9NYXRoLm1heCgxLG4yKTsKICAgIHZhciB2YXJMPShzdW1WMi9NYXRoLm1heCgxLG4yKSktbWVkaWEqbWVkaWE7CiAgICByZXR1cm4ge3g6YngsIHk6YnksIHc6YncsIGg6YmgsIGx1ejpsdXosIG5pdG86KHZhckw+PTQwKSwgZm9jbzpNYXRoLnJvdW5kKHZhckwpfTsKICB9Y2F0Y2goZSl7IHJldHVybiBudWxsOyB9Cn0KZnVuY3Rpb24gY2VudHJvRGUocHVudG9zKXsKICB2YXIgc3g9MCwgc3k9MCwgaTsKICBmb3IoaT0wO2k8cHVudG9zLmxlbmd0aDtpKyspeyBzeCs9cHVudG9zW2ldLng7IHN5Kz1wdW50b3NbaV0ueTsgfQogIHJldHVybiB7eDpzeC9wdW50b3MubGVuZ3RoLCB5OnN5L3B1bnRvcy5sZW5ndGh9Owp9CmZ1bmN0aW9uIGVhckRlKHB1bnRvcyl7CiAgaWYoIXB1bnRvc3x8cHVudG9zLmxlbmd0aDw2KXsgcmV0dXJuIDE7IH0KICBmdW5jdGlvbiBkMihhLGIpeyB2YXIgZHg9YS54LWIueCwgZHk9YS55LWIueTsgcmV0dXJuIE1hdGguc3FydChkeCpkeCtkeSpkeSk7IH0KICB2YXIgaD1kMihwdW50b3NbMF0scHVudG9zWzNdKTsKICBpZihoPDFlLTYpeyByZXR1cm4gMTsgfQogIHJldHVybiAoZDIocHVudG9zWzFdLHB1bnRvc1s1XSkrZDIocHVudG9zWzJdLHB1bnRvc1s0XSkpLygyKmgpOwp9CmZ1bmN0aW9uIGV2YWx1YUNhcmEoaW5mbyl7CiAgdmFyIHI9e3Zpc3RhOnRydWUsIG9rOmZhbHNlLCB0YW06J2JpZW4nLCBtb3Rpdm86JycsIGNvZDonJ307CiAgaWYoaW5mby5sdXo8NDUpeyByLmNvZD0nbHV6Jzsgci5tb3Rpdm89J1BPQ0EgTFVaOiBwb24gdHUgY2FyYSBoYWNpYSBsYSBsdXogbyBlbmNpZW5kZSB1bmEgbGFtcGFyYS4nOyByZXR1cm4gcjsgfQogIGlmKGluZm8ubml0bzwxNSl7IHIuY29kPSduaXRvJzsgci5tb3Rpdm89J05vIHNlIHZlIE5JVElETzogc29zdFx1MDBFOW4gZWwgdGVsZWZvbm8gZmlybWUgeSBlc3BlcmEgZWwgZW5mb3F1ZS4nOyByZXR1cm4gcjsgfQogIGlmKGluZm8udGFtPDAuMzApeyByLnRhbT0nbGVqb3MnOyByLmNvZD0nbGVqb3MnOyByLm1vdGl2bz0nQUNFUkNBVEU6IHR1IGNhcmEgZGViZSBsbGVuYXIgZWwgT1ZBTE8gKGZvdG8gZGUgcm9zdHJvLCBubyBtZWRpbyBjdWVycG8pLic7IHJldHVybiByOyB9CiAgaWYoaW5mby50YW0+MC44Nil7IHIudGFtPSdjZXJjYSc7IHIuY29kPSdjZXJjYSc7IHIubW90aXZvPSdBTEVKQVRFIHVuIHBvY28gcGFyYSBxdWUgdHUgY2FyYSBxdWVwYSBlbnRlcmEgZW4gZWwgb3ZhbG8uJzsgcmV0dXJuIHI7IH0KICBpZihNYXRoLmFicyhpbmZvLmZ4LTAuNSk+MC4xNnx8aW5mby5meTwwLjMwfHxpbmZvLmZ5PjAuNzQpeyByLmNvZD0nZnVlcmEnOyByLm1vdGl2bz0nQ2VudHJhIHR1IGNhcmEgZGVudHJvIGRlbCBPVkFMTywgbWlyYW5kbyBhIGxhIGNhbWFyYS4nOyByZXR1cm4gcjsgfQogIGlmKE1hdGguYWJzKGluZm8ucm9sbCk+MTYpeyByLmNvZD0ncm9sbCc7IHIubW90aXZvPSdFbmRlcmV6YSBsYSBjYWJlemE6IG5vIGxhIGluY2xpbmVzIGEgbG9zIGxhZG9zLic7IHJldHVybiByOyB9CiAgaWYoTWF0aC5hYnMoaW5mby55YXcpPjAuMjQpeyByLmNvZD0neWF3Jzsgci5tb3Rpdm89J01pcmEgREUgRlJFTlRFIGEgbGEgY2FtYXJhLCBubyBkZSBsYWRvLic7IHJldHVybiByOyB9CiAgaWYoaW5mby5vam9zPDAuMTApeyByLmNvZD0nb2pvcyc7IHIubW90aXZvPSdBYnJlIGxvcyBvam9zIHkgbWlyYSBmaWpvIGEgbGEgY2FtYXJhLic7IHJldHVybiByOyB9CiAgci5vaz10cnVlOyByLm1vdGl2bz0nUGVyZmVjdG86IHNvc3RcdTAwRTluIGxhIHBvc2ljaW9uLi4uJzsKICByZXR1cm4gcjsKfQpmdW5jdGlvbiBuaXRvRGVSZ2JhKGRhdG9zLCBkdywgZGgsIGNhamEpewogIHZhciB4MD1NYXRoLm1heCgxLGNhamEueCsxKSwgeTA9TWF0aC5tYXgoMSxjYWphLnkrMSk7CiAgdmFyIHgxPU1hdGgubWluKGR3LTEsY2FqYS54K2NhamEudy0xKSwgeTE9TWF0aC5taW4oZGgtMSxjYWphLnkrY2FqYS5oLTEpOwogIHZhciBzPTAsczI9MCxrPTAseCx5OwogIGZvcih5PXkwO3k8eTE7eSsrKXsKICAgIGZvcih4PXgwO3g8eDE7eCsrKXsKICAgICAgdmFyIHA9eSpkdyt4OwogICAgICB2YXIgbDE9KGRhdG9zW3AqNF0qMytkYXRvc1twKjQrMV0qNCtkYXRvc1twKjQrMl0pPj4zOwogICAgICB2YXIgbDI9KGRhdG9zWyhwLTEpKjRdKjMrZGF0b3NbKHAtMSkqNCsxXSo0K2RhdG9zWyhwLTEpKjQrMl0pPj4zOwogICAgICB2YXIgbDM9KGRhdG9zWyhwKzEpKjRdKjMrZGF0b3NbKHArMSkqNCsxXSo0K2RhdG9zWyhwKzEpKjQrMl0pPj4zOwogICAgICB2YXIgbDQ9KGRhdG9zWyhwLWR3KSo0XSozK2RhdG9zWyhwLWR3KSo0KzFdKjQrZGF0b3NbKHAtZHcpKjQrMl0pPj4zOwogICAgICB2YXIgbDU9KGRhdG9zWyhwK2R3KSo0XSozK2RhdG9zWyhwK2R3KSo0KzFdKjQrZGF0b3NbKHArZHcpKjQrMl0pPj4zOwogICAgICB2YXIgbHA9NCpsMS1sMi1sMy1sNC1sNTsKICAgICAgcys9bHA7IHMyKz1scCpscDsgaysrOwogICAgfQogIH0KICBpZighayl7IHJldHVybiAwOyB9CiAgdmFyIG09cy9rOwogIHJldHVybiAoczIvayktbSptOwp9CmZ1bmN0aW9uIGJ1c2NhckNhcmFWaXZhKHYsIGNiKXsKICB0cnl7CiAgICBpZighKFcuZmFjZWFwaSYmVy5mYWNlYXBpLm5ldHMmJlcuZmFjZWFwaS5uZXRzLnRpbnlGYWNlRGV0ZWN0b3ImJlcuZmFjZWFwaS5UaW55RmFjZURldGVjdG9yT3B0aW9ucykpeyBjYihudWxsKTsgcmV0dXJuOyB9CiAgICB2YXIgRD16eURldCgpOwogICAgdmFyIHZ3PXYudmlkZW9XaWR0aHx8NjQwLCB2aD12LnZpZGVvSGVpZ2h0fHw0ODA7CiAgICB2YXIgZHc9MjI0LCBkaD1NYXRoLm1heCg4MCxNYXRoLnJvdW5kKGR3KnZoL3Z3KSk7CiAgICB2YXIgYz1ELmN2Q2FyYTsKICAgIGlmKCFjKXsgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsgRC5jdkNhcmE9YzsgfQogICAgaWYoYy53aWR0aCE9PWR3fHxjLmhlaWdodCE9PWRoKXsgYy53aWR0aD1kdzsgYy5oZWlnaHQ9ZGg7IH0KICAgIHZhciBnPWMuZ2V0Q29udGV4dCgnMmQnKTsgaWYoIWcpeyBjYihudWxsKTsgcmV0dXJuOyB9CiAgICBnLmRyYXdJbWFnZSh2LDAsMCxkdyxkaCk7CiAgICB2YXIgZGF0b3M9bnVsbDsKICAgIHRyeXsgZGF0b3M9Zy5nZXRJbWFnZURhdGEoMCwwLGR3LGRoKS5kYXRhOyB9Y2F0Y2goZSl7IGRhdG9zPW51bGw7IH0KICAgIHZhciBvcHQ9bmV3IFcuZmFjZWFwaS5UaW55RmFjZURldGVjdG9yT3B0aW9ucyh7aW5wdXRTaXplOjIyNCwgc2NvcmVUaHJlc2hvbGQ6MC40NX0pOwogICAgVy5mYWNlYXBpLmRldGVjdFNpbmdsZUZhY2UoYyxvcHQpLndpdGhGYWNlTGFuZG1hcmtzKCkud2l0aEZhY2VEZXNjcmlwdG9yKCkudGhlbihmdW5jdGlvbihyKXsKICAgICAgdHJ5ewogICAgICAgIGlmKCFyfHwhci5kZXRlY3Rpb24peyBjYih7dmlzdGE6ZmFsc2UsIG9rOmZhbHNlLCB0OkRhdGUubm93KCl9KTsgcmV0dXJuOyB9CiAgICAgICAgdmFyIGI9ci5kZXRlY3Rpb24uYm94OwogICAgICAgIHZhciBmeD0oYi54K2Iud2lkdGgvMikvZHcsIGZ5PShiLnkrYi5oZWlnaHQvMikvZGg7CiAgICAgICAgdmFyIHRhbT1iLmhlaWdodC9kaDsKICAgICAgICB2YXIgcm9sbD0wLCB5YXc9MCwgb2pvcz0xOwogICAgICAgIGlmKHIubGFuZG1hcmtzKXsKICAgICAgICAgIHZhciBMPXIubGFuZG1hcmtzLmdldExlZnRFeWUoKSwgUj1yLmxhbmRtYXJrcy5nZXRSaWdodEV5ZSgpLCBOPXIubGFuZG1hcmtzLmdldE5vc2UoKTsKICAgICAgICAgIGlmKEwmJlImJkwubGVuZ3RoPj00JiZSLmxlbmd0aD49NCl7CiAgICAgICAgICAgIHZhciBsYz1jZW50cm9EZShMKSwgcmM9Y2VudHJvRGUoUik7CiAgICAgICAgICAgIHJvbGw9TWF0aC5hdGFuMihyYy55LWxjLnksIHJjLngtbGMueCkqMTgwL01hdGguUEk7CiAgICAgICAgICAgIHZhciBteD0obGMueCtyYy54KS8yOwogICAgICAgICAgICBpZihOJiZOLmxlbmd0aD40KXsgeWF3PShOWzRdLngtbXgpL01hdGgubWF4KDEsYi53aWR0aCk7IH0KICAgICAgICAgICAgb2pvcz1NYXRoLm1pbihlYXJEZShMKSwgZWFyRGUoUikpOwogICAgICAgICAgfQogICAgICAgIH0KICAgICAgICB2YXIgY2FqYT17eDpNYXRoLnJvdW5kKGIueCp2dy9kdyksIHk6TWF0aC5yb3VuZChiLnkqdmgvZGgpLCB3Ok1hdGgucm91bmQoYi53aWR0aCp2dy9kdyksIGg6TWF0aC5yb3VuZChiLmhlaWdodCp2aC9kaCl9OwogICAgICAgIGNhamEueD1NYXRoLm1heCgwLHZ3LWNhamEueC1jYWphLncpOwogICAgICAgIHZhciBsdXo9MCwgbml0bz0wOwogICAgICAgIGlmKGRhdG9zKXsKICAgICAgICAgIHZhciByeDA9TWF0aC5tYXgoMCxNYXRoLnJvdW5kKGIueCkpLCByeTA9TWF0aC5tYXgoMCxNYXRoLnJvdW5kKGIueSkpOwogICAgICAgICAgdmFyIHJ4MT1NYXRoLm1pbihkdyxNYXRoLnJvdW5kKGIueCtiLndpZHRoKSksIHJ5MT1NYXRoLm1pbihkaCxNYXRoLnJvdW5kKGIueStiLmhlaWdodCkpOwogICAgICAgICAgdmFyIHM9MCxrPTAseCx5OwogICAgICAgICAgZm9yKHk9cnkwO3k8cnkxO3krKyl7IGZvcih4PXJ4MDt4PHJ4MTt4KyspeyBzKz0oZGF0b3NbKHkqZHcreCkqNF0qMytkYXRvc1soeSpkdyt4KSo0KzFdKjQrZGF0b3NbKHkqZHcreCkqNCsyXSk+PjM7IGsrKzsgfSB9CiAgICAgICAgICBsdXo9az8ocy9rKTowOwogICAgICAgICAgbml0bz0ocngxPnJ4MCsyJiZyeTE+cnkwKzIpP25pdG9EZVJnYmEoZGF0b3MsZHcsZGgse3g6cngwLHk6cnkwLHc6cngxLXJ4MCxoOnJ5MS1yeTB9KTowOwogICAgICAgIH0KICAgICAgICB2YXIgZGU9ZXZhbHVhQ2FyYSh7Zng6ZngsZnk6ZnksdGFtOnRhbSxyb2xsOnJvbGwseWF3Onlhdyxvam9zOm9qb3MsbHV6Omx1eixuaXRvOm5pdG99KTsKICAgICAgICBjYih7dmlzdGE6dHJ1ZSwgb2s6ZGUub2ssIGNvZDpkZS5jb2QsIG1vdGl2bzpkZS5tb3Rpdm8sIHRhbTpkZS50YW0sIGZ4OmZ4LCBmeTpmeSwgY2FqYTpjYWphLCBsdXo6bHV6LCBuaXRvOm5pdG8sIG9qb3M6b2pvcywgcm9sbDpyb2xsLCB5YXc6eWF3LCB0OkRhdGUubm93KCl9KTsKICAgICAgfWNhdGNoKGUpeyBjYihudWxsKTsgfQogICAgfSkuY2F0Y2goZnVuY3Rpb24oKXsgY2IobnVsbCk7IH0pOwogIH1jYXRjaChlKXsgY2IobnVsbCk7IH0KfQpmdW5jdGlvbiBlbm1hcmNhclZlcmRlKHBzSWQsIHYpewogIC8qIHYxMTogY29udG9ybm8gUE9MSUdPTkFMIHJlYWwgcXVlIHNpZ3VlIGFsIGRvY3VtZW50byAocHMgMiB5IDMpIHkgT1ZBTE8gY29uIG1vdG9yIGZhY2lhbCAocHMgNCkgKi8KICB0cnl7CiAgICB2YXIgT1Y9eycyJzonb3ZGJywnMyc6J292QScsJzQnOidvdlMnfTsKICAgIHZhciBvdklkPU9WW3BzSWRdOwogICAgaWYoIW92SWQpeyByZXR1cm47IH0KICAgIHZhciBzdElkPShwc0lkPT09JzInKT8nc3RGJzooKHBzSWQ9PT0nMycpPydzdEEnOidzdFYnKTsKICAgIHZhciBEPXp5RGV0KCk7CiAgICB2YXIgc3Q9RFtwc0lkXTsKICAgIGlmKCFzdCl7IHN0PURbcHNJZF09e2NhamE6bnVsbCwgdDotMWU5LCBlc3RhZG86JycsIGl2Om51bGx9OyB9CiAgICBzdC50MD1EYXRlLm5vdygpOyBzdC5jYWphPW51bGw7IHN0LmVzdGFkbz0nJzsgc3QuYXV0bz0wOyBzdC5hdXRvSGVjaG89ZmFsc2U7IHN0LmNkPTA7IHN0Lmhpc3Q9W107CiAgICB2YXIgcGludGFyRG9jPWZ1bmN0aW9uKGNhamEsIGVzdGFkbyl7CiAgICAgIHRyeXsKICAgICAgICB2YXIgb3Y9JChvdklkKTsgaWYoIW92KXsgcmV0dXJuOyB9CiAgICAgICAgdmFyIHZ3PSh2JiZ2LnZpZGVvV2lkdGgpfHwwLCB2aD0odiYmdi52aWRlb0hlaWdodCl8fDA7CiAgICAgICAgaWYoIXZ3fHwhdmgpeyByZXR1cm47IH0KICAgICAgICBpZihvdi53aWR0aCE9PXZ3fHxvdi5oZWlnaHQhPT12aCl7IG92LndpZHRoPXZ3OyBvdi5oZWlnaHQ9dmg7IH0KICAgICAgICB2YXIgZz1vdi5nZXRDb250ZXh0KCcyZCcpOyBpZighZyl7IHJldHVybjsgfQogICAgICAgIGcuY2xlYXJSZWN0KDAsMCx2dyx2aCk7CiAgICAgICAgdmFyIHgseSx3LGg7CiAgICAgICAgaWYoIWNhamEpeyB4PU1hdGgucm91bmQodncqMC4wNyk7IHk9TWF0aC5yb3VuZCh2aCowLjA5KTsgdz12dy14KjI7IGg9dmgteSoyOyB9CiAgICAgICAgZWxzZXsgeD1jYWphLng7IHk9Y2FqYS55OyB3PWNhamEudzsgaD1jYWphLmg7IH0KICAgICAgICBpZih3PDEwfHxoPDEwKXsgcmV0dXJuOyB9CiAgICAgICAgdmFyIGNvbD0oZXN0YWRvPT09J29rJyk/JyMzZmI5NTAnOigoZXN0YWRvPT09J21hbCcpPycjYzAzOTJiJzonI2UzYjM0MScpOwogICAgICAgIGcuc3Ryb2tlU3R5bGU9Y29sOyBnLmxpbmVXaWR0aD01OwogICAgICAgIHZhciBMPU1hdGgucm91bmQoTWF0aC5taW4odyxoKSooY2FqYT8wLjE2OjAuMTQpKTsKICAgICAgICBnLmJlZ2luUGF0aCgpOwogICAgICAgIGcubW92ZVRvKHgseStMKTsgZy5saW5lVG8oeCx5KTsgZy5saW5lVG8oeCtMLHkpOwogICAgICAgIGcubW92ZVRvKHgrdy1MLHkpOyBnLmxpbmVUbyh4K3cseSk7IGcubGluZVRvKHgrdyx5K0wpOwogICAgICAgIGcubW92ZVRvKHgrdyx5K2gtTCk7IGcubGluZVRvKHgrdyx5K2gpOyBnLmxpbmVUbyh4K3ctTCx5K2gpOwogICAgICAgIGcubW92ZVRvKHgrTCx5K2gpOyBnLmxpbmVUbyh4LHkraCk7IGcubGluZVRvKHgseStoLUwpOwogICAgICAgIGcuc3Ryb2tlKCk7CiAgICAgICAgZy5zYXZlKCk7CiAgICAgICAgZy5nbG9iYWxBbHBoYT1jYWphPzAuNDU6MC4yMDsKICAgICAgICBnLmxpbmVXaWR0aD0xLjY7IGcuc3Ryb2tlUmVjdCh4LHksdyxoKTsKICAgICAgICBnLnJlc3RvcmUoKTsKICAgICAgfWNhdGNoKGUpe30KICAgIH07CiAgICB2YXIgcGludGFyUXVhZD1mdW5jdGlvbihxdWFkLCBlc3RhZG8sIG51bWVybyl7CiAgICAgIHRyeXsKICAgICAgICB2YXIgb3Y9JChvdklkKTsgaWYoIW92KXsgcmV0dXJuOyB9CiAgICAgICAgdmFyIHZ3PSh2JiZ2LnZpZGVvV2lkdGgpfHwwLCB2aD0odiYmdi52aWRlb0hlaWdodCl8fDA7CiAgICAgICAgaWYoIXZ3fHwhdmgpeyByZXR1cm47IH0KICAgICAgICBpZihvdi53aWR0aCE9PXZ3fHxvdi5oZWlnaHQhPT12aCl7IG92LndpZHRoPXZ3OyBvdi5oZWlnaHQ9dmg7IH0KICAgICAgICB2YXIgZz1vdi5nZXRDb250ZXh0KCcyZCcpOyBpZighZyl7IHJldHVybjsgfQogICAgICAgIGcuY2xlYXJSZWN0KDAsMCx2dyx2aCk7CiAgICAgICAgaWYocXVhZCYmcXVhZC50bCYmcXVhZC50ciYmcXVhZC5iciYmcXVhZC5ibCl7CiAgICAgICAgICB2YXIgY29sPShlc3RhZG89PT0nb2snKT8nIzNmYjk1MCc6KChlc3RhZG89PT0nbWFsJyk/JyNlNjdlMjInOicjZTNiMzQxJyk7CiAgICAgICAgICB0cnl7CiAgICAgICAgICAgIGcuZmlsbFN0eWxlPSdyZ2JhKDAsMCwwLDAuNDUpJzsKICAgICAgICAgICAgZy5iZWdpblBhdGgoKTsKICAgICAgICAgICAgZy5yZWN0KDAsMCx2dyx2aCk7CiAgICAgICAgICAgIGcubW92ZVRvKHF1YWQudGwueCxxdWFkLnRsLnkpOyBnLmxpbmVUbyhxdWFkLnRyLngscXVhZC50ci55KTsgZy5saW5lVG8ocXVhZC5ici54LHF1YWQuYnIueSk7IGcubGluZVRvKHF1YWQuYmwueCxxdWFkLmJsLnkpOyBnLmNsb3NlUGF0aCgpOwogICAgICAgICAgICBnLmZpbGwoJ2V2ZW5vZGQnKTsKICAgICAgICAgIH1jYXRjaChlRil7IGcuZmlsbFN0eWxlPSdyZ2JhKDAsMCwwLDAuMjIpJzsgZy5maWxsUmVjdCgwLDAsdncsdmgpOyB9CiAgICAgICAgICBnLnN0cm9rZVN0eWxlPWNvbDsgZy5saW5lV2lkdGg9NTsgZy5saW5lSm9pbj0ncm91bmQnOwogICAgICAgICAgZy5iZWdpblBhdGgoKTsKICAgICAgICAgIGcubW92ZVRvKHF1YWQudGwueCxxdWFkLnRsLnkpOyBnLmxpbmVUbyhxdWFkLnRyLngscXVhZC50ci55KTsgZy5saW5lVG8ocXVhZC5ici54LHF1YWQuYnIueSk7IGcubGluZVRvKHF1YWQuYmwueCxxdWFkLmJsLnkpOyBnLmNsb3NlUGF0aCgpOwogICAgICAgICAgZy5zdHJva2UoKTsKICAgICAgICAgIGcuZmlsbFN0eWxlPWNvbDsKICAgICAgICAgIHZhciBwdHM9W3F1YWQudGwscXVhZC50cixxdWFkLmJyLHF1YWQuYmxdLCBpOwogICAgICAgICAgZm9yKGk9MDtpPDQ7aSsrKXsgZy5iZWdpblBhdGgoKTsgZy5hcmMocHRzW2ldLngscHRzW2ldLnksOSwwLE1hdGguUEkqMik7IGcuZmlsbCgpOyB9CiAgICAgICAgfWVsc2V7CiAgICAgICAgICB2YXIgeDI9TWF0aC5yb3VuZCh2dyowLjA3KSwgeTI9TWF0aC5yb3VuZCh2aCowLjEyKSwgdzI9dncteDIqMiwgaDI9dmgteTIqMjsKICAgICAgICAgIGcuc3Ryb2tlU3R5bGU9KGVzdGFkbz09PSdtYWwnKT8nI2U2N2UyMic6JyM5YWEwYTYnOwogICAgICAgICAgZy5saW5lV2lkdGg9NDsgZy5zZXRMaW5lRGFzaChbMTQsMTBdKTsKICAgICAgICAgIGcuc3Ryb2tlUmVjdCh4Mix5Mix3MixoMik7CiAgICAgICAgICBnLnNldExpbmVEYXNoKFtdKTsKICAgICAgICB9CiAgICAgICAgaWYobnVtZXJvPjApewogICAgICAgICAgZy5zYXZlKCk7CiAgICAgICAgICBnLmZvbnQ9J2JvbGQgMTEwcHggc2Fucy1zZXJpZic7IGcudGV4dEFsaWduPSdjZW50ZXInOyBnLnRleHRCYXNlbGluZT0nbWlkZGxlJzsKICAgICAgICAgIGcubGluZVdpZHRoPTEwOyBnLnN0cm9rZVN0eWxlPSdyZ2JhKDAsMCwwLDAuNTUpJzsKICAgICAgICAgIGcuc3Ryb2tlVGV4dChTdHJpbmcobnVtZXJvKSx2dy8yLHZoLzIpOwogICAgICAgICAgZy5maWxsU3R5bGU9JyMzZmI5NTAnOyBnLmZpbGxUZXh0KFN0cmluZyhudW1lcm8pLHZ3LzIsdmgvMik7CiAgICAgICAgICBnLnJlc3RvcmUoKTsKICAgICAgICB9CiAgICAgIH1jYXRjaChlKXt9CiAgICB9OwogICAgdmFyIHBpbnRhck92YWxvPWZ1bmN0aW9uKGVzdGFkbywgbnVtZXJvLCBpbmZvKXsKICAgICAgdHJ5ewogICAgICAgIHZhciBvdj0kKG92SWQpOyBpZighb3YpeyByZXR1cm47IH0KICAgICAgICB2YXIgdnc9KHYmJnYudmlkZW9XaWR0aCl8fDAsIHZoPSh2JiZ2LnZpZGVvSGVpZ2h0KXx8MDsKICAgICAgICBpZighdnd8fCF2aCl7IHJldHVybjsgfQogICAgICAgIGlmKG92LndpZHRoIT09dnd8fG92LmhlaWdodCE9PXZoKXsgb3Yud2lkdGg9dnc7IG92LmhlaWdodD12aDsgfQogICAgICAgIHZhciBnPW92LmdldENvbnRleHQoJzJkJyk7IGlmKCFnKXsgcmV0dXJuOyB9CiAgICAgICAgZy5jbGVhclJlY3QoMCwwLHZ3LHZoKTsKICAgICAgICB2YXIgY3g9dncqMC41LCBjeT12aCowLjUyLCByeD12dyowLjMwLCByeT12aCowLjM4OwogICAgICAgIHZhciBjb2w9KGVzdGFkbz09PSdvaycpPycjM2ZiOTUwJzooKGVzdGFkbz09PSdjYXJhJyk/JyNlM2IzNDEnOicjOWFhMGE2Jyk7CiAgICAgICAgdHJ5ewogICAgICAgICAgZy5maWxsU3R5bGU9J3JnYmEoMCwwLDAsMC40MCknOwogICAgICAgICAgZy5iZWdpblBhdGgoKTsKICAgICAgICAgIGcucmVjdCgwLDAsdncsdmgpOwogICAgICAgICAgZy5tb3ZlVG8oY3grcngsY3kpOwogICAgICAgICAgaWYoZy5lbGxpcHNlKXsgZy5lbGxpcHNlKGN4LGN5LHJ4LHJ5LDAsMCxNYXRoLlBJKjIpOyB9IGVsc2UgeyBnLnJlY3QoY3gtcngsY3ktcnkscngqMixyeSoyKTsgfQogICAgICAgICAgZy5maWxsKCdldmVub2RkJyk7CiAgICAgICAgfWNhdGNoKGVGKXsgZy5maWxsU3R5bGU9J3JnYmEoMCwwLDAsMC4yMiknOyBnLmZpbGxSZWN0KDAsMCx2dyx2aCk7IH0KICAgICAgICBnLnNhdmUoKTsKICAgICAgICBnLnN0cm9rZVN0eWxlPWNvbDsgZy5saW5lV2lkdGg9NjsKICAgICAgICBnLmJlZ2luUGF0aCgpOyBpZihnLmVsbGlwc2UpeyBnLmVsbGlwc2UoY3gsY3kscngscnksMCwwLE1hdGguUEkqMik7IH0gZWxzZSB7IGcuc3Ryb2tlUmVjdChjeC1yeCxjeS1yeSxyeCoyLHJ5KjIpOyB9CiAgICAgICAgZy5zdHJva2UoKTsKICAgICAgICBnLnJlc3RvcmUoKTsKICAgICAgICBpZihpbmZvJiZpbmZvLmNhamEmJmluZm8uY2FqYS53PjQpewogICAgICAgICAgZy5zdHJva2VTdHlsZT0oZXN0YWRvPT09J29rJyk/JyMzZmI5NTAnOicjZTNiMzQxJzsgZy5saW5lV2lkdGg9MzsKICAgICAgICAgIGcuc3Ryb2tlUmVjdChpbmZvLmNhamEueCxpbmZvLmNhamEueSxpbmZvLmNhamEudyxpbmZvLmNhamEuaCk7CiAgICAgICAgfQogICAgICAgIHZhciBwcm9nPShzdCYmc3QuYXV0byk/TWF0aC5taW4oMSxzdC5hdXRvLzQpOjA7CiAgICAgICAgaWYocHJvZz4wKXsKICAgICAgICAgIGcuc2F2ZSgpOyBnLnN0cm9rZVN0eWxlPScjM2ZiOTUwJzsgZy5saW5lV2lkdGg9ODsKICAgICAgICAgIGcuYmVnaW5QYXRoKCk7CiAgICAgICAgICBnLmFyYyhjeCxjeSxNYXRoLm1heChyeCxyeSkrMTYsLU1hdGguUEkvMiwtTWF0aC5QSS8yK3Byb2cqTWF0aC5QSSoyKTsKICAgICAgICAgIGcuc3Ryb2tlKCk7IGcucmVzdG9yZSgpOwogICAgICAgIH0KICAgICAgICBpZihudW1lcm8+MCl7CiAgICAgICAgICBnLnNhdmUoKTsKICAgICAgICAgIGcuZm9udD0nYm9sZCAxMTBweCBzYW5zLXNlcmlmJzsgZy50ZXh0QWxpZ249J2NlbnRlcic7IGcudGV4dEJhc2VsaW5lPSdtaWRkbGUnOwogICAgICAgICAgZy5saW5lV2lkdGg9MTA7IGcuc3Ryb2tlU3R5bGU9J3JnYmEoMCwwLDAsMC41NSknOwogICAgICAgICAgZy5zdHJva2VUZXh0KFN0cmluZyhudW1lcm8pLHZ3LzIsdmgvMik7CiAgICAgICAgICBnLmZpbGxTdHlsZT0nIzNmYjk1MCc7IGcuZmlsbFRleHQoU3RyaW5nKG51bWVybyksdncvMix2aC8yKTsKICAgICAgICAgIGcucmVzdG9yZSgpOwogICAgICAgIH0KICAgICAgfWNhdGNoKGUpe30KICAgIH07CiAgICB2YXIgdWx0aW1vPScnOwogICAgdmFyIGF2aXNhcj1mdW5jdGlvbihjb2RlLHR4dCxjb2xvcil7IGlmKGNvZGUhPT11bHRpbW8peyB1bHRpbW89Y29kZTsgbXNnKHN0SWQsdHh0LGNvbG9yKTsgfSB9OwogICAgaWYocHNJZD09PSc0Jyl7CiAgICAgIHBpbnRhck92YWxvKCcnLDAsbnVsbCk7CiAgICAgIGF2aXNhcignaW5pJywnUG9uIHR1IGNhcmEgZGVudHJvIGRlbCBPVkFMTy4gTGEgY2FwdHVyYSBlcyBBVVRPTUFUSUNBIGN1YW5kbyB0b2RvIGVzdGUgY29ycmVjdG8uJywnI2E2MCcpOwogICAgICBpZihzdC5pdil7IHRyeXsgY2xlYXJJbnRlcnZhbChzdC5pdik7IH1jYXRjaChlKXt9IH0KICAgICAgc3QuaXY9c2V0SW50ZXJ2YWwoZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICBpZighc3RyZWFtc1twc0lkXSl7IHJldHVybjsgfQogICAgICAgICAgYnVzY2FyQ2FyYVZpdmEodixmdW5jdGlvbihpbmZvKXsKICAgICAgICAgICAgdHJ5ewogICAgICAgICAgICAgIEVTVC5jYXJhVml2YT1pbmZvOwogICAgICAgICAgICAgIGlmKCFpbmZvfHwhaW5mby52aXN0YSl7CiAgICAgICAgICAgICAgICBzdC5hdXRvPTA7IHN0LmNkPTA7CiAgICAgICAgICAgICAgICBwaW50YXJPdmFsbygnY2FyYScsMCxpbmZvfHxudWxsKTsKICAgICAgICAgICAgICAgIGF2aXNhcigoaW5mbyYmaW5mby5jb2QpfHwnbm9kZXQnLChpbmZvJiZpbmZvLm1vdGl2byl8fCdCdXNjYW5kbyB0dSBjYXJhLi4uIGJ1ZW5hIGx1eiwgc2luIGdvcnJhIG5pIGxlbnRlcyBvc2N1cm9zLicsJyNhNjAnKTsKICAgICAgICAgICAgICAgIHJldHVybjsKICAgICAgICAgICAgICB9CiAgICAgICAgICAgICAgdmFyIG51bWVybz0wOwogICAgICAgICAgICAgIGlmKGluZm8ub2speyBzdC5hdXRvPShzdC5hdXRvfHwwKSsxOyB9IGVsc2UgeyBzdC5hdXRvPTA7IHN0LmNkPTA7IH0KICAgICAgICAgICAgICBpZihzdC5hdXRvPj00KXsKICAgICAgICAgICAgICAgIHN0LmNkPShzdC5jZHx8MCkrMTsKICAgICAgICAgICAgICAgIG51bWVybz1NYXRoLm1heCgxLDQtc3QuY2QpOwogICAgICAgICAgICAgICAgcGludGFyT3ZhbG8oJ29rJyxudW1lcm8saW5mbyk7CiAgICAgICAgICAgICAgICBhdmlzYXIoJ2NkJytudW1lcm8sJ0NhcHR1cmFuZG8gZW4gJytudW1lcm8rJy4uLiBubyB0ZSBtdWV2YXMuJywnIzA4MCcpOwogICAgICAgICAgICAgICAgaWYoc3QuY2Q+PTQmJiFzdC5hdXRvSGVjaG8pewogICAgICAgICAgICAgICAgICBzdC5hdXRvSGVjaG89dHJ1ZTsgdmlicmFyKCk7CiAgICAgICAgICAgICAgICAgIHByb2Nlc2FyU2VsZmllKCk7CiAgICAgICAgICAgICAgICB9CiAgICAgICAgICAgICAgICByZXR1cm47CiAgICAgICAgICAgICAgfQogICAgICAgICAgICAgIHBpbnRhck92YWxvKGluZm8ub2s/J29rJzonY2FyYScsMCxpbmZvKTsKICAgICAgICAgICAgICBhdmlzYXIoaW5mby5vaz8ncHJlJzppbmZvLmNvZCwgaW5mby5tb3Rpdm8sIGluZm8ub2s/JyMwODAnOicjYTYwJyk7CiAgICAgICAgICAgIH1jYXRjaChlMyl7fQogICAgICAgICAgfSk7CiAgICAgICAgfWNhdGNoKGUpe30KICAgICAgfSw0MzApOwogICAgfWVsc2V7CiAgICAgIHBpbnRhckRvYyhudWxsLCcnKTsKICAgICAgYXZpc2FyKCdpbmknLCdCdXNjYW5kbyBlbCBkb2N1bWVudG8uLi4gcG9ubG8gc29icmUgZm9uZG8gT1NDVVJPLCBzaW4gYnJpbGxvLiBMYXMgNCBlc3F1aW5hcyBzZSBtYXJjYW4gc29sYXMuJywnI2E2MCcpOwogICAgICBpZihzdC5pdil7IHRyeXsgY2xlYXJJbnRlcnZhbChzdC5pdik7IH1jYXRjaChlKXt9IH0KICAgICAgc3QuaXY9c2V0SW50ZXJ2YWwoZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICBpZighc3RyZWFtc1twc0lkXSl7IHJldHVybjsgfQogICAgICAgICAgdmFyIHE9ZGV0ZWN0YXJEb2NRdWFkKHYpOwogICAgICAgICAgdmFyIGVzdD0nbWFsJywgY29kPSdub25lJywgdHh0PSdCdXNjYW5kbyBlbCBkb2N1bWVudG8uLi4gcG9ubG8gc29icmUgZm9uZG8gT1NDVVJPLCBsbGVuYW5kbyBlbCBtYXJjbywgc2luIGJyaWxsby4nLCBjb2w9JyNhNjAnLCBxdWFkPW51bGwsIG51bWVybz0wOwogICAgICAgICAgaWYocSYmcS5sbGVubyl7CiAgICAgICAgICAgIHZhciBiMT1xLmx1ej49NDgsIGIyPXEubml0bz49MzQsIGIzPShxLmJsYW5jbz09bnVsbCl8fChxLmJsYW5jbzw9MC4yMik7CiAgICAgICAgICAgIHN0LmF1dG89MDsKICAgICAgICAgICAgaWYoIWIxKXsgc3QuY2Q9MDsgZXN0PSdtYWwnOyBjb2Q9J2x1eic7IHR4dD0nUE9DQSBMVVo6IGJ1c2NhIG1lam9yIGlsdW1pbmFjaW9uIG8gdXNhIEVsZWdpciBhcmNoaXZvIGNvbiB1bmEgZm90byBkZSBjZXJjYS4nOyBjb2w9JyNjMDAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYoIWIyKXsgc3QuY2Q9MDsgZXN0PSdtYWwnOyBjb2Q9J25pdG8nOyB0eHQ9J05vIHNlIHZlIE5JVElETzogc29zdFx1MDBFOW4gZmlybWUsIGVzcGVyYSBlbCBlbmZvcXVlIHkgZXZpdGEgZWwgYnJpbGxvLic7IGNvbD0nI2MwMCc7IH0KICAgICAgICAgICAgZWxzZSBpZighYjMpeyBzdC5jZD0wOyBlc3Q9J21hbCc7IGNvZD0nYmxhJzsgdHh0PSdIYXkgUkVGTEVKTyBlbiBlbCBkb2N1bWVudG86IGluY2xcdTAwRURuYWxvIHVuIHBvY28gcGFyYSBxdWl0YXIgZWwgYnJpbGxvLic7IGNvbD0nI2MwMCc7IH0KICAgICAgICAgICAgZWxzZXsKICAgICAgICAgICAgICAvKiBoZXJlZGFkbyB2MTQ6IHNpIGVsIGRvY3VtZW50byBsbGVuYSBlbCBjdWFkcm8gY29uIGx1eiB5IG5pdGlkZXosCiAgICAgICAgICAgICAgICAgdGFtYmllbiBjYXB0dXJhIFNPTE8gY29uIGN1ZW50YSBhdHJhcyAoYW50ZXMgb2JsaWdhYmEgYSB0b2NhcgogICAgICAgICAgICAgICAgIENBUFRVUkFSKS4gTWlzbW8gMy0yLTEgcXVlIGN1YW5kbyBoYXkgNCBlc3F1aW5hcy4gKi8KICAgICAgICAgICAgICBzdC5jZD0oc3QuY2R8fDApKzE7CiAgICAgICAgICAgICAgbnVtZXJvPU1hdGgubWF4KDEsNC1zdC5jZCk7CiAgICAgICAgICAgICAgZXN0PSdvayc7IGNvZD0nY2QnK251bWVybzsgdHh0PSdDYXB0dXJhbmRvIGVuICcrbnVtZXJvKycuLi4gbm8gdGUgbXVldmFzLic7IGNvbD0nIzA4MCc7CiAgICAgICAgICAgICAgaWYoc3QuY2Q+PTQmJiFzdC5hdXRvSGVjaG8pewogICAgICAgICAgICAgICAgc3QuYXV0b0hlY2hvPXRydWU7IHZpYnJhcigpOwogICAgICAgICAgICAgICAgbWFuZWphcihwc0lkPT09JzInPydiQ2FwRic6J2JDYXBBJyk7CiAgICAgICAgICAgICAgICByZXR1cm47CiAgICAgICAgICAgICAgfQogICAgICAgICAgICB9CiAgICAgICAgICAgIHBpbnRhckRvYyhudWxsLCBlc3QpOwogICAgICAgICAgfWVsc2UgaWYocSl7CiAgICAgICAgICAgIHF1YWQ9cTsKICAgICAgICAgICAgc3QuaGlzdC5wdXNoKHF1YWQpOyBzdC51bHRRdWFkPXF1YWQ7IHN0LnVsdFF1YWRUPURhdGUubm93KCk7CiAgICAgICAgICAgIGlmKHN0Lmhpc3QubGVuZ3RoPjcpeyBzdC5oaXN0LnNoaWZ0KCk7IH0KICAgICAgICAgICAgdmFyIGMxPXEubHV6Pj00OCwgYzI9cS5uaXRvPj0zNCwgYzM9KHEuYmxhbmNvPT1udWxsKXx8KHEuYmxhbmNvPD0wLjIwKTsKICAgICAgICAgICAgc3QuYXV0bz0wOyBzdC5jZD0wOwogICAgICAgICAgICBpZihxLmRlc2NhcnRhZG89PT0ncGVxdWVubycpeyBlc3Q9J21hbCc7IGNvZD0nZmFyJzsgdHh0PSdBQ0VSQ0FURTogZWwgZG9jdW1lbnRvIHNlIHZlIG11eSBwZXF1ZVx1MDBGMW8gZW4gbGEgZm90by4nOyBjb2w9JyNhNjAnOyB9CiAgICAgICAgICAgIGVsc2UgaWYocS5kZXNjYXJ0YWRvPT09J2Zvcm1hJyl7IGVzdD0nbWFsJzsgY29kPSdmb3JtYSc7IHR4dD0nTm8gdmVvIGJpZW4gbGFzIDQgZXNxdWluYXM6IGFjXHUwMEU5cmNhdGUgeSB1c2EgdW4gZm9uZG8gb3NjdXJvLic7IGNvbD0nI2E2MCc7IH0KICAgICAgICAgICAgZWxzZSBpZighYzEpeyBlc3Q9J21hbCc7IGNvZD0nbHV6JzsgdHh0PSdQT0NBIExVWjogYnVzY2EgbWVqb3IgaWx1bWluYWNpb24gbyB1c2EgRWxlZ2lyIGFyY2hpdm8gY29uIHVuYSBmb3RvIGRlIGNlcmNhLic7IGNvbD0nI2MwMCc7IH0KICAgICAgICAgICAgZWxzZSBpZighYzIpeyBlc3Q9J21hbCc7IGNvZD0nbml0byc7IHR4dD0nTm8gc2UgdmUgTklUSURPOiBzb3N0XHUwMEU5biBmaXJtZSwgZXNwZXJhIGVsIGVuZm9xdWUgeSBldml0YSBlbCBicmlsbG8uJzsgY29sPScjYzAwJzsgfQogICAgICAgICAgICBlbHNlIGlmKCFjMyl7IGVzdD0nbWFsJzsgY29kPSdibGEnOyB0eHQ9J0hheSBSRUZMRUpPIGVuIGVsIGRvY3VtZW50bzogaW5jbFx1MDBFRG5hbG8gdW4gcG9jbyBwYXJhIHF1aXRhciBlbCBicmlsbG8uJzsgY29sPScjYzAwJzsgfQogICAgICAgICAgICBlbHNlIGlmKHF1YWRFc3RhYmxlKHN0Lmhpc3QpKXsKICAgICAgICAgICAgICBzdC5hdXRvPTE7CiAgICAgICAgICAgICAgc3QuY2Q9KHN0LmNkfHwwKSsxOwogICAgICAgICAgICAgIG51bWVybz1NYXRoLm1heCgxLDQtc3QuY2QpOwogICAgICAgICAgICAgIGVzdD0nb2snOyBjb2Q9J2NkJytudW1lcm87IHR4dD0nQ2FwdHVyYW5kbyBlbiAnK251bWVybysnLi4uIG5vIHRlIG11ZXZhcy4nOyBjb2w9JyMwODAnOwogICAgICAgICAgICAgIGlmKHN0LmNkPj00JiYhc3QuYXV0b0hlY2hvKXsKICAgICAgICAgICAgICAgIHN0LmF1dG9IZWNobz10cnVlOyB2aWJyYXIoKTsKICAgICAgICAgICAgICAgIG1hbmVqYXIocHNJZD09PScyJz8nYkNhcEYnOidiQ2FwQScpOwogICAgICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgICAgIH0KICAgICAgICAgICAgfWVsc2V7CiAgICAgICAgICAgICAgZXN0PSdjYXNpJzsgY29kPSdlc3BlcmEnOyB0eHQ9J0RvY3VtZW50byBkZXRlY3RhZG8uIFNvc3RlbmxvIHF1aWV0byBwYXJhIGNhcHR1cmFyIHNvbG8uLi4nOyBjb2w9JyMwODAnOwogICAgICAgICAgICB9CiAgICAgICAgICAgIHBpbnRhclF1YWQocXVhZCwgZXN0LCBudW1lcm8pOwogICAgICAgICAgfWVsc2V7CiAgICAgICAgICAgIHN0LmF1dG89MDsgc3QuY2Q9MDsKICAgICAgICAgICAgaWYoRGF0ZS5ub3coKS1zdC50PjEyMDApeyBzdC5jYWphPW51bGw7IH0KICAgICAgICAgICAgdmFyIGNhamFGPWRldGVjdGFyRG9jQm94KHYpOwogICAgICAgICAgICBpZihjYWphRil7CiAgICAgICAgICAgICAgc3QuY2FqYT1jYWphRjsgc3QudWx0Q2FqYT1jYWphRjsgc3QudWx0Q2FqYVQ9RGF0ZS5ub3coKTsgc3QudD1EYXRlLm5vdygpOwogICAgICAgICAgICAgIGVzdD0oY2FqYUYubml0byYmY2FqYUYubHV6Pj00OCk/J2Nhc2knOidtYWwnOwogICAgICAgICAgICAgIGNvZD0oZXN0PT09J2Nhc2knKT8nYXByb3gnOidjYWwnOwogICAgICAgICAgICAgIHR4dD0oZXN0PT09J2Nhc2knKT8nQ2FzaTogc29zdFx1MDBFOW4gcXVpZXRvLiBDb24gZm9uZG8gb3NjdXJvIG1hcmNvIGxhcyA0IGVzcXVpbmFzIHkgY2FwdHVybyBzb2xvLic6J1NlIHZlIGZsb2pvOiBtXHUwMEUxcyBsdXosIGZpcm1lLCBzaW4gYnJpbGxvLic7CiAgICAgICAgICAgICAgY29sPShlc3Q9PT0nY2FzaScpPycjYTYwJzonI2MwMCc7CiAgICAgICAgICAgIH1lbHNlIGlmKERhdGUubm93KCktc3QudD4xMjAwKXsKICAgICAgICAgICAgICBjb2Q9J25vbmUnOyB0eHQ9J0J1c2NhbmRvIGVsIGRvY3VtZW50by4uLiBwb25sbyBzb2JyZSBmb25kbyBPU0NVUk8sIGxsZW5hbmRvIGVsIG1hcmNvLCBzaW4gYnJpbGxvLic7CiAgICAgICAgICAgIH0KICAgICAgICAgICAgcGludGFyRG9jKGNhamFGfHxzdC5jYWphfHxudWxsLCBlc3QpOwogICAgICAgICAgfQogICAgICAgICAgYXZpc2FyKGNvZCx0eHQsY29sKTsKICAgICAgICB9Y2F0Y2goZSl7fQogICAgICB9LDMwMCk7CiAgICB9CiAgICBpZighdi5fX3p5TWFyY28pewogICAgICB2Ll9fenlNYXJjbz0xOwogICAgICB2LmFkZEV2ZW50TGlzdGVuZXIoJ3BsYXlpbmcnLGZ1bmN0aW9uKCl7IHRyeXsgYWxpbmVhck92ZXJsYXkocHNJZCwgdik7IGlmKHBzSWQ9PT0nNCcpeyBwaW50YXJPdmFsbygnJywwLG51bGwpOyB9IGVsc2UgeyBwaW50YXJEb2MobnVsbCwnJyk7IH0gfWNhdGNoKGUpe30gfSk7CiAgICAgIHYuYWRkRXZlbnRMaXN0ZW5lcignbG9hZGVkbWV0YWRhdGEnLGZ1bmN0aW9uKCl7IHRyeXsgYWxpbmVhck92ZXJsYXkocHNJZCwgdik7IGlmKHBzSWQ9PT0nNCcpeyBwaW50YXJPdmFsbygnJywwLG51bGwpOyB9IGVsc2UgeyBwaW50YXJEb2MobnVsbCwnJyk7IH0gfWNhdGNoKGUpe30gfSk7CiAgICB9CiAgfWNhdGNoKGUpe30KfQpmdW5jdGlvbiBpbnRlbnRhckVuZm9xdWUoc3QpewogIHRyeXsKICAgIHZhciB0cj0oc3QmJnN0LmdldFZpZGVvVHJhY2tzKT9zdC5nZXRWaWRlb1RyYWNrcygpWzBdOm51bGw7CiAgICBpZighdHIpeyByZXR1cm47IH0KICAgIHZhciBjYXBzPXRyLmdldENhcGFiaWxpdGllcz90ci5nZXRDYXBhYmlsaXRpZXMoKTpudWxsOwogICAgaWYoY2FwcyYmY2Fwcy5mb2N1c01vZGUmJmNhcHMuZm9jdXNNb2RlLmpvaW4mJmNhcHMuZm9jdXNNb2RlLmpvaW4oJyAnKS5pbmRleE9mKCdjb250aW51b3VzJyk+PTApewogICAgICB2YXIgcD10ci5hcHBseUNvbnN0cmFpbnRzKHthZHZhbmNlZDpbe2ZvY3VzTW9kZTonY29udGludW91cyd9XX0pOwogICAgICBpZihwJiZwLmNhdGNoKXsgcC5jYXRjaChmdW5jdGlvbigpe30pOyB9CiAgICB9CiAgfWNhdGNoKGUpe30KfQpmdW5jdGlvbiBhYnJpckNhbShwc0lkLCBmYWNpbmcsIHN0SWQsIGNhcElkKXsKICB2YXIgdj1maW5kVmlkZW8ocHNJZCk7CiAgaWYoIXYpeyBtc2coc3RJZCwnTm8gZW5jb250cmUgZWwgdmlkZW8gZGUgbGEgY2FtYXJhIGVuIGxhIHBhZ2luYS4nLCAnI2MwMCcpOyByZXR1cm4gUHJvbWlzZS5yZWplY3QobmV3IEVycm9yKCdzaW4gdmlkZW8nKSk7IH0KICBpZighbmF2aWdhdG9yLm1lZGlhRGV2aWNlcyB8fCAhbmF2aWdhdG9yLm1lZGlhRGV2aWNlcy5nZXRVc2VyTWVkaWEpewogICAgbXNnKHN0SWQsJ1R1IG5hdmVnYWRvciBubyBwZXJtaXRlIGNhbWFyYS4gVXNhIGxhIG9wY2lvbiBkZSBnYWxlcmlhLicsICcjYzAwJyk7CiAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QobmV3IEVycm9yKCdzaW4gY2FtYXJhJykpOwogIH0KICBwYXJhckNhbShwc0lkKTsKICB2YXIgem9uYT0kKCd2eicrbGV0cmFEZShwc0lkKSk7CiAgaWYoem9uYSl7IHpvbmEuc3R5bGUuZGlzcGxheT0nYmxvY2snOyB9CiAgbXNnKHN0SWQsJ1BpZGllbmRvIHBlcm1pc28gZGUgY2FtYXJhLi4uJywnJyk7CiAgdmFyIGRvY1pvbmE9KHBzSWQ9PT0nMid8fHBzSWQ9PT0nMycpOwogIHJldHVybiBuYXZpZ2F0b3IubWVkaWFEZXZpY2VzLmdldFVzZXJNZWRpYSh7YXVkaW86ZmFsc2UsIHZpZGVvOntmYWNpbmdNb2RlOmZhY2luZywgd2lkdGg6e2lkZWFsOmRvY1pvbmE/MTkyMDoxMjgwfSwgaGVpZ2h0OntpZGVhbDpkb2Nab25hPzEwODA6NzIwfX19KS50aGVuKGZ1bmN0aW9uKHN0KXsKICAgIHN0cmVhbXNbcHNJZF09c3Q7CiAgICB2LnNyY09iamVjdD1zdDsKICAgIHRyeXsgdi5zZXRBdHRyaWJ1dGUoJ3BsYXlzaW5saW5lJywncGxheXNpbmxpbmUnKTsgfWNhdGNoKGUpe30KICAgIHYubXV0ZWQ9dHJ1ZTsKICAgIHRyeXsgdi5zdHlsZS50cmFuc2Zvcm09KHBzSWQ9PT0nNCcpPydzY2FsZVgoLTEpJzonJzsgfWNhdGNoKGVNKXt9CiAgICBpbnRlbnRhckVuZm9xdWUoc3QpOwogICAgdmFyIHA9di5wbGF5KCk7IGlmKHAmJnAuY2F0Y2gpeyBwLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH0KICAgIGVzdGlsb0NoaWNvKHYpOwogICAgdmFyIGNhcD0kKGNhcElkKTsKICAgIGlmKGNhcCl7IGNhcC5kaXNhYmxlZD1mYWxzZTsgY2FwLnN0eWxlLmRpc3BsYXk9Jyc7IGNhcC5zdHlsZS52aXNpYmlsaXR5PSd2aXNpYmxlJzsgY2FwLnN0eWxlLnBvaW50ZXJFdmVudHM9J2F1dG8nOyBjYXAuc3R5bGUucG9zaXRpb249Y2FwLnN0eWxlLnBvc2l0aW9ufHwncmVsYXRpdmUnOyBjYXAuc3R5bGUuekluZGV4PSc5OTk5JzsgfQogICAgdmFyIE9WPXsnMic6J292RicsJzMnOidvdkEnLCc0Jzonb3ZTJ307CiAgICB2YXIgb3Y9JChPVltwc0lkXSk7CiAgICBpZihvdil7IG92LnN0eWxlLnBvaW50ZXJFdmVudHM9J25vbmUnOyB9CiAgICB2YXIgem9uYT0kKCd2eicrbGV0cmFEZShwc0lkKSk7CiAgICBpZih6b25hKXsgem9uYS5zdHlsZS5wb3NpdGlvbj0ncmVsYXRpdmUnOyB9CiAgICBlbm1hcmNhclZlcmRlKHBzSWQsIHYpOwogICAgYWxpbmVhck92ZXJsYXkocHNJZCwgdik7CiAgICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IHRyeXsgYWxpbmVhck92ZXJsYXkocHNJZCwgdik7IH1jYXRjaChlKXt9IH0sMjUwKTsKICAgIHZhciBxPShwc0lkPT09JzQnKTsKICAgIG1zZyhzdElkLCBxPydDYW1hcmEgbGlzdGEuIFBvbiB0dSBjYXJhIGVuIGVsIE9WQUxPOiBzZSBjYXB0dXJhIFNPTE8gY3VhbmRvIHRvZG8gZXN0ZSBjb3JyZWN0by4nOidDYW1hcmEgbGlzdGEuIEJ1c2NvIGxhcyA0IGVzcXVpbmFzIGRlbCBkb2N1bWVudG86IHNvc3RcdTAwRTlubG8gcXVpZXRvIHkgY2FwdHVybyBzb2xvLicsJyMwODAnKTsKICAgIHJldHVybiB0cnVlOwogIH0pLmNhdGNoKGZ1bmN0aW9uKGUpewogICAgaWYoem9uYSl7IHRyeXsgem9uYS5zdHlsZS5kaXNwbGF5PSdub25lJzsgfWNhdGNoKGUyKXt9IH0KICAgIG1zZyhzdElkLCdObyBwdWRlIGFicmlyIGxhIGNhbWFyYSAoJysoZSYmZS5uYW1lP2UubmFtZTonZXJyb3InKSsnKS4gUHVlZGVzIHVzYXIgbGEgZ2FsZXJpYSBvIHJldmlzYSBlbCBwZXJtaXNvLicsJyNjMDAnKTsKICAgIHRocm93IGU7CiAgfSk7Cn0KZnVuY3Rpb24gcGFyYXJDYW0ocHNJZCl7CiAgdmFyIHN0PXN0cmVhbXNbcHNJZF07CiAgaWYoc3QpewogICAgdHJ5eyBzdC5nZXRUcmFja3MoKS5mb3JFYWNoKGZ1bmN0aW9uKHQpeyB0cnl7IHQuc3RvcCgpOyB9Y2F0Y2goZSl7fSB9KTsgfWNhdGNoKGUpe30KICB9CiAgc3RyZWFtc1twc0lkXT1udWxsOwogIHRyeXsKICAgIHZhciB2dj1maW5kVmlkZW8ocHNJZCk7CiAgICBpZih2dil7IHZ2LnN0eWxlLnRyYW5zZm9ybT0nJzsgfQogIH1jYXRjaChlVCl7fQogIHRyeXsKICAgIHZhciBEPXp5RGV0KCksIHN0RD1EW3BzSWRdOwogICAgaWYoc3REJiZzdEQuaXYpeyBjbGVhckludGVydmFsKHN0RC5pdik7IHN0RC5pdj1udWxsOyB9CiAgICBpZihwc0lkPT09JzQnKXsgRVNULmNhcmFWaXZhPW51bGw7IH0KICB9Y2F0Y2goZSl7fQogIHRyeXsKICAgIHZhciB6b25hPSQoJ3Z6JytsZXRyYURlKHBzSWQpKTsKICAgIGlmKHpvbmEpeyB6b25hLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgICB2YXIgT1Y9eycyJzonb3ZGJywnMyc6J292QScsJzQnOidvdlMnfTsKICAgIHZhciBvdj0kKE9WW3BzSWRdKTsKICAgIGlmKG92KXsgdmFyIGc9b3YuZ2V0Q29udGV4dCgnMmQnKTsgaWYoZyl7IGcuY2xlYXJSZWN0KDAsMCxvdi53aWR0aHx8MSxvdi5oZWlnaHR8fDEpOyB9IH0KICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIHBhcmFyVG9kYXMoKXsgdmFyIGs7IGZvcihrIGluIHN0cmVhbXMpeyBwYXJhckNhbShrKTsgfSB9CmZ1bmN0aW9uIGNhcHR1cmFyVmlkZW8ocHNJZCwgbWF4RGltKXsKICB2YXIgdj1maW5kVmlkZW8ocHNJZCk7CiAgaWYoIXYgfHwgIXYudmlkZW9XaWR0aCB8fCAhc3RyZWFtc1twc0lkXSl7IHJldHVybiBudWxsOyB9CiAgdmFyIHc9di52aWRlb1dpZHRoLCBoPXYudmlkZW9IZWlnaHQ7CiAgdmFyIHNjPU1hdGgubWluKDEsKG1heERpbXx8MTAyNCkvTWF0aC5tYXgodyxoKSk7CiAgdmFyIGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7CiAgYy53aWR0aD1NYXRoLnJvdW5kKHcqc2MpOyBjLmhlaWdodD1NYXRoLnJvdW5kKGgqc2MpOwogIGMuZ2V0Q29udGV4dCgnMmQnKS5kcmF3SW1hZ2UodiwwLDAsYy53aWR0aCxjLmhlaWdodCk7CiAgdmFyIGQ9Yy50b0RhdGFVUkwoJ2ltYWdlL2pwZWcnLDAuOSk7CiAgcGFyYXJDYW0ocHNJZCk7CiAgcmV0dXJuIGQ7Cn0KZnVuY3Rpb24gZG93bnNjYWxlKGRhdGFVcmwsIG1heERpbSl7CiAgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7CiAgICB2YXIgaW09bmV3IEltYWdlKCk7CiAgICBpbS5vbmxvYWQ9ZnVuY3Rpb24oKXsKICAgICAgdmFyIHNjPU1hdGgubWluKDEsKG1heERpbXx8MTAyNCkvTWF0aC5tYXgoaW0ud2lkdGgsaW0uaGVpZ2h0KSk7CiAgICAgIHZhciBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOwogICAgICBjLndpZHRoPU1hdGgubWF4KDEsTWF0aC5yb3VuZChpbS53aWR0aCpzYykpOwogICAgICBjLmhlaWdodD1NYXRoLm1heCgxLE1hdGgucm91bmQoaW0uaGVpZ2h0KnNjKSk7CiAgICAgIGMuZ2V0Q29udGV4dCgnMmQnKS5kcmF3SW1hZ2UoaW0sMCwwLGMud2lkdGgsYy5oZWlnaHQpOwogICAgICByZXMoYy50b0RhdGFVUkwoJ2ltYWdlL2pwZWcnLDAuOSkpOwogICAgfTsKICAgIGltLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVzKGRhdGFVcmwpOyB9OwogICAgaW0uc3JjPWRhdGFVcmw7CiAgfSk7Cn0KZnVuY3Rpb24gYXJjaGl2b0FEYXRvcyhmaWxlKXsKICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzLHJlail7CiAgICB2YXIgZnI9bmV3IEZpbGVSZWFkZXIoKTsKICAgIGZyLm9ubG9hZD1mdW5jdGlvbigpeyByZXMoU3RyaW5nKGZyLnJlc3VsdCkpOyB9OwogICAgZnIub25lcnJvcj1mdW5jdGlvbigpeyByZWoobmV3IEVycm9yKCdubyBwdWRlIGxlZXIgZWwgYXJjaGl2bycpKTsgfTsKICAgIGZyLnJlYWRBc0RhdGFVUkwoZmlsZSk7CiAgfSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IE9DUiBjb24gY2FjaGUgKyBtZWpvcmEgZGUgaW1hZ2VuID09PT09PT09PT09PT09PT09ICovCnZhciBjYWNoZU9jcj17fSwgcHJvbWVzYVdvcmtlcj1udWxsOwpmdW5jdGlvbiBhYnJpcldvcmtlck9jcigpewogIGlmKHByb21lc2FXb3JrZXIpeyByZXR1cm4gcHJvbWVzYVdvcmtlcjsgfQogIHRyeXsKICAgIGlmKHR5cGVvZiBUZXNzZXJhY3QhPT0ndW5kZWZpbmVkJyAmJiBUZXNzZXJhY3QuY3JlYXRlV29ya2VyKXsKICAgICAgcHJvbWVzYVdvcmtlcj1UZXNzZXJhY3QuY3JlYXRlV29ya2VyKCdzcGErZW5nJywxLHtsb2dnZXI6ZnVuY3Rpb24oKXt9fSkudGhlbihmdW5jdGlvbih3KXsgcmV0dXJuIHc7IH0pLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiBudWxsOyB9KTsKICAgICAgcmV0dXJuIHByb21lc2FXb3JrZXI7CiAgICB9CiAgfWNhdGNoKGUpe30KICBwcm9tZXNhV29ya2VyPVByb21pc2UucmVzb2x2ZShudWxsKTsKICByZXR1cm4gcHJvbWVzYVdvcmtlcjsKfQpmdW5jdGlvbiBtZWpvcmFySW1hZ2VuKGRhdGFVcmwpewogIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpewogICAgdmFyIGltPW5ldyBJbWFnZSgpOwogICAgaW0ub25sb2FkPWZ1bmN0aW9uKCl7CiAgICAgIHRyeXsKICAgICAgICB2YXIgYW5jaG89aW0ud2lkdGgsIGFsdG89aW0uaGVpZ2h0OwogICAgICAgIHZhciBlc2MxPU1hdGgubWluKDMsIE1hdGgubWF4KDEsIDE0MDAvTWF0aC5tYXgoMSxNYXRoLm1pbihhbmNobyxhbHRvKSkpKTsKICAgICAgICB2YXIgZXNjMj1NYXRoLm1pbigxLCAyNjAwL01hdGgubWF4KDEsTWF0aC5tYXgoYW5jaG8sYWx0bykpKTsKICAgICAgICB2YXIgc2M9TWF0aC5taW4oZXNjMSxlc2MyKTsKICAgICAgICBpZighKHNjPjApKXsgc2M9MTsgfQogICAgICAgIHZhciBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOwogICAgICAgIGMud2lkdGg9TWF0aC5tYXgoMSxNYXRoLnJvdW5kKGFuY2hvKnNjKSk7CiAgICAgICAgYy5oZWlnaHQ9TWF0aC5tYXgoMSxNYXRoLnJvdW5kKGFsdG8qc2MpKTsKICAgICAgICB2YXIgZz1jLmdldENvbnRleHQoJzJkJyk7CiAgICAgICAgaWYoIWcpeyByZXMobnVsbCk7IHJldHVybjsgfQogICAgICAgIGcuaW1hZ2VTbW9vdGhpbmdFbmFibGVkPXRydWU7CiAgICAgICAgdHJ5eyBnLmltYWdlU21vb3RoaW5nUXVhbGl0eT0naGlnaCc7IH1jYXRjaChlMil7fQogICAgICAgIGcuZHJhd0ltYWdlKGltLDAsMCxjLndpZHRoLGMuaGVpZ2h0KTsKICAgICAgICB2YXIgaWRkPWcuZ2V0SW1hZ2VEYXRhKDAsMCxjLndpZHRoLGMuaGVpZ2h0KSwgcD1pZGQuZGF0YSwgbj1wLmxlbmd0aC80OwogICAgICAgIHZhciBoaXN0PW5ldyBJbnQzMkFycmF5KDI1NiksIGksIGssIHN1bT0wOwogICAgICAgIGZvcihpPTA7aTxuO2krKyl7IHZhciByPXBbaSo0XSwgZ2c9cFtpKjQrMV0sIGI9cFtpKjQrMl07IHZhciBsPShyKjMrZ2cqNCtiKT4+MzsgcFtpKjRdPWw7IHBbaSo0KzFdPWw7IHBbaSo0KzJdPWw7IGhpc3RbbF0rKzsgc3VtKz1sOyB9CiAgICAgICAgdmFyIG1lZGlhPXN1bS9NYXRoLm1heCgxLG4pOwogICAgICAgIHZhciBnYW49MTsKICAgICAgICBpZihtZWRpYTw4MCl7IGdhbj0wLjU4OyB9CiAgICAgICAgZWxzZSBpZihtZWRpYTwxMDUpeyBnYW49MC43MjsgfQogICAgICAgIGVsc2UgaWYobWVkaWE+MTg1KXsgZ2FuPTEuMjU7IH0KICAgICAgICB2YXIgYWNjPTAsIGxvPTAsIGhpPTI1NTsKICAgICAgICBmb3Ioaz0wO2s8MjU2O2srKyl7IGFjYys9aGlzdFtrXTsgaWYoYWNjPj1uKjAuMDIpeyBsbz1rOyBicmVhazsgfSB9CiAgICAgICAgYWNjPTA7CiAgICAgICAgZm9yKGs9MjU1O2s+PTA7ay0tKXsgYWNjKz1oaXN0W2tdOyBpZihhY2M+PW4qMC4wMil7IGhpPWs7IGJyZWFrOyB9IH0KICAgICAgICB2YXIgZXNjPShoaT5sbyk/MjU1LyhoaS1sbyk6MTsKICAgICAgICBmb3IoaT0wO2k8bjtpKyspeyB2YXIgdj0ocFtpKjRdLWxvKSplc2M7IHY9djwwPzA6KHY+MjU1PzI1NTp2KTsgdj0yNTUqTWF0aC5wb3codi8yNTUsZ2FuKTsgcFtpKjRdPXY7IHBbaSo0KzFdPXY7IHBbaSo0KzJdPXY7IH0KICAgICAgICB2YXIgdG1wPW5ldyBVaW50OEFycmF5KG4pOwogICAgICAgIGZvcihpPTA7aTxuO2krKyl7IHRtcFtpXT1wW2kqNF07IH0KICAgICAgICB2YXIgYW5jaG8yPWMud2lkdGg7CiAgICAgICAgZm9yKHZhciB5PTE7eTxjLmhlaWdodC0xO3krKyl7CiAgICAgICAgICBmb3IodmFyIHg9MTt4PGFuY2hvMi0xO3grKyl7CiAgICAgICAgICAgIHZhciBxPXkqYW5jaG8yK3g7CiAgICAgICAgICAgIHZhciBibD0odG1wW3FdK3RtcFtxLTFdK3RtcFtxKzFdK3RtcFtxLWFuY2hvMl0rdG1wW3ErYW5jaG8yXSkqMC4yOwogICAgICAgICAgICB2YXIgdjI9dG1wW3FdKzAuNCoodG1wW3FdLWJsKTsKICAgICAgICAgICAgdjI9djI8MD8wOih2Mj4yNTU/MjU1OnYyKTsKICAgICAgICAgICAgdmFyIHczPXEqNDsgcFt3M109djI7IHBbdzMrMV09djI7IHBbdzMrMl09djI7CiAgICAgICAgICB9CiAgICAgICAgfQogICAgICAgIGcucHV0SW1hZ2VEYXRhKGlkZCwwLDApOwogICAgICAgIHJlcyhjKTsKICAgICAgfWNhdGNoKGUpeyByZXMobnVsbCk7IH0KICAgIH07CiAgICBpbS5vbmVycm9yPWZ1bmN0aW9uKCl7IHJlcyhudWxsKTsgfTsKICAgIGltLnNyYz1kYXRhVXJsOwogIH0pOwp9CmZ1bmN0aW9uIHJlY29ydGVTdXBlcmlvcihjdil7CiAgdHJ5ewogICAgdmFyIHc9Y3Yud2lkdGgsIGg9TWF0aC5yb3VuZChjdi5oZWlnaHQqMC42Mik7CiAgICBpZih3PDQwfHxoPDQwKXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOwogICAgYy53aWR0aD13OyBjLmhlaWdodD1oOwogICAgYy5nZXRDb250ZXh0KCcyZCcpLmRyYXdJbWFnZShjdiwwLDAsdyxoLDAsMCx3LGgpOwogICAgcmV0dXJuIGM7CiAgfWNhdGNoKGUpeyByZXR1cm4gbnVsbDsgfQp9CmZ1bmN0aW9uIHJlY29ub2NlckNvbihpbWcsIHBzbSl7CiAgcmV0dXJuIGFicmlyV29ya2VyT2NyKCkudGhlbihmdW5jdGlvbih3KXsKICAgIGZ1bmN0aW9uIGNvblRlc3MoKXsKICAgICAgcmV0dXJuIFRlc3NlcmFjdC5yZWNvZ25pemUoaW1nLCdzcGErZW5nJyx7bG9nZ2VyOmZ1bmN0aW9uKCl7fX0pLnRoZW4oZnVuY3Rpb24ocil7IHJldHVybiAociYmci5kYXRhJiZyLmRhdGEudGV4dCk/ci5kYXRhLnRleHQ6Jyc7IH0pLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiAnJzsgfSk7CiAgICB9CiAgICBpZighKHcmJncucmVjb2duaXplKSl7IHJldHVybiBjb25UZXNzKCk7IH0KICAgIHZhciBwcmU9KHcuc2V0UGFyYW1ldGVycyYmcHNtKT93LnNldFBhcmFtZXRlcnMoe3Rlc3NlZGl0X3BhZ2VzZWdfbW9kZTpTdHJpbmcocHNtKX0pOlByb21pc2UucmVzb2x2ZSgpOwogICAgcmV0dXJuIHByZS50aGVuKGZ1bmN0aW9uKCl7IHJldHVybiB3LnJlY29nbml6ZShpbWcpOyB9KS50aGVuKGZ1bmN0aW9uKHIpewogICAgICBpZih3LnNldFBhcmFtZXRlcnMpeyB0cnl7IHcuc2V0UGFyYW1ldGVycyh7dGVzc2VkaXRfcGFnZXNlZ19tb2RlOiczJ30pLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH1jYXRjaChlMil7fSB9CiAgICAgIHJldHVybiAociYmci5kYXRhJiZyLmRhdGEudGV4dCk/ci5kYXRhLnRleHQ6Jyc7CiAgICB9KS5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gY29uVGVzcygpOyB9KTsKICB9KS5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gJyc7IH0pOwp9CmZ1bmN0aW9uIG9jck11bHRpKGRhdGFVcmwsIGVzQnVlbm8pewogIGlmKHR5cGVvZiBUZXNzZXJhY3Q9PT0ndW5kZWZpbmVkJyB8fCAhVGVzc2VyYWN0LnJlY29nbml6ZSl7CiAgICByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKFtdKTsKICB9CiAgcmV0dXJuIG1lam9yYXJJbWFnZW4oZGF0YVVybCkudGhlbihmdW5jdGlvbihjdil7CiAgICB2YXIgdmFycz1bXTsKICAgIGlmKGN2KXsKICAgICAgdmFycy5wdXNoKHtpbWc6Y3YsIHBzbTonMyd9KTsKICAgICAgdmFyIHJjPXJlY29ydGVTdXBlcmlvcihjdik7CiAgICAgIGlmKHJjKXsgdmFycy5wdXNoKHtpbWc6cmMsIHBzbTonNid9KTsgfQogICAgICAvKiBoZXJlZGFkbyB2MTQ6IHBhc2UgZGlzcGVyc28gKFBTTSAxMSkgcGFyYSBsb3MgY2FtcG9zIHN1ZWx0b3MgZGVsCiAgICAgICAgIGRvY3VtZW50byAoTk9NQlJFUyAvIEFQRUxMSURPUyB2YW4gZW4gbGluZWFzIHNlcGFyYWRhcyB5IGVsIHBhc2UKICAgICAgICAgbm9ybWFsIGEgdmVjZXMgbG9zIHNhbHRhKS4gZXNCdWVubyBjb3J0YSBhcGVuYXMgYWNpZXJ0YS4gKi8KICAgICAgdmFycy5wdXNoKHtpbWc6Y3YsIHBzbTonMTEnfSk7CiAgICB9CiAgICB2YXJzLnB1c2goe2ltZzpkYXRhVXJsLCBwc206JzMnfSk7CiAgICB2YXIgaT0wLCB0ZXh0b3M9W107CiAgICBmdW5jdGlvbiBwYXNvKCl7CiAgICAgIGlmKGk+PXZhcnMubGVuZ3RoKXsgcmV0dXJuIFByb21pc2UucmVzb2x2ZSh0ZXh0b3MpOyB9CiAgICAgIHZhciByPXZhcnNbaSsrXTsKICAgICAgcmV0dXJuIHJlY29ub2NlckNvbihyLmltZywgci5wc20pLnRoZW4oZnVuY3Rpb24odCl7CiAgICAgICAgaWYodCl7IHRleHRvcy5wdXNoKHQpOyB9CiAgICAgICAgaWYodCYmZXNCdWVubyYmZXNCdWVubyh0KSl7IHJldHVybiB0ZXh0b3M7IH0KICAgICAgICByZXR1cm4gcGFzbygpOwogICAgICB9KS5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gcGFzbygpOyB9KTsKICAgIH0KICAgIHJldHVybiBwYXNvKCk7CiAgfSk7Cn0KZnVuY3Rpb24gZWxlZ2lyVGV4dG8odGV4dG9zLCBlc2NyaXRvKXsKICB2YXIgbWVqb3I9JycsIG1qPS0xLCBpOwogIGZvcihpPTA7aTx0ZXh0b3MubGVuZ3RoO2krKyl7CiAgICB2YXIgdD10ZXh0b3NbaV18fCcnLCBwPTA7CiAgICBpZihlc2NyaXRvKXsKICAgICAgdmFyIG5jPW5vbWJyZUNvaW5jaWRlKGVzY3JpdG8sdCxmYWxzZSk7CiAgICAgIHA9KG5jLm9rPzEwMDA6MCkrKG5jLnB1bnR8fDApKjEwMDsKICAgIH0KICAgIHArPU1hdGgubWluKDUwLCh0LnJlcGxhY2UoL1teQS1aMC05XS9naSwnJykubGVuZ3RoKS8zMCk7CiAgICBpZihwPm1qKXsgbWo9cDsgbWVqb3I9dDsgfQogIH0KICByZXR1cm4gbWVqb3I7Cn0KZnVuY3Rpb24gaGFjZXJPY3IoZGF0YVVybCl7CiAgaWYoY2FjaGVPY3JbZGF0YVVybF0peyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKGNhY2hlT2NyW2RhdGFVcmxdKTsgfQogIGlmKHR5cGVvZiBUZXNzZXJhY3Q9PT0ndW5kZWZpbmVkJyB8fCAhVGVzc2VyYWN0LnJlY29nbml6ZSl7CiAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QobmV3IEVycm9yKCdPQ1Igbm8gZGlzcG9uaWJsZSwgcmV2aXNhIHR1IGludGVybmV0JykpOwogIH0KICByZXR1cm4gb2NyTXVsdGkoZGF0YVVybCwgZnVuY3Rpb24odCl7IHJldHVybiAodHx8JycpLnJlcGxhY2UoL1teQS1aMC05XS9naSwnJykubGVuZ3RoPj0zNDsgfSkudGhlbihmdW5jdGlvbih0ZXh0b3MpewogICAgdmFyIHQ9ZWxlZ2lyVGV4dG8odGV4dG9zLCBudWxsKTsKICAgIGNhY2hlT2NyW2RhdGFVcmxdPXR8fCcnOwogICAgcmV0dXJuIHR8fCcnOwogIH0pOwp9CmZ1bmN0aW9uIG9jckZyZW50ZShkYXRhVXJsKXsKICBpZihjYWNoZU9jcltkYXRhVXJsXSl7IHJldHVybiBQcm9taXNlLnJlc29sdmUoY2FjaGVPY3JbZGF0YVVybF0pOyB9CiAgcmV0dXJuIG9jck11bHRpKGRhdGFVcmwsIGZ1bmN0aW9uKHQpeyByZXR1cm4gbm9tYnJlQ29pbmNpZGUoRVNULmVzY3JpdG8sIHR8fCcnLCBmYWxzZSkub2s7IH0pLnRoZW4oZnVuY3Rpb24odGV4dG9zKXsKICAgIHZhciB0PWVsZWdpclRleHRvKHRleHRvcywgRVNULmVzY3JpdG8pOwogICAgaWYodCl7IGNhY2hlT2NyW2RhdGFVcmxdPXQ7IH0KICAgIHJldHVybiB0fHwnJzsKICB9KTsKfQoKLyogPT09PT09PT09PT09PT09PT0gYmlvbWV0cmlhIGZhY2lhbCA9PT09PT09PT09PT09PT09PSAqLwp2YXIgZmFjZVA9bnVsbDsKZnVuY3Rpb24gY2FyZ2FyRmFjZUFwaSgpewogIGlmKGZhY2VQKXsgcmV0dXJuIGZhY2VQOyB9CiAgZmFjZVA9bmV3IFByb21pc2UoZnVuY3Rpb24ocmVzLHJlail7CiAgICBmdW5jdGlvbiBsaXN0bygpeyByZXR1cm4gVy5mYWNlYXBpICYmIFcuZmFjZWFwaS5uZXRzICYmIFcuZmFjZWFwaS5uZXRzLnRpbnlGYWNlRGV0ZWN0b3IgJiYgVy5mYWNlYXBpLm5ldHMuZmFjZVJlY29nbml0aW9uTmV0OyB9CiAgICBmdW5jdGlvbiBtb2RlbG9zKGJhc2UpewogICAgICByZXR1cm4gUHJvbWlzZS5hbGwoWwogICAgICAgIFcuZmFjZWFwaS5uZXRzLnRpbnlGYWNlRGV0ZWN0b3IubG9hZEZyb21VcmkoYmFzZSksCiAgICAgICAgVy5mYWNlYXBpLm5ldHMuZmFjZUxhbmRtYXJrNjhOZXQubG9hZEZyb21VcmkoYmFzZSksCiAgICAgICAgVy5mYWNlYXBpLm5ldHMuZmFjZVJlY29nbml0aW9uTmV0LmxvYWRGcm9tVXJpKGJhc2UpCiAgICAgIF0pOwogICAgfQogICAgZnVuY3Rpb24gaW5pY2lhcigpewogICAgICB2YXIgYmFzZT0naHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L2doL2p1c3RhZHVkZXdob2hhY2tzL2ZhY2UtYXBpLmpzQDAuMjIuMi93ZWlnaHRzJzsKICAgICAgbW9kZWxvcyhiYXNlKS50aGVuKGZ1bmN0aW9uKCl7IHJlcygpOyB9LCBmdW5jdGlvbigpeyBtb2RlbG9zKCdodHRwczovL2p1c3RhZHVkZXdob2hhY2tzLmdpdGh1Yi5pby9mYWNlLWFwaS5qcy9tb2RlbHMnKS50aGVuKGZ1bmN0aW9uKCl7IHJlcygpOyB9LCByZWopOyB9KTsKICAgIH0KICAgIGlmKGxpc3RvKCkpeyBpbmljaWFyKCk7IHJldHVybjsgfQogICAgdmFyIHM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnc2NyaXB0Jyk7CiAgICBzLnNyYz0naHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9mYWNlLWFwaS5qc0AwLjIyLjIvZGlzdC9mYWNlLWFwaS5taW4uanMnOwogICAgcy5vbmxvYWQ9ZnVuY3Rpb24oKXsgaWYobGlzdG8oKSl7IGluaWNpYXIoKTsgfSBlbHNlIHsgcmVqKG5ldyBFcnJvcignZmFjZWFwaSBubyBxdWVkbyBsaXN0bycpKTsgfSB9OwogICAgcy5vbmVycm9yPWZ1bmN0aW9uKCl7IHJlaihuZXcgRXJyb3IoJ25vIHNlIHB1ZG8gY2FyZ2FyIGVsIHZlcmlmaWNhZG9yIGZhY2lhbCcpKTsgfTsKICAgIGRvY3VtZW50LmhlYWQuYXBwZW5kQ2hpbGQocyk7CiAgfSk7CiAgcmV0dXJuIGZhY2VQOwp9CmZ1bmN0aW9uIGNvblRpbWVvdXQocCwgbXMpewogIHJldHVybiBQcm9taXNlLnJhY2UoW3AsIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7IHNldFRpbWVvdXQoZnVuY3Rpb24oKXsgcmVzKG51bGwpOyB9LCBtcyk7IH0pXSk7Cn0KZnVuY3Rpb24gZGV0ZWN0YXJDYXJhRW4oZGF0YVVybCwgaW50ZW50byl7CiAgcmV0dXJuIGNhcmdhckZhY2VBcGkoKS50aGVuKGZ1bmN0aW9uKCl7CiAgICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsKICAgICAgdmFyIGltPW5ldyBJbWFnZSgpOwogICAgICBpbS5vbmxvYWQ9ZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICB2YXIgdGFtPShpbnRlbnRvPT09Mik/NTEyOjMyMDsKICAgICAgICAgIHZhciBvcHQ9bmV3IFcuZmFjZWFwaS5UaW55RmFjZURldGVjdG9yT3B0aW9ucyh7aW5wdXRTaXplOnRhbSwgc2NvcmVUaHJlc2hvbGQ6KGludGVudG89PT0yKT8wLjM6MC40fSk7CiAgICAgICAgICBXLmZhY2VhcGkuZGV0ZWN0U2luZ2xlRmFjZShpbSxvcHQpLndpdGhGYWNlTGFuZG1hcmtzKCkud2l0aEZhY2VEZXNjcmlwdG9yKCkudGhlbihmdW5jdGlvbihyKXsKICAgICAgICAgICAgaWYociYmci5kZXRlY3Rpb24peyByZXMocik7IHJldHVybjsgfQogICAgICAgICAgICBpZihpbnRlbnRvPT09Mil7IHJlcyhudWxsKTsgcmV0dXJuOyB9CiAgICAgICAgICAgIHJlcyhkZXRlY3RhckNhcmFFbihkYXRhVXJsLChpbnRlbnRvPT09MSk/MjoxKSk7CiAgICAgICAgICB9KS5jYXRjaChmdW5jdGlvbigpewogICAgICAgICAgICBpZihpbnRlbnRvPT09Mil7IHJlcyhudWxsKTsgcmV0dXJuOyB9CiAgICAgICAgICAgIHJlcyhkZXRlY3RhckNhcmFFbihkYXRhVXJsLChpbnRlbnRvPT09MSk/MjoxKSk7CiAgICAgICAgICB9KTsKICAgICAgICB9Y2F0Y2goZSl7IHJlcyhudWxsKTsgfQogICAgICB9OwogICAgICBpbS5vbmVycm9yPWZ1bmN0aW9uKCl7IHJlcyhudWxsKTsgfTsKICAgICAgaW0uc3JjPWRhdGFVcmw7CiAgICB9KTsKICB9KS5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gbnVsbDsgfSk7Cn0KZnVuY3Rpb24gcmVjb3J0ZUNhcmEoZGF0YVVybCl7CiAgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7CiAgICB2YXIgaW09bmV3IEltYWdlKCk7CiAgICBpbS5vbmxvYWQ9ZnVuY3Rpb24oKXsKICAgICAgdHJ5ewogICAgICAgIHZhciBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOwogICAgICAgIGMud2lkdGg9TWF0aC5tYXgoNDAsTWF0aC5yb3VuZChpbS53aWR0aCowLjYyKSk7CiAgICAgICAgYy5oZWlnaHQ9TWF0aC5tYXgoNDAsTWF0aC5yb3VuZChpbS5oZWlnaHQqMC42NikpOwogICAgICAgIGMuZ2V0Q29udGV4dCgnMmQnKS5kcmF3SW1hZ2UoaW0sMCwwLGltLndpZHRoLE1hdGgucm91bmQoaW0uaGVpZ2h0KjAuOSksMCwwLGMud2lkdGgsYy5oZWlnaHQpOwogICAgICAgIHJlcyhjLnRvRGF0YVVSTCgnaW1hZ2UvanBlZycsMC45KSk7CiAgICAgIH1jYXRjaChlKXsgcmVzKG51bGwpOyB9CiAgICB9OwogICAgaW0ub25lcnJvcj1mdW5jdGlvbigpeyByZXMobnVsbCk7IH07CiAgICBpbS5zcmM9ZGF0YVVybDsKICB9KTsKfQpmdW5jdGlvbiBkZXRlY3RhckNhcmFEb2MoZGF0YVVybCl7CiAgaWYoIWRhdGFVcmwpeyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKG51bGwpOyB9CiAgcmV0dXJuIGRldGVjdGFyQ2FyYUVuKGRhdGFVcmwpLnRoZW4oZnVuY3Rpb24ocil7CiAgICBpZihyJiZyLmRldGVjdGlvbil7IHJldHVybiByOyB9CiAgICByZXR1cm4gcmVjb3J0ZUNhcmEoZGF0YVVybCkudGhlbihmdW5jdGlvbihyZWMpewogICAgICBpZighcmVjKXsgcmV0dXJuIG51bGw7IH0KICAgICAgcmV0dXJuIGRldGVjdGFyQ2FyYUVuKHJlYywxKTsKICAgIH0pOwogIH0pOwp9CmZ1bmN0aW9uIGRpc3RGKGEsYil7CiAgdmFyIHM9MCxpOwogIGZvcihpPTA7aTxhLmxlbmd0aDtpKyspeyB2YXIgZD1hW2ldLWJbaV07IHMrPWQqZDsgfQogIHJldHVybiBNYXRoLnNxcnQocyk7Cn0KCi8qID09PT09PT09PT09PT09PT09IGd1YXJkaWFuIGRlIG9yZGVuIDEtMi0zLTQtNSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBwZXJtaXRpZG9IYXN0YSgpewogIHZhciBwPTE7CiAgaWYoRVNULm5vbWJyZU9rKXsgcD0yOyB9CiAgaWYoRVNULm5vbWJyZU9rICYmIEVTVC5mcmVudGVPayl7IHA9MzsgfQogIGlmKEVTVC5ub21icmVPayAmJiBFU1QuZnJlbnRlT2sgJiYgKEVTVC5yZXZlcnNvT2sgfHwgIUVTVC5uZWNlc2l0YVJldmVyc28pKXsgcD00OyB9CiAgaWYoRVNULnNlbGZpZU9rICYmIHA+PTQpeyBwPTU7IH0KICByZXR1cm4gcDsKfQp2YXIgTU9WTElCUkU9ZmFsc2U7CmZ1bmN0aW9uIHZvbHZlclRvY2FkbygpeyB0cnl7IHJldHVybiAhIShXLl9fenlWb2x2ZXJUb2NhZG8mJigoRGF0ZS5ub3coKS1XLl9fenlWb2x2ZXJUb2NhZG8pPDMwMDApKTsgfWNhdGNoKGUpeyByZXR1cm4gZmFsc2U7IH0gfQpmdW5jdGlvbiBtb3N0cmFyUGFzbyhuKXsKICAvKiB2MTY6IGd1YXJkaWEgYW50aS1wYXRhZGEuIFNpIGNvZGlnbyB2aWVqbyAodmFsaWRhY2lvbmVzIGxlZ2FkYXMgbwogICAgIHVuIHJlLXJlbmRlciBkZWwgc2Vydmlkb3IpIHRlIHRpcmEgaGFjaWEgYXRyYXMgZGVzZGUgZWwgcGFzbyA0LTUKICAgICBzaW4gcXVlIGhheWFzIHRvY2FkbyBWb2x2ZXIsIGVsIHNhbHRvIHNlIENBTkNFTEE6IHNpZ3VlcyBlbiB0dQogICAgIHBhc28gY29uIHRvZG8gaW50YWN0by4gTG9zIHJlZ3Jlc29zIHF1ZSBUVSBwaWRlcyAoYm90b24gUmVwZXRpcgogICAgIGZvdG8sIGJvdG9uIElyIGFsIHBhc28gMSwgVm9sdmVyKSBtYXJjYW4gTU9WTElCUkUgbyBlbCB0b3F1ZSB5CiAgICAgcGFzYW4gc2luIHByb2JsZW1hLiAqLwogIHRyeXsKICAgIHZhciBwbT1FU1QucGFzb01heHx8MTsKICAgIGlmKHBtPj00ICYmIG4+PTEgJiYgbjxwbSAmJiAhTU9WTElCUkUgJiYgIXZvbHZlclRvY2FkbygpICYmIHBlcm1pdGlkb0hhc3RhKCk+PXBtKXsKICAgICAgbXNnKCd6eUd1YXJkaWEnLCdObyB0ZSByZWdyZXNhbW9zOiB0dSByZWdpc3RybyBzaWd1ZSBjb21wbGV0byBlbiBlbCBwYXNvICcrcG0rJy4gUGFyYSBjb3JyZWdpciBhbGdvIHVzYSBWb2x2ZXIuJywnI2E2MCcpOwogICAgICBuPXBtOwogICAgfQogIH1jYXRjaChlKXt9CiAgaWYobj4oRVNULnBhc29NYXh8fDEpKXsgRVNULnBhc29NYXg9bjsgfQogIHZhciBpLGVsLCByYj0kKCd6eUJ0blJlcEZvdG8nKTsKICBpZihyYil7IHJiLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgZm9yKGk9MTtpPD01O2krKyl7CiAgICBlbD0kKCdwcycraSk7CiAgICBpZihlbCl7CiAgICAgIGVsLmNsYXNzTmFtZT0ncGFzbycrKGk9PT1uPycgYWN0JzonJyk7CiAgICAgIGVsLnN0eWxlLmRpc3BsYXk9Jyc7CiAgICB9CiAgfQogIHZhciBwcj0kKCdwcm9nJyk7CiAgaWYocHIpeyBwci50ZXh0Q29udGVudD0nUEFTTyAnK24rJyBERSA1JzsgfQogIGlmKEVTVC5wYXNvPj0yICYmIEVTVC5wYXNvPD00ICYmIEVTVC5wYXNvIT09bil7IHRyeXsgcGFyYXJDYW0oRVNULnBhc28pOyB9Y2F0Y2goZSl7fSB9CiAgRVNULnBhc289bjsKICB0cnl7IHJlc3BhbGRhKCk7IH1jYXRjaChlKXt9CiAgaWYobj09PTUpewogICAgZGVzY3VicmVDbGF2ZXModHJ1ZSk7CiAgICB2YXIgYT1DTFYuYSwgYj1DTFYuYjsKICAgIGlmKGEpeyBhLmRpc2FibGVkPWZhbHNlOyB9CiAgICBpZihiKXsgYi5kaXNhYmxlZD1mYWxzZTsgfQogICAgdHJ5eyBpZihyZXN0YXVyYXJDbGF2ZVNlc2lvbigpKXsgbG9nKCd2MTc6IGNsYXZlIHJlcHVlc3RhIGRlc2RlIGxhIHNlc2lvbicpOyB9IH1jYXRjaChlUmMpe30KICAgIHRyeXsgdmFsaWRhckNsYXZlcygpOyB9Y2F0Y2goZVZjKXt9CiAgICB0cnl7IGJhcnJlTWVuc2FqZXMoKTsgfWNhdGNoKGUpe30KICAgIHRyeXsgbGltcGlhTGVnYWRvKCk7IH1jYXRjaChlKXt9CiAgICB0cnl7IHBpbnRhRGlhZygpOyB9Y2F0Y2goZSl7fQogICAgdmFyIHJmPUVTVC5mcmVudGVPaz8nRnJlbnRlIE9LJzonRkFMVEEgRlJFTlRFJzsKICAgIHZhciBycj0oIUVTVC5uZWNlc2l0YVJldmVyc298fEVTVC5yZXZlcnNvT2spPydSZXZlcnNvIE9LJzonRkFMVEEgUkVWRVJTTyc7CiAgICB2YXIgcnM9RVNULnNlbGZpZU9rPydTZWxmaWUgdmVyaWZpY2FkYSc6J1NFTEZJRSBTSU4gVkVSSUZJQ0FSJzsKICAgIHZhciB0b2RvPShFU1QuZnJlbnRlT2smJkVTVC5zZWxmaWVPayYmKCFFU1QubmVjZXNpdGFSZXZlcnNvfHxFU1QucmV2ZXJzb09rKSk7CiAgICBtc2coJ3p5UmVzdW1lbjUnLCdWZXJpZmljYWNpb24gZmluYWw6ICcrcmYrJyB8ICcrcnIrJyB8ICcrcnMrJy4gRXNjcmliZSB0dSBjbGF2ZSAyIHZlY2VzIHkgY3JlYSB0dSBaSUQuJyx0b2RvPycjMDgwJzonI2MwMCcpOwogIH0KICB0cnl7IHZhciBhY3Q9JCgncHMnK24pOyBpZihhY3QmJmFjdC5zY3JvbGxJbnRvVmlldyl7IGFjdC5zY3JvbGxJbnRvVmlldyh7YmVoYXZpb3I6J3Ntb290aCcsYmxvY2s6J3N0YXJ0J30pOyB9IH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gYXZhbnphcihuKXsgbW9zdHJhclBhc28obik7IH0KZnVuY3Rpb24gdmVyaWZpY2FyKCl7CiAgdHJ5ewogICAgdmFyIGFjdD1kb2N1bWVudC5xdWVyeVNlbGVjdG9yKCcucGFzby5hY3QnKTsKICAgIHZhciBybj1hY3QmJmFjdC5pZD9wYXJzZUludChTdHJpbmcoYWN0LmlkKS5yZXBsYWNlKCdwcycsJycpLDEwKTowOwogICAgaWYocm4+PTEmJnJuPD01JiZybiE9PUVTVC5wYXNvKXsKICAgICAgRVNULnBhc289cm47CiAgICAgIHZhciBwbXY9RVNULnBhc29NYXh8fDE7CiAgICAgIGlmKHBtdj49NCAmJiBybjxwbXYgJiYgIU1PVkxJQlJFICYmICF2b2x2ZXJUb2NhZG8oKSAmJiBwZXJtaXRpZG9IYXN0YSgpPj1wbXYpewogICAgICAgIG1zZygnenlHdWFyZGlhJywnTm8gdGUgcmVncmVzYW1vczogdHUgcmVnaXN0cm8gc2lndWUgY29tcGxldG8gZW4gZWwgcGFzbyAnK3BtdisnLicsJyNhNjAnKTsKICAgICAgICBtb3N0cmFyUGFzbyhwbXYpOwogICAgICAgIHJldHVybjsKICAgICAgfQogICAgfQogIH1jYXRjaChlKXt9CiAgdHJ5eyB2YWxpZGFyUGFzbzEodHJ1ZSk7IH1jYXRjaChlKXt9CiAgdmFyIHBlcj1wZXJtaXRpZG9IYXN0YSgpOwogIGlmKEVTVC5wYXNvPnBlcil7CiAgICBpZihwZXI9PT0xKXsgbXNnKCd6eUd1YXJkaWEnLCdQYXJhIHNlZ3VpciwgZXNjcmliZSB0dSBub21icmUgeSBlbGlnZSBlbCB0aXBvIGRlIGRvY3VtZW50byBlbiBlbCBwYXNvIDEuJywnI2E2MCcpOyB9CiAgICBlbHNleyBtc2coJ3p5R3VhcmRpYScsJ1RlIHJlZ3Jlc28gYWwgcGFzbyAnK3BlcisnIHBhcmEgc2VndWlyIGVuIG9yZGVuLicsJyNhNjAnKTsgfQogICAgbW9zdHJhclBhc28ocGVyKTsKICB9CiAgdmFyIHNlbD0kKCd0aXBvRG9jJyk7CiAgaWYoc2VsICYmIHNlbC52YWx1ZSAmJiAvcGFzYXBvcnRlfHBhc3Nwb3J0L2kudGVzdCgoc2VsLm9wdGlvbnMmJnNlbC5vcHRpb25zW3NlbC5zZWxlY3RlZEluZGV4XSYmc2VsLm9wdGlvbnNbc2VsLnNlbGVjdGVkSW5kZXhdLnRleHQpfHwnJykpewogICAgdmFyIHBzMz0kKCdwczMnKSwgbnI9JCgnbm90YVJldicpOwogICAgaWYocHMzKXsgcHMzLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgICBpZihucil7IG5yLnN0eWxlLmRpc3BsYXk9J25vbmUnOyB9CiAgfQp9CnZhciB2dGltZXI9bnVsbDsKZnVuY3Rpb24gcHJvZ3JhbWFyVmVyaWZpY2FyKCl7CiAgaWYodnRpbWVyKXsgcmV0dXJuOyB9CiAgdnRpbWVyPXNldFRpbWVvdXQoZnVuY3Rpb24oKXsgdnRpbWVyPW51bGw7IHRyeXsgdmVyaWZpY2FyKCk7IH1jYXRjaChlKXt9IH0sMTIwKTsKfQp0cnl7CiAgbmV3IE11dGF0aW9uT2JzZXJ2ZXIocHJvZ3JhbWFyVmVyaWZpY2FyKS5vYnNlcnZlKGRvY3VtZW50LmJvZHkse2NoaWxkTGlzdDp0cnVlLHN1YnRyZWU6dHJ1ZSxhdHRyaWJ1dGVzOnRydWUsYXR0cmlidXRlRmlsdGVyOlsnc3R5bGUnLCdjbGFzcycsJ2hpZGRlbicsJ2Rpc2FibGVkJ119KTsKfWNhdGNoKGUpe30KCi8qID09PT09PT09PT09PT09PT09IHBhc28gMTogc29sbyBmb3JtYXRvIGRlbCBub21icmUgKHZhbGlkYSBTT0xPIGFsIGNvbnRpbnVhciwgbnVuY2EgbWllbnRyYXMgZXNjcmliZXMpID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHZhbGlkYXJQYXNvMShzaWxlbmNpb3NvKXsKICB2YXIgaW5wPSQoJ25vbWJyZScpLCBzZWw9JCgndGlwb0RvYycpOwogIHZhciB2PWlucD8oaW5wLnZhbHVlfHwnJykudHJpbSgpOicnOwogIHZhciBsZXRyYXM9L15bQS1aYS16XHUwMEMxXHUwMEM5XHUwMENEXHUwMEQzXHUwMERBXHUwMERDXHUwMEQxXHUwMEUxXHUwMEU5XHUwMEVEXHUwMEYzXHUwMEZBXHUwMEZDXHUwMEYxXSsoIFtBLVphLXpcdTAwQzFcdTAwQzlcdTAwQ0RcdTAwRDNcdTAwREFcdTAwRENcdTAwRDFcdTAwRTFcdTAwRTlcdTAwRURcdTAwRjNcdTAwRkFcdTAwRkNcdTAwRjFdKykqJC8udGVzdCh2KTsKICB2YXIgbnA9dj92LnNwbGl0KC9ccysvKS5sZW5ndGg6MDsKICB2YXIgb2s9KHYubGVuZ3RoPj01ICYmIGxldHJhcyAmJiBucD49Mik7CiAgdmFyIHQ9Y2xhc2lmaWNhclRpcG8oKTsKICBFU1QudGlwbz10Lms7CiAgRVNULm5lY2VzaXRhUmV2ZXJzbz10LnJldmVyc287CiAgdmFyIHRpcG9Paz0hIShzZWwgJiYgU3RyaW5nKHNlbC52YWx1ZXx8JycpLmxlbmd0aD4wKTsKICBFU1Qubm9tYnJlT2s9b2s7CiAgRVNULmVzY3JpdG89bm9ybSh2KTsKICBpZihzaWxlbmNpb3NvKXsgcmV0dXJuIG9rJiZ0aXBvT2s7IH0KICBpZihpbnApeyBpbnAuc3R5bGUuYm9yZGVyQ29sb3I9b2s/Jyc6JyNjMDAnOyB9CiAgdmFyIG1ubz0nJzsKICBpZighb2speyBtbm89dj8nRXNjcmliZSB0dSBub21icmUgeSB0dSBhcGVsbGlkbyAoc29sbyBsZXRyYXMgeSBlc3BhY2lvczsgc2lydmUgY29uIDEgbyAyIG5vbWJyZXMgeSAxIG8gMiBhcGVsbGlkb3MpLic6J0VzY3JpYmUgdHUgbm9tYnJlIHkgdHUgYXBlbGxpZG8gcGFyYSBjb250aW51YXIuJzsgfQogIG1zZygnenlFcnJOb21icmUnLG1ubyxtbm8/JyNjMDAnOicnKTsKICB2YXIgbXRpPXRpcG9Paz8nJzonRWxpZ2UgdHUgdGlwbyBkZSBkb2N1bWVudG8gZW4gbGEgbGlzdGEuJzsKICBtc2coJ3p5RXJyVGlwbycsbXRpLG10aT8nI2MwMCc6JycpOwogIHJldHVybiBvayYmdGlwb09rOwp9CmZ1bmN0aW9uIGxpbXBpYXJFcnJvcmVzUGFzbzEoKXsKICB2YXIgZTE9JCgnenlFcnJOb21icmUnKTsgaWYoZTEgJiYgZTEudGV4dENvbnRlbnQpeyBlMS50ZXh0Q29udGVudD0nJzsgZTEuc3R5bGUuY29sb3I9Jyc7IH0KICB2YXIgZTI9JCgnenlFcnJUaXBvJyk7IGlmKGUyICYmIGUyLnRleHRDb250ZW50KXsgZTIudGV4dENvbnRlbnQ9Jyc7IGUyLnN0eWxlLmNvbG9yPScnOyB9CiAgdmFyIGlucD0kKCdub21icmUnKTsgaWYoaW5wICYmIGlucC5zdHlsZS5ib3JkZXJDb2xvcil7IGlucC5zdHlsZS5ib3JkZXJDb2xvcj0nJzsgfQp9CmZ1bmN0aW9uIHJlc2V0ZWFyRG9jdW1lbnRvKCl7CiAgRVNULmZyZW50ZU9rPWZhbHNlOyBFU1QucmV2ZXJzb09rPWZhbHNlOyBFU1Quc2VsZmllT2s9ZmFsc2U7IEVTVC5pbnRlbnRvcz01OyBFU1QuY2FyYURvYz1udWxsOwp9CgovKiA9PT09PT09PT09PT09PT09PSBwYXNvIDI6IGZyZW50ZSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBmYWxsb0xlY3R1cmFGcmVudGUobSl7CiAgYnVzeShmYWxzZSk7CiAgbXNnKCdzdEYnLG0rJyBUb2NhIENBUFRVUkFSIGRlIG51ZXZvLCBjb24gYnVlbmEgbHV6IHkgc2luIGJyaWxsby4nLCcjYzAwJyk7Cn0KZnVuY3Rpb24gYXZhbnphclRyYXNGcmVudGUoKXsKICBhdmFuemFyKEVTVC5uZWNlc2l0YVJldmVyc28/Mzo0KTsKICBpZihFU1QubmVjZXNpdGFSZXZlcnNvKXsKICAgIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsgdHJ5eyBhYnJpckNhbSgnMycsJ2Vudmlyb25tZW50Jywnc3RBJywnYkNhcEEnKS5jYXRjaChmdW5jdGlvbigpe30pOyB9Y2F0Y2goZSl7fSB9LDUwMCk7CiAgfQp9CmZ1bmN0aW9uIGFjZXB0YXJGcmVudGVDb25maXJtYWRvKHRleHRvT0NSLCBsZWN0dXJhKXsKICBFU1QuZnJlbnRlT2s9dHJ1ZTsKICBFU1QuZnJlbnRlVGV4dG89KHRleHRvT0NSfHwnJykrJ1xuTEVDVFVSQSBDT05GSVJNQURBOiAnK2xlY3R1cmE7CiAgdHJ5eyByZXNwYWxkYSgpOyB9Y2F0Y2goZSl7fQogIG9jdWx0YXJDb25maXJtYWNpb25MZWN0dXJhKCk7CiAgbXNnKCdzdEYnLCdcdTI3MTMgRnJlbnRlIGNvbmZpcm1hZG86ICcrbGVjdHVyYSwnIzA4MCcpOwogIGF2YW56YXJUcmFzRnJlbnRlKCk7Cn0KZnVuY3Rpb24gYWJyaXJDb25maXJtYWNpb25MZWN0dXJhKHRleHRvT0NSLCBsZWlkbyl7CiAgdHJ5ewogICAgdmFyIGNvbnQ9JCgnenlMZWNCb3gnKTsKICAgIGlmKCFjb250KXsKICAgICAgY29udD1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgICAgY29udC5pZD0nenlMZWNCb3gnOwogICAgICBjb250LnN0eWxlLmNzc1RleHQ9J2JvcmRlcjoxcHggc29saWQgIzdjM2FlZDtib3JkZXItcmFkaXVzOjEycHg7cGFkZGluZzoxMHB4O21hcmdpbjo4cHggMDtiYWNrZ3JvdW5kOiMxNzEyMmI7JzsKICAgICAgdmFyIHBzMj0kKCdwczInKTsKICAgICAgaWYocHMyJiZwczIuaW5zZXJ0QmVmb3JlKXsgcHMyLmluc2VydEJlZm9yZShjb250LHBzMi5maXJzdENoaWxkKTsgfSBlbHNlIHsgZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZChjb250KTsgfQogICAgICB2YXIgdDE9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2Jyk7CiAgICAgIHQxLnN0eWxlLmNzc1RleHQ9J2ZvbnQtc2l6ZToxM3B4O2NvbG9yOiNlNmU2ZmE7bWFyZ2luLWJvdHRvbTo2cHg7bGluZS1oZWlnaHQ6MS4zNTsnOwogICAgICB0MS50ZXh0Q29udGVudD0nTm8gcHVkZSBjb25maXJtYXIgZWwgbm9tYnJlIGNvbiBzZWd1cmlkYWQuIEVzdG8gZnVlIGxvIHF1ZSBMRVx1MDBDRCBkZWwgZG9jdW1lbnRvLiBDb3JyaWdlIFNPTE8gbGFzIGxldHJhcyBtYWwgbGVcdTAwRURkYXMgeSBjb25maXJtYTonOwogICAgICBjb250LmFwcGVuZENoaWxkKHQxKTsKICAgICAgdmFyIGlucD1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdpbnB1dCcpOwogICAgICBpbnAuaWQ9J3p5TGVjSW4nOwogICAgICBpbnAudHlwZT0ndGV4dCc7CiAgICAgIGlucC5hdXRvY29tcGxldGU9J29mZic7CiAgICAgIGlucC5wbGFjZWhvbGRlcj0nTm9tYnJlIGxlaWRvIGRlbCBkb2N1bWVudG8nOwogICAgICBpbnAuc3R5bGUuY3NzVGV4dD0nd2lkdGg6MTAwJTtib3gtc2l6aW5nOmJvcmRlci1ib3g7cGFkZGluZzoxMHB4O2JvcmRlci1yYWRpdXM6MTBweDtib3JkZXI6MXB4IHNvbGlkICM0NDQ7YmFja2dyb3VuZDojMGUwYjFlO2NvbG9yOiNmZmY7Zm9udC1zaXplOjE1cHg7dGV4dC10cmFuc2Zvcm06dXBwZXJjYXNlO21hcmdpbi1ib3R0b206OHB4Oyc7CiAgICAgIGNvbnQuYXBwZW5kQ2hpbGQoaW5wKTsKICAgICAgdmFyIGIxPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2J1dHRvbicpOwogICAgICBiMS5pZD0nenlMZWNCdG4nOwogICAgICBiMS50eXBlPSdidXR0b24nOwogICAgICBiMS50ZXh0Q29udGVudD0nQ29uZmlybWFyOiBhc1x1MDBFRCBzZSBsZWUgZW4gbWkgZG9jdW1lbnRvJzsKICAgICAgYjEuc3R5bGUuY3NzVGV4dD0nZGlzcGxheTpibG9jazt3aWR0aDoxMDAlO3BhZGRpbmc6MTFweDtib3JkZXI6MDtib3JkZXItcmFkaXVzOjEwcHg7YmFja2dyb3VuZDojN2MzYWVkO2NvbG9yOiNmZmY7Zm9udC1zaXplOjE0cHg7Zm9udC13ZWlnaHQ6NjAwO21hcmdpbi1ib3R0b206NnB4Oyc7CiAgICAgIGNvbnQuYXBwZW5kQ2hpbGQoYjEpOwogICAgICB2YXIgYjI9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnYnV0dG9uJyk7CiAgICAgIGIyLmlkPSd6eUxlY1JlcCc7CiAgICAgIGIyLnR5cGU9J2J1dHRvbic7CiAgICAgIGIyLnRleHRDb250ZW50PSdNZWpvciByZXBpdG8gbGEgZm90byc7CiAgICAgIGIyLnN0eWxlLmNzc1RleHQ9J2Rpc3BsYXk6YmxvY2s7d2lkdGg6MTAwJTtwYWRkaW5nOjEwcHg7Ym9yZGVyOjA7Ym9yZGVyLXJhZGl1czoxMHB4O2JhY2tncm91bmQ6IzJjMmMzYztjb2xvcjojZGRkO2ZvbnQtc2l6ZToxM3B4Oyc7CiAgICAgIGNvbnQuYXBwZW5kQ2hpbGQoYjIpOwogICAgICB2YXIgbT1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgICAgbS5pZD0nenlMZWNNc2cnOwogICAgICBtLnN0eWxlLmNzc1RleHQ9J2ZvbnQtc2l6ZToxM3B4O21hcmdpbi10b3A6NnB4O2xpbmUtaGVpZ2h0OjEuMzU7JzsKICAgICAgY29udC5hcHBlbmRDaGlsZChtKTsKICAgICAgYjEuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKCl7CiAgICAgICAgdHJ5ewogICAgICAgICAgdmFyIHY9bm9ybSgkKCd6eUxlY0luJyk/JCgnenlMZWNJbicpLnZhbHVlOicnKTsKICAgICAgICAgIHZhciBvY3JUb2tzPXRva2Vuc05vbWJyZURlKGNvbnQuX19vY3J8fCcnKTsKICAgICAgICAgIGlmKCF0b2tlbnNEZSh2KS5sZW5ndGgpeyBtc2coJ3p5TGVjTXNnJywnRXNjcmliZSBsbyBxdWUgc2UgbGVlIGVuIGVsIGRvY3VtZW50byAoc29sbyBsZXRyYXMpLicsJyNjMDAnKTsgcmV0dXJuOyB9CiAgICAgICAgICAvKiBoZXJlZGFkbyB2MTQ6IHNpbiBjYWxsZWpvbiBzaW4gc2FsaWRhLiBBbnRlcywgc2kgZWwgT0NSIGhhYmlhCiAgICAgICAgICAgICBzYWx0YWRvIHVuYSBwYWxhYnJhIChlai4gbm8gbGV5byBBTEZPTlNPKSwgZWwgZ3VhcmRhcnJhaWwKICAgICAgICAgICAgIHJlY2hhemFiYSBsYSBjb3JyZWNjaW9uIGF1bnF1ZSBlc2NyaWJpZXJhcyB0dXMgbm9tYnJlcwogICAgICAgICAgICAgdmVyZGFkZXJvcyB5IGVsIHBhbmVsIHZvbHZpYSBTSUVNUFJFLiBBaG9yYSB0dSBub21icmUgZGVsCiAgICAgICAgICAgICBwYXNvIDEgbWFuZGE6IGVsIGd1YXJkYXJyYWlsIHNvbG8gZXhpZ2UgcXVlIGxhIGNvcnJlY2Npb24KICAgICAgICAgICAgIGd1YXJkZSBhbGd1bmEgcmVsYWNpb24gY29uIGxvIHF1ZSBzZSBsZXlvIGRlbCBkb2N1bWVudG8uICovCiAgICAgICAgICB2YXIgbmM9bm9tYnJlQ29pbmNpZGUoRVNULmVzY3JpdG8sIHYsIGZhbHNlKTsKICAgICAgICAgIGlmKCFuYy5vayl7CiAgICAgICAgICAgIG1zZygnenlMZWNNc2cnLCdDb24gZXNhIGxlY3R1cmEgdHUgbm9tYnJlIHNpZ3VlIHNpbiBjb2luY2lkaXIuIFJldmlzYSB0dSBub21icmUgZGVsIHBhc28gMSBvIHJlcGl0ZSBsYSBmb3RvLicsJyNjMDAnKTsKICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgfQogICAgICAgICAgaWYob2NyVG9rcy5sZW5ndGg+MCYmIWVkaWNpb25BY2VwdGFibGUodiwgb2NyVG9rcykpewogICAgICAgICAgICB2YXIgdmQ9dG9rZW5zRGUodiksIGNvbXBhcnRlPWZhbHNlLCBpMSwgajE7CiAgICAgICAgICAgIGZvcihpMT0wO2kxPHZkLmxlbmd0aCYmIWNvbXBhcnRlO2kxKyspewogICAgICAgICAgICAgIGZvcihqMT0wO2oxPG9jclRva3MubGVuZ3RoO2oxKyspeyBpZihwYXJQYXJlY2lkbyh2ZFtpMV0sb2NyVG9rc1tqMV0pKXsgY29tcGFydGU9dHJ1ZTsgYnJlYWs7IH0gfQogICAgICAgICAgICB9CiAgICAgICAgICAgIGlmKCFjb21wYXJ0ZSl7CiAgICAgICAgICAgICAgbXNnKCd6eUxlY01zZycsJ0VzYSBsZWN0dXJhIG5vIHNlIHBhcmVjZSBhIGxvIHF1ZSBMRVx1MDBDRCBkZWwgZG9jdW1lbnRvLiBDb3JyaWdlIGxhcyBsZXRyYXMgbWFsIGxlXHUwMEVEZGFzIG8gcmVwaXRlIGxhIGZvdG8gY29uIG1lam9yIGx1ei4nLCcjYzAwJyk7CiAgICAgICAgICAgICAgcmV0dXJuOwogICAgICAgICAgICB9CiAgICAgICAgICB9CiAgICAgICAgICBhY2VwdGFyRnJlbnRlQ29uZmlybWFkbyhjb250Ll9fb2NyfHwnJywgdik7CiAgICAgICAgfWNhdGNoKGUpe30KICAgICAgfSk7CiAgICAgIGIyLmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbigpewogICAgICAgIHRyeXsKICAgICAgICAgIG9jdWx0YXJDb25maXJtYWNpb25MZWN0dXJhKCk7CiAgICAgICAgICBtc2coJ3N0RicsJ1RvY2EgQ0FQVFVSQVIgeSByZXBpdGUgbGEgZm90bzogYnVlbmEgbHV6LCBzaW4gYnJpbGxvLCBxdWUgZWwgZG9jdW1lbnRvIGxsZW5lIGVsIG1hcmNvLicsJyNhNjAnKTsKICAgICAgICB9Y2F0Y2goZSl7fQogICAgICB9KTsKICAgIH0KICAgIGNvbnQuX19vY3I9dGV4dG9PQ1J8fCcnOwogICAgdmFyIGlucDI9JCgnenlMZWNJbicpOwogICAgaWYoaW5wMil7IGlucDIudmFsdWU9KGxlaWRvfHwnJyk7IH0KICAgIGNvbnQuc3R5bGUuZGlzcGxheT0nYmxvY2snOwogICAgbXNnKCd6eUxlY01zZycsJycsJycpOwogICAgbXNnKCdzdEYnLCdSZXZpc2EgYWJham8gbG8gcXVlIGxlXHUwMEVEIGRlbCBkb2N1bWVudG86IHB1ZWRlcyBjb3JyZWdpciBsYXMgbGV0cmFzIG1hbCBsZVx1MDBFRGRhcy4nLCcjYTYwJyk7CiAgfWNhdGNoKGUpe30KfQpmdW5jdGlvbiBvY3VsdGFyQ29uZmlybWFjaW9uTGVjdHVyYSgpewogIHZhciBjPSQoJ3p5TGVjQm94Jyk7CiAgaWYoYyl7IGMuc3R5bGUuZGlzcGxheT0nbm9uZSc7IH0KfQpmdW5jdGlvbiBwcm9jZXNhckZyZW50ZShkYXRhVXJsKXsKICBFU1QuZnJlbnRlT2s9ZmFsc2U7CiAgRVNULmNhcmFEb2M9bnVsbDsKICBvY3VsdGFyQ29uZmlybWFjaW9uTGVjdHVyYSgpOwogIGJ1c3kodHJ1ZSk7CiAgbXNnKCdzdEYnLCdMZXllbmRvIGVsIGRvY3VtZW50byAocGFzZSAxIGRlIDMpLi4uJywnJyk7CiAgRVNULmZyZW50ZUltZz1kYXRhVXJsOwogIHNob3dJbWcoJ3BGJyxkYXRhVXJsKTsKICB2YXIgcENhcmE9Y29uVGltZW91dChkZXRlY3RhckNhcmFFbihkYXRhVXJsKSwxNTAwMCk7CiAgdmFyIHBUeHQ9b2NyRnJlbnRlKGRhdGFVcmwpLmNhdGNoKGZ1bmN0aW9uKGUpeyByZXR1cm4gJ09DUl9FUlI6JysoZSYmZS5tZXNzYWdlP2UubWVzc2FnZTonJyk7IH0pOwogIFByb21pc2UuYWxsKFtwQ2FyYSxwVHh0XSkudGhlbihmdW5jdGlvbihyKXsKICAgIHZhciBjYXJhPXJbMF0sIHRleHRvPXJbMV18fCcnOwogICAgaWYodGV4dG8uaW5kZXhPZignT0NSX0VSUjonKT09PTApeyBmYWxsb0xlY3R1cmFGcmVudGUoJ05vIHB1ZGUgbGVlciBlbCBkb2N1bWVudG8gKCcrdGV4dG8uc2xpY2UoOCkrJykuJyk7IHJldHVybjsgfQogICAgaWYodGV4dG8ucmVwbGFjZSgvXHMvZywnJykubGVuZ3RoPDE1KXsgZmFsbG9MZWN0dXJhRnJlbnRlKCdObyBsZVx1MDBFRCBzdWZpY2llbnRlIHRleHRvLiBBY1x1MDBFOXJjYXRlLCBidWVuYSBsdXosIHF1ZSBlbCBkb2N1bWVudG8gbGxlbmUgZWwgbWFyY28uJyk7IHJldHVybjsgfQogICAgdmFyIGxhZG89ZGV0ZWN0YXJMYWRvKHRleHRvLCEhKGNhcmEmJmNhcmEuZGV0ZWN0aW9uKSk7CiAgICBpZihsYWRvPT09J3JldmVyc28nKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RGJywnRXNvIGVzIGVsIFJFVkVSU08gKHNlIHZlbiBkaXJlY2Npb25lcyBvIGxhIHpvbmEgTVJaKS4gTmVjZXNpdG8gZWwgRlJFTlRFOiBkb25kZSBlc3RcdTAwRTEgdHUgRk9UTyB5IHR1cyBkYXRvcy4gVnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICBpZihsYWRvIT09J2ZyZW50ZScgJiYgIShjYXJhJiZjYXJhLmRldGVjdGlvbikpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbXNnKCdzdEYnLCdObyBwdWRlIGNvbmZpcm1hciBxdWUgc2VhIGVsIEZSRU5URS4gQXNlZ1x1MDBGQXJhdGUgZGUgcXVlIHNlIHZlYSB0dSBmb3RvIHkgdHVzIGRhdG9zLCBzaW4gYnJpbGxvLCB5IHZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgaWYoY2FyYSYmY2FyYS5kZXRlY3Rpb24mJmNhcmEuZGVzY3JpcHRvcil7IEVTVC5jYXJhRG9jPWNhcmEuZGVzY3JpcHRvcjsgfQogICAgdmFyIG5jPW5vbWJyZUNvaW5jaWRlKEVTVC5lc2NyaXRvLHRleHRvLG1yekxpbmVhcyh0ZXh0bykubGVuZ3RoPjApOwogICAgaWYobmMuaGF5ICYmICFuYy5vayl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBhYnJpckNvbmZpcm1hY2lvbkxlY3R1cmEodGV4dG8sIG5jLmxlaWRvKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgRVNULmZyZW50ZU9rPXRydWU7CiAgICBFU1QuZnJlbnRlVGV4dG89dGV4dG87CiAgICBtc2coJ3N0RicsJ1x1MjcxMyBGcmVudGUgbGVcdTAwRURkbyBjb3JyZWN0YW1lbnRlLicrKG5jLm9rPygnIE5vbWJyZTogJytuYy5sZWlkbysnLicpOicnKSwnIzA4MCcpOwogICAgYnVzeShmYWxzZSk7CiAgICBhdmFuemFyVHJhc0ZyZW50ZSgpOwogIH0pOwp9Ci8qIHYxNjogTlVOQ0Egc2UgYm9ycmEgdHUgdHJhYmFqbyB5IE5VTkNBIHRlIHJlZ3Jlc2EgYWwgcGFzbyAxLiBBbnRlcwogICBlc3RhIGZ1bmNpb24gcmVzZXRlYWJhIGVsIGRvY3VtZW50byB5IHRlIGJvdGFiYSBhbCBpbmljaW8gKGNvbiBlbAogICBNUlogZGVsIHJldmVyc28gbGVpZG8gYSBtZWRpYXMgZXJhIGNhc2kgc2VndXJvIHF1ZSBzYWx0YXJhKS4gQWhvcmEKICAgc29sbyBhdmlzYSBjb24gY2FsbWEgYXF1aSBtaXNtbzogZm90b3MgeSBhdmFuY2UgcXVlZGFuIGludGFjdG9zLiAqLwpmdW5jdGlvbiBub21icmVOb0NvaW5jaWRlTXNnKHR4dCl7CiAgdmFyIG5uPSQoJ25vbWJyZU5vQ29pbmNpZGUnKTsKICBpZihubil7IG5uLnRleHRDb250ZW50PXR4dDsgbm4uc3R5bGUuZGlzcGxheT0nYmxvY2snOyBubi5zdHlsZS5jb2xvcj0nI2E2MCc7IH0KICBtc2coJ3N0QScsJycpOyBtc2coJ3N0RicsJycpOwogIG1zZygnenlFcnJOb21icmUnLHR4dCsnIFNpIHR1IG5vbWJyZSBlc3RcdTAwRTEgYmllbiBlc2NyaXRvIHB1ZWRlcyBTRUdVSVI6IHRvY2EgQ29udGludWFyLiBUdSBhdmFuY2UgeSB0dXMgZm90b3Mgbm8gc2UgYm9ycmFuLicsJyNhNjAnKTsKfQpmdW5jdGlvbiBib3RvblJlcGV0aXJGb3RvKCl7CiAgdmFyIGI9JCgnenlCdG5SZXBGb3RvJyk7CiAgaWYoIWIpewogICAgYj1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdidXR0b24nKTsKICAgIGIuaWQ9J3p5QnRuUmVwRm90byc7CiAgICBiLnR5cGU9J2J1dHRvbic7CiAgICBiLnRleHRDb250ZW50PSdSZXBldGlyIGxhIGZvdG8gZGVsIGRvY3VtZW50byc7CiAgICBiLnN0eWxlLmNzc1RleHQ9J2Rpc3BsYXk6YmxvY2s7bWFyZ2luOjhweCAwO3BhZGRpbmc6MTFweCAxNHB4O2JvcmRlcjowO2JvcmRlci1yYWRpdXM6MTBweDtiYWNrZ3JvdW5kOiM3YzNhZWQ7Y29sb3I6I2ZmZjtmb250LXNpemU6MTRweDtmb250LXdlaWdodDo2MDA7d2lkdGg6MTAwJTsnOwogICAgYi5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oKXsgdHJ5eyBNT1ZMSUJSRT10cnVlOyBhdmFuemFyKDIpOyBNT1ZMSUJSRT1mYWxzZTsgfWNhdGNoKGUpeyBNT1ZMSUJSRT1mYWxzZTsgfSB9KTsKICAgIHZhciBhbmNsYT0kKCd6eUVyck5vbWJyZScpOwogICAgaWYoYW5jbGEmJmFuY2xhLnBhcmVudE5vZGUpeyBhbmNsYS5wYXJlbnROb2RlLmluc2VydEJlZm9yZShiLGFuY2xhLm5leHRTaWJsaW5nKTsgfQogICAgZWxzZXsgZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZChiKTsgfQogIH0KICBiLnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsKfQoKLyogdjE2OiBib3RvbiBWT0xVTlRBUklPIHBhcmEgaXIgYWwgcGFzbyAxIChudW5jYSB1biBtb3ZpbWllbnRvIGZvcnphZG86CiAgIHNvbG8gYXBhcmVjZSBzaSBkZSB2ZXJkYWQgZmFsdGEgZWwgbm9tYnJlIHkgZWwgdXN1YXJpbyBkZWNpZGUpLiAqLwpmdW5jdGlvbiBib3RvbklyUGFzbzEoKXsKICB2YXIgYj0kKCd6eUJ0bklyMScpOwogIGlmKCFiKXsKICAgIGI9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnYnV0dG9uJyk7CiAgICBiLmlkPSd6eUJ0bklyMSc7CiAgICBiLnR5cGU9J2J1dHRvbic7CiAgICBiLnRleHRDb250ZW50PSdJciBhbCBwYXNvIDEgYSBlc2NyaWJpciBtaSBub21icmUnOwogICAgYi5zdHlsZS5jc3NUZXh0PSdkaXNwbGF5OmJsb2NrO21hcmdpbjo4cHggMDtwYWRkaW5nOjExcHggMTRweDtib3JkZXI6MDtib3JkZXItcmFkaXVzOjEwcHg7YmFja2dyb3VuZDojMmMyYzNjO2NvbG9yOiNkZGQ7Zm9udC1zaXplOjE0cHg7Zm9udC13ZWlnaHQ6NjAwO3dpZHRoOjEwMCU7JzsKICAgIGIuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKCl7IHRyeXsgTU9WTElCUkU9dHJ1ZTsgYXZhbnphcigxKTsgTU9WTElCUkU9ZmFsc2U7IH1jYXRjaChlKXsgTU9WTElCUkU9ZmFsc2U7IH0gfSk7CiAgICB2YXIgYW5jbGE9JCgnenlDbGF2ZU9rJyk7CiAgICBpZihhbmNsYSYmYW5jbGEucGFyZW50Tm9kZSl7IGFuY2xhLnBhcmVudE5vZGUuaW5zZXJ0QmVmb3JlKGIsYW5jbGEubmV4dFNpYmxpbmcpOyB9CiAgICBlbHNleyB2YXIgcHM1PSQoJ3BzNScpOyBpZihwczUpeyBwczUuYXBwZW5kQ2hpbGQoYik7IH0gZWxzZSB7IGRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQoYik7IH0gfQogIH0KICBiLnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsKfQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyAzOiByZXZlcnNvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHJldmVyc29BY2VwdGFibGUodGV4dG8pewogIHZhciB0PSh0ZXh0b3x8JycpLnRvVXBwZXJDYXNlKCk7CiAgaWYoKHQubWF0Y2goLzwvZyl8fFtdKS5sZW5ndGg+PTYpeyByZXR1cm4gdHJ1ZTsgfQogIGlmKC9QREY0ST83Ly50ZXN0KHQucmVwbGFjZSgvXHMvZywnJykpKXsgcmV0dXJuIHRydWU7IH0KICB2YXIgZnVlcnRlcz1bJ0RPTUlDSUxJTycsJ0RJUkVDQ0lPTicsJ0RJUkVDQ0lcdTAwRDNOJywnQ09MT05JQScsJ0JBUlJJTycsJ1JFU0lERU5DSUEnLCdDQVNFUklPJywnQ0FOVE9OJywnQUxERUEnLCdPQlNFUlZBQ0lPTicsJ09CU0VSVkFDSVx1MDBEM04nLCdFU1RBRE8gQ0lWSUwnLCdET05BTlRFJywnR1JVUE8gU0FORycsJ1RJUE8gREUgU0FORycsJ0VORE9SU0VNRU5UJywnUkVTVFJJQ1RJT04nLCdBRERSRVNTJ107CiAgdmFyIGksYz0wOwogIGZvcihpPTA7aTxmdWVydGVzLmxlbmd0aDtpKyspeyBpZih0LmluZGV4T2YoZnVlcnRlc1tpXSk+PTApeyBjKys7IH0gfQogIGlmKGM+PTIpeyByZXR1cm4gdHJ1ZTsgfQogIGlmKEVTVC50aXBvPT09J3VzYScgJiYgL1xiKElTU3xFWFB8RER8NER8NEZ8UkVTVHxFTkR8REwpXGIvLnRlc3QodCkpeyByZXR1cm4gdHJ1ZTsgfQogIHJldHVybiBmYWxzZTsKfQpmdW5jdGlvbiBwcm9jZXNhclJldmVyc28oZGF0YVVybCl7CiAgRVNULnJldmVyc29Paz1mYWxzZTsKICBidXN5KHRydWUpOwogIG1zZygnc3RBJywnTGV5ZW5kbyBlbCByZXZlcnNvLi4uJywnJyk7CiAgRVNULnJldmVyc29JbWc9ZGF0YVVybDsKICBzaG93SW1nKCdwQScsZGF0YVVybCk7CiAgaGFjZXJPY3IoZGF0YVVybCkudGhlbihmdW5jdGlvbih0ZXh0byl7CiAgICBpZih0ZXh0by5yZXBsYWNlKC9ccy9nLCcnKS5sZW5ndGg8MTAgJiYgIXJldmVyc29BY2VwdGFibGUodGV4dG8pKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RBJywnTm8gbGVcdTAwRUQgc3VmaWNpZW50ZSB0ZXh0byBlbiBlbCByZXZlcnNvLiBBY1x1MDBFOXJjYXRlLCBidWVuYSBsdXosIHkgdnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICB2YXIgY2FyYVBlbmQ9bnVsbDsKICAgIHZhciBsYWRvPWRldGVjdGFyTGFkbyh0ZXh0byxmYWxzZSk7CiAgICBpZihsYWRvPT09J2ZyZW50ZScpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbXNnKCdzdEEnLCdFc28gZXMgZWwgRlJFTlRFIChzZSB2ZSBsYSBmb3RvIHkgbG9zIGRhdG9zKS4gTmVjZXNpdG8gZWwgUkVWRVJTTzogZGlyZWNjaW9uZXMgbyBsYSB6b25hIE1SWi4gVnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICBpZihsYWRvIT09J3JldmVyc28nICYmICFyZXZlcnNvQWNlcHRhYmxlKHRleHRvKSl7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBtc2coJ3N0QScsJ05vIHB1ZGUgY29uZmlybWFyIHF1ZSBzZWEgZWwgUkVWRVJTTy4gTXVlc3RyYSBsYXMgZGlyZWNjaW9uZXMgbyBsYSB6b25hIGRlIHJheWl0YXMvTVJaIHkgdnVlbHZlIGEgY2FwdHVyYXIuJywnI2MwMCcpOwogICAgICByZXR1cm47CiAgICB9CiAgICAvKiB2MTY6IGVsIHJldmVyc28gWUEgTk8gdmFsaWRhIGVsIG5vbWJyZS4gRWwgbm9tYnJlIHF1ZWRvCiAgICAgICBjb25maXJtYWRvIGNvbiBlbCBmcmVudGUgeSBzdSBwYW5lbCBkZSBsZWN0dXJhOyBlbCBNUlogZGVsCiAgICAgICByZXZlcnNvIHNhbGUgYSBtZWRpYXMgY29uIHBvY2EgbHV6IHkgaGFjaWEgcXVlIHRlIGJvdGFyYW4gYWwKICAgICAgIHBhc28gMSBjb24gdG9kbyBib3JyYWRvIChlbCByZWJvdGUgcXVlIHJlcG9ydGFzdGUpLiBBcXVpIHNvbG8KICAgICAgIHNlIHZhbGlkYSBxdWUgc2VhIGVsIHJldmVyc28uICovCiAgICBFU1QucmV2ZXJzb09rPXRydWU7CiAgICBFU1QucmV2ZXJzb1RleHRvPXRleHRvOwogICAgdHJ5eyByZXNwYWxkYSgpOyB9Y2F0Y2goZSl7fQogICAgbXNnKCdzdEEnLCdcdTI3MTMgUmV2ZXJzbyBsZVx1MDBFRGRvIGNvcnJlY3RhbWVudGUuJywnIzA4MCcpOwogICAgYnVzeShmYWxzZSk7CiAgICBhdmFuemFyKDQpOwogICAgc2V0VGltZW91dChmdW5jdGlvbigpeyB0cnl7IGFicmlyQ2FtKCc0JywndXNlcicsJ3N0VicsJ2JTZWxmaWUnKS5jYXRjaChmdW5jdGlvbigpe30pOyB9Y2F0Y2goZSl7fSB9LDUwMCk7CiAgfSkuY2F0Y2goZnVuY3Rpb24oZSl7CiAgICBidXN5KGZhbHNlKTsKICAgIG1zZygnc3RBJywnRXJyb3IgbGV5ZW5kbyBlbCByZXZlcnNvOiAnKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOicnKSsnLiBWdWVsdmUgYSBjYXB0dXJhci4nLCcjYzAwJyk7CiAgfSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IHBhc28gNDogc2VsZmllID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHJlY29ydGVSb3N0cm8oZGF0YVVybCwgZGV0KXsKICB0cnl7CiAgICBpZighZGV0IHx8ICFkZXQuZGV0ZWN0aW9uIHx8ICFkZXQuZGV0ZWN0aW9uLmJveCl7IHJldHVybiBQcm9taXNlLnJlc29sdmUoZGF0YVVybCk7IH0KICAgIHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpewogICAgICB2YXIgaW09bmV3IEltYWdlKCk7CiAgICAgIGltLm9ubG9hZD1mdW5jdGlvbigpewogICAgICAgIHRyeXsKICAgICAgICAgIHZhciBiPWRldC5kZXRlY3Rpb24uYm94LCBXMD1pbS53aWR0aCwgSDA9aW0uaGVpZ2h0OwogICAgICAgICAgdmFyIGN3PWIud2lkdGgqMi4yLCBjaD1iLmhlaWdodCoyLjY7CiAgICAgICAgICB2YXIgY3g9Yi54K2Iud2lkdGgvMiwgY3k9Yi55K2IuaGVpZ2h0KjAuNTI7CiAgICAgICAgICB2YXIgeDA9TWF0aC5tYXgoMCxNYXRoLnJvdW5kKGN4LWN3LzIpKSwgeTA9TWF0aC5tYXgoMCxNYXRoLnJvdW5kKGN5LWNoLzIpKTsKICAgICAgICAgIHZhciB3MD1NYXRoLm1pbihXMC14MCxNYXRoLnJvdW5kKGN3KSksIGgwPU1hdGgubWluKEgwLXkwLE1hdGgucm91bmQoY2gpKTsKICAgICAgICAgIGlmKHcwPDQwfHxoMDw0MCl7IHJlcyhkYXRhVXJsKTsgcmV0dXJuOyB9CiAgICAgICAgICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICAgICAgICAgIGMud2lkdGg9dzA7IGMuaGVpZ2h0PWgwOwogICAgICAgICAgdmFyIGc9Yy5nZXRDb250ZXh0KCcyZCcpOwogICAgICAgICAgaWYoIWcpeyByZXMoZGF0YVVybCk7IHJldHVybjsgfQogICAgICAgICAgZy5kcmF3SW1hZ2UoaW0sIHgwLCB5MCwgdzAsIGgwLCAwLCAwLCB3MCwgaDApOwogICAgICAgICAgcmVzKGMudG9EYXRhVVJMKCdpbWFnZS9qcGVnJywwLjkpKTsKICAgICAgICB9Y2F0Y2goZUUpeyByZXMoZGF0YVVybCk7IH0KICAgICAgfTsKICAgICAgaW0ub25lcnJvcj1mdW5jdGlvbigpeyByZXMoZGF0YVVybCk7IH07CiAgICAgIGltLnNyYz1kYXRhVXJsOwogICAgfSk7CiAgfWNhdGNoKGUpeyByZXR1cm4gUHJvbWlzZS5yZXNvbHZlKGRhdGFVcmwpOyB9Cn0KZnVuY3Rpb24gY2FqYURlUXVhZChxLCB2dywgdmgsIG1hcmcpewogIHRyeXsKICAgIGlmKCFxIHx8ICFxLnRsIHx8ICFxLnRyIHx8ICFxLmJyIHx8ICFxLmJsKXsgcmV0dXJuIG51bGw7IH0KICAgIHZhciB4cz1bcS50bC54LHEudHIueCxxLmJyLngscS5ibC54XSwgeXM9W3EudGwueSxxLnRyLnkscS5ici55LHEuYmwueV07CiAgICB2YXIgeDA9TWF0aC5taW4uYXBwbHkobnVsbCx4cyksIHgxPU1hdGgubWF4LmFwcGx5KG51bGwseHMpOwogICAgdmFyIHkwPU1hdGgubWluLmFwcGx5KG51bGwseXMpLCB5MT1NYXRoLm1heC5hcHBseShudWxsLHlzKTsKICAgIHZhciBteD0oeDEteDApKm1hcmcsIG15PSh5MS15MCkqbWFyZzsKICAgIHgwPU1hdGgubWF4KDAsTWF0aC5mbG9vcih4MC1teCkpOyB5MD1NYXRoLm1heCgwLE1hdGguZmxvb3IoeTAtbXkpKTsKICAgIHgxPU1hdGgubWluKHZ3LE1hdGguY2VpbCh4MStteCkpOyB5MT1NYXRoLm1pbih2aCxNYXRoLmNlaWwoeTErbXkpKTsKICAgIGlmKHgxLXgwPDQwfHx5MS15MDw0MCl7IHJldHVybiBudWxsOyB9CiAgICByZXR1cm4ge3g6eDAsIHk6eTAsIHc6eDEteDAsIGg6eTEteTB9OwogIH1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0KfQpmdW5jdGlvbiBjYXB0dXJhclZpZGVvRG9jKHBzSWQsIG1heERpbSl7CiAgdmFyIHY9ZmluZFZpZGVvKHBzSWQpOwogIGlmKCF2IHx8ICF2LnZpZGVvV2lkdGggfHwgIXN0cmVhbXNbcHNJZF0peyByZXR1cm4gbnVsbDsgfQogIHZhciB2dz12LnZpZGVvV2lkdGgsIHZoPXYudmlkZW9IZWlnaHQ7CiAgdmFyIHN0PXp5RGV0KClbcHNJZF18fG51bGw7CiAgdmFyIHI9bnVsbCwgYWhvcmE9RGF0ZS5ub3coKTsKICBpZihzdCl7CiAgICBpZihzdC51bHRRdWFkICYmIChhaG9yYS0oc3QudWx0UXVhZFR8fDApKTwxNTAwKXsgcj1jYWphRGVRdWFkKHN0LnVsdFF1YWQsIHZ3LCB2aCwgMC4wNCk7IH0KICAgIGlmKCFyICYmIHN0LnVsdENhamEgJiYgKGFob3JhLShzdC51bHRDYWphVHx8MCkpPDIwMDApewogICAgICB2YXIgYj1zdC51bHRDYWphLCBteD1iLncqMC4wMywgbXk9Yi5oKjAuMDM7CiAgICAgIHZhciBieD1NYXRoLm1heCgwLE1hdGguZmxvb3IoYi54LW14KSksIGJ5PU1hdGgubWF4KDAsTWF0aC5mbG9vcihiLnktbXkpKTsKICAgICAgdmFyIGJ3PU1hdGgubWluKHZ3LWJ4LE1hdGguY2VpbChiLncrbXgqMikpLCBiaD1NYXRoLm1pbih2aC1ieSxNYXRoLmNlaWwoYi5oK215KjIpKTsKICAgICAgaWYoYnc+PTQwJiZiaD49NDApeyByPXt4OmJ4LCB5OmJ5LCB3OmJ3LCBoOmJofTsgfQogICAgfQogIH0KICBpZighcil7IHI9e3g6TWF0aC5yb3VuZCh2dyowLjA3KSwgeTpNYXRoLnJvdW5kKHZoKjAuMDkpLCB3Ok1hdGgucm91bmQodncqMC44NiksIGg6TWF0aC5yb3VuZCh2aCowLjgyKX07IH0KICBpZihyLng8MCl7IHIueD0wOyB9CiAgaWYoci55PDApeyByLnk9MDsgfQogIGlmKHIueCtyLnc+dncpeyByLnc9dnctci54OyB9CiAgaWYoci55K3IuaD52aCl7IHIuaD12aC1yLnk7IH0KICBpZihyLnc8NDB8fHIuaDw0MCl7IHJldHVybiBjYXB0dXJhclZpZGVvKHBzSWQsIG1heERpbSk7IH0KICB2YXIgc2M9TWF0aC5taW4oMSwgKG1heERpbXx8MTYwMCkvTWF0aC5tYXgoci53LCByLmgpKTsKICB2YXIgYz1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdjYW52YXMnKTsKICBjLndpZHRoPU1hdGgubWF4KDE2LE1hdGgucm91bmQoci53KnNjKSk7CiAgYy5oZWlnaHQ9TWF0aC5tYXgoMTYsTWF0aC5yb3VuZChyLmgqc2MpKTsKICB2YXIgZz1jLmdldENvbnRleHQoJzJkJyk7CiAgaWYoIWcpeyByZXR1cm4gY2FwdHVyYXJWaWRlbyhwc0lkLCBtYXhEaW0pOyB9CiAgZy5kcmF3SW1hZ2Uodiwgci54LCByLnksIHIudywgci5oLCAwLCAwLCBjLndpZHRoLCBjLmhlaWdodCk7CiAgdmFyIGQ9Yy50b0RhdGFVUkwoJ2ltYWdlL2pwZWcnLDAuOSk7CiAgcGFyYXJDYW0ocHNJZCk7CiAgcmV0dXJuIGQ7Cn0KZnVuY3Rpb24gcHJvY2VzYXJTZWxmaWUoKXsKICBFU1Quc2VsZmllT2s9ZmFsc2U7CiAgdmFyIGltZz1jYXB0dXJhclZpZGVvKCc0JywxMDQ4KTsKICBpZighaW1nKXsgbXNnKCdzdFYnLCdQcmltZXJvIGFicmUgbGEgY2FtYXJhIHkgcG9uIHR1IGNhcmEgZGVudHJvIGRlbCBtYXJjby4nLCcjYzAwJyk7IHJldHVybjsgfQogIGJ1c3kodHJ1ZSk7CiAgbXNnKCdzdFYnLCdCdXNjYW5kbyB0dSByb3N0cm8gcGFyYSBsYSBmb3RvIGRlIGNhcmEuLi4nLCcnKTsKICBjb25UaW1lb3V0KGRldGVjdGFyQ2FyYUVuKGltZyksMTIwMDApLnRoZW4oZnVuY3Rpb24oZDApewogICAgdmFyIHBSZWM9KGQwJiZkMC5kZXRlY3Rpb24pP3JlY29ydGVSb3N0cm8oaW1nLGQwKTpQcm9taXNlLnJlc29sdmUoaW1nKTsKICAgIHJldHVybiBwUmVjLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiBpbWc7IH0pOwogIH0pLmNhdGNoKGZ1bmN0aW9uKCl7IHJldHVybiBpbWc7IH0pLnRoZW4oZnVuY3Rpb24ocmVjKXsKICAgIEVTVC5zZWxmaWVJbWc9cmVjfHxpbWc7CiAgICBFU1Qucm9zdHJvUmVjb3J0YWRvPSEhKHJlYyYmcmVjIT09aW1nKTsKICAgIHNob3dJbWcoJ3BTJyxFU1Quc2VsZmllSW1nKTsKICAgIG1zZygnc3RWJywnQ29tcGFyYW5kbyB0dSBjYXJhIGNvbiBsYSBkZWwgZG9jdW1lbnRvLi4uJywnJyk7CiAgICB2YXIgcERvYz1FU1QuY2FyYURvYz9Qcm9taXNlLnJlc29sdmUoRVNULmNhcmFEb2MpOmNvblRpbWVvdXQoZGV0ZWN0YXJDYXJhRG9jKEVTVC5mcmVudGVJbWd8fEVTVC5yZXZlcnNvSW1nfHwnJyksMTUwMDApLnRoZW4oZnVuY3Rpb24ocil7IHJldHVybiAociYmci5kZXRlY3Rpb24mJnIuZGVzY3JpcHRvcik/ci5kZXNjcmlwdG9yOm51bGw7IH0pOwogICAgdmFyIHBTZWw9Y29uVGltZW91dChkZXRlY3RhckNhcmFFbihFU1Quc2VsZmllSW1nLDIpLDE1MDAwKS50aGVuKGZ1bmN0aW9uKHIwKXsKICAgICAgaWYocjAmJnIwLmRldGVjdGlvbil7IHJldHVybiByMDsgfQogICAgICByZXR1cm4gY29uVGltZW91dChkZXRlY3RhckNhcmFFbihFU1Quc2VsZmllSW1nKSwxNTAwMCk7CiAgICB9KTsKICAgIFByb21pc2UuYWxsKFtwRG9jLHBTZWxdKS50aGVuKGZ1bmN0aW9uKHIpewogICAgICB2YXIgZERvYz1yWzBdLCBlblNlbD1yWzFdOwogICAgICBpZighZERvYyl7IGJ1c3koZmFsc2UpOyBmYWxsb1NlbGZpZSgnTm8gcHVkZSB2ZXIgYmllbiBsYSBjYXJhIGVuIGxhIGZvdG8gZGVsIGRvY3VtZW50by4gVmFtb3MgYSByZXBldGlyIGxhIGZvdG8gZGVsIGRvY3VtZW50byBjb24gbWVqb3IgbHV6LicpOyByZXR1cm47IH0KICAgICAgaWYoIWVuU2VsIHx8ICFlblNlbC5kZXRlY3Rpb24peyBidXN5KGZhbHNlKTsgZmFsbG9TZWxmaWUoJ05vIHB1ZGUgdmVyIHR1IGNhcmEgZW4gbGEgc2VsZmllLiBNZWpvciBsYSBsdXosIHF1aXRhdGUgZ29ycmEgbyBsZW50ZXMgb3NjdXJvcy4nKTsgcmV0dXJuOyB9CiAgICAgIHZhciBkPWRpc3RGKGREb2MsZW5TZWwuZGVzY3JpcHRvcik7CiAgICAgIGlmKGQ8PTAuNjApewogICAgICAgIEVTVC5zZWxmaWVPaz10cnVlOyBFU1QuaW50ZW50b3M9NTsKICAgICAgICB0cnl7IHJlc3BhbGRhKCk7IH1jYXRjaChlKXt9CiAgICAgICAgbXNnKCdzdFYnLCdcdTI3MTMgVmVyaWZpY2FjaVx1MDBGM24gZmFjaWFsIHN1cGVyYWRhLiBQYXNhbmRvIGEgdHUgY2xhdmUuJywnIzA4MCcpOwogICAgICAgIGJ1c3koZmFsc2UpOyBhdmFuemFyKDUpOwogICAgICB9ZWxzZXsKICAgICAgICBidXN5KGZhbHNlKTsKICAgICAgICBmYWxsb1NlbGZpZSgnVHUgY2FyYSBubyBjb2luY2lkZSBjb24gbGEgZGVsIGRvY3VtZW50byAoZGlzdGFuY2lhICcrZC50b0ZpeGVkKDIpKycpLicrKEVTVC5yb3N0cm9SZWNvcnRhZG8/Jyc6JyBBY2VyY2F0ZTogdHUgY2FyYSBkZWJlIGxsZW5hciBlbCBvdmFsby4nKSk7CiAgICAgIH0KICAgIH0pLmNhdGNoKGZ1bmN0aW9uKGUpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgZmFsbG9TZWxmaWUoJ0VsIHZlcmlmaWNhZG9yIGZhY2lhbCBubyBjYXJnXHUwMEYzOiAnKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOicnKSsnLiBSZXZpc2EgdHUgaW50ZXJuZXQgeSByZWludGVudGEuJyk7CiAgICB9KTsKICB9KTsKfQpmdW5jdGlvbiBmYWxsb1NlbGZpZShtKXsKICBFU1QuaW50ZW50b3MtLTsKICBpZihFU1QuaW50ZW50b3M8PTApewogICAgRVNULmludGVudG9zPTU7CiAgICBFU1Quc2VsZmllT2s9ZmFsc2U7CiAgICBtc2coJ3N0VicsJ1NlIGFnb3Rhcm9uIGxvcyBpbnRlbnRvcyBkZSBsYSBzZWxmaWUsIHBlcm8gTk8gcGVyZGlzdGUgbmFkYTogbmkgdHUgbm9tYnJlIG5pIHR1cyBmb3RvcyBkZWwgZG9jdW1lbnRvIHNlIGJvcnJhbi4gTWVqb3JhIGxhIGx1eiBkZSB0dSBjYXJhLCBBQ0VSQ0FURSBoYXN0YSBxdWUgdHUgY2FyYSBsbGVuZSBlbCBvdmFsbyB5IHRvY2EgQ0FQVFVSQVIgZGUgbnVldm8uJywnI2E2MCcpOwogIH1lbHNlewogICAgbXNnKCdzdFYnLCdcdTI3MTcgJyttKycgVGUgcXVlZGFuICcrRVNULmludGVudG9zKycgaW50ZW50byhzKS4gVG9jYSBDQVBUVVJBUiBkZSBudWV2bzogeW8gcmVjb3J0byBzb2xvIHR1IHJvc3Ryby4nLCcjYzAwJyk7CiAgfQp9Ci8qID09PT09PT09PT09PT09PT09IHBhc28gNTogY2xhdmUgKyBaSUQgKHYxNykgPT09PT09PT09PT09PT09PT0KICAgdjE3OiBMQSBDTEFWRSBZQSBOTyBTRSBQSUVSREUgTkkgU0UgIk9MVklEQSIuIExvIHJlcG9ydGFkbyBjb24gY2FwdHVyYQogICBlbCA5LzExIChlc2NyaWJlcyBsYSBjbGF2ZSwgdG9jYXMgQ3JlYXIgbWkgWklELCBsYSBwYWdpbmEgdnVlbHZlIGNvbiBsYQogICBjbGF2ZSBCT1JSQURBIHkgcGFyZWNlIHF1ZSAibm8gcmVjb25vY2UgbGEgY2xhdmUiKSB0ZW5pYSBjYXVzYXMgY29uY3JldGFzLAogICB0b2RhcyBjb3JyZWdpZGFzIGFxdWk6CiAgIGEpIGxvcyBjYW1wb3Mgc2UgYnVzY2FiYW4gU09MTyBwb3IgaWQgZmlqbyAiY2xhdmUiLyJjbGF2ZTIiOiBzaSBlbAogICAgICBmb3JtdWxhcmlvIHJlYWwgdXNhIG90cm9zIGlkLCBsYSB2YWxpZGFjaW9uIG51bmNhIHZlIGxvIHF1ZSBlc2NyaWJlcy4KICAgICAgQWhvcmEgc2UgZGVzY3VicmVuIHBvciB0aXBvIChpbnB1dFt0eXBlPXBhc3N3b3JkXSkgeSBub21icmUvaWQgcGFyZWNpZG87CiAgIGIpIGVsIGF1dG9ycmVsbGVubyBkZWwgbmF2ZWdhZG9yIG5vIGRpc3BhcmEgImlucHV0IjogYWhvcmEgaGF5IHNvbmRlbwogICAgICBjYWRhIDYwMCBtcyArIGV2ZW50b3MgY2hhbmdlL2JsdXIgeSBzZSBzaW5jcm9uaXphIHNvbG87CiAgIGMpIGFsIHJlY2FyZ2Fyc2UgbGEgcGFnaW5hIGxhIGNsYXZlIG5vIHNlIGd1YXJkYWJhOiBhaG9yYSBxdWVkYSByZXNwYWxkYWRhCiAgICAgIGVuIHNlc3Npb25TdG9yYWdlIChzb2xvIGVuIHR1IHRlbGVmb25vLCBtdWVyZSBhbCBjZXJyYXIgZWwgbmF2ZWdhZG9yKQogICAgICB5IHNlIHJlcG9uZSBzb2xhIGVuIGxvcyBjdWFkcm9zIHF1ZSBlc3RlbiB2YWNpb3MgYWwgdm9sdmVyLiAqLwp2YXIgQ0xWPXthOm51bGwsYjpudWxsLG1vZG86MCx1MTp1bmRlZmluZWQsdTI6dW5kZWZpbmVkfTsKdmFyIEtTRVNNPSd6eUNsYXZlUzE3JzsKZnVuY3Rpb24gY2FtcG9zQ2xhdmUoKXsgcmV0dXJuIFtDTFYuYSxDTFYuYl07IH0KZnVuY3Rpb24gZGVzY3VicmVDbGF2ZXMoZm9yY2UpewogIGlmKCFmb3JjZSYmQ0xWLmEpewogICAgdHJ5eyBpZihDTFYuYS5vd25lckRvY3VtZW50JiZkb2N1bWVudC5jb250YWlucyhDTFYuYSkpeyByZXR1cm4gQ0xWOyB9IH1jYXRjaChlQyl7IH0KICB9CiAgdmFyIGxpc3RhPVtdLCBpLCBqOwogIGZ1bmN0aW9uIG1ldGUoZWwpewogICAgaWYoIWVsfHxsaXN0YS5pbmRleE9mKGVsKT49MCl7IHJldHVybjsgfQogICAgdmFyIHR5PSgoZWwudHlwZXx8JycpKycnKS50b0xvd2VyQ2FzZSgpOwogICAgaWYodHkhPT0ncGFzc3dvcmQnJiZ0eSE9PSd0ZXh0Jyl7IHJldHVybjsgfQogICAgbGlzdGEucHVzaChlbCk7CiAgfQogIG1ldGUoJCgnY2xhdmUnKSk7IG1ldGUoJCgnY2xhdmUyJykpOwogIHZhciBwczU9JCgncHM1Jyk7CiAgaWYobGlzdGEubGVuZ3RoPDImJnBzNSl7CiAgICB2YXIgaW5zPXBzNS5xdWVyeVNlbGVjdG9yQWxsKCdpbnB1dFt0eXBlPXBhc3N3b3JkXScpOwogICAgZm9yKGo9MDtqPGlucy5sZW5ndGgmJmxpc3RhLmxlbmd0aDwyO2orKyl7IG1ldGUoaW5zW2pdKTsgfQogIH0KICBpZihsaXN0YS5sZW5ndGg8MSl7CiAgICB2YXIgZj1udWxsOwogICAgdHJ5eyBmPWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJ2Zvcm0nKTsgfWNhdGNoKGVRKXsgZj1udWxsOyB9CiAgICBpZihmKXsgdmFyIGluczI9Zi5xdWVyeVNlbGVjdG9yQWxsKCdpbnB1dFt0eXBlPXBhc3N3b3JkXScpOyBmb3Ioaj0wO2o8aW5zMi5sZW5ndGgmJmxpc3RhLmxlbmd0aDwyO2orKyl7IG1ldGUoaW5zMltqXSk7IH0gfQogIH0KICBpZihsaXN0YS5sZW5ndGg8MSl7CiAgICB2YXIgaW5zMz1kb2N1bWVudC5xdWVyeVNlbGVjdG9yQWxsKCdpbnB1dFt0eXBlPXBhc3N3b3JkXScpOwogICAgZm9yKGo9MDtqPGluczMubGVuZ3RoJiZsaXN0YS5sZW5ndGg8MjtqKyspeyBtZXRlKGluczNbal0pOyB9CiAgfQogIGlmKGxpc3RhLmxlbmd0aDwxKXsKICAgIHZhciBpbnM0PWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoJ2lucHV0W3R5cGU9dGV4dF0nKTsKICAgIGZvcihqPTA7ajxpbnM0Lmxlbmd0aCYmbGlzdGEubGVuZ3RoPDI7aisrKXsKICAgICAgdmFyIG5tPSgoKGluczRbal0uaWR8fCcnKSsnJykrJyAnKygoaW5zNFtqXS5uYW1lfHwnJykrJycpKS50b0xvd2VyQ2FzZSgpOwogICAgICBpZigvY2xhdmV8cGFzc3xjb250cmFzLy50ZXN0KG5tKSl7IG1ldGUoaW5zNFtqXSk7IH0KICAgIH0KICB9CiAgaWYobGlzdGEubGVuZ3RoPj0yKXsgQ0xWLmE9bGlzdGFbMF07IENMVi5iPWxpc3RhWzFdOyBDTFYubW9kbz0yOyB9CiAgZWxzZSBpZihsaXN0YS5sZW5ndGg9PT0xKXsgQ0xWLmE9bGlzdGFbMF07IENMVi5iPW51bGw7IENMVi5tb2RvPTE7IH0KICBlbHNleyBDTFYuYT1udWxsOyBDTFYuYj1udWxsOyBDTFYubW9kbz0wOyB9CiAgcmV0dXJuIENMVjsKfQpmdW5jdGlvbiBsZWVyQ2xhdmVzKCl7CiAgZGVzY3VicmVDbGF2ZXMoZmFsc2UpOwogIHJldHVybiB7IHYxOihDTFYuYT9DTFYuYS52YWx1ZTonJyksIHYyOihDTFYuYj9DTFYuYi52YWx1ZTonJyksIG1vZG86Q0xWLm1vZG8sIGE6Q0xWLmEsIGI6Q0xWLmIgfTsKfQpmdW5jdGlvbiBndWFyZGFyQ2xhdmVTZXNpb24oKXsKICB0cnl7CiAgICB2YXIgTD1sZWVyQ2xhdmVzKCk7CiAgICBpZighTC5hKXsgcmV0dXJuOyB9CiAgICBzZXNzaW9uU3RvcmFnZS5zZXRJdGVtKEtTRVNNLEpTT04uc3RyaW5naWZ5KHtjMTpMLnYxLGMyOkwudjIsdHM6RGF0ZS5ub3coKX0pKTsKICAgIENMVi51MT1MLnYxOyBDTFYudTI9TC52MjsKICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIHJlc3RhdXJhckNsYXZlU2VzaW9uKCl7CiAgdHJ5ewogICAgdmFyIHM9c2Vzc2lvblN0b3JhZ2UuZ2V0SXRlbShLU0VTTSk7CiAgICBpZighcyl7IHJldHVybiBmYWxzZTsgfQogICAgdmFyIGQ9SlNPTi5wYXJzZShzKXx8e307CiAgICBpZihEYXRlLm5vdygpLShkLnRzfHwwKT44NjQwMDAwMCl7IHNlc3Npb25TdG9yYWdlLnJlbW92ZUl0ZW0oS1NFU00pOyByZXR1cm4gZmFsc2U7IH0KICAgIGRlc2N1YnJlQ2xhdmVzKGZhbHNlKTsKICAgIHZhciBoZWNobz1mYWxzZTsKICAgIGlmKENMVi5hJiYhQ0xWLmEudmFsdWUmJmQuYzEpeyBDTFYuYS52YWx1ZT1kLmMxOyBoZWNobz10cnVlOyB9CiAgICBpZihDTFYuYiYmIUNMVi5iLnZhbHVlJiZkLmMyKXsgQ0xWLmIudmFsdWU9ZC5jMjsgaGVjaG89dHJ1ZTsgfQogICAgcmV0dXJuIGhlY2hvOwogIH1jYXRjaChlKXsgcmV0dXJuIGZhbHNlOyB9Cn0KZnVuY3Rpb24gbWVuc2FqZUNsYXZlKEwpewogIEw9THx8bGVlckNsYXZlcygpOwogIHZhciB2MT1MLnYxfHwnJywgdjI9TC52Mnx8Jyc7CiAgaWYoTC5tb2RvPT09MSl7CiAgICBpZighdjEpeyByZXR1cm4ge3Q6JycsYzonJyxvazpmYWxzZX07IH0KICAgIGlmKHYxLmxlbmd0aDw4KXsgcmV0dXJuIHt0OidcdTI3MTcgVHUgY2xhdmUgdGllbmUgJyt2MS5sZW5ndGgrJyBjYXJhY3Rlcihlcyk7IG5lY2VzaXRhIG1pbmltbyA4LicsYzonI2MwMCcsb2s6ZmFsc2V9OyB9CiAgICByZXR1cm4ge3Q6J1x1MjcxMyBDbGF2ZSBsaXN0YS4gVG9jYSBlbCBib3RcdTAwRjNuIHBhcmEgY3JlYXIgdHUgWklELicsYzonIzA4MCcsb2s6dHJ1ZX07CiAgfQogIGlmKCF2MSYmIXYyKXsgcmV0dXJuIHt0OicnLGM6Jycsb2s6ZmFsc2V9OyB9CiAgaWYoIXYxKXsgcmV0dXJuIHt0OidFc2NyaWJlIHR1IGNsYXZlIGVuIGVsIFBSSU1FUiBjdWFkcm8gKCJDcmVhIHR1IGNsYXZlIGRlIGFjY2VzbyIpLicsYzonI2MwMCcsb2s6ZmFsc2V9OyB9CiAgaWYoIXYyKXsgcmV0dXJuIHt0OidGYWx0YSBSRVBFVElSIGxhIGNsYXZlOiBlc2NyaWJlIGxhIE1JU01BIGNsYXZlIGVuIGVsIHNlZ3VuZG8gY3VhZHJvICgiUmVwaXRlIGxhIGNsYXZlIikuJyxjOicjYjQ1MzA5JyxvazpmYWxzZX07IH0KICBpZih2MS5sZW5ndGg8OCl7IHJldHVybiB7dDonXHUyNzE3IFR1IGNsYXZlIHRpZW5lICcrdjEubGVuZ3RoKycgY2FyYWN0ZXIoZXMpOyBuZWNlc2l0YSBtaW5pbW8gOCBlbiBsb3MgZG9zIGN1YWRyb3MuJyxjOicjYzAwJyxvazpmYWxzZX07IH0KICBpZih2MSE9PXYyKXsgcmV0dXJuIHt0OidcdTI3MTcgTGFzIGNsYXZlcyBOTyBjb2luY2lkZW46IGVsIHNlZ3VuZG8gY3VhZHJvIGRlYmUgc2VyIEVYQUNUQU1FTlRFIGlndWFsIGFsIHByaW1lcm8uJyxjOicjYzAwJyxvazpmYWxzZX07IH0KICByZXR1cm4ge3Q6J1x1MjcxMyBDbGF2ZXMgbGlzdGFzIGUgaWd1YWxlcy4gVG9jYSBlbCBib3RcdTAwRjNuIHBhcmEgY3JlYXIgdHUgWklELicsYzonIzA4MCcsb2s6dHJ1ZX07Cn0KZnVuY3Rpb24gdmFsaWRhckNsYXZlcygpewogIHZhciBMPWxlZXJDbGF2ZXMoKSwgZD0kKCdkZXNnbG9zZScpOwogIGlmKCFMLmEpeyByZXR1cm47IH0KICBndWFyZGFyQ2xhdmVTZXNpb24oKTsKICB2YXIgdD1tZW5zYWplQ2xhdmUoTCk7CiAgaWYoZCl7IGQudGV4dENvbnRlbnQ9dC50OyBkLnN0eWxlLmNvbG9yPXQuYzsgfQogIGlmKHQub2speyBoYWJpbGl0YXJTdWJtaXQoKTsgfQp9CmZ1bmN0aW9uIGhhYmlsaXRhclN1Ym1pdCgpewogIHZhciBwcz0kKCdwczUnKTsKICBpZighcHMpeyByZXR1cm47IH0KICB2YXIgYnRucz1wcy5xdWVyeVNlbGVjdG9yQWxsKCdidXR0b24sIGlucHV0W3R5cGU9YnV0dG9uXSwgaW5wdXRbdHlwZT1zdWJtaXRdLCBbcm9sZT1idXR0b25dJyksIGksIGhheT1mYWxzZTsKICBmb3IoaT0wO2k8YnRucy5sZW5ndGg7aSsrKXsKICAgIHZhciBlc1N1Ym1pdD1mYWxzZTsKICAgIHRyeXsgZXNTdWJtaXQ9KChidG5zW2ldLmdldEF0dHJpYnV0ZSgndHlwZScpfHwnJykudG9Mb3dlckNhc2UoKT09PSdzdWJtaXQnKTsgfWNhdGNoKGVUKXsgZXNTdWJtaXQ9ZmFsc2U7IH0KICAgIHZhciB0PSgoYnRuc1tpXS50ZXh0Q29udGVudHx8JycpKycgJysoYnRuc1tpXS52YWx1ZXx8JycpKS50b1VwcGVyQ2FzZSgpOwogICAgaWYoZXNTdWJtaXR8fC9DUkVBUnxSRUdJU1RSfEZJTkFMSVpBUnxDT05USU5VQVJ8RU5WSUFSfEFDRVBUQVJ8WklELy50ZXN0KHQpKXsgYnRuc1tpXS5kaXNhYmxlZD1mYWxzZTsgaGF5PXRydWU7IH0KICB9CiAgaWYoIWhheSl7IG1zZygnenlDbGF2ZU9rJywnU2kgbm8gdmVzIGVsIGJvdFx1MDBGM24gcGFyYSBjcmVhciB0dSBaSUQsIGF2XHUwMEVEc2FtZS4nLCcjYTYwJyk7IH0KfQoKLyogPT09PT09PT09PT09PT09PT0gcGFzbyA1OiBmaWx0cm8gZmluYWwgYW50ZXMgZGVsIGVudmlvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGNsYXZlc0xpc3RhcygpewogIHZhciBMPWxlZXJDbGF2ZXMoKTsKICBpZighTC5hKXsgcmV0dXJuIGZhbHNlOyB9CiAgaWYoIUwudjF8fEwudjEubGVuZ3RoPDgpeyByZXR1cm4gZmFsc2U7IH0KICBpZihMLm1vZG89PT0yJiZMLnYxIT09TC52Mil7IHJldHVybiBmYWxzZTsgfQogIHJldHVybiB0cnVlOwp9CmZ1bmN0aW9uIGZvdG9zQ29tcGxldGFzKCl7CiAgcmV0dXJuICEhKEVTVC5mcmVudGVPayYmRVNULnNlbGZpZU9rJiYoIUVTVC5uZWNlc2l0YVJldmVyc298fEVTVC5yZXZlcnNvT2spKTsKfQpmdW5jdGlvbiByZWxsZW5hckZvdG9zRm9ybXVsYXJpbygpewogIHZhciBwczU9JCgncHM1Jyk7CiAgdmFyIGY9cHM1PyhwczUucXVlcnlTZWxlY3RvcignZm9ybScpfHxudWxsKTpudWxsOwogIGlmKCFmKXsgdHJ5eyBmPWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3IoJ2Zvcm0nKTsgfWNhdGNoKGUpeyBmPW51bGw7IH0gfQogIGlmKCFmfHwhZi5lbGVtZW50cyl7IHJldHVybjsgfQogIHZhciBlbHM9Zi5lbGVtZW50cywgaTsKICBmb3IoaT0wO2k8ZWxzLmxlbmd0aDtpKyspewogICAgdmFyIGVsPWVsc1tpXTsKICAgIGlmKCFlbCl7IGNvbnRpbnVlOyB9CiAgICB2YXIgdGFnPWVsLnRhZ05hbWV8fCcnOwogICAgaWYodGFnIT09J0lOUFVUJyYmdGFnIT09J1RFWFRBUkVBJyl7IGNvbnRpbnVlOyB9CiAgICB2YXIgdD0oKGVsLnR5cGV8fCcnKSsnJykudG9Mb3dlckNhc2UoKTsKICAgIGlmKHRhZz09PSdJTlBVVCcmJnQhPT0naGlkZGVuJyYmdCE9PSd0ZXh0Jyl7IGNvbnRpbnVlOyB9CiAgICBpZigoZWwudmFsdWV8fCcnKS5sZW5ndGg+MTApeyBjb250aW51ZTsgfQogICAgdmFyIG5vbT0oKChlbC5uYW1lfHwnJykrJycpKycgJysoKGVsLmlkfHwnJykrJycpKS50b0xvd2VyQ2FzZSgpOwogICAgaWYoL2ZyZW50ZXxmcm9udGFsfGFudmVyc298Zm90b2Z8ZG9jMXxmb3RvMS8udGVzdChub20pKXsgaWYoRVNULmZyZW50ZUltZyl7IGVsLnZhbHVlPUVTVC5mcmVudGVJbWc7IH0gfQogICAgZWxzZSBpZigvcmV2ZXJzb3xkb3Jzb3x0cmFzZXJhfGZvdG9yZXZ8ZG9jMnxmb3RvMi8udGVzdChub20pKXsgaWYoRVNULnJldmVyc29JbWcpeyBlbC52YWx1ZT1FU1QucmV2ZXJzb0ltZzsgfSB9CiAgICBlbHNlIGlmKC9zZWxmaWV8cm9zdHJvfGZhY2lhbHxjYXJhfGZhY2V8Zm90bzN8Zm90b3MvLnRlc3Qobm9tKSl7IGlmKEVTVC5zZWxmaWVJbWcpeyBlbC52YWx1ZT1FU1Quc2VsZmllSW1nOyB9IH0KICB9Cn0KZnVuY3Rpb24gZ3VhcmRpYUVudmlvKGV2KXsKICBmdW5jdGlvbiBibG9xdWVhcigpewogICAgaWYoZXYpeyB0cnl7IGlmKGV2LnByZXZlbnREZWZhdWx0KXsgZXYucHJldmVudERlZmF1bHQoKTsgfSBpZihldi5zdG9wUHJvcGFnYXRpb24peyBldi5zdG9wUHJvcGFnYXRpb24oKTsgfSBpZihldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24peyBldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24oKTsgfSB9Y2F0Y2goZSl7fSB9CiAgICByZXR1cm4gZmFsc2U7CiAgfQogIGlmKCFjbGF2ZXNMaXN0YXMoKSl7CiAgICB2YXIgbWM9bWVuc2FqZUNsYXZlKCk7CiAgICBndWFyZGFyQ2xhdmVTZXNpb24oKTsKICAgIG1zZygnenlDbGF2ZU9rJywnQW50ZXMgZGUgY3JlYXIgdHUgWklEOiAnKyhtYy50fHwnZXNjcmliZSBsYSBjbGF2ZSAobWluIDgpIHkgcmVwaXRlbGEgaWd1YWwgZW4gbG9zIGRvcyBjdWFkcm9zLicpLG1jLmN8fCcjYzAwJyk7CiAgICByZXR1cm4gYmxvcXVlYXIoKTsKICB9CiAgLyogdjE2OiBlbCBub21icmUgWUEgTk8gcmVib3RhIGFxdWkuIEFudGVzLCBzaSBlbCBub21icmUgbm8gY2FsemFiYQogICAgIGFsIDEwMCUgY29uIGxhIGxlY3R1cmEgZGVsIGRvY3VtZW50bywgZXN0ZSBndWFyZGlhIHRlIGJvdGFiYSBhbAogICAgIHBhc28gMSBKVVNUTyBhbCBjcmVhciBlbCBaSUQgKHBlcmRpZW5kbyB0b2RvKS4gVHUgbm9tYnJlIHF1ZWRvCiAgICAgY29uZmlybWFkbyBlbiBlbCBwYXNvIDI6IGFxdWkgc29sbyBzZSBhdmlzYSwgbnVuY2Egc2UgcmVncmVzYS4KICAgICBTaSBmYWx0YSBlbCBub21icmUgZGUgdmVyZGFkLCB0ZSBkZWphbW9zIHVuIGJvdG9uIHBhcmEgaXIgZGUKICAgICBmb3JtYSBWT0xVTlRBUklBLCBzaW4gbW92ZXJ0ZSBhIGxhIGZ1ZXJ6YS4gKi8KICBpZighRVNULm5vbWJyZU9rKXsKICAgIG1zZygnenlDbGF2ZU9rJywnRmFsdGEgdHUgbm9tYnJlIGRlbCBwYXNvIDEuIE5vIHRlIG11ZXZvIGRlIGFxdWk6IHVzYSBlbCBib3RvbiBkZSBhYmFqbyBwYXJhIGlyIGEgZXNjcmliaXJsbyBjdWFuZG8gcXVpZXJhcy4nLCcjYTYwJyk7CiAgICBib3RvbklyUGFzbzEoKTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICBpZihFU1QuZnJlbnRlVGV4dG8pewogICAgdmFyIG5jRj1ub21icmVDb2luY2lkZShFU1QuZXNjcml0bywgRVNULmZyZW50ZVRleHRvLCBmYWxzZSk7CiAgICBpZihuY0YuaGF5ICYmICFuY0Yub2spewogICAgICBtc2coJ3p5Q2xhdmVPaycsJ0F2aXNvOiB0dSBub21icmUgKCcrRVNULmVzY3JpdG8rJykgeSBlbCBkZWwgZG9jdW1lbnRvICgnK25jRi5sZWlkbysnKSBkaWZpZXJlbi4gWWEgbG8gY29uZmlybWFzdGUgZW4gZWwgcGFzbyAyLCBhc2kgcXVlIHNlZ3VpbW9zOiBzZSBjcmVhIHR1IFpJRCBjb24gdHUgbm9tYnJlLicsJyNhNjAnKTsKICAgIH0KICB9CiAgaWYoIUVTVC5mcmVudGVPayl7CiAgICBtc2coJ3N0RicsIEVTVC5mcmVudGVJbWc/J0xhIGZvdG8gZGVsIEZSRU5URSBubyBwYXNcdTAwRjMgbGEgbGVjdHVyYS4gVGUgbGxldm8gYWwgcGFzbyAyIHBhcmEgcmVwZXRpcmxhIChsYXMgZGVtYXMgZm90b3Mgc2UgY29uc2VydmFuKS4nOidGYWx0YSBsYSBmb3RvIGRlbCBGUkVOVEUgZGVsIGRvY3VtZW50by4gVGUgbGxldm8gYWwgcGFzbyAyIHBhcmEgdG9tYXJsYSAobGFzIGRlbWFzIGZvdG9zIHNlIGNvbnNlcnZhbikuJywnI2MwMCcpOwogICAgTU9WTElCUkU9dHJ1ZTsgYXZhbnphcigyKTsgTU9WTElCUkU9ZmFsc2U7CiAgICByZXR1cm4gYmxvcXVlYXIoKTsKICB9CiAgaWYoRVNULm5lY2VzaXRhUmV2ZXJzbyYmIUVTVC5yZXZlcnNvT2spewogICAgbXNnKCdzdEEnLCBFU1QucmV2ZXJzb0ltZz8nTGEgZm90byBkZWwgUkVWRVJTTyBubyBwYXNcdTAwRjMgbGEgbGVjdHVyYS4gVGUgbGxldm8gYWwgcGFzbyAzIHBhcmEgcmVwZXRpcmxhLic6J0ZhbHRhIGxhIGZvdG8gZGVsIFJFVkVSU08gZGVsIGRvY3VtZW50by4gVGUgbGxldm8gYWwgcGFzbyAzIHBhcmEgdG9tYXJsYS4nLCcjYzAwJyk7CiAgICBNT1ZMSUJSRT10cnVlOyBhdmFuemFyKDMpOyBNT1ZMSUJSRT1mYWxzZTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICBpZighRVNULnNlbGZpZUltZyl7CiAgICBtc2coJ3N0VicsJ0ZhbHRhIGxhIHNlbGZpZS4gVGUgbGxldm8gYWwgcGFzbyA0IHBhcmEgdG9tYXJsYS4nLCcjYzAwJyk7CiAgICBNT1ZMSUJSRT10cnVlOyBhdmFuemFyKDQpOyBNT1ZMSUJSRT1mYWxzZTsKICAgIHJldHVybiBibG9xdWVhcigpOwogIH0KICBpZighRVNULnNlbGZpZU9rKXsKICAgIG1zZygnc3RWJywnTGEgc2VsZmllIE5PIHBhc1x1MDBGMyBsYSB2ZXJpZmljYWNpXHUwMEYzbiBmYWNpYWwuIFRlIGxsZXZvIGFsIHBhc28gNCBwYXJhIHJlcGV0aXJsYTogYnVlbmEgbHV6IHkgY2FyYSBjZW50cmFkYSBlbiBlbCBcdTAwRjN2YWxvLicsJyNjMDAnKTsKICAgIE1PVkxJQlJFPXRydWU7IGF2YW56YXIoNCk7IE1PVkxJQlJFPWZhbHNlOwogICAgcmV0dXJuIGJsb3F1ZWFyKCk7CiAgfQogIHJlbGxlbmFyRm90b3NGb3JtdWxhcmlvKCk7CiAgbXNnKCd6eUNsYXZlT2snLCdUb2RvIHZlcmlmaWNhZG86IGNyZWFuZG8gdHUgWklELi4uJywnIzA4MCcpOwogIHJldHVybiB0cnVlOwp9CgovKiA9PT09PT09PT09PT09PT09PSB2MTM6IGFudGktYmxvcXVlbyBsZWdhZG8gKyBkaWFnbm9zdGljbyBlbiB2aXZvID09PT09PT09PT09PT09PT09CiAgIEVsIGVycm9yIHJvam8gIkZhbHRhIGxhIGZvdG8gZnJvbnRhbCAocGFzbyAyKSIgTk8gZXN0YSBlbiBlc3RlIG51Y2xlbzogdmllbmUgZGUKICAgY29kaWdvIHZpZWpvIGRlIHN1cGVyYXBwLnB5IGZ1ZXJhIGRlbCBibG9xdWUgbWFyY2FkbyAodW4gc2NyaXB0IGxlZ2FkbyBxdWUKICAgcmUtdmFsaWRhIGFsIGVudmlhciB5IGJsb3F1ZWEsIG8gdGV4dG8gcmVzaWR1YWwgZW4gcGFudGFsbGEpLiBBcXVpIHNlIGhhY2U6CiAgIDEpIGxpbXBpYUxlZ2FkbygpOiBkZXRlY3RhIGZ1bmNpb25lcyBnbG9iYWxlcyBjdXlvIGNvZGlnbyBjb250aWVuZSBlc2UgdGV4dG8geQogICAgICBsYXMgdnVlbHZlIG5vLW9wOyBhZGVtYXMgc2UgdHJhZ2EgbG9zIGFsZXJ0L2NvbmZpcm0gY29uIGVzZSB0ZXh0by4KICAgMikgcHJlZW1wdEVudmlvKCk6IG95ZW50ZSBlbiBXSU5ET1cgZW4gZmFzZSBjYXB0dXJhICh3aW5kb3cgY29ycmUgQU5URVMgcXVlCiAgICAgIGRvY3VtZW50IHkgcXVlIGVsIGZvcm0pLiBTaSBUT0RPIHlhIHBhc28sIHJlbGxlbmEgbGFzIGZvdG9zLCBhdmlzYSAiY3JlYW5kbwogICAgICB0dSBaSUQiIHkgY29ydGEgYSBsb3Mgb3llbnRlcyBsZWdhZG9zIGNvbiBzdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24sIGRlamFuZG8KICAgICAgcXVlIGVsIGVudmlvIG5hdGl2byBkZWwgZm9ybXVsYXJpbyBzaWdhLiBTaSBmYWx0YSBhbGdvLCBubyB0b2NhIG5hZGEuCiAgIDMpIGJhcnJlTWVuc2FqZXMoKTogYm9ycmEgdGV4dG9zIHJvam9zIHJlc2lkdWFsZXMgeSByZS1oYWJpbGl0YSBib3RvbmVzCiAgICAgIGRlc2hhYmlsaXRhZG9zIFNPTE8gY3VhbmRvIHRvZG8geWEgcGFzby4KICAgNCkgcGFuZWxEaWFnKCk6IGJvdG9uICJpIiBmaWpvIGFiYWpvIGEgbGEgZGVyZWNoYTsgbXVlc3RyYSBxdWUgYmxvcXVlYSwgbG9zCiAgICAgIGNhbXBvcyBkZWwgZm9ybXVsYXJpbywgZWwgYWN0aW9uL21ldGhvZCB5IGxhcyBmdW5jaW9uZXMgbGVnYWRhcyBoYWxsYWRhcy4KKi8KdmFyIERJQUc9e2xlZ2FkbzpbXSxhbGVydGFzOjAsdWx0U3VibWl0OicnLHVsdENsaWNrOicnfTsKLyogdjE2OiBUWF9ST0pBIGFtcGxpYWRhLiBBZGVtYXMgZGVsIHRleHRvIHZpZWpvICJGYWx0YSBsYSBmb3RvIGZyb250YWwKICAgKHBhc28gMikiLCBhaG9yYSBjYXphIGxvcyB0ZXh0b3MgZGVsIGNvbnRyb2wgZGUgbm9tYnJlIGRlbCBjb2RpZ28KICAgbGVnYWRvICgiTG9zIG5vbWJyZXMgZGVsIGRvY3VtZW50byAuLi4gbm8gY29pbmNpZGVuIGNvbiBlbCBub21icmUKICAgLi4uIiwgImNvcnJpZ2UgLi4uIHBhc28gMSIpLiBDb24gZXNvIGxpbXBpYUxlZ2FkbyB0YW1iaWVuIG5ldXRyYWxpemEKICAgbGFzIGZ1bmNpb25lcyBkZWwgbGVnYWRvIHF1ZSBib3RhYmFuIGFsIHVzdWFyaW8gYWwgaW5pY2lvIHBvciBlbAogICBub21icmUuICovCnZhciBUWF9ST0pBPS9mYWx0YS57MCwyNH1mcm9udGFsfGZyb250YWwuezAsMjR9cGFzb1xzKjJ8bm9tYnJlcz9ccytkZWxccytkb2N1bWVudG98bm9ccytjb2luY2lkZVtuXT9ccytjb25ccytlbFxzK25vbWJyZXxjb3JyaWdlLnswLDI0fXBhc29ccyoxL2k7CnZhciBNSU9TX0lEUz17J3p5UmVzdW1lbjUnOjEsJ3p5Q2xhdmVPayc6MSwnenlHdWFyZGlhJzoxLCd6eUVyck5vbWJyZSc6MSwnenlFcnJUaXBvJzoxLCd6eUxlY01zZyc6MSwnenlMZWNCb3gnOjEsJ3N0Ric6MSwnc3RBJzoxLCdzdFYnOjF9OwpmdW5jdGlvbiBob3JhMTMoKXsKICB0cnl7IHJldHVybiAobmV3IERhdGUoKSkudG9JU09TdHJpbmcoKS5zbGljZSgxMSwxOSk7IH1jYXRjaChlKXsgcmV0dXJuICcnOyB9Cn0KZnVuY3Rpb24gdG9kb09rUGFyYUNyZWFyKCl7CiAgaWYoIWNsYXZlc0xpc3RhcygpKXsgcmV0dXJuIGZhbHNlOyB9CiAgaWYoIUVTVC5ub21icmVPayl7IHJldHVybiBmYWxzZTsgfQogIGlmKCFFU1QuZnJlbnRlT2speyByZXR1cm4gZmFsc2U7IH0KICBpZihFU1QubmVjZXNpdGFSZXZlcnNvJiYhRVNULnJldmVyc29Payl7IHJldHVybiBmYWxzZTsgfQogIGlmKCFFU1Quc2VsZmllSW1nfHwhRVNULnNlbGZpZU9rKXsgcmV0dXJuIGZhbHNlOyB9CiAgLyogdjE2OiB5YSBOTyBzZSByZS12YWxpZGEgZWwgbm9tYnJlIGFxdWkgKGVyYSBsYSBjYXVzYSBleGFjdGEgZGVsCiAgICAgcmVib3RlIGp1c3RvIGFsIHRvY2FyIGVsIGJvdG9uIGRlIGNyZWFyIGVsIFpJRCkuIEVsIG5vbWJyZSBxdWVkbwogICAgIGNlcnJhZG8gZW4gZWwgcGFzbyAyIGNvbiBzdSBwYW5lbCBkZSBsZWN0dXJhLiAqLwogIHJldHVybiB0cnVlOwp9CmZ1bmN0aW9uIGxpbXBpYUxlZ2FkbygpewogIHZhciBub21icmVzPVtdOwogIHRyeXsKICAgIHZhciBrcz1PYmplY3QuZ2V0T3duUHJvcGVydHlOYW1lcyhXKTsKICAgIGZvcih2YXIgaT0wO2k8a3MubGVuZ3RoO2krKyl7CiAgICAgIHZhciBrPWtzW2ldOwogICAgICB0cnl7CiAgICAgICAgdmFyIHY9V1trXTsKICAgICAgICBpZih0eXBlb2Ygdj09PSdmdW5jdGlvbicmJnYudG9TdHJpbmcmJlRYX1JPSkEudGVzdCh2LnRvU3RyaW5nKCkpJiZrIT09J2xpbXBpYUxlZ2FkbycpewogICAgICAgICAgbm9tYnJlcy5wdXNoKGspOwogICAgICAgICAgV1trXT1mdW5jdGlvbigpe307CiAgICAgICAgfQogICAgICB9Y2F0Y2goZSl7fQogICAgfQogIH1jYXRjaChlKXt9CiAgdHJ5ewogICAgICBpZih0eXBlb2YgVy5hbGVydD09PSdmdW5jdGlvbicmJiFXLl9fenlBbGVydDE2KXsKICAgICAgdmFyIGEwPVcuYWxlcnQ7CiAgICAgIFcuYWxlcnQ9ZnVuY3Rpb24obSl7IGlmKFRYX1JPSkEudGVzdChTdHJpbmcobT09bnVsbD8nJzptKSkpeyBESUFHLmFsZXJ0YXMrKzsgcmV0dXJuOyB9IHJldHVybiBhMC5hcHBseShXLGFyZ3VtZW50cyk7IH07CiAgICAgIFcuX196eUFsZXJ0MTY9dHJ1ZTsKICAgIH0KICAgIGlmKHR5cGVvZiBXLmNvbmZpcm09PT0nZnVuY3Rpb24nJiYhVy5fX3p5Q29uZmlybTE2KXsKICAgICAgdmFyIGMwPVcuY29uZmlybTsKICAgICAgVy5jb25maXJtPWZ1bmN0aW9uKG0peyBpZihUWF9ST0pBLnRlc3QoU3RyaW5nKG09PW51bGw/Jyc6bSkpKXsgRElBRy5hbGVydGFzKys7IHJldHVybiB0cnVlOyB9IHJldHVybiBjMC5hcHBseShXLGFyZ3VtZW50cyk7IH07CiAgICAgIFcuX196eUNvbmZpcm0xNj10cnVlOwogICAgfQogIH1jYXRjaChlKXt9CiAgRElBRy5sZWdhZG89bm9tYnJlczsKICBpZihub21icmVzLmxlbmd0aCl7IGxvZygndjE2OiBmdW5jaW9uZXMgbGVnYWRhcyBuZXV0cmFsaXphZGFzOicsIG5vbWJyZXMuam9pbignLCcpKTsgfQp9CmZ1bmN0aW9uIGJhcnJlTWVuc2FqZXMoKXsKICBpZighdG9kb09rUGFyYUNyZWFyKCkpeyByZXR1cm47IH0KICB0cnl7CiAgICB2YXIgbm9kZXM9ZG9jdW1lbnQuYm9keT9kb2N1bWVudC5ib2R5LnF1ZXJ5U2VsZWN0b3JBbGwoJ2RpdixzcGFuLHAsbGksc2VjdGlvbicpOltdOwogICAgZm9yKHZhciBpPTA7aTxub2Rlcy5sZW5ndGgmJmk8ODAwO2krKyl7CiAgICAgIHZhciBlbD1ub2Rlc1tpXTsKICAgICAgaWYoIWVsfHxlbC5pZD09PSd6eURpYWcxNid8fE1JT1NfSURTW2VsLmlkXSl7IGNvbnRpbnVlOyB9CiAgICAgIC8qIHYxNjogQ09SUkVDQ0lPTiBJTVBPUlRBTlRFLiBBbnRlcyBzZSBsaW1waWFiYSBjdWFscXVpZXIgY29udGVuZWRvcgogICAgICAgICBjdXlvIHRleHRvIGRpamVyYSAiRmFsdGEgbGEgZm90byBmcm9udGFsLi4uIiAtIHkgZWwgcHJvcGlvIHBzNQogICAgICAgICAocXVlIGNvbnRpZW5lIGVsIGZvcm11bGFyaW8geSBlbCBib3RvbiBkZSBjcmVhciBlbCBaSUQpIHBvZGlhCiAgICAgICAgIHF1ZWRhciBiYXJyaWRvOiB0ZXh0Q29udGVudD0nJyBCT1JSQSBsb3MgaGlqb3MsIG8gc2VhIHF1ZSBlbAogICAgICAgICBmb3JtdWxhcmlvIGRlc2FwYXJlY2lhIGp1c3RvIGN1YW5kbyB0b2RvIGVzdGFiYSBsaXN0by4gQWhvcmEgdW4KICAgICAgICAgY29udGVuZWRvciBjb24gZm9ybXVsYXJpby9pbnB1dHMvYm90b25lcyBOVU5DQSBzZSB0b2NhOiBzb2xvIHNlCiAgICAgICAgIGxpbXBpYW4gbG9zIGF2aXNvcyBob2phIChkaXZzIGRlIHRleHRvIHN1ZWx0bykuICovCiAgICAgIGlmKC9ecHNbMS01XSQvLnRlc3QoZWwuaWR8fCcnKSl7IGNvbnRpbnVlOyB9CiAgICAgIHRyeXsgaWYoZWwucXVlcnlTZWxlY3RvciYmZWwucXVlcnlTZWxlY3RvcignZm9ybSxpbnB1dCxidXR0b24sc2VsZWN0LHRleHRhcmVhJykpeyBjb250aW51ZTsgfSB9Y2F0Y2goZVEpe30KICAgICAgdmFyIHQ9ZWwudGV4dENvbnRlbnR8fCcnOwogICAgICBpZihUWF9ST0pBLnRlc3QodCkmJnQubGVuZ3RoPDMwMCl7CiAgICAgICAgZWwudGV4dENvbnRlbnQ9Jyc7CiAgICAgICAgaWYoZWwuc3R5bGUpeyBlbC5zdHlsZS5kaXNwbGF5PSdub25lJzsgfQogICAgICB9CiAgICB9CiAgfWNhdGNoKGUpe30KICB0cnl7CiAgICB2YXIgcHM1PSQoJ3BzNScpOwogICAgaWYocHM1KXsKICAgICAgdmFyIGJzPXBzNS5xdWVyeVNlbGVjdG9yQWxsKCdidXR0b24sIGlucHV0W3R5cGU9c3VibWl0XScpOwogICAgICBmb3IodmFyIGs9MDtrPGJzLmxlbmd0aDtrKyspeyBpZihic1trXS5kaXNhYmxlZCl7IGJzW2tdLmRpc2FibGVkPWZhbHNlOyB9IH0KICAgIH0KICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIHBpbnRhRGlhZygpewogIHZhciBiPSQoJ3p5RGlhZzE2Jyk7CiAgaWYoIWJ8fGIuc3R5bGUuZGlzcGxheT09PSdub25lJyl7IHJldHVybjsgfQogIHZhciBMPVtdOwogIEwucHVzaCgnbnVjbGVvOiBSRVYgRiB2MTcgYWN0aXZvJyk7CiAgTC5wdXNoKCdlc3RhZG86IG5vbWJyZU9rPScrRVNULm5vbWJyZU9rKycgZnJlbnRlT2s9JytFU1QuZnJlbnRlT2srJyByZXZlcnNvT2s9JytFU1QucmV2ZXJzb09rKycgKG5lY2VzaXRhUmV2ZXJzbz0nK0VTVC5uZWNlc2l0YVJldmVyc28rJykgc2VsZmllT2s9JytFU1Quc2VsZmllT2srJyBwYXNvPScrRVNULnBhc28rJyBwYXNvTWF4PScrKEVTVC5wYXNvTWF4fHwxKSk7CiAgTC5wdXNoKCd0b2RvT2tQYXJhQ3JlYXI6ICcrKHRvZG9Pa1BhcmFDcmVhcigpPydTSSc6J05PJykpOwogIEwucHVzaCgnY2xhdmVzOiBtb2RvPScrKENMVi5tb2RvfHwwKSsnIGN1YWRybzE9JysoQ0xWLmE/KCgoQ0xWLmEudmFsdWV8fCcnKS5sZW5ndGgpPygnT0soJytDTFYuYS52YWx1ZS5sZW5ndGgrJyknKTonVkFDSU8nKTonKG5vIGhhbGxhZG8pJykrJyBjdWFkcm8yPScrKENMVi5iPygoKENMVi5iLnZhbHVlfHwnJykubGVuZ3RoKT8oJ09LKCcrQ0xWLmIudmFsdWUubGVuZ3RoKycpJyk6J1ZBQ0lPJyk6KENMVi5tb2RvPT09MT8nKG5vIHJlcXVlcmlkbyknOicobm8gaGFsbGFkbyknKSkpOwogIEwucHVzaCgnY2xhdmUgcmVzcGFsZGFkYSBlbiBzZXNpb246ICcrKGZ1bmN0aW9uKCl7IHRyeXsgdmFyIHM9c2Vzc2lvblN0b3JhZ2UuZ2V0SXRlbShLU0VTTSk7IGlmKCFzKXsgcmV0dXJuICdOTyc7IH0gdmFyIGQ9SlNPTi5wYXJzZShzKXx8e307IHJldHVybiAnU0kgKCcrKChkLmMxfHwnJykubGVuZ3RoKSsnKycrKChkLmMyfHwnJykubGVuZ3RoKSsnIGNhcmFjdGVyZXMpJzsgfWNhdGNoKGUpeyByZXR1cm4gJz8nOyB9IH0pKCkpOwogIEwucHVzaCgnWklEOiAnKyhoYXlFeGl0bygpPygnQ1JFQURPJysoZnVuY3Rpb24oKXsgdHJ5eyB2YXIgYz1sb2NhbFN0b3JhZ2UuZ2V0SXRlbSgnenlaaWRDb2RpZ28xNycpOyByZXR1cm4gYz8oJyAoJytjKycpJyk6Jyc7IH1jYXRjaChlMil7IHJldHVybiAnJzsgfSB9KSgpKToncGVuZGllbnRlJykpOwogIEwucHVzaCgncmVzcGFsZG86ICcrKFcuX196eVJlc2NhdGFkbzE2PydSRUNVUEVSQURPIGFsIGFicmlyJzonZ3VhcmRhZG8gZW4gZXN0ZSB0ZWxlZm9ubycpKycgfCByZWVudmlvcyB0cmFzIHJlYm90ZTogJysoZnVuY3Rpb24oKXsgdHJ5eyByZXR1cm4gbG9jYWxTdG9yYWdlLmdldEl0ZW0oJ3p5UmVib3RlczE2Jyl8fCcwJzsgfWNhdGNoKGUpeyByZXR1cm4gJz8nOyB9IH0pKCkpOwogIEwucHVzaCgnbGVnYWRvIG5ldXRyYWxpemFkbzogJysoRElBRy5sZWdhZG8ubGVuZ3RoP0RJQUcubGVnYWRvLmpvaW4oJywgJyk6JyhuaW5ndW5hIGZ1bmNpb24gY29uIGVsIHRleHRvIHJvam8pJykpOwogIEwucHVzaCgnYWxlcnRhcyByb2phcyB0cmFnYWRhczogJytESUFHLmFsZXJ0YXMpOwogIHZhciBmPW51bGw7CiAgdHJ5eyB2YXIgcHM1PSQoJ3BzNScpOyBmPXBzNT8ocHM1LnF1ZXJ5U2VsZWN0b3IoJ2Zvcm0nKXx8ZG9jdW1lbnQucXVlcnlTZWxlY3RvcignZm9ybScpKTpudWxsOyB9Y2F0Y2goZSl7fQogIGlmKGYpewogICAgTC5wdXNoKCdmb3JtIGFjdGlvbjogJysoZi5nZXRBdHRyaWJ1dGUoJ2FjdGlvbicpfHwnKGVzdGEgbWlzbWEgcGFnaW5hKScpKycgIG1ldGhvZDogJysoKChmLm1ldGhvZHx8J2dldCcpKycnKS50b1VwcGVyQ2FzZSgpKSk7CiAgICB0cnl7CiAgICAgIHZhciBlbHM9Zi5lbGVtZW50cywgdmlzPVtdOwogICAgICBmb3IodmFyIGk9MDtpPGVscy5sZW5ndGgmJnZpcy5sZW5ndGg8MTY7aSsrKXsKICAgICAgICB2YXIgZWw9ZWxzW2ldOwogICAgICAgIGlmKCFlbHx8IWVsLm5hbWUpeyBjb250aW51ZTsgfQogICAgICAgIHZpcy5wdXNoKGVsLm5hbWUrJz0nKygoKGVsLnZhbHVlfHwnJykubGVuZ3RoPjApPygnT0soJytlbC52YWx1ZS5sZW5ndGgrJyknKTonVkFDSU8nKSk7CiAgICAgIH0KICAgICAgTC5wdXNoKCdjYW1wb3M6ICcrKHZpcy5qb2luKCcgfCAnKXx8JyhuaW5ndW5vIGNvbiBuYW1lKScpKTsKICAgIH1jYXRjaChlKXt9CiAgfWVsc2V7CiAgICBMLnB1c2goJ2Zvcm06IE5PIGhheSA8Zm9ybT4gKGVsIGxlZ2FkbyBjcmVhIGVsIFpJRCBwb3IgSlMvZmV0Y2gpJyk7CiAgfQogIHRyeXsKICAgIHZhciBjYW5kPWRvY3VtZW50LnF1ZXJ5U2VsZWN0b3JBbGwoJ1tvbmNsaWNrXSxbb25zdWJtaXRdJyk7CiAgICB2YXIgaGl0cz1bXTsKICAgIGZvcih2YXIgaj0wO2o8Y2FuZC5sZW5ndGgmJmhpdHMubGVuZ3RoPDQ7aisrKXsKICAgICAgdmFyIGM9Y2FuZFtqXTsKICAgICAgdmFyIHM9KChjLmdldEF0dHJpYnV0ZSgnb25jbGljaycpfHwnJykrJyAnKyhjLmdldEF0dHJpYnV0ZSgnb25zdWJtaXQnKXx8JycpKS50cmltKCk7CiAgICAgIGlmKFRYX1JPSkEudGVzdChzKSl7IGhpdHMucHVzaCgoKGMuaWR8fGMudGFnTmFtZSl8fCc/JykrJzogJytzLnJlcGxhY2UoL1xzKy9nLCcgJykuc2xpY2UoMCwxNTApKTsgfQogICAgfQogICAgaWYoaGl0cy5sZW5ndGgpewogICAgICBMLnB1c2goJ3ZhbGlkYWNpb24gbGVnYWRhIGVuIGF0cmlidXRvczonKTsKICAgICAgZm9yKHZhciBxPTA7cTxoaXRzLmxlbmd0aDtxKyspeyBMLnB1c2goJyAgJytoaXRzW3FdKTsgfQogICAgfQogIH1jYXRjaChlKXt9CiAgdHJ5ewogICAgdmFyIFVSPWxvY2FsU3RvcmFnZS5nZXRJdGVtKCd6eVVsdGltYVJlc3B1ZXN0YTE2Jyk7CiAgICBpZihVUil7IEwucHVzaCgncmVzcHVlc3RhIGRlbCBzZXJ2aWRvciAoaW5pY2lvKTogJytVUi5zbGljZSgwLDI2MCkpOyB9CiAgfWNhdGNoKGUpe30KICBpZihESUFHLnVsdENsaWNrKXsgTC5wdXNoKCd1bHRpbW8gY2xpY2s6ICcrRElBRy51bHRDbGljayk7IH0KICBpZihESUFHLnVsdFN1Ym1pdCl7IEwucHVzaCgndWx0aW1vIHN1Ym1pdDogJytESUFHLnVsdFN1Ym1pdCk7IH0KICBiLnRleHRDb250ZW50PUwuam9pbignXG4nKTsKfQpmdW5jdGlvbiBwYW5lbERpYWcoKXsKICB0cnl7CiAgICBpZigkKCd6eURpYWcxNicpKXsgcmV0dXJuOyB9CiAgICB2YXIgY2hpcD1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgIGNoaXAuaWQ9J3p5RGlhZ0NoaXAxNic7CiAgICBjaGlwLnN0eWxlLmNzc1RleHQ9J3Bvc2l0aW9uOmZpeGVkO3JpZ2h0OjEwcHg7Ym90dG9tOjEwcHg7ei1pbmRleDoyMTQ3NDgzNjQ2O3dpZHRoOjMwcHg7aGVpZ2h0OjMwcHg7Ym9yZGVyLXJhZGl1czo1MCU7YmFja2dyb3VuZDojMTExO2NvbG9yOiMwZjA7Zm9udDpib2xkIDE1cHgvMzBweCBtb25vc3BhY2U7dGV4dC1hbGlnbjpjZW50ZXI7Y3Vyc29yOnBvaW50ZXI7b3BhY2l0eTouNTtib3gtc2hhZG93OjAgMXB4IDRweCByZ2JhKDAsMCwwLC40KTsnOwogICAgY2hpcC50ZXh0Q29udGVudD0naSc7CiAgICBjaGlwLnRpdGxlPSdkaWFnbm9zdGljbyB2MTcnOwogICAgY2hpcC5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oKXsKICAgICAgdmFyIGI9JCgnenlEaWFnMTYnKTsKICAgICAgaWYoIWIpeyByZXR1cm47IH0KICAgICAgdmFyIHZpc2libGU9KGIuc3R5bGUuZGlzcGxheT09PSdub25lJyk7CiAgICAgIGIuc3R5bGUuZGlzcGxheT12aXNpYmxlPydibG9jayc6J25vbmUnOwogICAgICBpZih2aXNpYmxlKXsgcGludGFEaWFnKCk7IH0KICAgIH0pOwogICAgdmFyIGJveD1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdwcmUnKTsKICAgIGJveC5pZD0nenlEaWFnMTYnOwogICAgYm94LnN0eWxlLmNzc1RleHQ9J2Rpc3BsYXk6bm9uZTtwb3NpdGlvbjpmaXhlZDtsZWZ0OjhweDtyaWdodDo4cHg7Ym90dG9tOjQ4cHg7ei1pbmRleDoyMTQ3NDgzNjQ1O21heC1oZWlnaHQ6NTUlO292ZXJmbG93OmF1dG87YmFja2dyb3VuZDojMGIwYjBiO2NvbG9yOiMwZjA7Zm9udDoxMXB4LzEuNDUgbW9ub3NwYWNlO3BhZGRpbmc6MTBweDtib3JkZXItcmFkaXVzOjhweDt3aGl0ZS1zcGFjZTpwcmUtd3JhcDt3b3JkLWJyZWFrOmJyZWFrLWFsbDtib3gtc2hhZG93OjAgNHB4IDE2cHggcmdiYSgwLDAsMCwuNSk7bWFyZ2luOjA7JzsKICAgIGJveC50ZXh0Q29udGVudD0nbnVjbGVvOiBSRVYgRiB2MTcnOwogICAgZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZChib3gpOwogICAgZG9jdW1lbnQuYm9keS5hcHBlbmRDaGlsZChjaGlwKTsKICB9Y2F0Y2goZSl7fQp9CmZ1bmN0aW9uIHByZWVtcHRFbnZpbygpewogIFcuYWRkRXZlbnRMaXN0ZW5lcignc3VibWl0JyxmdW5jdGlvbihldil7CiAgICB0cnl7CiAgICAgIHZhciBmPWV2LnRhcmdldDsKICAgICAgaWYoIWZ8fCFmLnRhZ05hbWV8fGYudGFnTmFtZSE9PSdGT1JNJyl7IHJldHVybjsgfQogICAgICBESUFHLnVsdFN1Ym1pdD1ob3JhMTMoKSsnICcrKGYuZ2V0QXR0cmlidXRlKCdhY3Rpb24nKXx8Jyhlc3RhIG1pc21hIHBhZ2luYSknKSsnIFsnKygoKGYubWV0aG9kfHwnZ2V0JykrJycpLnRvVXBwZXJDYXNlKCkpKyddJzsKICAgICAgdmFyIHBzNT0kKCdwczUnKTsKICAgICAgaWYocHM1JiZwczUuY29udGFpbnMoZikmJnRvZG9Pa1BhcmFDcmVhcigpKXsKICAgICAgICByZWxsZW5hckZvdG9zRm9ybXVsYXJpbygpOwogICAgICAgIGJhcnJlTWVuc2FqZXMoKTsKICAgICAgICBndWFyZGFyQ2xhdmVTZXNpb24oKTsKICAgICAgICBtc2coJ3p5Q2xhdmVPaycsJ1RvZG8gdmVyaWZpY2FkbzogY3JlYW5kbyB0dSBaSUQuLi4nLCcjMDgwJyk7CiAgICAgICAgcGludGFEaWFnKCk7CiAgICAgICAgLyogdjE3OiBlbCBlbnZpbyBwcm90ZWdpZG8gcG9yIGZldGNoIHZhIERFU0RFIEVMIFBSSU1FUiBpbnRlbnRvCiAgICAgICAgICAgKGFudGVzIHNvbG8gdHJhcyB1biByZWJvdGUpLiBTaSBlbCBzZXJ2aWRvciBkZXZ1ZWx2ZSBlbAogICAgICAgICAgIGZvcm11bGFyaW8sIE5PIHNlIHJlY2FyZ2EgbGEgcGFnaW5hOiB0ZSBxdWVkYXMgZW4gZWwgcGFzbyA1CiAgICAgICAgICAgY29uIGxhIGNsYXZlIGVzY3JpdGEgeSB0b2RvIGludGFjdG8sIHkgbGEgcmVzcHVlc3RhIGNydWRhCiAgICAgICAgICAgcXVlZGEgZW4gZWwgcGFuZWwgImkiLiBTaSBlbCBzZXJ2aWRvciBjcmVhIGVsIFpJRCwgYXBhcmVjZQogICAgICAgICAgIGxhIHBhbnRhbGxhIGRlIGV4aXRvIGNvbiB0dSBaSUQuICovCiAgICAgICAgaWYoVy5mZXRjaCl7CiAgICAgICAgICAvKiB2MTc6IGRvYmxlIHRvcXVlIHJhcGlkbyAtPiBzZSBpZ25vcmEgZWwgc2VndW5kbyBlbnZpbyAobm8KICAgICAgICAgICAgIGhheSBzZWd1bmRvIHN1Ym1pdCBuYXRpdm8gbWllbnRyYXMgZWwgZmV0Y2ggZXN0YSBlbiB2dWVsbykuICovCiAgICAgICAgICBpZihXLl9fenlFbnZpYW5kbzE3KXsKICAgICAgICAgICAgdHJ5eyBpZihldi5wcmV2ZW50RGVmYXVsdCl7IGV2LnByZXZlbnREZWZhdWx0KCk7IH0gfWNhdGNoKGVQMil7fQogICAgICAgICAgICBpZihldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24peyBldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24oKTsgfQogICAgICAgICAgICByZXR1cm47CiAgICAgICAgICB9CiAgICAgICAgICBXLl9fenlFbnZpYW5kbzE3PXRydWU7CiAgICAgICAgICB0cnl7IGlmKGV2LnByZXZlbnREZWZhdWx0KXsgZXYucHJldmVudERlZmF1bHQoKTsgfSB9Y2F0Y2goZVApe30KICAgICAgICAgIGVudmlhclBvckZldGNoKGYpOwogICAgICAgICAgaWYoZXYuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKXsgZXYuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKCk7IH0KICAgICAgICAgIHJldHVybjsKICAgICAgICB9CiAgICAgICAgaWYoZXYuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKXsgZXYuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKCk7IH0KICAgICAgfQogICAgfWNhdGNoKGUpe30KICB9LHRydWUpOwogIFcuYWRkRXZlbnRMaXN0ZW5lcignY2xpY2snLGZ1bmN0aW9uKGV2KXsKICAgIHRyeXsKICAgICAgdmFyIHBzNT0kKCdwczUnKSwgZWw9ZXYudGFyZ2V0OwogICAgICBpZighcHM1fHwhZWx8fCFwczUuY29udGFpbnMoZWwpKXsgcmV0dXJuOyB9CiAgICAgIHZhciBiPWVsLCBlc0JvdG9uPWZhbHNlLCBwcm9mPTA7CiAgICAgIHdoaWxlKGImJmIhPT1wczUmJnByb2Y8Nil7CiAgICAgICAgdmFyIHRnPWIudGFnTmFtZXx8Jyc7CiAgICAgICAgaWYodGc9PT0nQlVUVE9OJ3x8KHRnPT09J0lOUFVUJyYmKCgoYi50eXBlfHwnJyk9PT0nc3VibWl0Jyl8fCgoYi50eXBlfHwnJyk9PT0naW1hZ2UnKSkpfHwoYi5nZXRBdHRyaWJ1dGUmJmIuZ2V0QXR0cmlidXRlKCdyb2xlJyk9PT0nYnV0dG9uJykpeyBlc0JvdG9uPXRydWU7IGJyZWFrOyB9CiAgICAgICAgYj1iLnBhcmVudE5vZGU7IHByb2YrKzsKICAgICAgfQogICAgICBpZighZXNCb3Rvbnx8IWIpeyByZXR1cm47IH0KICAgICAgdmFyIHR5PShiLnRhZ05hbWU9PT0nQlVUVE9OJyk/KCgoYi5nZXRBdHRyaWJ1dGUoJ3R5cGUnKSl8fCdzdWJtaXQnKSsnJykudG9Mb3dlckNhc2UoKTooKChiLnR5cGV8fCcnKSsnJykudG9Mb3dlckNhc2UoKSk7CiAgICAgIHZhciBlbkZvcm09ZmFsc2UsIHA9YjsKICAgICAgd2hpbGUocCl7IGlmKHAudGFnTmFtZT09PSdGT1JNJyl7IGVuRm9ybT10cnVlOyBicmVhazsgfSBwPXAucGFyZW50Tm9kZTsgfQogICAgICBESUFHLnVsdENsaWNrPWhvcmExMygpKycgJysoYi5pZHx8Yi50YWdOYW1lKSsnIHR5cGU9Jyt0eSsnIGZvcm09JysoZW5Gb3JtPydzaSc6J25vJyk7CiAgICAgIGlmKHR5PT09J3N1Ym1pdCcmJmVuRm9ybSYmdG9kb09rUGFyYUNyZWFyKCkpewogICAgICAgIHJlbGxlbmFyRm90b3NGb3JtdWxhcmlvKCk7CiAgICAgICAgYmFycmVNZW5zYWplcygpOwogICAgICAgIG1zZygnenlDbGF2ZU9rJywnVG9kbyB2ZXJpZmljYWRvOiBjcmVhbmRvIHR1IFpJRC4uLicsJyMwODAnKTsKICAgICAgICBpZihldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24peyBldi5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24oKTsgfQogICAgICB9CiAgICB9Y2F0Y2goZSl7fQogIH0sdHJ1ZSk7Cn0KCi8qIHYxNzogZW52aW8gcHJvdGVnaWRvIHBvciBmZXRjaCBkZXNkZSBlbCBQUklNRVIgaW50ZW50byArIHBhbnRhbGxhIGRlIGV4aXRvLgogICAtIHJlYm90ZSBkZWwgc2Vydmlkb3IgLT4gTk8gcmVjYXJnYTogc2lndWVzIGVuIGVsIHBhc28gNSBjb24gVE9ETyAoY2xhdmUgaW5jbHVpZGEpOwogICAtIGV4aXRvIC0+IG1hcmNhIHp5WmlkT0sxNyArIGNvZGlnbyBkZSBaSUQgc2kgdmllbmUgKyBwYW50YWxsYSB2ZXJkZTsKICAgLSBmYWxsbyBkZWwgY2FuYWwgLT4gcmVpbnRlbnRvIG5vcm1hbCB5IGxhIGNsYXZlIHNlIHJlcG9uZSBzb2xhIGlndWFsLiAqLwpmdW5jdGlvbiBxdWl0YUFjZW50b3Mocyl7CiAgcmV0dXJuIChzfHwnJykucmVwbGFjZSgvW1x1MDBDMC1cdTAwQzVdL2csJ0EnKS5yZXBsYWNlKC9bXHUwMEM4LVx1MDBDQl0vZywnRScpLnJlcGxhY2UoL1tcdTAwQ0MtXHUwMENGXS9nLCdJJykucmVwbGFjZSgvW1x1MDBEMi1cdTAwRDZdL2csJ08nKS5yZXBsYWNlKC9bXHUwMEQ5LVx1MDBEQ10vZywnVScpLnJlcGxhY2UoL1x1MDBEMS9nLCdOJykucmVwbGFjZSgvW1x1MDBFMC1cdTAwRTVdL2csJ2EnKS5yZXBsYWNlKC9bXHUwMEU4LVx1MDBFQl0vZywnZScpLnJlcGxhY2UoL1tcdTAwRUMtXHUwMEVGXS9nLCdpJykucmVwbGFjZSgvW1x1MDBGMi1cdTAwRjZdL2csJ28nKS5yZXBsYWNlKC9bXHUwMEY5LVx1MDBGQ10vZywndScpLnJlcGxhY2UoL1x1MDBGMS9nLCduJyk7Cn0KdmFyIFJYX09LPS8oY3JlYWRvIGNvbiBleGl0b3x6aWQgY3JlYWRvfHppZCBmdWUgY3JlYWRvfGJpZW52ZW5pZHxmZWxpY2lkYWRlc3xyZWdpc3RybyBjb21wbGV0YWRvfGFjY2VzbyBjcmVhZG98eWEgcHVlZGVzIGVudHJhcnxjdWVudGEgY3JlYWRhKS9pOwpmdW5jdGlvbiBleHRyYWVyWmlkKHQpewogIHZhciBtPSh0fHwnJykubWF0Y2goL1pJRFteQS1aYS16MC05XXswLDE2fShbQS1aMC05XVtBLVowLTlcLV17MywxOX0pLyk7CiAgcmV0dXJuIG0/bVsxXTonJzsKfQpmdW5jdGlvbiBzaW5UYWdzKHQpewogIHJldHVybiBTdHJpbmcodHx8JycpLnJlcGxhY2UoLzxzY3JpcHRbXHNcU10qPzxcL3NjcmlwdD4vZ2ksJyAnKS5yZXBsYWNlKC88c3R5bGVbXHNcU10qPzxcL3N0eWxlPi9naSwnICcpLnJlcGxhY2UoLzxbXj5dKz4vZywnICcpLnJlcGxhY2UoLyZuYnNwOy9nLCcgJykucmVwbGFjZSgvXHMrL2csJyAnKS50cmltKCkuc2xpY2UoMCwzMDApOwp9CmZ1bmN0aW9uIHBhbmVsRXhpdG8oemlkLGV4dHJhKXsKICB0cnl7CiAgICBpZigkKCd6eUV4aXRvMTcnKSl7IHJldHVybjsgfQogICAgdmFyIG89ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2Jyk7CiAgICBvLmlkPSd6eUV4aXRvMTcnOwogICAgby5zdHlsZS5jc3NUZXh0PSdwb3NpdGlvbjpmaXhlZDtsZWZ0OjA7cmlnaHQ6MDt0b3A6MDtib3R0b206MDt6LWluZGV4OjIxNDc0ODM2NDc7YmFja2dyb3VuZDpyZ2JhKDQsMzQsMjAsLjk3KTtjb2xvcjojZWFmZmYwO3BhZGRpbmc6MjJweCAxOHB4O292ZXJmbG93OmF1dG87Zm9udC1mYW1pbHk6LWFwcGxlLXN5c3RlbSxSb2JvdG8sQXJpYWwsc2Fucy1zZXJpZjt0ZXh0LWFsaWduOmNlbnRlcjsnOwogICAgdmFyIGg9Jyc7CiAgICBoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjU0cHg7bGluZS1oZWlnaHQ6MTttYXJnaW4tdG9wOjE4cHg7Ij5cdTI3MDU8L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9ImZvbnQtc2l6ZToyNnB4O2ZvbnQtd2VpZ2h0OjgwMDttYXJnaW46MTRweCAwIDZweDsiPlx1MDBBMVRVIFpJRCBGVUUgQ1JFQURPITwvZGl2Pic7CiAgICBoKz0nPGRpdiBzdHlsZT0iZm9udC1zaXplOjE1cHg7b3BhY2l0eTouOTI7Ij5ZYSBmb3JtYXMgcGFydGUgZGUgbGEgUmVkIGRlIGNvbmZpYW56YSBkaWdpdGFsLjwvZGl2Pic7CiAgICBpZih6aWQpeyBoKz0nPGRpdiBzdHlsZT0ibWFyZ2luOjE4cHggYXV0byA2cHg7ZGlzcGxheTppbmxpbmUtYmxvY2s7YmFja2dyb3VuZDojMGEzZDI0O2JvcmRlcjoycHggc29saWQgIzM0ZDM5OTtjb2xvcjojYTdmM2QwO2ZvbnQ6NzAwIDIycHgvMS4yIG1vbm9zcGFjZTtwYWRkaW5nOjEycHggMThweDtib3JkZXItcmFkaXVzOjEycHg7bGV0dGVyLXNwYWNpbmc6MXB4OyI+JytTdHJpbmcoemlkKS5yZXBsYWNlKC9bXkEtWmEtejAtOVwtXS9nLCcnKSsnPC9kaXY+JzsgfQogICAgaCs9JzxkaXYgc3R5bGU9Im1hcmdpbjoxNnB4IDAgNHB4O2ZvbnQtc2l6ZToxNHB4O29wYWNpdHk6Ljk7dGV4dC1hbGlnbjpsZWZ0O21heC13aWR0aDo0MjBweDttYXJnaW4tbGVmdDphdXRvO21hcmdpbi1yaWdodDphdXRvOyI+JzsKICAgIGgrPSc8ZGl2IHN0eWxlPSJtYXJnaW46NnB4IDA7Ij4xLiBBcHVudGEgdHUgWklEJysoemlkPycgKGVsIGNvZGlnbyBkZSBhcnJpYmEpJzonJykrJy48L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9Im1hcmdpbjo2cHggMDsiPjIuIFRvY2EgTElTVE8gYXF1aSBhYmFqby48L2Rpdj4nOwogICAgaCs9JzxkaXYgc3R5bGU9Im1hcmdpbjo2cHggMDsiPjMuIEVudHJhIGNvbiB0dSBjbGF2ZSBkb25kZSBkaWNlICJZYSB0ZW5nbyBaSUQiLjwvZGl2Pic7CiAgICBoKz0nPC9kaXY+JzsKICAgIGlmKGV4dHJhKXsgaCs9JzxkaXYgc3R5bGU9Im1hcmdpbjoxMHB4IGF1dG87Zm9udC1zaXplOjEycHg7b3BhY2l0eTouNzU7bWF4LXdpZHRoOjQyMHB4O3RleHQtYWxpZ246bGVmdDsiPlJlc3B1ZXN0YSBkZWwgc2Vydmlkb3I6ICcrU3RyaW5nKGV4dHJhKS5yZXBsYWNlKC8mL2csJyZhbXA7JykucmVwbGFjZSgvPC9nLCcmbHQ7JykrJzwvZGl2Pic7IH0KICAgIGgrPSc8YnV0dG9uIGlkPSJ6eUV4aXRvQnRuMTciIHR5cGU9ImJ1dHRvbiIgc3R5bGU9Im1hcmdpbi10b3A6MThweDtwYWRkaW5nOjE0cHggNDRweDtib3JkZXI6MDtib3JkZXItcmFkaXVzOjEycHg7YmFja2dyb3VuZDojMjJjNTVlO2NvbG9yOiMwNDIyMGY7Zm9udC1zaXplOjE3cHg7Zm9udC13ZWlnaHQ6ODAwOyI+TElTVE88L2J1dHRvbj4nOwogICAgby5pbm5lckhUTUw9aDsKICAgIGRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQobyk7CiAgICB2YXIgYnQ9JCgnenlFeGl0b0J0bjE3Jyk7CiAgICBpZihidCl7IGJ0LmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbigpeyB0cnl7IG8ucGFyZW50Tm9kZS5yZW1vdmVDaGlsZChvKTsgfWNhdGNoKGVYKXt9IHRyeXsgbG9jYWxTdG9yYWdlLnJlbW92ZUl0ZW0oJ3p5WmlkT0sxNycpOyB9Y2F0Y2goZVkpe30gfSk7IH0KICAgIG1zZygnenlDbGF2ZU9rJywnXHUyNzEzIFpJRCBjcmVhZG8gY29uIGV4aXRvLiBZYSBwdWVkZXMgZW50cmFyIGNvbiB0dSBjbGF2ZS4nLCcjMDgwJyk7CiAgfWNhdGNoKGUpe30KfQpmdW5jdGlvbiBoYXlFeGl0bygpeyB0cnl7IHJldHVybiAhIWxvY2FsU3RvcmFnZS5nZXRJdGVtKCd6eVppZE9LMTcnKTsgfWNhdGNoKGUpeyByZXR1cm4gZmFsc2U7IH0gfQpmdW5jdGlvbiBtb3N0cmFyRXhpdG9TaUhheSgpewogIGlmKCFoYXlFeGl0bygpKXsgcmV0dXJuOyB9CiAgdmFyIHppZD0nJzsKICB0cnl7IHppZD1sb2NhbFN0b3JhZ2UuZ2V0SXRlbSgnenlaaWRDb2RpZ28xNycpfHwnJzsgfWNhdGNoKGUpeyB9CiAgcGFuZWxFeGl0byh6aWQsJycpOwp9CmZ1bmN0aW9uIGVudmlhclBvckZldGNoKGYpewogIHZhciB1cmw9KGYuZ2V0QXR0cmlidXRlKCdhY3Rpb24nKXx8KFcubG9jYXRpb24mJlcubG9jYXRpb24ucGF0aG5hbWUpfHwnJyk7CiAgdmFyIG1ldG9kbz0oKChmLm1ldGhvZHx8J3Bvc3QnKSsnJykudG9VcHBlckNhc2UoKSl8fCdQT1NUJzsKICB2YXIgZmQ9bnVsbDsKICB0cnl7IGZkPW5ldyBGb3JtRGF0YShmKTsgfWNhdGNoKGVGKXsgVy5fX3p5RW52aWFuZG8xNz1mYWxzZTsgcmV0dXJuOyB9CiAgaWYoIVcuZmV0Y2h8fCFmZCl7IFcuX196eUVudmlhbmRvMTc9ZmFsc2U7IHJldHVybjsgfQogIGd1YXJkYXJDbGF2ZVNlc2lvbigpOwogIG1zZygnenlDbGF2ZU9rJywnQ3JlYW5kbyB0dSBaSUQgKGVudmlvIHByb3RlZ2lkbywgc2luIHJlY2FyZ2FyKS4uLicsJyMwODAnKTsKICBXLmZldGNoLmNhbGwoVyx1cmwse21ldGhvZDptZXRvZG8sYm9keTpmZCxjcmVkZW50aWFsczonc2FtZS1vcmlnaW4nLHJlZGlyZWN0Oidmb2xsb3cnfSkudGhlbihmdW5jdGlvbihyKXsKICAgIHJldHVybiByLnRleHQoKTsKICB9KS50aGVuKGZ1bmN0aW9uKHQpewogICAgVy5fX3p5RW52aWFuZG8xNz1mYWxzZTsKICAgIHQ9dHx8Jyc7CiAgICB2YXIgdG49cXVpdGFBY2VudG9zKHQpOwogICAgdHJ5eyBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgnenlVbHRpbWFSZXNwdWVzdGExNicsdC5yZXBsYWNlKC9ccysvZywnICcpLnNsaWNlKDAsNDAwMCkpOyB9Y2F0Y2goZVMpe30KICAgIHZhciByZWJvdGU9L25vbWJyZU5vQ29pbmNpZGV8Q3JlYXIgbWkgWklEfFBBU08gWzE1XSBERSA1fGlkPSJwczEifGlkPSdwczEnfFJlcGl0ZSBsYSBjbGF2ZS9pLnRlc3QodG4pJiYhUlhfT0sudGVzdCh0bik7CiAgICBpZihyZWJvdGUpewogICAgICB2YXIgbj0xOwogICAgICB0cnl7IG49KHBhcnNlSW50KGxvY2FsU3RvcmFnZS5nZXRJdGVtKCd6eVJlYm90ZXMxNicpfHwnMCcsMTApfHwwKSsxOyBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgnenlSZWJvdGVzMTYnLFN0cmluZyhuKSk7IH1jYXRjaChlTCl7fQogICAgICBtc2coJ3p5Q2xhdmVPaycsJ0VsIHNlcnZpZG9yIGRldm9sdmlvIGVsIGZvcm11bGFyaW8gKGludGVudG8gJytuKycpLiBOTyB0b2Nhc3RlIG5hZGEgbWFsIHkgTk8gcGVyZGlzdGUgTkFEQTogc2lndWVzIGVuIGVsIHBhc28gNSBjb24gdHUgY2xhdmUgZXNjcml0YSB5IHR1cyBmb3Rvcy4gQWJyZSBlbCBwYW5lbCAiaSIgcGFyYSB2ZXIgcXVlIHJlc3BvbmRpbyBlbCBzZXJ2aWRvciB5IGF2aXNhbWUuJywnI2E2MCcpOwogICAgICB0cnl7IHZhciBieD0kKCd6eURpYWcxNicpOyBpZihieCl7IGJ4LnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsgfSBwaW50YURpYWcoKTsgfWNhdGNoKGVEKXt9CiAgICB9ZWxzZXsKICAgICAgdmFyIHppZD1leHRyYWVyWmlkKHRuKTsKICAgICAgdHJ5eyBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgnenlaaWRPSzE3JyxTdHJpbmcoRGF0ZS5ub3coKSkpOyBpZih6aWQpeyBsb2NhbFN0b3JhZ2Uuc2V0SXRlbSgnenlaaWRDb2RpZ28xNycsemlkKTsgfSB9Y2F0Y2goZUUpe30KICAgICAgdHJ5eyBsb2NhbFN0b3JhZ2UucmVtb3ZlSXRlbSgnenlSZWJvdGVzMTYnKTsgbG9jYWxTdG9yYWdlLnJlbW92ZUl0ZW0oJ3p5UmVzcGFsZG9GMTYnKTsgc2Vzc2lvblN0b3JhZ2UucmVtb3ZlSXRlbShLU0VTTSk7IH1jYXRjaChlQyl7fQogICAgICB2YXIgcmVjYXJnYT10LmluZGV4T2YoJ1pZUkEtUkVWRicpPj0wOwogICAgICBwYW5lbEV4aXRvKHppZCxzaW5UYWdzKHQpKTsKICAgICAgaWYocmVjYXJnYSl7IHRyeXsgZG9jdW1lbnQub3BlbigpOyBkb2N1bWVudC53cml0ZSh0KTsgZG9jdW1lbnQuY2xvc2UoKTsgfWNhdGNoKGVXKXsgdHJ5eyBXLmxvY2F0aW9uLmhyZWY9dXJsOyB9Y2F0Y2goZUgpe30gfSB9CiAgICB9CiAgfSkuY2F0Y2goZnVuY3Rpb24oZSl7CiAgICBXLl9fenlFbnZpYW5kbzE3PWZhbHNlOwogICAgZ3VhcmRhckNsYXZlU2VzaW9uKCk7CiAgICBtc2coJ3p5Q2xhdmVPaycsJ0VsIGNhbmFsIHByb3RlZ2lkbyBubyByZXNwb25kaW8gKCcrKGUmJmUubWVzc2FnZT9lLm1lc3NhZ2U6J2Vycm9yJykrJykuIFJlaW50ZW50byBub3JtYWw6IHNpIGxhIHBhZ2luYSBzZSByZWNhcmdhLCB0dSBjbGF2ZSBzZSByZXBvbmUgc29sYS4nLCcjYTYwJyk7CiAgICB0cnl7IGYuc3VibWl0KCk7IH1jYXRjaChlRjIpeyB9CiAgfSk7Cn0KCmZ1bmN0aW9uIGVuZ2FuY2hhckVudmlvRmluYWwoKXsKICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdzdWJtaXQnLGZ1bmN0aW9uKGV2KXsKICAgIHRyeXsKICAgICAgdmFyIHBzNT0kKCdwczUnKSwgZj1ldi50YXJnZXQ7CiAgICAgIGlmKHBzNSYmZiYmcHM1LmNvbnRhaW5zKGYpKXsgZ3VhcmRpYUVudmlvKGV2KTsgfQogICAgfWNhdGNoKGUpe30KICB9LHRydWUpOwogIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbihldil7CiAgICB0cnl7CiAgICAgIHZhciBwczU9JCgncHM1JyksIGVsPWV2LnRhcmdldDsKICAgICAgaWYoIXBzNXx8IWVsfHwhcHM1LmNvbnRhaW5zKGVsKSl7IHJldHVybjsgfQogICAgICB2YXIgYj1lbCwgZXNCb3Rvbj1mYWxzZSwgcHJvZj0wOwogICAgICB3aGlsZShiJiZiIT09cHM1JiZwcm9mPDYpewogICAgICAgIHZhciB0Zz1iLnRhZ05hbWV8fCcnOwogICAgICAgIGlmKHRnPT09J0JVVFRPTid8fCh0Zz09PSdJTlBVVCcmJigoYi50eXBlfHwnJyk9PT0nc3VibWl0J3x8KGIudHlwZXx8JycpPT09J2J1dHRvbicpKXx8KGIuZ2V0QXR0cmlidXRlJiZiLmdldEF0dHJpYnV0ZSgncm9sZScpPT09J2J1dHRvbicpKXsgZXNCb3Rvbj10cnVlOyBicmVhazsgfQogICAgICAgIGI9Yi5wYXJlbnROb2RlOyBwcm9mKys7CiAgICAgIH0KICAgICAgaWYoIWVzQm90b24peyByZXR1cm47IH0KICAgICAgaWYoIWNsYXZlc0xpc3RhcygpfHwhZm90b3NDb21wbGV0YXMoKSl7IGd1YXJkaWFFbnZpbyhldik7IH0KICAgICAgZWxzZXsgcmVsbGVuYXJGb3Rvc0Zvcm11bGFyaW8oKTsgfQogICAgfWNhdGNoKGUpe30KICB9LHRydWUpOwp9CgovKiA9PT09PT09PT09PT09PT09PSBpbnRlcnJ1cHRvciBkZSBib3RvbmVzID09PT09PT09PT09PT09PT09ICovCnZhciBNSU89eydiQWJyaXJGJzoxLCdiQ2FwRic6MSwnYkFicmlyQSc6MSwnYkNhcEEnOjEsJ2JBYnJpckNhbSc6MSwnYlNlbGZpZSc6MSwnYlJlcFNlbGZpZSc6MSwnYklyNCc6MSwnYklyNSc6MX07CmZ1bmN0aW9uIG1hbmVqYXIoaWQpewogIHN3aXRjaChpZCl7CiAgICBjYXNlICdiQWJyaXJGJzogYWJyaXJDYW0oJzInLCdlbnZpcm9ubWVudCcsJ3N0RicsJ2JDYXBGJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgYnJlYWs7CiAgICBjYXNlICdiQ2FwRic6IHsgdmFyIGY9Y2FwdHVyYXJWaWRlb0RvYygnMicsMTYwMCk7IGlmKCFmKXsgbXNnKCdzdEYnLCdBYnJlIGxhIGNcdTAwRTFtYXJhIHByaW1lcm8gKGJvdFx1MDBGM24gYWJyaXIgY1x1MDBFMW1hcmEpLicsJyNjMDAnKTsgfSBlbHNlIHsgcHJvY2VzYXJGcmVudGUoZik7IH0gYnJlYWs7IH0KICAgIGNhc2UgJ2JBYnJpckEnOiBhYnJpckNhbSgnMycsJ2Vudmlyb25tZW50Jywnc3RBJywnYkNhcEEnKS5jYXRjaChmdW5jdGlvbigpe30pOyBicmVhazsKICAgIGNhc2UgJ2JDYXBBJzogeyB2YXIgYT1jYXB0dXJhclZpZGVvRG9jKCczJywxNjAwKTsgaWYoIWEpeyBtc2coJ3N0QScsJ0FicmUgbGEgY1x1MDBFMW1hcmEgcHJpbWVybyAoYm90XHUwMEYzbiBhYnJpciBjXHUwMEUxbWFyYSkuJywnI2MwMCcpOyB9IGVsc2UgeyBwcm9jZXNhclJldmVyc28oYSk7IH0gYnJlYWs7IH0KICAgIGNhc2UgJ2dhbEYnOiBjbGlja0FyY2hpdm8oJzInKTsgYnJlYWs7CiAgICBjYXNlICdnYWxBJzogY2xpY2tBcmNoaXZvKCczJyk7IGJyZWFrOwogICAgY2FzZSAnYkFicmlyQ2FtJzogRVNULnNlbGZpZU9rPWZhbHNlOyBFU1QuY2FyYVZpdmE9bnVsbDsgYWJyaXJDYW0oJzQnLCd1c2VyJywnc3RWJywnYlNlbGZpZScpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IGJyZWFrOwogICAgY2FzZSAnYlNlbGZpZSc6IHsKICAgICAgdmFyIGN2PUVTVC5jYXJhVml2YSwgdDBzPSh6eURldCgpWyc0J10mJnp5RGV0KClbJzQnXS50MCl8fERhdGUubm93KCk7CiAgICAgIHZhciBsaXN0bz1jdiYmY3Yub2smJigoRGF0ZS5ub3coKS0oY3YudHx8MCkpPDI1MDApOwogICAgICB2YXIgZGV0ZWN0b3JWaWVqbz0oRGF0ZS5ub3coKS10MHMpPjE1MDAwOwogICAgICBpZighbGlzdG8mJiFkZXRlY3RvclZpZWpvKXsKICAgICAgICBtc2coJ3N0VicsIChjdiYmY3YudmlzdGEpPydDZW50cmEgdHUgY2FyYSBkZW50cm8gZGVsIE9WQUxPIChkZWJlIHBvbmVyc2UgVkVSREUpIHkgbHVlZ28gdG9jYSBDQVBUVVJBUi4nOidQcmVwYXJhbmRvIGVsIGRldGVjdG9yIGZhY2lhbC4uLiBlc3BlcmEgdW5vcyBzZWd1bmRvcy4nLCcjYTYwJyk7CiAgICAgICAgYnJlYWs7CiAgICAgIH0KICAgICAgcHJvY2VzYXJTZWxmaWUoKTsKICAgICAgYnJlYWs7CiAgICB9CiAgICBjYXNlICdiUmVwU2VsZmllJzogRVNULnNlbGZpZU9rPWZhbHNlOyBFU1QuY2FyYVZpdmE9bnVsbDsgYWJyaXJDYW0oJzQnLCd1c2VyJywnc3RWJywnYlNlbGZpZScpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IGJyZWFrOwogICAgY2FzZSAnYklyNCc6CiAgICAgIGlmKHBlcm1pdGlkb0hhc3RhKCk+PTQpeyBhdmFuemFyKDQpOyB9CiAgICAgIGVsc2V7IG1zZygnc3RBJywnQVx1MDBGQW4gbm8gcHVlZGVzIHBhc2FyOiBwcmltZXJvIGNvbXBsZXRhIGVsIGRvY3VtZW50byAoZnJlbnRlJysoRVNULm5lY2VzaXRhUmV2ZXJzbz8nIHkgcmV2ZXJzbyc6JycpKycpLicsJyNjMDAnKTsgfQogICAgICBicmVhazsKICAgIGNhc2UgJ2JJcjUnOgogICAgICBpZihwZXJtaXRpZG9IYXN0YSgpPj01KXsgYXZhbnphcig1KTsgfQogICAgICBlbHNleyBtc2coJ3N0VicsJ0FcdTAwRkFuIG5vIHB1ZWRlcyBwYXNhcjogcHJpbWVybyBwYXNhIGxhIHZlcmlmaWNhY2lcdTAwRjNuIGZhY2lhbC4nLCcjYzAwJyk7IH0KICAgICAgYnJlYWs7CiAgfQp9CmRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ2NsaWNrJyxmdW5jdGlvbihlKXsKICB2YXIgZWw9ZS50YXJnZXQ7CiAgd2hpbGUoZWwgJiYgZWwhPT1kb2N1bWVudCAmJiAhKGVsLmlkICYmIE1JT1tlbC5pZF0pKXsgZWw9ZWwucGFyZW50Tm9kZTsgfQogIGlmKCFlbCB8fCBlbD09PWRvY3VtZW50KXsgcmV0dXJuOyB9CiAgaWYoZS5wcmV2ZW50RGVmYXVsdCl7IGUucHJldmVudERlZmF1bHQoKTsgfQogIGlmKGUuc3RvcFByb3BhZ2F0aW9uKXsgZS5zdG9wUHJvcGFnYXRpb24oKTsgfQogIGlmKGUuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKXsgZS5zdG9wSW1tZWRpYXRlUHJvcGFnYXRpb24oKTsgfQogIHRyeXsgbWFuZWphcihlbC5pZCxlKTsgfWNhdGNoKGVycil7IGxvZygnZXJyb3IgZW4nLGVsLmlkLGVycik7IH0KfSx0cnVlKTsKCi8qID09PT09PT09PT09PT09PT09IGdhbGVyaWEgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gY2xpY2tBcmNoaXZvKHBzSWQpewogIHZhciBjb250PSQoJ3BzJytwc0lkKTsKICB2YXIgaW5wPWNvbnQ/Y29udC5xdWVyeVNlbGVjdG9yKCdpbnB1dFt0eXBlPWZpbGVdJyk6bnVsbDsKICBpZihpbnApeyBpbnAuY2xpY2soKTsgfQogIGVsc2V7IG1zZyhwc0lkPT09JzInPydzdEYnOidzdEEnLCdObyBlbmNvbnRyXHUwMEU5IGVsIHNlbGVjdG9yIGRlIGFyY2hpdm9zLicsJyNjMDAnKTsgfQp9CmZ1bmN0aW9uIGVuZ2FuY2hhckdhbGVyaWEoaWQscHNJZCl7CiAgdmFyIGVsPSQoaWQpOwogIGlmKCFlbCl7IHJldHVybjsgfQogIGlmKGVsLnRhZ05hbWU9PT0nSU5QVVQnICYmIChlbC50eXBlfHwnJykudG9Mb3dlckNhc2UoKT09PSdmaWxlJyl7CiAgICBlbC5hZGRFdmVudExpc3RlbmVyKCdjaGFuZ2UnLGZ1bmN0aW9uKCl7CiAgICAgIHZhciBmPWVsLmZpbGVzJiZlbC5maWxlc1swXTsKICAgICAgaWYoIWYpeyByZXR1cm47IH0KICAgICAgYXJjaGl2b0FEYXRvcyhmKS50aGVuKGZ1bmN0aW9uKGQpeyByZXR1cm4gZG93bnNjYWxlKGQsKHBzSWQ9PT0nMid8fHBzSWQ9PT0nMycpPzE2MDA6MTAyNCk7IH0pLnRoZW4oZnVuY3Rpb24oZCl7CiAgICAgICAgaWYocHNJZD09PScyJyl7IHByb2Nlc2FyRnJlbnRlKGQpOyB9IGVsc2UgeyBwcm9jZXNhclJldmVyc28oZCk7IH0KICAgICAgfSkuY2F0Y2goZnVuY3Rpb24oZXIpeyBtc2cocHNJZD09PScyJz8nc3RGJzonc3RBJywnTm8gcHVkZSBsZWVyIGxhIGltYWdlbjogJysoZXImJmVyLm1lc3NhZ2U/ZXIubWVzc2FnZTonJyksJyNjMDAnKTsgfSk7CiAgICB9KTsKICB9ZWxzZXsKICAgIE1JT1tpZF09MTsKICB9Cn0KCi8qID09PT09PT09PT09PT09PT09IGV2ZW50b3MgZGUgcGFzb3MgMSB5IDUgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gZW5nYW5jaGFyUGFzbzEoKXsKICB2YXIgaW5wPSQoJ25vbWJyZScpLCBzZWw9JCgndGlwb0RvYycpOwogIGlmKGlucCl7CiAgICBpbnAuYWRkRXZlbnRMaXN0ZW5lcignaW5wdXQnLGZ1bmN0aW9uKCl7CiAgICAgIC8qIHYxNjogZWRpdGFyIHR1IG5vbWJyZSBKQU1BUyB0ZSBtdWV2ZSBkZSBwYXNvIG5pIHRlIHJlZ3Jlc2EgYWwKICAgICAgICAgaW5pY2lvLiBTaSBxdWVkYSBpbnZhbGlkbyBvIGRpZmllcmUgZGVsIGRvY3VtZW50byBzb2xvIHNlCiAgICAgICAgIGF2aXNhOyB0dSBhdmFuY2UgeSB0dXMgZm90b3Mgc2UgY29uc2VydmFuLiAqLwogICAgICB2YXIgYW50ZXNPaz1FU1Qubm9tYnJlT2s7CiAgICAgIHZhbGlkYXJQYXNvMSh0cnVlKTsKICAgICAgaWYoIUVTVC5ub21icmVPayAmJiBhbnRlc09rICYmIEVTVC5wYXNvPjEpewogICAgICAgIG1zZygnenlFcnJOb21icmUnLCdFbCBub21icmUgcXVlZFx1MDBGMyBpbmNvbXBsZXRvIG8gaW52YWxpZG8uIENvcnJcdTAwRURnZWxvIGFxdVx1MDBFRCBjdWFuZG8gcXVpZXJhczogdHVzIGZvdG9zIHlhIHRvbWFkYXMgc2UgY29uc2VydmFuLicsJyNhNjAnKTsKICAgICAgICByZXR1cm47CiAgICAgIH0KICAgICAgaWYoRVNULm5vbWJyZU9rICYmIEVTVC5wYXNvPjEgJiYgRVNULmZyZW50ZVRleHRvKXsKICAgICAgICB2YXIgbmM9bm9tYnJlQ29pbmNpZGUoRVNULmVzY3JpdG8sIEVTVC5mcmVudGVUZXh0bywgZmFsc2UpOwogICAgICAgIGlmKG5jLmhheSAmJiAhbmMub2spewogICAgICAgICAgbXNnKCd6eUVyck5vbWJyZScsJ0F2aXNvOiBlbCBub21icmUgbnVldm8gbm8gY29pbmNpZGUgY29uIGxvIHF1ZSBkaWNlIGVsIGRvY3VtZW50byAoJytuYy5sZWlkbysnKS4gWWEgY29uZmlybWFzdGUgbGEgbGVjdHVyYSwgYXNpIHF1ZSBwdWVkZXMgc2VndWlyLicsJyNhNjAnKTsKICAgICAgICAgIHJldHVybjsKICAgICAgICB9CiAgICAgIH0KICAgICAgbGltcGlhckVycm9yZXNQYXNvMSgpOwogICAgfSk7CiAgfQogIGlmKHNlbCl7CiAgICBzZWwuYWRkRXZlbnRMaXN0ZW5lcignY2hhbmdlJyxmdW5jdGlvbigpewogICAgICB2YXIgYW50ZXM9RVNULnRpcG87CiAgICAgIHZhbGlkYXJQYXNvMSh0cnVlKTsKICAgICAgaWYoRVNULnRpcG8hPT1hbnRlcyl7IHJlc2V0ZWFyRG9jdW1lbnRvKCk7IH0KICAgICAgbGltcGlhckVycm9yZXNQYXNvMSgpOwogICAgfSk7CiAgfQp9Ci8qIHYxNzogZXZlbnRvcyBkZSBsYSBjbGF2ZSBhIHBydWViYSBkZSB0b2RvOiBlbmxhY2UgZGlyZWN0byBhIGxvcyBjYW1wb3MKICAgaGFsbGFkb3MsIG95ZW50ZSBkZWxlZ2FkbyBlbiBkb2N1bWVudCBwYXJhIGVsIGF1dG9ycmVsbGVubywgeSBzb25kZW8gZGUKICAgNjAwIG1zIHF1ZSBkZXRlY3RhIENVQUxRVUlFUiBjYW1iaW8gKGF1dG9jb21wbGV0YWRvLCBnZXN0b3IgZGUgY2xhdmVzLAogICByZXB1ZXN0byBkZSBsYSBzZXNpb24pLiAqLwpmdW5jdGlvbiBlbmdhbmNoYXJQYXNvNSgpewogIGZ1bmN0aW9uIGVuZ2FuY2hhKCl7CiAgICBkZXNjdWJyZUNsYXZlcyghQ0xWLmEpOwogICAgdmFyIGNzPWNhbXBvc0NsYXZlKCksIGk7CiAgICBmb3IoaT0wO2k8Y3MubGVuZ3RoO2krKyl7CiAgICAgIHZhciBlbD1jc1tpXTsKICAgICAgaWYoIWVsfHxlbC5fX3p5MTcpeyBjb250aW51ZTsgfQogICAgICBlbC5fX3p5MTc9MTsKICAgICAgZWwuYWRkRXZlbnRMaXN0ZW5lcignaW5wdXQnLHZhbGlkYXJDbGF2ZXMpOwogICAgICBlbC5hZGRFdmVudExpc3RlbmVyKCdjaGFuZ2UnLHZhbGlkYXJDbGF2ZXMpOwogICAgICBlbC5hZGRFdmVudExpc3RlbmVyKCdibHVyJyxndWFyZGFyQ2xhdmVTZXNpb24pOwogICAgfQogIH0KICBlbmdhbmNoYSgpOwogIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ2lucHV0JyxmdW5jdGlvbihldil7IHZhciB0PWV2LnRhcmdldDsgaWYodCYmKCh0LnR5cGV8fCcnKSsnJykudG9Mb3dlckNhc2UoKT09PSdwYXNzd29yZCcpeyB2YWxpZGFyQ2xhdmVzKCk7IH0gfSx0cnVlKTsKICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdjaGFuZ2UnLGZ1bmN0aW9uKGV2KXsgdmFyIHQ9ZXYudGFyZ2V0OyBpZih0JiYoKHQudHlwZXx8JycpKycnKS50b0xvd2VyQ2FzZSgpPT09J3Bhc3N3b3JkJyl7IHZhbGlkYXJDbGF2ZXMoKTsgfSB9LHRydWUpOwogIHNldEludGVydmFsKGZ1bmN0aW9uKCl7CiAgICB0cnl7CiAgICAgIHZhciBMPWxlZXJDbGF2ZXMoKTsKICAgICAgaWYoIUwuYSl7IHJldHVybjsgfQogICAgICBpZihMLnYxIT09Q0xWLnUxfHxMLnYyIT09Q0xWLnUyKXsgdmFsaWRhckNsYXZlcygpOyB9CiAgICAgIGVsc2V7IGd1YXJkYXJDbGF2ZVNlc2lvbigpOyB9CiAgICB9Y2F0Y2goZSl7fQogIH0sNjAwKTsKfQoKLyogPT09PT09PT09PT09PT09PT0gdjE2OiByZXNwYWxkbyB5IHJlc2NhdGUgZGVsIHJlZ2lzdHJvID09PT09PT09PT09PT09PT09CiAgIFR1IHJlZ2lzdHJvIHNlIGd1YXJkYSBTT0xPIGVuIHR1IHRlbGVmb25vIChsb2NhbFN0b3JhZ2UpOiBub21icmUsCiAgIHRpcG8gZGUgZG9jdW1lbnRvLCBmb3RvcyB5IGhhc3RhIHF1ZSBwYXNvIGxsZWdhc3RlLiBTaSBlbCBzZXJ2aWRvcgogICB0ZSBkZXZ1ZWx2ZSBlbCBmb3JtdWxhcmlvIHkgbGEgcGFnaW5hIHNlIHZ1ZWx2ZSBhIGNhcmdhciwgYWwgYWJyaXIKICAgZGUgbnVldm8gU0lHVUVTIGRvbmRlIGliYXM6IG5vIGVtcGllemFzIGRlc2RlIGNlcm8gbnVuY2EgbWFzLgogICBTZSBib3JyYSBzb2xvIHNpIHBhc2FuIDI0IGhvcmFzIG8gc2kgY3JlYXMgZWwgWklEIGRlIHZlcmRhZC4gKi8KdmFyIEtFWVI9J3p5UmVzcGFsZG9GMTYnOwpmdW5jdGlvbiByZXNwYWxkYSgpewogIHRyeXsKICAgIGlmKCFFU1Qubm9tYnJlT2smJiFFU1QuZnJlbnRlT2speyByZXR1cm47IH0KICAgIHZhciBpbk49JCgnbm9tYnJlJyksIGluVD0kKCd0aXBvRG9jJyk7CiAgICB2YXIgZD17djoxNiwgdHM6RGF0ZS5ub3coKSwgbm9tYnJlOihpbk4mJmluTi52YWx1ZSk/aW5OLnZhbHVlOicnLCB0aXBvOihpblQmJmluVC52YWx1ZSk/aW5ULnZhbHVlOicnLCBlc2NyaXRvOkVTVC5lc2NyaXRvfHwnJywgcGFzbzpFU1QucGFzb3x8MSwgcGFzb01heDpFU1QucGFzb01heHx8MSwgZnJlbnRlT2s6ISFFU1QuZnJlbnRlT2ssIHJldmVyc29PazohIUVTVC5yZXZlcnNvT2ssIHNlbGZpZU9rOiEhRVNULnNlbGZpZU9rLCBuZWNlc2l0YVJldmVyc286ISFFU1QubmVjZXNpdGFSZXZlcnNvLCBmcmVudGVUZXh0bzpFU1QuZnJlbnRlVGV4dG98fCcnLCBpbWdzOnt9fTsKICAgIGZ1bmN0aW9uIG1ldGVyKCl7CiAgICAgIHRyeXsgbG9jYWxTdG9yYWdlLnNldEl0ZW0oS0VZUixKU09OLnN0cmluZ2lmeShkKSk7IHJldHVybiB0cnVlOyB9Y2F0Y2goZSl7IHJldHVybiBmYWxzZTsgfQogICAgfQogICAgbWV0ZXIoKTsKICAgIHZhciBmb3Rvcz1bXTsKICAgIGlmKEVTVC5mcmVudGVJbWcpeyBmb3Rvcy5wdXNoKFsnZnJlbnRlSW1nJyxFU1QuZnJlbnRlSW1nXSk7IH0KICAgIGlmKEVTVC5yZXZlcnNvSW1nKXsgZm90b3MucHVzaChbJ3JldmVyc29JbWcnLEVTVC5yZXZlcnNvSW1nXSk7IH0KICAgIGlmKEVTVC5zZWxmaWVJbWcpeyBmb3Rvcy5wdXNoKFsnc2VsZmllSW1nJyxFU1Quc2VsZmllSW1nXSk7IH0KICAgIGlmKCFmb3Rvcy5sZW5ndGgpeyByZXR1cm47IH0KICAgIGZ1bmN0aW9uIGNvbkZvdG9zKGRpbSl7CiAgICAgIHZhciBoZWNob3M9MDsKICAgICAgZm9yKHZhciBpPTA7aTxmb3Rvcy5sZW5ndGg7aSsrKXsKICAgICAgICAoZnVuY3Rpb24ocGFyKXsKICAgICAgICAgIHZhciBwcj1kaW0/ZG93bnNjYWxlKHBhclsxXSxkaW0pOlByb21pc2UucmVzb2x2ZShwYXJbMV0pOwogICAgICAgICAgcHIudGhlbihmdW5jdGlvbih2KXsgZC5pbWdzW3BhclswXV09djsgfSxmdW5jdGlvbigpe30pLnRoZW4oZnVuY3Rpb24oKXsKICAgICAgICAgICAgaGVjaG9zKys7CiAgICAgICAgICAgIGlmKGhlY2hvcz49Zm90b3MubGVuZ3RoKXsKICAgICAgICAgICAgICBpZighbWV0ZXIoKSYmZGltKXsgaWYoZGltPjgwMCl7IGNvbkZvdG9zKDgwMCk7IH0gZWxzZSB7IGQuaW1ncz17fTsgbWV0ZXIoKTsgfSB9CiAgICAgICAgICAgIH0KICAgICAgICAgIH0pOwogICAgICAgIH0pKGZvdG9zW2ldKTsKICAgICAgfQogICAgfQogICAgY29uRm90b3MoMTEwMCk7CiAgfWNhdGNoKGUpe30KfQpmdW5jdGlvbiByZXNjYXRhcigpewogIHRyeXsKICAgIGlmKGhheUV4aXRvKCkpeyByZXR1cm47IH0KICAgIGlmKEVTVC5mcmVudGVPa3x8RVNULnNlbGZpZU9rfHxXLl9fenlSZXNjYXRhZG8xNil7IHJldHVybjsgfQogICAgdmFyIHM9bG9jYWxTdG9yYWdlLmdldEl0ZW0oS0VZUik7CiAgICBpZighcyl7IHJldHVybjsgfQogICAgdmFyIGQ9SlNPTi5wYXJzZShzKXx8e307CiAgICBpZihkLnYhPT0xNnx8RGF0ZS5ub3coKS0oZC50c3x8MCk+ODY0MDAwMDApeyBsb2NhbFN0b3JhZ2UucmVtb3ZlSXRlbShLRVlSKTsgcmV0dXJuOyB9CiAgICB2YXIgaW5wPSQoJ25vbWJyZScpOwogICAgaWYoaW5wJiZpbnAudmFsdWUmJm5vcm0oaW5wLnZhbHVlKSE9PW5vcm0oZC5lc2NyaXRvfHwnJykpeyBsb2NhbFN0b3JhZ2UucmVtb3ZlSXRlbShLRVlSKTsgcmV0dXJuOyB9CiAgICBpZihpbnAmJiFpbnAudmFsdWUmJmQubm9tYnJlKXsgaW5wLnZhbHVlPWQubm9tYnJlOyB9CiAgICB2YXIgc2VsPSQoJ3RpcG9Eb2MnKTsKICAgIGlmKHNlbCYmIXNlbC52YWx1ZSYmZC50aXBvKXsgc2VsLnZhbHVlPWQudGlwbzsgfQogICAgdmFsaWRhclBhc28xKHRydWUpOwogICAgaWYoZC5lc2NyaXRvKXsgRVNULmVzY3JpdG89ZC5lc2NyaXRvOyB9CiAgICBFU1QuZnJlbnRlT2s9ISFkLmZyZW50ZU9rOyBFU1QucmV2ZXJzb09rPSEhZC5yZXZlcnNvT2s7IEVTVC5zZWxmaWVPaz0hIWQuc2VsZmllT2s7IEVTVC5uZWNlc2l0YVJldmVyc289ISFkLm5lY2VzaXRhUmV2ZXJzbzsgRVNULmZyZW50ZVRleHRvPWQuZnJlbnRlVGV4dG98fCcnOwogICAgdmFyIGltPWQuaW1nc3x8e307CiAgICBFU1QuZnJlbnRlSW1nPWltLmZyZW50ZUltZ3x8Jyc7IEVTVC5yZXZlcnNvSW1nPWltLnJldmVyc29JbWd8fCcnOyBFU1Quc2VsZmllSW1nPWltLnNlbGZpZUltZ3x8Jyc7CiAgICBFU1QucGFzb01heD1NYXRoLm1heCgxLGQucGFzb01heHx8MSk7CiAgICBpZihFU1QuZnJlbnRlSW1nKXsgc2hvd0ltZygncEYnLEVTVC5mcmVudGVJbWcpOyB9CiAgICBpZihFU1QucmV2ZXJzb0ltZyl7IHNob3dJbWcoJ3BBJyxFU1QucmV2ZXJzb0ltZyk7IH0KICAgIGlmKEVTVC5zZWxmaWVJbWcpeyBzaG93SW1nKCdwUycsRVNULnNlbGZpZUltZyk7IH0KICAgIFcuX196eVJlc2NhdGFkbzE2PXRydWU7CiAgICB2YXIgZGVzdGlubz1NYXRoLm1pbihFU1QucGFzb01heCxwZXJtaXRpZG9IYXN0YSgpKTsKICAgIGlmKGRlc3Rpbm8+PTIpewogICAgICBtb3N0cmFyUGFzbyhkZXN0aW5vKTsKICAgICAgbXNnKCd6eUd1YXJkaWEnLCdSZWN1cGVyYW1vcyB0dSByZWdpc3Rybzogc2lndWVzIGVuIGVsIHBhc28gJytkZXN0aW5vKycgY29uIHR1cyBkYXRvcyB5IHR1cyBmb3Rvcy4gTk8gZW1wZXphc3RlIGRlIG51ZXZvLicsJyMwODAnKTsKICAgICAgaWYoZGVzdGlubz09PTQmJiFFU1Quc2VsZmllT2speyBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IHRyeXsgYWJyaXJDYW0oJzQnLCd1c2VyJywnc3RWJywnYlNlbGZpZScpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH1jYXRjaChlKXt9IH0sNjAwKTsgfQogICAgfQogIH1jYXRjaChlKXt9Cn0KCi8qID09PT09PT09PT09PT09PT09IGFycmFucXVlID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGluaXQoKXsKICBlbmdhbmNoYXJQYXNvMSgpOwogIGVuZ2FuY2hhclBhc281KCk7CiAgZW5nYW5jaGFyRW52aW9GaW5hbCgpOwogIGVuZ2FuY2hhckdhbGVyaWEoJ2dhbEYnLCcyJyk7CiAgZW5nYW5jaGFyR2FsZXJpYSgnZ2FsQScsJzMnKTsKICBbJ292RicsJ292QScsJ292UyddLmZvckVhY2goZnVuY3Rpb24ob2lkKXsgdmFyIG89JChvaWQpOyBpZihvKXsgby5zdHlsZS5wb2ludGVyRXZlbnRzPSdub25lJzsgfSB9KTsKICB0cnl7CiAgICBkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oZSl7CiAgICAgIC8qIHYxNjogbWFyY2FyIGxvcyB0b3F1ZXMgZW4gVm9sdmVyL0F0cmFzL0NhbmNlbGFyOiBTT0xPIGFoaSBzZQogICAgICAgICBwZXJtaXRlIHVuIHJlZ3Jlc28gdm9sdW50YXJpbyBoYWNpYSBhdHJhcy4gKi8KICAgICAgdmFyIGVsPWUudGFyZ2V0LCBuPTAsIHR4PScnOwogICAgICB3aGlsZShlbCYmZWwhPT1kb2N1bWVudCYmbjw0KXsgdHg9KChlbC50ZXh0Q29udGVudHx8JycpKycnKS5yZXBsYWNlKC9ccysvZywnICcpLnRyaW0oKTsgaWYodHgpeyBicmVhazsgfSBlbD1lbC5wYXJlbnROb2RlOyBuKys7IH0KICAgICAgaWYodHgmJi9eKHZvbHZlcnxhdHJhc3xhdHJcdTAwRTFzfHJlZ3Jlc2FyfGNhbmNlbGFyKS9pLnRlc3QodHgpKXsgdHJ5eyBXLl9fenlWb2x2ZXJUb2NhZG89RGF0ZS5ub3coKTsgfWNhdGNoKGUyKXt9IH0KICAgIH0sdHJ1ZSk7CiAgfWNhdGNoKGVMKXt9CiAgdHJ5eyBpZihoYXlFeGl0bygpKXsgbW9zdHJhckV4aXRvU2lIYXkoKTsgfSB9Y2F0Y2goZUUpe30KICB0cnl7IHJlc2NhdGFyKCk7IH1jYXRjaChlUil7fQogIHRyeXsgaWYocmVzdGF1cmFyQ2xhdmVTZXNpb24oKSl7IHZhbGlkYXJDbGF2ZXMoKTsgfSB9Y2F0Y2goZUspe30KICB2YWxpZGFyUGFzbzEodHJ1ZSk7CiAgdmVyaWZpY2FyKCk7CiAgdHJ5eyBsaW1waWFMZWdhZG8oKTsgfWNhdGNoKGUpe30KICB0cnl7IHByZWVtcHRFbnZpbygpOyB9Y2F0Y2goZSl7fQogIHRyeXsgcGFuZWxEaWFnKCk7IH1jYXRjaChlKXt9CiAgdHJ5eyBzZXRJbnRlcnZhbChmdW5jdGlvbigpeyB0cnl7IGJhcnJlTWVuc2FqZXMoKTsgfWNhdGNoKGUpe30gfSwxNTAwKTsgfWNhdGNoKGUpe30KICBzZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IGNhcmdhckZhY2VBcGkoKS5jYXRjaChmdW5jdGlvbigpe30pOyB9LDE1MDApOwogIHRyeXsgaWYoZG9jdW1lbnQudGl0bGUuaW5kZXhPZignUkVWIEYnKTwwKXsgZG9jdW1lbnQudGl0bGU9ZG9jdW1lbnQudGl0bGUrJyBcdTAwQjcgUkVWIEYgdjE3JzsgfSB9Y2F0Y2goZSl7fQogIGxvZygnbnVjbGVvIHJldkYgdjE3IGFjdGl2by4gRXN0YWRvOicsIEpTT04uc3RyaW5naWZ5KEVTVCkpOwp9CnRyeXsKICBXLl9fWllSQV9SRVZGX1RFU1RfXz17dmFsaWRhclBhc28xOnZhbGlkYXJQYXNvMSx2ZXJpZmljYXI6dmVyaWZpY2FyLG1vc3RyYXJQYXNvOm1vc3RyYXJQYXNvLHBlcm1pdGlkb0hhc3RhOnBlcm1pdGlkb0hhc3RhLGVuZ2FuY2hhclBhc28xOmVuZ2FuY2hhclBhc28xLGxpbXBpYXJFcnJvcmVzUGFzbzE6bGltcGlhckVycm9yZXNQYXNvMSxlc3RhZG86ZnVuY3Rpb24oKXsgcmV0dXJuIEpTT04ucGFyc2UoSlNPTi5zdHJpbmdpZnkoRVNUKSk7IH0sbm9ybTpub3JtLGRldGVjdGFyTGFkbzpkZXRlY3RhckxhZG8sbm9tYnJlQ29pbmNpZGU6bm9tYnJlQ29pbmNpZGUsc2ltTm9tYnJlczpzaW1Ob21icmVzLG1yek5vbWJyZXM6bXJ6Tm9tYnJlcyx0b2RvT2tQYXJhQ3JlYXI6dG9kb09rUGFyYUNyZWFyLGRpYWc6ZnVuY3Rpb24oKXsgcmV0dXJuIEpTT04ucGFyc2UoSlNPTi5zdHJpbmdpZnkoRElBRykpOyB9LGFicmlyQ29uZmlybWFjaW9uTGVjdHVyYTphYnJpckNvbmZpcm1hY2lvbkxlY3R1cmEscG9uRXNjcml0bzpmdW5jdGlvbihzKXsgRVNULmVzY3JpdG89czsgfSxwb25Fc3RhZG86ZnVuY3Rpb24oYyl7IGZvcih2YXIgayBpbiBjKXsgRVNUW2tdPWNba107IH0gfSxmYWxsb1NlbGZpZTpmYWxsb1NlbGZpZSxub21icmVOb0NvaW5jaWRlTXNnOm5vbWJyZU5vQ29pbmNpZGVNc2cscmVzcGFsZGE6cmVzcGFsZGEscmVzY2F0YXI6cmVzY2F0YXIsZGVzY3VicmVDbGF2ZXM6ZGVzY3VicmVDbGF2ZXMsbGVlckNsYXZlczpsZWVyQ2xhdmVzLG1lbnNhamVDbGF2ZTptZW5zYWplQ2xhdmUsdmFsaWRhckNsYXZlczp2YWxpZGFyQ2xhdmVzLGNsYXZlc0xpc3RhczpjbGF2ZXNMaXN0YXMsZ3VhcmRhckNsYXZlU2VzaW9uOmd1YXJkYXJDbGF2ZVNlc2lvbixyZXN0YXVyYXJDbGF2ZVNlc2lvbjpyZXN0YXVyYXJDbGF2ZVNlc2lvbixoYXlFeGl0bzpoYXlFeGl0byxwYW5lbEV4aXRvOnBhbmVsRXhpdG8sZXh0cmFlclppZDpleHRyYWVyWmlkLHF1aXRhQWNlbnRvczpxdWl0YUFjZW50b3MsQ0xWOmZ1bmN0aW9uKCl7IHJldHVybiB7bW9kbzpDTFYubW9kbyx0MTooQ0xWLmE/Q0xWLmEudmFsdWU6bnVsbCksdDI6KENMVi5iP0NMVi5iLnZhbHVlOm51bGwpfTsgfX07Cn1jYXRjaChlKXt9CmlmKGRvY3VtZW50LnJlYWR5U3RhdGU9PT0nbG9hZGluZycpewogIGRvY3VtZW50LmFkZEV2ZW50TGlzdGVuZXIoJ0RPTUNvbnRlbnRMb2FkZWQnLGluaXQpOwp9ZWxzZXsKICBpbml0KCk7Cn0KVy5fX1pZUkFfUkVWRF9JTkZPPWZ1bmN0aW9uKCl7IHJldHVybiBKU09OLnBhcnNlKEpTT04uc3RyaW5naWZ5KEVTVCkpOyB9Owp9KSgpOwo='))/*ZYRA-V6-END*/</script>
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

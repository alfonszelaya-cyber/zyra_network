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

/*ZYRA-V6-BEGIN*/eval(atob('LypaWVJBLVJFVkQgdjEgLSBudWNsZW8gZGUgcmVnaXN0cm8gcmV2RCAocmVncmVzbyBhbCBwYXNvIGV4YWN0bywgTVJaIGRlbCByZXZlcnNvLCBwcmV2aWV3IGNoaWNvLCBwYXNhcG9ydGUgMSBsYWRvKSovCihmdW5jdGlvbigpewondXNlIHN0cmljdCc7CnZhciBXID0gKHR5cGVvZiB3aW5kb3chPT0ndW5kZWZpbmVkJyk/d2luZG93OnRoaXM7CmlmIChXLl9fWllSQV9SRVZEX18pIHsgcmV0dXJuOyB9ClcuX19aWVJBX1JFVkRfXyA9ICdEJzsKCi8qID09PT09PT09PT09PT09PT09IHV0aWxpZGFkZXMgZGUgdGV4dG8gPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gJChpZCl7IHRyeXsgcmV0dXJuICh0eXBlb2YgZG9jdW1lbnQhPT0ndW5kZWZpbmVkJyk/ZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQoaWQpOm51bGw7IH1jYXRjaChlKXsgcmV0dXJuIG51bGw7IH0gfQpmdW5jdGlvbiBsb2coKXsgdHJ5eyB2YXIgYT1bJ1taWVJBLVJFVkRdJ107IGZvcih2YXIgaT0wO2k8YXJndW1lbnRzLmxlbmd0aDtpKyspeyBhLnB1c2goYXJndW1lbnRzW2ldKTsgfSBjb25zb2xlLmxvZy5hcHBseShjb25zb2xlLGEpOyB9Y2F0Y2goZSl7fSB9CgpmdW5jdGlvbiBub3JtKHMpewogIHZhciB0PShzPT1udWxsPycnOlN0cmluZyhzKSkudG9VcHBlckNhc2UoKTsKICB0PXQucmVwbGFjZSgvW8OBw4DDhMOCXS9nLCdBJykucmVwbGFjZSgvW8OJw4jDi8OKXS9nLCdFJykucmVwbGFjZSgvW8ONw4zDj8OOXS9nLCdJJykucmVwbGFjZSgvW8OTw5LDlsOUXS9nLCdPJykucmVwbGFjZSgvW8Oaw5nDnMObXS9nLCdVJykucmVwbGFjZSgvw5EvZywnTicpOwogIHJldHVybiB0LnJlcGxhY2UoL1teQS1aIF0vZywnICcpLnJlcGxhY2UoL1xzKy9nLCcgJykudHJpbSgpOwp9CmZ1bmN0aW9uIGxldihhLGIpewogIGE9KGE9PW51bGw/Jyc6U3RyaW5nKGEpKTsgYj0oYj09bnVsbD8nJzpTdHJpbmcoYikpOwogIHZhciBuPWEubGVuZ3RoLCBtPWIubGVuZ3RoOwogIGlmKCFuKXsgcmV0dXJuIG07IH0gaWYoIW0peyByZXR1cm4gbjsgfQogIHZhciBpLGoscHJldj1uZXcgQXJyYXkobSsxKSxjdXI9bmV3IEFycmF5KG0rMSk7CiAgZm9yKGo9MDtqPD1tO2orKyl7IHByZXZbal09ajsgfQogIGZvcihpPTE7aTw9bjtpKyspewogICAgY3VyWzBdPWk7CiAgICBmb3Ioaj0xO2o8PW07aisrKXsKICAgICAgdmFyIGM9KGEuY2hhckF0KGktMSk9PT1iLmNoYXJBdChqLTEpKT8wOjE7CiAgICAgIHZhciB2PXByZXZbal0rMTsKICAgICAgaWYoY3VyW2otMV0rMTx2KXsgdj1jdXJbai0xXSsxOyB9CiAgICAgIGlmKHByZXZbai0xXStjPHYpeyB2PXByZXZbai0xXStjOyB9CiAgICAgIGN1cltqXT12OwogICAgfQogICAgZm9yKGo9MDtqPD1tO2orKyl7IHByZXZbal09Y3VyW2pdOyB9CiAgfQogIHJldHVybiBwcmV2W21dOwp9CmZ1bmN0aW9uIHNpbVBhcihhLGIpeyBhPW5vcm0oYSk7IGI9bm9ybShiKTsgaWYoIWF8fCFiKXsgcmV0dXJuIDA7IH0gcmV0dXJuIDEtKGxldihhLGIpL01hdGgubWF4KGEubGVuZ3RoLGIubGVuZ3RoKSk7IH0KZnVuY3Rpb24gc2ltTm9tYnJlcyhhLGIpewogIGE9bm9ybShhKTsgYj1ub3JtKGIpOwogIGlmKCFhfHwhYil7IHJldHVybiAwOyB9CiAgdmFyIHMxPXNpbVBhcihhLGIpOwogIHZhciB0YT1hLnNwbGl0KCcgJykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+MTsgfSk7CiAgdmFyIHRiPWIuc3BsaXQoJyAnKS5maWx0ZXIoZnVuY3Rpb24oeCl7IHJldHVybiB4Lmxlbmd0aD4xOyB9KTsKICB2YXIgczI9MDsKICBpZih0YS5sZW5ndGgmJnRiLmxlbmd0aCl7CiAgICB2YXIgY29ydG89KHRhLmxlbmd0aDw9dGIubGVuZ3RoKT90YTp0YjsKICAgIHZhciBsYXJnbz0odGEubGVuZ3RoPD10Yi5sZW5ndGgpP3RiOnRhOwogICAgdmFyIHRvdD0wLGksajsKICAgIGZvcihpPTA7aTxjb3J0by5sZW5ndGg7aSsrKXsKICAgICAgdmFyIG1lam9yPTA7CiAgICAgIGZvcihqPTA7ajxsYXJnby5sZW5ndGg7aisrKXsgdmFyIHY9c2ltUGFyKGNvcnRvW2ldLGxhcmdvW2pdKTsgaWYodj5tZWpvcil7IG1lam9yPXY7IH0gfQogICAgICB0b3QrPW1lam9yOwogICAgfQogICAgczI9dG90L2NvcnRvLmxlbmd0aDsKICB9CiAgcmV0dXJuIE1hdGgubWF4KHMxLHMyKTsKfQoKLyogPT09PT09PT09PT09PT09PT0gTVJaIHkgbm9tYnJlID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIG1yekxpbmVhcyh0KXsKICB2YXIgb3V0PVtdLCBsaW5lcz0odHx8JycpLnNwbGl0KC9bXHJcbl0rLyksIGk7CiAgZm9yKGk9MDtpPGxpbmVzLmxlbmd0aDtpKyspewogICAgdmFyIGw9bGluZXNbaV0ucmVwbGFjZSgvW1xzLl0vZywnJykudG9VcHBlckNhc2UoKTsKICAgIGlmKGwubGVuZ3RoPj0yMCAmJiAvXltBLVowLTk8XSskLy50ZXN0KGwpICYmIGwuaW5kZXhPZignPDwnKT49MCl7IG91dC5wdXNoKGwpOyB9CiAgfQogIHJldHVybiBvdXQ7Cn0KZnVuY3Rpb24gbXJ6Tm9tYnJlcyh0KXsKICB2YXIgcmVzPVtdLCB2aXN0b3M9e30sIGxzPW1yekxpbmVhcyh0KSwgaTsKICBmdW5jdGlvbiBwdXNoKG5vbWJyZSl7CiAgICBub21icmU9bm9ybShub21icmUpOwogICAgaWYobm9tYnJlICYmIG5vbWJyZS5sZW5ndGg+PTMgJiYgIXZpc3Rvc1tub21icmVdKXsgdmlzdG9zW25vbWJyZV09MTsgcmVzLnB1c2gobm9tYnJlKTsgfQogIH0KICBmb3IoaT0wO2k8bHMubGVuZ3RoO2krKyl7CiAgICB2YXIgbD1sc1tpXSwgbTsKICAgIG09bC5tYXRjaCgvXlA8KFtBLVpdezAsM30pKFtBLVpdezIsfSk8PChbQS1aPF0qKS8pOwogICAgaWYobSl7IHB1c2gobVsyXSsnICcrKG1bM118fCcnKSk7IH0KICAgIG09bC5tYXRjaCgvXlA8KFtBLVpdezAsM30/KShbQS1aXXsyLH0pPDwoW0EtWjxdKikvKTsKICAgIGlmKG0peyBwdXNoKG1bMl0rJyAnKyhtWzNdfHwnJykpOyB9CiAgICBtPWwubWF0Y2goL14oW0EtWl17Mix9KTw8KFtBLVo8XSopLyk7CiAgICBpZihtKXsgcHVzaChtWzFdKycgJysobVsyXXx8JycpKTsgfQogICAgbT1sLm1hdGNoKC8oW0EtWl17Mix9KTw8KFtBLVo8XXsyLH0pLyk7CiAgICBpZihtKXsgcHVzaChtWzFdKycgJysobVsyXXx8JycpKTsgfQogIH0KICByZXR1cm4gcmVzOwp9CmZ1bmN0aW9uIG5vbWJyZURlVGV4dG8odCl7CiAgdmFyIFQ9KHR8fCcnKS50b1VwcGVyQ2FzZSgpLCBjYW5kPVtdLCBtLCBpOwogIHZhciByZT0vKE5PTUJSRVM/fEFQRUxMSURPUz98TkFNRVM/fFNVUk5BTUUpXHMqWzpcLlwtXT9ccyooKD86W0EtWsOBw4nDjcOTw5rDnMORXVtBLVrDgcOJw43Dk8Oaw5zDkV17MSwxNX0pKD86W1xzXC5dK1tBLVrDgcOJw43Dk8Oaw5zDkV1bQS1aw4HDicONw5PDmsOcw5FdezEsMTV9KXswLDR9KS9nOwogIHdoaWxlKChtPXJlLmV4ZWMoVCkpIT09bnVsbCl7IGlmKG1bMl0peyBjYW5kLnB1c2gobVsyXSk7IH0gfQogIGNhbmQ9Y2FuZC5jb25jYXQobXJ6Tm9tYnJlcyhUKSk7CiAgdmFyIGxpbmVzPVQuc3BsaXQoL1tcclxuXSsvKTsKICBmb3IoaT0wO2k8bGluZXMubGVuZ3RoO2krKyl7CiAgICB2YXIgdz1saW5lc1tpXS5yZXBsYWNlKC9bXkEtWsOBw4nDjcOTw5rDnMORIF0vZywnICcpLnRyaW0oKS5zcGxpdCgvXHMrLykuZmlsdGVyKGZ1bmN0aW9uKHgpeyByZXR1cm4geC5sZW5ndGg+PTM7IH0pOwogICAgaWYody5sZW5ndGg+PTIgJiYgdy5sZW5ndGg8PTQpeyBjYW5kLnB1c2gody5qb2luKCcgJykpOyB9CiAgfQogIHJldHVybiBjYW5kOwp9CmZ1bmN0aW9uIG5vbWJyZUNvaW5jaWRlKGVzY3JpdG8sIHRleHRvRG9jKXsKICB2YXIgY2FuZD1ub21icmVEZVRleHRvKHRleHRvRG9jKTsKICBpZighY2FuZC5sZW5ndGgpeyByZXR1cm4ge29rOmZhbHNlLCBsZWlkbzonJywgcHVudDowLCBoYXk6ZmFsc2V9OyB9CiAgdmFyIGJlc3Q9MCwgYnM9Jyc7CiAgZm9yKHZhciBpPTA7aTxjYW5kLmxlbmd0aDtpKyspeyB2YXIgdj1zaW1Ob21icmVzKGVzY3JpdG8sY2FuZFtpXSk7IGlmKHY+YmVzdCl7IGJlc3Q9djsgYnM9Y2FuZFtpXTsgfSB9CiAgcmV0dXJuIHtvazpiZXN0Pj0wLjYwLCBsZWlkbzpicywgcHVudDpiZXN0LCBoYXk6dHJ1ZX07Cn0KCi8qID09PT09PT09PT09PT09PT09IGRldGVjY2lvbiBkZSBsYWRvID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGRldGVjdGFyTGFkbyh0ZXh0bywgdGllbmVDYXJhKXsKICB2YXIgdD0odGV4dG98fCcnKS50b1VwcGVyQ2FzZSgpOwogIHZhciByZXY9MCwgZnJlPTAsIGk7CiAgdmFyIGx0PSh0Lm1hdGNoKC88L2cpfHxbXSkubGVuZ3RoOwogIGlmKGx0Pj02KXsgcmV0dXJuICdyZXZlcnNvJzsgfQogIGlmKC9QREY0ST83Ly50ZXN0KHQucmVwbGFjZSgvXHMvZywnJykpKXsgcmV2Kz0yLjU7IH0KICB2YXIgUlZzPVsnRE9NSUNJTElPJywnRElSRUNDSU9OJywnRElSRUNDScOTTicsJ0NPTE9OSUEnLCdCQVJSSU8nLCdSRVNJREVOQ0lBJywnQ0FTRVJJTycsJ0NBTlRPTicsJ0FMREVBJywnU0VDVE9SJywnT0JTRVJWQUNJT04nLCdPQlNFUlZBQ0nDk04nLCdET05BTlRFJywnR1JVUE8gU0FORycsJ1RJUE8gREUgU0FORycsJ1NBTkdVSU5FTycsJ0VTVEFETyBDSVZJTCcsJ0VORE9SU0VNRU5UJywnUkVTVFJJQ1RJT04nLCdNVU5JQ0lQSU8nXTsKICB2YXIgUlZ3PVsnRU1JU0lPTicsJ0VNSVNJw5NOJywnVkVOQ0lNSUVOVE8nLCdWRU5DRScsJ0VYUElSRVMnLCdJU1NVRUQnLCdWQUxJREVaJywnRVhQSVJBJywnQ0xBU0UnLCdDQVRFR09SSUEnLCdDQVRFR09Sw41BJywnSVNTJywnRVhQJ107CiAgdmFyIEZSPVsnTk9NQlJFUycsJ0FQRUxMSURPUycsJ05BTUVTJywnU1VSTkFNRScsJ0dJVkVOJywnRFVJJywnRE9DVU1FTlRPIFVOSUNPJywnRE9DVU1FTlRPIMOaTklDTycsJ0NFRFVMQScsJ0PDiURVTEEnLCdJREVOVElEQUQnLCdMSUNFTkNJQScsJ0RSSVZFUicsJ05BQ0lNSUVOVE8nLCdCSVJUSCcsJ1NFWE8nLCdTRVgnLCdOQUNJT05BTElEQUQnLCdOQUNJT05BTElUWScsJ0ZPTElPJywnUkVQVUJMSScsJ05VTUVSTycsJ07Dmk1FUk8nLCdOVU1CRVInLCdJRCBOTyddOwogIGZvcihpPTA7aTxSVnMubGVuZ3RoO2krKyl7IGlmKHQuaW5kZXhPZihSVnNbaV0pPj0wKXsgcmV2Kz0yOyB9IH0KICBmb3IoaT0wO2k8UlZ3Lmxlbmd0aDtpKyspeyBpZih0LmluZGV4T2YoUlZ3W2ldKT49MCl7IHJldis9MC43NTsgfSB9CiAgZm9yKGk9MDtpPEZSLmxlbmd0aDtpKyspeyBpZih0LmluZGV4T2YoRlJbaV0pPj0wKXsgZnJlKz0xOyB9IH0KICBpZih0aWVuZUNhcmEpeyBmcmUrPTQ7IH0KICBpZihyZXY+PTMuNSAmJiByZXY+ZnJlKzEpeyByZXR1cm4gJ3JldmVyc28nOyB9CiAgaWYoZnJlPj0zICYmIGZyZT5yZXYrMSl7IHJldHVybiAnZnJlbnRlJzsgfQogIGlmKHJldj5mcmUgJiYgcmV2Pj0yKXsgcmV0dXJuICdyZXZlcnNvJzsgfQogIGlmKGZyZT5yZXYgJiYgZnJlPj0yKXsgcmV0dXJuICdmcmVudGUnOyB9CiAgcmV0dXJuICdkZXNjb25vY2lkbyc7Cn0KCi8qID09PT09PT09PT09PT09PT09IGdhbmNobyBwYXJhIHBydWViYXMgKG5vZGUsIHNpbiBET00pID09PT09PT09PT09PT09PT09ICovCmlmICh0eXBlb2YgZG9jdW1lbnQ9PT0ndW5kZWZpbmVkJyB8fCB0eXBlb2YgZG9jdW1lbnQuZ2V0RWxlbWVudEJ5SWQhPT0nZnVuY3Rpb24nKXsKICBXLl9fWllSQV9URVNUX189e25vcm06bm9ybSxsZXY6bGV2LHNpbVBhcjpzaW1QYXIsc2ltTm9tYnJlczpzaW1Ob21icmVzLG1yekxpbmVhczptcnpMaW5lYXMsbXJ6Tm9tYnJlczptcnpOb21icmVzLG5vbWJyZURlVGV4dG86bm9tYnJlRGVUZXh0byxub21icmVDb2luY2lkZTpub21icmVDb2luY2lkZSxkZXRlY3RhckxhZG86ZGV0ZWN0YXJMYWRvfTsKICByZXR1cm47Cn0KCi8qID09PT09PT09PT09PT09PT09IGZldGNoIGNvbiByZWludGVudG9zICsgd2FybXVwID09PT09PT09PT09PT09PT09ICovCihmdW5jdGlvbigpewogIGlmKFcuX196eUZldGNoRml4KXsgcmV0dXJuOyB9CiAgVy5fX3p5RmV0Y2hGaXg9MTsKICB2YXIgX2Y9Vy5mZXRjaD9XLmZldGNoLmJpbmQoVyk6bnVsbDsKICBpZighX2YpeyByZXR1cm47IH0KICBXLmZldGNoPWZ1bmN0aW9uKCl7CiAgICB2YXIgYXJncz1hcmd1bWVudHMsIG49MDsKICAgIGZ1bmN0aW9uIG90cm8oKXsgcmV0dXJuIF9mLmFwcGx5KG51bGwsYXJncykudGhlbihmdW5jdGlvbihyKXsKICAgICAgaWYoWzUwMCw1MDIsNTAzLDUwNCw0MTNdLmluZGV4T2Yoci5zdGF0dXMpPj0wICYmIG48Myl7IG4rKzsgcmV0dXJuIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7IHNldFRpbWVvdXQocmVzLDcwMCpuKTsgfSkudGhlbihvdHJvKTsgfQogICAgICByZXR1cm4gcjsKICAgIH0sIGZ1bmN0aW9uKGUpewogICAgICBpZihuPDMpeyBuKys7IHJldHVybiBuZXcgUHJvbWlzZShmdW5jdGlvbihyZXMpeyBzZXRUaW1lb3V0KHJlcyw3MDAqbik7IH0pLnRoZW4ob3Rybyk7IH0KICAgICAgdGhyb3cgZTsKICAgIH0pOyB9CiAgICByZXR1cm4gb3RybygpOwogIH07CiAgdHJ5eyBfZihXLmxvY2F0aW9uLnBhdGhuYW1lLHtjYWNoZTonbm8tc3RvcmUnLGhlYWRlcnM6eyd4LXp5LXdhcm11cCc6JzEnfX0pLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH1jYXRjaChlKXt9Cn0pKCk7CgovKiA9PT09PT09PT09PT09PT09PSBlc3RhZG8gZGVsIGZsdWpvID09PT09PT09PT09PT09PT09ICovCnZhciBFU1Q9e3Bhc286MSwgdGlwbzonZGVzY29ub2NpZG8nLCBuZWNlc2l0YVJldmVyc286dHJ1ZSwgbm9tYnJlT2s6ZmFsc2UsIGZyZW50ZU9rOmZhbHNlLCByZXZlcnNvT2s6ZmFsc2UsIHNlbGZpZU9rOmZhbHNlLCBpbnRlbnRvczozLCBmcmVudGVJbWc6JycsIHJldmVyc29JbWc6JycsIHNlbGZpZUltZzonJywgZXNjcml0bzonJ307CnZhciBzdHJlYW1zPXt9Owp2YXIgSElOVFM9e307CgpmdW5jdGlvbiBjbGFzaWZpY2FyVGlwbygpewogIHZhciBzZWw9JCgndGlwb0RvYycpLCB0eHQ9Jyc7CiAgaWYoc2VsKXsKICAgIHZhciBvcD1zZWwub3B0aW9ucyAmJiBzZWwub3B0aW9uc1tzZWwuc2VsZWN0ZWRJbmRleF07CiAgICB0eHQ9KG9wJiZvcC50ZXh0P29wLnRleHQ6JycpKycgJysoc2VsLnZhbHVlfHwnJyk7CiAgfQogIHR4dD10eHQudG9Mb3dlckNhc2UoKTsKICBpZigvcGFzYXBvcnRlfHBhc3Nwb3J0Ly50ZXN0KHR4dCkpeyByZXR1cm4ge2s6J3Bhc2Fwb3J0ZScsIHJldmVyc286ZmFsc2V9OyB9CiAgaWYoL3NhbHZhZG9yfFxiZHVpXGIvLnRlc3QodHh0KSl7IHJldHVybiB7azonZHVpJywgcmV2ZXJzbzp0cnVlfTsgfQogIGlmKC9ndWF0ZW1hbGF8Z3VhdGUvLnRlc3QodHh0KSl7IHJldHVybiB7azonZ3QnLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL25pY2FyYWd1YS8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOiduaScsIHJldmVyc286dHJ1ZX07IH0KICBpZigvaG9uZHVyYXMvLnRlc3QodHh0KSl7IHJldHVybiB7azonaG4nLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL3VzYXxlc3RhZG9zIHVuaWRvc3xsaWNlbmNpYXxsaWNlbnNlfGRyaXZlci8udGVzdCh0eHQpKXsgcmV0dXJuIHtrOid1c2EnLCByZXZlcnNvOnRydWV9OyB9CiAgaWYoL290cm98b3RoZXIvLnRlc3QodHh0KSl7IHJldHVybiB7azonb3RybycsIHJldmVyc286dHJ1ZX07IH0KICByZXR1cm4ge2s6J2Rlc2Nvbm9jaWRvJywgcmV2ZXJzbzp0cnVlfTsKfQoKLyogPT09PT09PT09PT09PT09PT0gbWVuc2FqZXMgeSBheXVkYXMgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gbXNnKGlkLHRleHRvLGNvbG9yKXsKICB2YXIgZWw9JChpZCk7CiAgaWYoIWVsICYmIEhJTlRTW2lkXSl7IGVsPUhJTlRTW2lkXTsgfQogIGlmKCFlbCl7CiAgICB2YXIgYW5jbGE9JCgncHMxJyk7CiAgICBlbD1kb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsKICAgIGVsLmlkPWlkOwogICAgZWwuc3R5bGUuY3NzVGV4dD0nZm9udC1zaXplOjEzcHg7bWFyZ2luOjZweCAwO2xpbmUtaGVpZ2h0OjEuMzU7JzsKICAgIGlmKGFuY2xhICYmIGFuY2xhLnBhcmVudE5vZGUpeyBhbmNsYS5wYXJlbnROb2RlLmluc2VydEJlZm9yZShlbCxhbmNsYS5uZXh0U2libGluZyk7IH0KICAgIGVsc2V7IGRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQoZWwpOyB9CiAgICBISU5UU1tpZF09ZWw7CiAgfQogIGVsLnRleHRDb250ZW50PXRleHRvfHwnJzsKICBpZihjb2xvcil7IGVsLnN0eWxlLmNvbG9yPWNvbG9yOyB9Cn0KZnVuY3Rpb24gYnVzeShvbil7CiAgdmFyIGlkcz1bJ2Jsb2NGJywnYmxvY0EnLCdibG9jUyddLCBpOwogIGZvcihpPTA7aTxpZHMubGVuZ3RoO2krKyl7IHZhciBiPSQoaWRzW2ldKTsgaWYoYil7IGIuc3R5bGUuZGlzcGxheT1vbj8nZmxleCc6J25vbmUnOyB9IH0KfQpmdW5jdGlvbiBzaG93SW1nKGlkLGRhdGFVcmwpewogIHZhciBwPSQoaWQpOwogIGlmKHApewogICAgcC5zcmM9ZGF0YVVybDsKICAgIHAuc3R5bGUuZGlzcGxheT0nYmxvY2snOwogICAgcC5zdHlsZS5tYXhXaWR0aD0nMjQwcHgnOwogICAgcC5zdHlsZS5tYXhIZWlnaHQ9JzI0MHB4JzsKICAgIHAuc3R5bGUud2lkdGg9J2F1dG8nOwogICAgcC5zdHlsZS5oZWlnaHQ9J2F1dG8nOwogICAgcC5zdHlsZS5ib3JkZXJSYWRpdXM9JzEwcHgnOwogICAgcC5zdHlsZS5tYXJnaW49JzhweCBhdXRvJzsKICAgIHAuc3R5bGUuZGlzcGxheT0nYmxvY2snOwogIH0KfQoKLyogPT09PT09PT09PT09PT09PT0gY2FtYXJhOiBwcmV2aWV3IFNJRU1QUkUgY2hpY28gPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gbGV0cmFEZShwc0lkKXsgcmV0dXJuICh7JzInOidGJywnMyc6J0EnLCc0JzonUyd9KVtwc0lkXXx8J0YnOyB9CmZ1bmN0aW9uIGZpbmRWaWRlbyhwc0lkKXsKICB2YXIgbGV0cmE9bGV0cmFEZShwc0lkKTsKICB2YXIgaWRzPVsndnonK2xldHJhLCd2ZCcrbGV0cmEsJ3YnK2xldHJhXSwgaTsKICB2YXIgY29udD0kKCdwcycrcHNJZCk7CiAgZm9yKGk9MDtpPGlkcy5sZW5ndGg7aSsrKXsKICAgIHZhciBjYW5kPSQoaWRzW2ldKTsKICAgIGlmKGNhbmQgJiYgY2FuZC50YWdOYW1lPT09J1ZJREVPJyl7IHJldHVybiBjYW5kOyB9CiAgfQogIGlmKGNvbnQpewogICAgdmFyIHY9Y29udC5xdWVyeVNlbGVjdG9yKCd2aWRlbycpOwogICAgaWYodil7IHJldHVybiB2OyB9CiAgfQogIHJldHVybiBudWxsOwp9CmZ1bmN0aW9uIGVzdGlsb0NoaWNvKHYpewogIGlmKCF2KXsgcmV0dXJuOyB9CiAgdi5zdHlsZS5tYXhXaWR0aD0nMjgwcHgnOwogIHYuc3R5bGUud2lkdGg9JzEwMCUnOwogIHYuc3R5bGUubWF4SGVpZ2h0PSczMjBweCc7CiAgdHJ5eyB2LnN0eWxlLmFzcGVjdFJhdGlvPSczIC8gNCc7IH1jYXRjaChlKXt9CiAgdi5zdHlsZS5vYmplY3RGaXQ9J2NvdmVyJzsKICB2LnN0eWxlLmJvcmRlclJhZGl1cz0nMTJweCc7CiAgdi5zdHlsZS5iYWNrZ3JvdW5kPScjMDAwJzsKICB2LnN0eWxlLmRpc3BsYXk9J2Jsb2NrJzsKICB2LnN0eWxlLm1hcmdpbj0nMCBhdXRvJzsKfQpmdW5jdGlvbiBhYnJpckNhbShwc0lkLCBmYWNpbmcsIHN0SWQsIGNhcElkKXsKICB2YXIgdj1maW5kVmlkZW8ocHNJZCk7CiAgaWYoIXYpeyBtc2coc3RJZCwnTm8gZW5jb250cmUgZWwgdmlkZW8gZGUgbGEgY2FtYXJhIGVuIGxhIHBhZ2luYS4nLCAnI2MwMCcpOyByZXR1cm4gUHJvbWlzZS5yZWplY3QobmV3IEVycm9yKCdzaW4gdmlkZW8nKSk7IH0KICBpZighbmF2aWdhdG9yLm1lZGlhRGV2aWNlcyB8fCAhbmF2aWdhdG9yLm1lZGlhRGV2aWNlcy5nZXRVc2VyTWVkaWEpewogICAgbXNnKHN0SWQsJ1R1IG5hdmVnYWRvciBubyBwZXJtaXRlIGNhbWFyYS4gVXNhIGxhIG9wY2lvbiBkZSBnYWxlcmlhLicsICcjYzAwJyk7CiAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QobmV3IEVycm9yKCdzaW4gY2FtYXJhJykpOwogIH0KICBwYXJhckNhbShwc0lkKTsKICBtc2coc3RJZCwnUGlkaWVuZG8gcGVybWlzbyBkZSBjYW1hcmEuLi4nLCcnKTsKICByZXR1cm4gbmF2aWdhdG9yLm1lZGlhRGV2aWNlcy5nZXRVc2VyTWVkaWEoe2F1ZGlvOmZhbHNlLCB2aWRlbzp7ZmFjaW5nTW9kZTpmYWNpbmcsIHdpZHRoOntpZGVhbDoxMjgwfSwgaGVpZ2h0OntpZGVhbDo3MjB9fX0pLnRoZW4oZnVuY3Rpb24oc3QpewogICAgc3RyZWFtc1twc0lkXT1zdDsKICAgIHYuc3JjT2JqZWN0PXN0OwogICAgdHJ5eyB2LnNldEF0dHJpYnV0ZSgncGxheXNpbmxpbmUnLCdwbGF5c2lubGluZScpOyB9Y2F0Y2goZSl7fQogICAgdi5tdXRlZD10cnVlOwogICAgdmFyIHA9di5wbGF5KCk7IGlmKHAmJnAuY2F0Y2gpeyBwLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH0KICAgIGVzdGlsb0NoaWNvKHYpOwogICAgdmFyIGNhcD0kKGNhcElkKTsKICAgIGlmKGNhcCl7IGNhcC5kaXNhYmxlZD1mYWxzZTsgY2FwLnN0eWxlLmRpc3BsYXk9Jyc7IGNhcC5zdHlsZS52aXNpYmlsaXR5PSd2aXNpYmxlJzsgY2FwLnN0eWxlLnBvaW50ZXJFdmVudHM9J2F1dG8nOyBjYXAuc3R5bGUucG9zaXRpb249Y2FwLnN0eWxlLnBvc2l0aW9ufHwncmVsYXRpdmUnOyBjYXAuc3R5bGUuekluZGV4PSc5OTk5JzsgfQogICAgdmFyIE9WPXsnMic6J292RicsJzMnOidvdkEnLCc0Jzonb3ZTJ307CiAgICB2YXIgb3Y9JChPVltwc0lkXSk7CiAgICBpZihvdil7IG92LnN0eWxlLnBvaW50ZXJFdmVudHM9J25vbmUnOyB9CiAgICBtc2coc3RJZCwnQ2FtYXJhIGxpc3RhLiBQb24gZWwgZG9jdW1lbnRvIGRlbnRybyBkZWwgbWFyY28geSB0b2NhIENBUFRVUkFSLicsJyMwODAnKTsKICAgIHJldHVybiB0cnVlOwogIH0pLmNhdGNoKGZ1bmN0aW9uKGUpewogICAgbXNnKHN0SWQsJ05vIHB1ZGUgYWJyaXIgbGEgY2FtYXJhICgnKyhlJiZlLm5hbWU/ZS5uYW1lOidlcnJvcicpKycpLiBQdWVkZXMgdXNhciBsYSBnYWxlcmlhIG8gcmV2aXNhIGVsIHBlcm1pc28uJywnI2MwMCcpOwogICAgdGhyb3cgZTsKICB9KTsKfQpmdW5jdGlvbiBwYXJhckNhbShwc0lkKXsKICB2YXIgc3Q9c3RyZWFtc1twc0lkXTsKICBpZihzdCl7CiAgICB0cnl7IHN0LmdldFRyYWNrcygpLmZvckVhY2goZnVuY3Rpb24odCl7IHRyeXsgdC5zdG9wKCk7IH1jYXRjaChlKXt9IH0pOyB9Y2F0Y2goZSl7fQogICAgc3RyZWFtc1twc0lkXT1udWxsOwogIH0KfQpmdW5jdGlvbiBwYXJhclRvZGFzKCl7IHZhciBrOyBmb3IoayBpbiBzdHJlYW1zKXsgcGFyYXJDYW0oayk7IH0gfQpmdW5jdGlvbiBjYXB0dXJhclZpZGVvKHBzSWQsIG1heERpbSl7CiAgdmFyIHY9ZmluZFZpZGVvKHBzSWQpOwogIGlmKCF2IHx8ICF2LnZpZGVvV2lkdGgpeyByZXR1cm4gbnVsbDsgfQogIHZhciB3PXYudmlkZW9XaWR0aCwgaD12LnZpZGVvSGVpZ2h0OwogIHZhciBzYz1NYXRoLm1pbigxLChtYXhEaW18fDEwMjQpL01hdGgubWF4KHcsaCkpOwogIHZhciBjPWRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2NhbnZhcycpOwogIGMud2lkdGg9TWF0aC5yb3VuZCh3KnNjKTsgYy5oZWlnaHQ9TWF0aC5yb3VuZChoKnNjKTsKICBjLmdldENvbnRleHQoJzJkJykuZHJhd0ltYWdlKHYsMCwwLGMud2lkdGgsYy5oZWlnaHQpOwogIHZhciBkPWMudG9EYXRhVVJMKCdpbWFnZS9qcGVnJywwLjg1KTsKICBwYXJhckNhbShwc0lkKTsKICByZXR1cm4gZDsKfQpmdW5jdGlvbiBkb3duc2NhbGUoZGF0YVVybCwgbWF4RGltKXsKICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsKICAgIHZhciBpbT1uZXcgSW1hZ2UoKTsKICAgIGltLm9ubG9hZD1mdW5jdGlvbigpewogICAgICB2YXIgc2M9TWF0aC5taW4oMSwobWF4RGltfHwxMDI0KS9NYXRoLm1heChpbS53aWR0aCxpbS5oZWlnaHQpKTsKICAgICAgdmFyIGM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnY2FudmFzJyk7CiAgICAgIGMud2lkdGg9TWF0aC5tYXgoMSxNYXRoLnJvdW5kKGltLndpZHRoKnNjKSk7CiAgICAgIGMuaGVpZ2h0PU1hdGgubWF4KDEsTWF0aC5yb3VuZChpbS5oZWlnaHQqc2MpKTsKICAgICAgYy5nZXRDb250ZXh0KCcyZCcpLmRyYXdJbWFnZShpbSwwLDAsYy53aWR0aCxjLmhlaWdodCk7CiAgICAgIHJlcyhjLnRvRGF0YVVSTCgnaW1hZ2UvanBlZycsMC44NSkpOwogICAgfTsKICAgIGltLm9uZXJyb3I9ZnVuY3Rpb24oKXsgcmVzKGRhdGFVcmwpOyB9OwogICAgaW0uc3JjPWRhdGFVcmw7CiAgfSk7Cn0KZnVuY3Rpb24gYXJjaGl2b0FEYXRvcyhmaWxlKXsKICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzLHJlail7CiAgICB2YXIgZnI9bmV3IEZpbGVSZWFkZXIoKTsKICAgIGZyLm9ubG9hZD1mdW5jdGlvbigpeyByZXMoU3RyaW5nKGZyLnJlc3VsdCkpOyB9OwogICAgZnIub25lcnJvcj1mdW5jdGlvbigpeyByZWoobmV3IEVycm9yKCdubyBwdWRlIGxlZXIgZWwgYXJjaGl2bycpKTsgfTsKICAgIGZyLnJlYWRBc0RhdGFVUkwoZmlsZSk7CiAgfSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IE9DUiBjb24gY2FjaGUgPT09PT09PT09PT09PT09PT0gKi8KdmFyIGNhY2hlT2NyPXt9OwpmdW5jdGlvbiBoYWNlck9jcihkYXRhVXJsKXsKICBpZihjYWNoZU9jcltkYXRhVXJsXSl7IHJldHVybiBQcm9taXNlLnJlc29sdmUoY2FjaGVPY3JbZGF0YVVybF0pOyB9CiAgaWYodHlwZW9mIFRlc3NlcmFjdD09PSd1bmRlZmluZWQnIHx8ICFUZXNzZXJhY3QucmVjb2duaXplKXsKICAgIHJldHVybiBQcm9taXNlLnJlamVjdChuZXcgRXJyb3IoJ09DUiBubyBkaXNwb25pYmxlLCByZXZpc2EgdHUgaW50ZXJuZXQnKSk7CiAgfQogIHJldHVybiBUZXNzZXJhY3QucmVjb2duaXplKGRhdGFVcmwsJ3NwYStlbmcnLHtsb2dnZXI6ZnVuY3Rpb24oKXt9fSkudGhlbihmdW5jdGlvbihyKXsKICAgIHZhciB0PShyJiZyLmRhdGEmJnIuZGF0YS50ZXh0KT9yLmRhdGEudGV4dDonJzsKICAgIGNhY2hlT2NyW2RhdGFVcmxdPXQ7CiAgICByZXR1cm4gdDsKICB9KS5jYXRjaChmdW5jdGlvbihlKXsKICAgIHJldHVybiBUZXNzZXJhY3QucmVjb2duaXplKGRhdGFVcmwsJ2VuZycse2xvZ2dlcjpmdW5jdGlvbigpe319KS50aGVuKGZ1bmN0aW9uKHIyKXsKICAgICAgdmFyIHQyPShyMiYmcjIuZGF0YSYmcjIuZGF0YS50ZXh0KT9yMi5kYXRhLnRleHQ6Jyc7CiAgICAgIGNhY2hlT2NyW2RhdGFVcmxdPXQyOwogICAgICByZXR1cm4gdDI7CiAgICB9KTsKICB9KTsKfQoKLyogPT09PT09PT09PT09PT09PT0gYmlvbWV0cmlhIGZhY2lhbCA9PT09PT09PT09PT09PT09PSAqLwp2YXIgZmFjZVA9bnVsbDsKZnVuY3Rpb24gY2FyZ2FyRmFjZUFwaSgpewogIGlmKGZhY2VQKXsgcmV0dXJuIGZhY2VQOyB9CiAgZmFjZVA9bmV3IFByb21pc2UoZnVuY3Rpb24ocmVzLHJlail7CiAgICBmdW5jdGlvbiBsaXN0bygpeyByZXR1cm4gVy5mYWNlYXBpICYmIFcuZmFjZWFwaS5uZXRzICYmIFcuZmFjZWFwaS5uZXRzLnRpbnlGYWNlRGV0ZWN0b3IgJiYgVy5mYWNlYXBpLm5ldHMuZmFjZVJlY29nbml0aW9uTmV0OyB9CiAgICBmdW5jdGlvbiBtb2RlbG9zKGJhc2UpewogICAgICByZXR1cm4gUHJvbWlzZS5hbGwoWwogICAgICAgIFcuZmFjZWFwaS5uZXRzLnRpbnlGYWNlRGV0ZWN0b3IubG9hZEZyb21VcmkoYmFzZSksCiAgICAgICAgVy5mYWNlYXBpLm5ldHMuZmFjZUxhbmRtYXJrNjhOZXQubG9hZEZyb21VcmkoYmFzZSksCiAgICAgICAgVy5mYWNlYXBpLm5ldHMuZmFjZVJlY29nbml0aW9uTmV0LmxvYWRGcm9tVXJpKGJhc2UpCiAgICAgIF0pOwogICAgfQogICAgZnVuY3Rpb24gaW5pY2lhcigpewogICAgICB2YXIgYmFzZT0naHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L2doL2p1c3RhZHVkZXdob2hhY2tzL2ZhY2UtYXBpLmpzQDAuMjIuMi93ZWlnaHRzJzsKICAgICAgbW9kZWxvcyhiYXNlKS50aGVuKGZ1bmN0aW9uKCl7IHJlcygpOyB9LCBmdW5jdGlvbigpeyBtb2RlbG9zKCdodHRwczovL2p1c3RhZHVkZXdob2hhY2tzLmdpdGh1Yi5pby9mYWNlLWFwaS5qcy9tb2RlbHMnKS50aGVuKGZ1bmN0aW9uKCl7IHJlcygpOyB9LCByZWopOyB9KTsKICAgIH0KICAgIGlmKGxpc3RvKCkpeyBpbmljaWFyKCk7IHJldHVybjsgfQogICAgdmFyIHM9ZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnc2NyaXB0Jyk7CiAgICBzLnNyYz0naHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L25wbS9mYWNlLWFwaS5qc0AwLjIyLjIvZGlzdC9mYWNlLWFwaS5taW4uanMnOwogICAgcy5vbmxvYWQ9ZnVuY3Rpb24oKXsgaWYobGlzdG8oKSl7IGluaWNpYXIoKTsgfSBlbHNlIHsgcmVqKG5ldyBFcnJvcignZmFjZWFwaSBubyBxdWVkbyBsaXN0bycpKTsgfSB9OwogICAgcy5vbmVycm9yPWZ1bmN0aW9uKCl7IHJlaihuZXcgRXJyb3IoJ25vIHNlIHB1ZG8gY2FyZ2FyIGVsIHZlcmlmaWNhZG9yIGZhY2lhbCcpKTsgfTsKICAgIGRvY3VtZW50LmhlYWQuYXBwZW5kQ2hpbGQocyk7CiAgfSk7CiAgcmV0dXJuIGZhY2VQOwp9CmZ1bmN0aW9uIGNvblRpbWVvdXQocCwgbXMpewogIHJldHVybiBQcm9taXNlLnJhY2UoW3AsIG5ldyBQcm9taXNlKGZ1bmN0aW9uKHJlcyl7IHNldFRpbWVvdXQoZnVuY3Rpb24oKXsgcmVzKG51bGwpOyB9LCBtcyk7IH0pXSk7Cn0KZnVuY3Rpb24gZGV0ZWN0YXJDYXJhRW4oZGF0YVVybCl7CiAgcmV0dXJuIGNhcmdhckZhY2VBcGkoKS50aGVuKGZ1bmN0aW9uKCl7CiAgICByZXR1cm4gbmV3IFByb21pc2UoZnVuY3Rpb24ocmVzKXsKICAgICAgdmFyIGltPW5ldyBJbWFnZSgpOwogICAgICBpbS5vbmxvYWQ9ZnVuY3Rpb24oKXsKICAgICAgICB0cnl7CiAgICAgICAgICB2YXIgb3B0PW5ldyBXLmZhY2VhcGkuVGlueUZhY2VEZXRlY3Rvck9wdGlvbnMoe2lucHV0U2l6ZTozMjAsIHNjb3JlVGhyZXNob2xkOjAuNH0pOwogICAgICAgICAgVy5mYWNlYXBpLmRldGVjdFNpbmdsZUZhY2UoaW0sb3B0KS53aXRoRmFjZUxhbmRtYXJrcygpLndpdGhGYWNlRGVzY3JpcHRvcigpLnRoZW4oZnVuY3Rpb24ocil7IHJlcyhyfHxudWxsKTsgfSkuY2F0Y2goZnVuY3Rpb24oKXsgcmVzKG51bGwpOyB9KTsKICAgICAgICB9Y2F0Y2goZSl7IHJlcyhudWxsKTsgfQogICAgICB9OwogICAgICBpbS5vbmVycm9yPWZ1bmN0aW9uKCl7IHJlcyhudWxsKTsgfTsKICAgICAgaW0uc3JjPWRhdGFVcmw7CiAgICB9KTsKICB9KS5jYXRjaChmdW5jdGlvbigpeyByZXR1cm4gbnVsbDsgfSk7Cn0KZnVuY3Rpb24gZGlzdEYoYSxiKXsKICB2YXIgcz0wLGk7CiAgZm9yKGk9MDtpPGEubGVuZ3RoO2krKyl7IHZhciBkPWFbaV0tYltpXTsgcys9ZCpkOyB9CiAgcmV0dXJuIE1hdGguc3FydChzKTsKfQoKLyogPT09PT09PT09PT09PT09PT0gZ3VhcmRpYW4gZGUgb3JkZW4gMS0yLTMtNC01ID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHBlcm1pdGlkb0hhc3RhKCl7CiAgdmFyIHA9MTsKICBpZihFU1Qubm9tYnJlT2speyBwPTI7IH0KICBpZihFU1Qubm9tYnJlT2sgJiYgRVNULmZyZW50ZU9rKXsgcD0zOyB9CiAgaWYoRVNULm5vbWJyZU9rICYmIEVTVC5mcmVudGVPayAmJiAoRVNULnJldmVyc29PayB8fCAhRVNULm5lY2VzaXRhUmV2ZXJzbykpeyBwPTQ7IH0KICBpZihFU1Quc2VsZmllT2sgJiYgcD49NCl7IHA9NTsgfQogIHJldHVybiBwOwp9CmZ1bmN0aW9uIG1vc3RyYXJQYXNvKG4pewogIHZhciBpLGVsOwogIGZvcihpPTE7aTw9NTtpKyspewogICAgZWw9JCgncHMnK2kpOwogICAgaWYoZWwpeyBlbC5zdHlsZS5kaXNwbGF5PShpPT09bik/Jyc6J25vbmUnOyB9CiAgfQogIEVTVC5wYXNvPW47CiAgaWYobj09PTUpewogICAgdmFyIGE9JCgnY2xhdmUnKSwgYj0kKCdjbGF2ZTInKTsKICAgIGlmKGEpeyBhLmRpc2FibGVkPWZhbHNlOyB9CiAgICBpZihiKXsgYi5kaXNhYmxlZD1mYWxzZTsgfQogIH0KICB0cnl7IHZhciBhY3Q9JCgncHMnK24pOyBpZihhY3QmJmFjdC5zY3JvbGxJbnRvVmlldyl7IGFjdC5zY3JvbGxJbnRvVmlldyh7YmVoYXZpb3I6J3Ntb290aCcsYmxvY2s6J3N0YXJ0J30pOyB9IH1jYXRjaChlKXt9Cn0KZnVuY3Rpb24gYXZhbnphcihuKXsgbW9zdHJhclBhc28obik7IH0KZnVuY3Rpb24gdmVyaWZpY2FyKCl7CiAgdmFyIHBlcj1wZXJtaXRpZG9IYXN0YSgpOwogIGlmKEVTVC5wYXNvPnBlcil7CiAgICBtc2coJ3p5R3VhcmRpYScsJ1RlIHJlZ3Jlc28gYWwgcGFzbyAnK3BlcisnIHBhcmEgc2VndWlyIGVuIG9yZGVuLicsJyNhNjAnKTsKICAgIG1vc3RyYXJQYXNvKHBlcik7CiAgfQogIHZhciBzZWw9JCgndGlwb0RvYycpOwogIGlmKHNlbCAmJiBzZWwudmFsdWUgJiYgL3Bhc2Fwb3J0ZXxwYXNzcG9ydC9pLnRlc3QoKHNlbC5vcHRpb25zJiZzZWwub3B0aW9uc1tzZWwuc2VsZWN0ZWRJbmRleF0mJnNlbC5vcHRpb25zW3NlbC5zZWxlY3RlZEluZGV4XS50ZXh0KXx8JycpKXsKICAgIHZhciBwczM9JCgncHMzJyksIG5yPSQoJ25vdGFSZXYnKTsKICAgIGlmKHBzMyl7IHBzMy5zdHlsZS5kaXNwbGF5PSdub25lJzsgfQogICAgaWYobnIpeyBuci5zdHlsZS5kaXNwbGF5PSdub25lJzsgfQogIH0KfQp2YXIgdnRpbWVyPW51bGw7CmZ1bmN0aW9uIHByb2dyYW1hclZlcmlmaWNhcigpewogIGlmKHZ0aW1lcil7IHJldHVybjsgfQogIHZ0aW1lcj1zZXRUaW1lb3V0KGZ1bmN0aW9uKCl7IHZ0aW1lcj1udWxsOyB0cnl7IHZlcmlmaWNhcigpOyB9Y2F0Y2goZSl7fSB9LDEyMCk7Cn0KdHJ5ewogIG5ldyBNdXRhdGlvbk9ic2VydmVyKHByb2dyYW1hclZlcmlmaWNhcikub2JzZXJ2ZShkb2N1bWVudC5ib2R5LHtjaGlsZExpc3Q6dHJ1ZSxzdWJ0cmVlOnRydWUsYXR0cmlidXRlczp0cnVlLGF0dHJpYnV0ZUZpbHRlcjpbJ3N0eWxlJywnY2xhc3MnLCdoaWRkZW4nLCdkaXNhYmxlZCddfSk7Cn1jYXRjaChlKXt9CgovKiA9PT09PT09PT09PT09PT09PSBwYXNvIDE6IHNvbG8gZm9ybWF0byBkZWwgbm9tYnJlID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHZhbGlkYXJQYXNvMSgpewogIHZhciBpbnA9JCgnbm9tYnJlJyksIHNlbD0kKCd0aXBvRG9jJyk7CiAgdmFyIG9rPWZhbHNlLCB0aXBvT2s9ZmFsc2U7CiAgdmFyIHY9aW5wPyhpbnAudmFsdWV8fCcnKS50cmltKCk6Jyc7CiAgdmFyIGxldHJhcz0vXltBLVphLXrDgcOJw43Dk8Oaw5zDkcOhw6nDrcOzw7rDvMOxXSsoIFtBLVphLXrDgcOJw43Dk8Oaw5zDkcOhw6nDrcOzw7rDvMOxXSspKiQvLnRlc3Qodik7CiAgb2s9KHYubGVuZ3RoPj0zICYmIGxldHJhcyk7CiAgaWYoaW5wKXsgaW5wLnN0eWxlLmJvcmRlckNvbG9yPW9rPycnOicjYzAwJzsgfQogIGlmKCFvayl7IG1zZygnenlFcnJOb21icmUnLCB2PygnRWwgbm9tYnJlIHNvbG8gcHVlZGUgbGxldmFyIGxldHJhcyB5IGVzcGFjaW9zIChzaW4gbnVtZXJvcyBuaSBzaW1ib2xvcykuJyk6JycsICcjYzAwJyk7IH0KICBlbHNleyBtc2coJ3p5RXJyTm9tYnJlJywnJywnJyk7IH0KICB2YXIgdD1jbGFzaWZpY2FyVGlwbygpOwogIEVTVC50aXBvPXQuazsKICBFU1QubmVjZXNpdGFSZXZlcnNvPXQucmV2ZXJzbzsKICB0aXBvT2s9ISEoc2VsICYmIFN0cmluZyhzZWwudmFsdWV8fCcnKS5sZW5ndGg+MCk7CiAgaWYoIXRpcG9Payl7IG1zZygnenlFcnJUaXBvJywnRWxpZ2UgdHUgdGlwbyBkZSBkb2N1bWVudG8gZW4gbGEgbGlzdGEuJywnI2MwMCcpOyB9CiAgZWxzZXsgbXNnKCd6eUVyclRpcG8nLCcnLCcnKTsgfQogIEVTVC5ub21icmVPaz1vazsKICBFU1QuZXNjcml0bz1ub3JtKHYpOwogIHJldHVybiBvayYmdGlwb09rOwp9CmZ1bmN0aW9uIHJlc2V0ZWFyRG9jdW1lbnRvKCl7CiAgRVNULmZyZW50ZU9rPWZhbHNlOyBFU1QucmV2ZXJzb09rPWZhbHNlOyBFU1Quc2VsZmllT2s9ZmFsc2U7IEVTVC5pbnRlbnRvcz0zOwp9CgovKiA9PT09PT09PT09PT09PT09PSBwYXNvIDI6IGZyZW50ZSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBwcm9jZXNhckZyZW50ZShkYXRhVXJsKXsKICBidXN5KHRydWUpOwogIG1zZygnc3RGJywnTGV5ZW5kbyBlbCBkb2N1bWVudG8uLi4nLCcnKTsKICBFU1QuZnJlbnRlSW1nPWRhdGFVcmw7CiAgc2hvd0ltZygncEYnLGRhdGFVcmwpOwogIHZhciBwQ2FyYT1jb25UaW1lb3V0KGRldGVjdGFyQ2FyYUVuKGRhdGFVcmwpLDEyMDAwKTsKICB2YXIgcFR4dD1oYWNlck9jcihkYXRhVXJsKS5jYXRjaChmdW5jdGlvbihlKXsgcmV0dXJuICdPQ1JfRVJSOicrKGUmJmUubWVzc2FnZT9lLm1lc3NhZ2U6JycpOyB9KTsKICBQcm9taXNlLmFsbChbcENhcmEscFR4dF0pLnRoZW4oZnVuY3Rpb24ocil7CiAgICB2YXIgY2FyYT1yWzBdLCB0ZXh0bz1yWzFdfHwnJzsKICAgIGlmKHRleHRvLmluZGV4T2YoJ09DUl9FUlI6Jyk9PT0wKXsgYnVzeShmYWxzZSk7IG1zZygnc3RGJywnTm8gcHVkZSBsZWVyIGVsIGRvY3VtZW50byAoJyt0ZXh0by5zbGljZSg4KSsnKS4gVG9jYSBDQVBUVVJBUiBkZSBudWV2bywgY29uIGJ1ZW5hIGx1eiB5IHNpbiBicmlsbG8uJywnI2MwMCcpOyByZXR1cm47IH0KICAgIGlmKHRleHRvLnJlcGxhY2UoL1xzL2csJycpLmxlbmd0aDwxNSl7IGJ1c3koZmFsc2UpOyBtc2coJ3N0RicsJ05vIGxlw60gc3VmaWNpZW50ZSB0ZXh0by4gQWPDqXJjYXRlLCBidWVuYSBsdXosIHF1ZSBlbCBkb2N1bWVudG8gbGxlbmUgZWwgbWFyY28geSB0b2NhIENBUFRVUkFSLicsJyNjMDAnKTsgcmV0dXJuOyB9CiAgICB2YXIgbGFkbz1kZXRlY3RhckxhZG8odGV4dG8sISEoY2FyYSYmY2FyYS5kZXRlY3Rpb24pKTsKICAgIGlmKGxhZG89PT0ncmV2ZXJzbycpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbXNnKCdzdEYnLCdFc28gZXMgZWwgUkVWRVJTTyAoc2UgdmVuIGRpcmVjY2lvbmVzIG8gbGEgem9uYSBNUlopLiBOZWNlc2l0byBlbCBGUkVOVEU6IGRvbmRlIGVzdMOhIHR1IEZPVE8geSB0dXMgZGF0b3MuIFZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgaWYobGFkbyE9PSdmcmVudGUnICYmICEoY2FyYSYmY2FyYS5kZXRlY3Rpb24pKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RGJywnTm8gcHVkZSBjb25maXJtYXIgcXVlIHNlYSBlbCBGUkVOVEUuIEFzZWfDunJhdGUgZGUgcXVlIHNlIHZlYSB0dSBmb3RvIHkgdHVzIGRhdG9zLCBzaW4gYnJpbGxvLCB5IHZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgdmFyIG5jPW5vbWJyZUNvaW5jaWRlKEVTVC5lc2NyaXRvLHRleHRvKTsKICAgIGlmKG5jLmhheSAmJiAhbmMub2spewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbm9tYnJlTm9Db2luY2lkZU1zZygnTG8gcXVlIGVzY3JpYmlzdGUgbm8gY29pbmNpZGUgY29uIGVsIGRvY3VtZW50byAobGXDrTogJytuYy5sZWlkbysnKS4gQ29ycmlnZSB0dSBub21icmUgZW4gZWwgcGFzbyAxLicpOwogICAgICByZXR1cm47CiAgICB9CiAgICBFU1QuZnJlbnRlT2s9dHJ1ZTsKICAgIEVTVC5mcmVudGVUZXh0bz10ZXh0bzsKICAgIG1zZygnc3RGJywn4pyTIEZyZW50ZSBsZcOtZG8gY29ycmVjdGFtZW50ZS4nKyhuYy5vaz8oJyBOb21icmU6ICcrbmMubGVpZG8rJy4nKTonJyksJyMwODAnKTsKICAgIGJ1c3koZmFsc2UpOwogICAgYXZhbnphcihFU1QubmVjZXNpdGFSZXZlcnNvPzM6NCk7CiAgfSk7Cn0KZnVuY3Rpb24gbm9tYnJlTm9Db2luY2lkZU1zZyh0eHQpewogIHJlc2V0ZWFyRG9jdW1lbnRvKCk7CiAgdmFyIG5uPSQoJ25vbWJyZU5vQ29pbmNpZGUnKTsKICBpZihubil7IG5uLnRleHRDb250ZW50PXR4dDsgbm4uc3R5bGUuZGlzcGxheT0nYmxvY2snOyBubi5zdHlsZS5jb2xvcj0nI2MwMCc7IH0KICBtc2coJ3N0QScsJycpOyBtc2coJ3N0RicsJycpOwogIG1zZygnenlFcnJOb21icmUnLHR4dCwnI2MwMCcpOwogIGF2YW56YXIoMSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IHBhc28gMzogcmV2ZXJzbyA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiByZXZlcnNvQWNlcHRhYmxlKHRleHRvKXsKICB2YXIgdD0odGV4dG98fCcnKS50b1VwcGVyQ2FzZSgpOwogIGlmKCh0Lm1hdGNoKC88L2cpfHxbXSkubGVuZ3RoPj02KXsgcmV0dXJuIHRydWU7IH0KICBpZigvUERGNEk/Ny8udGVzdCh0LnJlcGxhY2UoL1xzL2csJycpKSl7IHJldHVybiB0cnVlOyB9CiAgdmFyIGZ1ZXJ0ZXM9WydET01JQ0lMSU8nLCdESVJFQ0NJT04nLCdESVJFQ0NJw5NOJywnQ09MT05JQScsJ0JBUlJJTycsJ1JFU0lERU5DSUEnLCdDQVNFUklPJywnQ0FOVE9OJywnQUxERUEnLCdPQlNFUlZBQ0lPTicsJ09CU0VSVkFDScOTTicsJ0VTVEFETyBDSVZJTCcsJ0RPTkFOVEUnLCdHUlVQTyBTQU5HJywnVElQTyBERSBTQU5HJywnRU5ET1JTRU1FTlQnLCdSRVNUUklDVElPTicsJ0FERFJFU1MnXTsKICB2YXIgaSxjPTA7CiAgZm9yKGk9MDtpPGZ1ZXJ0ZXMubGVuZ3RoO2krKyl7IGlmKHQuaW5kZXhPZihmdWVydGVzW2ldKT49MCl7IGMrKzsgfSB9CiAgaWYoYz49Mil7IHJldHVybiB0cnVlOyB9CiAgaWYoRVNULnRpcG89PT0ndXNhJyAmJiAvXGIoSVNTfEVYUHxERHw0RHw0RnxSRVNUfEVORHxETClcYi8udGVzdCh0KSl7IHJldHVybiB0cnVlOyB9CiAgcmV0dXJuIGZhbHNlOwp9CmZ1bmN0aW9uIHByb2Nlc2FyUmV2ZXJzbyhkYXRhVXJsKXsKICBidXN5KHRydWUpOwogIG1zZygnc3RBJywnTGV5ZW5kbyBlbCByZXZlcnNvLi4uJywnJyk7CiAgRVNULnJldmVyc29JbWc9ZGF0YVVybDsKICBzaG93SW1nKCdwQScsZGF0YVVybCk7CiAgaGFjZXJPY3IoZGF0YVVybCkudGhlbihmdW5jdGlvbih0ZXh0byl7CiAgICBpZih0ZXh0by5yZXBsYWNlKC9ccy9nLCcnKS5sZW5ndGg8MTAgJiYgIXJldmVyc29BY2VwdGFibGUodGV4dG8pKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RBJywnTm8gbGXDrSBzdWZpY2llbnRlIHRleHRvIGVuIGVsIHJldmVyc28uIEFjw6lyY2F0ZSwgYnVlbmEgbHV6LCB5IHZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgdmFyIGNhcmFQZW5kPW51bGw7CiAgICB2YXIgbGFkbz1kZXRlY3RhckxhZG8odGV4dG8sZmFsc2UpOwogICAgaWYobGFkbz09PSdmcmVudGUnKXsKICAgICAgYnVzeShmYWxzZSk7CiAgICAgIG1zZygnc3RBJywnRXNvIGVzIGVsIEZSRU5URSAoc2UgdmUgbGEgZm90byB5IGxvcyBkYXRvcykuIE5lY2VzaXRvIGVsIFJFVkVSU086IGRpcmVjY2lvbmVzIG8gbGEgem9uYSBNUlouIFZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgaWYobGFkbyE9PSdyZXZlcnNvJyAmJiAhcmV2ZXJzb0FjZXB0YWJsZSh0ZXh0bykpewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbXNnKCdzdEEnLCdObyBwdWRlIGNvbmZpcm1hciBxdWUgc2VhIGVsIFJFVkVSU08uIE11ZXN0cmEgbGFzIGRpcmVjY2lvbmVzIG8gbGEgem9uYSBkZSByYXlpdGFzL01SWiB5IHZ1ZWx2ZSBhIGNhcHR1cmFyLicsJyNjMDAnKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgdmFyIG5jPW5vbWJyZUNvaW5jaWRlKEVTVC5lc2NyaXRvLHRleHRvKTsKICAgIGlmKG5jLmhheSAmJiAhbmMub2spewogICAgICBidXN5KGZhbHNlKTsKICAgICAgbm9tYnJlTm9Db2luY2lkZU1zZygnRWwgbm9tYnJlIGRlbCByZXZlcnNvICgnK25jLmxlaWRvKycpIG5vIGNvaW5jaWRlIGNvbiBsbyBxdWUgZXNjcmliaXN0ZS4gQ29ycmlnZSB0dSBub21icmUgZW4gZWwgcGFzbyAxLicpOwogICAgICByZXR1cm47CiAgICB9CiAgICBFU1QucmV2ZXJzb09rPXRydWU7CiAgICBFU1QucmV2ZXJzb1RleHRvPXRleHRvOwogICAgbXNnKCdzdEEnLCfinJMgUmV2ZXJzbyBsZcOtZG8gY29ycmVjdGFtZW50ZS4nLCcjMDgwJyk7CiAgICBidXN5KGZhbHNlKTsKICAgIGF2YW56YXIoNCk7CiAgfSkuY2F0Y2goZnVuY3Rpb24oZSl7CiAgICBidXN5KGZhbHNlKTsKICAgIG1zZygnc3RBJywnRXJyb3IgbGV5ZW5kbyBlbCByZXZlcnNvOiAnKyhlJiZlLm1lc3NhZ2U/ZS5tZXNzYWdlOicnKSsnLiBWdWVsdmUgYSBjYXB0dXJhci4nLCcjYzAwJyk7CiAgfSk7Cn0KCi8qID09PT09PT09PT09PT09PT09IHBhc28gNDogc2VsZmllID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIHByb2Nlc2FyU2VsZmllKCl7CiAgdmFyIGltZz1jYXB0dXJhclZpZGVvKCc0JywxMDQ4KTsKICBpZighaW1nKXsgbXNnKCdzdFYnLCdQcmltZXJvIGFicmUgbGEgY8OhbWFyYSB5IHBvbiB0dSBjYXJhIGRlbnRybyBkZWwgbWFyY28uJywnI2MwMCcpOyByZXR1cm47IH0KICBFU1Quc2VsZmllSW1nPWltZzsKICBzaG93SW1nKCdwUycsaW1nKTsKICBidXN5KHRydWUpOwogIG1zZygnc3RWJywnQ29tcGFyYW5kbyB0dSBjYXJhIGNvbiBsYSBkZWwgZG9jdW1lbnRvLi4uJywnJyk7CiAgdmFyIHBEb2M9Y29uVGltZW91dChkZXRlY3RhckNhcmFFbihFU1QuZnJlbnRlSW1nfHxFU1QucmV2ZXJzb0ltZ3x8JycpLDE1MDAwKTsKICB2YXIgcFNlbD1jb25UaW1lb3V0KGRldGVjdGFyQ2FyYUVuKGltZyksMTUwMDApOwogIFByb21pc2UuYWxsKFtwRG9jLHBTZWxdKS50aGVuKGZ1bmN0aW9uKHIpewogICAgdmFyIGVuRG9jPXJbMF0sIGVuU2VsPXJbMV07CiAgICBpZighZW5Eb2MgfHwgIWVuRG9jLmRldGVjdGlvbil7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBmYWxsb1NlbGZpZSgnTm8gcHVkZSB2ZXIgYmllbiBsYSBjYXJhIGVuIGxhIGZvdG8gZGVsIGRvY3VtZW50by4gVmFtb3MgYSByZXBldGlyIGxhIGZvdG8gZGVsIGRvY3VtZW50byBjb24gbWVqb3IgbHV6LicpOwogICAgICByZXR1cm47CiAgICB9CiAgICBpZighZW5TZWwgfHwgIWVuU2VsLmRldGVjdGlvbil7CiAgICAgIGJ1c3koZmFsc2UpOwogICAgICBmYWxsb1NlbGZpZSgnTm8gcHVkZSB2ZXIgdHUgY2FyYSBlbiBsYSBzZWxmaWUuIE1lam9yIGxhIGx1eiwgcXXDrXRhdGUgZ29ycmEgbyBsZW50ZXMgb3NjdXJvcy4nKTsKICAgICAgcmV0dXJuOwogICAgfQogICAgdmFyIGQ9ZGlzdEYoZW5Eb2MuZGVzY3JpcHRvcixlblNlbC5kZXNjcmlwdG9yKTsKICAgIGlmKGQ8PTAuNjApewogICAgICBFU1Quc2VsZmllT2s9dHJ1ZTsKICAgICAgRVNULmludGVudG9zPTM7CiAgICAgIG1zZygnc3RWJywn4pyTIFZlcmlmaWNhY2nDs24gZmFjaWFsIHN1cGVyYWRhLiBQYXNhbmRvIGEgdHUgY2xhdmUuJywnIzA4MCcpOwogICAgICBidXN5KGZhbHNlKTsKICAgICAgYXZhbnphcig1KTsKICAgIH1lbHNlewogICAgICBidXN5KGZhbHNlKTsKICAgICAgZmFsbG9TZWxmaWUoJ1R1IGNhcmEgbm8gY29pbmNpZGUgY29uIGxhIGRlbCBkb2N1bWVudG8gKGRpc3RhbmNpYSAnK2QudG9GaXhlZCgyKSsnKS4nKTsKICAgIH0KICB9KS5jYXRjaChmdW5jdGlvbihlKXsKICAgIGJ1c3koZmFsc2UpOwogICAgZmFsbG9TZWxmaWUoJ0VsIHZlcmlmaWNhZG9yIGZhY2lhbCBubyBjYXJnw7M6ICcrKGUmJmUubWVzc2FnZT9lLm1lc3NhZ2U6JycpKycuIFJldmlzYSB0dSBpbnRlcm5ldCB5IHJlaW50ZW50YS4nKTsKICB9KTsKfQpmdW5jdGlvbiBmYWxsb1NlbGZpZShtKXsKICBFU1QuaW50ZW50b3MtLTsKICBpZihFU1QuaW50ZW50b3M8PTApewogICAgRVNULmludGVudG9zPTM7CiAgICBFU1Quc2VsZmllT2s9ZmFsc2U7CiAgICBtc2coJ3N0VicsJ1NlIGFnb3Rhcm9uIGxvcyAzIGludGVudG9zLiBWb2x2ZW1vcyBhIGxhIGZvdG8gZGVsIGRvY3VtZW50bzsgcmV2w61zYWxhIHkgdnVlbHZlIGEgdG9tYXJsYSwgeSBzZWd1aW1vcyBlbiBvcmRlbiBwb3IgbG9zIHBhc29zLicsJyNhNjAnKTsKICAgIGF2YW56YXIoMik7CiAgfWVsc2V7CiAgICBtc2coJ3N0VicsJ+KclyAnK20rJyBUZSBxdWVkYW4gJytFU1QuaW50ZW50b3MrJyBpbnRlbnRvKHMpLiBUb2NhIENBUFRVUkFSIGRlIG51ZXZvLicsJyNjMDAnKTsKICB9Cn0KCi8qID09PT09PT09PT09PT09PT09IHBhc28gNTogY2xhdmUgKyBaSUQgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gdmFsaWRhckNsYXZlcygpewogIHZhciBhPSQoJ2NsYXZlJyksIGI9JCgnY2xhdmUyJyksIGQ9JCgnZGVzZ2xvc2UnKTsKICBpZighYXx8IWIpeyByZXR1cm47IH0KICBpZighYi52YWx1ZSl7IGlmKGQpeyBkLnRleHRDb250ZW50PScnOyB9IHJldHVybjsgfQogIGlmKGEudmFsdWU9PT1iLnZhbHVlKXsKICAgIGlmKGQpeyBkLnRleHRDb250ZW50PSfinJMgTGFzIGNsYXZlcyBjb2luY2lkZW4uIFRvY2EgZWwgYm90w7NuIHBhcmEgY3JlYXIgdHUgWklELic7IGQuc3R5bGUuY29sb3I9JyMwODAnOyB9CiAgICBoYWJpbGl0YXJTdWJtaXQoKTsKICB9ZWxzZXsKICAgIGlmKGQpeyBkLnRleHRDb250ZW50PSfinJcgTGFzIGNsYXZlcyBubyBjb2luY2lkZW4uIENvcnLDrWdlbGFzIGFxdcOtLCBubyBzYWxlcyBkZWwgcGFzbyA1IGhhc3RhIHF1ZSBjb2luY2lkYW4uJzsgZC5zdHlsZS5jb2xvcj0nI2MwMCc7IH0KICB9Cn0KZnVuY3Rpb24gaGFiaWxpdGFyU3VibWl0KCl7CiAgdmFyIHBzPSQoJ3BzNScpOwogIGlmKCFwcyl7IHJldHVybjsgfQogIHZhciBidG5zPXBzLnF1ZXJ5U2VsZWN0b3JBbGwoJ2J1dHRvbiwgaW5wdXRbdHlwZT1idXR0b25dLCBpbnB1dFt0eXBlPXN1Ym1pdF0sIFtyb2xlPWJ1dHRvbl0nKSwgaSwgaGF5PWZhbHNlOwogIGZvcihpPTA7aTxidG5zLmxlbmd0aDtpKyspewogICAgdmFyIHQ9KChidG5zW2ldLnRleHRDb250ZW50fHwnJykrJyAnKyhidG5zW2ldLnZhbHVlfHwnJykpLnRvVXBwZXJDYXNlKCk7CiAgICBpZigvQ1JFQVJ8UkVHSVNUUnxGSU5BTElaQVJ8Q09OVElOVUFSfEVOVklBUnxBQ0VQVEFSfFpJRC8udGVzdCh0KSl7IGJ0bnNbaV0uZGlzYWJsZWQ9ZmFsc2U7IGhheT10cnVlOyB9CiAgfQogIGlmKCFoYXkpeyBtc2coJ3p5Q2xhdmVPaycsJ1NpIG5vIHZlcyBlbCBib3TDs24gcGFyYSBjcmVhciB0dSBaSUQsIGF2w61zYW1lLicsJyNhNjAnKTsgfQp9CgovKiA9PT09PT09PT09PT09PT09PSBpbnRlcnJ1cHRvciBkZSBib3RvbmVzID09PT09PT09PT09PT09PT09ICovCnZhciBNSU89eydiQWJyaXJGJzoxLCdiQ2FwRic6MSwnYkFicmlyQSc6MSwnYkNhcEEnOjEsJ2JBYnJpckNhbSc6MSwnYlNlbGZpZSc6MSwnYlJlcFNlbGZpZSc6MSwnYklyNCc6MSwnYklyNSc6MX07CmZ1bmN0aW9uIG1hbmVqYXIoaWQpewogIHN3aXRjaChpZCl7CiAgICBjYXNlICdiQWJyaXJGJzogYWJyaXJDYW0oJzInLCdlbnZpcm9ubWVudCcsJ3N0RicsJ2JDYXBGJykuY2F0Y2goZnVuY3Rpb24oKXt9KTsgYnJlYWs7CiAgICBjYXNlICdiQ2FwRic6IHsgdmFyIGY9Y2FwdHVyYXJWaWRlbygnMicsMTAyNCk7IGlmKCFmKXsgbXNnKCdzdEYnLCdBYnJlIGxhIGPDoW1hcmEgcHJpbWVybyAoYm90w7NuIGFicmlyIGPDoW1hcmEpLicsJyNjMDAnKTsgfSBlbHNlIHsgcHJvY2VzYXJGcmVudGUoZik7IH0gYnJlYWs7IH0KICAgIGNhc2UgJ2JBYnJpckEnOiBhYnJpckNhbSgnMycsJ2Vudmlyb25tZW50Jywnc3RBJywnYkNhcEEnKS5jYXRjaChmdW5jdGlvbigpe30pOyBicmVhazsKICAgIGNhc2UgJ2JDYXBBJzogeyB2YXIgYT1jYXB0dXJhclZpZGVvKCczJywxMDI0KTsgaWYoIWEpeyBtc2coJ3N0QScsJ0FicmUgbGEgY8OhbWFyYSBwcmltZXJvIChib3TDs24gYWJyaXIgY8OhbWFyYSkuJywnI2MwMCcpOyB9IGVsc2UgeyBwcm9jZXNhclJldmVyc28oYSk7IH0gYnJlYWs7IH0KICAgIGNhc2UgJ2dhbEYnOiBjbGlja0FyY2hpdm8oJzInKTsgYnJlYWs7CiAgICBjYXNlICdnYWxBJzogY2xpY2tBcmNoaXZvKCczJyk7IGJyZWFrOwogICAgY2FzZSAnYkFicmlyQ2FtJzogYWJyaXJDYW0oJzQnLCd1c2VyJywnc3RWJywnYlNlbGZpZScpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IGJyZWFrOwogICAgY2FzZSAnYlNlbGZpZSc6IHByb2Nlc2FyU2VsZmllKCk7IGJyZWFrOwogICAgY2FzZSAnYlJlcFNlbGZpZSc6IGFicmlyQ2FtKCc0JywndXNlcicsJ3N0VicsJ2JTZWxmaWUnKS5jYXRjaChmdW5jdGlvbigpe30pOyBicmVhazsKICAgIGNhc2UgJ2JJcjQnOgogICAgICBpZihwZXJtaXRpZG9IYXN0YSgpPj00KXsgYXZhbnphcig0KTsgfQogICAgICBlbHNleyBtc2coJ3N0QScsJ0HDum4gbm8gcHVlZGVzIHBhc2FyOiBwcmltZXJvIGNvbXBsZXRhIGVsIGRvY3VtZW50byAoZnJlbnRlJysoRVNULm5lY2VzaXRhUmV2ZXJzbz8nIHkgcmV2ZXJzbyc6JycpKycpLicsJyNjMDAnKTsgfQogICAgICBicmVhazsKICAgIGNhc2UgJ2JJcjUnOgogICAgICBpZihwZXJtaXRpZG9IYXN0YSgpPj01KXsgYXZhbnphcig1KTsgfQogICAgICBlbHNleyBtc2coJ3N0VicsJ0HDum4gbm8gcHVlZGVzIHBhc2FyOiBwcmltZXJvIHBhc2EgbGEgdmVyaWZpY2FjacOzbiBmYWNpYWwuJywnI2MwMCcpOyB9CiAgICAgIGJyZWFrOwogIH0KfQpkb2N1bWVudC5hZGRFdmVudExpc3RlbmVyKCdjbGljaycsZnVuY3Rpb24oZSl7CiAgdmFyIGVsPWUudGFyZ2V0OwogIHdoaWxlKGVsICYmIGVsIT09ZG9jdW1lbnQgJiYgIShlbC5pZCAmJiBNSU9bZWwuaWRdKSl7IGVsPWVsLnBhcmVudE5vZGU7IH0KICBpZighZWwgfHwgZWw9PT1kb2N1bWVudCl7IHJldHVybjsgfQogIGlmKGUucHJldmVudERlZmF1bHQpeyBlLnByZXZlbnREZWZhdWx0KCk7IH0KICBpZihlLnN0b3BQcm9wYWdhdGlvbil7IGUuc3RvcFByb3BhZ2F0aW9uKCk7IH0KICBpZihlLnN0b3BJbW1lZGlhdGVQcm9wYWdhdGlvbil7IGUuc3RvcEltbWVkaWF0ZVByb3BhZ2F0aW9uKCk7IH0KICB0cnl7IG1hbmVqYXIoZWwuaWQsZSk7IH1jYXRjaChlcnIpeyBsb2coJ2Vycm9yIGVuJyxlbC5pZCxlcnIpOyB9Cn0sdHJ1ZSk7CgovKiA9PT09PT09PT09PT09PT09PSBnYWxlcmlhID09PT09PT09PT09PT09PT09ICovCmZ1bmN0aW9uIGNsaWNrQXJjaGl2byhwc0lkKXsKICB2YXIgY29udD0kKCdwcycrcHNJZCk7CiAgdmFyIGlucD1jb250P2NvbnQucXVlcnlTZWxlY3RvcignaW5wdXRbdHlwZT1maWxlXScpOm51bGw7CiAgaWYoaW5wKXsgaW5wLmNsaWNrKCk7IH0KICBlbHNleyBtc2cocHNJZD09PScyJz8nc3RGJzonc3RBJywnTm8gZW5jb250csOpIGVsIHNlbGVjdG9yIGRlIGFyY2hpdm9zLicsJyNjMDAnKTsgfQp9CmZ1bmN0aW9uIGVuZ2FuY2hhckdhbGVyaWEoaWQscHNJZCl7CiAgdmFyIGVsPSQoaWQpOwogIGlmKCFlbCl7IHJldHVybjsgfQogIGlmKGVsLnRhZ05hbWU9PT0nSU5QVVQnICYmIChlbC50eXBlfHwnJykudG9Mb3dlckNhc2UoKT09PSdmaWxlJyl7CiAgICBlbC5hZGRFdmVudExpc3RlbmVyKCdjaGFuZ2UnLGZ1bmN0aW9uKCl7CiAgICAgIHZhciBmPWVsLmZpbGVzJiZlbC5maWxlc1swXTsKICAgICAgaWYoIWYpeyByZXR1cm47IH0KICAgICAgYXJjaGl2b0FEYXRvcyhmKS50aGVuKGZ1bmN0aW9uKGQpeyByZXR1cm4gZG93bnNjYWxlKGQsMTAyNCk7IH0pLnRoZW4oZnVuY3Rpb24oZCl7CiAgICAgICAgaWYocHNJZD09PScyJyl7IHByb2Nlc2FyRnJlbnRlKGQpOyB9IGVsc2UgeyBwcm9jZXNhclJldmVyc28oZCk7IH0KICAgICAgfSkuY2F0Y2goZnVuY3Rpb24oZXIpeyBtc2cocHNJZD09PScyJz8nc3RGJzonc3RBJywnTm8gcHVkZSBsZWVyIGxhIGltYWdlbjogJysoZXImJmVyLm1lc3NhZ2U/ZXIubWVzc2FnZTonJyksJyNjMDAnKTsgfSk7CiAgICB9KTsKICB9ZWxzZXsKICAgIE1JT1tpZF09MTsKICB9Cn0KCi8qID09PT09PT09PT09PT09PT09IGV2ZW50b3MgZGUgcGFzb3MgMSB5IDUgPT09PT09PT09PT09PT09PT0gKi8KZnVuY3Rpb24gZW5nYW5jaGFyUGFzbzEoKXsKICB2YXIgaW5wPSQoJ25vbWJyZScpLCBzZWw9JCgndGlwb0RvYycpOwogIGlmKGlucCl7CiAgICBpbnAuYWRkRXZlbnRMaXN0ZW5lcignaW5wdXQnLGZ1bmN0aW9uKCl7CiAgICAgIHZhciBhbnRlc09rPUVTVC5ub21icmVPazsKICAgICAgdmFsaWRhclBhc28xKCk7CiAgICAgIGlmKCFFU1Qubm9tYnJlT2sgJiYgYW50ZXNPayAmJiBFU1QucGFzbz4xKXsKICAgICAgICByZXNldGVhckRvY3VtZW50bygpOwogICAgICAgIG1zZygnenlFcnJOb21icmUnLCdFbCBub21icmUgY2FtYmnDsyB5IG5vIGVzIHbDoWxpZG8uIENvcnLDrWdlbG8gcGFyYSBzZWd1aXIuJywnI2MwMCcpOwogICAgICB9CiAgICAgIGlmKEVTVC5ub21icmVPayAmJiBFU1QucGFzbz09PTEgJiYgc2VsICYmIFN0cmluZyhzZWwudmFsdWV8fCcnKS5sZW5ndGg+MCl7IGF2YW56YXIoMik7IH0KICAgIH0pOwogIH0KICBpZihzZWwpewogICAgc2VsLmFkZEV2ZW50TGlzdGVuZXIoJ2NoYW5nZScsZnVuY3Rpb24oKXsKICAgICAgdmFsaWRhclBhc28xKCk7CiAgICAgIHJlc2V0ZWFyRG9jdW1lbnRvKCk7CiAgICAgIGlmKEVTVC5ub21icmVPayAmJiBTdHJpbmcoc2VsLnZhbHVlfHwnJykubGVuZ3RoPjApeyBhdmFuemFyKDIpOyB9CiAgICB9KTsKICB9Cn0KZnVuY3Rpb24gZW5nYW5jaGFyUGFzbzUoKXsKICB2YXIgYT0kKCdjbGF2ZScpLCBiPSQoJ2NsYXZlMicpOwogIGlmKGEpeyBhLmFkZEV2ZW50TGlzdGVuZXIoJ2lucHV0Jyx2YWxpZGFyQ2xhdmVzKTsgfQogIGlmKGIpeyBiLmFkZEV2ZW50TGlzdGVuZXIoJ2lucHV0Jyx2YWxpZGFyQ2xhdmVzKTsgfQp9CgovKiA9PT09PT09PT09PT09PT09PSBhcnJhbnF1ZSA9PT09PT09PT09PT09PT09PSAqLwpmdW5jdGlvbiBpbml0KCl7CiAgZW5nYW5jaGFyUGFzbzEoKTsKICBlbmdhbmNoYXJQYXNvNSgpOwogIGVuZ2FuY2hhckdhbGVyaWEoJ2dhbEYnLCcyJyk7CiAgZW5nYW5jaGFyR2FsZXJpYSgnZ2FsQScsJzMnKTsKICBbJ292RicsJ292QScsJ292UyddLmZvckVhY2goZnVuY3Rpb24ob2lkKXsgdmFyIG89JChvaWQpOyBpZihvKXsgby5zdHlsZS5wb2ludGVyRXZlbnRzPSdub25lJzsgfSB9KTsKICB2YWxpZGFyUGFzbzEoKTsKICB2ZXJpZmljYXIoKTsKICBpZihFU1Qubm9tYnJlT2sgJiYgRVNULnBhc289PT0xKXsgYXZhbnphcigyKTsgfQogIHNldFRpbWVvdXQoZnVuY3Rpb24oKXsgY2FyZ2FyRmFjZUFwaSgpLmNhdGNoKGZ1bmN0aW9uKCl7fSk7IH0sMTUwMCk7CiAgdHJ5eyBpZihkb2N1bWVudC50aXRsZS5pbmRleE9mKCdSRVYgRCcpPDApeyBkb2N1bWVudC50aXRsZT1kb2N1bWVudC50aXRsZSsnIMK3IFJFViBEJzsgfSB9Y2F0Y2goZSl7fQogIGxvZygnbnVjbGVvIHJldkQgYWN0aXZvLiBFc3RhZG86JywgSlNPTi5zdHJpbmdpZnkoRVNUKSk7Cn0KaWYoZG9jdW1lbnQucmVhZHlTdGF0ZT09PSdsb2FkaW5nJyl7CiAgZG9jdW1lbnQuYWRkRXZlbnRMaXN0ZW5lcignRE9NQ29udGVudExvYWRlZCcsaW5pdCk7Cn1lbHNlewogIGluaXQoKTsKfQpXLl9fWllSQV9SRVZEX0lORk89ZnVuY3Rpb24oKXsgcmV0dXJuIEpTT04ucGFyc2UoSlNPTi5zdHJpbmdpZnkoRVNUKSk7IH07Cn0pKCk7Cg=='))/*ZYRA-V6-END*/</script>
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

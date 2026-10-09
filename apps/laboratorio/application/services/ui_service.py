"""Servicio de UI: construye las vistas desde las fuentes unicas.

Fase 2 EN VIVO: capturar, comprender y disenar usan datos reales.
Ley 3: maximo 3 botones de accion por vista. Ley 1: paneles sin
backend declaran su fase. Seguridad: todo dato pasa por escapar().
"""
import json
from pathlib import Path
from urllib.parse import quote

from apps.laboratorio.application.services.ui_fases import FASE_POR_MENU
from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo
from apps.laboratorio.infrastructure.security.html_sanitizer import escapar
from apps.laboratorio.infrastructure.services.template_render import render
from apps.laboratorio.permissions.roles.role_definitions import menus_de
from apps.laboratorio.registry.menus.menu_tree import MENUS, existe as existe_menu
from apps.laboratorio.shared.enums.creation_type import CreationType
from apps.laboratorio.shared.enums.input_kind import InputKind
from apps.laboratorio.shared.exceptions.domain_errors import EntidadNoEncontradaError

RAIZ_APP = Path(__file__).resolve().parents[2]
RUTA_PLANTILLAS = RAIZ_APP / "templates" / "dashboards"
RUTA_TRADUCCIONES = RAIZ_APP / "assets" / "translations"

MENUS_VIVOS = ("inicio", "simular", "capturar", "comprender", "disenar")

ICONO_POR_MENU = {
    "inicio": "i-home", "capturar": "i-capturar", "comprender": "i-comprender",
    "disenar": "i-disenar", "crear": "i-crear", "cuatro_d": "i-4d",
    "simular": "i-simular", "probar": "i-probar", "comparar": "i-comparar",
    "optimizar": "i-optimizar", "renderizar": "i-render", "presentar": "i-presentar",
    "proyectar": "i-proyectar", "salidas": "i-salidas", "exportar": "i-exportar",
    "biblioteca": "i-biblioteca", "red": "i-red", "gobierno": "i-gobierno",
}

_cache = {"plantillas": {}, "textos": None}


def cargar_plantilla(nombre: str) -> str:
    if nombre not in _cache["plantillas"]:
        ruta = RUTA_PLANTILLAS / nombre
        if not ruta.is_file():
            raise ValueError("Plantilla inexistente: " + nombre)
        _cache["plantillas"][nombre] = ruta.read_text(encoding="utf-8")
    return _cache["plantillas"][nombre]


def textos() -> dict:
    if _cache["textos"] is None:
        ruta = RUTA_TRADUCCIONES / "es.json"
        if not ruta.is_file():
            raise ValueError("Catalogo de textos ausente: es.json")
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            raise ValueError("es.json debe ser un objeto JSON.")
        _cache["textos"] = datos
    return _cache["textos"]


def _t(clave: str) -> str:
    return str(textos().get(clave, clave))


def rol_principal(identidad) -> str:
    return identidad.roles[0] if identidad.roles else "sin_rol"


def _menus_permitidos(identidad) -> set:
    permitidos = set()
    for rol in identidad.roles:
        permitidos |= set(menus_de(rol))
    return permitidos


def _nav(identidad, menu_activo: str) -> str:
    permitidos = _menus_permitidos(identidad)
    grupos = {}
    for m in MENUS:
        if m["id"] in permitidos:
            grupos.setdefault(m["grupo"], []).append(m)
    partes = []
    for grupo in sorted(grupos):
        partes.append('<div class="grupo"><div class="grupo-titulo">' + escapar(grupo) + "</div>")
        for m in grupos[grupo]:
            clase = "nav-item activo" if m["id"] == menu_activo else "nav-item"
            icono = ICONO_POR_MENU.get(m["id"], "i-home")
            partes.append(
                '<a class="' + clase + '" href="/laboratorio/ui/' + m["id"] + '">'
                + '<svg class="ic" aria-hidden="true"><use href="/laboratorio/ui/assets/icons.svg#' + icono + '"/></svg>'
                + "<span>" + escapar(m["nombre"]) + "</span></a>"
            )
        partes.append("</div>")
    return "\n".join(partes)


def _botones(botones, fase: int, vivo: bool) -> str:
    partes = []
    for b in botones:
        if vivo:
            partes.append(
                '<button class="btn btn-primary" data-accion="' + escapar(b) + '">'
                + escapar(b) + "</button>"
            )
        else:
            partes.append(
                '<button class="btn btn-ghost" disabled title="'
                + escapar(_t("ui.fase") + " " + str(fase)) + '">'
                + escapar(b) + '<span class="badge">F' + str(fase) + "</span></button>"
            )
    return "\n".join(partes)


def _pagina(titulo: str, nav: str, contenido: str, identidad) -> str:
    esqueleto = cargar_plantilla("base.html")
    return render(esqueleto, {
        "titulo": titulo,
        "nav": nav,
        "contenido": contenido,
        "rol_nombre": rol_principal(identidad),
        "zid": identidad.zid,
        "roles": ",".join(identidad.roles),
    })


def _opciones_proyectos(proyectos) -> str:
    if not proyectos:
        return '<option value="">sin proyectos</option>'
    return "".join(
        '<option value="' + escapar(str(p.id)) + '">' + escapar(p.titulo) + "</option>"
        for p in proyectos
    )


def render_home(identidad, repo_proyectos) -> str:
    proyectos = repo_proyectos.listar({"propietario_zid": identidad.zid}, 50, 0)
    filas = []
    for p in proyectos:
        filas.append(
            "<tr><td>" + escapar(p.titulo) + "</td>"
            + '<td><span class="pill">' + escapar(p.tipo_creacion.value) + "</span></td>"
            + "<td>" + escapar(p.etapa_actual.value) + "</td>"
            + '<td><a class="link" href="/laboratorio/api/v1/projects/'
            + str(p.id) + '/scenarios">escenarios</a></td></tr>'
        )
    cuerpo_tabla = "\n".join(filas) or (
        '<tr><td colspan="4" class="vacio">' + escapar(_t("ui.sin_proyectos")) + "</td></tr>"
    )
    seccion_crear = ""
    if identidad.tiene_permiso(PermisoCodigo.PROYECTO_CREAR):
        opciones = "".join(
            '<option value="' + escapar(t.value) + '">' + escapar(t.value) + "</option>"
            for t in CreationType
        )
        seccion_crear = render(cargar_plantilla("crear.html"), {
            "btn_nuevo": _t("ui.nuevo_proyecto"),
            "btn_documento": _t("ui.documento"),
            "btn_simular": _t("ui.simular"),
            "ayuda_doc": _t("ui.ayuda_doc"),
            "titulo_opcional": _t("ui.titulo_opcional"),
            "tipo_auto": _t("ui.tipo_auto"),
            "placeholder_doc": _t("ui.placeholder_doc"),
            "btn_crear_doc": _t("ui.crear_doc"),
            "opciones_tipo": opciones,
        })
    contenido = render(cargar_plantilla("home.html"), {
        "saludo": "Hola, " + identidad.zid,
        "total_proyectos": str(len(proyectos)),
        "seccion_crear": seccion_crear,
        "filas": cuerpo_tabla,
    })
    return _pagina("Inicio - ZYRA LABORATORIO", _nav(identidad, "inicio"), contenido, identidad)


def _tabla_simulacion(identidad, repo_proyectos, repo_escenarios) -> str:
    proyectos = repo_proyectos.listar({"propietario_zid": identidad.zid}, 50, 0)
    filas = []
    for p in proyectos:
        escs = repo_escenarios.listar({"proyecto_id": p.id}, 20, 0)
        resumen = ", ".join(e.tipo.value + ": " + e.titulo for e in escs)
        filas.append(
            "<tr><td>" + escapar(p.titulo) + "</td><td>"
            + escapar(resumen or "sin escenarios") + "</td>"
            + '<td><a class="link" href="/laboratorio/api/v1/projects/'
            + str(p.id) + '/scenarios">ver JSON</a></td></tr>'
        )
    cuerpo = "\n".join(filas) or (
        '<tr><td colspan="3" class="vacio">' + escapar(_t("ui.sin_proyectos")) + "</td></tr>"
    )
    return (
        '<section class="tarjeta"><h2>Proyectos y escenarios (datos reales)</h2>'
        + '<table><thead><tr><th>Proyecto</th><th>Escenarios</th><th>API</th></tr></thead>'
        + "<tbody>" + cuerpo + "</tbody></table></section>"
    )


def _extra_capturar(identidad, repo_proyectos, repo_inputs) -> str:
    proyectos = repo_proyectos.listar({"propietario_zid": identidad.zid}, 50, 0)
    ids = [p.id for p in proyectos]
    entradas = repo_inputs.listar_por_proyectos(ids) if ids else []
    filas = []
    for e in entradas[:20]:
        es_media = e.tipo.value in ("foto", "escaneo")
        contenido = "[sellado " + e.hash_sha256[:12] + "]" if es_media else e.contenido[:80]
        filas.append(
            "<tr><td>" + escapar(e.titulo) + "</td>"
            + '<td><span class="pill">' + escapar(e.tipo.value) + "</span></td>"
            + "<td>" + escapar(contenido) + "</td>"
            + '<td><a class="link" href="/laboratorio/api/v1/inputs/' + str(e.id)
            + '/understand">comprender</a></td></tr>'
        )
    cuerpo = "\n".join(filas) or (
        '<tr><td colspan="4" class="vacio">' + escapar(_t("ui.sin_entradas")) + "</td></tr>"
    )
    tipos = "".join(
        '<option value="' + escapar(t.value) + '">' + escapar(t.value) + "</option>"
        for t in (InputKind.TEXTO, InputKind.FOTO, InputKind.ESCANEO)
    )
    return render(cargar_plantilla("capturar.html"), {
        "ayuda_entrada": _t("ui.ayuda_entrada"),
        "placeholder_entrada": _t("ui.placeholder_entrada"),
        "btn_capturar": _t("ui.btn_capturar"),
        "opciones_proyectos": _opciones_proyectos(proyectos),
        "opciones_tipos": tipos,
        "filas": cuerpo,
    })


def _extra_comprender(identidad, repo_proyectos, repo_comprensiones) -> str:
    proyectos = repo_proyectos.listar({"propietario_zid": identidad.zid}, 50, 0)
    ids = [p.id for p in proyectos]
    comps = repo_comprensiones.listar_por_proyectos(ids) if ids else []
    filas = []
    for c in comps[:20]:
        tipos = ", ".join(sorted({h.get("tipo", "?") for h in c.hallazgos})) or "sin hallazgos"
        filas.append(
            "<tr><td>" + escapar(str(c.entrada_id)) + "</td>"
            + "<td>" + escapar(c.resumen[:80]) + "</td>"
            + '<td><span class="pill">' + escapar(c.dominio) + "</span></td>"
            + "<td>" + str(c.total_hallazgos) + " (" + escapar(tipos) + ")</td>"
            + "<td>" + str(round(c.confianza * 100, 1)) + "%</td></tr>"
        )
    cuerpo = "\n".join(filas) or (
        '<tr><td colspan="5" class="vacio">' + escapar(_t("ui.sin_comprensiones")) + "</td></tr>"
    )
    return render(cargar_plantilla("comprender.html"), {
        "ayuda_comprension": _t("ui.ayuda_comprension"),
        "filas": cuerpo,
    })


def _extra_disenar(identidad, repo_proyectos, repo_disenos) -> str:
    proyectos = repo_proyectos.listar({"propietario_zid": identidad.zid}, 50, 0)
    ids = [p.id for p in proyectos]
    disenos = repo_disenos.listar_por_proyectos(ids) if ids else []
    filas = []
    for b in disenos[:20]:
        nombres = ", ".join(c.get("nombre", "") for c in b.componentes[:5])
        filas.append(
            "<tr><td>" + escapar(b.nombre) + "</td>"
            + '<td><span class="pill">' + escapar(b.tipo_creacion.value) + "</span></td>"
            + "<td>" + str(len(b.componentes)) + " componentes</td>"
            + "<td>" + escapar(nombres) + "</td></tr>"
        )
    cuerpo = "\n".join(filas) or (
        '<tr><td colspan="4" class="vacio">' + escapar(_t("ui.sin_disenos")) + "</td></tr>"
    )
    opciones = "".join(
        '<option value="' + escapar(t.value) + '">' + escapar(t.value) + "</option>"
        for t in CreationType
    )
    return render(cargar_plantilla("disenar.html"), {
        "ayuda_blueprint": _t("ui.ayuda_blueprint"),
        "placeholder_componentes": _t("ui.placeholder_componentes"),
        "btn_disenar": _t("ui.btn_disenar"),
        "opciones_proyectos": _opciones_proyectos(proyectos),
        "opciones_tipo": opciones,
        "filas": cuerpo,
    })


def render_panel(identidad, menu_id: str, sub_nombre: str, repos: dict) -> str:
    if not existe_menu(menu_id):
        raise EntidadNoEncontradaError("Menu inexistente.", menu_id)
    permitidos = _menus_permitidos(identidad)
    if menu_id not in permitidos:
        from apps.laboratorio.shared.exceptions.domain_errors import PermisoDenegadoError
        raise PermisoDenegadoError("Tu rol no tiene acceso al menu " + menu_id + ".")
    menu = next(m for m in MENUS if m["id"] == menu_id)
    fase = FASE_POR_MENU.get(menu_id, 10)
    vivo = menu_id in MENUS_VIVOS
    tabs = []
    for s in menu["submenus"]:
        activa = ' class="tab activo"' if s["nombre"] == sub_nombre else ' class="tab"'
        tabs.append(
            '<a' + activa + ' href="/laboratorio/ui/' + menu_id
            + "?sub=" + quote(s["nombre"]) + '">' + escapar(s["nombre"]) + "</a>"
        )
    tabs_html = "\n".join(tabs) or '<span class="tab activo">Vista general</span>'
    sub_actual = None
    for s in menu["submenus"]:
        if s["nombre"] == sub_nombre:
            sub_actual = s
            break
    if sub_actual is None and menu["submenus"]:
        sub_actual = menu["submenus"][0]
    botones_html = ""
    if sub_actual is not None:
        botones_html = _botones(sub_actual["botones"], fase, vivo)
    estado_html = (
        '<div class="estado ok">' + escapar(_t("ui.en_vivo")) + "</div>"
        if vivo
        else '<div class="estado">' + escapar(_t("ui.fase") + " " + str(fase)) + "</div>"
    )
    extra = ""
    if menu_id == "simular":
        extra = _tabla_simulacion(identidad, repos["proyectos"], repos["escenarios"])
    elif menu_id == "capturar":
        extra = _extra_capturar(identidad, repos["proyectos"], repos["inputs"])
    elif menu_id == "comprender":
        extra = _extra_comprender(identidad, repos["proyectos"], repos["comprensiones"])
    elif menu_id == "disenar":
        extra = _extra_disenar(identidad, repos["proyectos"], repos["disenos"])
    contenido = render(cargar_plantilla("panel.html"), {
        "menu_nombre": menu["nombre"],
        "sub_nombre": sub_actual["nombre"] if sub_actual else "Vista general",
        "tabs": tabs_html,
        "estado": estado_html,
        "botones": botones_html,
        "extra": extra,
    })
    return _pagina(
        menu["nombre"] + " - ZYRA LABORATORIO",
        _nav(identidad, menu_id), contenido, identidad,
    )

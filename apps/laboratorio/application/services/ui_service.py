"""Servicio de UI: construye las vistas desde las fuentes unicas.

Fase 7 EN VIVO: presentar y exportar usan datos reales. Ley 3:
maximo 3 botones de accion por vista. Ley 1: lo no disponible
declara fase.
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

MENUS_VIVOS = ("inicio", "simular", "capturar", "comprender", "disenar",
               "crear", "biblioteca", "cuatro_d", "probar", "comparar",
               "optimizar", "renderizar", "presentar", "exportar")

FORMATOS_GENERACION = (
    ("imagen", "Imagen"), ("pagina", "Pagina"), ("modelo", "Modelo"),
    ("animacion", "Animacion"), ("naked3d", "Naked-3D"),
    ("holograma", "Holograma"), ("oligrama", "Oligrama"),
)

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


def _opciones_escenas(escenas) -> str:
    if not escenas:
        return '<option value="">sin escenas</option>'
    return "".join(
        '<option value="' + escapar(str(s.id)) + '">' + escapar(s.nombre) + "</option>"
        for s in escenas
    )


def _opciones_escenarios(proyectos, repo_escenarios) -> str:
    if not proyectos:
        return '<option value="">sin proyectos</option>'
    opciones = []
    for p in proyectos:
        escs = repo_escenarios.listar({"proyecto_id": p.id}, 50, 0)
        for e in escs:
            opciones.append(
                '<option value="' + escapar(str(e.id)) + '" data-proyecto="'
                + escapar(str(p.id)) + '">' + escapar(
                    p.titulo + " | " + e.tipo.value + ": " + e.titulo
                ) + "</option>"
            )
    if not opciones:
        return '<option value="">sin escenarios</option>'
    return "\n".join(opciones)


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


def _select_formatos() -> str:
    return "".join(
        '<option value="' + escapar(v) + '">' + escapar(nombre) + "</option>"
        for v, nombre in FORMATOS_GENERACION
    )


def _extra_crear(identidad, repos) -> str:
    proyectos = repos["proyectos"].listar({"propietario_zid": identidad.zid}, 50, 0)
    ids = [p.id for p in proyectos]
    escenas = repos["escenas"].listar_por_proyectos(ids) if ids else []
    artefactos = repos["artefactos"].listar_por_proyectos(ids) if ids else []
    filas_esc = []
    for s in escenas[:20]:
        filas_esc.append(
            "<tr><td>" + escapar(s.nombre) + "</td>"
            + "<td>" + str(s.ancho) + "x" + str(s.alto) + "</td>"
            + "<td>" + str(len(s.objetos)) + "</td>"
            + '<td><select class="sel-gen" data-escena="' + escapar(str(s.id)) + '">'
            + _select_formatos()
            + '</select> <button class="btn btn-primary btn-gen" data-generar="'
            + escapar(str(s.id)) + '">Generar</button></td></tr>'
        )
    cuerpo_esc = "\n".join(filas_esc) or (
        '<tr><td colspan="4" class="vacio">' + escapar(_t("ui.sin_escenas")) + "</td></tr>"
    )
    filas_art = []
    for a in artefactos[:20]:
        filas_art.append(
            "<tr><td>" + escapar(a.nombre) + "</td>"
            + '<td><span class="pill">' + escapar(a.formato) + "</span></td>"
            + "<td>" + str(a.tamano_bytes) + " B</td>"
            + '<td><a class="link" href="/laboratorio/api/v1/artifacts/' + str(a.id)
            + '">abrir</a></td></tr>'
        )
    cuerpo_art = "\n".join(filas_art) or (
        '<tr><td colspan="4" class="vacio">' + escapar(_t("ui.sin_artefactos")) + "</td></tr>"
    )
    return render(cargar_plantilla("creacion.html"), {
        "ayuda_escena": _t("ui.ayuda_escena"),
        "placeholder_objetos": _t("ui.placeholder_objetos"),
        "btn_crear_escena": _t("ui.btn_crear_escena"),
        "opciones_proyectos": _opciones_proyectos(proyectos),
        "filas_escenas": cuerpo_esc,
        "filas_artefactos": cuerpo_art,
    })


def _extra_biblioteca(identidad, repos) -> str:
    activos = repos["activos"].listar_por_propietario(identidad.zid)
    filas = []
    for a in activos[:20]:
        filas.append(
            "<tr><td>" + escapar(a.nombre) + "</td>"
            + '<td><span class="pill">' + escapar(a.tipo) + "</span></td>"
            + "<td>" + str(a.tamano_bytes) + " B</td>"
            + "<td>" + escapar(", ".join(a.etiquetas)) + "</td>"
            + "<td>" + escapar(a.hash_sha256[:12]) + "</td></tr>"
        )
    cuerpo = "\n".join(filas) or (
        '<tr><td colspan="5" class="vacio">' + escapar(_t("ui.sin_activos")) + "</td></tr>"
    )
    return render(cargar_plantilla("biblioteca.html"), {
        "ayuda_activo": _t("ui.ayuda_activo"),
        "btn_guardar_activo": _t("ui.btn_guardar_activo"),
        "filas": cuerpo,
    })


def _extra_cuatro_d(identidad, repos) -> str:
    proyectos = repos["proyectos"].listar({"propietario_zid": identidad.zid}, 50, 0)
    ids = [p.id for p in proyectos]
    escenas = repos["escenas"].listar_por_proyectos(ids) if ids else []
    filas_tl = []
    filas_luz = []
    filas_int = []
    for s in escenas[:20]:
        linea = repos["timelines"].obtener_por_escena(s.id)
        if linea is not None:
            filas_tl.append(
                "<tr><td>" + escapar(s.nombre) + "</td>"
                + "<td>" + str(linea.duracion_s) + "s @ " + str(linea.fps) + "fps</td>"
                + "<td>" + str(len(linea.pistas)) + " pistas / "
                + str(linea.total_keyframes) + " keyframes</td></tr>"
            )
        luz = repos["luces"].obtener_por_escena(s.id)
        if luz is not None:
            filas_luz.append(
                "<tr><td>" + escapar(s.nombre) + "</td>"
                + "<td>" + str(len(luz.pasos)) + " pasos</td>"
                + '<td><span class="pill">' + escapar(luz.color_dominate) + "</span></td></tr>"
            )
        zonas = repos["interacciones"].listar_por_escena(s.id)
        for z in zonas[:5]:
            filas_int.append(
                "<tr><td>" + escapar(s.nombre) + "</td>"
                + "<td>" + escapar(z.titulo) + "</td>"
                + '<td><span class="pill">' + escapar(z.accion) + "</span></td>"
                + "<td>" + escapar("(%.0f,%.0f %.0fx%.0f)" % (z.x, z.y, z.w, z.h)) + "</td></tr>"
            )
    cuerpo_tl = "\n".join(filas_tl) or (
        '<tr><td colspan="3" class="vacio">' + escapar(_t("ui.sin_timelines")) + "</td></tr>"
    )
    cuerpo_luz = "\n".join(filas_luz) or (
        '<tr><td colspan="3" class="vacio">' + escapar(_t("ui.sin_luces")) + "</td></tr>"
    )
    cuerpo_int = "\n".join(filas_int) or (
        '<tr><td colspan="4" class="vacio">' + escapar(_t("ui.sin_interacciones")) + "</td></tr>"
    )
    return render(cargar_plantilla("cuatro_d.html"), {
        "ayuda_4d": _t("ui.ayuda_4d"),
        "ayuda_luz": _t("ui.ayuda_luz"),
        "ayuda_interaccion": _t("ui.ayuda_interaccion"),
        "btn_timeline": _t("ui.btn_timeline"),
        "btn_luz": _t("ui.btn_luz"),
        "btn_interaccion": _t("ui.btn_interaccion"),
        "opciones_escenas": _opciones_escenas(escenas),
        "filas_timelines": cuerpo_tl,
        "filas_luces": cuerpo_luz,
        "filas_interacciones": cuerpo_int,
    })


def _extra_simular(identidad, repos) -> str:
    proyectos = repos["proyectos"].listar({"propietario_zid": identidad.zid}, 50, 0)
    ids = [p.id for p in proyectos]
    sims = repos["simulaciones"].listar_por_proyectos(ids) if ids else []
    filas_sim = []
    for s in sims[:20]:
        m = s.metricas or {}
        filas_sim.append(
            "<tr><td>" + escapar(str(s.escenario_id)) + "</td>"
            + "<td>" + str(s.horizonte_anios) + " anios (+" + str(s.crecimiento_pct) + "%)</td>"
            + "<td>" + escapar("equilibrio: anio " + str(m.get("punto_equilibrio_anio", 0))
                               + " · ROI " + str(m.get("roi_pct", 0)) + "% · "
                               + str(m.get("tendencia", "-"))) + "</td>"
            + "<td>" + str(round(float(m.get("puntaje_final", 0.0)), 1)) + "</td></tr>"
        )
    cuerpo_sim = "\n".join(filas_sim) or (
        '<tr><td colspan="4" class="vacio">' + escapar(_t("ui.sin_simulaciones")) + "</td></tr>"
    )
    return render(cargar_plantilla("simular.html"), {
        "ayuda_simular": _t("ui.ayuda_simular"),
        "btn_simular_evolucion": _t("ui.btn_simular_evolucion"),
        "opciones_escenarios": _opciones_escenarios(proyectos, repos["escenarios"]),
        "filas_simulaciones": cuerpo_sim,
    })


def _extra_probar(identidad, repos) -> str:
    proyectos = repos["proyectos"].listar({"propietario_zid": identidad.zid}, 50, 0)
    filas = []
    for p in proyectos[:20]:
        evaluaciones = repos["evaluaciones"].listar({"proyecto_id": p.id}, 20, 0)
        for ev in evaluaciones[:5]:
            m = ev.metricas or {}
            filas.append(
                "<tr><td>" + escapar(p.titulo) + "</td>"
                + "<td>" + escapar(str(ev.escenario_id)) + "</td>"
                + "<td>" + str(round(ev.puntaje_total, 2)) + "</td>"
                + "<td>" + escapar("costo " + str(m.get("costo", "-"))
                                   + " · beneficio " + str(m.get("beneficio", "-"))
                                   + " · riesgo " + str(m.get("riesgo", "-"))) + "</td></tr>"
            )
    cuerpo = "\n".join(filas) or (
        '<tr><td colspan="4" class="vacio">' + escapar(_t("ui.sin_evaluaciones")) + "</td></tr>"
    )
    return (
        '<p class="ayuda">' + escapar(_t("ui.ayuda_probar")) + "</p>"
        '<section class="tarjeta"><h2>Evaluaciones reales (formula oficial)</h2>'
        + '<table><thead><tr><th>Proyecto</th><th>Escenario</th><th>Puntaje</th><th>Dimensiones</th></tr></thead>'
        + "<tbody>" + cuerpo + "</tbody></table></section>"
    )


def _extra_comparar(identidad, repos) -> str:
    proyectos = repos["proyectos"].listar({"propietario_zid": identidad.zid}, 50, 0)
    ids = [p.id for p in proyectos]
    comparaciones = repos["comparaciones"].listar_por_proyectos(ids) if ids else []
    filas = []
    for c in comparaciones[:20]:
        ganador_titulo = ""
        for p in c.participantes:
            if str(p.get("escenario_id", "")) == c.ganador:
                ganador_titulo = p.get("titulo", "")
                break
        filas.append(
            "<tr><td>" + escapar(ganador_titulo or c.ganador) + "</td>"
            + '<td><span class="pill">+' + escapar(c.brecha) + "</span></td>"
            + "<td>" + str(len(c.participantes)) + " escenarios</td>"
            + '<td><a class="link" href="/laboratorio/api/v1/comparisons/'
            + str(c.id) + '/report.html">informe</a></td></tr>'
        )
    cuerpo = "\n".join(filas) or (
        '<tr><td colspan="4" class="vacio">' + escapar(_t("ui.sin_comparaciones")) + "</td></tr>"
    )
    return render(cargar_plantilla("comparar.html"), {
        "ayuda_comparar": _t("ui.ayuda_comparar"),
        "btn_comparar": _t("ui.btn_comparar"),
        "opciones_proyectos": _opciones_proyectos(proyectos),
        "filas": cuerpo,
    })


def _extra_optimizar(identidad, repos) -> str:
    proyectos = repos["proyectos"].listar({"propietario_zid": identidad.zid}, 50, 0)
    ids = [p.id for p in proyectos]
    propuestas = repos["optimizaciones"].listar_por_proyectos(ids) if ids else []
    filas = []
    for o in propuestas[:20]:
        estado_pill = "ok" if o.estado == "aplicada" else "pill"
        boton = ""
        if o.estado == "sugerida":
            boton = ('<button class="btn btn-primary btn-gen" data-aplicar="'
                     + escapar(str(o.id)) + '">Aplicar</button>')
        filas.append(
            "<tr><td>" + escapar(str(o.escenario_id)) + "</td>"
            + "<td>" + str(round(o.puntaje_actual, 1)) + " → "
            + str(round(o.puntaje_proyectado, 1)) + " (+" + str(o.mejora_estimada) + ")</td>"
            + "<td>" + str(len(o.recomendaciones)) + " acciones</td>"
            + '<td><span class="' + estado_pill + '">' + escapar(o.estado) + "</span></td>"
            + "<td>" + boton + "</td></tr>"
        )
    cuerpo = "\n".join(filas) or (
        '<tr><td colspan="5" class="vacio">' + escapar(_t("ui.sin_optimizaciones")) + "</td></tr>"
    )
    return render(cargar_plantilla("optimizar.html"), {
        "ayuda_optimizar": _t("ui.ayuda_optimizar"),
        "btn_optimizar": _t("ui.btn_optimizar"),
        "opciones_escenarios": _opciones_escenarios(proyectos, repos["escenarios"]),
        "filas": cuerpo,
    })


def _extra_renderizar(identidad, repos) -> str:
    proyectos = repos["proyectos"].listar({"propietario_zid": identidad.zid}, 50, 0)
    ids = [p.id for p in proyectos]
    escenas = repos["escenas"].listar_por_proyectos(ids) if ids else []
    resumenes = repos["renders"].listar_resumen_por_proyectos(ids) if ids else []
    filas_r = []
    for r in resumenes[:20]:
        prof = "si" if r.get("con_profundidad") else "no"
        filas_r.append(
            "<tr><td>" + escapar(str(r["escena_id"])) + "</td>"
            + '<td><span class="pill">' + escapar(r["calidad"]) + "</span></td>"
            + "<td>" + str(r["ancho"]) + "x" + str(r["alto"]) + " · "
            + str(round(float(r["duracion_ms"]), 1)) + " ms</td>"
            + "<td>prof: " + prof + "</td>"
            + '<td><a class="link" href="/laboratorio/api/v1/renders/' + str(r["id"])
            + '">imagen</a>'
            + (' <a class="link" href="/laboratorio/api/v1/renders/' + str(r["id"])
               + '/depth.png">profundidad</a>' if r.get("con_profundidad") else "")
            + "</td></tr>"
        )
    cuerpo_r = "\n".join(filas_r) or (
        '<tr><td colspan="5" class="vacio">' + escapar(_t("ui.sin_renders")) + "</td></tr>"
    )
    return render(cargar_plantilla("renderizar.html"), {
        "ayuda_renderizar": _t("ui.ayuda_renderizar"),
        "btn_renderizar": _t("ui.btn_renderizar"),
        "opciones_escenas": _opciones_escenas(escenas),
        "filas_renders": cuerpo_r,
    })


def _extra_presentar(identidad, repos) -> str:
    proyectos = repos["proyectos"].listar({"propietario_zid": identidad.zid}, 50, 0)
    ids = [p.id for p in proyectos]
    escenas = repos["escenas"].listar_por_proyectos(ids) if ids else []
    presentaciones = repos["presentaciones"].listar_por_proyectos(ids) if ids else []
    filas = []
    for p in presentaciones[:20]:
        estado = (
            '<span class="ok">sellada</span>' if p.sellada
            else '<span class="pill">borrador</span>'
        )
        filas.append(
            "<tr><td>" + escapar(p.titulo) + "</td>"
            + "<td>" + str(len(p.pasos)) + " pasos · "
            + str(round(p.duracion_total, 1)) + "s</td>"
            + "<td>" + estado + "</td>"
            + '<td><a class="link" href="/laboratorio/api/v1/presentations/'
            + str(p.id) + '/play">reproducir</a></td></tr>'
        )
    cuerpo = "\n".join(filas) or (
        '<tr><td colspan="4" class="vacio">' + escapar(_t("ui.sin_presentaciones")) + "</td></tr>"
    )
    opciones_pasos = "\n".join(
        '<option value="' + escapar(str(s.id)) + '" data-proyecto="'
        + escapar(str(s.proyecto_id)) + '">' + escapar(s.nombre) + "</option>"
        for s in escenas[:10]
    ) or '<option value="">sin escenas</option>'
    opciones_presentaciones = "\n".join(
        '<option value="' + escapar(str(p.id)) + '" data-proyecto="'
        + escapar(str(p.proyecto_id)) + '">'
        + escapar(p.titulo + (" (sellada)" if p.sellada else "")) + "</option>"
        for p in presentaciones if not p.sellada
    ) or '<option value="">sin presentaciones por sellar</option>'
    return render(cargar_plantilla("presentar.html"), {
        "ayuda_presentar": _t("ui.ayuda_presentar"),
        "btn_crear_presentacion": _t("ui.btn_crear_presentacion"),
        "btn_sellar": _t("ui.btn_sellar"),
        "opciones_proyectos": _opciones_proyectos(proyectos),
        "opciones_pasos": opciones_pasos,
        "opciones_presentaciones": opciones_presentaciones,
        "filas": cuerpo,
    })


def _extra_exportar(identidad, repos) -> str:
    proyectos = repos["proyectos"].listar({"propietario_zid": identidad.zid}, 50, 0)
    ids = [p.id for p in proyectos]
    exportaciones = repos["exportaciones"].listar_por_proyectos(ids) if ids else []
    filas = []
    for e in exportaciones[:20]:
        filas.append(
            "<tr><td>" + escapar(e.tipo) + "</td>"
            + "<td>" + escapar(e.destino or "-") + "</td>"
            + "<td>" + str(len(e.piezas)) + " piezas · "
            + str(e.tamano_total) + " B</td>"
            + "<td>" + escapar(e.hash_sha256[:12]) + "</td></tr>"
        )
    cuerpo = "\n".join(filas) or (
        '<tr><td colspan="4" class="vacio">' + escapar(_t("ui.sin_exports")) + "</td></tr>"
    )
    return render(cargar_plantilla("exportar.html"), {
        "ayuda_exportar": _t("ui.ayuda_exportar"),
        "btn_exportar": _t("ui.btn_exportar"),
        "opciones_proyectos": _opciones_proyectos(proyectos),
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
        extra = _extra_simular(identidad, repos)
    elif menu_id == "capturar":
        extra = _extra_capturar(identidad, repos["proyectos"], repos["inputs"])
    elif menu_id == "comprender":
        extra = _extra_comprender(identidad, repos["proyectos"], repos["comprensiones"])
    elif menu_id == "disenar":
        extra = _extra_disenar(identidad, repos["proyectos"], repos["disenos"])
    elif menu_id == "crear":
        extra = _extra_crear(identidad, repos)
    elif menu_id == "biblioteca":
        extra = _extra_biblioteca(identidad, repos)
    elif menu_id == "cuatro_d":
        extra = _extra_cuatro_d(identidad, repos)
    elif menu_id == "probar":
        extra = _extra_probar(identidad, repos)
    elif menu_id == "comparar":
        extra = _extra_comparar(identidad, repos)
    elif menu_id == "optimizar":
        extra = _extra_optimizar(identidad, repos)
    elif menu_id == "renderizar":
        extra = _extra_renderizar(identidad, repos)
    elif menu_id == "presentar":
        extra = _extra_presentar(identidad, repos)
    elif menu_id == "exportar":
        extra = _extra_exportar(identidad, repos)
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

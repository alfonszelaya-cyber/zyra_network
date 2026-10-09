"""Catalogo descriptivo de permisos (los codigos viven en constants)."""

from apps.laboratorio.constants.permissions.permission_codes import PermisoCodigo

DESCRIPCIONES = {
    PermisoCodigo.VER: "Ver contenidos segun rol",
    PermisoCodigo.PROYECTO_CREAR: "Crear proyectos",
    PermisoCodigo.PROYECTO_EDITAR: "Editar proyectos propios",
    PermisoCodigo.CAPTURAR: "Capturar entradas (describir, foto, escaneo, medicion)",
    PermisoCodigo.DISENAR: "Disenar blueprints y componentes",
    PermisoCodigo.CREAR_CONTENIDO: "Generar imagenes, video, paginas y modelos",
    PermisoCodigo.EDITAR_4D: "Editar tiempo, luz, interaccion y camara",
    PermisoCodigo.SIMULAR: "Crear y ejecutar escenarios A/B/C",
    PermisoCodigo.EVALUAR: "Evaluar escenarios con evaluate_scenario",
    PermisoCodigo.COMPARAR: "Comparar resultados de escenarios",
    PermisoCodigo.OPTIMIZAR: "Sugerir y aplicar optimizaciones",
    PermisoCodigo.RENDERIZAR: "Renderizar en la escalera de calidad",
    PermisoCodigo.PRESENTAR: "Construir y ensayar presentaciones",
    PermisoCodigo.PROYECTAR: "Operar proyeccion en superficies",
    PermisoCodigo.EXPORTAR: "Exportar entregables y bundles",
    PermisoCodigo.BIBLIOTECA_GESTIONAR: "Gestionar activos y plantillas",
    PermisoCodigo.RED_CONTRATOS: "Operar contratos con otras apps ZYRA",
    PermisoCodigo.GOBIERNO_TOTAL: "Gobierno total del sistema",
}


def catalogo() -> list:
    return [
        {"codigo": c, "descripcion": DESCRIPCIONES.get(c, "")}
        for c in PermisoCodigo.TODOS
    ]


def validar_codigo(codigo: str) -> bool:
    return codigo in PermisoCodigo.TODOS

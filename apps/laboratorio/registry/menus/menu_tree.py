"""DUENO UNICO del arbol de menus de LABORATORIO (Ley 3: max 3 botones)."""

MENUS = (
    {"id": "inicio", "numero": 0, "nombre": "Inicio", "grupo": "general", "submenus": ()},
    {"id": "capturar", "numero": 1, "nombre": "Capturar", "grupo": "captura", "submenus": (
        {"nombre": "Describir", "botones": ("Redactar", "Desde ZYRA", "Guardar")},
        {"nombre": "Fotografiar", "botones": ("Camara", "Subir", "Analizar")},
        {"nombre": "Escanear", "botones": ("Iniciar", "Importar nube", "Ajustar")},
        {"nombre": "Medir", "botones": ("Medir", "Importar plano", "Validar")},
        {"nombre": "Importar", "botones": ("Archivo", "De otra app", "Vincular")},
    )},
    {"id": "comprender", "numero": 2, "nombre": "Comprender", "grupo": "captura", "submenus": (
        {"nombre": "Analisis", "botones": ("Analizar entrada", "Ver hallazgos", "Confirmar")},
    )},
    {"id": "disenar", "numero": 3, "nombre": "Disenar", "grupo": "creacion", "submenus": (
        {"nombre": "Blueprint", "botones": ("Nuevo", "Elegir tipo", "Estructurar")},
        {"nombre": "Componentes", "botones": ("Anadir", "Editar", "Quitar")},
        {"nombre": "Requisitos", "botones": ("Definir", "Validar", "Guardar")},
    )},
    {"id": "crear", "numero": 4, "nombre": "Crear", "grupo": "creacion", "submenus": (
        {"nombre": "Escena 3D", "botones": ("Construir", "Importar modelo", "Materiales")},
        {"nombre": "Imagen", "botones": ("Generar", "Ajustar", "Guardar")},
        {"nombre": "Video", "botones": ("Secuencia", "Generar", "Guardar")},
        {"nombre": "Pagina", "botones": ("Generar", "Editar", "Publicar")},
        {"nombre": "Modelo", "botones": ("Generar", "Exportar", "Versionar")},
    )},
    {"id": "cuatro_d", "numero": 5, "nombre": "4D", "grupo": "creacion", "submenus": (
        {"nombre": "Tiempo", "botones": ("Nueva linea", "Anadir pista", "Previsualizar")},
        {"nombre": "Luz", "botones": ("Anadir luz", "Programar", "Previsualizar")},
        {"nombre": "Interaccion", "botones": ("Anadir", "Probar", "Publicar")},
        {"nombre": "Camara", "botones": ("Recorrido", "Puntos de vista", "Grabar")},
    )},
    {"id": "simular", "numero": 6, "nombre": "Simular", "grupo": "decision", "submenus": (
        {"nombre": "Escenarios", "botones": ("Nuevo A/B/C", "Ejecutar", "Resultados")},
        {"nombre": "Evolucion", "botones": ("Horizonte", "Ejecutar", "Pelicula")},
        {"nombre": "Dominio", "botones": ("Elegir", "Configurar", "Ejecutar")},
    )},
    {"id": "probar", "numero": 7, "nombre": "Probar", "grupo": "decision", "submenus": (
        {"nombre": "Pruebas", "botones": ("Definir", "Ejecutar", "Informe")},
        {"nombre": "Evaluacion", "botones": ("Evaluar", "Metricas", "Riesgos")},
    )},
    {"id": "comparar", "numero": 8, "nombre": "Comparar", "grupo": "decision", "submenus": (
        {"nombre": "Comparacion", "botones": ("Seleccionar", "Comparar", "Informe")},
    )},
    {"id": "optimizar", "numero": 9, "nombre": "Optimizar", "grupo": "decision", "submenus": (
        {"nombre": "Mejoras", "botones": ("Sugerir mejoras", "Aplicar", "Re-evaluar")},
    )},
    {"id": "renderizar", "numero": 10, "nombre": "Renderizar", "grupo": "visual", "submenus": (
        {"nombre": "Calidad", "botones": ("Borrador", "Alta", "Fotorreal")},
        {"nombre": "Fotograma", "botones": ("Renderizar", "Ver", "Sellar")},
        {"nombre": "Secuencia", "botones": ("Rango", "Renderizar todo", "Progreso")},
        {"nombre": "Profundidad", "botones": ("Activar canal", "Ver mapa", "Exportar")},
    )},
    {"id": "presentar", "numero": 11, "nombre": "Presentar", "grupo": "entrega", "submenus": (
        {"nombre": "Crear", "botones": ("Nueva", "Anadir paso", "Ordenar")},
        {"nombre": "Ensayar", "botones": ("Reproducir", "Tiempo", "Notas")},
        {"nombre": "Sellar", "botones": ("Sellar en ZYRA", "Compartir", "Historial")},
    )},
    {"id": "proyectar", "numero": 12, "nombre": "Proyectar", "grupo": "entrega", "submenus": (
        {"nombre": "Superficie", "botones": ("Escanear", "Ver modelo", "Guardar")},
        {"nombre": "Calibrar", "botones": ("Proyector", "Calibrar", "Probar")},
        {"nombre": "Multi-superficie", "botones": ("Agrupar", "Bordes", "Color")},
        {"nombre": "En vivo", "botones": ("Iniciar", "Previsualizar", "Detener")},
    )},
    {"id": "salidas", "numero": 13, "nombre": "Salidas", "grupo": "entrega", "submenus": (
        {"nombre": "Registrar", "botones": ("Detectar", "Registrar", "Probar")},
        {"nombre": "Destino", "botones": ("Pantalla", "Proyector", "Holo/LF/AR-VR")},
        {"nombre": "Estado", "botones": ("Ver", "Cambiar", "Historial")},
    )},
    {"id": "exportar", "numero": 14, "nombre": "Exportar", "grupo": "entrega", "submenus": (
        {"nombre": "Entregables", "botones": ("Imagen/Video/Pagina", "Modelo/Bundle", "Enviar a ZYRA")},
    )},
    {"id": "biblioteca", "numero": 15, "nombre": "Biblioteca", "grupo": "sistema", "submenus": (
        {"nombre": "Activos", "botones": ("Buscar", "Subir", "Etiquetar")},
        {"nombre": "Plantillas", "botones": ("Usar", "Crear", "Destacar")},
        {"nombre": "Historial", "botones": ("Ver", "Restaurar", "Versiones")},
    )},
    {"id": "red", "numero": 16, "nombre": "Red", "grupo": "sistema", "submenus": (
        {"nombre": "Contratos", "botones": ("Ver", "Solicitar datos", "Publicar indicador")},
        {"nombre": "Confianza", "botones": ("Sellar", "Verificar", "Cadena")},
        {"nombre": "GOV-DATA", "botones": ("Publicar", "Indicadores", "Estado")},
    )},
    {"id": "gobierno", "numero": 17, "nombre": "Gobierno", "grupo": "sistema", "submenus": (
        {"nombre": "Roles", "botones": ("Ver", "Asignar", "Revocar")},
        {"nombre": "Permisos", "botones": ("Matriz", "Reglas", "Auditoria")},
        {"nombre": "Sistema", "botones": ("Motores", "Configuracion", "Diagnostico")},
    )},
)


def arbol() -> tuple:
    return MENUS


def ids() -> tuple:
    return tuple(m["id"] for m in MENUS)


def existe(id_menu: str) -> bool:
    return id_menu in ids()


def validar() -> dict:
    vistos = set()
    for m in MENUS:
        if m["id"] in vistos:
            raise ValueError("Menu duplicado: " + m["id"])
        vistos.add(m["id"])
    numeros = sorted(m["numero"] for m in MENUS)
    if numeros != list(range(len(MENUS))):
        raise ValueError("Los numeros de menu deben ser 0..n-1.")
    botones = 0
    for m in MENUS:
        for sub in m["submenus"]:
            if not sub["botones"] or len(sub["botones"]) > 3:
                raise ValueError("Ley 3 violada en " + m["id"] + "/" + sub["nombre"])
            botones += len(sub["botones"])
    return {
        "menus": len(MENUS),
        "submenus": sum(len(m["submenus"]) for m in MENUS),
        "botones": botones,
    }


def botones_total() -> int:
    return validar()["botones"]

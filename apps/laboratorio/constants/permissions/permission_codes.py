"""Codigos de permiso oficiales de LABORATORIO."""


class PermisoCodigo:
    """Catalogo plano: laboratorio.<recurso>.<accion>."""

    VER = "laboratorio.ver"
    PROYECTO_CREAR = "laboratorio.proyecto.crear"
    PROYECTO_EDITAR = "laboratorio.proyecto.editar"
    CAPTURAR = "laboratorio.capturar"
    DISENAR = "laboratorio.disenar"
    CREAR_CONTENIDO = "laboratorio.crear_contenido"
    EDITAR_4D = "laboratorio.editar_4d"
    SIMULAR = "laboratorio.simular"
    EVALUAR = "laboratorio.evaluar"
    COMPARAR = "laboratorio.comparar"
    OPTIMIZAR = "laboratorio.optimizar"
    RENDERIZAR = "laboratorio.renderizar"
    PRESENTAR = "laboratorio.presentar"
    PROYECTAR = "laboratorio.proyectar"
    EXPORTAR = "laboratorio.exportar"
    BIBLIOTECA_GESTIONAR = "laboratorio.biblioteca.gestionar"
    RED_CONTRATOS = "laboratorio.red.contratos"
    GOBIERNO_TOTAL = "laboratorio.gobierno.total"

    TODOS = (
        VER, PROYECTO_CREAR, PROYECTO_EDITAR, CAPTURAR, DISENAR,
        CREAR_CONTENIDO, EDITAR_4D, SIMULAR, EVALUAR, COMPARAR,
        OPTIMIZAR, RENDERIZAR, PRESENTAR, PROYECTAR, EXPORTAR,
        BIBLIOTECA_GESTIONAR, RED_CONTRATOS, GOBIERNO_TOTAL,
    )

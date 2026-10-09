"""Modulo vertical de CAPTURA: manifiesto + router de documentos."""

from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="capture",
        nombre="Captura",
        version="0.1.0",
        descripcion="Capturador de documentos: cualquier texto se convierte en proyecto",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import documents as r_documents
    return (r_documents,)


def conectar(app) -> None:
    """Registra el modulo y conecta sus routers."""
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

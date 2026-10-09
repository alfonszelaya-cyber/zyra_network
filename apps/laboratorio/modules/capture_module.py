"""Modulo vertical de CAPTURA: documentos y entradas de material."""
from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="capture",
        nombre="Captura",
        version="0.2.0",
        descripcion="Captura de documentos, texto y foto con sellado SHA-256",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import documents as r_documents
    return (r_documents,)


def conectar(app) -> None:
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

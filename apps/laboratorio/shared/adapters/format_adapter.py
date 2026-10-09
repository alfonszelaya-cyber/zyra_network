"""Dueño unico del mapa ExportFormat -> extension/mime/binario."""
from apps.laboratorio.shared.enums.export_format import ExportFormat

_MAPA = {
    ExportFormat.SVG: ("svg", "image/svg+xml", False),
    ExportFormat.PNG: ("png", "image/png", True),
    ExportFormat.JPEG: ("jpg", "image/jpeg", True),
    ExportFormat.VIDEO_MP4: ("mp4", "video/mp4", True),
    ExportFormat.PAGINA_HTML: ("html", "text/html", False),
    ExportFormat.MODELO_3D: ("gltf", "model/gltf+json", False),
    ExportFormat.BUNDLE_VERIFICABLE: ("bundle.json", "application/json", False),
    ExportFormat.DOSSIER: ("dossier.html", "text/html", False),
}


class AdaptadorFormato:
    """Traduccion oficial de formatos de exportacion."""

    @staticmethod
    def _entrada(formato):
        formato_enum = ExportFormat(formato) if isinstance(formato, str) else formato
        if not isinstance(formato_enum, ExportFormat) or formato_enum not in _MAPA:
            raise ValueError("Formato sin mapeo oficial: " + repr(formato))
        return _MAPA[formato_enum]

    @staticmethod
    def extension(formato) -> str:
        """Extension de archivo oficial del formato."""
        return AdaptadorFormato._entrada(formato)[0]

    @staticmethod
    def mime(formato) -> str:
        """Tipo MIME oficial del formato."""
        return AdaptadorFormato._entrada(formato)[1]

    @staticmethod
    def es_binario(formato) -> bool:
        """True si el formato se sirve como bytes binarios."""
        return AdaptadorFormato._entrada(formato)[2]

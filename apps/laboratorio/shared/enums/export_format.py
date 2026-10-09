"""Formatos de exportacion de LABORATORIO."""

from enum import Enum


class ExportFormat(str, Enum):
    """Salidas que los motores de exportacion pueden producir."""

    SVG = "svg"
    PNG = "png"
    JPEG = "jpeg"
    VIDEO_MP4 = "video_mp4"
    PAGINA_HTML = "pagina_html"
    MODELO_3D = "modelo_3d"
    BUNDLE_VERIFICABLE = "bundle_verificable"
    DOSSIER = "dossier"

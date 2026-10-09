"""Errores de las cadenas de trabajo (pipeline D1 y proyeccion)."""

from apps.laboratorio.shared.exceptions.base import LaboratorioError


class EtapaInvalidaError(LaboratorioError):
    """La etapa solicitada no existe en la cadena."""

    codigo = "etapa_invalida"


class PipelineNoIniciadoError(LaboratorioError):
    """Se pidio avanzar sin haber iniciado la cadena."""

    codigo = "pipeline_no_iniciado"


class SuperficieNoCalibradaError(LaboratorioError):
    """Proyeccion solicitada sin calibracion previa."""

    codigo = "superficie_no_calibrada"


class DestinoNoDisponibleError(LaboratorioError):
    """El destino de salida no esta disponible (Ley 1: honesto)."""

    codigo = "destino_no_disponible"

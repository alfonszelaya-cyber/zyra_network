"""Politica de retencion: limites de versiones, historial y archivo."""
from datetime import datetime, timedelta, timezone


class PoliticaRetencion:
    """Limites oficiales de conservacion de LABORATORIO."""

    VERSIONES_MAXIMAS = 50
    ENTRADAS_HISTORIAL_POR_PROYECTO = 5000
    DIAS_ARCHIVADO = 365

    @staticmethod
    def conservar_ultimas(elementos, maximo: int) -> list:
        """Devuelve solo los ultimos N elementos en orden."""
        if not isinstance(maximo, int) or isinstance(maximo, bool) or maximo < 1:
            raise ValueError("maximo debe ser entero positivo.")
        return list(elementos)[-maximo:]

    @staticmethod
    def requiere_archivado(fecha: datetime, ahora: datetime = None, dias: int = None) -> bool:
        """True si la fecha supera la ventana de archivado oficial."""
        limite = dias or PoliticaRetencion.DIAS_ARCHIVADO
        if not isinstance(limite, int) or limite < 1:
            raise ValueError("dias debe ser entero positivo.")
        referencia = ahora or datetime.now(timezone.utc)
        if not isinstance(fecha, datetime):
            raise ValueError("fecha debe ser datetime.")
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return (referencia - fecha) > timedelta(days=limite)

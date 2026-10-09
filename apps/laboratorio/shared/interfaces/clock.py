"""Puerto del reloj del sistema (testeable, sin datetime.now directo)."""
import abc
from datetime import datetime


class Reloj(abc.ABC):
    """Contrato de obtencion del tiempo actual."""

    @abc.abstractmethod
    def ahora(self) -> datetime:
        """Momento actual con zona horaria."""

    def fecha_iso(self) -> str:
        """Momento actual en formato ISO 8601."""
        return self.ahora().isoformat()

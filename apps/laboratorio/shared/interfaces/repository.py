"""Puerto de repositorio: contrato de persistencia de agregados."""
import abc
from typing import Any, Dict, List, Optional


class Repositorio(abc.ABC):
    """Contrato minimo de todo repositorio de LABORATORIO."""

    @abc.abstractmethod
    def agregar(self, entidad: Any) -> Any:
        """Persiste una entidad nueva."""

    @abc.abstractmethod
    def obtener_por_id(self, id_entidad: Any) -> Optional[Any]:
        """Devuelve la entidad o None si no existe."""

    @abc.abstractmethod
    def listar(self, filtros: Optional[Dict[str, Any]] = None, limite: int = 20, offset: int = 0) -> List[Any]:
        """Lista entidades con filtros y paginacion."""

    @abc.abstractmethod
    def actualizar(self, entidad: Any) -> Any:
        """Actualiza una entidad existente."""

    @abc.abstractmethod
    def eliminar(self, id_entidad: Any) -> bool:
        """Elimina por id; True si existia."""

    def existe(self, id_entidad: Any) -> bool:
        """Comprueba existencia via obtener_por_id."""
        return self.obtener_por_id(id_entidad) is not None

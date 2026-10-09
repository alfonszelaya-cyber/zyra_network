"""Paginacion estandar para consultas de listas."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Pagina:
    """Resultado paginado generico."""

    items: List = field(default_factory=list)
    total: int = 0
    pagina: int = 1
    por_pagina: int = 20

    def __post_init__(self):
        if self.pagina < 1:
            raise ValueError("pagina debe ser mayor o igual a 1.")
        if self.por_pagina < 1 or self.por_pagina > 100:
            raise ValueError("por_pagina debe estar entre 1 y 100.")

    @property
    def total_paginas(self) -> int:
        """Numero total de paginas."""
        if self.total == 0:
            return 0
        return (self.total + self.por_pagina - 1) // self.por_pagina

    @property
    def hay_mas(self) -> bool:
        """Indica si existe una pagina siguiente."""
        return self.pagina < self.total_paginas

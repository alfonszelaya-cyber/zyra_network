"""Alias de tipos para datos JSON seguros."""

from typing import Any, Dict, List, Union

ValorJSON = Union[None, bool, int, float, str, List[Any], Dict[str, Any]]
ObjetoJSON = Dict[str, Any]
ListaJSON = List[ValorJSON]

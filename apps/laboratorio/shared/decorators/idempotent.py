"""Decorador idempotente: repetir la llamada no repite el efecto."""
import functools


def idempotente(func):
    """Cachea por argumentos; la segunda llamada devuelve sin ejecutar."""

    cache = {}

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        clave = (
            func.__module__,
            func.__qualname__,
            repr(args),
            tuple(sorted((k, repr(v)) for k, v in kwargs.items())),
        )
        if clave in cache:
            wrapper.aciertos += 1
            return cache[clave]
        resultado = func(*args, **kwargs)
        cache[clave] = resultado
        wrapper.ejecuciones += 1
        return resultado

    wrapper.ejecuciones = 0
    wrapper.aciertos = 0
    wrapper.limpiar = cache.clear
    return wrapper

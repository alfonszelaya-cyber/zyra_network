"""Decorador cronometrado: mide la duracion real de cada llamada."""
import functools
import time


def cronometrado(func):
    """Registra la duracion en ms del ultimo llamado en el wrapper."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        inicio = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            wrapper.ultima_duracion_ms = round(
                (time.perf_counter() - inicio) * 1000.0, 3
            )

    wrapper.ultima_duracion_ms = 0.0
    return wrapper

"""Decorador auditado: registra duracion y error de cada llamada."""
import functools
import time


def auditado(registrador=None):
    """Fábrica: registrador(dict) recibe el reporte de cada llamada."""

    def decorador(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            inicio = time.perf_counter()
            error = None
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                error = type(exc).__name__ + ": " + str(exc)
                raise
            finally:
                if registrador is not None:
                    registrador(
                        {
                            "funcion": func.__qualname__,
                            "duracion_ms": round(
                                (time.perf_counter() - inicio) * 1000.0, 3
                            ),
                            "error": error,
                        }
                    )

        return wrapper

    return decorador

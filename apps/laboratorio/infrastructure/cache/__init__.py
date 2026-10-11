"""Cache TTL en memoria: real, con expiracion y estadisticas.

- time.monotonic (inmune a cambios de reloj del sistema)
- expiracion perezosa en lectura + barrido en escritura
- maxlen con eviction FIFO
- estadisticas honestas: hits, misses, expiraciones, evictions
- seguro para hilos (Lock)
"""
import threading
import time


class CacheTTL:
    """Cache clave->valor con TTL en segundos."""

    def __init__(self, ttl_segundos: float = 60.0, maxlen: int = 1000):
        ttl = float(ttl_segundos)
        if ttl <= 0:
            raise ValueError("ttl_segundos debe ser positivo.")
        if int(maxlen) < 1:
            raise ValueError("maxlen debe ser mayor o igual a 1.")
        self._ttl = ttl
        self._maxlen = int(maxlen)
        self._datos = {}
        self._vencimientos = {}
        self._orden = []
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._expiraciones = 0
        self._evictions = 0

    @staticmethod
    def _ahora() -> float:
        return time.monotonic()

    def _purgar_interno(self, ahora: float) -> None:
        vencidas = [
            clave for clave, vence in self._vencimientos.items()
            if vence <= ahora
        ]
        for clave in vencidas:
            self._datos.pop(clave, None)
            self._vencimientos.pop(clave, None)
            try:
                self._orden.remove(clave)
            except ValueError:
                pass
            self._expiraciones += 1
        while len(self._orden) > self._maxlen:
            vieja = self._orden.pop(0)
            self._datos.pop(vieja, None)
            self._vencimientos.pop(vieja, None)
            self._evictions += 1

    def obtener(self, clave):
        with self._lock:
            ahora = self._ahora()
            self._purgar_interno(ahora)
            vence = self._vencimientos.get(clave)
            if vence is None or vence <= ahora:
                self._misses += 1
                return None
            self._hits += 1
            return self._datos[clave]

    def poner(self, clave, valor) -> None:
        with self._lock:
            ahora = self._ahora()
            self._purgar_interno(ahora)
            if clave not in self._datos:
                self._orden.append(clave)
            self._datos[clave] = valor
            self._vencimientos[clave] = ahora + self._ttl
            while len(self._orden) > self._maxlen:
                vieja = self._orden.pop(0)
                self._datos.pop(vieja, None)
                self._vencimientos.pop(vieja, None)
                self._evictions += 1

    def invalidar(self, clave) -> bool:
        with self._lock:
            if clave in self._datos:
                del self._datos[clave]
                self._vencimientos.pop(clave, None)
                try:
                    self._orden.remove(clave)
                except ValueError:
                    pass
                return True
            return False

    def vaciar(self) -> None:
        with self._lock:
            self._datos.clear()
            self._vencimientos.clear()
            self._orden.clear()

    def estadisticas(self) -> dict:
        with self._lock:
            self._purgar_interno(self._ahora())
            total = self._hits + self._misses
            ratio = (
                round(self._hits / total, 4) if total > 0 else 0.0
            )
            return {
                "entradas": len(self._datos),
                "maxlen": self._maxlen,
                "ttl_segundos": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_ratio": ratio,
                "expiraciones": self._expiraciones,
                "evictions": self._evictions,
            }

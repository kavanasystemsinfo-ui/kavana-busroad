"""Persistencia mínima en disco para BusRoad (ADR 007: coste cero).

Guardamos en un único fichero JSON (write atómico) lo que el auto-stop de Fly
mataba en cada reinicio:

- `cache_rutas`: respuesta de /ruta completa (dict de RutaResponse) por
  clave canónica. Recorta cuota ORS en rutas repetidas (patrón real del
  usuario: la misma ruta escolar).
- `cache_geocode`: candidatos [lng, lat] por dirección normalizada. Evita
  repetir geocodificación al cruzar varias rutas con un origen común.
- `contador_ruta` / `contador_asistente`: rate limit diario por IP que
  sobrevive al reinicio (antes moría con el proceso).

Sin base de datos ni servicios nuevos: es un JSON con lock de proceso y
escribir-atómico (os.replace). TTL por entrada. Si el fichero está corrupto o
no se puede escribir, arrancamos en memoria (fail-open: nunca romper la ruta).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Ruta del fichero (configurable). Por defecto store.json en el CWD; en el
# contenedor de Fly el CWD es /app y el fichero sobrevive al auto-stop (no al
# deploy, que es un fichero nuevo: aceptable, es caché y contadores).
DEFAULT_PATH = os.environ.get("BUSROAD_STORE_PATH", "store.json")


class Store:
    """Almacén JSON en disco con TTL por entrada. Síncrono y con lock (un solo
    proceso). Cada mutación escribe de forma atómica en disco."""

    def __init__(self, path: str | None = None):
        self._path = Path(path or DEFAULT_PATH)
        self._lock = threading.Lock()
        self._datos: dict = {}
        self._cargados = False

    # ----------------------------------------------------------------- carga
    def _cargar(self) -> None:
        if self._cargados:
            return
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                if isinstance(raw, dict):
                    self._datos = raw
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Store ilegible (%s); arranco en memoria: %s", self._path, e)
        self._cargados = True

    def _guardar(self) -> None:
        try:
            fd, tmp = tempfile.mkstemp(
                dir=self._path.parent, prefix=".store.", suffix=".tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._datos, fh, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, self._path)
        except OSError as e:
            logger.warning("Store no escribible (%s); sigo en memoria: %s", self._path, e)

    # ----------------------------------------------------------------- API
    def cache_get(self, ns: str, clave: str, ttl_seconds: int | None = None):
        """Devuelve el valor cacheado o None si no existe o venció el TTL."""
        with self._lock:
            self._cargar()
            entrada = self._datos.get(ns, {}).get(clave)
            if entrada is None:
                return None
            ts, valor = entrada["ts"], entrada["valor"]
            if ttl_seconds is not None and (time.time() - ts) > ttl_seconds:
                return None
            return valor

    def cache_set(self, ns: str, clave: str, valor) -> None:
        with self._lock:
            self._cargar()
            sub = self._datos.setdefault(ns, {})
            sub[clave] = {"ts": time.time(), "valor": valor}
            self._guardar()

    def counter_get(self, ns: str, clave: str, ttl_seconds: int | None = None) -> int:
        with self._lock:
            self._cargar()
            entrada = self._datos.get(ns, {}).get(clave)
            if entrada is None:
                return 0
            ts, n = entrada["ts"], entrada["n"]
            if ttl_seconds is not None and (time.time() - ts) > ttl_seconds:
                return 0
            return n

    def counter_incr(self, ns: str, clave: str, ttl_seconds: int | None = None) -> int:
        with self._lock:
            self._cargar()
            sub = self._datos.setdefault(ns, {})
            actual = sub.get(clave)
            if actual is None or (
                ttl_seconds is not None and (time.time() - actual["ts"]) > ttl_seconds
            ):
                n = 0
            else:
                n = actual["n"]
            sub[clave] = {"ts": time.time(), "n": n + 1}
            self._guardar()
            return n + 1

    def clear(self) -> None:
        """Vacía todo (usado por tests y como reset manual)."""
        with self._lock:
            self._datos = {}
            self._cargados = True
            try:
                self._path.unlink(missing_ok=True)
            except OSError:
                pass
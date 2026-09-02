"""Tests del motor de rutas: las paradas viajan en la respuesta (orden final).

El bug reportado (solo se guardaba origen→destino) venía de que el frontend no
guardaba paradas; para poder guardarlas el backend debe devolverlas en la
respuesta, y con optimización deben venir en el ORDEN REAL usado (el que
VROOM reordenó), no en el orden que tecleó el usuario.
"""

import asyncio

from app import motor


def _req(origen="Valencia", destino="Cheste", paradas=None, optimizar=False):
    return motor.RutaRequest(
        origen=origen,
        destino=destino,
        paradas=paradas or [],
        optimizar=optimizar,
    )


# ------------------------------------------------------------------ eco simple
def test_mock_eco_paradas():
    """El mock (sin claves) debe devolver las paradas que recibe."""
    req = _req(paradas=["Parada A", "Parada B"])
    resp = motor._mock(req)
    assert resp.paradas == ["Parada A", "Parada B"]


def test_sin_paradas_eco_vacio():
    """Sin paradas la respuesta lleva lista vacía, no None."""
    resp = motor._mock(_req())
    assert resp.paradas == []


# --------------------------------------------------- orden final con VROOM
def test_calcular_ors_paradas_en_orden_final(monkeypatch):
    """Con optimizar=true, la respuesta devuelve las paradas en el orden que
    VROOM decidió, no en el orden tecleado por el usuario."""

    addresses = {
        "Valencia": [0.40, 39.40],
        "Parada A": [0.10, 39.10],
        "Parada B": [0.20, 39.20],
        "Cheste": [0.50, 39.50],
    }

    async def fake_geocodificar(key, texto):
        return [[addresses[texto]]]

    async def fake_optimizar(key, coords):
        # VROOM dice: visita primero la parada 2 (índice 1) y luego la 1 (índice 0)
        return [coords[0], coords[2], coords[1], coords[3]], [1, 0]

    async def fake_pedir(key, coords, perfil, restricciones):
        return {
            "distancia_km": 10.0,
            "duracion_min": 12.0,
            "polyline": "abc",
            "pasos": ["step 1"],
            "paradas_resueltas": [],
        }

    monkeypatch.setattr(motor, "_geocodificar_ors", fake_geocodificar)
    monkeypatch.setattr(motor, "_optimizar_paradas_ors", fake_optimizar)
    monkeypatch.setattr(motor, "_pedir_ruta_ors", fake_pedir)

    req = _req(paradas=["Parada A", "Parada B"], optimizar=True)
    resp = asyncio.run(motor._calcular_ors("key", req))
    assert resp.paradas == ["Parada B", "Parada A"]


def test_calcular_ors_paradas_orden_manual(monkeypatch):
    """Sin optimización, la respuesta conserva el orden tecleado."""

    addresses = {
        "Valencia": [0.40, 39.40],
        "Parada A": [0.10, 39.10],
        "Parada B": [0.20, 39.20],
        "Cheste": [0.50, 39.50],
    }

    async def fake_geocodificar(key, texto):
        return [[addresses[texto]]]

    async def fake_pedir(key, coords, perfil, restricciones):
        return {
            "distancia_km": 10.0,
            "duracion_min": 12.0,
            "polyline": "abc",
            "pasos": ["step 1"],
            "paradas_resueltas": [],
        }

    monkeypatch.setattr(motor, "_geocodificar_ors", fake_geocodificar)
    monkeypatch.setattr(motor, "_pedir_ruta_ors", fake_pedir)

    req = _req(paradas=["Parada A", "Parada B"], optimizar=False)
    resp = asyncio.run(motor._calcular_ors("key", req))
    assert resp.paradas == ["Parada A", "Parada B"]
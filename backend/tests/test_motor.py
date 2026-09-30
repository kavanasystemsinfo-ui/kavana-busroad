"""Tests del motor de rutas: las paradas viajan en la respuesta (orden final).

El bug reportado (solo se guardaba origen→destino) venía de que el frontend no
guardaba paradas; para poder guardarlas el backend debe devolverlas en la
respuesta, y con optimización deben venir en el ORDEN REAL usado (el que
VROOM reordenó), no en el orden que tecleó el usuario.
"""

import asyncio
import time

from fastapi import HTTPException
import pytest

from app import motor
from app.store import Store


@pytest.fixture(autouse=True)
def _store_tmp(tmp_path):
    """Cada test usa un store en disco aislado (sin pisar el de otros tests)."""
    st = Store(str(tmp_path / "store.json"))
    motor.store = st
    yield st


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


# ------------------------------------------------- respaldo geocodificación
def test_geocodificar_respalda_con_nominatim_cuando_ors_falla(monkeypatch):
    """Si ORS no devuelve candidatos (cuota agotada, caída), usar Nominatim."""

    async def fake_ors(key, texto):
        return []  # ORS sin cuota / sin resultados

    async def fake_nominatim(texto):
        return [[-0.3763, 39.4699]]  # Valencia centro

    monkeypatch.setattr(motor, "_geocodificar_ors", fake_ors)
    monkeypatch.setattr(motor, "_geocodificar_nominatim", fake_nominatim)

    res = asyncio.run(motor._geocodificar("key", "Valencia"))
    assert res == [[-0.3763, 39.4699]]


def test_geocodificar_usa_ors_cuando_tiene_resultados(monkeypatch):
    """Con ORS sano, Nominatim no se llama (es solo respaldo de emergencia)."""

    llamado = {"nominatim": False}

    async def fake_ors(key, texto):
        return [[0.40, 39.40]]

    async def fake_nominatim(texto):
        llamado["nominatim"] = True
        return [[-0.3763, 39.4699]]

    monkeypatch.setattr(motor, "_geocodificar_ors", fake_ors)
    monkeypatch.setattr(motor, "_geocodificar_nominatim", fake_nominatim)

    res = asyncio.run(motor._geocodificar("key", "Valencia"))
    assert res == [[0.40, 39.40]]
    assert llamado["nominatim"] is False


def test_calcular_ors_error_honesto_cuando_ambos_geocoders_fallan(monkeypatch):
    """Si ORS y Nominatim no localizan nada, el error es claro (no mock)."""

    async def fake_geocodificar(key, texto):
        return []

    monkeypatch.setattr(motor, "_geocodificar", fake_geocodificar)

    import pytest

    req = _req(origen="XYZexiste?pqrs", destino="Otroinexistente?abcd")
    with pytest.raises(ValueError, match="No pude localizar"):
        asyncio.run(motor._calcular_ors("key", req))


# --------------------------------------------------- caché de rutas + rate limit
def test_geocodificar_usa_cache_sin_reiterar_ors(monkeypatch):
    """La 2ª geocodificación del mismo texto sale de caché (no repite ORS)."""
    llamadas = {"ors": 0}

    async def fake_ors(key, texto):
        llamadas["ors"] += 1
        return [[0.40, 39.40]]

    monkeypatch.setattr(motor, "_geocodificar_ors", fake_ors)
    monkeypatch.setattr(motor, "_geocodificar_nominatim", lambda texto: [])

    r1 = asyncio.run(motor._geocodificar("key", "Valencia"))
    r2 = asyncio.run(motor._geocodificar("key", "Valencia"))
    assert r1 == [[0.40, 39.40]]
    assert r2 == [[0.40, 39.40]]
    assert llamadas["ors"] == 1


def test_cache_ruta_segunda_llamada_no_golpea_ors(monkeypatch):
    """Dos requests idénticos por el endpoint: el 2º sale de caché (1 solo _calcular_ors)."""
    from fastapi.testclient import TestClient

    from app.main import app

    llamadas = {"n": 0}

    async def fake_calcular(key, req):
        llamadas["n"] += 1
        return motor._mock(req)

    monkeypatch.setattr(motor, "_calcular_ors", fake_calcular)
    monkeypatch.setattr("app.motor.store", motor.store)
    monkeypatch.setenv("ORS_API_KEY", "test-key")

    client = TestClient(app)
    body = {
        "origen": "Valencia",
        "destino": "Cheste",
        "paradas": [],
        "optimizar": False,
        "vehiculo": {"alto_m": 3.0, "ancho_m": 2.5, "largo_m": 10.0, "peso_kg": 12000},
    }
    r1 = client.post("/api/v1/ruta", json=body)
    r2 = client.post("/api/v1/ruta", json=body)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["distancia_km"] == r2.json()["distancia_km"]
    assert llamadas["n"] == 1, "el 2º request debió salir de caché sin llamar a ORS"


def test_rate_limit_por_ip_devuelve_429(monkeypatch):
    """Superado el límite diario de misses, un request nuevo devuelve 429."""
    from fastapi.testclient import TestClient

    from app.main import app

    async def fake_calcular(key, req):
        return motor._mock(req)

    monkeypatch.setattr(motor, "_calcular_ors", fake_calcular)
    monkeypatch.setattr("app.motor.store", motor.store)
    monkeypatch.setenv("ORS_API_KEY", "test-key")

    motor.RUTAS_MAX_POR_IP_DIA = 2
    body = {
        "origen": "Valencia",
        "destino": "Cheste",
        "paradas": [],
        "optimizar": False,
        "vehiculo": {"alto_m": 3.0, "ancho_m": 2.5, "largo_m": 10.0, "peso_kg": 12000},
    }
    client = TestClient(app)
    # 2 misses distintos (destinos distintos para no cachear) + 1 más con cache limpia
    r1 = client.post("/api/v1/ruta", json={**body, "destino": "Paterna"})
    r2 = client.post("/api/v1/ruta", json={**body, "destino": "Riba-roja"})
    r3 = client.post("/api/v1/ruta", json={**body, "destino": "Liria"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


def test_nominatim_se_serializa_a_1s_entre_llamadas():
    """El fallback Nominatim espacia >=1 s las llamadas (ToS ~1 req/s), así
    hasta 20 paradas sin cuota ORS no autosabotean el fallback."""
    import asyncio as _asyncio
    import time as _time

    # reset del reloj interno para no heredar esperas de otros tests
    motor._ultimo_nominatim = 0.0
    motor.NOMINATIM_INTERVALO_S = 1.0

    async def _dos():
        t0 = _time.monotonic()
        await motor._respetar_intervalo_nominatim()  # 1ª: sin espera
        t1 = _time.monotonic()
        await motor._respetar_intervalo_nominatim()  # 2ª: debe esperar ~1s
        t2 = _time.monotonic()
        return t1 - t0, t2 - t1

    primera, segunda = _asyncio.run(_dos())
    assert primera < 0.5, f"la 1ª no debía esperar (tuvo {primera:.2f}s)"
    assert segunda >= 0.9, f"la 2ª debió esperar ~1s (tuvo {segunda:.2f}s)"


# --------------------------------------------------- sugerencias de geocodificación
def test_geocode_expone_candidatos_con_nombre(monkeypatch):
    """El endpoint /geocode devuelve candidatos {label,lat,lon} para elegir el punto correcto
    antes de enrutar (fallo peor para un conductor: ruta al sitio equivocado)."""
    from fastapi.testclient import TestClient

    from app.main import app

    async def fake_candidatos(key, texto):
        return [
            {"label": "Higueruelas, Valencia, España", "lat": 39.7543, "lon": -0.9181},
            {"label": "Higueruela, Albacete, España", "lat": 38.9646, "lon": -1.4460},
        ]

    monkeypatch.setenv("ORS_API_KEY", "test-key")
    # _geocode_ors es el helper que consulta a ORS; lo sustituimos por el fake
    monkeypatch.setattr(motor, "_geocode_ors", fake_candidatos)
    monkeypatch.setattr("app.motor.store", motor.store)
    client = TestClient(app)
    r = client.get("/api/v1/geocode", params={"q": "Higueruela"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["candidatos"]) == 2
    assert data["candidatos"][0]["label"].startswith("Higueruelas")
    assert abs(data["candidatos"][0]["lat"] - 39.75) < 0.01


def test_geocode_prioriza_ors_y_cachea(monkeypatch):
    """El 2º request del mismo texto sale de caché (reusa el store, sin re-consultar ORS)."""
    from fastapi.testclient import TestClient

    from app.main import app

    llamadas = {"n": 0}

    async def fake_candidatos(key, texto):
        llamadas["n"] += 1
        return [{"label": "Paterna, Valencia, España", "lat": 39.5028, "lon": -0.4406}]

    monkeypatch.setenv("ORS_API_KEY", "test-key")
    monkeypatch.setattr(motor, "_geocode_ors", fake_candidatos)
    monkeypatch.setattr("app.motor.store", motor.store)
    client = TestClient(app)
    r1 = client.get("/api/v1/geocode", params={"q": "Paterna"})
    r2 = client.get("/api/v1/geocode", params={"q": "Paterna"})
    assert r1.status_code == r2.status_code == 200
    assert llamadas["n"] == 1, "el 2º request debió salir de caché sin re-consultar ORS"


def test_geocode_sin_ors_respalda_con_nominatim(monkeypatch):
    """Sin ORS_API_KEY (o sin cuota), el respaldo es Nominatim, y honesto: si ambos
    fallan devuelve lista vacía, no candidatos inventados."""
    from fastapi.testclient import TestClient

    from app.main import app

    async def fake_nominatim(texto):
        return [{"label": "Cheste, Valencia, España", "lat": 39.4952, "lon": -0.6826}]

    # sin ORS_API_KEY en env → va a Nominatim
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    monkeypatch.setattr(motor, "_geocode_nominatim", fake_nominatim)
    monkeypatch.setattr("app.motor.store", motor.store)
    client = TestClient(app)
    r = client.get("/api/v1/geocode", params={"q": "Cheste"})
    assert r.status_code == 200
    assert r.json()["candidatos"] == [
        {"label": "Cheste, Valencia, España", "lat": 39.4952, "lon": -0.6826}
    ]


# ------------------------------------------- errores que el usuario puede leer
# Jorge (2026-09-30): en producción la app enseñaba "Error 422: ... respondió
# 404" en bruto. Un fallo del motor tiene que llegar con un motivo en español y
# su status correcto (503 si el motor no responde, 422 si la dirección no existe).
class _RespuestaFalsa:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class _ClienteFalso:
    """Cliente httpx mínimo: solo lo que usan los helpers de ORS."""

    def __init__(self, respuesta):
        self._respuesta = respuesta

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, **kwargs):
        return self._respuesta


def test_error_ors_traduce_los_codigos_a_motivos_en_espanol():
    """Cada código que afecta al usuario tiene su propio mensaje, sin códigos
    ni JSON crudo (el conductor no puede hacer nada con "respondió 404")."""
    assert motor._error_ors(404).status_code == 422
    assert "dirección" in motor._error_ors(404).detalle
    assert motor._error_ors(429).status_code == 429
    assert motor._error_ors(500).status_code == 503
    assert motor._error_ors(503).status_code == 503
    assert motor._error_ors(401).status_code == 503
    for codigo in (400, 401, 404, 429, 500, 503):
        detalle = motor._error_ors(codigo).detalle
        assert "{" not in detalle and "}" not in detalle
        assert str(codigo) not in detalle


def test_pedir_ruta_ors_no_filtra_el_json_de_ors(monkeypatch):
    """Con cuota agotada, _pedir_ruta_ors lanza ErrorMotorRutas ya en español."""
    cliente = _ClienteFalso(_RespuestaFalsa(429, '{"error":{"code":2010}}'))
    monkeypatch.setattr(motor.httpx, "AsyncClient", lambda **k: cliente)

    with pytest.raises(motor.ErrorMotorRutas) as exc:
        asyncio.run(motor._pedir_ruta_ors("key", [[0, 0], [1, 1]], "driving-hgv", None))

    assert exc.value.status_code == 429
    assert "saturado" in exc.value.detalle.lower()
    assert "{" not in exc.value.detalle


def test_optimizar_paradas_no_filtra_el_json_de_ors(monkeypatch):
    """El fallo de VROOM tampoco expone el cuerpo crudo de ORS."""
    cliente = _ClienteFalso(_RespuestaFalsa(503, "<html>gateway</html>"))
    monkeypatch.setattr(motor.httpx, "AsyncClient", lambda **k: cliente)

    with pytest.raises(motor.ErrorMotorRutas) as exc:
        asyncio.run(motor._optimizar_paradas_ors("key", [[0, 0], [1, 1], [2, 2], [3, 3]]))

    assert exc.value.status_code == 503
    assert "<html>" not in exc.value.detalle


def _body_ruta(destino="Cheste"):
    return {
        "origen": "Valencia",
        "destino": destino,
        "paradas": [],
        "optimizar": False,
        "vehiculo": {"alto_m": 3.0, "ancho_m": 2.5, "largo_m": 10.0, "peso_kg": 12000},
    }


def test_endpoint_ruta_usa_el_status_del_motor_y_manda_mensaje_claro(monkeypatch):
    """Caída del motor: 503 con motivo en español, no un 422 con el error crudo."""
    from fastapi.testclient import TestClient

    from app.main import app

    async def fake_calcular(key, req):
        raise motor._error_ors(503)

    monkeypatch.setattr(motor, "_calcular_ors", fake_calcular)
    monkeypatch.setattr("app.motor.store", motor.store)
    monkeypatch.setenv("ORS_API_KEY", "test-key")

    r = TestClient(app).post("/api/v1/ruta", json=_body_ruta())
    assert r.status_code == 503
    detalle = r.json()["detail"]
    assert "no responde" in detalle.lower()
    assert "OpenRouteService" not in detalle


def test_endpoint_ruta_direccion_no_encontrada_da_422_legible(monkeypatch):
    """Dirección no localizada: 422 con un motivo que se entiende."""
    from fastapi.testclient import TestClient

    from app.main import app

    async def fake_calcular(key, req):
        raise ValueError(
            "No pude localizar origen o destino. Añade la ciudad o el código postal y vuelve a intentarlo."
        )

    monkeypatch.setattr(motor, "_calcular_ors", fake_calcular)
    monkeypatch.setattr("app.motor.store", motor.store)
    monkeypatch.setenv("ORS_API_KEY", "test-key")

    r = TestClient(app).post("/api/v1/ruta", json=_body_ruta(destino="Riba-roja"))
    assert r.status_code == 422
    assert "localizar" in r.json()["detail"]

"""Motor de rutas para vehículos grandes con restricciones de dimensiones.

El ruteo real usa OpenRouteService (perfil driving-hgv, restricciones reales
en Europa con datos de OpenStreetMap). Requiere ORS_API_KEY.

Respaldo honesto (NUNCA mock a escondidas: con claves y fallo real se devuelve
el error, el mock es solo para desarrollo sin claves):
- Google Routes API se usa únicamente cuando NO hay ORS_API_KEY (ruta estándar
  de conducción; Google no aplica restricciones de dimensiones fuera de EE.UU.).
- Geocodificación: si ORS no localiza (o está sin cuota), respalda con
  Nominatim/OSM, serializado a ~1 req/s.

Sin claves responde con una ruta de ejemplo (mock).
"""

import asyncio
import hashlib
import json
import logging
import os
import time

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .store import Store

router = APIRouter(prefix="/api/v1", tags=["ruta"])

logger = logging.getLogger(__name__)


class ErrorMotorRutas(ValueError):
    """Fallo del motor con un motivo que el usuario puede leer.

    Hereda de ValueError para no alterar los `except ValueError` del flujo de
    candidatos, pero lleva su propio status HTTP: así el endpoint responde 503
    cuando el motor no está y 422 cuando la dirección no se localiza, en vez de
    un 422 con el JSON crudo de ORS.
    """

    def __init__(self, detalle: str, status_code: int = 422):
        super().__init__(detalle)
        self.detalle = detalle
        self.status_code = status_code


def _error_ors(status: int) -> ErrorMotorRutas:
    """Traduce el status que devuelve ORS a un motivo comprensible."""
    if status in (401, 403):
        return ErrorMotorRutas(
            "El motor de rutas ha rechazado la clave de acceso. Avisa al administrador.",
            503,
        )
    if status == 429:
        return ErrorMotorRutas(
            "El motor de rutas está saturado ahora mismo. Espera unos segundos y vuelve a intentarlo.",
            429,
        )
    if status == 404:
        return ErrorMotorRutas(
            "No encuentro esa dirección. Añade la ciudad o el código postal.", 422
        )
    if status >= 500:
        return ErrorMotorRutas(
            "El motor de rutas no responde ahora mismo. Inténtalo en unos segundos.", 503
        )
    return ErrorMotorRutas(
        "No he podido calcular esa ruta. Revisa el origen y el destino e inténtalo otra vez.",
        422,
    )


def _http_exception(e: Exception) -> HTTPException:
    """Respuesta HTTP de un fallo del motor (con su status propio si lo trae)."""
    if isinstance(e, ErrorMotorRutas):
        return HTTPException(status_code=e.status_code, detail=e.detalle)
    return HTTPException(status_code=422, detail=str(e))

# store compartido (cache + contadores). Los tests lo reemplazan por un Store
# apuntando a un fichero temporal.
store = Store()

# TTLs: rutas 24h (Una ruta escolar no cambia en el día), geocodificación 7
# días, contadores 25h (cubren el día + margen de tiempo de servidor).
TTL_RUTA_S = 24 * 3600
TTL_GEOCODE_S = 7 * 24 * 3600
TTL_CONTADOR_S = 25 * 3600

# Límite de rutas nuevas (miss de caché) por IP al día. Solo cuenta los misses:
# una ruta cacheada que se repite no vuelve a gastar cuota ORS.
RUTAS_MAX_POR_IP_DIA = int(os.environ.get("RUTAS_MAX_POR_IP_DIA", "30"))

# Nominatim (fallback de geocodificación, gratis) exige ~1 req/s. Serializamos
# las llamadas con un lock de proceso para no autosabotear el fallback cuando
# ORS está sin cuota y hasta 20 paradas caen en Nominatim seguidas.
NOMINATIM_INTERVALO_S = 1.0
_nominatim_lock = asyncio.Lock()
_ultimo_nominatim = 0.0


async def _respetar_intervalo_nominatim() -> None:
    """Espera lo que falte para que pasen >=1 s entre llamadas a Nominatim."""
    global _ultimo_nominatim
    async with _nominatim_lock:
        ahora = time.monotonic()
        espera = NOMINATIM_INTERVALO_S - (ahora - _ultimo_nominatim)
        if espera > 0:
            await asyncio.sleep(espera)
            ahora = time.monotonic()
        _ultimo_nominatim = ahora

ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-hgv"
ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
ORS_OPTIMIZATION_URL = "https://api.openrouteservice.org/optimization"
GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


# ------------------------------------------------------------------ esquemas
class Dimensiones(BaseModel):
    alto_m: float = Field(3.0, gt=0, description="Altura del vehículo en metros")
    ancho_m: float = Field(2.5, gt=0, description="Anchura en metros")
    largo_m: float = Field(10.0, gt=0, description="Longitud en metros")
    peso_kg: int = Field(12000, gt=0, description="Peso total en kg")


class RutaRequest(BaseModel):
    origen: str = Field(min_length=2, max_length=200)
    destino: str = Field(min_length=2, max_length=200)
    paradas: list[str] = Field(default_factory=list, max_length=20, description="Paradas intermedias en orden (o sin orden si optimizar=true)")
    optimizar: bool = Field(False, description="Si true, ORS optimiza el orden de las paradas (problema del viajante)")
    vehiculo: Dimensiones = Dimensiones()


class PuntoRiesgo(BaseModel):
    nombre: str
    tipo: str
    descripcion: str


class RutaConvencional(BaseModel):
    distancia_km: float
    duracion_min: float
    polyline: str
    pasos: list[str]


class RutaResponse(BaseModel):
    origen: str
    destino: str
    paradas: list[str] = []  # paradas en el orden REAL usado (tras optimización si aplica)
    distancia_km: float
    duracion_min: float
    polyline: str
    pasos: list[str]
    riesgos: list[PuntoRiesgo] = []
    motor: str  # "openrouteservice" | "google-routes" | "mock"
    convencional: RutaConvencional | None = None  # ruta de coche sin restricciones


# ------------------------------------------------------------------ helpers
async def _geocode_ors(api_key: str, texto: str) -> list[dict]:
    """Busca una dirección en ORS y devuelve candidatos con label + coordenadas.

    Fuerza España (boundary.country=ESP) para que Higueruelas no resuelva a
    Higueruela (Albacete) y devuelve varios candidatos con su nombre para que
    el usuario confirme cuál es antes de enrutar.
    """
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            ORS_GEOCODE_URL,
            params={"text": texto, "size": 3, "boundary.country": "ESP"},
            headers={"Authorization": api_key},
        )
    if r.status_code != 200:
        return []
    candidatos = []
    for f in r.json().get("features", []):
        g = f.get("geometry", {})
        coords = g.get("coordinates")
        if not coords:
            continue
        props = f.get("properties", {})
        candidatos.append(
            {"label": props.get("label", texto), "lat": coords[1], "lon": coords[0]}
        )
    return candidatos


async def _geocode_nominatim(texto: str) -> list[dict]:
    """Respaldo con Nominatim (OpenStreetMap) cuando ORS falla (cuota, caída).

    Gratis y sin key, pero con límite estricto (~1 req/s, serializado con
    _respetar_intervalo_nominatim) y solo como fallback. España forzada.
    """
    await _respetar_intervalo_nominatim()
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            NOMINATIM_URL,
            params={
                "q": texto,
                "format": "jsonv2",
                "limit": 3,
                "countrycodes": "es",
            },
            headers={"User-Agent": "KavanaBusRoad/1.0 (contact: kavanasystems.info@gmail.com)"},
        )
    if r.status_code != 200:
        return []
    candidatos = []
    for f in r.json():
        try:
            lon = float(f["lon"])
            lat = float(f["lat"])
        except (KeyError, ValueError, TypeError):
            continue
        candidatos.append({"label": f.get("display_name", texto), "lat": lat, "lon": lon})
    return candidatos


async def _geocodificar_ors(api_key: str, texto: str) -> list[list[float]]:
    """Convierte una dirección en candidatos [lng, lat] con ORS (compat)."""
    return [[c["lon"], c["lat"]] for c in await _geocode_ors(api_key, texto)]


async def _geocodificar_nominatim(texto: str) -> list[list[float]]:
    """Respaldo Nominatim devolviendo solo [lng, lat] (compat). Respeta ~1 req/s."""
    return [[c["lon"], c["lat"]] for c in await _geocode_nominatim(texto)]


async def _geocodificar(api_key: str, texto: str) -> list[list[float]]:
    """Geocodifica con ORS; si ORS no encuentra (o está sin cuota), respalda con Nominatim.

    Resultado cacheado en disco (store) por dirección normalizada: una ruta
    repetida con el mismo origen no vuelve a gastar cuota ORS ni a llamar a
    Nominatim (que además tiene límite de ~1 req/s).
    """
    clave = " ".join(texto.strip().lower().split())
    if not clave:
        return []
    cacheado = store.cache_get("geocode", clave, TTL_GEOCODE_S)
    if cacheado is not None:
        return cacheado
    candidatos = await _geocodificar_ors(api_key, texto)
    if not candidatos:
        candidatos = await _geocodificar_nominatim(texto)
    if candidatos:
        store.cache_set("geocode", clave, candidatos)
    return candidatos


async def _pedir_ruta_ors(
    api_key: str, coords: list, perfil: str, restricciones: dict | None
) -> dict:
    """Pide una ruta a ORS y devuelve {distancia_km, duracion_min, polyline, pasos}.

    coords: lista de [lng, lat] con 2 o más puntos (origen, paradas..., destino).
    """
    payload = {
        "coordinates": coords,
        "radiuses": [1500] * len(coords),
        "language": "es",
    }
    if restricciones:
        payload["options"] = {"profile_params": {"restrictions": restricciones}}
    async with httpx.AsyncClient(timeout=40) as client:
        r = await client.post(
            f"https://api.openrouteservice.org/v2/directions/{perfil}",
            json=payload,
            headers={"Authorization": api_key, "Content-Type": "application/json"},
        )
    if r.status_code != 200:
        logger.warning("ORS (%s) respondió %s: %s", perfil, r.status_code, r.text[:200])
        raise _error_ors(r.status_code)
    route = r.json().get("routes", [{}])[0]
    summary = route.get("summary", {})
    pasos = []
    for seg in route.get("segments", []):
        for step in seg.get("steps", []):
            txt = step.get("instruction") or step.get("name") or ""
            if txt:
                pasos.append(txt)
    return {
        "distancia_km": round(summary.get("distance", 0) / 1000, 1),
        "duracion_min": round(summary.get("duration", 0) / 60, 1),
        "polyline": route.get("geometry", ""),
        "pasos": pasos[:25],
        "paradas_resueltas": route.get("way_points", []),
    }


async def _optimizar_paradas_ors(api_key: str, coords: list) -> tuple[list, list[int]]:
    """Devuelve (coordenadas reordenadas, orden de paradas) según la ruta óptima (VROOM).

    El endpoint /optimization resuelve el problema del viajante: recibe el
    origen, las paradas y el destino, y devuelve el orden óptimo de visita.
    Aquí reordenamos las coordenadas intermedias según ese orden y devolvemos
    el orden (índices sobre las paradas originales) para que la respuesta
    pueda reflejar las paradas en el orden en que realmente se recorren.
    """
    if len(coords) <= 3:
        return coords, list(range(len(coords) - 2))  # sin paradas (o una sola) no hay nada que optimizar
    origen = coords[0]
    destino = coords[-1]
    paradas = coords[1:-1]
    payload = {
        "vehicles": [{
            "id": 0,
            "profile": "driving-hgv",
            "start": origen,
            "end": destino,
        }],
        "jobs": [
            {"id": i, "location": p} for i, p in enumerate(paradas)
        ],
    }
    async with httpx.AsyncClient(timeout=40) as client:
        r = await client.post(
            ORS_OPTIMIZATION_URL,
            json=payload,
            headers={"Authorization": api_key, "Content-Type": "application/json"},
        )
    if r.status_code != 200:
        logger.warning("Optimización ORS respondió %s: %s", r.status_code, r.text[:200])
        raise _error_ors(r.status_code)
    data = r.json()
    routes = data.get("routes", [])
    if not routes:
        return coords, list(range(len(coords) - 2))
    # Reordenar paradas según los steps (start → job N → ... → end)
    orden: list[int] = []
    for step in routes[0].get("steps", []):
        job = step.get("job")
        if job is not None:
            orden.append(job)
    if not orden:
        return coords, list(range(len(coords) - 2))
    reordenadas = [origen] + [paradas[j] for j in orden] + [destino]
    return reordenadas, orden


async def _calcular_ors(api_key: str, req: RutaRequest) -> RutaResponse:
    """Ruta con restricciones reales de dimensiones (perfil driving-hgv).

    Soporta paradas intermedias: geocodifica origen + paradas + destino y
    pasa todos los puntos a ORS en orden (o con optimización si req.optimizar).

    También calcula la ruta convencional (driving-car, sin restricciones)
    con las mismas coordenadas, para que el usuario compare la diferencia.
    """
    origenes = await _geocodificar(api_key, req.origen)
    destinos = await _geocodificar(api_key, req.destino)
    if not origenes or not destinos:
        raise ValueError(
            "No pude localizar origen o destino. Añade la ciudad o el código postal y vuelve a intentarlo."
        )

    # Geocodificar paradas intermedias (cada una con sus candidatos)
    paradas_candidatas: list[list] = []
    for p in req.paradas:
        cands = await _geocodificar(api_key, p)
        if not cands:
            raise ValueError(f"No pude localizar la parada «{p}». Añade la ciudad o el código postal.")
        paradas_candidatas.append(cands)

    v = req.vehiculo
    restricciones = {
        "height": v.alto_m,
        "width": v.ancho_m,
        "length": v.largo_m,
        "weight": float(v.peso_kg),
    }
    ultimo_error = "Sin ruta enrutable entre los puntos indicados."
    for o in origenes[:2]:
        for d in destinos[:2]:
            # Combinar cada parada con su primer candidato (más probable)
            coords = [o] + [pc[0] for pc in paradas_candidatas] + [d]
            # Orden de paradas: por defecto el tecleado por el usuario
            orden_paradas = list(range(len(req.paradas)))
            # Si se pide optimización, reordenar las paradas con VROOM
            if req.optimizar:
                try:
                    coords, orden_paradas = await _optimizar_paradas_ors(api_key, coords)
                except ValueError:
                    pass  # si falla la optimización, usar el orden dado
            try:
                segura = await _pedir_ruta_ors(
                    api_key, coords, "driving-hgv", restricciones
                )
            except ValueError as e:
                ultimo_error = str(e)
                continue
            # Ruta convencional (coche) con las mismas coordenadas
            try:
                convencional = await _pedir_ruta_ors(
                    api_key, coords, "driving-car", None
                )
            except ValueError:
                convencional = None
            return RutaResponse(
                origen=req.origen,
                destino=req.destino,
                paradas=[req.paradas[i] for i in orden_paradas],
                distancia_km=segura["distancia_km"],
                duracion_min=segura["duracion_min"],
                polyline=segura["polyline"],
                pasos=segura["pasos"],
                motor="openrouteservice",
                convencional=(
                    RutaConvencional(
                        distancia_km=convencional["distancia_km"],
                        duracion_min=convencional["duracion_min"],
                        polyline=convencional["polyline"],
                        pasos=convencional["pasos"],
                    )
                    if convencional
                    else None
                ),
            )
    raise ValueError(ultimo_error)


async def _calcular_google(api_key: str, req: RutaRequest) -> RutaResponse:
    """Ruta estándar de conducción (Google no aplica dimensiones en Europa)."""
    payload = {
        "origin": {"address": req.origen},
        "destination": {"address": req.destino},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "routes.distanceMeters,routes.duration,"
            "routes.polyline.encodedPolyline,routes.legs.steps.navigationInstruction"
        ),
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(GOOGLE_ROUTES_URL, json=payload, headers=headers)
    if r.status_code != 200:
        logger.warning("Google Routes respondió %s: %s", r.status_code, r.text[:200])
        raise _error_ors(r.status_code)

    route = r.json().get("routes", [{}])[0]
    pasos = []
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            ni = step.get("navigationInstruction", {}).get("instructions", "")
            if ni:
                pasos.append(ni)
    return RutaResponse(
        origen=req.origen,
        destino=req.destino,
        paradas=req.paradas,
        distancia_km=round(route.get("distanceMeters", 0) / 1000, 1),
        duracion_min=round(int(route.get("duration", "0s").rstrip("s")) / 60, 1),
        polyline=route.get("polyline", {}).get("encodedPolyline", ""),
        pasos=pasos[:12],
        motor="google-routes",
    )


def _mock(req: RutaRequest) -> RutaResponse:
    """Ruta de ejemplo para desarrollo sin claves."""
    return RutaResponse(
        origen=req.origen,
        destino=req.destino,
        paradas=req.paradas,
        distancia_km=42.5,
        duracion_min=38.0,
        polyline="mock",
        pasos=[
            "Sal por la A-3 hacia el este",
            "Mantente en la autovía 12 km",
            "Toma la salida 345 hacia la CV-30",
            "Continúa 8 km por la CV-30",
            "Gira a la derecha en la calle Mayor",
            "Has llegado a tu destino",
        ],
        riesgos=[
            PuntoRiesgo(nombre="Puente de la autovía", tipo="altura", descripcion="Altura libre 4,1 m. Tu vehículo pasa (3,0 m)."),
            PuntoRiesgo(nombre="Calle Mayor", tipo="anchura", descripcion="Calle estrecha de 6 m. Pasa con precaución."),
        ],
        motor="mock",
    )


# ------------------------------------------------------------------- rutas
# Modelo de sugerencia de geocodificación: para que el usuario confirme el
# punto correcto ANTES de enrutar (fallo peor para un conductor: ruta al sitio
# equivocado). El backend ya resolvía candidatos internamente; ahora los expone.
class GeocodeCandidato(BaseModel):
    label: str
    lat: float
    lon: float


class GeocodeResponse(BaseModel):
    candidatos: list[GeocodeCandidato]


TTL_GEOCODE_SUGERENCIAS_S = 24 * 3600


async def _sugerencias_geocode(api_key: str, texto: str) -> list[dict]:
    """Candidatos con nombre para confirmar un punto antes de enrutar.

    ORS primero (mejor calidad en España); si está sin cuota o no encuentra,
    Nominatim como respaldo. Cacheado en el store por texto normalizado.
    """
    clave = " ".join(texto.strip().lower().split())
    if not clave:
        return []
    cacheado = store.cache_get("geocode_sugerencias", clave, TTL_GEOCODE_SUGERENCIAS_S)
    if cacheado is not None:
        return cacheado
    candidatos = []
    if api_key:
        candidatos = await _geocode_ors(api_key, texto)
    if not candidatos:
        candidatos = await _geocode_nominatim(texto)
    if candidatos:
        store.cache_set("geocode_sugerencias", clave, candidatos)
    return candidatos


@router.get("/geocode", response_model=GeocodeResponse)
async def geocode_sugerencias(q: str):
    """Exponer los candidatos geocodificados para que el usuario confirme el
    punto antes de enrutar. Sin candidatos → lista vacía (honesto, no inventa).
    """
    ors_key = os.environ.get("ORS_API_KEY", "").strip()
    texto = q.strip() if q else ""
    candidatos = await _sugerencias_geocode(ors_key, texto)
    return GeocodeResponse(candidatos=candidatos)


def _clave_cache_ruta(req: RutaRequest) -> str:
    """Clave canónica de una ruta: hash de origen/destino/paradas/optimizar/dimensiones.

    Una misma ruta escolar repetida (el patrón real) genera SIEMPRE la misma
    clave, así que el segundo cálculo sale de caché sin gastar cuota ORS.
    """
    v = req.vehiculo
    canonico = json.dumps(
        {
            "origen": req.origen.strip().lower(),
            "destino": req.destino.strip().lower(),
            "paradas": [p.strip().lower() for p in req.paradas],
            "optimizar": req.optimizar,
            "vehiculo": [round(v.alto_m, 2), round(v.ancho_m, 2), round(v.largo_m, 2), round(v.peso_kg, 0)],
        },
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


@router.post("/ruta", response_model=RutaResponse)
async def calcular_ruta(req: RutaRequest, request: Request):
    ors_key = os.environ.get("ORS_API_KEY", "").strip()
    google_key = os.environ.get("GOOGLE_API_KEY", "").strip()

    # 1. OpenRouteService: restricciones de dimensiones reales en Europa
    if ors_key:
        clave = _clave_cache_ruta(req)
        cacheado = store.cache_get("cache_rutas", clave, TTL_RUTA_S)
        if cacheado is not None:
            return RutaResponse(**cacheado)
        # Rate limit por IP SOLO sobre misses: la ruta cacheada no cuesta ORS.
        ip = request.client.host if request.client else "unknown"
        clave_ip = f"{time.strftime('%Y-%m-%d')}|{ip}"
        if store.counter_get("contador_ruta", clave_ip, TTL_CONTADOR_S) >= RUTAS_MAX_POR_IP_DIA:
            return JSONResponse(
                status_code=429,
                content={
                    "error": f"Has alcanzado el límite diario de {RUTAS_MAX_POR_IP_DIA} rutas nuevas por visitante. Vuelve mañana."
                },
            )
        try:
            resp = await _calcular_ors(ors_key, req)
        except (ErrorMotorRutas, ValueError) as e:
            # El detalle crudo de ORS queda en el log; al usuario le llega el
            # motivo en español con el status correcto (503, 429 o 422).
            print(
                f"[DIAG] ruta fallida | origen={req.origen!r} destino={req.destino!r} "
                f"paradas={req.paradas!r} optimizar={req.optimizar} | {e}"
            )
            raise _http_exception(e)
        # Solo se cuenta ni se cachea lo que salió bien (miss auténtico)
        store.counter_incr("contador_ruta", clave_ip, TTL_CONTADOR_S)
        store.cache_set("cache_rutas", clave, resp.model_dump())
        return resp

    # 2. Google Routes: ruta estándar (sin dimensiones fuera de EE.UU.)
    if google_key:
        try:
            return await _calcular_google(google_key, req)
        except (ErrorMotorRutas, ValueError) as e:
            raise _http_exception(e)

    # 3. Sin claves: mock para desarrollo
    return _mock(req)

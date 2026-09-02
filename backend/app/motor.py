"""Motor de rutas para vehículos grandes con restricciones de dimensiones.

Motores (en orden de preferencia):
1. OpenRouteService (perfil driving-hgv): restricciones de altura/anchura/
   largo/peso REALES en Europa (datos OpenStreetMap). Requiere ORS_API_KEY.
2. Google Routes API: ruta estándar de conducción (Google no soporta
   restricciones de dimensiones fuera de EE.UU.). Requiere GOOGLE_API_KEY.
3. Mock: respuesta de ejemplo sin ninguna clave para desarrollo.

Sin claves responde con una ruta de ejemplo (mock).
"""

import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["ruta"])

ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-hgv"
ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
ORS_OPTIMIZATION_URL = "https://api.openrouteservice.org/optimization"
GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


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
async def _geocodificar_ors(api_key: str, texto: str) -> list[list[float]]:
    """Convierte una dirección en candidatos [lng, lat] con ORS.

    Fuerza España (boundary.country=ESP) para que "Higueruelas" no
    resuelva a "Higueruela" (Albacete), y devuelve varios candidatos
    por si el primero no es enrutable.
    """
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            ORS_GEOCODE_URL,
            params={"text": texto, "api_key": None, "size": 3, "boundary.country": "ESP"},
            headers={"Authorization": api_key},
        )
    if r.status_code != 200:
        return []
    return [
        f["geometry"]["coordinates"]
        for f in r.json().get("features", [])
        if f.get("geometry", {}).get("coordinates")
    ]


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
        raise ValueError(f"OpenRouteService ({perfil}) respondió {r.status_code}: {r.text[:120]}")
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
        raise ValueError(f"Optimización ORS respondió {r.status_code}: {r.text[:120]}")
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
    origenes = await _geocodificar_ors(api_key, req.origen)
    destinos = await _geocodificar_ors(api_key, req.destino)
    if not origenes or not destinos:
        raise ValueError("No pude localizar origen o destino. Prueba con nombres más exactos.")

    # Geocodificar paradas intermedias (cada una con sus candidatos)
    paradas_candidatas: list[list] = []
    for p in req.paradas:
        cands = await _geocodificar_ors(api_key, p)
        if not cands:
            raise ValueError(f"No pude localizar la parada: {p}")
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
        raise ValueError(f"Google Routes respondió {r.status_code}: {r.text[:300]}")

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
@router.post("/ruta", response_model=RutaResponse)
async def calcular_ruta(req: RutaRequest):
    ors_key = os.environ.get("ORS_API_KEY", "").strip()
    google_key = os.environ.get("GOOGLE_API_KEY", "").strip()

    # 1. OpenRouteService: restricciones de dimensiones reales en Europa
    if ors_key:
        try:
            return await _calcular_ors(ors_key, req)
        except ValueError as e:
            # Sin claves no hay nada que devolver; con claves, el error es real
            raise HTTPException(status_code=422, detail=str(e))

    # 2. Google Routes: ruta estándar (sin dimensiones fuera de EE.UU.)
    if google_key:
        try:
            return await _calcular_google(google_key, req)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    # 3. Sin claves: mock para desarrollo
    return _mock(req)

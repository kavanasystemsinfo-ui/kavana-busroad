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
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["ruta"])

ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-hgv"
ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
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
    vehiculo: Dimensiones = Dimensiones()


class PuntoRiesgo(BaseModel):
    nombre: str
    tipo: str
    descripcion: str


class RutaResponse(BaseModel):
    origen: str
    destino: str
    distancia_km: float
    duracion_min: float
    polyline: str
    pasos: list[str]
    riesgos: list[PuntoRiesgo] = []
    motor: str  # "openrouteservice" | "google-routes" | "mock"


# ------------------------------------------------------------------ helpers
async def _geocodificar_ors(api_key: str, texto: str) -> list[float] | None:
    """Convierte una dirección en coordenadas [lng, lat] con ORS."""
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            ORS_GEOCODE_URL,
            params={"text": texto, "api_key": api_key, "size": 1},
        )
    if r.status_code != 200:
        return None
    feats = r.json().get("features", [])
    if not feats:
        return None
    return feats[0].get("geometry", {}).get("coordinates")


async def _calcular_ors(api_key: str, req: RutaRequest) -> RutaResponse:
    """Ruta con restricciones reales de dimensiones (perfil driving-hgv)."""
    origen = await _geocodificar_ors(api_key, req.origen)
    destino = await _geocodificar_ors(api_key, req.destino)
    if not origen or not destino:
        raise ValueError("No pude localizar origen o destino. Prueba con nombres más exactos.")

    v = req.vehiculo
    payload = {
        "coordinates": [origen, destino],
        "options": {
            "profile_params": {
                "restrictions": {
                    "height": v.alto_m,
                    "width": v.ancho_m,
                    "length": v.largo_m,
                    "weight": float(v.peso_kg),
                }
            }
        },
    }
    async with httpx.AsyncClient(timeout=40) as client:
        r = await client.post(
            ORS_DIRECTIONS_URL,
            json=payload,
            headers={"Authorization": api_key, "Content-Type": "application/json"},
        )
    if r.status_code != 200:
        raise ValueError(f"OpenRouteService respondió {r.status_code}: {r.text[:300]}")

    route = r.json().get("routes", [{}])[0]
    summary = route.get("summary", {})
    pasos = []
    for seg in route.get("segments", []):
        for step in seg.get("steps", []):
            txt = step.get("instruction") or step.get("name") or ""
            if txt:
                pasos.append(txt)
    return RutaResponse(
        origen=req.origen,
        destino=req.destino,
        distancia_km=round(summary.get("distance", 0) / 1000, 1),
        duracion_min=round(summary.get("duration", 0) / 60, 1),
        polyline=route.get("geometry", ""),
        pasos=pasos[:15],
        motor="openrouteservice",
    )


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
            return _mock(req)

    # 2. Google Routes: ruta estándar (sin dimensiones fuera de EE.UU.)
    if google_key:
        try:
            return await _calcular_google(google_key, req)
        except ValueError:
            return _mock(req)

    # 3. Sin claves: mock para desarrollo
    return _mock(req)

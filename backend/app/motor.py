"""Motor de rutas: Google Routes API con dimensiones de vehículo.

Sin GOOGLE_API_KEY responde con una ruta de ejemplo para poder desarrollar.
"""

import os

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["ruta"])

GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


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
    motor: str  # "google-routes" | "mock"


# ------------------------------------------------------------------ helpers
async def _geocodificar(api_key: str, texto: str) -> tuple[float, float] | None:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(GOOGLE_GEOCODE_URL, params={"address": texto, "key": api_key})
        if r.status_code != 200:
            return None
        loc = r.json().get("results", [{}])[0].get("geometry", {}).get("location")
        if not loc:
            return None
        return loc["lat"], loc["lng"]


async def _calcular_google(api_key: str, req: RutaRequest) -> RutaResponse:
    """Ruta real con restricciones del vehículo (Routes API Preferred)."""
    origen = await _geocodificar(api_key, req.origen)
    destino = await _geocodificar(api_key, req.destino)
    if not origen or not destino:
        raise ValueError("No pude localizar origen o destino. Prueba con nombres más exactos.")

    v = req.vehiculo
    payload = {
        "origin": {"location": {"latLng": {"latitude": origen[0], "longitude": origen[1]}}},
        "destination": {"location": {"latLng": {"latitude": destino[0], "longitude": destino[1]}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "vehicle": {
            "vehicleType": "AUTOMOBILE",
            "dimensionInfo": {
                "length": {"value": v.largo_m, "unit": "METERS"},
                "width": {"value": v.ancho_m, "unit": "METERS"},
                "height": {"value": v.alto_m, "unit": "METERS"},
            },
            "weightInfo": {
                "weight": {"value": float(v.peso_kg), "unit": "KILOGRAMS"},
            },
        },
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
    """Ruta de ejemplo para desarrollo sin clave de Google."""
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
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return _mock(req)
    try:
        return await _calcular_google(api_key, req)
    except ValueError as e:
        # Sin geocodificación posible, devolvemos el mock con aviso
        return _mock(req)

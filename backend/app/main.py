"""Kavana BusRoad — API de rutas para vehículos grandes.

Backend en FastAPI (Python) que calcula rutas evitando puentes, túneles y
calles donde no cabe el vehículo (autobuses, furgonetas, grúas...).

Motor de rutas: Google Routes API con restricciones de dimensiones del
vehículo. Sin clave configurada, responde con una ruta de ejemplo (mock)
para poder desarrollar sin coste.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .motor import router as motor_router

app = FastAPI(
    title="Kavana BusRoad API",
    description="Rutas para vehículos grandes con restricciones de dimensiones",
    version="0.1.0",
)

# CORS: la PWA (Vercel) y el desarrollo local pueden llamar a la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://busroad.kavanasystems.com",
        "https://kavana-busroad.vercel.app",
        "https://frontend-605yf47nv-vistaprods-projects.vercel.app",
        "https://frontend-alpha-eight-85.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(motor_router)


@app.get("/api/v1/health")
def health():
    import os
    motor = "mock"
    if os.environ.get("ORS_API_KEY"):
        motor = "openrouteservice"
    elif os.environ.get("GOOGLE_API_KEY"):
        motor = "google-routes"
    return {"status": "ok", "motor": motor}

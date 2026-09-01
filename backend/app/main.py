"""Kavana BusRoad — API de rutas para vehículos grandes.

Backend en FastAPI (Python) que calcula rutas evitando puentes, túneles y
calles donde no cabe el vehículo (autobuses, furgonetas, grúas...).

Motor de rutas: Google Routes API con restricciones de dimensiones del
vehículo. Sin clave configurada, responde con una ruta de ejemplo (mock)
para poder desarrollar sin coste.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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
        "https://www.kavanasystems.com",
        "https://kavana-busroad.vercel.app",
        "https://frontend-605yf47nv-vistaprods-projects.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(motor_router)


# ---------------------------------------------------------------- asistente
# Asistente técnico RAG (público, sin auth): un reclutador pregunta cómo
# funciona el proyecto y el bot responde solo con la documentación real.
class AskRequest(BaseModel):
    question: str = Field(min_length=4, max_length=500)


@app.post("/api/v1/assistant/ask-tech")
async def ask_tech(req: AskRequest, request: Request):
    from .assistant import enforce_rate_limit, responder

    ip = request.client.host if request.client else "unknown"
    try:
        enforce_rate_limit(ip)
    except Exception as e:
        return JSONResponse(status_code=429, content={"error": str(e)})

    import os

    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return JSONResponse(
            status_code=500,
            content={"error": "Asistente no configurado (falta OPENROUTER_API_KEY en el servidor)"},
        )

    try:
        result = await responder(api_key, req.question.strip())
        return {"success": True, **result}
    except Exception as e:
        logger = logging.getLogger("busroad.assistant")
        logger.error("Asistente: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": "El asistente falló al responder. Inténtalo de nuevo en un momento."},
        )


@app.get("/api/v1/assistant/stats")
def assistant_stats():
    from .assistant import estadisticas_corpus

    return estadisticas_corpus()


@app.get("/api/v1/health")
def health():
    import os
    motor = "mock"
    if os.environ.get("ORS_API_KEY"):
        motor = "openrouteservice"
    elif os.environ.get("GOOGLE_API_KEY"):
        motor = "google-routes"
    return {"status": "ok", "motor": motor}

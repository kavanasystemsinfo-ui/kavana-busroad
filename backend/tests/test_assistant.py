"""Tests del asistente técnico RAG de BusRoad (estándar kavana-chatbot-standard)."""

import asyncio
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app import assistant


def _indice_test():
    """Índice con un corpus controlado: 2 ADRs falsos + 1 plantilla + README."""
    tmp = Path("/tmp/busroad_corpus_test")
    adr = tmp / "docs" / "adr"
    adr.mkdir(parents=True, exist_ok=True)
    (tmp / "README.md").write_text(
        "# Kavana BusRoad\n\nProyecto de rutas para vehículos grandes que evita puentes y túneles.\n"
        "Backend FastAPI con OpenRouteService, frontend Vue 3.\n"
    )
    (adr / "001-motor.md").write_text(
        "## Decisión\n\nSe eligió OpenRouteService con perfil driving-hgv para respetar "
        "las restricciones de dimensiones del vehículo en Europa.\n"
    )
    (adr / "002-template.md").write_text(
        "## Plantilla\n\nEsto es una plantilla de ADR y no debe indexarse.\n"
    )

    import importlib

    prev = os.environ.get("BUSROAD_DOCS_ROOT")
    os.environ["BUSROAD_DOCS_ROOT"] = str(tmp)
    importlib.reload(assistant)
    if prev is None:
        os.environ.pop("BUSROAD_DOCS_ROOT", None)
    else:
        os.environ["BUSROAD_DOCS_ROOT"] = prev
    return assistant.construir_indice(assistant.cargar_corpus())


def test_corpus_excluye_plantillas():
    idx = _indice_test()
    fuentes = {c["fuente"] for c in idx["chunks"]}
    assert "docs/adr/002-template.md" not in fuentes


def test_corpus_incluye_adr_res_README():
    idx = _indice_test()
    fuentes = {c["fuente"] for c in idx["chunks"]}
    assert "docs/adr/001-motor.md" in fuentes
    assert "README.md" in fuentes


def test_pregunta_fuera_de_corpus_responde_sin_llm():
    idx = _indice_test()
    docs = assistant.buscar(idx, "cuál es el color favorito del fundador de la empresa de Jorge")
    assert not docs or docs[0]["score"] < 0.02


def test_rate_limit_ventana():
    assistant._preguntas_ip.clear()
    with pytest.raises(assistant.RateLimitExceeded):
        for _ in range(assistant.MAX_PREGUNTAS_DIA_POR_IP + 1):
            assistant.enforce_rate_limit("1.2.3.4")


def test_rate_limit_diario():
    import time as _t

    assistant._preguntas_ip.clear()
    # Simular que esta IP ya agotó el cupo de hoy
    clave = f"{_t.strftime('%Y-%m-%d')}|5.6.7.8"
    assistant._preguntas_ip[clave] = assistant.MAX_PREGUNTAS_DIA_POR_IP
    with pytest.raises(assistant.RateLimitExceeded):
        assistant.enforce_rate_limit("5.6.7.8")
    # Otra IP distinta puede seguir preguntando el mismo día
    assistant.enforce_rate_limit("9.9.9.9")
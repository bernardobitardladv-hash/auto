"""Ponto de entrada da automação CRM DL.

O serviço começa em modo seguro: recebe e valida a configuração, mas não cria
tarefas nem altera negócios enquanto AUTOMATION_ENABLED não for explicitamente
habilitado para o piloto.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status

app = FastAPI(title="Automação CRM DL", version="0.1.0")


def configured() -> bool:
    """Indica se as credenciais mínimas foram configuradas no ambiente."""
    return all(os.getenv(key) for key in ("BITRIX_CLIENT_ID", "BITRIX_CLIENT_SECRET"))


def enabled() -> bool:
    return os.getenv("AUTOMATION_ENABLED", "false").strip().lower() == "true"


@app.get("/health")
def health() -> dict[str, Any]:
    """Healthcheck sem expor segredos ou dados de CRM."""
    return {
        "status": "ok",
        "configured": configured(),
        "automation_enabled": enabled(),
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/bitrix/install")
async def install(request: Request) -> dict[str, str]:
    """Recebe a instalação OAuth; a persistência será habilitada com o Postgres."""
    payload = await request.form()
    if not payload.get("AUTH_ID") and not payload.get("auth"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payload OAuth ausente")
    # Não registrar payload: ele pode conter tokens OAuth.
    return {"status": "received"}


@app.post("/bitrix/robot")
async def robot(request: Request) -> dict[str, str]:
    """Endpoint dos robôs próprios. Escritas ficam bloqueadas até o piloto."""
    if not configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="app não configurado")
    _ = await request.form()  # nunca registrar parâmetros de negócio
    return {"status": "accepted" if enabled() else "dry-run"}


@app.post("/bitrix/event")
async def event(request: Request) -> dict[str, str]:
    """Endpoint de eventos Bitrix; a implementação de deduplicação vem no próximo commit."""
    if not configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="app não configurado")
    _ = await request.form()
    return {"status": "accepted" if enabled() else "dry-run"}

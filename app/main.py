"""Ponto de entrada da automação CRM DL.

O serviço começa em modo seguro: recebe e valida a configuração, mas não cria
tarefas nem altera negócios enquanto AUTOMATION_ENABLED não for explicitamente
habilitado para o piloto.
"""

from __future__ import annotations

import os
import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from .db import Database
from .bitrix import BitrixClient
from .workflow import Workflow

app = FastAPI(title="Automação CRM DL", version="0.1.0")


def configured() -> bool:
    """Indica se as credenciais mínimas foram configuradas no ambiente."""
    if os.getenv("BITRIX_WEBHOOK_URL", "").strip():
        return True
    return all(
        os.getenv(key)
        for key in ("BITRIX_CLIENT_ID", "BITRIX_CLIENT_SECRET")
    )


def enabled() -> bool:
    return (os.getenv("AUTOMATION_ENABLED", "false").strip().lower() == "true" and os.getenv("PILOT_UNLOCK", "false").strip().lower() == "true")


def valid_event_token(data: dict[str, str]) -> bool:
    """Valida tokens dos webhooks de saída sem registrá-los."""
    allowed = {token.strip() for token in os.getenv("BITRIX_EVENT_TOKENS", "").split(",") if token.strip()}
    if not allowed:
        return False
    received = data.get("auth[application_token]") or data.get("application_token") or data.get("APPLICATION_TOKEN")
    return received in allowed


@app.on_event("startup")
async def startup() -> None:
    app.state.db = Database(os.getenv("DATABASE_URL"))
    app.state.workflow = Workflow(app.state.db, enabled())
    asyncio.create_task(_connect_db())

async def _connect_db() -> None:
    try:
        await asyncio.wait_for(app.state.db.start(), timeout=15)
    except Exception:
        pass

@app.on_event("shutdown")
async def shutdown() -> None:
    if getattr(app.state, "db", None): await app.state.db.close()


@app.get("/health")
def health() -> dict[str, Any]:
    """Healthcheck sem expor segredos ou dados de CRM."""
    return {
        "status": "ok",
        "configured": configured(),
        "automation_enabled": enabled(),
        "database_ready": bool(getattr(getattr(app, "state", None), "db", None) and getattr(app.state.db, "pool", None)),
        "time": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/diagnostics")
async def diagnostics() -> dict[str, bool]:
    """Diagnóstico sem expor segredos: usado somente na validação do piloto."""
    return {
        "database_ready": bool(app.state.db.pool),
        "oauth_ready": bool(await app.state.db.oauth()),
        "webhook_ready": bool(os.getenv("BITRIX_WEBHOOK_URL", "").strip()),
    }


@app.get("/diagnostics/crm-fields")
async def diagnostic_crm_fields() -> dict[str, dict[str, str | None]]:
    """Expõe apenas metadados dos campos operacionais, nunca valores de clientes."""
    raw = await BitrixClient(app.state.db).call("crm.item.fields", {"entityTypeId": 2})
    fields = raw.get("fields", raw) if isinstance(raw, dict) else {}
    keywords = ("resultado", "retorno", "handoff", "piloto", "sdr resp")
    return {
        name: {"title": meta.get("title"), "type": meta.get("type")}
        for name, meta in fields.items()
        if isinstance(meta, dict) and (name in {"ufCrm_1782774357152", "ufCrmHorarioRetorno", "ufCrmSdrResp", "ufCrmHandoff", "ufCrmPilotoAutomacao"} or any(word in str(meta.get("title", "")).lower() for word in keywords))
    }


@app.post("/bitrix/install")
async def install(request: Request) -> dict[str, str]:
    """Recebe e armazena o retorno OAuth da instalação do Bitrix."""
    data = {str(key): str(value) for key, value in request.query_params.multi_items()}
    try:
        payload = await request.form()
        data.update({str(key): str(value) for key, value in payload.multi_items()})
    except Exception:
        pass
    if not any(key in data for key in ("AUTH_ID", "auth[access_token]", "access_token")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payload OAuth ausente")
    await app.state.db.save_oauth(data)
    return {"status": "stored"}


@app.post("/bitrix/robot")
async def robot(request: Request) -> dict[str, str]:
    """Endpoint dos robôs próprios. Escritas ficam bloqueadas até o piloto."""
    if not configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="app não configurado")
    _ = await request.form()  # nunca registrar parâmetros de negócio
    return {"status": "accepted" if enabled() else "dry-run"}


@app.post("/bitrix/event")
async def event(request: Request) -> dict[str, str]:
    """Recebe eventos autenticados do Bitrix e os encaminha ao motor."""
    if not configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="app não configurado")
    data = {str(key): str(value) for key, value in (await request.form()).multi_items()}
    if not valid_event_token(data):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token de evento inválido")
    return {"status": await app.state.workflow.event(data)}


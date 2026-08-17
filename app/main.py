"""Ponto de entrada da automação CRM DL.

O serviço começa em modo seguro: recebe e valida a configuração, mas não cria
tarefas nem altera negócios enquanto AUTOMATION_ENABLED não for explicitamente
habilitado para o piloto.
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import FastAPI, HTTPException, Request, status

app = FastAPI(title="Automação CRM DL", version="0.1.0")


def configured() -> bool:
    """Indica se as credenciais mínimas foram configuradas no ambiente."""
    return all(os.getenv(key) for key in ("BITRIX_CLIENT_ID", "BITRIX_CLIENT_SECRET"))


def enabled() -> bool:
    return os.getenv("AUTOMATION_ENABLED", "false").strip().lower() == "true"


async def ensure_schema() -> None:
    """Cria o armazenamento local do token OAuth sem expor o conteúdo em logs."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return
    connection = await asyncpg.connect(database_url)
    try:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_installation (
                installation_key TEXT PRIMARY KEY,
                payload_json JSONB NOT NULL,
                received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    finally:
        await connection.close()


@app.on_event("startup")
async def startup() -> None:
    await ensure_schema()


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
    """Recebe e armazena o retorno OAuth da instalação do Bitrix."""
    payload = await request.form()
    data = {str(key): str(value) for key, value in payload.multi_items()}
    if not any(key in data for key in ("AUTH_ID", "auth[access_token]", "access_token")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payload OAuth ausente")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="banco não configurado")
    connection = await asyncpg.connect(database_url)
    try:
        await connection.execute(
            """
            INSERT INTO oauth_installation (installation_key, payload_json, received_at)
            VALUES ('bitrix', $1::jsonb, NOW())
            ON CONFLICT (installation_key)
            DO UPDATE SET payload_json = EXCLUDED.payload_json, received_at = EXCLUDED.received_at
            """,
            json.dumps(data),
        )
    finally:
        await connection.close()
    return {"status": "stored"}


@app.post("/bitrix/robot")
async def robot(request: Request) -> dict[str, str]:
    """Endpoint dos robôs próprios. Escritas ficam bloqueadas até o piloto."""
    if not configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="app não configurado")
    _ = await request.form()
    return {"status": "accepted" if enabled() else "dry-run"}


@app.post("/bitrix/event")
async def event(request: Request) -> dict[str, str]:
    """Endpoint de eventos Bitrix; a deduplicação será adicionada antes do piloto."""
    if not configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="app não configurado")
    _ = await request.form()
    return {"status": "accepted" if enabled() else "dry-run"}

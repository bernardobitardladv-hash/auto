from __future__ import annotations

from datetime import datetime, timezone
import json
import os

from .bitrix import BitrixClient
from .engine import next_step

STAGES = {(0, "PREPARATION"): "SDR_TENTATIVA", (0, "UC_OIFN4M"): "SDR_RETORNO", (23, "NEW"): "BDR_CONTATO", (23, "PREPARATION"): "BDR_RECUPERAR"}
RESULT_FIELD = "ufCrm_1782774357152"
RESULT_ROUTES = {
    (0, "PREPARATION"): {"81": "UC_OIFN4M", "51": "UC_58ABGO", "47": "LOSE", "57": "APOLOGY"},
    (0, "UC_OIFN4M"): {"51": "UC_58ABGO", "47": "LOSE", "55": "UC_QK2GWQ"},
    (23, "NEW"): {"49": "C23:EXECUTING", "51": "C23:PREPARATION", "47": "C23:LOSE"},
    (23, "PREPARATION"): {"49": "C23:EXECUTING"},
}


def _stage(deal):
    return int(deal.get("categoryId") or 0), str(deal.get("stageId") or "").split(":")[-1]


def _version(deal):
    return deal.get("updatedTime") or deal.get("dateModify") or json.dumps({"stage": deal.get("stageId"), "category": deal.get("categoryId")}, sort_keys=True)


def _result(deal):
    value = deal.get(RESULT_FIELD) or deal.get(RESULT_FIELD.upper())
    if isinstance(value, list): value = value[0] if value else None
    return str(value) if value is not None else ""


class Workflow:
    def __init__(self, db, enabled): self.db, self.enabled = db, enabled

    async def event(self, data):
        event = data.get("event") or data.get("EVENT") or ""
        entity_id = data.get("data[FIELDS][ID]") or data.get("FIELDS[ID]") or data.get("id")
        if not entity_id: return "ignored"
        if not self.enabled: return "dry-run"
        if event.upper().startswith("ONCRM"): return await self.deal_changed(int(entity_id), event)
        if event.upper() == "ONTASKUPDATE": return await self.task_changed(int(entity_id), event)
        return "accepted"

    async def task_changed(self, task_id, event="ONTASKUPDATE"):
        client = BitrixClient(self.db)
        task_result = await client.task(task_id)
        task = task_result.get("task") or task_result
        version = task.get("changedDate") or task.get("dateChanged") or task_id
        if not await self.db.mark_event(f"{event}:{task_id}:{version}"): return "duplicate"
        state = await self.db.state_by_task(task_id)
        if not state: return "task-untracked"
        if str(task.get("status") or "") not in ("5", "completed"): return "task-open"
        await self.db.save_state(state["deal_id"], category_id=state["category_id"], stage_id=state["stage_id"], cadence=state["cadence"], position=int(state["position"])+1, started_at=state["started_at"], anchor_at=state["anchor_at"], open_task_id=None, next_due=None, active=True)
        return await self.deal_changed(int(state["deal_id"]), "task-complete", dedupe=False)

    async def deal_changed(self, deal_id, event="ONCRMDEALUPDATE", dedupe=True):
        client = BitrixClient(self.db); deal = await client.deal(deal_id)
        if dedupe and not await self.db.mark_event(f"{event}:{deal_id}:{_version(deal)}"): return "duplicate"
        pilot_id = os.getenv("PILOT_DEAL_ID", "").strip()
        if str(deal.get("ufCrmPilotoAutomacao") or deal.get("UF_CRM_PILOTO_AUTOMACAO") or "N") != "Y" and pilot_id != str(deal_id): return "outside-pilot"
        async with self.db.lock_deal(deal_id):
            category, stage = _stage(deal); cadence = STAGES.get((category, stage)); state = await self.db.state(deal_id)
            result = _result(deal)
            destination = RESULT_ROUTES.get((category, stage), {}).get(result)
            if destination:
                await client.update_deal(deal_id, {"stageId": destination})
                if state and state["open_task_id"]:
                    try: await client.complete_task(int(state["open_task_id"]))
                    except Exception: pass
                await self.db.deactivate_state(deal_id)
                return "moved-by-result"
            if category == 0 and stage == "UC_58ABGO":
                if not state or state["cadence"] != "SDR_HANDOFF" or not state["open_task_id"]:
                    if not deal.get("assignedById"): raise ValueError("negócio sem responsável")
                    handoff = await client.add_task({"TITLE": f"DL | Resumo / Handoff | negócio {deal_id}", "DESCRIPTION": "Preencher Handoff: temperatura, perfil, detalhes, dores, impedimentos e objeções. Depois, marcar ganho manual.", "RESPONSIBLE_ID": deal["assignedById"], "DEADLINE": datetime.now(timezone.utc).replace(hour=20, minute=0, second=0, microsecond=0).isoformat()})
                    handoff_id = int((handoff.get("task") or {}).get("id"))
                    await self.db.save_state(deal_id, category_id=category, stage_id=deal.get("stageId"), cadence="SDR_HANDOFF", position=0, started_at=datetime.now(timezone.utc), anchor_at=None, open_task_id=handoff_id, next_due=None, active=True)
                    return "handoff-created"
                return "waiting-handoff"
            if not cadence:
                if state and state["active"]:
                    if state["open_task_id"]:
                        try: await client.complete_task(int(state["open_task_id"]))
                        except Exception: pass
                    await self.db.deactivate_state(deal_id)
                    return "cadence-cleared"
                return "no-cadence"
            if state and state["open_task_id"] and state["cadence"] == cadence: return "waiting-task"
            if state and state["open_task_id"] and state["cadence"] != cadence:
                try: await client.complete_task(int(state["open_task_id"]))
                except Exception: pass
                await self.db.deactivate_state(deal_id); state = None
            started = state["started_at"] if state and state["cadence"] == cadence else datetime.now(timezone.utc)
            position = int(state["position"]) if state and state["cadence"] == cadence else 0
            step = next_step(cadence, position, started, deal.get("ufCrmHorarioRetorno"), result=result)
            if step["kind"] == "exhausted":
                destination = step["destination"]
                await client.update_deal(deal_id, {"categoryId": destination["category_id"], "stageId": destination["stage_id"]})
                await self.db.deactivate_state(deal_id)
                return "moved"
            responsible = deal.get("assignedById")
            if cadence == "BDR_RECUPERAR" and position == 1:
                responsible = deal.get("ufCrmSdrResp") or responsible
            if not responsible: raise ValueError("negócio sem responsável")
            touch = step["task"]
            result = await client.add_task({"TITLE": f"DL | {touch['label']} | negócio {deal_id}", "DESCRIPTION": f"Executar {touch['channel']} e registrar o resultado no negócio.", "RESPONSIBLE_ID": responsible, "DEADLINE": step["due_at"]})
            raw_task_id = (result.get("task") or {}).get("id") if isinstance(result, dict) else None
            if raw_task_id is None: raise RuntimeError("Bitrix não retornou o ID da tarefa")
            await self.db.save_state(deal_id, category_id=category, stage_id=deal.get("stageId"), cadence=cadence, position=step["position"], started_at=started, anchor_at=deal.get("ufCrmHorarioRetorno"), open_task_id=int(raw_task_id), next_due=step["due_at"], active=True)
            return "task-created"


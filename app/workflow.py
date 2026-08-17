from __future__ import annotations
from datetime import datetime, timezone
from .engine import next_step
from .bitrix import BitrixClient

STAGES = {(0, "PREPARATION"): "SDR_TENTATIVA", (0, "UC_OIFN4M"): "SDR_RETORNO", (23, "NEW"): "BDR_CONTATO", (23, "PREPARATION"): "BDR_RECUPERAR"}

def _stage(deal):
    return int(deal.get("categoryId") or 0), str(deal.get("stageId") or "").split(":")[-1]

class Workflow:
    def __init__(self, db, enabled): self.db, self.enabled = db, enabled
    async def event(self, data):
        event = data.get("event") or data.get("EVENT") or ""
        deal_id = data.get("data[FIELDS][ID]") or data.get("FIELDS[ID]") or data.get("id")
        if not deal_id: return "ignored"
        if not await self.db.mark_event(f"{event}:{deal_id}:{data.get('ts') or ''}"): return "duplicate"
        if not self.enabled: return "dry-run"
        if event.upper().startswith("ONCRM"): return await self.deal_changed(int(deal_id))
        if event.upper() == "ONTASKUPDATE": return await self.task_changed(int(deal_id))
        return "accepted"
    async def task_changed(self, task_id):
        state = await self.db.state_by_task(task_id)
        if not state: return "task-untracked"
        task = await BitrixClient(self.db).task(task_id)
        status = str((task.get("task") or task).get("status") or "")
        if status not in ("5", "completed"): return "task-open"
        await self.db.save_state(state["deal_id"], category_id=state["category_id"], stage_id=state["stage_id"], cadence=state["cadence"], position=int(state["position"])+1, started_at=state["started_at"], anchor_at=state["anchor_at"], open_task_id=None, next_due=None, active=True)
        return await self.deal_changed(int(state["deal_id"]))
    async def deal_changed(self, deal_id):
        client = BitrixClient(self.db); deal = await client.deal(deal_id)
        if str(deal.get("ufCrmPilotoAutomacao") or deal.get("UF_CRM_PILOTO_AUTOMACAO") or "N") != "Y": return "outside-pilot"
        category, stage = _stage(deal); cadence = STAGES.get((category, stage)); state = await self.db.state(deal_id)
        if not cadence: return "no-cadence"
        if state and state["open_task_id"] and state["cadence"] == cadence: return "waiting-task"
        if state and state["open_task_id"] and state["cadence"] != cadence:
            try: await client.complete_task(int(state["open_task_id"]))
            except Exception: pass
        now = datetime.now(timezone.utc); started = state["started_at"] if state and state["cadence"] == cadence else now
        position = int(state["position"]) if state and state["cadence"] == cadence else 0
        step = next_step(cadence, position, started, deal.get("ufCrmHorarioRetorno"))
        if step["kind"] == "exhausted":
            dest = step["destination"]; await client.update_deal(deal_id, {"categoryId": dest["category_id"], "stageId": dest["stage_id"]}); return "moved"
        touch = step["task"]; result = await client.add_task({"TITLE": f"DL | {touch['label']} | negócio {deal_id}", "DESCRIPTION": f"Executar {touch['channel']} e registrar o resultado no negócio.", "RESPONSIBLE_ID": deal.get("assignedById"), "DEADLINE": step["due_at"], "UF_CRM_TASK": [f"D_{deal_id}"]})
        task_id = (result.get("task") or {}).get("id") if isinstance(result, dict) else None
        await self.db.save_state(deal_id, category_id=category, stage_id=deal.get("stageId"), cadence=cadence, position=step["position"], started_at=started, anchor_at=deal.get("ufCrmHorarioRetorno"), open_task_id=task_id, next_due=step["due_at"], active=True)
        return "task-created"


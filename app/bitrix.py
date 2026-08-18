from __future__ import annotations
import os
import httpx

class BitrixClient:
    def __init__(self, db): self.db = db
    async def call(self, method, params):
        """Chama a API sem expor credenciais em logs ou respostas."""
        webhook = os.getenv('BITRIX_WEBHOOK_URL', '').strip().rstrip('/')
        if webhook:
            url = f"{webhook}/{method}.json"
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(url, json=params)
                response.raise_for_status(); data = response.json()
            if 'error' in data: raise RuntimeError(f"Bitrix {data['error']}")
            return data.get('result', data)
        row = await self.db.oauth()
        if not row or not row['access_token']: raise RuntimeError('OAuth Bitrix não instalado')
        endpoint = row['client_endpoint'] or f"https://{row['domain']}/rest/"
        url = endpoint.rstrip('/') + '/' + method + '.json'
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, data={**params, 'auth': row['access_token']})
            response.raise_for_status(); data = response.json()
        if 'error' in data: raise RuntimeError(f"Bitrix {data['error']}")
        return data.get('result', data)
    async def deal(self, deal_id):
        result = await self.call('crm.item.get', {'entityTypeId': 2, 'id': deal_id})
        return result.get('item', result) if isinstance(result, dict) else result
    async def update_deal(self, deal_id, fields): return await self.call('crm.item.update', {'entityTypeId': 2, 'id': deal_id, 'fields': fields})
    async def add_task(self, fields): return await self.call('tasks.task.add', {'fields': fields})
    async def task(self, task_id): return await self.call('tasks.task.get', {'taskId': task_id})
    async def complete_task(self, task_id): return await self.call('tasks.task.complete', {'taskId': task_id})
    async def bind_event(self, event_name, handler):
        return await self.call('event.bind', {'event': event_name, 'handler': handler})


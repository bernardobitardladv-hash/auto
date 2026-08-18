from __future__ import annotations
import os
import httpx

class BitrixClient:
    _result_map = None
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
    async def result_code(self, raw_value):
        value = str(raw_value or '')
        if value in {'45','47','49','51','55','57','71','73','81'}: return value
        if self.__class__._result_map is None:
            mapping = {}
            labels = {'não atendeu':'45','desqualificado':'47','agendado':'49','qualificado':'51','sem interesse':'55','telefone incorreto':'57','não compareceu':'71','reagendado':'73','atendeu - pediu retorno':'81','atendeu-pediu retorno':'81'}
            for field_name in ('UF_CRM_RESULTADO_TENTATIVA','UF_CRM_1782774357152'):
                rows = await self.call('crm.deal.userfield.list', {'filter': {'FIELD_NAME': field_name}})
                rows = rows if isinstance(rows, list) else rows.get('items', []) if isinstance(rows, dict) else []
                for row in rows:
                    details = row
                    if not row.get('LIST') and (row.get('ID') or row.get('id')):
                        details = await self.call('crm.deal.userfield.get', {'id': row.get('ID') or row.get('id')})
                    for item in details.get('LIST', []) or details.get('list', []):
                        item_id = str(item.get('ID') or item.get('id') or '')
                        code = str(item.get('XML_ID') or item.get('xmlId') or '')
                        label = str(item.get('VALUE') or item.get('value') or '').strip().lower()
                        mapping[item_id] = code if code in labels.values() else labels.get(label, '')
            self.__class__._result_map = mapping
        return self.__class__._result_map.get(value, value)


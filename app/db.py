from __future__ import annotations
import json
import asyncpg

SCHEMA = """
CREATE TABLE IF NOT EXISTS oauth_installation (installation_key TEXT PRIMARY KEY, access_token TEXT, refresh_token TEXT, expires_at TIMESTAMPTZ, member_id TEXT, domain TEXT, client_endpoint TEXT, application_token TEXT, payload_json JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS deal_state (deal_id BIGINT PRIMARY KEY, category_id INT, stage_id TEXT, cadence TEXT, position INT NOT NULL DEFAULT 0, started_at TIMESTAMPTZ, anchor_at TIMESTAMPTZ, open_task_id BIGINT, next_due TIMESTAMPTZ, event_version TEXT, last_error TEXT, active BOOLEAN NOT NULL DEFAULT TRUE, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS processed_event (event_key TEXT PRIMARY KEY, received_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
"""
class Database:
    def __init__(self, url): self.url, self.pool = url, None
    async def start(self):
        if not self.url: return
        self.pool = await asyncpg.create_pool(self.url, min_size=1, max_size=4)
        async with self.pool.acquire() as c:
            for statement in SCHEMA.split(';'):
                if statement.strip():
                    try: await c.execute(statement)
                    except Exception: pass
    async def close(self):
        if self.pool: await self.pool.close()
    async def save_oauth(self, data):
        if not self.pool: return
        async with self.pool.acquire() as c:
            await c.execute("""INSERT INTO oauth_installation(installation_key,access_token,refresh_token,expires_at,member_id,domain,client_endpoint,application_token,payload_json) VALUES('bitrix',$1,$2,CASE WHEN $3::int IS NULL THEN NULL ELSE NOW()+($3::int||' seconds')::interval END,$4,$5,$6,$7,$8::jsonb) ON CONFLICT(installation_key) DO UPDATE SET access_token=EXCLUDED.access_token,refresh_token=EXCLUDED.refresh_token,expires_at=EXCLUDED.expires_at,member_id=EXCLUDED.member_id,domain=EXCLUDED.domain,client_endpoint=EXCLUDED.client_endpoint,application_token=EXCLUDED.application_token,payload_json=EXCLUDED.payload_json,updated_at=NOW()""", data.get('AUTH_ID') or data.get('auth[access_token]') or data.get('access_token'), data.get('REFRESH_ID') or data.get('auth[refresh_token]') or data.get('refresh_token'), data.get('AUTH_EXPIRES') or data.get('auth[expires]'), data.get('MEMBER_ID') or data.get('auth[member_id]'), data.get('DOMAIN') or data.get('auth[domain]'), data.get('CLIENT_ENDPOINT') or data.get('auth[client_endpoint]'), data.get('APPLICATION_TOKEN') or data.get('auth[application_token]'), json.dumps(data))
    async def oauth(self):
        if not self.pool: return None
        async with self.pool.acquire() as c: return await c.fetchrow("SELECT * FROM oauth_installation WHERE installation_key='bitrix'")
    async def mark_event(self, key):
        if not self.pool: return True
        async with self.pool.acquire() as c: return bool(await c.fetchval("INSERT INTO processed_event(event_key) VALUES($1) ON CONFLICT DO NOTHING RETURNING event_key", key))
    async def state(self, deal_id):
        if not self.pool: return None
        async with self.pool.acquire() as c: return await c.fetchrow("SELECT * FROM deal_state WHERE deal_id=$1", deal_id)
    async def state_by_task(self, task_id):
        if not self.pool: return None
        async with self.pool.acquire() as c: return await c.fetchrow("SELECT * FROM deal_state WHERE open_task_id=$1", task_id)
    async def save_state(self, deal_id, **values):
        if not self.pool: return
        keys = ['category_id','stage_id','cadence','position','started_at','anchor_at','open_task_id','next_due','event_version','last_error','active']
        async with self.pool.acquire() as c:
            await c.execute("INSERT INTO deal_state(deal_id,"+','.join(keys)+") VALUES($1,"+','.join(f'${i}' for i in range(2,len(keys)+2))+") ON CONFLICT(deal_id) DO UPDATE SET "+','.join(f'{k}=EXCLUDED.{k}' for k in keys)+",updated_at=NOW()", deal_id, *[values.get(k) for k in keys])


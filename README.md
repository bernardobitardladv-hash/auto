# Automação CRM DL

Aplicação OAuth local do Bitrix24 para centralizar as cadências e tarefas do CRM.

## Segurança operacional

- Credenciais vivem apenas nas variáveis do Railway; `.env` não é versionado.
- O serviço começa com `AUTOMATION_ENABLED=false`: não cria tarefas nem altera negócios.
- A ativação só será feita após um piloto completo com `ufCrmPilotoAutomacao = Y`.

## Endpoints

- `GET /health`: saúde da aplicação, sem segredos.
- `POST /bitrix/install`: callback de instalação OAuth.
- `POST /bitrix/robot`: handler dos robôs próprios.
- `POST /bitrix/event`: recebimento de eventos Bitrix.

O próximo incremento adiciona Postgres, renovação OAuth e a cadência SDR do piloto com idempotência.

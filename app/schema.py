from __future__ import annotations

RESULT_OPTIONS = (
    ("45", "Não atendeu"),
    ("47", "Desqualificado"),
    ("49", "Agendado"),
    ("51", "Qualificado"),
    ("55", "Sem Interesse"),
    ("57", "Telefone Incorreto"),
    ("71", "Não Compareceu"),
    ("73", "Reagendado"),
    ("81", "Atendeu - Pediu Retorno"),
)

FIELD_SPECS = (
    {
        "FIELD_NAME": "UF_CRM_RESULTADO_TENTATIVA",
        "EDIT_FORM_LABEL": "Resultado da Tentativa",
        "LIST_COLUMN_LABEL": "Resultado da Tentativa",
        "USER_TYPE_ID": "enumeration",
        "LIST": [
            {"VALUE": label, "XML_ID": code, "SORT": (index + 1) * 10, "DEF": "N"}
            for index, (code, label) in enumerate(RESULT_OPTIONS)
        ],
    },
    {"FIELD_NAME": "UF_CRM_HORARIO_RETORNO", "EDIT_FORM_LABEL": "Horário de Retorno", "LIST_COLUMN_LABEL": "Horário de Retorno", "USER_TYPE_ID": "datetime"},
    {"FIELD_NAME": "UF_CRM_SDR_RESP", "EDIT_FORM_LABEL": "SDR Original", "LIST_COLUMN_LABEL": "SDR Original", "USER_TYPE_ID": "employee"},
    {"FIELD_NAME": "UF_CRM_HANDOFF", "EDIT_FORM_LABEL": "Handoff", "LIST_COLUMN_LABEL": "Handoff", "USER_TYPE_ID": "string", "MULTIPLE": "N"},
    {"FIELD_NAME": "UF_CRM_PILOTO_AUTOMACAO", "EDIT_FORM_LABEL": "Piloto Automação", "LIST_COLUMN_LABEL": "Piloto Automação", "USER_TYPE_ID": "boolean"},
)


async def ensure_operational_fields(client):
    result = {}
    for spec in FIELD_SPECS:
        name = spec["FIELD_NAME"]
        found = await client.call("crm.deal.userfield.list", {"filter": {"FIELD_NAME": name}})
        items = found if isinstance(found, list) else found.get("items", []) if isinstance(found, dict) else []
        if items:
            result[name] = {"status": "existing", "id": str(items[0].get("ID") or items[0].get("id") or "")}
            continue
        created = await client.call("crm.deal.userfield.add", {"fields": spec})
        result[name] = {"status": "created", "id": str(created)}
    return result


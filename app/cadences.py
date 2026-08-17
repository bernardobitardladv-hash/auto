"""Cadências versionadas da automação CRM DL.

Cada toque é uma tarefa independente. A criação efetiva só ocorre quando o
piloto estiver habilitado; esta definição é a fonte de configuração do serviço.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Touch:
    day: int
    hour: int
    minute: int
    channel: str
    label: str


BDR_CONTACT = (
    Touch(0, 13, 0, "ligacao", "Ligação 1"),
    Touch(0, 15, 0, "ligacao", "Ligação 2"),
    Touch(0, 17, 0, "whatsapp", "WhatsApp 1"),
    Touch(1, 13, 0, "ligacao", "Ligação 3"),
    Touch(1, 15, 0, "ligacao", "Ligação 4"),
    Touch(1, 17, 0, "whatsapp", "WhatsApp 2 — última tentativa"),
)

CADENCES = {"BDR_CONTATO": BDR_CONTACT}

# Ao esgotar a sequência sem contato, o negócio segue para Recuperar / F-Up.
EXHAUSTION_STAGE = {"BDR_CONTATO": {"category_id": 23, "stage_id": "C23:PREPARATION"}}

"""Cadências versionadas da automação CRM DL.

Cada toque é uma tarefa independente. A criação efetiva só ocorre quando o
piloto estiver habilitado; esta definição é a fonte de configuração do serviço.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Touch:
    day: int
    hour: int | None
    minute: int = 0
    channel: str = "ligacao"
    label: str = ""
    offset_hours: int = 0
    conditional_result: str | None = None


BDR_CONTACT = (
    Touch(0, 13, 0, "ligacao", "Ligação 1"),
    Touch(0, 15, 0, "ligacao", "Ligação 2"),
    Touch(0, 17, 0, "whatsapp", "WhatsApp 1"),
    Touch(1, 13, 0, "ligacao", "Ligação 3"),
    Touch(1, 15, 0, "ligacao", "Ligação 4"),
    Touch(1, 17, 0, "whatsapp", "WhatsApp 2 — última tentativa"),
)

BDR_RECUPERAR = (
    Touch(0, None, channel="whatsapp", label="Recuperar — mensagem inicial", offset_hours=1),
    Touch(2, 13, channel="ligacao", label="Recuperar — ligação ao SDR original"),
    Touch(4, 13, channel="whatsapp", label="Recuperar — mensagem 2"),
    Touch(7, 13, channel="whatsapp", label="Recuperar — mensagem final"),
)
SDR_TENTATIVA = tuple(Touch(day, None, channel=channel, label=label) for day, channel, label in (
    (1, "ligacao", "SDR — tentativa 1"), (1, "whatsapp", "SDR — tentativa 2"),
    (2, "ligacao", "SDR — tentativa 3"), (3, "whatsapp", "SDR — tentativa 4"),
    (5, "ligacao", "SDR — tentativa 5"), (6, "whatsapp", "SDR — tentativa 6"),
    (8, "ligacao", "SDR — tentativa 7"), (10, "whatsapp", "SDR — tentativa 8"),
    (11, "whatsapp", "SDR — tentativa 9 — encerramento")))
SDR_RETORNO = (
    Touch(0, None, channel="whatsapp", label="SDR retorno — confirmação"),
    Touch(0, None, channel="ligacao", label="SDR retorno — ligação agendada"),
    Touch(0, None, channel="whatsapp", label="SDR retorno — reforço", offset_hours=1, conditional_result="45"),
    Touch(1, None, channel="ligacao", label="SDR retorno — D+1"),
    Touch(2, None, channel="whatsapp", label="SDR retorno — D+2"),
    Touch(3, None, channel="whatsapp", label="SDR retorno — final"))
CADENCES = {"BDR_CONTATO": BDR_CONTACT, "BDR_RECUPERAR": BDR_RECUPERAR, "SDR_TENTATIVA": SDR_TENTATIVA, "SDR_RETORNO": SDR_RETORNO}

# Ao esgotar a sequência sem contato, o negócio segue para Recuperar / F-Up.
EXHAUSTION_STAGE = {"BDR_CONTATO": {"category_id": 23, "stage_id": "C23:PREPARATION"}, "BDR_RECUPERAR": {"category_id": 23, "stage_id": "C23:APOLOGY"}, "SDR_TENTATIVA": {"category_id": 0, "stage_id": "C0:UC_XXPI8O"}, "SDR_RETORNO": {"category_id": 0, "stage_id": "C0:UC_XXPI8O"}}


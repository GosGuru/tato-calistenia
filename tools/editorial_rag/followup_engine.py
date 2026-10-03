"""Follow-up qualification and proposal engine for ManyChat leads.

Provides isolated classification, rule evaluation and draft generation
without touching or mutating the primary setter conversational state.
"""
import json
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from .api_runner import create_runner, ProviderConfig
from .followup_rules import FOLLOWUP_SYSTEM_PROMPT


class LeadMessage(BaseModel):
    model_config = ConfigDict(extra='ignore')
    sender: str  # 'lead' | 'tato' | 'system'
    text: str
    date: Optional[str] = None


class LeadRecord(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str
    name: str
    handle: Optional[str] = None
    last_date: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    messages: List[LeadMessage] = Field(default_factory=list)


class FollowupProposal(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str
    name: str
    handle: Optional[str] = None
    last_date: Optional[str] = None
    eligible: bool
    reason: str
    followup_number: int = 0
    pending_topic: str = ''
    draft: str = ''
    selected: bool = False
    status: str = 'pending'  # 'pending' | 'sending' | 'sent' | 'skipped' | 'failed'
    sent_text: Optional[str] = None
    error: Optional[str] = None


DISQUALIFYING_TAGS = {'no califica', 'no_califica', 'agendado', 'agendo', 'menor', 'spam'}


def count_consecutive_tato_followups(messages: List[LeadMessage]) -> int:
    """Count how many consecutive outbound messages Tato sent at the end of the history."""
    count = 0
    for m in reversed(messages):
        if m.sender == 'system':
            continue
        if m.sender == 'tato':
            count += 1
        else:
            break
    return count


def format_history_for_eval(lead: LeadRecord) -> str:
    lines = [f"LEAD: {lead.name} (@{lead.handle or 'sin_handle'})", f"ETIQUETAS: {', '.join(lead.tags) or 'ninguna'}", "HISTORIAL COMPLETO:"]
    for m in lead.messages:
        who = 'Prospecto' if m.sender == 'lead' else 'Tato' if m.sender == 'tato' else 'Sistema'
        when = f" [{m.date}]" if m.date else ""
        lines.append(f"- {who}{when}: {m.text}")
    return "\n".join(lines)


def evaluate_lead_static(lead: LeadRecord) -> Optional[FollowupProposal]:
    """Fast deterministic eligibility pre-checks before calling an LLM."""
    lower_tags = {t.lower().strip() for t in lead.tags}
    if any(dt in lower_tags for dt in DISQUALIFYING_TAGS):
        return FollowupProposal(
            id=lead.id,
            name=lead.name,
            handle=lead.handle,
            last_date=lead.last_date,
            eligible=False,
            reason="Excluido por etiqueta (no califica o agendado)",
            selected=False,
        )

    if not lead.messages:
        return FollowupProposal(
            id=lead.id,
            name=lead.name,
            handle=lead.handle,
            last_date=lead.last_date,
            eligible=False,
            reason="Historial vacío",
            selected=False,
        )

    consecutive_tato = count_consecutive_tato_followups(lead.messages)
    if consecutive_tato >= 2:
        return FollowupProposal(
            id=lead.id,
            name=lead.name,
            handle=lead.handle,
            last_date=lead.last_date,
            eligible=False,
            reason="Límite alcanzado: ya tiene 2 seguimientos sin respuesta",
            followup_number=consecutive_tato,
            selected=False,
        )

    # Check for obvious clear rejections in lead's latest message
    last_lead_msgs = [m for m in lead.messages if m.sender == 'lead']
    if last_lead_msgs:
        last_text = last_lead_msgs[-1].text.lower()
        if any(r in last_text for r in ['no me interesa', 'no me escribas', 'borrame', 'no quiero saber nada', 'no gracias']):
            return FollowupProposal(
                id=lead.id,
                name=lead.name,
                handle=lead.handle,
                last_date=lead.last_date,
                eligible=False,
                reason="Rechazo claro del lead en el último mensaje",
                selected=False,
            )

    return None


def clean_draft_line(text: str) -> str:
    """Enforce single line, no quotes, ending in ? if active."""
    clean = text.strip().strip('"\'`')
    clean = re.sub(r'[\r\n]+', ' ', clean).strip()
    if clean and not clean.endswith('?') and not clean.endswith('.'):
        clean += '?'
    return clean


async def evaluate_lead_llm(lead: LeadRecord, provider_config: Optional[ProviderConfig] = None) -> FollowupProposal:
    """Evaluate lead using LLM with isolated followup rules."""
    static_result = evaluate_lead_static(lead)
    if static_result is not None:
        return static_result

    history_str = format_history_for_eval(lead)
    prompt = f"{FOLLOWUP_SYSTEM_PROMPT}\n\nAnalizá este contacto y devolvé únicamente el JSON:\n\n{history_str}"

    cfg = provider_config or ProviderConfig(provider='deepseek', model='deepseek-chat')
    runner = create_runner(cfg)

    try:
        raw_output = await runner(prompt)
        # Parse JSON from output
        json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
        if not json_match:
            raise ValueError(f"No valid JSON in model output: {raw_output[:100]}")
        data = json.loads(json_match.group(0))

        is_eligible = bool(data.get('eligible', False))
        draft = clean_draft_line(str(data.get('draft', ''))) if is_eligible else ''

        return FollowupProposal(
            id=lead.id,
            name=lead.name,
            handle=lead.handle,
            last_date=lead.last_date,
            eligible=is_eligible,
            reason=str(data.get('reason', '')),
            followup_number=int(data.get('followup_number', 1 if is_eligible else 0)),
            pending_topic=str(data.get('pending_topic', '')),
            draft=draft,
            selected=is_eligible,
        )
    except Exception as e:
        return FollowupProposal(
            id=lead.id,
            name=lead.name,
            handle=lead.handle,
            last_date=lead.last_date,
            eligible=False,
            reason=f"Error al evaluar: {str(e)[:120]}",
            selected=False,
        )

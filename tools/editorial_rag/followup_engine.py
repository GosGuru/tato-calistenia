"""Follow-up qualification and proposal engine for ManyChat leads.

Provides isolated classification, rule evaluation and draft generation
without touching or mutating the primary setter conversational state.
"""
import asyncio
import inspect
import json
import re
import unicodedata
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

    # Check if Tato already sent FUP 2 (🙃)
    if lead.messages and lead.messages[-1].sender == 'tato':
        last_tato_text = lead.messages[-1].text.strip()
        if '🙃' in last_tato_text:
            return FollowupProposal(
                id=lead.id,
                name=lead.name,
                handle=lead.handle,
                last_date=lead.last_date,
                eligible=False,
                reason="Límite alcanzado: ya se envió FUP 2 (🙃) sin respuesta",
                followup_number=2,
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


def extract_first_name(full_name: str) -> Optional[str]:
    """Extract clean personal first name from contact name or handle."""
    if not full_name:
        return None
    # Normalize unicode to handle stylized fonts like ~𝑨𝒍𝒗𝒂𝒓𝒐 𝑻𝒐𝒎𝒂𝒔~
    normalized = unicodedata.normalize('NFKC', full_name)
    # Remove emojis, punctuation, brackets, symbols and underscores
    clean = re.sub(r'[^\w\s]|_', ' ', normalized)
    parts = clean.split()
    if not parts:
        return None
    candidate = parts[0].strip()
    if len(candidate) < 2 or candidate.isdigit():
        return None

    STOPWORDS = {
        'usuario', 'lead', 'instagram', 'contacto', 'user', 'info', 'cliente', 'admin',
        'profile', 'cuenta', 'pagina', 'oficial', 'official', 'the', 'a', 'an', 'and',
        'no', 'si', 'el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'en', 'por',
        'para', 'con', 'sin', 'yo', 'tu', 'su', 'mi', 'mis', 'tus', 'sus'
    }
    if candidate.lower() in STOPWORDS:
        return None

    # Clean trailing repeated letters from handles (e.g. benjaa -> benja)
    candidate = re.sub(r'([a-zA-Z])\1+$', r'\1', candidate)
    # Strip trailing digits from handles (e.g. axel01 -> axel)
    candidate = re.sub(r'\d+$', '', candidate)
    if len(candidate) < 2:
        return None

    return candidate.capitalize()


def clean_draft_line(text: str) -> str:
    """Enforce single line, no quotes, no opening ¿, preserving 🙃."""
    clean = text.strip().strip('"\'`')
    clean = re.sub(r'[\r\n]+', ' ', clean).strip()
    if not clean:
        return ''
    if clean == '🙃' or clean.startswith('🙃'):
        return '🙃'
    # Strip opening question or exclamation marks
    clean = clean.lstrip('¿¡').strip()
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
        call_res = runner(prompt)
        if inspect.isawaitable(call_res):
            raw_output = await call_res
        else:
            raw_output = call_res
        # Parse JSON from output
        json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
        if not json_match:
            raise ValueError(f"No valid JSON in model output: {raw_output[:100]}")
        data = json.loads(json_match.group(0))

        is_eligible = bool(data.get('eligible', False))
        fup_num = int(data.get('followup_number', 1 if is_eligible else 0))
        reason = str(data.get('reason', '')).strip()

        # Safety override: lack of historical context must NEVER block FUP in ManyChat inbox
        if not is_eligible:
            lower_reason = reason.lower()
            is_blocked_by_context = any(w in lower_reason for w in [
                'insuficiente', 'ambiguo', 'poco contexto', 'sin contexto', 'falta de contexto',
                'solo hay un mensaje', 'del prospecto', 'esperando respuesta', 'sin mensaje saliente',
                'no fup', 'requiere respuesta', 'inicial'
            ])
            is_genuine_stop = any(w in lower_reason for w in ['rechazo', 'no califica', 'agendado', 'límite', 'limite', 'menor'])
            if is_blocked_by_context and not is_genuine_stop:
                is_eligible = True
                fup_num = 1
                reason = "Listo para FUP 1 (reactivación en bandeja Tú)"

        # Enforce Holly sequence strictly
        draft = ''
        if is_eligible:
            if fup_num == 2:
                draft = '🙃'
            else:
                first_name = extract_first_name(lead.name)
                if first_name:
                    draft = f"{first_name}?"
                else:
                    raw_draft = clean_draft_line(str(data.get('draft', '')))
                    draft = raw_draft if raw_draft and raw_draft != '?' else 'como va?'

        return FollowupProposal(
            id=lead.id,
            name=lead.name,
            handle=lead.handle,
            last_date=lead.last_date,
            eligible=is_eligible,
            reason=reason,
            followup_number=fup_num,
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

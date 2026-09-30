"""In-memory editorial experiment, not a runtime or a semantic evaluator."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

Phase = Literal["contexto", "destino", "brecha", "sentido", "disposicion", "ruta", "conversion"]
Status = Literal["candidate", "approved", "rejected", "deferred"]
PHASES = {"contexto", "destino", "brecha", "sentido", "disposicion", "ruta", "conversion"}


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected nonempty text")


def _identifier(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", value):
        raise ValueError("Expected an opaque identifier, not a path or quote")


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"\w+", text.casefold()))


@dataclass(frozen=True)
class Card:
    card_id: str
    provenance_id: str
    status: Status
    sanitized: bool
    phase: Phase
    gate: str
    situation: str
    last_assistant_move: str
    proposed_move: str
    positive_voice: str
    negative_repetition: str

    def __post_init__(self):
        for value in (self.card_id, self.provenance_id, self.gate,
                      self.last_assistant_move, self.proposed_move):
            _identifier(value)
        for value in (self.situation, self.positive_voice, self.negative_repetition):
            _text(value)
        if not isinstance(self.sanitized, bool) or not self.sanitized or self.phase not in PHASES:
            raise ValueError("Sanitized attestation and valid phase required")
        if self.status not in {"candidate", "approved", "rejected", "deferred"}:
            raise ValueError("Invalid card status")


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    text: str

    def __post_init__(self):
        if self.role not in {"user", "assistant"}:
            raise ValueError("Only sanitized conversation roles accepted")
        _text(self.text)


@dataclass(frozen=True)
class Conversation:
    sanitized: bool
    phase: Phase
    gate: str
    situation: str
    last_assistant_move: str
    messages: tuple[Message, ...]

    def __post_init__(self):
        if not isinstance(self.sanitized, bool) or not self.sanitized or self.phase not in PHASES:
            raise ValueError("Sanitized attestation and valid phase required")
        _identifier(self.gate)
        _identifier(self.last_assistant_move)
        _text(self.situation)
        if not isinstance(self.messages, tuple) or not self.messages:
            raise TypeError("Pass an immutable, nonempty sanitized message tuple")
        if not all(isinstance(message, Message) for message in self.messages):
            raise TypeError("Expected Message values, not paths or imports")

    @property
    def previous_assistant(self) -> str:
        return next((m.text for m in reversed(self.messages) if m.role == "assistant"), "")


def retrieve(cards: tuple[Card, ...], conversation: Conversation) -> Card | None:
    """Exact gate/phase filter, lexical overlap, move match, repetition penalty."""
    ranked = []
    ids = set()
    for card in cards:
        if not isinstance(card, Card):
            raise TypeError("Expected curated Card values")
        if card.card_id in ids:
            raise ValueError("Duplicate card ID")
        ids.add(card.card_id)
        if (card.status != "approved" or card.phase != conversation.phase
                or card.gate != conversation.gate):
            continue
        overlap = len(set(_tokens(card.situation)) & set(_tokens(conversation.situation)))
        if not overlap:
            continue
        score = 10 * overlap + 3 * (card.last_assistant_move == conversation.last_assistant_move)
        if conversation.previous_assistant and card.proposed_move == conversation.last_assistant_move:
            score -= 20
        ranked.append((score, card.card_id, card))
    return min(ranked, key=lambda item: (-item[0], item[1]))[2] if ranked else None


@dataclass(frozen=True)
class Guidance:
    card_id: str
    provenance_id: str
    positive_voice: str
    negative_repetition: str


@dataclass(frozen=True)
class Packet:
    variant: Literal["current", "editorial"]
    current_rules: str
    conversation: Conversation
    guidance: Guidance | None
    boundary: str = (
        "Current rules remain authoritative. Editorial guidance affects voice only, "
        "not phase, safety, offer or sequence. Compose from the current case; "
        "never copy guidance wording or use it as a response template."
    )


def packets(conversation: Conversation, cards: tuple[Card, ...],
            current_rules: str) -> tuple[Packet, Packet]:
    """Caller supplies current rules verbatim; no source-file loading."""
    _text(current_rules)
    card = retrieve(cards, conversation)
    guidance = None if card is None else Guidance(
        card.card_id, card.provenance_id, card.positive_voice, card.negative_repetition)
    return (Packet("current", current_rules, conversation, None),
            Packet("editorial", current_rules, conversation, guidance))


@dataclass(frozen=True)
class Signals:
    exact_previous: bool
    same_opening: bool
    shared_trigrams: int
    guidance_trigrams: int


def _trigrams(text: str) -> set[tuple[str, ...]]:
    tokens = _tokens(text)
    return {tokens[i:i + 3] for i in range(len(tokens) - 2)}


def _signals(output: str, packet: Packet) -> Signals:
    _text(output)
    previous = packet.conversation.previous_assistant
    a, b = _tokens(output), _tokens(previous)
    guidance_grams = set()
    if packet.guidance:
        guidance_grams = (_trigrams(packet.guidance.positive_voice)
                          | _trigrams(packet.guidance.negative_repetition))
    return Signals(bool(b) and a == b,
                   len(a) >= 2 and len(b) >= 2 and a[:2] == b[:2],
                   len(_trigrams(output) & _trigrams(previous)),
                   len(_trigrams(output) & guidance_grams))


@dataclass(frozen=True)
class Comparison:
    current: Signals
    editorial: Signals
    card_id: str | None


def compare(conversation: Conversation, cards: tuple[Card, ...], current_rules: str,
            runner: Callable[[Packet], str]) -> Comparison:
    """Two synchronous calls; external runner owns isolation and all side effects.

    Outputs are transient: the returned report contains counts/flags, never drafts.
    Exceptions propagate; no retry, persistence, logging or semantic verdict.
    """
    current, editorial = packets(conversation, cards, current_rules)
    return Comparison(_signals(runner(current), current),
                      _signals(runner(editorial), editorial),
                      editorial.guidance.card_id if editorial.guidance else None)

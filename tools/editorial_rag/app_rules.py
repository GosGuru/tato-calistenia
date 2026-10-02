"""Loader for the lean Railway DM app prompt pack.

Reads only the pack files next to this module (`base.md` and `cards.json`). It is
deliberately independent of the local setter rule sources: the offline bank hashes those
seven normative files and this module never opens, joins or snapshots them.
"""
import json
from dataclasses import fields as dataclass_fields
from pathlib import Path

if __package__:
    from .prototype import Card
else:
    from prototype import Card

PACK_DIR = Path(__file__).resolve().parent / 'app_rules'
BASE_PATH = PACK_DIR / 'base.md'
CARDS_PATH = PACK_DIR / 'cards.json'
# Mirrors the per-field text limit enforced by editorial_criteria._card.
MAX_FIELD_CHARACTERS = 2000
# Conservative character bound for the concatenated criterion_passage(): the embedder
# rejects passages over model_manifest.json max_tokens (512) and tokenization cannot run
# here, so every pack card must stay under this character budget.
MAX_PASSAGE_CHARACTERS = 1200
CARD_FIELDS = tuple(field.name for field in dataclass_fields(Card))
# The pack stores these as opaque identifiers, never as quotes or lead data.
OPAQUE_FIELDS = ('card_id', 'provenance_id', 'gate',
                 'last_assistant_move', 'proposed_move')
# Prose fields. prototype.Card validates `situation` with _text, not _identifier, so it
# must read as "Aplica cuando ... . No aplica cuando ... ." for retrieve() to match it.
TEXT_FIELDS = ('situation', 'positive_voice', 'negative_repetition')


def load_app_rules() -> str:
    """Always-on base prompt text: every invariant, no expressive content."""
    text = BASE_PATH.read_text(encoding='utf-8')
    if not text.strip():
        raise ValueError('Empty app base prompt')
    return text


def _cards_from_data(data) -> tuple[Card, ...]:
    """Validate an in-memory card list; any malformed card raises ValueError."""
    if type(data) is not list or not data:
        raise ValueError('App cards must be a nonempty JSON array')
    cards, seen = [], set()
    for index, item in enumerate(data):
        where = f'app card {index}'
        if type(item) is not dict:
            raise ValueError(where + ': expected an object')
        if set(item) != set(CARD_FIELDS):
            raise ValueError(where + ': fields must be exactly ' + ','.join(CARD_FIELDS))
        if type(item['card_id']) is str:
            where = 'app card ' + item['card_id']
        for name in OPAQUE_FIELDS + TEXT_FIELDS:
            value = item[name]
            if type(value) is not str or not value.strip() or '\0' in value:
                raise ValueError(where + ': invalid text for ' + name)
            if len(value) > MAX_FIELD_CHARACTERS:
                raise ValueError(where + ': ' + name + ' exceeds field limit')
            value.encode('utf-8')
        try:
            card = Card(**item)
        except (TypeError, ValueError) as error:
            raise ValueError(where + ': ' + str(error)) from None
        if card.card_id in seen:
            raise ValueError(where + ': duplicate card_id')
        seen.add(card.card_id)
        cards.append(card)
    return tuple(cards)


def load_app_cards() -> tuple[Card, ...]:
    """Validated Card instances from cards.json; malformed input raises ValueError."""
    try:
        data = json.loads(CARDS_PATH.read_text(encoding='utf-8'))
    except OSError as error:
        raise ValueError('app cards unavailable: ' + str(error)) from None
    except ValueError as error:
        raise ValueError('app cards are not valid JSON: ' + str(error)) from None
    return _cards_from_data(data)

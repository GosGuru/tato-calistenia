"""Immutable editorial integrity records, independent of activation or inference."""
import hashlib
import math
from dataclasses import dataclass, fields
from types import MappingProxyType

if __package__:
    from .model_setup import SPEC
    from .prototype import Card, _identifier
    from .supabase_reader import _json, _uuid
else:
    from model_setup import SPEC
    from prototype import Card, _identifier
    from supabase_reader import _json, _uuid

CARD_FIELDS = tuple(field.name for field in fields(Card))
CONTENT_FIELDS = ('owner_id', 'card_id', 'provenance_id', 'phase', 'gate', 'situation',
                  'last_assistant_move', 'proposed_move', 'positive_voice',
                  'negative_repetition', 'sanitized')
MODEL_METADATA = MappingProxyType({
    **{name: SPEC[name] for name in ('model', 'revision', 'spec_version',
                                    'preprocessing_version', 'runtime_version', 'dimensions')},
    'graph_sha256': next(item['hash'] for item in SPEC['files']
                         if item['path'] == 'onnx/model_quantized.onnx'),
})
ROW_FIELDS = frozenset(CARD_FIELDS) | {'owner_id', 'approval_id', 'fingerprint', 'embedding'} | MODEL_METADATA.keys()


def _card(card):
    if type(card) is not Card:
        raise ValueError('Invalid criterion card')
    card.__post_init__()
    for name in CARD_FIELDS:
        value = getattr(card, name)
        if name != 'sanitized':
            if type(value) is not str or len(value) > 2000 or '\0' in value:
                raise ValueError('Invalid criterion text')
            value.encode('utf-8')


def fingerprint(owner_id: str, card: Card) -> str:
    """SHA256 of concatenated decimal UTF-8 byte length + ':' + field bytes.

    No normalization, JSON, approval or status. Fixed CONTENT_FIELDS order is SQL ABI.
    """
    _uuid(owner_id)
    _card(card)
    digest = hashlib.sha256()
    for name in CONTENT_FIELDS:
        value = owner_id if name == 'owner_id' else getattr(card, name)
        if name == 'sanitized':
            value = 'true' if value else 'false'
        data = value.encode('utf-8')
        digest.update(str(len(data)).encode('ascii') + b':' + data)
    return digest.hexdigest()


def criterion_passage(card: Card) -> str:
    """Candidate content is allowed. Prefixing belongs exclusively to embed_passages."""
    _card(card)
    return '\n'.join(name + ': ' + getattr(card, name) for name in CONTENT_FIELDS[3:-1])


def validate_vector(value) -> tuple[float, ...]:
    if type(value) not in (list, tuple) or len(value) != 384:
        raise ValueError('Invalid vector dimensions')
    try:
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in value):
            raise ValueError('Invalid vector values')
        result = tuple(float(x) for x in value)
    except (ValueError, OverflowError, TypeError):
        raise ValueError('Invalid vector values') from None
    if abs(math.sqrt(math.fsum(x*x for x in result)) - 1) > 1e-4:
        raise ValueError('Invalid vector norm')
    return result


@dataclass(frozen=True)
class EmbeddingRecord:
    model: str
    revision: str
    spec_version: str
    preprocessing_version: str
    runtime_version: str
    dimensions: int
    graph_sha256: str
    vector: tuple[float, ...]

    def __post_init__(self):
        for name, expected in MODEL_METADATA.items():
            actual = getattr(self, name)
            if type(actual) is not type(expected) or actual != expected:
                raise ValueError('Embedding pin mismatch')
        if type(self.vector) is not tuple:
            raise ValueError('Immutable vector required')
        validate_vector(self.vector)


@dataclass(frozen=True)
class Criterion:
    owner_id: str
    card: Card
    approval_id: str
    fingerprint: str
    embedding: EmbeddingRecord

    def __post_init__(self):
        _card(self.card)
        _identifier(self.approval_id)
        if self.card.status != 'approved' or self.fingerprint != fingerprint(self.owner_id, self.card):
            raise ValueError('Unapproved or stale criterion')
        if type(self.embedding) is not EmbeddingRecord:
            raise ValueError('Invalid embedding record')
        self.embedding.__post_init__()


def parse_criterion(row: dict, expected_owner: str) -> Criterion:
    _uuid(expected_owner)
    if type(row) is not dict or set(row) != ROW_FIELDS or row['owner_id'] != expected_owner:
        raise ValueError('Invalid criterion row')
    if type(row['embedding']) is not str or len(row['embedding']) > 32768:
        raise ValueError('Invalid embedding serialization')
    record = EmbeddingRecord(**{name: row[name] for name in MODEL_METADATA},
                             vector=validate_vector(_json(row['embedding'])))
    return Criterion(row['owner_id'], Card(**{name: row[name] for name in CARD_FIELDS}),
                     row['approval_id'], row['fingerprint'], record)

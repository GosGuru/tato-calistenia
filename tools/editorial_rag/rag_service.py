"""Fresh owner-scoped criteria retrieval; query text and vectors stay local."""
from .editorial_criteria import Criterion
from .editorial_library import ranklocal, read_library
from .local_embedding import embed_query
from .raw_history import valid_raw_text

GUIDANCE_FIELDS = ('phase', 'gate', 'situation', 'last_assistant_move', 'proposed_move',
                   'positive_voice', 'negative_repetition')


def retrieve(auth, history):
    revision, state, jwt, config = auth.snapshot()
    if state != 'connected':
        return revision, (), {'status': state, 'count': 0}
    try:
        criteria = read_library(jwt, config)
        if not criteria:
            return revision, (), {'status': 'empty', 'count': 0}
        # Defense in depth, including trusted reader replacement in integration tests.
        for criterion in criteria:
            if type(criterion) is not Criterion or criterion.owner_id != config.owner_id:
                raise ValueError('Invalid criterion')
            criterion.__post_init__()
            if any(not valid_raw_text(getattr(criterion.card, name)) for name in GUIDANCE_FIELDS):
                raise ValueError('Invalid guidance text')
        ranked = ranklocal(criteria, embed_query(history), max_results=2)
        guidance = tuple({name: getattr(item.criterion.card, name) for name in GUIDANCE_FIELDS}
                         for item in ranked)
        return revision, guidance, {'status': 'supplied', 'count': len(guidance)}
    except Exception:
        return revision, (), {'status': 'unavailable', 'count': 0}

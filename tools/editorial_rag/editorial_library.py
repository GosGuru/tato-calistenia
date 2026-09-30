"""Bounded criteria-only GET and advisory local cosine ranking. No model calls."""
import math
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlencode

if __package__:
    from . import supabase_reader as legacy
    from .editorial_criteria import (
        MODEL_METADATA,
        ROW_FIELDS,
        Criterion,
        parse_criterion,
        validate_vector,
    )
    from .library_config import LibraryConfig
    from .model_setup import SPEC
else:
    import supabase_reader as legacy
    from editorial_criteria import (
        MODEL_METADATA,
        ROW_FIELDS,
        Criterion,
        parse_criterion,
        validate_vector,
    )
    from library_config import LibraryConfig
    from model_setup import SPEC

MAX_BYTES = 2 * 1024 * 1024
MAX_CRITERIA = 50


class LibraryError(RuntimeError):
    """Fixed, content-free read failure."""


def _read(jwt, config, transport):
    if type(config) is not LibraryConfig:
        raise ValueError('Validated library configuration required')
    config.__post_init__()
    if legacy._claims(jwt, config.project_url) != config.owner_id:
        raise ValueError('Owner mismatch')
    query = {'select': ','.join(sorted(ROW_FIELDS)), 'owner_id': 'eq.' + config.owner_id,
             'order': 'card_id.asc', 'limit': MAX_CRITERIA + 1}
    query.update({name: 'eq.' + str(value) for name, value in MODEL_METADATA.items()})
    url = config.project_url + '/rest/v1/editorial_runtime_library?' + urlencode(query)
    # LibraryConfig revalidation binds scheme, origin and fixed REST path above.
    request = urllib.request.Request(url, method='GET', headers={  # noqa: S310
        'apikey': config.publishable_key, 'Authorization': 'Bearer ' + jwt,
        'Accept': 'application/json', 'Accept-Encoding': 'identity'})
    with transport(request, timeout=legacy.TIMEOUT) as response:
        if (response.status != 200 or response.geturl() != url
                or response.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
            raise ValueError('Rejected response')
        body = response.read(MAX_BYTES + 1)
    if type(body) is not bytes or len(body) > MAX_BYTES:
        raise ValueError('Invalid response size')
    rows = legacy._json(body.decode('utf-8'))
    if type(rows) is not list or len(rows) > MAX_CRITERIA:
        raise ValueError('Invalid result count')
    criteria = tuple(parse_criterion(row, config.owner_id) for row in rows)
    if len({item.card.card_id for item in criteria}) != len(criteria):
        raise ValueError('Duplicate criteria')
    return criteria


def read_library(access_jwt, config, *, transport=None):
    """Claims are preflight only; Supabase validates signature. No history parameter.

    Test transport is trusted code. Timeout is socket-level, not a total deadline.
    """
    try:
        return _read(access_jwt, config, legacy._transport if transport is None else transport)
    except Exception:
        del access_jwt, config, transport
    raise LibraryError('Editorial library unavailable or rejected; no criteria returned')


@dataclass(frozen=True)
class RankedCriterion:
    rank: int
    similarity: float
    criterion: Criterion
    advisory: str = 'Conditional guidance only; not confidence, phase or permission to convert.'


def ranklocal(criteria, queryvectors, max_results=2):
    """Exact cosine; maximum over ALL query chunks, no threshold or phase filter."""
    if (type(criteria) not in (tuple, list) or len(criteria) > MAX_CRITERIA
            or type(queryvectors) not in (tuple, list)
            or not 1 <= len(queryvectors) <= SPEC['max_chunks']
            or type(max_results) is not int or not 1 <= max_results <= 2):
        raise ValueError('Invalid ranking bounds')
    queries = tuple(validate_vector(vector) for vector in queryvectors)
    seen, owners, scores = set(), set(), []
    for criterion in criteria:
        if type(criterion) is not Criterion:
            raise ValueError('Expected approved criterion')
        criterion.__post_init__()
        identity = criterion.card.card_id
        if identity in seen:
            raise ValueError('Duplicate criterion')
        seen.add(identity)
        owners.add(criterion.owner_id)
        vector = criterion.embedding.vector
        norm = math.sqrt(math.fsum(x*x for x in vector))
        score = max(math.fsum(x*y for x, y in zip(vector, query, strict=True)) /
                    (norm * math.sqrt(math.fsum(x*x for x in query))) for query in queries)
        scores.append((max(-1.0, min(1.0, score)), identity, criterion))
    if len(owners) > 1:
        raise ValueError('Mixed owners')
    scores.sort(key=lambda item: (-item[0], item[1]))
    return tuple(RankedCriterion(index+1, score, item)
                 for index, (score, _, item) in enumerate(scores[:max_results]))
